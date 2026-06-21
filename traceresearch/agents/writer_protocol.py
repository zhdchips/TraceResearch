"""WriterProtocol — abstract boundary for report generation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from traceresearch.agents.writer import DraftReport, FinalReport
    from traceresearch.evidence.models import (
        CritiqueResult,
        Evidence,
        ResearchBrief,
        VerificationResult,
    )


class WriterProtocol(ABC):
    """Protocol that every Writer implementation MUST satisfy.

    Deterministic and LLM-backed Writers are interchangeable behind this
    interface. The Harness depends on WriterProtocol, not concrete classes.
    """

    @abstractmethod
    def draft(self, *, brief, evidence) -> "DraftReport":
        """Generate outline and draft claims from evidence candidates."""
        ...

    @abstractmethod
    def final(self, *, brief, verified_evidence, verification, critique) -> "FinalReport":
        """Generate the final research report from verified evidence."""
        ...
