# Resume-based assessment

Normal updates can now generate contextual fit assessments with a signed-in Codex
CLI. Matching saved assessments are reused before any model call. The ranker uses
these ratings for Apply order; unassessed jobs never receive a numeric recommendation.

## Local setup

Install Codex CLI and sign in from your normal PowerShell terminal:

```powershell
codex.cmd login
codex.cmd login status
```

`codex.cmd` avoids PowerShell's script-execution-policy restriction on npm's
`codex.ps1`. The application invokes the installed Node entry point directly on
Windows. It never reads, copies, or exports Codex login credentials. On macOS or
Linux, use `codex login`. Authentication and account usage limits are managed by
Codex; this provider does not require a separate OpenAI API key. See the official
[authentication](https://learn.chatgpt.com/docs/auth) and
[noninteractive execution](https://learn.chatgpt.com/docs/non-interactive-mode)
documentation.

Keep an extracted UTF-8 resume in the private folder and configure the private
`.job-search-assistant-private/assessment-config.json`:

```json
{
  "enabled": true,
  "provider": "codex",
  "resume_path": ".job-search-assistant-private/resume.txt",
  "model": null,
  "max_refresh_calls": 20
}
```

Keep resume text and configuration local; use synthetic data in public examples.
Omit contact details from assessment input. If configuration also records
`resume_source` and `resume_source_sha256`, a changed source PDF stops the update
until its private extracted text and source hash are refreshed. This avoids
silently continuing with an old resume. An explicit `--resume` accepts UTF-8 text
or Markdown; it does not parse a PDF or persist a new configuration.

## Run

The usual command automatically reuses saved results and assesses missing/changed
inputs when configured:

```powershell
.\.venv\Scripts\python.exe -m job_search_assistant update --urls-file new_urls.txt
```

Newly added jobs are assessed before existing jobs. Normal updates attempt every
new or still-unassessed job without a default total call cutoff. Matching saved
assessments are reused. Jobs with a previous saved assessment whose inputs changed
share a separate allowance of 20 refresh attempts per run, configured with
`max_refresh_calls`. Failed attempts count against allowances. Previous assessment
history is identified by the stable job ID, including earlier cache revisions.
Manual ratings and protected application statuses remain intact.

An explicit `--max-ai-calls` caps all AI requests, including new jobs and refreshes;
it does not increase the separate refresh allowance. For existing configurations,
legacy `max_calls` is used as the refresh allowance only; `max_refresh_calls` takes
precedence. No private configuration edit is needed to enable uncapped initial
assessments. The CLI reports assessment progress and summarizes unavailable results.
Missing evidence, provider failures, explicit limits, or account limits may still
leave jobs needing assessment.

Useful options:

- `--offline`: no posting, search, or AI network requests; use matching saved assessments.
- `--no-ai`: posting checks still run; no new AI requests, but saved results are reused.
- `--reassess`: request fresh assessments instead of reusing saved results. Earlier
  saved revisions are retained. Explicit manual ratings are still preserved.
- `--max-ai-calls 5`: cap all model requests in this run (optional, maximum 200).
  The cap includes failed attempts. Additional jobs remain Needs assessment until
  a later run. Codex calls use account limits; API calls use API billing.
- `--ai-model MODEL`: optional model override. The Codex provider otherwise uses
  its built-in default with user configuration disabled for this controlled task.

Codex receives the resume, the specific job's saved description, selected earlier
review notes, and candidate preferences over stdin. It runs with a read-only
sandbox, no shell tool, disabled web search and delegation, no approval prompts,
and ephemeral sessions. A JSON schema constrains its result. Application code
alone writes the workbook. Normal user configuration/MCP servers are not loaded.

## Evidence and ordering

Each known criterion must include a contextual rationale and actual quotations
from both the resume and role evidence. The application checks the quotations
against the provided text before saving ratings. Invalid responses, login errors,
timeouts, insufficient information and exhausted call limits never create scores.
Saved results are checked again on reuse and are keyed to the resume, preferences,
job identity/evidence and assessment prompt version. Resume, preference or role
changes therefore require reassessment; timestamps and status changes alone do not.

Legacy review notes may support a provisional assessment. Their limitations must
appear in uncertainties; they are not relabelled as newly verified employer facts.
Similar-jobs recommendations are removed from LinkedIn description input. Missing
skills on a resume are not proof of inability. AI quotation validation establishes
source grounding, not factual truth or the correctness of the model's judgment.

The workbook shows assessment source, date, summary, quoted evidence, strengths,
gaps, uncertainties, and any issue. Complete means all four criteria are rated;
it does not mean every employer requirement or the vacancy is verified. Partial
ratings remain flagged. Existing manual criterion ratings take precedence over
automatic assessment as a whole and are never overwritten. Other user tracking
fields remain unchanged.

Only Not Applied and blank-status jobs enter automatic assessment. Applied, Closed,
Rejected, Elapsed-Rejected, Interviewing and other manual statuses never trigger
model requests. Vacancy/data exclusions remain held for review, except CGI future opportunities
which are assessed with an explicit caveat.
Assessment itself never changes status or infers vacancy availability. Policy 1.1
orders by contextual fit with bounded urgency; workbook ranking assumes acceptable location with visible warnings. Standalone
library ranking retains location exclusions unless explicitly overridden. See the prioritization policy.

## Optional direct API provider

Set `provider` to `openai`, set a structured-output-capable `model` (default
`gpt-5.4-mini`), and configure `OPENAI_API_KEY` in your environment. Do not put keys
in configuration or source files. This optional path posts to the fixed OpenAI
Responses API endpoint with `store: false`, no tools, and a strict output schema.
It uses Python's standard HTTPS library and needs no SDK package. See
[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

Offline tests cover request contracts and failures with synthetic providers. A
successful live CLI/API assessment cannot be claimed when authentication or
network access is unavailable in the execution environment.


## Reassess selected rows

Use `--reassess-rows` for fresh AI assessments of specific Excel rows in the
input sheet (including the header when counting, so jobs start at row 2):

```powershell
.\.venv\Scripts\python.exe -m job_search_assistant update --workbook jobs.xlsx --reassess-rows 2,5-7
```

Comma-separated row numbers and inclusive ranges are supported. Inspect the
specified workbook before choosing rows: output sorting changes row numbers.
Use `--sheet` if selecting a sheet other than the default Assistant queue.
Only selected rows can trigger AI calls; other jobs reuse matching saved
assessments or remain unassessed if none match. Only selected existing jobs have posting pages refreshed; unselected evidence
is retained so its assessment cache is not invalidated. Archival still runs. This option does not bypass missing role evidence,
duplicates, vacancy/deadline review holds, or manually supplied criterion ratings.
Protected application statuses and nonexistent rows are rejected before fetching.

An enabled provider and resume configuration are required. Do not combine with
`--reassess`, `--offline`, or `--no-ai`. The normal AI call limit still applies.
Use the existing `--reassess` option to refresh all eligible assessments instead.


## Reassess jobs marked as needing attention

Use `--reassess-needed` to select jobs by their saved **Apply order** value,
regardless of where you moved their rows:

```powershell
.\.venv\Scripts\python.exe -m job_search_assistant update --reassess-needed
```

This selects **Needs assessment** and **Needs review**, ignoring case and extra
spaces (also accepts the typo **Needs Assessement**). Selection occurs before
fetching and sorting. Only Not applied/blank application statuses qualify;
Closed, Rejected, Interviewing and other protected statuses are untouched.
Unselected jobs use matching saved assessments without new AI calls. Existing
manual ratings remain authoritative. Selection does not bypass vacancy/data
holds or missing evidence, so some rows can still require review afterward.

Do not combine with `--reassess-rows`, `--reassess`, `--offline`, or `--no-ai`.
Posting checks run only for selected existing jobs. AI call limits, workbook
creation and archival still apply.
New/unassessed jobs have no default total call cutoff; previously assessed jobs
share the configured refresh allowance (default 20). Use `--max-ai-calls` to set
an explicit total cap.
The default input is the sole current top-level workbook, including your saved
manual edits. Save and close Excel first. Add `--workbook` if multiple files exist.


## Refresh failures and missing descriptions

A forced refresh that fails keeps a previously saved assessment active only when
its cache key matches the current candidate, preferences and role inputs, and its
quotations still validate. A refresh returning entirely unknown ratings also
keeps that matching valid assessment. The workbook reports the refresh failure;
it does not claim the earlier assessment was newly completed. Changed inputs do
not silently reuse earlier ratings. The previous workbook summary and assessment
date remain in separate historical columns and do not affect ranking.

Unsupported quotations trigger at most one correction request with validation
feedback. Both requests count against the total and refresh allowances. Other
provider errors are not automatically retried, and quotation validation is never
relaxed.

`Assistant assessment outcome` distinguishes `Description needed`,
`Assessment failed`, `Saved assessment retained; refresh failed`, `Assessment needed`,
and `Assessed`.
The existing `Needs assessment` Apply order marker remains compatible with
`--reassess-needed`. For missing descriptions, obtain role-specific evidence before
repeatedly requesting assessments.

When a newly fetched page lacks a substantive structured posting or scoped job
body and has less text than the saved description, or lacks recognizable
role-duty wording, the earlier
evidence and its source/date are retained. The latest fetch snapshot is recorded
separately; a warning explains that current availability remains unverified.
An explicit closure notice still takes precedence. This conservative heuristic
cannot identify every generic page and does not verify current vacancy status.

Extraction also reads explicit JobPosting objects in application/json scripts
and scopes fallback text to known public job-description containers (including
LinkedIn, Lever, Greenhouse and SuccessFactors) before page-wide text. No JavaScript
is executed, no access controls are bypassed, and missing job details are not
inferred. Client-rendered or blocked sites may still require a supplied description
or a verified alternate posting.
