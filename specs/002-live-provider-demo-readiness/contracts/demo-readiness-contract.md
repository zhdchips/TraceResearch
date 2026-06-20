# Demo Readiness Contract

## README Required Sections

Root `README.md` must include:

- Project positioning: Deep Research multi-agent CLI prototype.
- Architecture overview: `Planner`, `Researcher`, `Verifier`, `Critic`, `Writer`, `Evidence Store`, `Trace Log`, provider abstraction.
- Fixture demo path.
- Live web demo path.
- Configuration and secret handling.
- Eval/review workflow.
- Artifact inspection instructions.
- Limitations and Non-Goals.
- Interview screen-share demo path.

## Fixture Demo Path

Must include:

```text
python3 -m pytest
traceresearch run --query "<fixture-compatible query>" --source-provider fixture --case-id 001-framework-comparison
traceresearch eval --cases-dir eval/cases --source-provider fixture --results-dir eval/results
```

Expected explanation:

- Deterministic.
- No API key needed.
- Good for regression and demo fallback.

## Live Demo Path

Must include:

```text
export TRACERESEARCH_WEB_PROVIDER=exa
export EXA_API_KEY=<your-local-key>
traceresearch run --query "<live research query>" --source-provider web --output-dir runs
```

Expected explanation:

- Requires network and provider account.
- Not default CI gate.
- Results may vary.
- Inspect `final_report.md`, `evidence.jsonl`, `trace.jsonl`.

## Unconfigured Failure Demo

Must include:

```text
unset EXA_API_KEY
traceresearch run --query "<live research query>" --source-provider web --output-dir runs
```

Expected result:

- `status=failed`
- `error_type=provider_not_configured`
- no silent fallback to fixture

## Limitations

README must state:

- No Web UI.
- No LLM-backed agents in this feature.
- Fixture eval remains source of deterministic quality signal.
- Live provider can vary by network, quota, ranking, and source availability.
- Do not commit API keys.
