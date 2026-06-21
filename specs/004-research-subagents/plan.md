# Implementation Plan: Research Subagents

> Language Policy: English headings, Chinese explanatory body, English AI/Agent terms, and English machine-readable keys.

## Architecture

### System Overview

当前 `ResearchHarness._run_with_provider()` 中 research phase 是内联的串行 loop（lines 174-228），每个 `ResearchTask` 依次通过 `Researcher.research()` 调用 source provider。本 plan 将该 loop 替换为三层 subagent 架构：

```
                    ┌─────────────────────────┐
                    │   ResearchHarness        │
                    │   _run_with_provider()   │
                    └───────────┬─────────────┘
                                │ brief + provider
                                ▼
                    ┌─────────────────────────┐
                    │   LeadResearchAgent      │
                    │   conduct_research()     │
                    │                          │
                    │  - Gets research_tasks   │
                    │  - Dispatches to executor│
                    │  - Dedups results        │
                    │  - Assigns evidence IDs  │
                    │  - Writes EvidenceStore  │
                    │  - Records Trace         │
                    └───────────┬─────────────┘
                                │ list[ResearchTask]
                                ▼
                    ┌─────────────────────────┐
                    │   SubagentExecutor       │
                    │   (ThreadPoolExecutor)   │
                    │                          │
                    │  - max_workers=3         │
                    │  - task_timeout          │
                    │  - failure isolation      │
                    └───────┬───────┬─────────┘
                            │       │
                    ┌───────┘       └───────┐
                    ▼                       ▼
            ┌──────────────┐       ┌──────────────┐
            │ResearchTaskAgent│     │ResearchTaskAgent│ ...
            │  subagent_id   │       │  subagent_id   │
            │                │       │                │
            │ search + fetch │       │ search + fetch │
            └───────┬────────┘       └───────┬────────┘
                    │                        │
                    ▼                        ▼
            CandidateEvidenceBatch   CandidateEvidenceBatch
```

### Module Layout

新增文件：
- `traceresearch/agents/lead_researcher.py` — `LeadResearchAgent` 类 + `LeadResearchResult` dataclass
- `traceresearch/agents/subagent_executor.py` — `SubagentExecutor` 类
- `traceresearch/agents/research_task_agent.py` — `ResearchTaskAgent` 类
- `traceresearch/agents/subagent_models.py` — `SubagentStatus`, `CompressedResearchContext`, `CandidateEvidenceBatch`, `ToolEvent`

修改文件：
- `traceresearch/harness/orchestrator.py` — research loop 替换为 `LeadResearchAgent.conduct_research()`
- `traceresearch/trace/models.py` — 新增 `AgentRole.RESEARCH_LEAD` 和 `AgentRole.RESEARCH_SUBAGENT`

### 模块边界

| Module | Reads | Writes | Shared State |
|--------|-------|--------|-------------|
| LeadResearchAgent | ResearchBrief, SourceDiscoveryProvider | EvidenceStore (via add), TraceWriter, returns LeadResearchResult | Provider instance (shared across subagents via closure) |
| SubagentExecutor | list[ResearchTask], agent_factory | list[CandidateEvidenceBatch] | ThreadPoolExecutor (internal) |
| ResearchTaskAgent | CompressedResearchContext, SourceDiscoveryProvider | CandidateEvidenceBatch | Accesses shared provider instance (search/fetch calls) |
| Orchestrator | LeadResearchAgent result | artifacts, subsequent phases | None |

## Agent Roles

| Role | Responsibility | Inputs | Outputs | Tools |
| --- | --- | --- | --- | --- |
| Planner | 任务拆解与研究维度规划 | user query | research brief | none |
| LeadResearchAgent | research task 派发、结果合并、dedup、Evidence Store 写入、Trace | research brief, source provider | LeadResearchResult (evidence + failed_task_ids), Trace events | SubagentExecutor |
| ResearchTaskAgent (subagent) | 单 task source discovery | compressed context, source provider | candidate evidence batch | provider.search / provider.fetch |
| SubagentExecutor | bounded concurrency 调度 | list[ResearchTask], agent factory | list[CandidateEvidenceBatch] | ThreadPoolExecutor |
| Verifier | 证据质量和 claim 支撑检查 | evidence / draft claims | verification result | evaluator |
| Critic | 缺失视角、风险、反例检查 | draft report, failed task info | critique | model |
| Writer | 基于 evidence 生成报告 | verified evidence | final report | none |

## Data Flow

1. User query → Planner → ResearchBrief (不变)
2. ResearchBrief → **LeadResearchAgent.conduct_research()** （替代原串行 loop）
3. LeadResearchAgent → SubagentExecutor → N × ResearchTaskAgent (concurrent)
4. Each ResearchTaskAgent → provider.search() + provider.fetch() → CandidateEvidenceBatch
5. SubagentExecutor → LeadResearchAgent: 收集所有 batch
6. LeadResearchAgent → dedup → assign evidence IDs → EvidenceStore.add()
7. LeadResearchAgent → TraceWriter: 记录 lifecycle 和 tool result
8. Evidence Store → Verifier / Critic / Writer (不变)

**关键变化：步骤 2-7 替代原 orchestrator lines 174-228。其余 unchanged。**

## Evidence Store Design

Evidence Store schema 不变。变化点在于写入路径：

- **Before**: Researcher 写入 EvidenceStore（每个 task 后立即写入）
- **After**: LeadResearchAgent 在所有 subagents 完成后统一写入

Evidence ID 分配策略：
- 格式：`EV-{run_id}-{seq:03d}`（与 Researcher._to_evidence 一致，由 LeadResearchAgent 统一分配）
- 分配顺序：按 task 定义顺序（`brief.research_tasks` index 顺序），而非 completion 顺序
- 跨 task 的 source items 按 task 内 source 顺序连续编号
- Dedup：如果两个 subagent 返回了 dupe source (same URL or same fixture key)，只保留第一次出现的（按 task 定义顺序），跳过 duplicate

### CandidateEvidenceBatch

```python
@dataclass
class CandidateEvidenceBatch:
    task_id: str
    subagent_id: str
    status: SubagentStatus  # success, partial, failed, timed_out
    candidates: list[Evidence]  # evidence_id 为临时占位符
    error: ErrorInfo | None = None
    tool_events: list[ToolEvent] = field(default_factory=list)
```

## Trace Design

### New AgentRole entries

```python
class AgentRole(StrEnum):
    # ... existing ...
    RESEARCH_LEAD = "ResearchLead"       # 新增：Lead Agent orchestration
    RESEARCH_SUBAGENT = "ResearchSubagent"  # 新增：per-task subagent
```

### New Trace Events

```
Research Phase (Lead Agent perspective):
  RESEARCH_LEAD START    — task_count, max_concurrent
  RESEARCH_LEAD TOOL_CALL — dispatching tasks to executor
  RESEARCH_LEAD TOOL_RESULT — executor results summary
  RESEARCH_LEAD FINISH   — total_evidence, failed_tasks, dedup_skipped

Subagent Lifecycle (per task):
  RESEARCH_SUBAGENT START    — task_id, subagent_id, perspective
  RESEARCH_SUBAGENT TOOL_CALL — task_id, subagent_id, tool_name="fixture.search"|"exa.search"
  RESEARCH_SUBAGENT TOOL_RESULT — task_id, subagent_id, result_count, source_ids
  RESEARCH_SUBAGENT FINISH   — task_id, subagent_id, status, latency_ms
  RESEARCH_SUBAGENT ERROR    — task_id, subagent_id, error type/message (on failure)
```

### Trace Field Compatibility

`TraceEvent` 模型新增 optional fields（不破坏旧 trace reader）：
- `subagent_id: str | None = None`

### 并发 Trace 顺序

并发 subagents 的 Trace 事件按**完成时间**写入，不保证 task_id 顺序。每个事件包含 `task_id`、`subagent_id`、`created_at` 以供后续排序。

## Eval Harness Design

### 变更点

- EvalRunner 通过 `Harness.run_fixture()` 运行，internal research phase 变为 subagent-based
- `SubagentExecutor` 在 fixture eval 中对 FixtureSourceProvider 做并发调用
- `LeadResearchAgent` 将同一个 provider 实例共享给所有 subagent。`FixtureSourceProvider` 内部缓存 loaded YAML 和 parsed `EvalCase`；`ExaSearchProvider` 内部有 document cache。两者在并发调用时存在共享 mutable 状态，但由于 provider 的 search/fetch 结果在单次 run 内是幂等的，且 Python GIL 保护了单个 dict 操作的原子性，当前未观察到 data corruption。
- Evidence 输出必须与 003 基线一致（在 `max_concurrent=1` 时 100% 等价；在 `max_concurrent=3` 时 evidence ID 可能因 timing 不同而变化，但应设法保序）

### Evidence ID 稳定性策略

由于 fixture eval 使用 FixtureSourceProvider（deterministic），并发执行时 subagent 完成顺序不影响结果 — `search()` 返回的 results 是确定性的。Lead Agent 在收集所有 batches 后，按 `brief.research_tasks` 的**定义顺序**（而非 completion 顺序）分配 evidence ID，保证 ID 稳定性。

### Metrics 不变

所有 9 个 metrics 保持：`planner_coverage`, `perspective_diversity`, `source_relevance`, `source_authority`, `citation_completeness`, `faithfulness`, `unsupported_claim_count`, `critical_hallucination_count`, `case_pass_rate`。

## Technical Decisions

- **TD-001**: 使用 `ThreadPoolExecutor` 而非 `asyncio` — Reason: SourceDiscoveryProvider 是同步接口，现有代码全为同步。ThreadPoolExecutor 对 I/O-bound 并发足够且无需重构整个 call chain。
- **TD-002**: Evidence ID 按 task 定义顺序分配（非 completion 顺序）— Reason: 稳定性优先。Fixture eval 要求 evidence ID 跨 run 一致。
- **TD-003**: Subagent 通过 `agent_factory` callable 创建（而非直接实例化）— Reason: SubagentExecutor 不需要知道 ResearchTaskAgent 的构造方式，便于测试和 mock。
- **TD-004**: Trace subagent 事件使用独立的 `AgentRole.RESEARCH_SUBAGENT`（而非复用 `RESEARCHER`）— Reason: 清晰区分 Lead Agent orchestration 和 per-task execution。
- **TD-005**: `max_concurrent_research_tasks` 默认值 3，可通过 env var `TRACERESEARCH_MAX_CONCURRENT_RESEARCH_TASKS` 覆盖 — Reason: 遵循 003 的 env var 模式，不强制 CLI flag。
- **TD-006**: `EvidenceStore._dedupe_key()` 提取为 module-level function 供 LeadResearchAgent 复用 — Reason: 避免代码重复，保持 dedup 逻辑一致性。
- **TD-007**: `ResearchTaskAgent` 复用现有 `Researcher._to_evidence()` 方法 — Reason: 避免重复实现 evidence 构造逻辑，保证 evidence 内容一致性。
- **TD-008**: `SubagentExecutor` 使用 `concurrent.futures.as_completed()` 收集结果 — Reason: 先完成的 subagent 先被收集，但最终排序由 Lead Agent 按 task 定义顺序重新排列。

## Failure Handling

### Partial Failure Policy

| Scenario | Behavior |
|----------|----------|
| 1+ subagents fail, others succeed | Lead Agent 保留 successful evidence，记录 failed task IDs。Harness 不 crash。Critic 在 `missing_perspectives` 中标注 failed tasks。Run status = COMPLETED (partial)。 |
| All subagents fail | No evidence stored。Harness 返回 FAILED。Trace 记录所有 error 事件。 |
| Subagent timeout | Subagent 标记为 timed_out。超时任务不返回部分结果（返回空 `CandidateEvidenceBatch`，status=TIMED_OUT）。 |
| Provider error within subagent | Exception caught by ResearchTaskAgent。Error 记录在 `CandidateEvidenceBatch.error`，由 Lead 写入 Trace 为 RESEARCH_SUBAGENT FINISH status=FAILED 和 TOOL_RESULT error。Other subagents unaffected。 |
| Empty research tasks | Lead Agent 返回空 list，不报错。 |

### 与当前行为的对比

- **Before**: 第一个 task 的 `SourceDiscoveryError` → orchestrator 直接 catch → run 立即 FAIL → return
- **After**: 第一个 task 的 error → ResearchTaskAgent 捕获并包装为 `CandidateEvidenceBatch` (status=FAILED, error via to_trace_error()) → SubagentExecutor 收集 → LeadResearchAgent 记录为 RESEARCH_SUBAGENT FINISH status=FAILED + TOOL_RESULT error → 其他 tasks 继续 → 最终根据是否有任何 evidence 决定 run status

## Test Strategy

### Unit Tests (新增文件)

1. **`tests/unit/test_subagent_executor.py`**
   - 3 个 tasks with mock factory，concurrency=2 → all 3 complete
   - 1 个 task fails，2 succeed → failure isolation works
   - max_concurrent=1 → serial execution order matches task order
   - Timeout behavior → task marked timed_out
   - Empty task list → returns empty
   - All tasks fail → returns all with failed status

2. **`tests/unit/test_research_task_agent.py`**
   - With FixtureSourceProvider → returns valid CandidateEvidenceBatch
   - CompressedResearchContext doesn't leak harness state
   - Empty search results → batch with status=partial, reason
   - Provider error → batch with status=failed, error info

3. **`tests/unit/test_lead_research_agent.py`**
   - conduct_research with fixture provider → returns LeadResearchResult (evidence + failed_task_ids)
   - Evidence ID ordering matches task definition order
   - Dedup: two tasks return same URL-based source → one evidence
   - Partial failure: 1 succeed, 1 fail → evidence for 1, failed_task_ids populated
   - All fail → returns empty evidence with failed_task_ids
   - Trace events recorded correctly (RESEARCH_LEAD + RESEARCH_SUBAGENT + TOOL_CALL/TOOL_RESULT)
   - Trace IDs are unique under concurrent execution

4. **`tests/unit/test_subagent_models.py`**
   - Model validation for SubagentStatus, CompressedResearchContext, CandidateEvidenceBatch
   - ToolEvent dataclass fields

### Integration Tests (新增/修改)

5. **`tests/integration/test_subagent_research_integration.py`**
   - Full harness run with fixture provider → produces valid evidence
   - Evidence content matches 003 baseline (concurrency=1)
   - Evidence content matches 003 baseline (concurrency=3)
   - Trace.jsonl contains RESEARCH_LEAD and RESEARCH_SUBAGENT events
   - Partial failure with mocked provider → run completes, evidence partial

### Regression Tests (existing, must pass)

6. All existing tests in `tests/unit/`, `tests/integration/`, `tests/eval/` — 100% pass
7. `traceresearch eval --cases-dir eval/cases --source-provider fixture --results-dir eval/results` — 5/5 pass

## Risks

- **Risk-001**: `LeadResearchAgent` 将同一个 provider 实例共享给所有 subagent 线程。`FixtureSourceProvider` 有内部 YAML/EvalCase cache，`ExaSearchProvider` 有 document cache — 两者在并发调用时存在共享 mutable 状态。Mitigation：provider 的 search/fetch 结果在单次 run 内幂等，Python GIL 保护单 dict 操作原子性。当前未观察到 data corruption，但 risk 未被完全消除。已通过并发测试验证。
- **Risk-002**: Evidence ID 稳定性。并发执行时 evidence 的生成顺序可能与串行不同，导致 ID 变化。Mitigation：Lead Agent 按 task 定义顺序（非 completion 顺序）分配 ID。
- **Risk-003**: Trace 事件乱序使回放复杂。Mitigation：每个事件包含 `created_at`、`task_id`、`subagent_id`。
- **Risk-004**: orchestrator 与 LeadResearchAgent 的重叠责任可能引入 coordinator 逻辑不一致。Mitigation：LeadResearchAgent 封装所有 research phase 逻辑，orchestrator 只调用 `conduct_research()` 获取结果。
- **Risk-005**: `SubagentExecutor` 可能因为 `ThreadPoolExecutor` 的 daemon thread 在 pytest 结束时被强制关闭而丢失 Trace 事件。Mitigation：所有 Trace 写入通过 TraceWriter（同步 JSONL append），在 subagent 完成时立即记录。

## Constitution Check

| Principle | Compliance | Notes |
|-----------|-----------|-------|
| I. Research Contract First | ✅ | `conduct_research()` receives brief (ResearchBrief), tasks already planned |
| II. Evidence-Grounded Output | ✅ | Lead Agent writes to Evidence Store; Writer/Verifier unchanged |
| III. Traceable Agent Execution | ✅ | New RESEARCH_LEAD + RESEARCH_SUBAGENT trace events with full lifecycle |
| IV. Context Isolation and Compression | ✅ | ResearchTaskAgent receives CompressedResearchContext, not full harness |
| V. Eval-Gated Iteration | ✅ | Unit + integration tests planned; fixture eval regression required |

No constitution violations. All principles either maintained or strengthened (Context Isolation improved via CompressedResearchContext).

## Complexity Tracking

No new external dependencies. All concurrency via stdlib `concurrent.futures`. No LangGraph, LangChain, or other orchestration framework.

Single justified complexity: `SubagentExecutor` class (~80 lines) is the only new abstraction beyond simple delegation. It's justified by the need for bounded concurrency, timeout, and failure isolation — functions that can't be done with a simple `for` loop.

## Design Caveats & Known Limitations

以下 caveats 是本 feature 中已知的设计取舍，在 plan 阶段已识别并被显式接受。它们不是 bug，也不阻塞 release（全量测试已通过），但指出了当前实现的边界。

### Caveat 1: Timeout is batch-level, not per-task wall-clock timeout

`SubagentExecutor` 使用 `concurrent.futures.as_completed(timeout=task_timeout)` 控制等待窗口。此 timeout 是从 `execute()` 调用开始到 `as_completed` 循环结束的总时长。它不是每个 task 从提交到线程开始运行起计算的独立 wall-clock timeout。

**影响**：当 `max_workers < task_count` 时，队列中尚未开始执行的 task 可能与已超时的运行中 task 一起被标记为 `TIMED_OUT`。

**接受原因**：目标是防止 caller 被慢 task 无限阻塞（已达成），不是实现精确 per-task scheduler。Fixture eval 路径不受影响（task 快速返回）。

**未来方向**：记录每个 task 的 `submit_time`，在 `as_completed` 循环中对已完成 + 超时的 future 分别处理；对超时 future 调用 `future.cancel()` 仅影响未开始的 future。

### Caveat 2: Timeout cannot forcibly terminate running provider calls

`pool.shutdown(wait=False)` 使 `execute()` 快速返回而不等待慢 task，但已运行中的 thread/provider call 继续执行到自然结束。Python thread 没有安全强杀机制。

**影响**：timeout 后后台 provider 调用可能仍在执行。由于 `LeadResearchAgent` 将同一个 provider 实例共享给所有 subagent，`FixtureSourceProvider` 的内部 YAML cache 和 `ExaSearchProvider` 的 document cache 在并发调用时是共享 mutable 状态。timeout 后若后台线程继续写入这些 cache，可能与主线程后续操作产生 late mutation 风险。当前实践中依赖 provider 操作的幂等性和 Python GIL 的 dict 操作原子性，未观察到 data corruption，但此风险未被消除。

**接受原因**：`SourceDiscoveryProvider` 是同步接口。当前超时仅用于防护 hung provider 导致 caller 永久阻塞的场景。不用于精确资源管理。

**未来方向**：provider-level HTTP timeout、async provider + `asyncio.wait_for()`、process isolation（multiprocessing）、或 sandbox/runtime-level cancellation。

### Caveat 3: Tool observability is at search level, not per-fetch

Trace 中的 `RESEARCH_SUBAGENT TOOL_CALL/TOOL_RESULT` 事件包围的是 `Researcher.research()` 的整体流程 — `provider.search()` 后接多次 `provider.fetch()`。没有为单个 `provider.fetch()` 写独立 trace event。

**影响**：无法从 trace 中区分 "search 成功但某个 fetch 失败" 和 "search 本身失败"；per-source fetch latency 不可见。

**接受原因**：search-level observability 满足当前 eval 和 review 需求。Fixture eval 的 provider 总是返回完整数据。Live provider 的 fetch 失败通过 `Evidence.limitations` 和 Trace error 间接体现。

**未来方向**：让 `ResearchTaskAgent` 或 `Researcher` 为每个 `provider.fetch()` 分别记录 tool event（如 `fixture.fetch`），或扩展 `ToolEvent` 以携带 source_id 级别的 metadata。
