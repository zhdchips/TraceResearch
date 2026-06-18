# CLI Contract: Deep Research Multi-Agent MVP

## Command: `traceresearch run`

Purpose: 对单个 research question 执行一次 Deep Research run，并写入 `runs/<run_id>/` artifacts。

Inputs:

```text
traceresearch run \
  --query "<research question>" \
  --source-provider fixture \
  --case-id 001-framework-comparison \
  --output-dir runs
```

Required options:

- `--query`: user research question
- `--source-provider`: `fixture` for MVP; `web` may return not-configured

Optional options:

- `--case-id`: bind run to an eval fixture case
- `--output-dir`: parent artifact directory, default `runs`

Outputs:

- Prints `run_id`, `status`, and artifact directory.
- Writes `research_brief.json`, `research_tasks.json`, `evidence.jsonl`, `verification.json`, `critique.json`, `outline.md`, `draft_report.md`, `final_report.md`, `report.json`, and `trace.jsonl`.

Failure behavior:

- Ambiguous query returns `needs_clarification` and writes Trace.
- Source provider not configured returns failed status with error summary.
- Unsupported final claims block completion.

## Command: `traceresearch eval`

Purpose: 运行 5 个 seed eval cases，并输出 metrics summary。

Inputs:

```text
traceresearch eval \
  --cases-dir eval/cases \
  --source-provider fixture \
  --results-dir eval/results
```

Outputs:

- Writes one result summary JSON under `eval/results/`.
- Writes per-case run artifacts under `runs/<run_id>/`.
- Prints `case_pass_rate`, failed case IDs, and suggested next phase.

Required metrics:

- `planner_coverage`
- `perspective_diversity`
- `source_relevance`
- `source_authority`
- `citation_completeness`
- `faithfulness`
- `unsupported_claim_count`
- `critical_hallucination_count`
- `case_pass_rate`
