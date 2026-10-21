"""Explicit inputs: None means unknown, never a negative finding."""

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

Fit = Literal["strong", "good", "stretch", "unsuitable", "unknown"]


@dataclass(frozen=True)
class CandidatePreferences:
    target_roles: tuple[str, ...] = ("Engineering Manager", "Senior Engineering Manager", "Director of Engineering", "Technical Program Manager", "Program Manager")
    home_city: str = "Halifax"
    country: str = "Canada"
    remote_countries: tuple[str, ...] = ("Canada",)
    acceptable_office_cities: tuple[str, ...] = ("Halifax",)
    strengths: tuple[str, ...] = ("SaaS", "cloud infrastructure", "engineering leadership", "data platforms", "blockchain infrastructure", "identity and access management", "cross-functional delivery", "organizational change")
    prefer_leadership: bool = True
    willing_to_relocate: bool = False
    work_authorizations: tuple[str, ...] = ()
    unavailable_work_authorizations: tuple[str, ...] = ()


@dataclass(frozen=True)
class Gap:
    description: str
    severity: Literal["manageable", "major", "fundamental"]
    evidence: str

    def __post_init__(self):
        if self.severity not in ("manageable", "major", "fundamental"):
            raise ValueError("Invalid gap severity")
        if not self.description.strip() or not self.evidence.strip():
            raise ValueError("Gaps require a description and supporting evidence")


@dataclass(frozen=True)
class Assessment:
    """Contextual judgment supplied by a human, or a future validated provider.

    Evidence should compare posting requirements with candidate accomplishments.
    Target roles and strengths guide this assessment, not keyword scoring.
    """

    leadership_fit: Fit = "unknown"
    technical_fit: Fit = "unknown"
    career_alignment: Fit = "unknown"
    opportunity_quality: Fit = "unknown"
    evidence: dict[str, str] = field(default_factory=dict)
    strengths: tuple[str, ...] = ()
    gaps: tuple[Gap, ...] = ()
    regular_hands_on_coding: bool | None = None
    coding_evidence: str | None = None
    assessor: str = "human"

    def __post_init__(self):
        for criterion in ("leadership_fit", "technical_fit", "career_alignment", "opportunity_quality"):
            value = getattr(self, criterion)
            if value not in ("strong", "good", "stretch", "unsuitable", "unknown"):
                raise ValueError(f"Invalid assessment for {criterion}")
            if value != "unknown" and not self.evidence.get(criterion, "").strip():
                raise ValueError(f"Evidence required for {criterion}")
        if self.regular_hands_on_coding is not None and not (self.coding_evidence or "").strip():
            raise ValueError("Known coding requirements need evidence")


@dataclass(frozen=True)
class Location:
    arrangement: Literal["remote", "hybrid", "onsite", "unknown"] = "unknown"
    allowed_remote_countries: tuple[str, ...] | None = None
    office_city: str | None = None
    relocation_required: bool | None = None
    required_work_authorization: str | None = None
    evidence: str | None = None

    def __post_init__(self):
        if self.arrangement not in ("remote", "hybrid", "onsite", "unknown"):
            raise ValueError("Invalid working arrangement")
        known = (self.arrangement != "unknown" or self.allowed_remote_countries is not None
                 or self.office_city is not None or self.relocation_required is not None
                 or self.required_work_authorization is not None)
        if known and not (self.evidence or "").strip():
            raise ValueError("Known location restrictions need evidence")


@dataclass(frozen=True)
class Job:
    id: str
    company: str
    title: str
    url: str
    status: Literal["applied", "outstanding", "rejected"] = "outstanding"
    verification: Literal["open", "closed", "unverified"] = "unverified"
    description: str | None = None
    source_urls: tuple[str, ...] = ()
    last_verified: date | None = None
    posting_date: date | None = None
    deadline: date | None = None
    location: Location = field(default_factory=Location)
    assessment: Assessment = field(default_factory=Assessment)
    manual_priority: int | None = None
    tracking: dict[str, object] = field(default_factory=dict)
    assume_location_acceptable: bool = False

    def __post_init__(self):
        if not self.id.strip() or not self.company.strip() or not self.title.strip():
            raise ValueError("Job id, company, and title are required")
        if self.status not in ("applied", "outstanding", "rejected"):
            raise ValueError("Invalid application status")
        if self.verification not in ("open", "closed", "unverified"):
            raise ValueError("Invalid verification status")
        if self.verification != "unverified" and self.last_verified is None:
            raise ValueError("Confirmed open/closed jobs require a verification date")
        if self.manual_priority is not None and (type(self.manual_priority) is not int or self.manual_priority < 1):
            raise ValueError("Manual priority must be a positive integer")


@dataclass(frozen=True)
class RankingPolicy:
    version: str = "1.1"
    old_posting_days: int = 14
    approaching_deadline_days: int = 7

    def __post_init__(self):
        if self.old_posting_days < 0 or self.approaching_deadline_days < 0:
            raise ValueError("Urgency windows must be nonnegative")


@dataclass(frozen=True)
class RankedJob:
    job: Job
    overall_fit: Fit
    location_eligibility: Literal["eligible", "ineligible", "unknown"]
    priority: int | None
    reasons: tuple[str, ...]
    review_flags: tuple[str, ...]
    rubric_version: str
    as_of: date


@dataclass(frozen=True)
class RankingResult:
    applied: tuple[RankedJob, ...]
    outstanding: tuple[RankedJob, ...]
    rejected: tuple[RankedJob, ...]
    excluded: tuple[RankedJob, ...]

    @property
    def ordered(self) -> tuple[RankedJob, ...]:
        """Spreadsheet sections; exclusions are separately available for review."""
        return self.applied + self.outstanding + self.rejected
