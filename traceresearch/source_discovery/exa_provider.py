"""Exa live web source discovery provider."""

from __future__ import annotations

import hashlib
import json
import socket
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from typing import Any

from pydantic import HttpUrl

from traceresearch.config import LiveProviderConfig
from traceresearch.evidence.models import (
    ResearchTask,
    SourceDocument,
    SourceResult,
    SourceType,
)
from traceresearch.source_discovery.base import (
    ProviderNoResultsError,
    ProviderNotConfiguredError,
    ProviderRateLimitedError,
    ProviderServiceError,
    ProviderTimeoutError,
    SourceNormalizationError,
    SourceRef,
    SourceDiscoveryProvider,
)


class ExaSearchProvider(SourceDiscoveryProvider):
    provider_name = "web"
    provider_display_name = "exa"
    tool_name = "exa.search"

    def __init__(self, *, config: LiveProviderConfig) -> None:
        self.config = config
        self._documents: dict[str, SourceDocument] = {}

    def search(self, task: ResearchTask, limit: int) -> list[SourceResult]:
        if not self.config.has_api_key:
            raise ProviderNotConfiguredError(self.provider_display_name)

        request_limit = max(1, min(limit, self.config.max_results))
        body = {
            "query": task.query,
            "numResults": request_limit,
            "contents": {
                "highlights": True,
                "summary": True,
                "text": True,
            },
        }
        try:
            payload = self._post_search(body)
        except TimeoutError as exc:
            raise ProviderTimeoutError(
                self.provider_display_name,
                "search",
                message="Exa search timed out.",
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            if isinstance(exc, socket.timeout):
                raise ProviderTimeoutError(
                    self.provider_display_name,
                    "search",
                    message="Exa search timed out.",
                ) from exc
            raise ProviderServiceError(
                self.provider_display_name,
                "search",
                message="Exa search request failed.",
            ) from exc

        results = payload.get("results") if isinstance(payload, dict) else None
        if not results:
            raise ProviderNoResultsError(self.provider_display_name)
        if not isinstance(results, list):
            raise SourceNormalizationError(self.provider_display_name)

        request_id = _optional_str(payload.get("requestId"))
        normalized: list[SourceResult] = []
        for rank, item in enumerate(results[:request_limit], start=1):
            if not isinstance(item, dict):
                raise SourceNormalizationError(self.provider_display_name)
            source, document = self._normalize_result(
                item,
                provider_rank=rank,
                request_id=request_id,
            )
            normalized.append(source)
            self._documents[source.source_id] = document

        if not normalized:
            raise ProviderNoResultsError(self.provider_display_name)
        return normalized

    def fetch(self, source_ref: SourceRef) -> SourceDocument:
        try:
            return self._documents[source_ref.source_id]
        except KeyError as exc:
            raise SourceNormalizationError(
                self.provider_display_name,
                "fetch",
                message=f"Source document is not cached: {source_ref.source_id}",
            ) from exc

    def _post_search(self, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.config.base_url.rstrip('/')}/search"
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.config.api_key or "",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.config.timeout_seconds,
            ) as response:
                self._raise_for_http_status(response.status, "")
                data = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body_text = _safe_decode(exc.read())
            self._raise_for_http_status(exc.code, body_text)
        except socket.timeout as exc:
            raise TimeoutError("Exa search timed out") from exc

        try:
            payload = json.loads(data)
        except json.JSONDecodeError as exc:
            raise SourceNormalizationError(
                self.provider_display_name,
                message="Exa search response was not valid JSON.",
            ) from exc
        if not isinstance(payload, dict):
            raise SourceNormalizationError(self.provider_display_name)
        return payload

    def _raise_for_http_status(self, status_code: int, body_text: str) -> None:
        message = _safe_provider_message(status_code, body_text)
        if status_code in {401, 403}:
            raise ProviderNotConfiguredError(self.provider_display_name)
        if status_code == 429:
            raise ProviderRateLimitedError(
                self.provider_display_name,
                "search",
                message=message or "Exa rate limit exceeded.",
                status_code=status_code,
            )
        if status_code >= 500:
            raise ProviderServiceError(
                self.provider_display_name,
                "search",
                message=message or "Exa provider error.",
                status_code=status_code,
            )
        if status_code >= 400:
            raise ProviderServiceError(
                self.provider_display_name,
                "search",
                message=message or "Exa request failed.",
                status_code=status_code,
                retryable=False,
            )

    def _normalize_result(
        self,
        item: dict[str, Any],
        *,
        provider_rank: int,
        request_id: str | None,
    ) -> tuple[SourceResult, SourceDocument]:
        title = _optional_str(item.get("title"))
        url = _optional_str(item.get("url"))
        highlights = _string_list(item.get("highlights"))
        summary = _optional_str(item.get("summary"))
        text = _optional_str(item.get("text"))
        snippet = _first_text(highlights + [summary, text])

        if not (title or url) or not snippet:
            raise SourceNormalizationError(self.provider_display_name)

        source_id = _source_id(item, url=url)
        retrieved_at = datetime.now(timezone.utc)
        source = SourceResult(
            source_id=source_id,
            provider=self.provider_name,
            title=title or url or source_id,
            url=url,
            source_type=_guess_source_type(url, title),
            publisher=_optional_str(item.get("author")) or _publisher_from_url(url),
            published_at=_parse_date(_optional_str(item.get("publishedDate"))),
            retrieved_at=retrieved_at,
            snippet=snippet,
            provider_rank=provider_rank,
        )
        document = SourceDocument(
            source_id=source_id,
            title=source.title,
            url=source.url,
            content_excerpt=_bound_excerpt(_first_text([summary] + highlights + [text])),
            metadata={
                "provider": self.provider_name,
                "provider_name": self.provider_display_name,
                "provider_request_id": request_id,
                "provider_rank": provider_rank,
                "provider_score": item.get("score"),
                "source_type": source.source_type.value,
                "author": _optional_str(item.get("author")),
                "published_at": source.published_at.isoformat() if source.published_at else None,
                "highlights": highlights,
                "summary": summary,
                "key_points": highlights[:3] or ([summary] if summary else []),
                "supported_claims": [summary] if summary else highlights[:1],
                "limitations": _limitations(item, text=text, highlights=highlights, summary=summary),
                "authority_score": _authority_score(source.source_type),
                "relevance_score": float(item.get("score") or 0.7),
            },
            retrieved_at=retrieved_at,
        )
        return source, document


def _safe_decode(value: bytes) -> str:
    return value.decode("utf-8", errors="replace") if value else ""


def _safe_provider_message(status_code: int, body_text: str) -> str:
    body = body_text.strip()
    if len(body) > 160:
        body = body[:157] + "..."
    return f"Exa provider returned HTTP {status_code}: {body}" if body else f"Exa provider returned HTTP {status_code}."


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _first_text(values: list[str | None]) -> str:
    for value in values:
        if value and value.strip():
            return _bound_excerpt(value.strip())
    return ""


def _bound_excerpt(value: str, *, limit: int = 1200) -> str:
    return value if len(value) <= limit else value[: limit - 3].rstrip() + "..."


def _source_id(item: dict[str, Any], *, url: str | None) -> str:
    raw_id = _optional_str(item.get("id")) or url or _optional_str(item.get("title")) or "source"
    digest = hashlib.sha1(raw_id.encode("utf-8")).hexdigest()[:12]
    return f"exa:{digest}"


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _publisher_from_url(url: str | None) -> str | None:
    if not url:
        return None
    stripped = url.removeprefix("https://").removeprefix("http://")
    return stripped.split("/", 1)[0] or None


def _guess_source_type(url: str | None, title: str | None) -> SourceType:
    text = f"{url or ''} {title or ''}".lower()
    if "github.com" in text:
        return SourceType.REPO
    if "arxiv.org" in text or "paper" in text:
        return SourceType.PAPER
    if "docs." in text or "/docs" in text or "documentation" in text:
        return SourceType.OFFICIAL_DOC
    if "report" in text:
        return SourceType.REPORT
    if "news" in text:
        return SourceType.NEWS
    if "blog" in text:
        return SourceType.BLOG
    return SourceType.UNKNOWN


def _authority_score(source_type: SourceType) -> float:
    return {
        SourceType.OFFICIAL_DOC: 0.9,
        SourceType.PAPER: 0.85,
        SourceType.REPO: 0.8,
        SourceType.REPORT: 0.75,
        SourceType.NEWS: 0.65,
        SourceType.BLOG: 0.55,
        SourceType.UNKNOWN: 0.5,
    }[source_type]


def _limitations(
    item: dict[str, Any],
    *,
    text: str | None,
    highlights: list[str],
    summary: str | None,
) -> list[str]:
    notes: list[str] = []
    if not _optional_str(item.get("publishedDate")):
        notes.append("Provider result did not include a published date.")
    if not text:
        notes.append("Provider result did not include full text; using highlights or summary.")
    if not highlights and not summary:
        notes.append("Provider result had limited extracted context.")
    return notes
