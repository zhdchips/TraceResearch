# Eval Notes: Live Provider Demo Readiness

## Scope

Fixture eval is the required regression gate for feature `002-live-provider-demo-readiness`. Live web smoke is manual/non-CI because provider availability, quota, network behavior, ranking, and source freshness are outside deterministic regression control.

## Required Fixture Gate

Run:

```bash
python3 -m pytest
traceresearch eval --cases-dir eval/cases --source-provider fixture --results-dir eval/results
```

Expected:

- 5 seed cases execute.
- `case_pass_rate=1.0`.
- 9 required metrics are present.
- Bad-case notes are empty for a passing run.

## Manual Live Smoke: Configured Success

Run only when a local Exa credential is available:

```bash
export TRACERESEARCH_WEB_PROVIDER=exa
export EXA_API_KEY=
export TRACERESEARCH_WEB_TIMEOUT_SECONDS=10
export TRACERESEARCH_WEB_MAX_RESULTS=5

traceresearch run \
  --query "What changed in AI coding agents during the last 12 months?" \
  --source-provider web \
  --output-dir runs
```

Expected:

- CLI prints `run_id`, `status`, and `artifact_dir`.
- Completed run writes `final_report.md`, `evidence.jsonl`, `trace.jsonl`, and `report.json`.
- `final_report.md` key claims include `[EV-...]`.
- `evidence.jsonl` includes live source title, URL/source reference, retrieved_at, summary, and supported claims.
- `trace.jsonl` includes `exa.search` or clear provider failure event.

## Manual Live Smoke: Unconfigured Failure

Run:

```bash
unset EXA_API_KEY
traceresearch run \
  --query "What changed in AI coding agents during the last 12 months?" \
  --source-provider web \
  --output-dir runs
```

Expected:

- `status=failed`
- `error_type=provider_not_configured`
- no silent fallback to Fixture
- no fixture evidence generated

## Result Record Format

Use this format after running or intentionally skipping live smoke:

```text
date:
operator:
fixture_eval_result:
fixture_eval_summary_path:
live_smoke_status: success | failed | skipped
live_smoke_command:
live_smoke_artifact_dir:
live_smoke_error_type:
skip_reason:
notes:
```

## Latest Result

- Date: 2026-06-21 02:07:00 CST
- Full pytest: PASS, `117 passed`
- Fixture eval: PASS, 5 seed cases executed, 5/5 pass
- Fixture eval summary: `eval/results/eval-20260620180616-26276f94-summary.json`
- Required metrics: PASS, all 5 case results include 9 required metrics
- Unconfigured web smoke: PASS
  - Command:

    ```bash
    unset EXA_API_KEY
    traceresearch run --query "What changed in AI coding agents during the last 12 months?" --source-provider web --output-dir runs
    ```

  - Observed output:

    ```text
    status=failed
    error_type=provider_not_configured
    error_message=Source discovery provider is not configured: exa
    ```

  - No silent fallback to Fixture was observed.
- Configured live smoke: SUCCESS
  - Date: 2026-06-21 10:26:33 CST
  - Artifact dir: `runs/run-d09f5082`
  - Command:

    ```bash
    set -a
    source .env
    set +a
    export TRACERESEARCH_WEB_PROVIDER=exa
    export TRACERESEARCH_WEB_TIMEOUT_SECONDS=10
    export TRACERESEARCH_WEB_MAX_RESULTS=5
    export SSL_CERT_FILE="$(python3 -c 'import certifi; print(certifi.where())')"
    traceresearch run --query "What changed in AI coding agents during the last 12 months?" --source-provider web --output-dir runs
    ```
  - Observed output:

    ```text
    run_id=run-d09f5082
    status=completed
    artifact_dir=runs/run-d09f5082
    ```

  - Artifact checks:
    - `final_report.md`: present
    - `report.json`: present
    - `evidence.jsonl`: present, 14 evidence rows, provider `web`
    - `trace.jsonl`: present, includes `exa.search`
    - final report contains `[EV-...]` evidence references
  - Environment note: the first live attempt failed due local Python SSL certificate verification (`CERTIFICATE_VERIFY_FAILED`). Setting `SSL_CERT_FILE` to the local `certifi` CA bundle allowed the live smoke to run without disabling TLS verification.
  - Execution note: this local shell did not have the `traceresearch` console script installed, so the smoke was executed through the current checkout's equivalent Typer CLI app invocation with the same `run` arguments.

- Secret scan: PASS
  - `git ls-files | rg '(^|/)\.env$'` returned no tracked `.env`.
  - Targeted tracked-file scan outside test/tool/template paths found no real API key pattern.
  - Broad scan only matched known fake redaction tokens in tests and `Risk-001` text, not real secrets.

## Bad Cases

- None for fixture eval.
- Configured live smoke succeeded and generated `runs/run-d09f5082`.

## Next Review Focus

- Review `review.md` decision and Non-Goals check.
- Preserve `runs/run-d09f5082` as the current configured live demo artifact path.
