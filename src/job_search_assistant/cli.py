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
from .assessment import load_service


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


def _row_selection(value):
    rows = set()
    try:
        for part in value.split(","):
            bounds = part.strip().split("-")
            if len(bounds) > 2:
                raise ValueError
            start, end = int(bounds[0]), int(bounds[-1])
            if start < 2 or end < start or end > 1048576:
                raise ValueError
            rows.update(range(start, end + 1))
    except ValueError:
        raise argparse.ArgumentTypeError("Use Excel row numbers/ranges such as 98,101,103-105 (rows start at 2)")
    return rows


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
    update.add_argument("--resume", type=Path, help="Private UTF-8 resume text (.txt/.md); otherwise use saved AI configuration")
    update.add_argument("--ai-model", help="Assessment model override; Codex otherwise uses its default")
    update.add_argument("--max-ai-calls", type=int, help="Optional cap on all AI requests in this run (new/unassessed jobs uncapped by default)")
    update.add_argument("--no-ai", action="store_true", help="Reuse matching saved assessments without new AI requests")
    update.add_argument("--reassess", action="store_true", help="Request fresh automatic assessments instead of reusing saved results; manual inputs stay intact")
    update.add_argument("--offline", action="store_true", help="Import and rank without making network requests")
    update.add_argument("--refresh", action="store_true", help="Compatibility option: Not Applied and blank statuses are already checked by default")
    update.add_argument("--keep-history-tabs", action="store_true", help="Retain old tabs when cross-sheet formulas require them")
    update.add_argument("--reassess-rows", type=_row_selection,
                        help="Fresh assessments only for selected input-sheet Excel rows, e.g. 98,101,103-105; others use cache only")
    update.add_argument("--reassess-needed", action="store_true",
                        help="Fresh assessments only for unapplied jobs whose saved Apply order is Needs assessment or Needs review")
    args = parser.parse_args(argv)
    if (args.reassess_rows is not None or args.reassess_needed) and (args.reassess or args.offline or args.no_ai):
        parser.error("Targeted reassessment cannot be combined with --reassess, --offline, or --no-ai")
    if args.reassess_rows is not None and args.reassess_needed:
        parser.error("Choose --reassess-rows or --reassess-needed, not both")
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
        service = load_service(source.parent, offline=args.offline, no_ai=args.no_ai, resume_path=args.resume,
                               model=args.ai_model, max_calls=args.max_ai_calls, reassess=args.reassess)
        result = update_workbook(source, output, urls, as_of=args.as_of, sheet=args.sheet,
                                 candidate=_candidate(args.preferences), offline=args.offline, refresh=args.refresh,
                                 compact=not args.keep_history_tabs, assessment_service=service, reassess_rows=args.reassess_rows, reassess_needed=args.reassess_needed,
                                 progress=lambda message: print(message, flush=True))
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
    if service is not None:
        print(f"Contextual assessments: {service.created} new; {service.reused} reused; {service.calls} AI requests.")
        for issue, count in result.assessment_issues.items():
            print(f"Assessments unavailable ({count}): {issue}")
        if service.provider is None and not args.offline and not args.no_ai:
            print("OPENAI_API_KEY is not configured: matching saved assessments were used; other jobs remain Needs assessment.")
    print("Open Assistant queue. Unknown fit needs contextual assessment; a readable URL does not confirm an open vacancy.")
    return 0
