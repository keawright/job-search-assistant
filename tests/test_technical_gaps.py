from dataclasses import replace

import pytest

from job_search_assistant import Gap, prioritize


@pytest.mark.parametrize("severity,expected", [("manageable", "strong"), ("major", "stretch"), ("fundamental", "unsuitable")])
def test_gap_severity_not_keyword_overlap(make_job, candidate, today, severity, expected):
    job = make_job()
    gap = Gap("Recent production Rust experience", severity, "Posting requires Rust delivery; candidate has led cloud teams but has no recent Rust work.")
    job = replace(job, assessment=replace(job.assessment, gaps=(gap,)))
    result = prioritize([job], candidate, as_of=today)
    row = (result.outstanding + result.excluded)[0]
    assert row.overall_fit == expected
    assert gap.evidence in " ".join(row.reasons)


def test_coding_preference_configurable(make_job, candidate, today):
    job = make_job()
    job = replace(job, assessment=replace(job.assessment, regular_hands_on_coding=True, coding_evidence="50% coding in posting"))
    assert prioritize([job], candidate, as_of=today).outstanding[0].overall_fit == "good"
    assert prioritize([job], replace(candidate, prefer_leadership=False), as_of=today).outstanding[0].overall_fit == "strong"
