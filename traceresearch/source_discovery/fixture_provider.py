"""Deterministic source discovery provider backed by local eval fixtures."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from traceresearch.evidence.models import (
    EvalCase,
    ResearchTask,
    SourceDocument,
    SourceResult,
    SourceType,
)
from traceresearch.source_discovery.base import (
    SourceDiscoveryError,
    SourceDiscoveryProvider,
    SourceRef,
)


class FixtureSourceError(SourceDiscoveryError):
    code = "fixture_source_error"


class FixtureCaseNotFoundError(FixtureSourceError):
    code = "fixture_case_not_found"

    def __init__(self, case_id: str) -> None:
        super().__init__(f"Fixture eval case not found: {case_id}")
        self.case_id = case_id


class FixtureSourceNotFoundError(FixtureSourceError):
    code = "fixture_source_not_found"

    def __init__(self, source_id: str) -> None:
        super().__init__(f"Fixture source not found: {source_id}")
        self.source_id = source_id


class FixtureSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: HttpUrl | None = None
    source_type: SourceType
    publisher: str | None = None
    published_at: date | None = None
    retrieved_at: datetime
    snippet: str = Field(min_length=1)
    content_excerpt: str = Field(min_length=1)
    perspectives: list[str] = Field(default_factory=list)
    task_keywords: list[str] = Field(default_factory=list)
    supported_claims: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    authority_signal: str = Field(min_length=1)
    authority_score: float = Field(ge=0.0, le=1.0)
    relevance_score: float = Field(ge=0.0, le=1.0)
    conflicting_evidence: bool = False
    case_id: str = Field(min_length=1)

    def to_source_result(self, provider_rank: int) -> SourceResult:
        return SourceResult(
            source_id=self.source_id,
            provider=FixtureSourceProvider.provider_name,
            title=self.title,
            url=self.url,
            source_type=self.source_type,
            publisher=self.publisher,
            published_at=self.published_at,
            retrieved_at=self.retrieved_at,
            snippet=self.snippet,
            provider_rank=provider_rank,
        )

    def to_source_document(self) -> SourceDocument:
        return SourceDocument(
            source_id=self.source_id,
            title=self.title,
            url=self.url,
            content_excerpt=self.content_excerpt,
            metadata={
                "provider": FixtureSourceProvider.provider_name,
                "case_id": self.case_id,
                "source_type": self.source_type.value,
                "publisher": self.publisher,
                "published_at": self.published_at.isoformat() if self.published_at else None,
                "perspectives": self.perspectives,
                "task_keywords": self.task_keywords,
                "supported_claims": self.supported_claims,
                "key_points": self.key_points,
                "limitations": self.limitations,
                "authority_signal": self.authority_signal,
                "authority_score": self.authority_score,
                "relevance_score": self.relevance_score,
                "conflicting_evidence": self.conflicting_evidence,
            },
            retrieved_at=self.retrieved_at,
        )


class FixtureSourceProvider(SourceDiscoveryProvider):
    provider_name = "fixture"

    def __init__(
        self,
        *,
        cases_dir: Path | str = Path("eval/cases"),
        sources_dir: Path | str = Path("eval/fixtures/sources"),
        case_id: str | None = None,
    ) -> None:
        self.cases_dir = Path(cases_dir)
        self.sources_dir = Path(sources_dir)
        self.case_id = case_id
        self._cases: dict[str, EvalCase] | None = None
        self._sources: dict[str, FixtureSource] | None = None

    def for_case(self, case_id: str) -> "FixtureSourceProvider":
        return FixtureSourceProvider(
            cases_dir=self.cases_dir,
            sources_dir=self.sources_dir,
            case_id=case_id,
        )

    def load_eval_cases(self) -> dict[str, EvalCase]:
        if self._cases is None:
            cases: dict[str, EvalCase] = {}
            for path in sorted(self.cases_dir.glob("*.yml")):
                data = _read_yaml_mapping(path)
                case = EvalCase.model_validate(data)
                cases[case.case_id] = case
            self._cases = dict(sorted(cases.items()))
        return self._cases

    def load_eval_case(self, case_id: str) -> EvalCase:
        try:
            return self.load_eval_cases()[case_id]
        except KeyError as exc:
            raise FixtureCaseNotFoundError(case_id) from exc

    def load_fixture_sources(self) -> dict[str, FixtureSource]:
        if self._sources is None:
            sources: dict[str, FixtureSource] = {}
            for path in sorted(self.sources_dir.glob("*.yml")):
                data = _read_yaml_mapping(path)
                case_id = str(data.get("case_id", "")).strip()
                for source_data in data.get("sources", []) or []:
                    source = FixtureSource.model_validate(
                        {**source_data, "case_id": source_data.get("case_id", case_id)}
                    )
                    sources[source.source_id] = source
            self._sources = dict(sorted(sources.items()))
        return self._sources

    def load_fixture_source(self, source_id: str) -> FixtureSource:
        try:
            return self.load_fixture_sources()[source_id]
        except KeyError as exc:
            raise FixtureSourceNotFoundError(source_id) from exc

    def search(self, task: ResearchTask, limit: int) -> list[SourceResult]:
        case_id = self._resolve_case_id(task)
        if case_id is None:
            return self._rank_sources(list(self.load_fixture_sources().values()), task, limit)
        return self.search_for_case(case_id, task, limit)

    def search_for_case(
        self,
        case_id: str,
        task: ResearchTask,
        limit: int,
    ) -> list[SourceResult]:
        if limit <= 0:
            return []

        case = self.load_eval_case(case_id)
        all_sources = self.load_fixture_sources()
        case_sources = [
            all_sources[source_id]
            for source_id in case.fixture_source_ids
            if source_id in all_sources
        ]
        return self._rank_sources(case_sources, task, limit)

    def fetch(self, source_ref: SourceRef) -> SourceDocument:
        return self.load_fixture_source(source_ref.source_id).to_source_document()

    def _resolve_case_id(self, task: ResearchTask) -> str | None:
        if self.case_id:
            return self.case_id

        cases = self.load_eval_cases()
        if task.run_id in cases:
            return task.run_id

        matching_cases = [
            case_id
            for case_id in cases
            if task.run_id.startswith(case_id) or case_id in task.research_task_id
        ]
        if len(matching_cases) == 1:
            return matching_cases[0]
        return None

    def _rank_sources(
        self,
        sources: list[FixtureSource],
        task: ResearchTask,
        limit: int,
    ) -> list[SourceResult]:
        if limit <= 0:
            return []

        scored = [
            (self._score_source(source, task), index, source)
            for index, source in enumerate(sources)
        ]
        matched = [
            (score, index, source)
            for score, index, source in scored
            if score > 0
        ]
        matched.sort(key=lambda item: (-item[0], item[1], item[2].source_id))
        return [
            source.to_source_result(provider_rank=rank)
            for rank, (_score, _index, source) in enumerate(matched[:limit], start=1)
        ]

    def _score_source(self, source: FixtureSource, task: ResearchTask) -> int:
        query_text = f"{task.perspective} {task.query}".lower()
        score = 0

        if task.perspective.lower() in {p.lower() for p in source.perspectives}:
            score += 8

        for keyword in source.task_keywords:
            if keyword.lower() in query_text:
                score += 3

        for perspective in source.perspectives:
            if perspective.lower() in query_text:
                score += 2

        title_terms = [term for term in source.title.lower().split() if len(term) > 3]
        score += sum(1 for term in title_terms if term in query_text)
        return score


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping in {path}")
    return data
