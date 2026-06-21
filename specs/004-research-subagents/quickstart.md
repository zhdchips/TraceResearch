# Quickstart: Research Subagents

## What Changed

Research phase 从串行 `Researcher.research()` loop 升级为基于 `SubagentExecutor` 的并行 subagent 架构。

**User-facing behavior unchanged** — CLI commands, artifact paths, evidence format 全部保持不变。

## How to Use

### Default (parallel, max 3 concurrent)

```bash
traceresearch run --query "What is the memory overhead of RAG vs long-context models?" \
  --source-provider fixture
```

### Serial execution (equivalent to old behavior)

```bash
TRACERESEARCH_MAX_CONCURRENT_RESEARCH_TASKS=1 \
  traceresearch run --query "..." --source-provider fixture
```

### Custom concurrency

```bash
TRACERESEARCH_MAX_CONCURRENT_RESEARCH_TASKS=5 \
  traceresearch run --query "..." --source-provider fixture
```

### Eval (unchanged)

```bash
traceresearch eval --cases-dir eval/cases --source-provider fixture --results-dir eval/results
```

## What to Expect

### Trace Events (new)

`trace.jsonl` 中新增两种 agent role：

- `ResearchLead` — Lead Agent 的 orchestration 事件（START, TOOL_CALL, TOOL_RESULT, FINISH）
- `ResearchSubagent` — 每个 research task 的 subagent 生命周期事件（START, TOOL_CALL, TOOL_RESULT, FINISH, ERROR）

### Partial Failure

如果部分 research tasks 失败，run 仍会完成。Critic 会在 `missing_perspectives` 中标注失败的 task。Final report 会反映数据收集的限制。

## Test Commands

```bash
# Unit + integration tests (excludes LLM smoke)
python3 -m pytest -m "not llm_smoke"

# Fixture eval regression
traceresearch eval --cases-dir eval/cases --source-provider fixture --results-dir eval/results

# Subagent-specific tests
python3 -m pytest tests/unit/test_subagent_executor.py tests/unit/test_research_task_agent.py tests/unit/test_lead_research_agent.py -v
```
