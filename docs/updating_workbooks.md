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

Open **Assistant queue** in the new workbook. The order is Interviewing, Applied, Outstanding,
Review, and **Rejected last**. Filter on Assistant section as needed. Outstanding is ordered by Assistant
priority. Review contains exclusions and input problems, with the original status
retained. Interviewing, Applied and Rejected always stay in their respective sections, including
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
- **User columns:** statuses, notes, dates, outcomes, assessment
  inputs, and custom columns are copied. Cell comments and hyperlinks are carried
  into the new queue. Relative formulas are translated when their row moves;
  complex cross-sheet formulas should be checked in Excel.
- **Apply order:** regenerated as consecutive numbers only for assessed actionable
  Not Applied (including blank/Outstanding) jobs and used to sort those rows.
  Entirely unassessed jobs display Needs assessment with no numeric Assistant
  priority; other review-blocked jobs receive no numeric recommendation either.
  Assistant assessment status distinguishes Complete, Partial, and Needs assessment.
  Legacy Why this fits/Gaps notes remain available as reassessment evidence but
  are not automatically converted to ratings. Interviewing jobs stay first, followed by Applied; Closed
  and Rejected stay at the bottom.
  Applied, Closed, Rejected, and other custom statuses display `-`. Use Manual
  priority to request a different position for an actionable job.
- **Applied aging:** every update, including offline, changes Applied to
  Elapsed-Rejected on or after its one-calendar-month anniversary. Applied Date,
  Date applied, or Application date supplies the date. Excel dates, ISO dates,
  and explicit month-name dates such as Oct-9-2026 are supported; ambiguous numeric
  dates are not guessed. If the next month lacks that day, use its last day.
  Missing, unreadable, and future dates retain Applied with a review flag.
  Elapsed-Rejected rows go below Rejected with a dash for Apply order; they are
  never fetched or searched. The explanation identifies this as a tracking
  assumption rather than an employer-confirmed rejection. All dates, notes,
  outcome fields, and annotations are retained. Other statuses are not aged.
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

By default new unique URLs and existing Not Applied or blank-status jobs are fetched.
Explicit visible closure notices change Application status to Closed. Closed jobs
are placed above Rejected and are never automatically fetched again. Applied,
Rejected, Interviewing, and all other statuses are left alone, even with `--refresh`.
Access failures leave the original status unchanged; see Assistant fetch issue and
Assistant review flags. Assistant availability checked on records the attempt date;
Assistant closure evidence records the notice and resolved URL. Failed requests,
missing metadata, and elapsed deadlines alone never mark a job Closed.
`--refresh` is now a compatibility option. Fetching existing posting URLs preserves
manual tracking, assessment, and location fields. `--offline` disables all fetching,
including alternative-link searches, even with `--refresh`.

For incomplete LinkedIn pages, a recognizable page title supplies company, role,
and location for a DuckDuckGo HTML search. At most three result pages are fetched;
exact normalized company/title metadata and visible location must match. A single
matching page is used; multiple matches are left for review. Source authority and
current availability remain unverified. Search snippets alone never close a job.
Assistant alternate URL stores the new source without replacing the original
posting URL; later checks use the alternate directly. Assistant discovery notes
and review flags explain blocked, empty, or ambiguous searches. Unknown company
placeholders and generated LinkedIn page titles may be repaired on existing rows,
while manual company/title values remain intact. Search identity and both original
and alternate fetched HTML are retained privately for traceability. If no company
and role can be extracted (for example a blocked new URL), no broad guess is made.
The search endpoint can be blocked or change format; this is a best-effort fallback.
Choose a different source tab with `--sheet "Application priorities"`; otherwise
the default is Assistant queue, Updated priorities, then Application priorities.
If the job-table headers differ substantially, the command stops for explicit
mapping rather than guessing. Unrecognized statuses are preserved for review.

## Candidate preferences

Automatic resume-based assessments can now be generated through signed-in Codex
and reused from private saved results. See [setup and behavior](automatic_assessment.md).
Manual criterion ratings take precedence. The generated assessment columns show
source, date, summary, resume/role quotations, strengths, gaps, uncertainties and
issues. Missing or failed assessment never receives a numeric Apply order.

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
varies; JavaScript-based ATS adapters remain future work. Optional Codex/API
assessment is implemented and tested with synthetic model responses; live inference
still requires a working login and network access in the user's normal terminal.


## Supplied alternate posting links

Put additional URLs for the same job in **Other source links** (or
**Other source links (URL)**), separated by spaces or newlines. A cell hyperlink
is also supported. When the primary posting fails or lacks a structured job
with a description, online updates try up to five distinct supplied links in
order before LinkedIn discovery. The first posting with structured employer and
role matching the known job identity and a description becomes the saved
**Assistant alternate URL**, used on subsequent updates. Original posting URLs
and manual tracking fields are preserved. Explicit closure notices on the main
page are retained rather than replaced by an alternate.

Different employers/roles, ambiguous posting pages, and unreadable links are
skipped with notes in **Assistant discovery notes**. Unknown job identities need
manual clarification before an alternate can be matched safely. Location,
source authority, and current vacancy still require verification. Offline updates
and protected statuses (including Interviewing) never fetch alternate links.


## Location assumptions

At the user's request, workbook assessments and application ordering assume
location will be acceptable. Earlier Halifax/location holds no longer prevent
fit assessment. Actual location evidence and original notes remain intact;
**Assistant review flags** warns that location needs checking, and
**Assistant location eligibility** says **assumed acceptable** where applicable.
This is a ranking assumption, not verified permission to work remotely or an
employer waiver. Availability, duplicate, and insufficient-role-evidence holds
still apply. The standalone ranking library retains its normal location checks
unless a job explicitly enables this assumption.


## CGI future opportunities and renewed availability

CGI Future opportunity rows are assessed and ranked at the user's request,
with a warning that a current staffed vacancy is not confirmed. Original notes
remain unchanged. Other legacy closed/unavailable holds remain in place.

After confirmation that applications are accepted, set Verification status to
`open` and Last verified to the confirmation date. Confirmation on or after an
old deadline supersedes that deadline for ranking; the date remains preserved
with a review flag and no deadline urgency boost. Record the confirmation source
in Availability confirmation or personal notes. A secondary URL alone does not
establish open availability. Future/invalid verification dates remain rejected.
