"""Boundary for future human/AI assessment providers; ranking stays independent."""

from typing import Protocol

from .models import Assessment, CandidatePreferences, Job


class AssessmentProvider(Protocol):
    def assess(self, job: Job, candidate: CandidatePreferences) -> Assessment:
        """Return contextual judgments with evidence, explicit gaps, and unknowns."""
        ...
