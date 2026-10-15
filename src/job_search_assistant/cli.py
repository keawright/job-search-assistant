"""Command-line workbook update workflow."""

import argparse
from dataclasses import fields
from datetime import date, datetime
import json
from pathlib import Path
import sys

from .models import CandidatePreferences
from .archive import archive_older_workbooks, current_workbook, fingerprint
from .workbook import update_workbook


def _candidate(path):
    if path is None:
        return CandidatePreferences()
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("Preferences must be a JSON object")
    defaults = CandidatePreferences()
    for key, value in data.items():
        if key not in {f.name for f in fields(defaults)}:
            raise ValueError(f"Unknown candidate preference: {key}")
        expected = getattr(defaults, key)
        if isinstance(expected, tuple):
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise ValueError(f"{key} must be a JSON list of strings")
            data[key] = tuple(value)
        elif type(value) is not type(expected):
            raise ValueError(f"Wrong preference type: {key}")
    held = {s.casefold() for s in data.get("work_authorizations", defaults.work_authorizations)}
    missing = {s.casefold() for s in data.get("unavailable_work_authorizations", defaults.unavailable_work_authorizations)}
    if held & missing:
        raise ValueError("Work authorization cannot be both held and unavailable")
    return CandidatePreferences(**data)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Add posting URLs and export a new, reviewable Excel application queue.")
    sub = parser.add_subparsers(dest="command", required=True)
    update = sub.add_parser("update", help="Read an existing workbook and write a new workbook")
    update.add_argument("--workbook", type=Path, help="Latest edited workbook; defaults to the sole .xlsx in the current folder")
    update.add_argument("--output", type=Path, help="New filename in the same folder; defaults to a timestamped filename")
    update.add_argument("--urls-file", type=Path, help="UTF-8 text: one URL per line; # comments allowed")
    update.add_argument("--url", action="append", default=[], help="Repeat for multiple posting URLs")
    update.add_argument("--sheet", help="Default: Assistant queue, then Updated priorities, then Application priorities")
    update.add_argument("--as-of", type=date.fromisoformat, default=date.today(), help="YYYY-MM-DD; defaults to local today")
    update.add_argument("--preferences", type=Path, help="Private JSON candidate preferences")
    update.add_argument("--offline", action="store_true", help="Import and rank without making network requests")
    update.add_argument("--refresh", action="store_true", help="Also fetch existing posting URLs; tracking fields remain untouched")
    update.add_argument("--keep-history-tabs", action="store_true", help="Retain old tabs when cross-sheet formulas require them")
    args = parser.parse_args(argv)
    try:
        source = (args.workbook or current_workbook(Path.cwd())).resolve()
        output = (args.output or source.parent / f"jobs-updated-{datetime.now():%Y%m%d-%H%M%S-%f}.xlsx").resolve()
        if source.parent != output.parent:
            raise ValueError("Keep the new workbook in the same folder as the current workbook; older versions go in archive/")
        if source.parent.name.casefold() == "archive":
            raise ValueError("Use the current workbook outside archive/ so your latest manual edits are retained")
        before = fingerprint(source)
        urls = args.url
        if args.urls_file:
            urls += args.urls_file.read_text(encoding="utf-8-sig").splitlines()
        result = update_workbook(source, output, urls, as_of=args.as_of, sheet=args.sheet,
                                 candidate=_candidate(args.preferences), offline=args.offline, refresh=args.refresh,
                                 compact=not args.keep_history_tabs)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(f"Created: {result.output}")
    try:
        if fingerprint(source) != before:
            raise OSError("Input workbook changed during the update. Your edited source is retained; rerun using it.")
        archived = archive_older_workbooks(result.output)
    except (OSError, ValueError) as exc:
        print(f"New workbook created, but archiving did not complete: {exc}. Close Excel before retrying.", file=sys.stderr)
        return 2
    print(f"Imported {result.imported}; added {result.added}; repeated URLs skipped {result.skipped_urls}.")
    print(f"Outstanding {result.outstanding}; held for review {result.review}; URL reads failed {result.fetch_failures}.")
    print(f"Archived {len(archived)} older workbooks in {result.output.parent / 'archive'}.")
    print("Open Assistant queue. Unknown fit needs contextual assessment; a readable URL does not confirm an open vacancy.")
    return 0
