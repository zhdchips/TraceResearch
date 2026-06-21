# Data Model: Research Subagents

**Created**: 2026-06-21
**Feature**: 004-research-subagents

## New Entities

### SubagentExecutor

Bounded concurrency runtime wrapping `ThreadPoolExecutor`.

```yaml
fields:
  max_workers: int               # default 3, from env var TRACERESEARCH_MAX_CONCURRENT_RESEARCH_TASKS
  task_timeout: float | None     # seconds, None = no timeout (default)
methods:
  execute(tasks, agent_factory) -> list[CandidateEvidenceBatch]
```

### CandidateEvidenceBatch

Subagent 返回的结果容器（未 dedup，未分配正式 evidence ID）。

```yaml
fields:
  task_id: str                   # ResearchTask.research_task_id
  subagent_id: str               # format: SA-{run_id}-{seq:03d}
  status: SubagentStatus         # success | partial | failed | timed_out
  candidates: list[Evidence]     # evidence_id 为临时占位符
  error: ErrorInfo | None        # error details if status=failed
```

### SubagentStatus (enum)

```yaml
values:
  success: "all sources fetched successfully"
  partial: "some sources failed to fetch"
  failed: "all sources failed or provider error"
  timed_out: "subagent exceeded task_timeout"
```

### CompressedResearchContext

传递给 subagent 的轻量上下文。

```yaml
fields:
  run_id: str
  brief_summary: str             # compressed objective summary from ResearchBrief
  task: ResearchTask             # the specific task to execute
  provider_name: str             # "fixture" | "web"
  created_at: datetime
```

### ResearchTaskAgent

单个 subagent 的执行单元。Callable with signature:

```python
(context: CompressedResearchContext, provider: SourceDiscoveryProvider) -> CandidateEvidenceBatch
```

内部逻辑：调用 `provider.search(task, limit)` → `provider.fetch(source_ref)` → 构造 `Evidence` 对象 → 返回 batch。

### LeadResearchAgent

Research phase 的总协调者。

```yaml
fields:
  executor: SubagentExecutor
  trace_writer: TraceWriter | None    # for recording lifecycle events
methods:
  conduct_research(brief, provider, run_id, run_dir) -> list[Evidence]
```

## Modified Entities

### AgentRole (enum extension)

```yaml
new_values:
  RESEARCH_LEAD: "ResearchLead"       # Lead Agent orchestration events
  RESEARCH_SUBAGENT: "ResearchSubagent"  # Per-task subagent events
```

### TraceEvent (model extension)

```yaml
new_optional_fields:
  subagent_id: str | None    # default None — populated for RESEARCH_SUBAGENT events
```

### CritiqueResult (model extension)

```yaml
new_optional_fields:
  failed_task_ids: list[str]  # research_task_ids that failed during research phase
```

## Unchanged Entities

以下实体在本 feature 中**不变**：

- `ResearchBrief`, `ResearchTask`, `Evidence`, `Claim`, `VerificationResult`, `DraftReport`, `FinalReport` — 结构完全不变
- `SourceResult`, `SourceDocument`, `SourceRef` — provider 接口不变
- `EvalCase`, `EvalResult` — eval 模型不变
- `ResearchRun`, `ResearchRunStatus`, `RunResult` — run 生命周期不变

## State Transitions

### ResearchTaskAgent Lifecycle

```
PENDING (task in brief.research_tasks)
  → RUNNING (SubagentExecutor dispatches to thread)
    → SUCCESS (all sources fetched, Evidence objects created)
    → PARTIAL (some sources fetched, some failed with non-fatal errors)
    → FAILED (provider error or all sources failed)
    → TIMED_OUT (exceeded task_timeout)
```

### Research Phase (Lead Agent perspective)

```
ResearchLead START
  → dispatch all tasks to executor
  → collect all CandidateEvidenceBatch results
  → dedup across batches
  → assign evidence IDs (task definition order)
  → write to EvidenceStore
  → record trace events
  → ResearchLead FINISH (returns list[Evidence])
```
