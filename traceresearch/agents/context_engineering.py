"""Context Engineering — structured context packs with budget enforcement.

Defines lightweight, serializable context structures that form stable
boundaries for future tool-calling Lead Agents. Each pack is a compressed
view of internal state designed to avoid unbounded prompt growth.

Design constraints (007):
- No real LLM calls
- No embeddings or vector stores
- Budget enforcement via item count, per-item chars, total chars
- Serializable to dict (for JSON trace/log output)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


@dataclass
class ContextBudget:
    """Budget constraints for a context pack.

    Attributes:
        max_evidence_items: Maximum number of EvidenceContext items.
        max_chars_per_evidence: Max characters per evidence summary (truncated).
        max_total_chars: Overall pack character budget (approximate).
    """

    max_evidence_items: int = 20
    max_chars_per_evidence: int = 500
    max_total_chars: int = 8_000


# ---------------------------------------------------------------------------
# Lightweight context structures
# ---------------------------------------------------------------------------


@dataclass
class EvidenceContext:
    """Compressed evidence suitable for LLM context.

    Retains the essential identification and summary fields, drops
    internal metadata (authority_score, relevance_score, etc.)
    """

    evidence_id: str
    source_title: str
    source_publisher: str | None
    source_url: str | None
    summary: str
    key_points: list[str]
    limitations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source_title": self.source_title,
            "source_publisher": self.source_publisher,
            "source_url": self.source_url,
            "summary": self.summary,
            "key_points": self.key_points,
            "limitations": self.limitations,
        }


@dataclass
class CritiqueContext:
    """Preserved critique fields for Lead Agent decision-making.

    Contains the fields that matter for deciding next steps.
    """

    decision: str
    next_phase: str
    missing_perspectives: list[str]
    limitations: list[str]
    failed_task_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "next_phase": self.next_phase,
            "missing_perspectives": self.missing_perspectives,
            "limitations": self.limitations,
            "failed_task_ids": self.failed_task_ids,
        }


@dataclass
class ContextPack:
    """A bounded view of internal state for a specific pipeline step.

    Encapsulates compressed evidence, critique (if available), a budget,
    and step metadata.  Intended to be the single argument passed to a
    future LLM tool-calling Lead Agent.
    """

    step: str
    evidence: list[EvidenceContext] = field(default_factory=list)
    critique: CritiqueContext | None = None
    budget: ContextBudget = field(default_factory=ContextBudget)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "evidence": [e.to_dict() for e in self.evidence],
            "critique": self.critique.to_dict() if self.critique else None,
            "budget": {
                "max_evidence_items": self.budget.max_evidence_items,
                "max_chars_per_evidence": self.budget.max_chars_per_evidence,
                "max_total_chars": self.budget.max_total_chars,
            },
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _truncate_text(text: str, max_chars: int) -> str:
    """Truncate *text* to *max_chars*, appending '…' when shortened."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def _estimate_chars(pack: ContextPack) -> int:
    """Rough character estimate of a ContextPack (for budget checks)."""
    total = len(pack.step)
    for ev in pack.evidence:
        total += len(ev.evidence_id) + len(ev.summary)
        total += sum(len(kp) for kp in ev.key_points)
        total += sum(len(lim) for lim in ev.limitations)
        total += len(ev.source_title)
        total += len(ev.source_publisher or "")
        total += len(ev.source_url or "")
    if pack.critique:
        total += len(pack.critique.decision)
        total += len(pack.critique.next_phase)
        total += sum(len(p) for p in pack.critique.missing_perspectives)
        total += sum(len(l) for l in pack.critique.limitations)
        total += sum(len(t) for t in pack.critique.failed_task_ids)
    return total


def _estimate_evidence_chars(ev: EvidenceContext) -> int:
    """Rough character count of a single EvidenceContext."""
    total = len(ev.evidence_id)
    total += len(ev.source_title)
    total += len(ev.source_publisher or "")
    total += len(ev.source_url or "")
    total += len(ev.summary)
    total += sum(len(kp) for kp in ev.key_points)
    total += sum(len(lim) for lim in ev.limitations)
    return total


def _compress_evidence(evidence: list[Any], budget: ContextBudget) -> list[EvidenceContext]:
    """Convert Evidence objects to EvidenceContext, respecting budget.

    Budget enforcement order:
    1. Cap count to max_evidence_items.
    2. Truncate each summary to max_chars_per_evidence.
    3. Stop adding items once estimated total chars exceeds max_total_chars.
    4. If even the first item exceeds max_total_chars, still keep it
       (evidence_id must never be dropped), but aggressively truncate
       key_points/limitations/summary to fit.
    """
    compressed: list[EvidenceContext] = []

    # Pre-compress each candidate
    candidates: list[EvidenceContext] = []
    for item in evidence[: budget.max_evidence_items]:
        url_str = str(item.source.url) if getattr(item.source, "url", None) else None
        ctx = EvidenceContext(
            evidence_id=item.evidence_id,
            source_title=getattr(item.source, "title", ""),
            source_publisher=getattr(item.source, "publisher", None),
            source_url=url_str,
            summary=_truncate_text(item.summary, budget.max_chars_per_evidence),
            key_points=list(item.key_points)[:5],
            limitations=list(item.limitations)[:5],
        )
        candidates.append(ctx)

    # Enforce max_total_chars
    running_chars = 0
    for ctx in candidates:
        item_chars = _estimate_evidence_chars(ctx)
        if compressed and (running_chars + item_chars > budget.max_total_chars):
            # Budget exceeded — stop adding more items (but never drop first)
            break
        if running_chars == 0 and item_chars > budget.max_total_chars and not compressed:
            # First item alone exceeds budget — aggressively truncate
            avail = budget.max_total_chars - len(ctx.evidence_id) - len(ctx.source_title) - len(ctx.source_publisher or "") - len(ctx.source_url or "")
            # Reserve ~40 chars for structure overhead
            avail = max(50, avail - 40)
            ctx.summary = _truncate_text(ctx.summary, avail // 2)
            ctx.key_points = []  # drop key_points under extreme budget
            ctx.limitations = []  # drop limitations
        compressed.append(ctx)
        running_chars += item_chars

    return compressed


# ---------------------------------------------------------------------------
# Context pack builders
# ---------------------------------------------------------------------------


def build_planning_context(
    brief: Any | None,
    tasks: list[Any] | None = None,
    budget: ContextBudget | None = None,
) -> ContextPack:
    """Build context for the planning step."""
    pack = ContextPack(
        step="planning",
        budget=budget or ContextBudget(),
        metadata={
            "objective": getattr(brief, "objective", "") if brief else "",
            "perspectives": list(getattr(brief, "perspectives", [])) if brief else [],
            "task_count": len(tasks) if tasks else 0,
        },
    )
    return pack


def build_research_context(
    evidence: list[Any],
    tasks: list[Any] | None = None,
    budget: ContextBudget | None = None,
) -> ContextPack:
    """Build context for the research step (compressed evidence)."""
    b = budget or ContextBudget()
    pack = ContextPack(
        step="research",
        evidence=_compress_evidence(evidence, b),
        budget=b,
        metadata={
            "total_evidence": len(evidence),
            "task_count": len(tasks) if tasks else 0,
        },
    )
    return pack


def build_writing_context(
    evidence: list[Any],
    draft: Any | None = None,
    budget: ContextBudget | None = None,
) -> ContextPack:
    """Build context for the writing step."""
    b = budget or ContextBudget()
    pack = ContextPack(
        step="writing",
        evidence=_compress_evidence(evidence, b),
        budget=b,
        metadata={
            "total_evidence": len(evidence),
            "has_draft": draft is not None,
            "claim_count": len(getattr(draft, "claims", [])) if draft else 0,
        },
    )
    return pack


def build_verification_context(
    verification: Any | None,
    evidence: list[Any],
    budget: ContextBudget | None = None,
) -> ContextPack:
    """Build context for the verification step."""
    b = budget or ContextBudget()
    claim_results = getattr(verification, "claim_results", []) if verification else []
    pack = ContextPack(
        step="verification",
        evidence=_compress_evidence(evidence, b),
        budget=b,
        metadata={
            "total_evidence": len(evidence),
            "claim_count": len(claim_results),
            "unsupported_claims": getattr(verification, "unsupported_claim_count", 0) if verification else 0,
        },
    )
    return pack


def build_critique_context(
    critique: Any | None,
    evidence: list[Any] | None = None,
    budget: ContextBudget | None = None,
) -> ContextPack:
    """Build context for the critique step — preserves decision & next_phase."""
    b = budget or ContextBudget()
    critique_ctx: CritiqueContext | None = None
    if critique:
        critique_ctx = CritiqueContext(
            decision=str(getattr(critique, "decision", "")),
            next_phase=str(getattr(critique, "next_phase", "")),
            missing_perspectives=list(getattr(critique, "missing_perspectives", [])),
            limitations=list(getattr(critique, "limitations_to_add", [])),
            failed_task_ids=list(getattr(critique, "failed_task_ids", [])),
        )
    pack = ContextPack(
        step="critique",
        evidence=_compress_evidence(evidence, b) if evidence else [],
        critique=critique_ctx,
        budget=b,
        metadata={},
    )
    return pack


def build_lead_decision_context(
    state: Any,
    budget: ContextBudget | None = None,
) -> ContextPack:
    """Build context for Lead Agent decision-making.

    Combines evidence and critique context into a single pack for
    the Lead Agent to decide the next tool call.
    """
    b = budget or ContextBudget()
    evidence = getattr(state, "evidence", []) or []
    critique = getattr(state, "critique_result", None)

    critique_ctx: CritiqueContext | None = None
    if critique:
        critique_ctx = CritiqueContext(
            decision=str(getattr(critique, "decision", "")),
            next_phase=str(getattr(critique, "next_phase", "")),
            missing_perspectives=list(getattr(critique, "missing_perspectives", [])),
            limitations=list(getattr(critique, "limitations_to_add", [])),
            failed_task_ids=list(getattr(critique, "failed_task_ids", [])),
        )

    pack = ContextPack(
        step="decision",
        evidence=_compress_evidence(evidence, b),
        critique=critique_ctx,
        budget=b,
        metadata={
            "status": getattr(state, "status", ""),
            "iteration_index": getattr(state, "iteration_index", 0),
            "max_iterations": getattr(state, "max_iterations", 1),
            "next_phase": getattr(state, "next_phase", None),
        },
    )
    return pack
