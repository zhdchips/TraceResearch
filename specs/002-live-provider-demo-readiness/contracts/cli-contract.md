# CLI Contract: Live Provider Demo Readiness

## Command: `traceresearch run --source-provider web`

Purpose: 对明确 research query 使用 live web provider 执行一次 Deep Research run。

Inputs:

```text
traceresearch run \
  --query "<research question>" \
  --source-provider web \
  --output-dir runs
```

Environment:

- `TRACERESEARCH_WEB_PROVIDER=exa`
- `EXA_API_KEY=<local secret>`
- `TRACERESEARCH_WEB_TIMEOUT_SECONDS=<positive number>`
- `TRACERESEARCH_WEB_MAX_RESULTS=<positive integer>`

Success outputs:

- Prints `run_id`, `status=completed`, and `artifact_dir`.
- Writes run artifacts under `runs/<run_id>/`.
- Required completed artifacts:
  - `research_brief.json`
  - `research_tasks.json`
  - `evidence.jsonl`
  - `verification.json`
  - `critique.json`
  - `outline.md`
  - `draft_report.md`
  - `final_report.md`
  - `report.json`
  - `trace.jsonl`

Unconfigured behavior:

- If `EXA_API_KEY` is missing or blank, CLI prints:
  - `status=failed`
  - `error_type=provider_not_configured`
  - `error_message=<safe message>`
- It must not create fixture evidence.
- It must not silently fallback to `FixtureSourceProvider`.

Provider error behavior:

- Timeout, rate limit, provider HTTP errors, schema normalization errors, and no-results outcomes must produce explicit status/error or limitation artifacts.
- Error messages must not include API keys.
- Trace must include provider operation and safe error.

## Command: `traceresearch eval --source-provider fixture`

Purpose: 保持 deterministic regression eval。

Inputs:

```text
traceresearch eval \
  --cases-dir eval/cases \
  --source-provider fixture \
  --results-dir eval/results
```

Required result:

- 5 seed cases run.
- `case_pass_rate=1.0`.
- 9 required metrics present.
- Live provider configuration must not alter fixture eval output.

## Live Smoke Command

Manual only:

```text
traceresearch run \
  --query "What changed in AI coding agents during the last 12 months?" \
  --source-provider web \
  --output-dir runs
```

Validation:

- Configured success: final report, evidence, trace exist.
- Unconfigured failure: `provider_not_configured`, no fallback.
- Not part of default pytest/CI gate.
