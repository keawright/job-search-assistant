from datetime import timedelta

import pytest

from job_search_assistant import RankingPolicy, prioritize


@pytest.mark.parametrize("age,first", [(14, "strong"), (15, "older")])
def test_age_threshold_can_promote_slightly_weaker_fit(make_job, candidate, today, age, first):
    result = prioritize([make_job("strong"), make_job("older", fit="good", posting_date=today-timedelta(days=age))], candidate, as_of=today)
    assert result.outstanding[0].job.id == first
    assert next(r for r in result.outstanding if r.job.id == "older").overall_fit == "good"


def test_deadline_outranks_posting_age_at_equal_fit(make_job, candidate, today):
    result = prioritize([make_job("old", posting_date=today-timedelta(days=30)), make_job("deadline", deadline=today+timedelta(days=2))], candidate, as_of=today)
    assert result.outstanding[0].job.id == "deadline"


def test_urgency_does_not_overcome_large_fit_gap_or_unsuitability(make_job, candidate, today):
    result = prioritize([make_job("stretch", fit="stretch", deadline=today), make_job("strong"), make_job("unsuitable", fit="unsuitable", deadline=today)], candidate, as_of=today)
    assert [r.job.id for r in result.outstanding] == ["strong", "stretch"]
    assert result.excluded[0].job.id == "unsuitable"


def test_passed_deadline_held_for_review_not_marked_closed(make_job, candidate, today):
    result = prioritize([make_job(deadline=today-timedelta(days=1))], candidate, as_of=today)
    assert not result.outstanding
    assert result.excluded[0].job.verification == "unverified"
    assert any("deadline has passed" in f for f in result.excluded[0].review_flags)


def test_configurable_window_and_future_posting(make_job, candidate, today):
    jobs = [make_job("new", posting_date=today+timedelta(days=1)), make_job("old", fit="good", posting_date=today-timedelta(days=5))]
    result = prioritize(jobs, candidate, as_of=today, policy=RankingPolicy(old_posting_days=3))
    assert result.outstanding[0].job.id == "old"
    assert any("future" in f for f in result.outstanding[1].review_flags)
