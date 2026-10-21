"""Versioned ordinal rules, not a probability or an opaque fit score."""

from dataclasses import replace
from datetime import date

from .models import CandidatePreferences, Job, RankedJob, RankingPolicy, RankingResult

_BANDS = {"strong": 3, "good": 2, "stretch": 1, "unsuitable": 0}
_NAMES = {value: key for key, value in _BANDS.items()}


def _location(job, candidate):
    loc = job.location
    if loc.required_work_authorization and loc.required_work_authorization.casefold() in {a.casefold() for a in candidate.unavailable_work_authorizations}:
        return "ineligible", "Candidate explicitly lacks mandatory work authorization."
    if loc.relocation_required and not candidate.willing_to_relocate:
        return "ineligible", "Relocation is required and candidate will not relocate."
    if loc.arrangement == "remote":
        if loc.allowed_remote_countries is None:
            return "unknown", "Remote does not establish eligibility from the candidate's country."
        allowed = {c.casefold() for c in loc.allowed_remote_countries}
        if candidate.country.casefold() not in allowed:
            return "ineligible", "Remote hiring excludes the candidate's country."
        if candidate.country.casefold() not in {c.casefold() for c in candidate.remote_countries}:
            return "ineligible", "Remote arrangement is outside candidate preferences."
        if loc.required_work_authorization and loc.required_work_authorization.casefold() not in {a.casefold() for a in candidate.work_authorizations}:
            return "unknown", "Required work authorization must be confirmed."
        return "eligible", "Remote hiring explicitly includes the candidate's country."
    if loc.arrangement in ("onsite", "hybrid") and loc.office_city:
        if loc.office_city.casefold() in {c.casefold() for c in candidate.acceptable_office_cities}:
            if loc.required_work_authorization and loc.required_work_authorization.casefold() not in {a.casefold() for a in candidate.work_authorizations}:
                return "unknown", "Required work authorization must be confirmed."
            return "eligible", "Required office attendance is in an acceptable city."
        if candidate.willing_to_relocate:
            return "unknown", "Distant office: relocation feasibility needs review."
        return "ineligible", "Regular office attendance is required in an unacceptable city."
    return "unknown", "Location eligibility is not established."


def _evaluate(job, candidate, policy, as_of):
    reasons, flags = [], []
    assessment = job.assessment
    values = [getattr(assessment, c) for c in ("leadership_fit", "technical_fit", "career_alignment", "opportunity_quality")]
    known = [v for v in values if v != "unknown"]
    if "unknown" in values:
        flags.append("Incomplete contextual assessment; unknown criteria are not treated as mismatches.")
    # Conservative bottleneck: do not average away a fundamental weakness.
    band = min((_BANDS[v] for v in known), default=0)
    fit = _NAMES[band] if known else "unknown"
    reasons.append(f"Contextual fit: {fit}; weakest known criterion determines the band.")
    for gap in assessment.gaps:
        reasons.append(f"{gap.severity.title()} gap: {gap.description} Evidence: {gap.evidence}")
        if gap.severity == "fundamental":
            band, fit = 0, "unsuitable"
        elif gap.severity == "major" and band > 1:
            band, fit = 1, "stretch"
    if candidate.prefer_leadership and assessment.regular_hands_on_coding and band > 0:
        band = max(1, band - 1)
        fit = _NAMES[band]
        reasons.append("Regular hands-on coding reduces fit by one band under the leadership preference.")
    location, location_reason = _location(job, candidate)
    if job.assume_location_acceptable and location != "eligible":
        flags.append("Location needs checking; assessed and ranked assuming location will be acceptable. " + location_reason)
        location = "assumed acceptable"
        location_reason = "Location assumed acceptable at user request; actual eligibility remains unverified."
    reasons.append(location_reason)
    if location == "unknown":
        flags.append("Confirm location/work authorization before applying.")
    if job.verification == "unverified":
        flags.append("Job availability is unverified; check the official employer page.")
    if job.last_verified and job.last_verified > as_of:
        raise ValueError(f"{job.id}: verification date is after the ranking date")
    urgency = 0
    if job.posting_date:
        age = (as_of - job.posting_date).days
        if age < 0:
            flags.append("Posting date is in the future; verify it.")
        elif age > policy.old_posting_days:
            urgency = 1
            reasons.append(f"Posting is {age} days old (over {policy.old_posting_days}).")
    else:
        flags.append("Posting date unknown; no posting-age boost.")
    deadline = job.deadline
    if deadline and deadline < as_of and job.verification == "open" and job.last_verified >= deadline:
        flags.append("Recorded deadline superseded by later confirmation that applications are accepted; original deadline retained.")
        deadline = None
    if deadline:
        remaining = (deadline - as_of).days
        if remaining < 0:
            flags.append("Recorded deadline has passed; verify availability before applying.")
        elif remaining <= policy.approaching_deadline_days:
            urgency = 2
            reasons.append(f"Deadline is in {remaining} days (within {policy.approaching_deadline_days}).")
    else:
        flags.append("Deadline unknown; no deadline boost.")
    excluded = job.verification == "closed" or location == "ineligible" or fit == "unsuitable" or bool(deadline and deadline < as_of)
    if job.verification == "closed":
        reasons.append("Confirmed closed: excluded from the application queue.")
    if excluded or band == 0:
        urgency = 0
    if urgency:
        reasons.append("Urgency raises queue position by at most one fit band; it does not change fit.")
    if job.manual_priority is not None:
        reasons.append(f"Manual queue position requested: {job.manual_priority}; eligibility and status still apply.")
    ranked = RankedJob(job, fit, location, None, tuple(reasons), tuple(flags), policy.version, as_of)
    # Fit drives recommendations. Confirmed ineligibility still excludes a job;
    # unknown location stays flagged and breaks comparable-fit ties only.
    key = (not bool(known), -(band + bool(urgency)), -urgency,
           "unknown" in values, -band, location not in ("eligible", "assumed acceptable"), job.deadline or date.max, job.id)
    return ranked, key, excluded


def prioritize(jobs: list[Job], candidate: CandidatePreferences, *, as_of: date, policy: RankingPolicy | None = None) -> RankingResult:
    """Return a new ranking without modifying records or user tracking fields.

    Duplicate IDs or normalized URLs are rejected for explicit reconciliation;
    silently merging records could overwrite user-maintained fields.
    """
    from urllib.parse import urlsplit, urlunsplit

    policy = policy or RankingPolicy()
    ids, urls = set(), set()
    applied, rejected, excluded, queue = [], [], [], []
    for job in jobs:
        parts = urlsplit(job.url)
        if parts.scheme.lower() not in ("http", "https") or not parts.hostname or parts.username or parts.password:
            raise ValueError(f"{job.id}: expected a public posting HTTP(S) URL without credentials")
        # Preserve query parameters: they may contain the posting identifier.
        normalized = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))
        if job.id in ids or normalized in urls:
            raise ValueError(f"Duplicate job id or URL: {job.id}; reconcile records explicitly")
        ids.add(job.id)
        urls.add(normalized)
        ranked, key, is_excluded = _evaluate(job, candidate, policy, as_of)
        if job.status == "applied":
            applied.append(ranked)
        elif job.status == "rejected":
            rejected.append(ranked)
        elif is_excluded:
            excluded.append(ranked)
        else:
            queue.append((key, ranked))
    ordered = [r for _, r in sorted(queue, key=lambda pair: pair[0])]
    # Insert manual requests at 1-based positions, clamped to queue length.
    manual = sorted((r for r in ordered if r.job.manual_priority is not None), key=lambda r: (r.job.manual_priority, r.job.id))
    ordered = [r for r in ordered if r.job.manual_priority is None]
    previous_position = 0
    for r in manual:
        position = min(max(r.job.manual_priority, previous_position + 1), len(ordered) + 1)
        ordered.insert(position - 1, r)
        previous_position = position
    groups = {}
    for r in ordered:
        groups.setdefault(r.job.company.strip().casefold(), []).append(r.job.id)
    result = []
    for position, r in enumerate(ordered, 1):
        flags = r.review_flags
        peers = groups[r.job.company.strip().casefold()]
        if len(peers) > 1:
            # Best fit ignores urgency and manual queue adjustments.
            fit_order = {"strong": 3, "good": 2, "stretch": 1, "unknown": -1, "unsuitable": 0}
            best = min((x for x in ordered if x.job.id in peers), key=lambda x: (-fit_order[x.overall_fit], x.location_eligibility != "eligible", x.job.id))
            flags += (f"Overlapping company opportunities: {', '.join(peers)}. Best assessed fit: {best.job.id} ({best.overall_fit}); review before multiple applications.",)
        result.append(replace(r, priority=position, review_flags=flags))
    return RankingResult(tuple(applied), tuple(result), tuple(rejected), tuple(excluded))
