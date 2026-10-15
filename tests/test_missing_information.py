from dataclasses import replace

import pytest

from job_search_assistant import Assessment, Location, prioritize


def test_unknowns_not_invented_or_declared_unsuitable(make_job, candidate, today):
    job = make_job(assessment=Assessment(), location=Location())
    row = prioritize([job], candidate, as_of=today).outstanding[0]
    assert row.overall_fit == "unknown"
    assert row.location_eligibility == "unknown"
    assert row.job.posting_date is None and row.job.deadline is None
    assert any("unverified" in f for f in row.review_flags)
    assert any("no posting-age boost" in f for f in row.review_flags)


def test_known_assessment_requires_evidence():
    with pytest.raises(ValueError, match="Evidence"):
        Assessment(leadership_fit="strong")


def test_future_verification_rejected(make_job, candidate, today):
    from datetime import timedelta
    with pytest.raises(ValueError, match="verification date"):
        prioritize([make_job(last_verified=today+timedelta(days=1))], candidate, as_of=today)


def test_description_sources_and_tracking_unchanged(make_job, candidate, today):
    job = make_job(description="Original text", source_urls=("https://example.com/original",), tracking={"notes": "Manual note", "date": "2026-10-01"})
    before = replace(job)
    result = prioritize([job], candidate, as_of=today)
    assert job == before
    assert result.outstanding[0].job is job
