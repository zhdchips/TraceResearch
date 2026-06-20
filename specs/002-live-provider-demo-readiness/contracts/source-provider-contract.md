# Source Provider Contract: Live Provider Demo Readiness

## Existing Interface

`SourceDiscoveryProvider` continues to expose:

```text
search(task, limit) -> SourceResult[]
fetch(source_ref) -> SourceDocument
```

## `ExaSearchProvider.search`

Inputs:

- `ResearchTask.research_task_id`
- `ResearchTask.query`
- `ResearchTask.perspective`
- `limit`
- `LiveProviderConfig`

Provider request:

- Endpoint: Exa `/search`
- Auth: `x-api-key` header from local environment
- Body includes query, bounded result count, and contents highlights/summary where supported.

Outputs:

- Ordered `SourceResult[]`.
- `provider` should remain `web`; provider-specific metadata should identify Exa.
- Empty array is allowed only when no-results reason is recorded by harness/researcher/Trace.

Required normalization:

- title -> `SourceResult.title`
- URL -> `SourceResult.url`
- highlights/summary/text excerpt -> `SourceResult.snippet` and `SourceDocument.content_excerpt`
- published date -> `SourceResult.published_at` when parseable
- rank -> `SourceResult.provider_rank`
- source type guess -> `SourceResult.source_type`
- retrieved_at -> current UTC timestamp

## `ExaSearchProvider.fetch`

Inputs:

- `SourceRef.source_id`
- `SourceRef.url`

Behavior:

- For first implementation, fetch may return the normalized content already captured during search if Exa search includes highlights/summary.
- It must not perform extra full-page crawling unless explicitly planned later.

Outputs:

- `SourceDocument` with compressed `content_excerpt` and redacted metadata.

## Error Contract

Errors:

- `provider_not_configured`
- `provider_timeout`
- `provider_rate_limited`
- `provider_error`
- `provider_no_results`
- `source_normalization_error`

Requirements:

- All errors must be safe for CLI and Trace.
- No error may contain `EXA_API_KEY`.
- `--source-provider web` must not fallback to fixture on any error.
