"""Researcher that compresses fixture sources into Evidence objects."""

from __future__ import annotations

from traceresearch.evidence.models import (
    Evidence,
    EvidenceStatus,
    ResearchTask,
    SourceDocument,
    SourceResult,
)
from traceresearch.source_discovery.base import SourceDiscoveryProvider, SourceRef


class Researcher:
    def research(
        self,
        *,
        run_id: str,
        task: ResearchTask,
        provider: SourceDiscoveryProvider,
        start_index: int,
    ) -> list[Evidence]:
        evidence_items: list[Evidence] = []
        results = provider.search(task, limit=task.source_limit)
        for offset, source in enumerate(results, start=start_index):
            document = provider.fetch(SourceRef(source_id=source.source_id, url=source.url))
            evidence_items.append(
                self._to_evidence(
                    run_id=run_id,
                    task=task,
                    source=source,
                    document=document,
                    sequence=offset,
                )
            )
        return evidence_items

    def _to_evidence(
        self,
        *,
        run_id: str,
        task: ResearchTask,
        source: SourceResult,
        document: SourceDocument,
        sequence: int,
    ) -> Evidence:
        metadata = document.metadata
        summary = str(metadata.get("summary") or document.content_excerpt).strip()
        supported_claims = _string_list(metadata.get("supported_claims"))
        key_points = _string_list(metadata.get("key_points"))
        limitations = _string_list(metadata.get("limitations"))
        if not supported_claims and summary:
            supported_claims = [summary]
        if not key_points and summary:
            key_points = [summary]
        if not limitations and source.provider == "web":
            limitations = ["Live web provider result should be reviewed for source freshness and relevance."]
        return Evidence(
            evidence_id=f"EV-{run_id}-{sequence:03d}",
            run_id=run_id,
            research_task_id=task.research_task_id,
            perspective=task.perspective,
            source=source,
            authority_score=float(metadata.get("authority_score", 0.5)),
            relevance_score=float(metadata.get("relevance_score", 0.5)),
            summary=summary,
            key_points=key_points,
            supported_claims=supported_claims,
            limitations=limitations,
            status=EvidenceStatus.CANDIDATE,
            verification_notes=[],
        )


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []
