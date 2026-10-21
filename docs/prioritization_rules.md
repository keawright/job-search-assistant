# Prioritization policy 1.1

All rules are deterministic for the same inputs, policy, and explicit `as_of` date.
Dates are calendar dates. Unknown values remain unknown. These ordinal rules are
reviewable design decisions, not inferred probabilities.

## Status and exclusions

1. In workbook output, Interviewing precedes Applied, then actionable Outstanding,
   Review, Closed, Rejected, and Elapsed-Rejected.
2. Preserve input order within Interviewing, Applied and Rejected; do not rewrite user status.
3. Exclude only Outstanding records that are confirmed closed, location-ineligible,
   assessed unsuitable, have a fundamental gap, or have a recorded passed deadline.
4. Return exclusions separately with their original status and explanations.
   Passed deadlines require verification; they do not prove a job is closed.
5. Unverified availability is flagged, not assumed open or closed. Confirmed open
   and closed inputs require a last-verification date. Future verification dates
   relative to `as_of` are rejected.

The workbook view places the separate Review collection between Outstanding and
Rejected, so **Rejected is the last section**. Manual application status remains
unchanged even when a record cannot be ranked. Earlier workbook files are archived;
the current workbook's user edits are the source for the next export.

## Contextual fit

Assess leadership responsibilities/scope, technical/domain experience, career
alignment, and opportunity quality as strong, good, stretch, unsuitable, or unknown.
Each known assessment requires supporting evidence. Include achievements,
transferable experience, realistic progression, growth, and distinctive experience
in the contextual rationale. Salary can inform that rationale; no salary cutoff
exists. No keyword count contributes to ranking.

The weakest known criterion determines overall fit. Unknown criteria remain
flagged and are not converted into failed requirements. An entirely unknown
assessment stays unknown. This conservative bottleneck prevents strengths in one
area from hiding a serious concern elsewhere; it can also undervalue exceptional
transferable strengths, so users can revise assessments or override queue position.

Manageable gaps retain the fit band; major gaps cap it at stretch; fundamental gaps
make it unsuitable. Regular coding lowers a suitable fit by one band (minimum
stretch) when leadership is preferred. Coding alone is not a disqualifier.
Every identified gap must include evidence and a severity judgment.

## Location and authorization

- Remote explicitly permitting the candidate's country is eligible if consistent
  with their remote preferences. Unspecified remote countries remain unknown.
- Remote restricted to other countries is ineligible.
- Hybrid/onsite attendance in configured acceptable cities is eligible.
- A distant office is ineligible unless relocation is acceptable; when acceptable,
  feasibility still requires review.
- Required relocation is ineligible when the candidate will not relocate.
- Explicitly unavailable mandatory work authorization is disqualifying. Missing
  authorization information requires review; do not infer lack of authorization.
- Known restrictions take precedence over missing information.

`home_city` is profile context; `acceptable_office_cities` is the explicit eligibility
rule. Changing one does not silently rewrite the other. Work authorization defaults
to unknown; callers should record known held or unavailable authorizations.

## Urgency and automatic ordering

Internally the fit bands have ordinal levels strong=3, good=2, stretch=1,
unsuitable=0. These are sorting levels, not public numerical fit scores.

- A known posting age **greater than** 14 days triggers age urgency (level 1).
- A known deadline from today through seven days away triggers deadline urgency
  (level 2). Deadline urgency takes precedence over age urgency.
- Either trigger can raise queue sorting by **one** fit band maximum; triggers
  never stack. The recorded fit assessment does not change.
- Unknown dates add no urgency. Future posting dates are flagged and receive no
  age boost. Entirely unassessed and excluded jobs receive no urgency boost.

Sort actionable Outstanding by:

1. At least one known contextual criterion before entirely unassessed records.
2. Fit band plus bounded urgency, descending.
3. Urgency level, descending (deadline before age before none).
4. Complete assessments before partial assessments.
5. Original fit band, descending.
6. Confirmed location eligibility before unknown eligibility for otherwise comparable fits.
7. Earliest known deadline; then stable ID.

Example: older good fit (2+1) precedes new strong fit (3+0), because urgency
breaks the equal effective band. Urgent stretch (1+1) stays below new strong (3).
Unknown location is flagged for verification; it does not by itself push a strong
fit below a weak one. Confirmed location ineligibility still excludes the job.
An older posting may already be stale, so age urgency is paired with availability
review flags rather than an invented closure prediction.

Thresholds are configurable through `RankingPolicy`. A material rule change should
receive a new policy version and regression tests.

## Manual ordering, duplicates, and overlapping roles

After automatic sorting, remove manually positioned records and insert them at
their requested 1-based queue positions. Positions beyond the queue clamp to the
end. Conflicting requested positions resolve by requested position then stable ID;
later requests move after earlier manual insertions when necessary. Report actual
final positions while retaining the requested position in the original record.
Overrides apply only inside the actionable Outstanding queue.

Reject duplicate IDs or normalized URLs instead of merging user information.
Normalize URL scheme/host case, trailing slashes, and fragments. Preserve query
parameters because they can identify distinct postings. This does not detect every
aggregator alias, tracking-parameter variant, or same-job alternate URL; those
require future reconciliation. URLs are validated but never fetched.

Flag multiple actionable opportunities at the same company (case-insensitive exact
company name), and identify the strongest assessed fit independent of urgency and
manual queue changes. Resolve equal fits by confirmed location then stable ID.
This is a review recommendation, not an instruction to apply to every position;
company aliases and partially unknown assessments still need human review.

All original descriptions, source URLs, strengths, gaps, comments, dates, and
arbitrary tracking fields are retained. The engine returns rankings without
mutating inputs or implementing a synchronization policy.
