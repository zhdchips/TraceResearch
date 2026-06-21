# Feature Specification: Research Subagents

**Feature Branch**: `004-research-subagents`
**Created**: 2026-06-21
**Status**: Draft
**Input**: 将 TraceResearch 的 research phase 从串行 Researcher loop 升级为 DeerFlow-inspired "Lead Agent + Tool-based Subagents" 架构。本阶段只改 research phase，不引入 LangGraph、Web UI、sandbox、memory、MCP 或 skills marketplace。

> Language Policy: English headings, Chinese explanatory body, English AI/Agent terms, and English machine-readable keys.

## Goal

本 feature 的目标是将当前 ResearchHarness 中 Planner 生成 research tasks 后的串行 Researcher loop 替换为基于 subagent 的并行执行架构。当前实现中，`Researcher.research()` 方法对每个 `ResearchTask` 依次调用 `SourceDiscoveryProvider.search()` 和 `fetch()`，在一个主线程中串行执行 — 当 research tasks 数量增多时，端到端延迟线性增长，且单个 task 的 source provider 失败即导致整个 run 失败。

核心变化是引入三层抽象：

1. **SubagentExecutor** — 基于 `ThreadPoolExecutor` 的 bounded concurrency runtime，负责并行派发 research tasks 给 subagents、管理 timeout、隔离 failure、收集结果。
2. **ResearchTaskAgent** — 每个 subagent 实例处理单个 `ResearchTask`，只接收压缩后的 brief context（不接收完整主上下文），调用 source provider search/fetch 后返回 candidate evidence batch。
3. **LeadResearchAgent** — 替代当前 orchestrator 中内联的 researcher loop，负责从 Planner 获取 research tasks、通过 SubagentExecutor 派发、收集所有 subagent 的 candidate evidence、统一 dedupe 和分配 evidence ID、写入 Evidence Store、记录 Trace。

本 feature 遵循 001-003 已确立的契约：CLI contract 不变（`traceresearch run` / `traceresearch eval` 仍可工作）、artifact contract 不变（所有文件路径和格式不变）、harness orchestration 的 Planner -> Research -> Writer -> Verifier -> Critic -> Writer 主流程不变、fixture eval 必须保持 deterministic。

本 feature 不实现：LLM-backed Researcher、LangGraph integration、sandbox、memory persistence、MCP tools、skills marketplace、Web UI。

## User Scenarios & Testing

### User Story 1 - Parallel research task execution reduces end-to-end latency (Priority: P1)

开发者运行 `traceresearch run` 时，系统使用 SubagentExecutor 并行执行多个 research tasks（默认最多 3 个并发）。当 Planner 生成 5 个 research tasks 且每个 task 需要 ~2 秒 source discovery 时，总 research phase 时间从 ~10 秒减少到 ~4 秒（在 3-way concurrency 下）。

**Why this priority**: 这是 feature 的核心价值 — 通过并行化减少 research phase 延迟，让用户更快看到 final report。

**Independent Test**: 使用 fixture provider 运行包含 3+ research tasks 的 eval case，测量 research phase 的 wall-clock 时间，验证并发执行比串行执行更快。

**Acceptance Scenarios**:

1. **Given** Planner 生成了 4 个 research tasks, **When** SubagentExecutor 以 `max_concurrent=3` 执行, **Then** 所有 4 个 tasks 都被执行（其中 3 个并发、1 个排队），每个 task 产生 evidence 记录。
2. **Given** 某个 subagent 因 provider error 失败, **When** 其他 subagents 正常完成, **Then** 成功的 subagent 的 evidence 被保留，失败的 task 被标记为 failed，run 不 crash。
3. **Given** `max_concurrent_research_tasks=1`, **When** 执行 research phase, **Then** tasks 串行执行，行为与当前实现等效。

---

### User Story 2 - Lead Agent deduplicates and writes evidence centrally (Priority: P1)

LeadResearchAgent 收集所有 subagent 返回的 candidate evidence batches 后，统一执行 dedup（基于 URL、title/publisher/date 等 key），分配稳定且唯一的 evidence ID，然后写入 Evidence Store。Subagent 不直接接触 Evidence Store 或 artifacts。

**Why this priority**: Evidence dedup 和 ID 稳定性是 artifact contract 和 eval determinism 的基础。集中化写入确保数据一致性。

**Independent Test**: 两个 subagent 返回了引用相同 source URL 的 candidate evidence，检查 Lead Agent 是否只写入一条 evidence 记录。

**Acceptance Scenarios**:

1. **Given** 两个 subagents 返回了指向同一 URL 的 candidate evidence, **When** Lead Agent 执行 dedup, **Then** Evidence Store 中只包含一条 evidence 记录，且其 evidence ID 稳定可预测。
2. **Given** subagents 返回了 5 条 candidate evidence, **When** Lead Agent 分配 evidence ID, **Then** ID 格式与当前 `EVD-{run_id}-{seq:03d}` 一致。
3. **Given** subagent 返回空的 candidate evidence batch, **When** Lead Agent 处理, **Then** 不写入空的 evidence 行，对应的 research task 在 trace 中标记为 no-results。

---

### User Story 3 - Trace records subagent lifecycle and provider tool results (Priority: P1)

Trace 必须完整记录 research phase 的 subagent 执行细节：Lead Agent 派发 task、每个 subagent 的 start/finish、subagent 内 source provider 的 tool_call/tool_result、subagent 的 error/timeout 事件。所有 Trace 事件必须可回放、可审计。

**Why this priority**: Traceability 是 TraceResearch 的核心架构原则。subagent 架构引入了并行和多层调用，Trace 必须能反映这些细节才能做 bad-case replay。

**Independent Test**: 运行 fixture eval 后检查 trace.jsonl，验证包含 Lead Agent、subagent lifecycle、provider tool result 事件。

**Acceptance Scenarios**:

1. **Given** research phase 启动, **When** Lead Agent 派发 tasks, **Then** Trace 包含 RESEARCH_LEAD START 事件，记录 task 数量和并发配置。
2. **Given** subagent 开始执行, **When** 调用 source provider search/fetch, **Then** Trace 包含 RESEARCH_SUBAGENT START、TOOL_CALL、TOOL_RESULT 和 FINISH 事件，每条事件包含 task_id 和 subagent_id。
3. **Given** subagent 执行超时或出错, **When** error 发生, **Then** Trace 包含 RESEARCH_SUBAGENT ERROR 事件，记录 error type、message、task_id 和 subagent_id。

---

### User Story 4 - Partial failure policy preserves good evidence (Priority: P2)

当部分 subagents 失败（provider timeout、provider error、无结果）时，Lead Agent 保留成功完成的 subagent 的 evidence，并将失败信息传递给 Critic。Critic 在 review 阶段标注 missing perspective 或 failed task 信息，Writer 在 final report 中如实反映数据收集的限制。

**Why this priority**: 相比当前"一个 task 失败即整个 run 失败"的行为，partial failure 允许用户从部分成功的 research 中获得价值。

**Independent Test**: 使用 fixture provider 并 inject 一个对特定 task 返回 error 的 provider（通过 mock），验证其他 tasks 的 evidence 正常写入且 run 状态为 partial。

**Acceptance Scenarios**:

1. **Given** 3 个 research tasks 中 1 个产生 provider error, **When** Lead Agent 完成 evidence 收集, **Then** 2 个成功的 task 的 evidence 被写入 Evidence Store，失败的 task 在 Critic 的 missing_perspectives 中被标注。
2. **Given** 所有 research tasks 都失败, **When** 没有 evidence 被收集, **Then** run 状态为 FAILED，Trace 记录所有 error 事件。
3. **Given** subagent 超时, **When** timeout 触发, **Then** subagent 被标记为 timed_out，超时前的部分结果（如有）被保留。

---

### User Story 5 - Fixture eval and deterministic behavior preserved (Priority: P1)

无论 SubagentExecutor 使用什么并发度，fixture eval 的 5 个 seed cases 必须保持 5/5 pass。evidence ID 必须稳定，evidence 内容必须与当前实现一致，Output Determinism 必须保持满分。`python3 -m pytest` 必须 100% pass。

**Why this priority**: 这是用户最核心的约束。subagent 架构引入的并发不能破坏现有 deterministic baseline。

**Independent Test**: 运行 fixture eval 和 `python3 -m pytest`，验证结果与 003 基线一致。

**Acceptance Scenarios**:

1. **Given** subagent 架构已部署, **When** 运行 `traceresearch eval --source-provider fixture`, **Then** 5 个 seed cases 5/5 pass, Output Determinism=1.0。
2. **Given** subagent 架构已部署, **When** 运行 `python3 -m pytest`, **Then** 所有 test 100% pass（排除 llm_smoke marker）。
3. **Given** fixture provider 在 subagent 内被调用, **When** 运行 eval, **Then** evidence 内容与 003 基线完全一致。

---

### Edge Cases

- **Subagent 超时与 hung task**: subagent 在 `SubagentExecutor` 中应支持可配置的 `task_timeout`。超时后 executor 必须标记该 subagent 为 timed_out，不阻塞其他 subagent。
- **空 research tasks 列表**: Planner 返回 0 个 research tasks 时，Lead Agent 必须 handle gracefully，返回空 evidence list，不报错。
- **Subagent 返回重复 evidence**: 两个不同 subagent 可能搜索不同 perspective 但返回相同 source。Lead Agent 的 dedup logic 必须基于 `_dedupe_key()` 处理。
- **Concurrency=1 的行为等价性**: 当 `max_concurrent_research_tasks=1` 时，SubagentExecutor 必须产生与当前串行 Researcher loop 等效的结果（包括 evidence 顺序和 ID）。
- **大量 research tasks**: 当 Planner 生成 20+ research tasks 时，SubagentExecutor 以 `max_concurrent=3` 分批执行，不创建超过并发限制的线程。
- **Source provider 线程安全性**: FixtureSourceProvider 和 ExaSearchProvider 在并发调用时必须是线程安全的。
- **Context isolation**: subagent 不得接收完整的 harness 上下文（如 Evidence Store 引用、Writer、Verifier 实例）。只接收压缩的 brief context、当前 task 和 source provider。
- **Trace sequence ordering**: 并发执行时，Trace 事件按完成时间写入，不保证 task_id 顺序。每个事件包含足够的标识信息用于 retroactive 排序。

## Requirements

### Functional Requirements

- **FR-001**: 系统 MUST 提供 `SubagentExecutor` 类，支持通过 `ThreadPoolExecutor` 实现 bounded concurrency，默认 `max_concurrent_research_tasks=3`，每个 task 有可配置的 timeout。
- **FR-002**: `SubagentExecutor` MUST 支持 failure isolation：单个 subagent 的异常不得影响其他 subagent 的执行，executor 收集所有 subagent 的返回结果和 failure 信息。
- **FR-003**: 系统 MUST 提供 `ResearchTaskAgent` 类（或 callable），每个实例负责处理单个 `ResearchTask`：接收压缩后的 brief context + task + source provider + run metadata，调用 `provider.search()` 和 `provider.fetch()`，返回 `CandidateEvidenceBatch`（不做 dedup，不写 Evidence Store）。
- **FR-004**: 系统 MUST 提供 `LeadResearchAgent` 类，替代当前 orchestrator 中内联的 researcher loop，负责：(a) 从 Planner 获取 research tasks，(b) 通过 SubagentExecutor 派发 tasks，(c) 收集 candidate evidence、(d) 统一 dedup 和分配 evidence ID、(e) 写入 Evidence Store、(f) 记录 Trace。
- **FR-005**: `LeadResearchAgent` MUST 实现 `conduct_research()` 方法作为 task-tool-like flow 入口。第一版为 Python callable，不需要 LangChain tool schema。
- **FR-006**: 每个 subagent 的上下文 MUST 被压缩：只包含 brief objective、当前 task 的 perspective/question、source provider reference、run metadata（run_id、created_at）。不得传入完整 harness 实例、Evidence Store、Writer 或 Verifier 引用。
- **FR-007**: Subagent 返回的 evidence candidate MUST 使用与现有 `Evidence` 模型兼容的结构。Lead Agent 分配最终的 `evidence_id`（格式 `EVD-{run_id}-{seq:03d}`）和 `retrieval_date`。
- **FR-008**: Lead Agent 的 dedup MUST 复用 `EvidenceStore._dedupe_key()` 逻辑或等效算法，基于 URL（web）或 title/publisher/retrieval_date（fixture）去重。
- **FR-009**: 系统 MUST 保持 partial failure policy：部分 subagents 失败时保留成功 subagent 的 evidence，将失败 task 信息传递给 Critic 和 Trace。
- **FR-010**: Trace MUST 记录以下新事件：`RESEARCH_LEAD` 事件（开始/结束，含 task 数量和并发配置）、`RESEARCH_SUBAGENT` 事件（开始/结束，含 task_id、subagent_id、status、latency）、tool_call/tool_result 事件（在 subagent 上下文中记录 source provider 调用）。
- **FR-011**: Trace 的旧字段（agent_role、event_type、tool_name 等）MUST 保持向后兼容。新增字段（如 subagent_id）为 optional 且不破坏现有 Trace reader。
- **FR-012**: 系统 MUST 在 `max_concurrent_research_tasks=1` 时产生与当前串行 Researcher loop 等效的行为，包括 evidence 顺序和内容。
- **FR-013**: CLI contract MUST 不变：`traceresearch run` 和 `traceresearch eval` 的参数和输出格式不变。
- **FR-014**: Artifact contract MUST 不变：所有文件路径（`research_brief.json`、`research_tasks.json`、`evidence.jsonl`、`trace.jsonl`、`final_report.md`、`report.json` 等）和格式不变。
- **FR-015**: FixtureSourceProvider MUST 在并发调用时保持线程安全且 deterministic。
- **FR-016**: 系统 MUST 不引入新重型依赖（如 LangGraph、LangChain、Celery、Redis）。并发实现 MUST 仅使用 stdlib `concurrent.futures.ThreadPoolExecutor`。
- **FR-017**: SubagentExecutor 的 `max_concurrent_research_tasks` MUST 可配置（通过构造函数参数或 env var `TRACERESEARCH_MAX_CONCURRENT_RESEARCH_TASKS`），默认值为 3。
- **FR-018**: 每个新增组件（SubagentExecutor、ResearchTaskAgent、LeadResearchAgent）MUST 有对应的 unit test 覆盖。

### Key Entities

- **SubagentExecutor**: Bounded concurrency runtime。管理 `ThreadPoolExecutor`，接收 `list[ResearchTask]` 和 `subagent_factory` callable，并行执行 tasks，收集结果。支持 `max_workers`、`task_timeout` 配置。
- **CandidateEvidenceBatch**: Subagent 返回的未 dedup、未分配正式 ID 的 evidence 候选集合。包含 `candidates: list[Evidence]`（evidence_id 为临时占位符）、`task_id`、`subagent_id`、`status`（success/partial/failed/timed_out）。
- **ResearchTaskAgent**: 单个 subagent 的 callable。输入为 `CompressedResearchContext`（包含 brief summary、task、provider reference、run_id），输出为 `CandidateEvidenceBatch`。
- **LeadResearchAgent**: 替代当前 orchestrator 中 researcher loop 的 agent。持有 `SubagentExecutor` 引用、`EvidenceStore` 引用、`TraceWriter` 引用。提供 `conduct_research(brief, provider, run_id, run_dir) -> list[Evidence]` 方法。
- **CompressedResearchContext**: 传递给 subagent 的压缩上下文。包含 `brief_summary`（来自 ResearchBrief.objective 的摘要）、`task`（完整 ResearchTask）、`provider_name`（字符串）、`run_id`、`created_at`。不包含 Evidence Store、Writer、Verifier 或其他 harness 组件。
- **SubagentStatus**: 枚举值：`success`、`partial`（部分 source 获取失败）、`failed`（全部失败）、`timed_out`。

### Deep Research / Agent Requirements

- **Research Contract**: `conduct_research()` 方法接收 research brief 和 source provider，返回 `list[Evidence]`。这是 research phase 的唯一对外接口。内部 subagent 执行细节对外不可见。
- **Agent Boundaries**: `LeadResearchAgent` 负责 orchestration、dedup、evidence ID 分配、Evidence Store 写入和 Trace 记录。`ResearchTaskAgent` 只负责执行单个 task 的 source discovery，不接触 Evidence Store 或 artifacts。`SubagentExecutor` 只负责并发调度，不关心 research domain logic。
- **Evidence Grounding**: research 后 evidence 的 grounding 逻辑不变：Writer 从 Evidence Store 读取 evidence，Verifier 基于 evidence 验证 claims。subagent 架构不改变 evidence 的质量或内容。
- **Traceability**: subagent lifecycle 必须在 Trace 中完整记录。每个 subagent 的 start/finish 事件包含 subagent_id（`SA-{run_id}-{seq:03d}`）、task_id、status、latency。Subagent 内 source provider 的 tool_call/tool_result 事件包含 task_id 和 subagent_id 作为上下文。
- **Context Engineering**: subagent 只接收压缩上下文 — brief objective summary + 当前 task + provider name + run metadata。这确保 subagent 不会依赖或意外修改主 harness 状态，也为未来 LLM-backed subagent 做上下文预算准备。
- **Eval Harness**: fixture eval 必须继续 5/5 pass。eval metrics 不变。LLM smoke eval（如果运行）的 faithfulness 和 citation completeness 检查仍适用。

## Non-Goals

- **NG-001**: 本 feature 不引入 LangGraph、LangChain 或任何 workflow orchestration framework。
- **NG-002**: 本 feature 不实现 LLM-backed Researcher — Researcher / subagent 仍然是 deterministic source discovery。
- **NG-003**: 本 feature 不提供 Web UI、sandbox、memory persistence、MCP tools 或 skills marketplace。
- **NG-004**: 本 feature 不改变 Writer、Verifier、Critic、Planner 的实现或接口。
- **NG-005**: 本 feature 不修改 CLI contract（`traceresearch run` / `traceresearch eval` 参数不变）。
- **NG-006**: 本 feature 不修改 artifact contract（文件路径、格式、内容 schema 不变）。
- **NG-007**: 本 feature 不引入异步 I/O（asyncio）— 并发基于 `ThreadPoolExecutor`。
- **NG-008**: 本 feature 不做 inter-run subagent caching 或持久化。

## Success Criteria

- **SC-001**: 使用 fixture provider 运行包含 3+ research tasks 的 eval case 时，research phase wall-clock 时间不超过串行执行的 70%（在 `max_concurrent=3` 下）。
- **SC-002**: fixture eval 的 5 个 seed cases 保持 5/5 pass，Output Determinism=1.0，所有 9 个 metrics 正常。
- **SC-003**: `python3 -m pytest` pass rate 保持 100%（排除 `llm_smoke` marker）。
- **SC-004**: 每个 subagent 执行包含 ResearchTask 的 start/finish 被记录到 Trace，包含 subagent_id、task_id、status、latency。
- **SC-005**: 当 1 个 subagent 失败、其他成功时，成功的 evidence 被写入 Evidence Store，失败信息在 Trace 中可追溯。
- **SC-006**: `max_concurrent_research_tasks=1` 时，evidence 输出与当前串行 Researcher loop 完全一致。
- **SC-007**: Evidence Store 中的 evidence ID 格式保持 `EVD-{run_id}-{seq:03d}`，ID 分配稳定可预测。
- **SC-008**: 不引入新的外部 Python 依赖（stdlib only 用于并发）。

## Assumptions

- **A-001**: `SourceDiscoveryProvider` 的 `search()` 和 `fetch()` 方法在并发调用时是线程安全的。FixtureSourceProvider 已验证线程安全（无共享可变状态），ExaSearchProvider 的 HTTP 调用天然线程安全。
- **A-002**: `ThreadPoolExecutor` 足以满足当前 research 阶段的并发需求。大多数 research tasks 的 latency 来自 I/O（网络请求或文件读取），线程模型适合 I/O-bound 并发。
- **A-003**: 现有 fixture eval 的 5 个 seed cases 足以验证 subagent 架构的 regression 稳定性。
- **A-004**: Current Harness 的 `_TraceRecorder` 内部类可以在 TraceWriter API 层面被复用，LeadResearchAgent 会新增自己的 Trace 事件记录逻辑。
- **A-005**: `EvidenceStore._dedupe_key()` 的逻辑对并发写入是安全的（Lead Agent 在所有 subagent 完成后统一写入，不存在并发写冲突）。
- **A-006**: CompressedResearchContext 的内容设计是基于当前 ResearchTask 模型的字段子集，足够 subagent 完成 source discovery 任务。
- **A-007**: 用户接受 subagent 架构引入的 Trace 事件增加（每个 task 至少有 START + FINISH + TOOL_CALL + TOOL_RESULT 4 条事件），Trace 文件大小会相应增长。

## Risks and Open Questions

- **Risk-001**: 并发引入的 Trace 事件乱序可能使 Trace 阅读和回放复杂化。Mitigation：每个事件包含足够的时间戳和上下文标识（task_id、subagent_id）用于排序和过滤。
- **Risk-002**: ThreadPoolExecutor 的线程创建开销在大量 short tasks 时可能抵消并发收益。Mitigation：当前 research tasks 数量通常 ≤10，且 task 的 I/O latency 远大于线程开销。
- **Risk-003**: Evidence ID 分配顺序可能因并发完成时间不同而变化，影响稳定性和测试断言。Mitigation：Lead Agent 按 task 定义顺序（而非完成顺序）分配 evidence ID。
- **Risk-004**: 如果 orchestrator 中 researcher loop 的代码逻辑与 subagent 代码路径出现 divergence，可能导致 fixture eval 失败。Mitigation：在 `max_concurrent=1` 时验证 subagent 行为与串行等价。
- **Open Question-001**: 是否需要在 `traceresearch run` CLI 中新增 `--max-concurrent-research-tasks` flag？当前留给 plan 阶段决策；如果没有强烈需求，先用 env var `TRACERESEARCH_MAX_CONCURRENT_RESEARCH_TASKS` 覆盖默认值。

## Quality Gates

- **QG-001**: Implement 后必须运行 `python3 -m pytest`，确认 100% pass（排除 `llm_smoke` marker）。
- **QG-002**: Implement 后必须运行 fixture eval，确认 5 seed cases 5/5 pass，Output Determinism=1.0。
- **QG-003**: Research tasks 通过 SubagentExecutor 执行（而非 direct serial loop）。
- **QG-004**: Evidence Store 包含有效 evidence 行，evidence ID 格式与现有一致。
- **QG-005**: Trace 包含 subagent lifecycle 事件和 provider tool result 事件。
- **QG-006**: Partial failure 时，成功 evidence 保留，Trace 记录失败信息。
- **QG-007**: `max_concurrent_research_tasks=1` 时，结果与当前串行实现一致。
- **QG-008**: 不引入新外部 Python 依赖。
