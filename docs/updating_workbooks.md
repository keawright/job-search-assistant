# Update an Excel queue from new URLs

Run commands from the project folder. A Python 3.11+ virtual environment with
the project installed is required. No API key is needed.

```powershell
cd "path\to\job-search-assistant"
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
notepad new_urls.txt
```

Put one complete URL per line in `new_urls.txt` and save it. Prefer the actual
employer posting. The file is ignored by Git. Run:

```powershell
.\.venv\Scripts\python.exe -m job_search_assistant update `
  --urls-file new_urls.txt
```

You can supply `--url "https://example.com/jobs/123"` instead, repeating the option
for more URLs. Omitting both URL options recalculates existing records only.
`--as-of 2026-10-15` supplies a fixed evaluation date; the default is local today.

Save and close Excel first. The default input is the sole `.xlsx` workbook in the
current folder. If more than one is present, the command asks you to select the
latest edited file explicitly with `--workbook`; it does not guess from timestamps.
The default output is a new timestamped workbook in the same folder. You can set
`--output "jobs-next.xlsx"` to choose a new filename. After a successful export,
older sibling workbooks move into `archive/` without overwriting previous backups.
Archived inputs are refused to prevent accidentally reverting your latest edits.

Open **Assistant queue** in the new workbook. The order is Applied, Outstanding,
Review, and **Rejected last**. Filter on Assistant section as needed. Outstanding is ordered by Assistant
priority. Review contains exclusions and input problems, with the original status
retained. Applied and Rejected always stay in their respective sections, including
records without URLs. Inspect review flags on every new opportunity.

## What URL reading does

The fetcher reads public HTTP/HTTPS HTML without authentication, checks every
redirect destination, pins connections to validated public IPs, restricts response
size and redirect count, and applies a request time budget. It does not use proxy
environment settings, cookies, browser automation, or compressed responses. DNS
resolution uses the operating system resolver and its timeout behavior.

Extraction prefers explicit Schema.org JobPosting data for company, title,
description, posting date, deadline, and remote-country eligibility. Remote without
an explicit country stays unknown. An office address alone does not prove required
attendance. A valid page does not prove the vacancy is open or the source official.
Automatic facts can still require review when the posting contains additional
restrictions not expressed in its structured metadata.

Without structured data, readable main/article text is retained with a warning.
Multiple postings on one page are not silently resolved to one opportunity.
Blocked, login-only, removed, JavaScript-only, and unsupported pages remain visible
with an error/review message. The tool does not bypass those restrictions or mark
a job closed merely because a request failed.

Full HTML and full extracted descriptions are saved to private JSON snapshots in
`.job-search-assistant-private/snapshots/` beside the output workbook. That directory
is ignored by Git. Excel displays up to 30,000 description characters; the snapshot
retains the entire extracted text and source. Do not publish snapshots.

## Add contextual assessments

New jobs start with unknown fit. A URL reader cannot establish competitiveness
without comparing the candidate's accomplishments to the requirements.

Edit these columns in Assistant queue:

| Editable column | Allowed content |
| --- | --- |
| Leadership fit, Technical fit, Career alignment, Opportunity quality | `strong`, `good`, `stretch`, `unsuitable`, `unknown` |
| Assessment evidence | Explain how accomplishments compare with role scope, technical/domain requirements, career goals, and growth. Required for known ratings. |
| Assessment strengths | One strength per line |
| Assessment gaps (JSON) | A JSON list, for example `[{"description":"Recent Rust development","severity":"manageable","evidence":"Posting lists Rust as an asset; candidate has adjacent platform leadership."}]` |
| Regular hands-on coding | `yes`, `no`, or blank/`unknown`; known values require Coding evidence |
| Manual priority | Positive integer: requested 1-based queue position |
| Working arrangement | `remote`, `hybrid`, `onsite`, or `unknown` |
| Remote countries | Comma-separated countries, e.g. `Canada, United States` |
| Office city | Required office city, when known |
| Relocation required | `yes`, `no`, or blank/`unknown` |
| Required work authorization | Authorization name matching your preference configuration |
| Location evidence | Evidence supporting the editable location fields; required for known location claims |
| Verification status | `open`, `closed`, `unverified`; known status requires Last verified |
| Last verified | An Excel date or ISO date `YYYY-MM-DD` |

Gap severity is `manageable`, `major`, or `fundamental`. Invalid or unsupported
assessment values stay in the workbook with review flags rather than being guessed.
These columns also provide the human fallback when automated URL reading fails.
You can paste a description in a separate user-maintained column and refer to it
in your evidence. Do not enter credentials into the workbook.

Save and close Excel, then run the command again using that **edited output** as
the next input and a **new** output name:

```powershell
.\.venv\Scripts\python.exe -m job_search_assistant update `
  --offline
```

This reads your edited Assistant queue and generates a new single-tab workbook.
The previous workbook, including any historical tabs, moves into `archive/`.
Only the new current workbook remains outside that folder. Never continue from an
older workbook if your latest tracking edits are in a newer one.

Application status is always a user-owned field. The command does not change
Applied or Rejected to Not applied, even during refresh or when you supply the
same posting URL again. Dates, notes, and outcome reasons are retained. Rejected
records with missing URLs or invalid assessments still appear at the bottom.
If the input changes during export, archiving stops and your edited input remains
in place; the command reports the conflict instead of choosing the stale result.
If Excel locks a file and archiving fails, close Excel and inspect the reported
current output and original input before retrying with an explicit source.

## Field ownership and preservation

- **Input file:** its bytes are not modified; after successful export it is moved
  into `archive/`. Existing output filenames are refused.
- **Existing tabs:** preserved in the byte-for-byte archived workbook. The current
  output normally contains only Assistant queue. Cross-sheet formulas stop this
  compact export rather than losing their references; use `--keep-history-tabs`
  if you deliberately need dependent historical tabs in the current output.
  Advanced Excel objects unsupported by openpyxl may not round-trip in regenerated
  tabs; the archived original remains the reference copy. Macro workbooks are
  not accepted. The supplied seed has no embedded drawing objects.
- **User columns:** statuses, notes, dates, outcomes, existing Apply order, assessment
  inputs, and custom columns are copied. Cell comments and hyperlinks are carried
  into the new queue. Relative formulas are translated when their row moves;
  complex cross-sheet formulas should be checked in Excel. Old Apply order is
  historical; the current order is Assistant priority.
- **Assistant columns:** generated facts, explanations, sections, priority, and
  flags are recomputed. Edit user columns rather than Assistant columns.
- **Dates:** known user Deadline/Posted date values take precedence over extracted
  dates. Unknown/unparseable dates do not earn urgency; warnings identify them.
  Excel dates and ISO dates are accepted; ambiguous free-text dates are not guessed.
- **Location:** any manual location inputs take complete precedence over extracted
  location facts. Fill the related fields and evidence together.
- **Legacy commentary:** old fit descriptions are retained, not converted to new
  criterion ratings. Equal unassessed records keep stable import order. Explicit
  legacy geography exclusions, closed/possibly closed listings, and future-only
  opportunities are held for review until explicit updated location/verification
  inputs supersede that historical finding. This avoids reviving old exclusions.
- **Duplicates:** repeated batch URLs and existing aliases are skipped after
  normalizing known tracking parameters. Different job query IDs remain distinct.
  Existing duplicate records are retained for review rather than merged. Company
  name alone is never a deduplication key. Cross-site aliases are not always
  detectable and require review.

By default only new unique URLs are fetched. `--refresh` also reads existing
posting URLs but does not replace user-owned company/title, tracking, assessment,
or location fields. `--offline` disables all fetching, even with `--refresh`.
Choose a different source tab with `--sheet "Application priorities"`; otherwise
the default is Assistant queue, Updated priorities, then Application priorities.
If the job-table headers differ substantially, the command stops for explicit
mapping rather than guessing. Unrecognized statuses are preserved for review.

## Candidate preferences

Copy `examples/preferences.json` to `data/private/preferences.json`, edit it, and
pass `--preferences data/private/preferences.json`. Only specified fields override
the library defaults. In particular, do not invent work authorization: use held
and explicitly unavailable authorization lists only for known facts.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests use synthetic workbooks and mocked HTTP responses. They cover tracking and
annotation preservation, repeat runs, human overrides, stale legacy exclusions,
duplicate reconciliation, failed reads, redirect address checks, private addresses,
response-size limits, structured extraction, and formula-injection protection.
No tests fetch real employer pages or require API keys. Real-site compatibility
varies; JavaScript-based ATS adapters and optional AI assessment remain future work.
