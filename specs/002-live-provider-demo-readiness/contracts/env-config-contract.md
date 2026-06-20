# Environment Config Contract: Live Provider Demo Readiness

## `.env.example`

Required example keys:

```env
# Live web provider selection. Feature 002 supports exa first.
TRACERESEARCH_WEB_PROVIDER=exa

# Local-only secret. Do not commit real keys.
EXA_API_KEY=

# Provider behavior.
TRACERESEARCH_WEB_TIMEOUT_SECONDS=10
TRACERESEARCH_WEB_MAX_RESULTS=5
```

Rules:

- `.env.example` must contain placeholders only.
- `.env` must remain ignored.
- Real API keys must not appear in tracked files, Trace, CLI output, report artifacts, or test fixtures.

## Config Loading

Inputs:

- Process environment variables.
- Optional `.env` loading may be documented for humans, but implementation must not require a third-party dotenv dependency unless planned separately.

Defaults:

- `TRACERESEARCH_WEB_PROVIDER`: `exa`
- `TRACERESEARCH_WEB_TIMEOUT_SECONDS`: `10`
- `TRACERESEARCH_WEB_MAX_RESULTS`: `5`

Validation:

- Missing or blank `EXA_API_KEY` -> `provider_not_configured`.
- Unsupported `TRACERESEARCH_WEB_PROVIDER` -> `provider_not_configured` or `provider_error` with clear message.
- Non-positive timeout/max results -> validation error with safe message.

Redaction:

- Config objects may expose `has_api_key`.
- Config string/repr/error output must not include `EXA_API_KEY` value.
