"""VerifierProtocol — abstract boundary for claim verification."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from traceresearch.agents.writer import DraftReport
    from traceresearch.evidence.models import Evidence, VerificationResult


class VerifierProtocol(ABC):
    """Protocol that every Verifier implementation MUST satisfy.

    Deterministic and LLM-backed Verifiers are interchangeable behind this
    interface. The Harness depends on VerifierProtocol, not concrete classes.
    """

    @abstractmethod
    def verify(self, *, run_id: str, draft, evidence) -> "VerificationResult":
        """Verify draft claims against the evidence store."""
        ...
