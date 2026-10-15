from datetime import date

import pytest

from job_search_assistant import Assessment, CandidatePreferences, Job, Location


@pytest.fixture
def today():
    return date(2026, 10, 15)


@pytest.fixture
def candidate():
    return CandidatePreferences()


@pytest.fixture
def make_job():
    def make(id="a", fit="strong", **kwargs):
        criteria = ("leadership_fit", "technical_fit", "career_alignment", "opportunity_quality")
        assessment = Assessment(**{c: fit for c in criteria}, evidence={c: "Synthetic assessment: led comparable SaaS teams and delivery." for c in criteria})
        defaults = dict(company="Example Labs", title="Engineering Manager", url=f"https://example.com/jobs/{id}",
                        assessment=assessment, location=Location(arrangement="remote", allowed_remote_countries=("Canada",), evidence="Posting explicitly permits remote work from Canada."))
        defaults.update(kwargs)
        return Job(id=id, **defaults)
    return make
