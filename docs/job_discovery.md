# Discovering new jobs

Run from the project directory containing the sole current application workbook:

```powershell
.\.venv\Scripts\python.exe -m job_search_assistant search
```

The search command reads every worksheet in the current workbook and historical
workbooks in `archive/`, including hidden sheets. It also excludes pending URLs
in `new_urls.txt`. It never edits or archives the application tracker. If multiple
current workbooks exist, supply `--workbook` explicitly.

The user-maintained `Rejected` tab is also an exclusion list. It can contain
plain posting URLs anywhere, with no headers or company/title fields required.
Hyperlinks and literal URLs in HYPERLINK formulas are read as well. Canonical URL
and recognized ATS identities exclude alternate links to the same posting.
The assessor carries this tab into each new workbook without assessing its rows
or changing its contents, including in the default compact export. Rejection
identities are retained in the search database and archived-workbook exclusions.

All search state is private under `.job-search-assistant-private/search/`:

- `discovery.sqlite3`: imported identities, findings, decisions, events, employer
  discovery list, source coverage and reporting history.
- `reports/`: timestamped Excel, CSV and Markdown reports. Keeping exports here
  prevents interference with the updater's sole-current-workbook selection.
- `logs/`: scheduled-run diagnostics.

The four workbook tabs are Recommended Jobs, Needs Verification, Rejected Jobs,
and Search Coverage. A search result is a lead, not an accepted recommendation.
Only fully reviewed Strong Fit / Good Fit roles with acceptable location,
supported material requirements and visible current application evidence qualify.
Missing salary is allowed, and there is no salary floor. Fit scores are ordinal
labels (Strong=4, Good=3), never hiring probabilities. Unknown posting dates remain
blank; crawl and update dates are not substituted. Fit sorts before recency.

Availability is checked before fit review. A current, explicit
employer closure notice rejects a role even when its description is missing.
HTTP 404/410 responses from a specific employer vacancy/application URL are
recorded as removed postings. A third-party missing page, missing careers index,
robots failure, HTTP 403/429, timeout or JavaScript-only page does not establish
closure; these remain unverified. Relevant roles with a full description can still
receive a grounded fit review while application status is unresolved; fit alone
cannot promote them to recommendations. Full public ATS descriptions are retained
when a subsequent JavaScript-only page provides less evidence. Previously supplied
grounded reviews remain subject to all export gates.
Export independently moves verified closures out of Needs Verification and into
Rejected Jobs. Rejected identities remain excluded on subsequent discovery runs.
An HTTP-successful page or visible Apply link alone never establishes acceptance.

Role and location exclusions run before uncertain-duplicate handling, again after
retrieval, during verification runs, and at export. Individual-contributor software
and security engineering roles do not belong in Needs Verification. Structured
foreign-only vacancy locations (including Remote Spain, Poland, US and UK) are
excluded; multi-country locations explicitly including Canada remain eligible for
full review. Missing location evidence remains unknown. Company office locations
in a Canadian role's description do not by themselves establish a restriction.
Director/Associate Director, engineering management, delivery, organizational
change, project and program leadership remain within scope; full requirements
and resume evidence determine fit, not title alone.

## Sources and limits

`search --plan` prints the title, specialization, board and employer discovery plan.
The public seed list spans SaaS, developer infrastructure, fintech, blockchain,
healthcare, commerce, consulting and Atlantic employers. Found employers and ATS
boards expand the persistent inventory. Sources include search-index discovery
for major boards and public Greenhouse, Lever and Ashby employer feeds. Other ATS
platforms are discovered through search and public role pages; authenticated or
undocumented internal endpoints are not accessed.

The direct search provider uses public DuckDuckGo HTML results without a paid API.
There is no guarantee that search engines index every posting. Robots checks,
bounded requests, per-host pacing and crawl delays apply. Access failures and
anti-bot challenges stop the affected source; no CAPTCHA or authentication bypass.
Host-level failure caching avoids hammering inaccessible sources. Coverage records
distinguish actual requests from queries skipped after a source failure.

Defaults: up to 200 search queries, 250 total HTTP requests (including robots),
and 100 fit-review calls. Use `--max-queries`, `--max-requests`, and `--max-ai-calls`
to change these budgets. Initial discovery title filtering is only a routing
filter; it does not substitute for full-description assessment. Most irrelevant
titles and non-posting documents are excluded before inference.

The configured private candidate input is loaded through the existing assessment
service, including its source-PDF fingerprint check. Direct corrections or search
preferences can be added to private `search/candidate-additions.md`. Search uses a
separate strict review schema and does not change the workbook assessor's earlier
location assumptions, ranking policy, protected statuses or saved assessments.
Codex receives the supplied candidate and role data only, without browsing or shell
tools. Model output must pass exact evidence quotation validation and all search
gates. Unknown material requirements require verification. Content hashes bind
review bundles to the precise role and candidate inputs.

## Duplicate checking and later runs

URL tracking parameters are removed while identity parameters remain. LinkedIn,
Greenhouse (including employer `gh_jid` links), Lever, Ashby, Workday, SmartRecruiters,
BambooHR, Zoho, Jobvite and iCIMS identities are recognized. Normalized company/title
matches are conservatively treated as already known; similar titles at the same
company require review. Different job IDs do not automatically prove novelty.
Unresolved employer aliases can still require human reconciliation.

Every discovered URL receives a stored decision and reason. Previously reported,
rejected and known duplicate vacancies remain excluded on future runs. Unverified
findings can be retrieved and assessed again; only newly qualified recommendations
are exported. Only the strongest new recommendation per company is exported by
default. Earlier decision events and source evidence remain in private history.
An OS-released file lock prevents overlapping manual/scheduled searches.

## Restricted-network execution

If local sockets are blocked, the application cannot access an assistant's connected
browser automatically. A connected-search run can instead save raw search responses
as private `captures/*.txt`, with matching `.meta.json` containing `queries`,
`checked_on`, and `method`. Capture headings use `Title (https://posting-url)`.
Search excerpts alone cannot qualify as verified full role descriptions.

```powershell
.\.venv\Scripts\python.exe -m job_search_assistant search --captures .job-search-assistant-private/search/captures --offline
```

An optional private `--reviews FILE.json` imports separately grounded reviews.
Each item contains a Posting dictionary, the search review schema, and an
`input_hash` from `review_hash(posting, resume)`. The engine revalidates every quote,
input hash, exclusion and eligibility gate. Supplying a review cannot bypass these
checks. Captures can include unavailable sources; do not claim direct board access
when only indexed evidence was available. Replaying an old bundle is not a fresh
vacancy check and should not be used as the daily unattended command.

## Weekday mornings on Windows

Optional installation in normal PowerShell (current signed-in user, no password or
paid cloud service):

```powershell
.\tools\schedule_search.ps1
```

Creates `JobSearchAssistantMorning` at 09:00 Monday-Friday in the machine's local
time zone. It runs only in the user's interactive session, with a hidden Python
window, a 20-call assessment budget, private logs and no application submissions.
It does not overwrite an existing task. `-At '08:30'` changes the installation time.
Inspect with `Get-ScheduledTask -TaskName JobSearchAssistantMorning`. Remove with
`Unregister-ScheduledTask -TaskName JobSearchAssistantMorning -Confirm:$false`.
Installation may require a normal desktop session if the sandbox denies scheduler
access. A sleeping/offline machine or signed-out user cannot guarantee a morning
run; StartWhenAvailable permits a later run when conditions allow.


## Mandatory current application-status verification

A job cannot appear on Recommended Jobs unless a job-specific employer/ATS
application form has been verified on the current local calendar date. This is
an independent program gate at both classification and export, separate from
AI fit judgments. An AI open verdict, a search snippet, a generic Apply button,
a public ATS listing alone, or an older cached page cannot satisfy it.

Proof records the current status, checked date, source URL, method and evidence.
The URL must identify the same vacancy. Third-party aggregator forms do not
establish employer acceptance. Connected-page evidence must explicitly have a
same-day crawl; otherwise it remains unverified even when it displays a form.
Verification expires at the next local calendar date. A fresh check failure
cannot establish acceptance. Nothing is submitted to an employer during checks.

The added report columns distinguish applicant tracking status (Not applied)
from the posting's application status (accepting/closed/unverified). These
checks never change the user's application tracker.

Recheck leads in the latest search report:

```powershell
.\.venv\Scripts\python.exe -m job_search_assistant search --verify-leads --max-verifications 100
```

Use `--input-report FILE.xlsx` to choose a specific search report. In a restricted
network environment, pass `--verification-captures DIRECTORY --offline` to process
connected public-page retrievals. Each private JSON capture contains `url`, `text`
(the complete connected retrieval including crawl metadata), and `checked_on`.
The program records every check in SQLite application_checks and writes a new
report without overwriting earlier outputs. Unchecked, inaccessible, stale,
ambiguous or unassessed cases stay out of Recommended Jobs. Confirmed acceptance
alone does not waive fit, location, mandatory requirements or duplicate gates.
