# Eval Plan: Research Subagents

> Language Policy: English headings, Chinese explanatory body, English AI/Agent terms and machine-readable keys.

**Feature**: 004-research-subagents
**Created**: 2026-06-21

## Scope

验证 research phase 从串行 Researcher loop 升级为 LeadResearchAgent + SubagentExecutor 架构后：
1. Fixture eval 5/5 pass，metrics 不低于 003 baseline
2. Trace 包含新 RESEARCH_LEAD 和 RESEARCH_SUBAGENT 事件
3. Evidence Store 包含有效 evidence 行，evidence ID 格式正确
4. 并行执行不引入 regression

## Metrics

| Metric | 003 Baseline | 004 Target |
|--------|------------|-----------|
| case_pass_rate | 1.0 | 1.0 |
| planner_coverage | 1.0 | 1.0 |
| perspective_diversity | 1.0 | 1.0 |
| source_relevance | 0.912 | ≥ 0.912 |
| source_authority | 0.848 | ≥ 0.848 |
| citation_completeness | 1.0 | 1.0 |
| faithfulness | 1.0 | 1.0 |
| unsupported_claim_count | 0 | 0 |
| critical_hallucination_count | 0 | 0 |

## Cases

5 seed eval cases (001-005)，全部使用 fixture provider：
- 001-framework-comparison
- 002-financial-grounding
- 003-ai-coding-agent-trends
- 004-openhands-runtime
- 005-rag-2026

## Commands

```bash
# Unit + integration tests (excluding LLM smoke)
python3 -m pytest -m "not llm_smoke"

# Fixture eval (via test runner)
python3 -m pytest tests/eval/test_eval_runner.py -v

# CLI eval (requires installed package)
traceresearch eval --cases-dir eval/cases --source-provider fixture --results-dir eval/results

# Trace validation
python3 -c "
import json
from pathlib import Path
runs = Path('runs')
for run_dir in runs.iterdir():
    trace = run_dir / 'trace.jsonl'
    if trace.exists():
        events = [json.loads(l) for l in trace.read_text().splitlines() if l.strip()]
        roles = {e['agent_role'] for e in events}
        if 'ResearchLead' in roles or 'ResearchSubagent' in roles:
            print(f'{run_dir.name}: subagent trace present')
"
```

## Latest Result

**Date**: 2026-06-21
**Test Suite**: 283 passed, 5 deselected (llm_smoke), 0 failed
**Eval Tests**: 4/4 passed — fixture eval runner executes all 5 seed cases successfully
**Integration Tests**: 37/37 passed — including subagent-specific integration tests

### Fixture Eval Results

5/5 seed cases pass through the subagent architecture with identical metrics to the 003 baseline.

### Trace Validation

Integration tests confirm:
- `trace.jsonl` contains RESEARCH_LEAD events (START, TOOL_RESULT, FINISH)
- `trace.jsonl` contains RESEARCH_SUBAGENT events (START, TOOL_CALL, TOOL_RESULT, FINISH) with task_id, subagent_id
- Provider tool calls/results tracked with proper tool_name ("fixture.search")
- Provider failures recorded as RESEARCH_SUBAGENT FINISH status=FAILED + TOOL_RESULT error with provider error codes
- Trace IDs are unique under concurrent execution (50-thread stress test)

### Evidence Store Validation

- Evidence IDs follow format `EV-{run_id}-{seq:03d}`
- Dedup works correctly (same URL → single Evidence row)
- Evidence content identical to 003 baseline when concurrency=1

### Parallel Execution Validation

- SubagentExecutor correctly executes tasks with bounded concurrency (default 3)
- Failure isolation: single failing task doesn't block successful tasks
- Timeout mechanism returns promptly for hung tasks (elapsed time <2s for 5s sleep with 0.1s timeout; batch-level timeout, not per-task wall-clock)
- All-failure detection returns FAILED run status

## Bad Cases

No bad cases identified in this evaluation. The subagent architecture preserves all existing behavior while adding parallel execution capability.

## Next Review Focus

- Review review.md for overall feature completeness assessment
- Verify that all functional requirements (FR-001 through FR-018) are met
- Check that all non-goals (NG-001 through NG-008) are respected
- Confirm no new external dependencies were introduced
