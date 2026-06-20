# Quickstart: Live Provider Demo Readiness

This quickstart defines the expected validation path for feature `002-live-provider-demo-readiness`.

## 1. Install / Local CLI

Preferred:

```bash
python3 -m pip install -e ".[dev]"
```

Fallback from checkout:

```bash
traceresearch() { PYTHONPATH=. python3 -c 'from traceresearch.cli import app; app()' "$@"; }
```

## 2. Fixture Regression

Run tests:

```bash
python3 -m pytest
```

Run fixture eval:

```bash
traceresearch eval \
  --cases-dir eval/cases \
  --source-provider fixture \
  --results-dir eval/results
```

Expected:

- Tests pass.
- Fixture eval runs 5 seed cases.
- `case_pass_rate=1.0`.
- 9 required metrics are present.

## 3. Unconfigured Web Provider Check

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
- no fixture fallback
- Trace or CLI error is safe and does not include secrets

## 4. Configured Live Smoke

Manual only; not a default CI gate.

```bash
export TRACERESEARCH_WEB_PROVIDER=exa
export EXA_API_KEY="<your-local-key>"
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
- `evidence.jsonl` contains live source title, URL/source reference, retrieved_at, summary, supported claims.
- `trace.jsonl` contains `exa.search` or clear provider failure event.

## 5. Inspect Evidence Grounding

```bash
RUN_DIR="runs/<run_id>"
rg -o "\\[EV-[^]]+\\]" "$RUN_DIR/final_report.md" | head -1
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

## 6. README Demo Readiness

Before review, confirm root `README.md` includes:

- project positioning
- architecture
- fixture demo
- live web demo
- secret handling
- eval/review workflow
- limitations
- interview screen-share path
