# Data Model: Live Provider Demo Readiness

## LiveProviderConfig

Fields:

- `provider_name`: string, required, default `exa`
- `api_key`: secret string, optional in memory only, never serialized to Trace/report
- `has_api_key`: boolean, derived
- `timeout_seconds`: positive number, default from environment or project default
- `max_results`: positive integer, default from environment or project default
- `base_url`: URL string, default provider endpoint

Validation:

- `provider_name` must be a supported live provider value for this feature: `exa`.
- `timeout_seconds` must be greater than 0.
- `max_results` must be at least 1.
- Missing or blank API key must map to `provider_not_configured`.
- String representation and error payloads must not include `api_key`.

## LiveSourceResult

Represents a normalized live web search result before conversion to `Evidence`.

Fields:

- `source_id`: stable string, required; derived from provider result ID or URL hash
- `provider`: `web`
- `provider_name`: `exa`
- `provider_request_id`: string or null
- `title`: string
- `url`: string or null
- `snippet`: string
- `highlights`: string[]
- `summary`: string or null
- `author`: string or null
- `published_at`: date/datetime or null
- `retrieved_at`: datetime
- `provider_rank`: integer starting at 1
- `provider_score`: number or null
- `raw_metadata`: redacted provider metadata object

Validation:

- Must have at least title or URL and at least one text-bearing field: snippet, highlight, summary, or text excerpt.
- Must not contain secrets.
- `provider_rank` starts at 1 per task result set.

## LiveSourceDocument

Represents fetch/contents data returned to `Researcher`.

Fields:

- `source_id`: string
- `title`: string
- `url`: string or null
- `content_excerpt`: string
- `metadata`: object
- `retrieved_at`: datetime

Validation:

- `content_excerpt` is compressed from highlights/summary/text and must be bounded for Writer-safe context.
- Metadata may include provider request ID, source type guess, author, published date, score, and limitations.

## ProviderError

Fields:

- `code`: `provider_not_configured | provider_timeout | provider_error | provider_rate_limited | provider_no_results | source_normalization_error`
- `provider_name`: string
- `operation`: `search | fetch | config`
- `message`: safe user-facing string
- `retryable`: boolean
- `status_code`: integer or null
- `latency_ms`: integer or null

Validation:

- `message` must not include API keys or request headers.
- Timeout and rate limit errors are retryable.
- Configuration errors are not retryable without user action.

## WebRunMode

State values:

- `fixture`: deterministic regression provider selected
- `web_unconfigured`: web selected but missing credential
- `web_running`: live provider request in progress
- `web_completed`: live provider returned usable evidence and run completed
- `web_no_results`: live provider returned no usable source
- `web_failed`: live provider failed safely

Transitions:

```text
fixture -> completed | needs_clarification | failed
web_unconfigured -> failed
web_running -> web_completed | web_no_results | web_failed
web_completed -> completed
web_no_results -> failed | completed_with_limitations
web_failed -> failed
```

## DemoRun

Fields:

- `query`: string
- `source_provider`: `fixture | web`
- `expected_mode`: `regression | live_success | live_unconfigured_failure`
- `artifact_dir`: path or null
- `result_file`: path or null
- `inspection_steps`: string[]
- `limitations`: string[]

Validation:

- README demo path must include one fixture regression path.
- README demo path must include live configured success command and unconfigured graceful failure command.
