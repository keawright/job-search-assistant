# Architecture

Current extension: `assessment.py` implements optional Codex CLI and direct
OpenAI Responses providers, grounded-quotation validation, private input-keyed
assessment reuse, and safe failure handling. CLI loads private resume/configuration
and passes the service into the workbook adapter. Explicit manual ratings retain
precedence; the pure ranking library still makes no network calls. Policy 1.1
makes contextual fit primary; unknown location is a tie-breaker. The historical
design notes below describe the earlier implementation; see automatic_assessment.md
for current runtime behavior.

The first iteration is a pure Python library, independent of HTTP, databases,
spreadsheets, and AI vendors. It takes existing jobs, preferences, a policy, and an
evaluation date, and returns ranked records with reasons. There are no side effects.

```text
Existing job records + contextual assessments + candidate preferences
                              |
                              v
              Validation and deterministic ranking
                              |
                              v
       Applied / Outstanding / Rejected + exclusions for review
```

`models.py` defines the public dataclasses and evidence requirements. `ranking.py`
handles eligibility, ordinal fit, bounded urgency, manual insertion, and company
review flags. `assessment.py` defines an optional provider protocol. No plugin
framework or provider implementation is needed to run the engine.

Assessments are contextual judgments, not claims that a small rules engine can
understand a career history. Candidate target roles and strengths inform the
assessor. A future provider receives both job and candidate and must return the
same structured evidence-backed assessment. Deterministic ranking remains separate.
Later AI output must be validated for evidence accuracy as well as schema shape;
schema validation alone cannot establish truth. The library currently checks that
evidence is present, not whether the evidence is factually correct.

Frozen dataclasses discourage accidental attribute replacement. Nested tracking and
evidence dictionaries remain caller-owned mutable objects; this engine never edits
them. A future persistence layer should serialize snapshots rather than rely on
shared mutable references.

## Future boundaries

- FastAPI translates requests into models and calls this library.
- SQLite stores job snapshots, assessments, user tracking, and ranking versions.
- React presents explanations, review flags, and explicit overrides.
- URL ingestion verifies official sources, preserves text/source provenance, and
  produces evidence without silently changing application tracking fields.
- Spreadsheet adapters define ownership per field and reconcile duplicates before
  import; no blind whole-row replacement.
- GitHub Actions runs tests using synthetic fixtures without production secrets.

The tradeoff is explicit assessment entry in version one. This keeps ranking
auditable and avoids committing early to scraping, paid models, infrastructure,
or an incompatible workbook mapping. Interfaces can evolve once real import and
UI requirements are exercised.

## Version 0.2: URL and workbook adapters

`cli.py` exposes the `update` command. `workbook.py` reads a selected job table,
retains every original tab, copies user cells into a new queue, calls the ranking
library, and saves only to a new filename. Unrankable records remain visible for
review, including duplicate conflicts and unknown status values. Missing URLs do
not change an Applied/Rejected section. Manual assessment/location/verification
columns are the human input boundary; Assistant columns are generated output.

`ingestion.py` separately fetches public HTML and extracts explicit JobPosting
facts. Every redirect is revalidated, connections use checked IP addresses, and
TLS retains server-name validation. Responses have byte/redirect/time budgets;
OS DNS resolution has its own timeout behavior. Neither readable HTML nor a
structured job object is treated as proof that the role is open. No title-based
or keyword-based competitiveness ratings are assigned.

Raw HTML and complete extracted text are kept in private sidecar snapshots. Excel
uses a bounded display excerpt. Repeated URL aliases are skipped without merging
tracking fields. Legacy closed/geography exclusions are held for reassessment
rather than silently revived. Human edits survive later refreshes because
extracted facts are stored separately and ownership is explicit.

The engine remains independent of these adapters. The workbook command is the
first useful end-to-end path; FastAPI, SQLite, React, CSV export, GitHub Actions,
and AI providers are still future work.

The CLI now keeps one current workbook with one queue tab by default. After saving
a new export it verifies that the input did not change during processing, then
`archive.py` moves older sibling workbooks into `archive/` using exclusive backup
creation and byte verification. Earlier tabs remain in those archived files.
An ambiguous current file selection is refused; callers can identify the latest
edited workbook explicitly. The low-level workbook function can still retain all
tabs; the CLI offers `--keep-history-tabs` for formula dependencies. Excel output
orders Interviewing, Applied, Outstanding, Review, Closed, Rejected, and
Elapsed-Rejected. Interviewing retains input order and stays above Applied.
