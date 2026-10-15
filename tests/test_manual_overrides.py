import pytest

from job_search_assistant import prioritize


def test_manual_position_overrides_calculated_order(make_job, candidate, today):
    result = prioritize([make_job("strong"), make_job("stretch", fit="stretch", manual_priority=1)], candidate, as_of=today)
    assert [r.job.id for r in result.outstanding] == ["stretch", "strong"]
    assert "Manual" in " ".join(result.outstanding[0].reasons)


def test_manual_priority_cannot_reopen_closed_or_rejected(make_job, candidate, today):
    result = prioritize([make_job("closed", verification="closed", last_verified=today, manual_priority=1), make_job("rejected", status="rejected", manual_priority=1), make_job("next")], candidate, as_of=today)
    assert [r.job.id for r in result.outstanding] == ["next"]
    assert result.rejected[0].job.id == "rejected"
    assert result.excluded[0].job.id == "closed"


def test_conflicting_manual_positions_have_stable_order(make_job, candidate, today):
    jobs = [make_job("z", manual_priority=1), make_job("a", manual_priority=1), make_job("middle"), make_job("last", manual_priority=99)]
    result = prioritize(jobs, candidate, as_of=today)
    assert [r.job.id for r in result.outstanding] == ["a", "z", "middle", "last"]


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_invalid_manual_priority_rejected(make_job, value):
    with pytest.raises(ValueError, match="Manual priority"):
        make_job(manual_priority=value)
