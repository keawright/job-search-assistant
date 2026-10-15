from dataclasses import replace

import pytest

from job_search_assistant import prioritize


def test_status_precedes_fit_and_preserves_user_tracking(make_job, candidate, today):
    tracking = {"comment": "Follow up next week", "applied_date": "2026-10-10", "custom": ["referral"]}
    applied = make_job("applied", fit="stretch", status="applied", tracking=tracking)
    jobs = [make_job("reject", status="rejected"), make_job("next"), applied]
    result = prioritize(jobs, candidate, as_of=today)
    assert [r.job.id for r in result.ordered] == ["applied", "next", "reject"]
    assert result.applied[0].job is applied
    assert applied.tracking == tracking
    assert result.outstanding[0].priority == 1


def test_closed_outstanding_excluded_without_changing_status(make_job, candidate, today):
    job = make_job(verification="closed", last_verified=today)
    result = prioritize([job], candidate, as_of=today)
    assert not result.outstanding
    assert result.excluded[0].job.status == "outstanding"


def test_closed_applied_stays_applied(make_job, candidate, today):
    result = prioritize([make_job(status="applied", verification="closed", last_verified=today)], candidate, as_of=today)
    assert len(result.applied) == 1
    assert not result.excluded


def test_duplicate_ids_and_normalized_urls_rejected(make_job, candidate, today):
    a = make_job()
    for b in (replace(a, url="https://example.com/jobs/different"), make_job("b", url=a.url + "/#tracking")):
        with pytest.raises(ValueError, match="Duplicate"):
            prioritize([a, b], candidate, as_of=today)


def test_query_distinguishes_postings(make_job, candidate, today):
    result = prioritize([make_job("a", url="https://example.com/job?id=1"), make_job("b", url="https://example.com/job?id=2")], candidate, as_of=today)
    assert len(result.outstanding) == 2


def test_same_company_flag_identifies_best_fit_independent_of_urgency(make_job, candidate, today):
    from datetime import timedelta
    result = prioritize([make_job("weaker", fit="good", posting_date=today-timedelta(days=20)), make_job("stronger")], candidate, as_of=today)
    assert result.outstanding[0].job.id == "weaker"
    assert all(any("Best assessed fit: stronger" in flag for flag in r.review_flags) for r in result.outstanding)


def test_ties_stable_across_input_order(make_job, candidate, today):
    jobs = [make_job("b"), make_job("a")]
    assert prioritize(jobs, candidate, as_of=today) == prioritize(list(reversed(jobs)), candidate, as_of=today)
