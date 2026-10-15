"""Entirely synthetic demonstration; no actual candidate or employer records.

Run from the project root: python examples/synthetic_jobs.py
"""

from datetime import date

from job_search_assistant import Assessment, CandidatePreferences, Job, Location, prioritize


def assessment(level: str) -> Assessment:
    return Assessment(
        leadership_fit=level,
        technical_fit=level,
        career_alignment=level,
        opportunity_quality=level,
        evidence={
            "leadership_fit": "Synthetic candidate led two SaaS teams; posting asks for comparable team leadership.",
            "technical_fit": "Candidate led cloud platform delivery; posting involves cloud reliability programs.",
            "career_alignment": "Management-led role aligns with the candidate's next leadership step.",
            "opportunity_quality": "Posting describes ownership of delivery and team development at a comparable scope.",
        },
        strengths=("Comparable team leadership", "Cloud delivery accomplishments"),
    )


def main():
    remote = Location(arrangement="remote", allowed_remote_countries=("Canada",), evidence="Synthetic posting explicitly allows remote employees in Canada.")
    jobs = [
        Job(id="new-strong", company="Example Cloud", title="Engineering Manager", url="https://example.com/jobs/new-strong", assessment=assessment("strong"), location=remote, posting_date=date(2026, 10, 14)),
        Job(id="older-good", company="Example Platform", title="Technical Program Manager", url="https://example.com/jobs/older-good", assessment=assessment("good"), location=remote, posting_date=date(2026, 9, 25)),
        Job(id="applied", company="Example Data", title="Engineering Manager", url="https://example.com/jobs/applied", status="applied", tracking={"application_date": "2026-10-10", "comment": "Synthetic referral submitted"}),
        Job(id="closed", company="Example Identity", title="Director of Engineering", url="https://example.com/jobs/closed", verification="closed", last_verified=date(2026, 10, 15)),
    ]
    result = prioritize(jobs, CandidatePreferences(), as_of=date(2026, 10, 15))
    for name in ("applied", "outstanding", "rejected", "excluded"):
        print(f"\n{name.upper()}")
        for row in getattr(result, name):
            print(f"  {row.priority or '-'} | {row.job.company} | {row.job.title} | fit={row.overall_fit}")
            for reason in row.reasons:
                print(f"    {reason}")
            for flag in row.review_flags:
                print(f"    Review: {flag}")


if __name__ == "__main__":
    main()
