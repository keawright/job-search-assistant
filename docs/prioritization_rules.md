# Prioritization policy 1.2

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

## Interview priority and automatic ordering

The queue estimates relative interview prospects using evidence, not numerical
interview probabilities or knowledge of unseen competitors. There is one ranked
list without a weekly application quota.

Sort actionable Outstanding by:

1. Known leadership or technical/domain match before entirely unknown employer match.
2. Weakest known leadership/technical match, descending; major gaps cap it at stretch.
3. Complete employer-match evidence before partial evidence.
4. Combined leadership/technical strength, descending, to distinguish comparable bands.
5. Confirmed location eligibility before unknown or assumed eligibility.
6. Known, nonfuture original posting dates before unknown/future dates, newest first.
7. Stable job ID for reproducibility.

Career alignment, opportunity quality and coding preference remain visible in
personal overall fit, rather than promoting a role's interview priority. Existing
unsuitable/fundamental-gap exclusions remain. Ratings are evidence-based judgments;
no candidate-pool size, hiring stage, referral or recruiter interest is invented.

Posting age breaks comparable-match ties. It never promotes weaker matches just
because they are older. Unknown/future dates receive no freshness advantage, and
future dates are flagged. A posting date is not proof that interviewing has or has
not begun; reposts and last-update dates should not replace original publication.

Deadlines within the configured warning window display Closing soon; they do not
boost interview priority. Passed deadlines retain the existing review checks.
`old_posting_days` remains accepted for compatibility but no longer changes order.

Unknown locations stay available and rank below confirmed eligibility among
comparable matches. Workbook location assumptions never override explicit
ineligibility. Default local offices include Halifax, Dartmouth and Bedford;
relocation remains disabled. Explicit remote Canada eligibility does not resolve
unrepresented province restrictions; record such restrictions when known.

Policy version 1.2 replaces the historical old-posting urgency promotion. For
example, a new strong match precedes an old good match, and a newer strong match
precedes an older equally strong match when location confidence is equal.

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
company name), and identify the strongest assessed fit independent of interview priority and
manual queue changes. Resolve equal fits by confirmed location then stable ID.
This is a review recommendation, not an instruction to apply to every position;
company aliases and partially unknown assessments still need human review.

All original descriptions, source URLs, strengths, gaps, comments, dates, and
arbitrary tracking fields are retained. The engine returns rankings without
mutating inputs or implementing a synchronization policy.
