from dataclasses import replace

import pytest

from job_search_assistant import Location, prioritize


@pytest.mark.parametrize("location,eligibility", [
    (Location(arrangement="remote", evidence="Remote advertised; countries unstated"), "unknown"),
    (Location(arrangement="remote", allowed_remote_countries=("US",), evidence="US only"), "ineligible"),
    (Location(arrangement="hybrid", office_city="Halifax", evidence="Halifax office twice weekly"), "eligible"),
    (Location(arrangement="onsite", office_city="Toronto", evidence="Toronto attendance daily"), "ineligible"),
    (Location(relocation_required=True, evidence="Must relocate"), "ineligible"),
])
def test_location_rules(make_job, candidate, today, location, eligibility):
    result = prioritize([make_job(location=location)], candidate, as_of=today)
    row = (result.outstanding + result.excluded)[0]
    assert row.location_eligibility == eligibility
    assert bool(result.excluded) == (eligibility == "ineligible")


def test_required_authorization_unknown_vs_explicitly_absent(make_job, candidate, today):
    job = make_job(location=Location(arrangement="remote", allowed_remote_countries=("Canada",), required_work_authorization="US", evidence="US authorization mandatory"))
    assert prioritize([job], candidate, as_of=today).outstanding[0].location_eligibility == "unknown"
    assert prioritize([job], replace(candidate, unavailable_work_authorizations=("US",)), as_of=today).excluded
    assert prioritize([job], replace(candidate, work_authorizations=("US",)), as_of=today).outstanding[0].location_eligibility == "eligible"


def test_unknown_authorization_does_not_hide_distant_office(make_job, candidate, today):
    job = make_job(location=Location(arrangement="onsite", office_city="Toronto", required_work_authorization="US", evidence="Toronto office; US authorization"))
    assert prioritize([job], candidate, as_of=today).excluded


def test_candidate_can_configure_acceptable_offices(make_job, candidate, today):
    job = make_job(location=Location(arrangement="hybrid", office_city="Toronto", evidence="Toronto twice weekly"))
    assert prioritize([job], replace(candidate, acceptable_office_cities=("Toronto",)), as_of=today).outstanding[0].location_eligibility == "eligible"
