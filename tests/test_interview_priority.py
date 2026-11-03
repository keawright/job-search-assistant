from dataclasses import replace
from datetime import timedelta

import pytest

from job_search_assistant import Location, prioritize
from job_search_assistant.searching.eligibility import location_gate


def test_confirmed_location_precedes_fresher_assumed_location(make_job, candidate, today):
    uncertain = make_job('a', location=Location(arrangement='remote', evidence='Remote; country unspecified'),
                         assume_location_acceptable=True, posting_date=today)
    confirmed = make_job('z', posting_date=today-timedelta(days=20))
    result = prioritize([uncertain, confirmed], candidate, as_of=today)
    assert [r.job.id for r in result.outstanding] == ['z', 'a']
    assert result.outstanding[1].location_eligibility == 'assumed acceptable'


def test_newer_comparable_match_precedes_closing_older_role(make_job, candidate, today):
    older = make_job('a', posting_date=today-timedelta(days=30), deadline=today)
    newer = make_job('z', posting_date=today-timedelta(days=1))
    result = prioritize([older, newer], candidate, as_of=today)
    assert [r.job.id for r in result.outstanding] == ['z', 'a']
    assert any('Closing soon' in f for f in result.outstanding[1].review_flags)


def test_future_and_unknown_dates_have_no_freshness_advantage(make_job, candidate, today):
    result = prioritize([make_job('a'), make_job('b', posting_date=today+timedelta(days=1)),
                         make_job('z', posting_date=today-timedelta(days=10))], candidate, as_of=today)
    assert [r.job.id for r in result.outstanding] == ['z', 'a', 'b']


def test_personal_appeal_does_not_hide_stronger_employer_match(make_job, candidate, today):
    strong = make_job('z')
    strong = replace(strong, assessment=replace(strong.assessment, career_alignment='stretch',
                      opportunity_quality='good', regular_hands_on_coding=True,
                      coding_evidence='Posting includes regular implementation.'))
    result = prioritize([make_job('a', fit='good'), strong], candidate, as_of=today)
    assert [r.job.id for r in result.outstanding] == ['z', 'a']
    assert result.outstanding[0].overall_fit == 'stretch'


def test_explicit_ineligibility_cannot_be_overridden_by_location_assumption(make_job, candidate, today):
    job = make_job(location=Location(arrangement='hybrid', office_city='Toronto', evidence='Toronto office required'),
                   assume_location_acceptable=True)
    result = prioritize([job], candidate, as_of=today)
    assert not result.outstanding
    assert result.excluded[0].location_eligibility == 'ineligible'


@pytest.mark.parametrize('city', ['Halifax', 'Dartmouth', 'Bedford'])
@pytest.mark.parametrize('arrangement', ['onsite', 'hybrid'])
def test_local_offices_are_eligible_in_ranker_and_discovery(make_job, candidate, today, city, arrangement):
    job = make_job(location=Location(arrangement=arrangement, office_city=city, evidence=f'{arrangement} in {city}'))
    assert prioritize([job], candidate, as_of=today).outstanding[0].location_eligibility == 'eligible'
    assert location_gate('', f'{arrangement} - {city}, Nova Scotia')[0] == 'eligible'
