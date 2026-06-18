# Quickstart: Deep Research Multi-Agent MVP

This quickstart defines the expected validation path after implementation. It does not require business code to exist during planning.

## 1. Install Project

Expected command:

```bash
python3 -m pip install -e ".[dev]"
```

## 2. Run One Fixture Research Case

Expected command:

```bash
traceresearch run \
  --query "Compare LangGraph, AutoGen, and CrewAI for building research agents" \
  --source-provider fixture \
  --case-id 001-framework-comparison
```

Expected result:

- A new `runs/<run_id>/` directory exists.
- `research_brief.json`, `evidence.jsonl`, `trace.jsonl`, `final_report.md`, and `report.json` exist.
- `final_report.md` key claims include `[EV-...]` evidence IDs.

## 3. Run Seed Eval Suite

Expected command:

```bash
traceresearch eval \
  --cases-dir eval/cases \
  --source-provider fixture \
  --results-dir eval/results
```

Expected result:

- All 5 seed eval cases run.
- `eval/results/<eval_run_id>-summary.json` exists.
- Metrics include `planner_coverage`, `perspective_diversity`, `source_relevance`, `source_authority`, `citation_completeness`, `faithfulness`, `unsupported_claim_count`, `critical_hallucination_count`, and `case_pass_rate`.
- `critical_hallucination_count` is 0 for passing MVP.

## 4. Inspect Evidence Grounding

Checklist:

- Pick one key claim from `final_report.md`.
- Follow its `[EV-...]` ID to `evidence.jsonl`.
- Confirm source metadata, summary, supported claims, and verification notes exist.
- Confirm related Agent steps appear in `trace.jsonl`.

## 5. Run Tests

Expected command:

```bash
pytest
```

Expected coverage areas:

- Schema validation
- Evidence Store read/write
- Trace writer
- Fixture source provider
- Report claim-to-evidence validation
- Eval metrics

## 6. MVP Pass Conditions

- Completed reports have no key claims without evidence IDs.
- `critical_hallucination_count == 0`.
- At least 4/5 seed cases pass planner coverage and citation completeness checks.
- Ambiguous query tests return clarification or explicit assumptions.
