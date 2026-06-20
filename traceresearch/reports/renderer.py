"""Markdown report rendering helpers."""

from __future__ import annotations

from datetime import timezone

from traceresearch.evidence.models import Evidence


def render_evidence_references(evidence: list[Evidence]) -> str:
    if not evidence:
        return "- No verified evidence references."

    lines: list[str] = []
    for item in evidence:
        retrieved_at = item.source.retrieved_at
        if retrieved_at.tzinfo is not None:
            retrieved_at = retrieved_at.astimezone(timezone.utc)
        timestamp = retrieved_at.isoformat().replace("+00:00", "Z")
        limitation_notes = "; ".join(item.limitations) if item.limitations else "No explicit limitation notes."
        lines.append(
            f"- [{item.evidence_id}] {item.source.title} | "
            f"type={item.source.source_type.value} | "
            f"retrieved_at={timestamp} | "
            f"limitations={limitation_notes}"
        )
    return "\n".join(lines)
