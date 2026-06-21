# TraceResearch

TraceResearch is a CLI-first Deep Research multi-agent prototype for producing evidence-grounded research reports. It takes a technical or business research question, runs a deterministic Agent Harness, stores source-grounded Evidence Store rows, writes a Trace Log, and emits inspectable artifacts such as `final_report.md`, `evidence.jsonl`, `trace.jsonl`, and `report.json`.

The project is intentionally small enough for an interview screen-share while still showing the important system shape: source discovery provider abstraction, Agent roles, evidence grounding, traceability, and eval/review workflow.

## Architecture

The harness executes the same ordered flow for Fixture and Live web modes:

```text
Planner
  -> Researcher
  -> Evidence Store
  -> Writer draft claims
  -> Verifier
  -> Critic
  -> Writer final report
  -> Trace Log
```

Core roles:

- Planner creates the research brief, perspectives, assumptions, and tasks.
- Researcher calls the selected source provider and compresses source metadata into evidence candidates.
- Evidence Store writes deduplicated `evidence.jsonl` rows.
- Writer drafts claims and later writes the final report.
- Verifier checks draft claims against evidence IDs.
- Critic checks coverage, weak support, and limitations.
- Trace Log records Agent steps, source provider calls, errors, and artifact-producing stages.

Source providers:

- Fixture provider is deterministic and powers regression tests and eval.
- Live web provider currently uses Exa through `--source-provider web`.

## Fixture Demo

Fixture mode needs no API key and is the default reliability path.

```bash
python3 -m pytest

traceresearch run \
  --query "Compare LangGraph, AutoGen, and CrewAI for building research agents" \
  --source-provider fixture \
  --case-id 001-framework-comparison \
  --output-dir runs

traceresearch eval --cases-dir eval/cases --source-provider fixture --results-dir eval/results
```

After a run, inspect:

```bash
RUN_DIR="runs/<run_id>"
ls "$RUN_DIR"
sed -n '1,120p' "$RUN_DIR/final_report.md"
head -3 "$RUN_DIR/evidence.jsonl"
head -5 "$RUN_DIR/trace.jsonl"
```

## Live web Demo

Live web mode is for manual demo smoke, not for default CI. Results vary by network, quota, ranking, and source availability.

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

Configured success should print `run_id`, `status=completed`, and `artifact_dir`. Inspect `final_report.md`, `evidence.jsonl`, and `trace.jsonl` to verify live source title, URL, retrieved timestamp, and evidence IDs.

Unconfigured failure is also a valid demo path:

```bash
unset EXA_API_KEY
traceresearch run \
  --query "What changed in AI coding agents during the last 12 months?" \
  --source-provider web \
  --output-dir runs
```

Expected output includes `status=failed` and `error_type=provider_not_configured`, with no silent fallback to Fixture.

## LLM-backed Writer / Verifier (Feature 003)

The deterministic Writer and Verifier can optionally be replaced with LLM-backed implementations for more natural report generation and semantic claim verification.

### Default: Deterministic Mode

```bash
# No configuration needed — deterministic Writer/Verifier is the default.
traceresearch run --query "Your research question" --source-provider fixture --case-id 001-framework-comparison --output-dir runs
```

### LLM Writer Mode

```bash
# Configure LLM provider (see .env.example)
export DEEPSEEK_API_KEY="sk-..."
# Optional: export TRACERESEARCH_WRITER_MODE=llm

traceresearch run \
  --query "Your research question" \
  --source-provider fixture \
  --case-id 001-framework-comparison \
  --writer-mode llm \
  --output-dir runs
```

### LLM Verifier Mode

```bash
traceresearch run \
  --query "Your research question" \
  --source-provider fixture \
  --case-id 001-framework-comparison \
  --verifier-mode llm \
  --output-dir runs
```

### Both LLM Modes

```bash
traceresearch run \
  --query "Your research question" \
  --source-provider fixture \
  --case-id 001-framework-comparison \
  --writer-mode llm \
  --verifier-mode llm \
  --output-dir runs
```

**Key behaviors**:

- Without API key, mode "llm" auto-falls-back to deterministic.
- LLM provider failure (timeout, rate limit, invalid response) also safely falls back to deterministic.
- Trace records `llm_mode`, `llm_model`, `llm_token_usage`, and `failover_reason`.

### LLM Smoke Eval (Manual Only)

```bash
# LLM smoke eval is manual — it is NOT part of default pytest/CI.
traceresearch llm-smoke
```

Without API key, it runs deterministic baseline; with key, it uses the real LLM.

## Secret Handling

Use `.env.example` as the template, but keep real credentials in your local shell or ignored `.env`.

```bash
cp .env.example .env
```

Do not commit API keys. Real secrets must not appear in tracked files, CLI output, Trace Log, Evidence Store, or report artifacts.

## Eval and Review

Fixture eval is the required regression gate:

```bash
traceresearch eval --cases-dir eval/cases --source-provider fixture --results-dir eval/results
```

Expected fixture result:

- 5 seed cases run.
- `case_pass_rate=1.0`.
- 9 required metrics are present.
- Bad-case notes are empty for a passing run.

Live web smoke is manual/non-CI. Record the result or skip reason in `specs/002-live-provider-demo-readiness/eval.md`, then capture review findings in `review.md` during the review phase.

## Artifact Inspection

Useful checks after any completed run:

```bash
RUN_DIR="runs/<run_id>"
rg -o "\[EV-[^]]+\]" "$RUN_DIR/final_report.md" | head -1
python3 - <<'PY'
import json
from pathlib import Path

run_dir = Path("runs/<run_id>")
report = (run_dir / "final_report.md").read_text(encoding="utf-8")
evidence_id = "EV-" + report.split("[EV-", 1)[1].split("]", 1)[0]
rows = [
    json.loads(line)
    for line in (run_dir / "evidence.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]
match = next(item for item in rows if item["evidence_id"] == evidence_id)
print(evidence_id)
print(match["source"]["title"])
print(match["source"]["url"])
print(match["status"])
PY
```

Trace inspection:

```bash
head -10 "$RUN_DIR/trace.jsonl"
rg "fixture.search|exa.search|web_search|provider_" "$RUN_DIR/trace.jsonl"
```

## Limitations

- No Web UI.
- LLM-backed Writer and Verifier are opt-in; Planner and Researcher remain deterministic.
- No PDF or HTML export.
- No large benchmark or live web CI gate.
- Fixture eval remains the deterministic quality signal.
- Live web results can vary by provider availability, quota, network, ranking, and source freshness.
- The current Live web provider is a demo-ready Exa integration, not a complete provider marketplace.

## Interview Demo Path

1. Show the architecture flow and roles in this README.
2. Run `python3 -m pytest` to show the regression gate.
3. Run the Fixture demo with `--source-provider fixture`.
4. Open `final_report.md`, `evidence.jsonl`, and `trace.jsonl`.
5. Run fixture eval with `traceresearch eval --cases-dir eval/cases --source-provider fixture --results-dir eval/results`.
6. If an Exa key is configured, run the Live web demo with `--source-provider web`.
7. If no key is configured, run the unconfigured failure demo and show `provider_not_configured`.
8. If a DeepSeek API key is configured, run `--writer-mode llm` and compare the report quality.
9. Run `traceresearch llm-smoke` to verify LLM smoke eval infrastructure.
