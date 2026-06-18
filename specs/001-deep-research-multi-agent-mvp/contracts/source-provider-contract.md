# Source Provider Contract: Deep Research Multi-Agent MVP

## Interface

`SourceDiscoveryProvider` exposes two operations:

```text
search(task, limit) -> SourceResult[]
fetch(source_ref) -> SourceDocument
```

## `search`

Inputs:

- `task.research_task_id`
- `task.query`
- `task.perspective`
- `limit`

Outputs:

- Ordered `SourceResult[]`
- Empty array is allowed only with a no-evidence reason recorded by `Researcher`

Required `SourceResult` fields:

- `source_id`
- `provider`
- `title`
- `url`
- `source_type`
- `publisher`
- `published_at`
- `retrieved_at`
- `snippet`
- `provider_rank`

## `fetch`

Inputs:

- `source_id`
- `url` or fixture reference

Outputs:

- `SourceDocument` with `content_excerpt`, title, metadata, and retrieval timestamp.

## Providers

### `FixtureSourceProvider`

MVP required. Reads stable local fixture sources for seed eval cases.

Behavior:

- Deterministic ordering.
- No network required.
- Must exercise the same `search` and `fetch` contract as future live providers.

### `WebSearchProviderStub`

MVP optional stub. Defines provider configuration and not-configured error.

Behavior:

- If selected without configuration, returns explicit `provider_not_configured`.
- Must write Trace error event.
- Must not silently fall back to fixture sources.
