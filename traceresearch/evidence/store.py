"""Filesystem-backed Evidence Store."""

from __future__ import annotations

import json
from pathlib import Path

from traceresearch.evidence.models import Evidence, EvidenceStatus


class EvidenceStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def add(self, evidence: Evidence) -> Evidence:
        existing = self.find_duplicate(evidence)
        if existing is not None:
            return existing

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as file:
            file.write(
                json.dumps(
                    evidence.model_dump(mode="json"),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
            file.write("\n")
        return evidence

    def list_all(self) -> list[Evidence]:
        if not self.path.exists():
            return []
        items: list[Evidence] = []
        with self.path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                items.append(Evidence.model_validate_json(line))
        return items

    def get(self, evidence_id: str) -> Evidence | None:
        for evidence in self.list_all():
            if evidence.evidence_id == evidence_id:
                return evidence
        return None

    def find_duplicate(self, evidence: Evidence) -> Evidence | None:
        new_key = _dedupe_key(evidence)
        for existing in self.list_all():
            if _dedupe_key(existing) == new_key:
                return existing
        return None

    def update_status(
        self,
        evidence_id: str,
        status: EvidenceStatus,
        verification_notes: list[str],
    ) -> Evidence:
        items = self.list_all()
        updated_items: list[Evidence] = []
        updated: Evidence | None = None
        for item in items:
            if item.evidence_id == evidence_id:
                item = item.model_copy(
                    update={
                        "status": status,
                        "verification_notes": verification_notes,
                    }
                )
                updated = item
            updated_items.append(item)

        if updated is None:
            raise KeyError(evidence_id)

        self._replace_all(updated_items)
        return updated

    def _replace_all(self, items: list[Evidence]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            for item in items:
                file.write(
                    json.dumps(
                        item.model_dump(mode="json"),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
                file.write("\n")


def _dedupe_key(evidence: Evidence) -> tuple[str, str]:
    source = evidence.source
    if source.url is not None:
        normalized_url = str(source.url).rstrip("/")
        return ("url", normalized_url)

    publisher = (source.publisher or "").strip().lower()
    title = source.title.strip().lower()
    retrieved_date = source.retrieved_at.date().isoformat()
    return ("fixture", f"{title}|{publisher}|{retrieved_date}")
