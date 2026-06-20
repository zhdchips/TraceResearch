# Quickstart: Deep Research Multi-Agent MVP

This quickstart defines the current validation path for the CLI-first MVP.

## 1. Install Project

Run from the repository root:

```bash
python3 -m pip install -e ".[dev]"
```

If the local Python environment cannot install the console script because build tooling is unavailable, run CLI commands from the checkout with:

```bash
traceresearch() { PYTHONPATH=. python3 -c 'from traceresearch.cli import app; app()' "$@"; }
```

## 2. Run One Fixture Research Case

Command:

```bash
traceresearch run \
  --query "Compare LangGraph, AutoGen, and CrewAI for building evidence-grounded deep research agents." \
  --source-provider fixture \
  --case-id 001-framework-comparison \
  --output-dir runs
```

Expected result:

- CLI prints `run_id`, `status`, and `artifact_dir`.
- A new `runs/<run_id>/` directory exists, for example `runs/001-framework-comparison-<suffix>/`.
- `runs/<run_id>/research_brief.json`, `runs/<run_id>/research_tasks.json`, `runs/<run_id>/evidence.jsonl`, `runs/<run_id>/verification.json`, `runs/<run_id>/critique.json`, `runs/<run_id>/outline.md`, `runs/<run_id>/draft_report.md`, `runs/<run_id>/final_report.md`, `runs/<run_id>/report.json`, and `runs/<run_id>/trace.jsonl` exist.
- `final_report.md` key claims include `[EV-...]` evidence IDs.

## 3. Run Seed Eval Suite

Command:

```bash
traceresearch eval \
  --cases-dir eval/cases \
  --source-provider fixture \
  --results-dir eval/results \
  --runs-dir runs
```

Expected result:

- All 5 seed eval cases run.
- `eval/results/<eval_run_id>-summary.json` exists.
- CLI prints `eval_run_id`, `case_pass_rate`, `failed_case_ids`, `suggested_next_phase`, and `result_file`.
- The summary JSON contains `case_results`, `metrics_summary`, `case_pass_rate`, `bad_case_notes`, `suggested_next_phase`, and `failed_case_ids`.
- Each case result includes `planner_coverage`, `perspective_diversity`, `source_relevance`, `source_authority`, `citation_completeness`, `faithfulness`, `unsupported_claim_count`, `critical_hallucination_count`, and `case_pass_rate`.
- `critical_hallucination_count` is 0 for passing MVP.

## 4. Inspect Evidence Grounding

Use the `artifact_dir` from the run command:

```bash
RUN_DIR="runs/<run_id>"
rg -o "\\[EV-[^]]+\\]" "$RUN_DIR/final_report.md" | head -1
python3 - <<'PY'
import json
from pathlib import Path

run_dir = Path("runs/<run_id>")
report = (run_dir / "final_report.md").read_text(encoding="utf-8")
evidence_id = report.split("[EV-", 1)[1].split("]", 1)[0]
evidence_id = "EV-" + evidence_id
evidence = [
    json.loads(line)
    for line in (run_dir / "evidence.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]
match = next(item for item in evidence if item["evidence_id"] == evidence_id)
print(evidence_id)
print(match["source"]["title"])
print(match["source"]["source_type"])
print(match["status"])
PY
```

Manual checklist:

- Pick one key claim from `final_report.md`.
- Follow its `[EV-...]` ID to `evidence.jsonl`.
- Confirm source metadata, summary, supported claims, and verification notes exist.
- Confirm related Agent steps appear in `trace.jsonl`.

## 5. Run Tests

Command:

```bash
python3 -m pytest
```

Expected coverage areas:

- Schema validation
- Evidence Store read/write
- Trace writer
- Fixture source provider
- Report claim-to-evidence validation
- Eval metrics

## 6. Manual Acceptance Commands

After the seed eval suite finishes, validate the latest summary file:

```bash
python3 - <<'PY'
import json
from pathlib import Path

required_metrics = {
    "planner_coverage",
    "perspective_diversity",
    "source_relevance",
    "source_authority",
    "citation_completeness",
    "faithfulness",
    "unsupported_claim_count",
    "critical_hallucination_count",
    "case_pass_rate",
}
result_path = sorted(Path("eval/results").glob("*-summary.json"))[-1]
payload = json.loads(result_path.read_text(encoding="utf-8"))
assert len(payload["case_results"]) == 5
for case_result in payload["case_results"]:
    assert required_metrics <= set(case_result["metrics"])
    assert required_metrics <= set(case_result["pass_fail"])
assert required_metrics <= set(payload["metrics_summary"]["metric_averages"])
assert "bad_case_notes" in payload
print(result_path)
print(payload["case_pass_rate"])
PY
```

## 7. MVP Pass Conditions

- Completed reports have no key claims without evidence IDs.
- `critical_hallucination_count == 0`.
- At least 4/5 seed cases pass planner coverage and citation completeness checks.
- Ambiguous query tests return clarification or explicit assumptions.
