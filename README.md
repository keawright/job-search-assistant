# Job Search Assistant

**Which job should I apply to next?** A small Python engine orders an existing
list of opportunities using evidence-backed fit assessments, location eligibility,
bounded urgency, and explicit manual adjustments. Every result retains its reasons,
unknowns, original record, and ranking-policy version.

## Current scope

Version 0.2 includes a deterministic ranking library and a command-line workflow
that reads posting URLs and exports an updated Excel queue. It preserves the input
workbook and original tracking columns. Older workbooks and their tabs go in
`archive/`; the current workbook normally contains one Assistant queue tab. New facts use structured
posting metadata; contextual fit remains evidence-backed human input.
Optional automatic resume-based assessment now uses your signed-in Codex CLI;
a direct OpenAI API provider is also available. Personal resumes, assessments,
workbooks and snapshots stay in ignored private files. There is no UI.

## Quick start (PowerShell)

Use Python 3.11 or newer. Run these commands from `Job Search Assistant`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe examples/synthetic_jobs.py
```

On macOS/Linux use `.venv/bin/python` instead. No activation step is needed.
The example uses fictional companies and `example.com` URLs; it never fetches them.
The older good-fit opportunity ranks before the newer strong-fit opportunity,
while Interviewing precedes Applied and a confirmed closed job stays outside the queue.

## Update your workbook from URLs

Add one employer posting URL per line to the local `new_urls.txt` file. Then run:

```powershell
.\.venv\Scripts\python.exe -m job_search_assistant update `
  --urls-file new_urls.txt
```

The command reads the sole current `.xlsx` file in this folder, writes a new
timestamped workbook, then moves older workbooks into `archive/`. Open
**Assistant queue** in the new file. Interviewing comes first, then Applied, Outstanding, Review,
and **Rejected at the very bottom**. Existing output names are refused.
New jobs have extracted facts and review
flags; configured automatic assessment compares their role evidence with your
resume. Unchanged saved assessments are reused. See
[automatic assessment and login setup](docs/automatic_assessment.md).
**Apply order** is recalculated from evidence-backed contextual assessment inputs.
Assessed actionable jobs receive numbers and are sorted by that number; entirely
unassessed jobs show **Needs assessment**, with no numeric Assistant priority.
Review-blocked jobs are not given a numeric application recommendation. The
**Assistant assessment status** column distinguishes Complete, Partial, and
Needs assessment. Interviewing jobs appear first, followed by Applied; Closed and Rejected remain at the bottom and display `-` for Apply order.
On every update (including offline), Applied jobs at least one calendar month past
their Applied Date become **Elapsed-Rejected** and move to the very bottom with
`-` for Apply order. Month-end anniversaries use the last day of the next month.
This is an aging convention, not confirmation from the employer. Missing,
unreadable, or future application dates keep Applied and receive a review flag.
Dates, notes, and outcome fields are preserved; Interviewing and other statuses
are not aged automatically.
Save and close your current workbook before running again. Manual Applied/Rejected
statuses, dates, notes, and outcomes are retained exactly. If several workbooks
are present, use `--workbook` to identify the latest edited file; no age-based guess
is made. Normal updates also check existing **Not Applied** and blank-status jobs.
An explicit visible closure notice changes Application status to **Closed**;
Closed jobs appear above Rejected and are not checked again. Other statuses are
never fetched or changed. Access failures leave the status unchanged and appear
in **Assistant fetch issue** and **Assistant review flags**. The check date and
closure evidence have dedicated Assistant columns. Missing metadata, a passed
deadline, and failed requests do not prove closure. `--offline` disables URL reads;
`--refresh` remains accepted for compatibility with earlier commands.

Incomplete LinkedIn pages now trigger a bounded public web search using the company,
role, and location parsed from the page title. A single alternative with matching
structured company/title and visible location is saved in **Assistant alternate URL**
and used for extraction and later checks. The original posting URL is retained.
**Assistant discovery notes** explains the result; ambiguous, blocked, or mismatched
searches remain for review. Unknown-company placeholders and LinkedIn page titles
can be repaired on existing unapplied rows; other manual fields are preserved.
The search uses DuckDuckGo's public HTML page without an API key and may be blocked
or change format. Matching does not establish that the source is official or that
the role is open. Offline runs never search.

See [the workbook guide](docs/updating_workbooks.md) for editable assessment columns,
field ownership, candidate preferences, duplicate handling, and fetch limitations.

## Using the library

```python
from datetime import date
from job_search_assistant import CandidatePreferences, Job, prioritize

jobs = [Job(
    id="example-1",
    company="Example Company",
    title="Engineering Manager",
    url="https://example.com/jobs/1",
)]
result = prioritize(jobs, CandidatePreferences(), as_of=date(2026, 10, 15))
for row in result.outstanding:
    print(row.priority, row.overall_fit, row.reasons, row.review_flags)
```

This record stays **unknown**, not unsuitable: no assessment or location evidence
has been supplied. See `examples/synthetic_jobs.py` for complete assessments.

## Inputs and explanations

- `CandidatePreferences`: target roles, strengths, leadership preference, country,
  allowed remote countries, acceptable office cities, relocation willingness,
  and explicitly held/unavailable work authorizations. No salary cutoff.
- `Job`: stable ID, company, title, URL, original description and additional source
  URLs, application status, availability verification, known dates, location,
  assessment, optional manual queue position, and arbitrary user `tracking` fields.
- `Assessment`: leadership fit, technical fit, career alignment, opportunity quality,
  strengths, evidenced gaps, and any evidenced regular coding requirement.
  A known contextual rating requires evidence comparing requirements with
  professional accomplishments. Target roles and strengths guide this human
  assessment. The configured model provider compares role evidence and resume
  accomplishments; no keyword-count fit score is used.
- `RankingPolicy`: version and configurable posting-age/deadline windows.
- `RankingResult`: Applied, actionable Outstanding, Rejected, and separate Excluded
  records. `ordered` returns the first three sections in that order. **Always
  retain `excluded` as well** so review records are not lost.

Every ranked row exposes its original job, overall fit, location eligibility,
recommended priority, reasons, review flags, rubric version, and evaluation date.
Strengths, gaps, criterion evidence, original text, and source URLs remain available
on `row.job`. No user record is modified or saved by the engine.

## Ranking rules and limitations

See [the exact rules](docs/prioritization_rules.md). Fit is categorical, not a
probability of an interview. Rules are transparent policy choices, not statistically
calibrated hiring predictions. Contextual input quality remains essential.

Unknown availability is flagged; confirmed closed jobs are excluded. A passed
deadline is held for verification without claiming the posting is closed.
Manual queue positions cannot change application status or bypass an exclusion.
Duplicate IDs or normalized URLs raise an error for explicit reconciliation.

URL reading cannot verify that a source is official or guarantee a job is still open.
Users must supply truthful verification dates and source evidence. Prefer employer
career pages. Full fetched HTML and extracted text are retained in private snapshots.

## Tests

`python -m pytest` covers status precedence, preserved tracking data, closed jobs,
duplicates, company overlaps, deterministic ties, posting-age boundaries, deadlines,
bounded urgency, location restrictions, work authorization, configurable preferences,
technical gaps, coding preferences, missing data, evidence validation, and manual
overrides. Workbook and ingestion tests also cover repeat updates, source tabs,
annotations, duplicate aliases, fetch failures, private-address redirects,
response-size limits, structured metadata, and formula-injection protection.
Tests use fixed dates and synthetic records; no live sites or API keys.

## Public repository and private data

Keep all project material in this folder. `.gitignore` excludes personal workbooks,
CSV files, databases, private data, environment files, and common key files.
Private URL lists and `.job-search-assistant-private/` snapshots are also excluded.
Only synthetic examples and test records belong in the public repository.
Ignore rules do not remove files already tracked by Git or detect every secret;
review staged content before publishing. Run `python tools/check_repository.py`
to check the actual Git index before every commit. See
[publication checks](docs/publishing.md). No license has been selected yet.

## Architecture and next steps

See [architecture](docs/architecture.md). Next phases:

1. Add SQLite persistence, schema migrations, and FastAPI endpoints.
2. Add a React/TypeScript table and editing interface.
3. Extend URL compatibility with targeted ATS adapters and availability verification.
4. Add CSV export and richer spreadsheet reconciliation where needed.
5. Expand evaluation coverage and live compatibility for the implemented assessment providers.

GitHub Actions runs the tests and repository privacy guard on pushes and pull
requests. Future credentials belong in backend environment
variables or CI secret storage, never in browser bundles or committed files.


Additional links for the same job can go in **Other source links**, separated by
spaces or newlines. If the main posting cannot provide a structured description,
online updates try these links and use the first matching employer/role posting.
See [supplied alternate links](docs/updating_workbooks.md#supplied-alternate-posting-links).


For fresh AI assessments of selected input-sheet Excel rows, use
`update --reassess-rows 98,101,103-105`. Other jobs reuse matching assessments
without new AI calls. See [selected reassessment](docs/automatic_assessment.md#reassess-selected-rows).


Use `update --reassess-needed` to retry jobs whose saved **Apply order** is
**Needs assessment** or **Needs review**, regardless of row position. Other jobs
reuse cached assessments; protected statuses and existing review holds remain.
