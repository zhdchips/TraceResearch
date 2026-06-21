# Tasks: Research Subagents

> Language Policy: English headings, Chinese task descriptions, English task IDs / file paths / commands / AI-Agent terms.

**Feature**: 004-research-subagents
**Created**: 2026-06-21
**Plan**: [plan.md](./plan.md)
**Spec**: [spec.md](./spec.md)

## Task Format

Every task uses this format:

```md
- [ ] TNNN [Priority] [Story?] 中文任务描述，关键术语保留英文
  - DoD: 可验证的完成标准
  - Tests: 测试命令和覆盖描述
  - Related files: 涉及的文件路径
```

**Priority**: P0 = 阻塞性 / gates / regression | P1 = 核心功能 | P2 = 文档 / polish

---

## Phase 1: Foundation — Models & Data Layer (Foundational)

> 本阶段定义新 data model、扩展 AgentRole、提取 dedup key。完成后可独立验证：所有新 model 可 import、`AgentRole` 包含新值、所有现有 tests 仍然 pass。阻塞所有后续 Phase。

- [ ] T001 [P0] 在 `traceresearch/trace/models.py` 中新增 `AgentRole.RESEARCH_LEAD` 和 `AgentRole.RESEARCH_SUBAGENT` enum 值
  - DoD: `AgentRole.RESEARCH_LEAD == "ResearchLead"`, `AgentRole.RESEARCH_SUBAGENT == "ResearchSubagent"`
  - Tests: 现有 trace model tests 继续 pass；`python3 -m pytest tests/unit/test_trace_models.py -v`
  - Related files: `traceresearch/trace/models.py`

- [ ] T002 [P0] 在 `traceresearch/trace/models.py` 的 `TraceEvent` 中新增可选字段 `subagent_id: str | None = None`
  - DoD: `TraceEvent(..., subagent_id="SA-run-001")` 可成功构造；不传 subagent_id 时默认为 None，不破坏现有 TraceEvent
  - Tests: `python3 -m pytest tests/unit/test_trace_models.py tests/unit/test_trace_writer.py -v`
  - Related files: `traceresearch/trace/models.py`

- [ ] T003 [P0] 创建 `traceresearch/agents/subagent_models.py` — 定义 `SubagentStatus` enum、`CandidateEvidenceBatch` dataclass、`CompressedResearchContext` dataclass
  - DoD: `SubagentStatus` 含 `success`/`partial`/`failed`/`timed_out` 枚举值；`CandidateEvidenceBatch` 含 `task_id`、`subagent_id`、`status`、`candidates`、`error` 字段；`CompressedResearchContext` 含 `run_id`、`brief_summary`、`task`、`provider_name`、`created_at` 字段
  - Tests: `python3 -m pytest tests/unit/test_subagent_models.py -v` (需创建)
  - Related files: `traceresearch/agents/subagent_models.py`, `tests/unit/test_subagent_models.py`

- [ ] T004 [P0] 提取 `EvidenceStore._dedupe_key()` 为 module-level 函数 `traceresearch/evidence/store.py` 中的 `dedupe_key(evidence) -> tuple[str, str]`，原 `_dedupe_key` 调用新函数
  - DoD: `dedupe_key()` 可被 LeadResearchAgent 直接 import；`EvidenceStore` 内部调用同名函数
  - Tests: `python3 -m pytest tests/unit/test_evidence_store.py -v` — 所有现有 tests pass
  - Related files: `traceresearch/evidence/store.py`, `tests/unit/test_evidence_store.py`

---

## Phase 2: Core Subagent Infrastructure (US1 — Parallel Research Execution)

> 实现 SubagentExecutor 和 ResearchTaskAgent，使 research tasks 可并行执行。完成后可独立验证：用 mock provider 并行执行 3 个 tasks，验证 concurrent execution 和 failure isolation。

- [ ] T005 [P1] [US1] 先写 test: `tests/unit/test_subagent_executor.py` — 覆盖：3 tasks concurrency=2, 1 fail 2 succeed, concurrency=1 serial order, timeout behavior, empty task list, all tasks fail
  - DoD: test 文件包含 6+ 个 scenario，使用 mock agent_factory
  - Tests: `python3 -m pytest tests/unit/test_subagent_executor.py -v`
  - Related files: `tests/unit/test_subagent_executor.py`

- [ ] T006 [P1] [US1] 实现 `traceresearch/agents/subagent_executor.py` — `SubagentExecutor` 类，使用 `ThreadPoolExecutor`，支持 `max_workers`（默认 3）、`task_timeout`（默认 None），`execute(tasks, agent_factory) -> list[CandidateEvidenceBatch]`
  - DoD: T005 全部 tests pass；failure isolation 工作正常；`Future.result(timeout)` pattern 正确
  - Tests: `python3 -m pytest tests/unit/test_subagent_executor.py -v`
  - Related files: `traceresearch/agents/subagent_executor.py`

- [ ] T007 [P1] [US1] 先写 test: `tests/unit/test_research_task_agent.py` — 覆盖：fixture provider 正常执行、返回有效 CandidateEvidenceBatch、空搜索结果、provider error 时返回 failed batch、CompressedResearchContext 不泄露 harness 引用
  - DoD: test 文件包含 4+ 个 scenario
  - Tests: `python3 -m pytest tests/unit/test_research_task_agent.py -v`
  - Related files: `tests/unit/test_research_task_agent.py`

- [ ] T008 [P1] [US1] 实现 `traceresearch/agents/research_task_agent.py` — `ResearchTaskAgent` callable class，接收 `CompressedResearchContext` + `SourceDiscoveryProvider`，调用 `provider.search()` + `provider.fetch()`，复用 `Researcher._to_evidence()` 构造 Evidence，返回 `CandidateEvidenceBatch`
  - DoD: T007 全部 tests pass；subagent 不访问 EvidenceStore、不调用 TraceWriter
  - Tests: `python3 -m pytest tests/unit/test_research_task_agent.py -v`
  - Related files: `traceresearch/agents/research_task_agent.py`

---

## Phase 3: Lead Research Agent (US2 — Evidence Dedup & Central Writing)

> 实现 LeadResearchAgent.conduct_research()，完成 task 派发、dedup、evidence ID 分配、Evidence Store 写入。完成后可独立验证：用 fixture provider 运行 research，验证 evidence 正确写入。

- [ ] T009 [P1] [US2] 先写 test: `tests/unit/test_lead_research_agent.py` — 覆盖：fixture provider 正常执行返回 evidence list、evidence ID 按 task 定义顺序分配、两个 task 返回重复 URL-based source 时 dedup 生效、2 succeed + 1 fail 时返回 2 个 task 的 evidence、全部 fail 时返回空 list、Trace 事件记录正确
  - DoD: test 文件包含 6+ 个 scenario
  - Tests: `python3 -m pytest tests/unit/test_lead_research_agent.py -v`
  - Related files: `tests/unit/test_lead_research_agent.py`

- [ ] T010 [P1] [US2] 实现 `traceresearch/agents/lead_researcher.py` — `LeadResearchAgent` 类，`conduct_research(brief, provider, run_id, run_dir, trace_writer=None) -> list[Evidence]`，内部使用 `SubagentExecutor` 派发 tasks，收集 batches 后按 task 定义顺序分配 evidence ID（格式 `EVD-{run_id}-{seq:03d}`），dedup（调用 `dedupe_key()`），写入 `EvidenceStore`，记录 Trace（如 trace_writer 提供）
  - DoD: T009 全部 tests pass；evidence 与当前 `Researcher.research()` 输出内容等效
  - Tests: `python3 -m pytest tests/unit/test_lead_research_agent.py -v`
  - Related files: `traceresearch/agents/lead_researcher.py`

- [ ] T011 [P2] [US2] 验证 FixtureSourceProvider 线程安全性 — 在 `tests/unit/test_fixture_provider.py` 中新增并发调用 test：3 threads 同时调用 `search()` + `fetch()`
  - DoD: test 验证 fixture provider 在并发调用下不 crash、返回结果正确
  - Tests: `python3 -m pytest tests/unit/test_fixture_provider.py -v`
  - Related files: `tests/unit/test_fixture_provider.py`

---

## Phase 4: Trace Integration (US3 — Subagent Lifecycle Tracing)

> 实现 RESEARCH_LEAD 和 RESEARCH_SUBAGENT trace 事件。完成后可独立验证：运行一次 research 后检查 trace.jsonl 包含所有新事件。

- [ ] T012 [P1] [US3] 先写 test: `tests/unit/test_subagent_trace.py` — 验证 LeadResearchAgent 产生 RESEARCH_LEAD START/FINISH 事件、每个 subagent 产生 RESEARCH_SUBAGENT START/FINISH 事件、subagent error 产生 ERROR 事件、tool_call/tool_result 包含 task_id 和 subagent_id
  - DoD: test 文件包含 5+ 个 scenario，使用 TraceWriter(TemporaryDirectory) 检查 trace.jsonl 内容
  - Tests: `python3 -m pytest tests/unit/test_subagent_trace.py -v`
  - Related files: `tests/unit/test_subagent_trace.py`

- [ ] T013 [P1] [US3] 在 `LeadResearchAgent.conduct_research()` 中添加 Trace 记录逻辑 — RESEARCH_LEAD START（task_count, max_concurrent）、每个 subagent 的 RESEARCH_SUBAGENT START/FINISH、subagent error 时 RESEARCH_SUBAGENT ERROR、RESEARCH_LEAD TOOL_RESULT（total_evidence, failed_tasks）、RESEARCH_LEAD FINISH
  - DoD: T012 全部 tests pass；trace.jsonl 可被 `TraceWriter.read_all()` 正常解析
  - Tests: `python3 -m pytest tests/unit/test_subagent_trace.py -v`
  - Related files: `traceresearch/agents/lead_researcher.py`

---

## Phase 5: Partial Failure & Error Handling (US4)

> 实现 partial failure policy，将失败 task 信息传递给 Critic。完成后可独立验证：mock 一个 subagent 失败，验证成功 evidence 保留且 Critic 感知 failure。

- [ ] T014 [P2] [US4] 在 `CritiqueResult` 中新增可选字段 `failed_task_ids: list[str]` （默认空 list，向后兼容）
  - DoD: `CritiqueResult(... failed_task_ids=["T-some"])` 可构造，不传时默认为 `[]`；现有 tests 继续 pass
  - Tests: `python3 -m pytest tests/unit/ -k "critic" -v`
  - Related files: `traceresearch/evidence/models.py`

- [ ] T015 [P2] [US4] 先写 integration test: `tests/integration/test_subagent_partial_failure.py` — 使用 mock provider 让 1 个 task 抛 `SourceDiscoveryError`，验证其他 2 个 tasks 的 evidence 正常写入、run status 为 COMPLETED、Critic.missing_perspectives 包含失败 task 的 perspective、Trace 记录 error 事件
  - DoD: test 覆盖 partial failure 的完整 flow
  - Tests: `python3 -m pytest tests/integration/test_subagent_partial_failure.py -v`
  - Related files: `tests/integration/test_subagent_partial_failure.py`

- [ ] T016 [P2] [US4] 在 `SubagentExecutor.execute()` 中实现 `task_timeout` 逻辑 — 使用 `Future.result(timeout)`，超时时标记 `SubagentStatus.TIMED_OUT`，保留已有的 partial results
  - DoD: T005 中 timeout test case pass
  - Tests: `python3 -m pytest tests/unit/test_subagent_executor.py -v`
  - Related files: `traceresearch/agents/subagent_executor.py`

---

## Phase 6: Harness Integration & Regression (US5)

> 将 LeadResearchAgent 集成到 ResearchHarness，替换内联 research loop。完成后可独立验证：fixture eval 5/5 pass，`python3 -m pytest` 100% pass。

- [ ] T017 [P0] 先写 integration test: `tests/integration/test_subagent_research_integration.py` — 覆盖：全 harness run (fixture provider) 产生有效 evidence、concurrency=1 时 evidence 与 003 baseline 一致、concurrency=3 时 evidence 内容一致（ID 可能不同）、trace.jsonl 包含 RESEARCH_LEAD 和 RESEARCH_SUBAGENT 事件
  - DoD: test 文件包含 4+ 个 scenario，使用 `ResearchHarness.run_fixture()`
  - Tests: `python3 -m pytest tests/integration/test_subagent_research_integration.py -v`
  - Related files: `tests/integration/test_subagent_research_integration.py`

- [ ] T018 [P0] 修改 `traceresearch/harness/orchestrator.py` — 将 research loop（lines 166-228）替换为 `LeadResearchAgent.conduct_research()` 调用：构造 `LeadResearchAgent`（如未注入），传入 `SubagentExecutor`（默认 max_workers 从 env var `TRACERESEARCH_MAX_CONCURRENT_RESEARCH_TASKS` 读取，默认 3），调用 `conduct_research()` 获取 `stored_evidence`
  - DoD: T017 所有 integration tests pass；orchestrator 对 ResearchHarness 的 Planner/Writer/Verifier/Critic 逻辑 zero 改动
  - Tests: `python3 -m pytest tests/integration/test_subagent_research_integration.py -v`
  - Related files: `traceresearch/harness/orchestrator.py`

- [ ] T019 [P0] 实现 `TRACERESEARCH_MAX_CONCURRENT_RESEARCH_TASKS` env var 读取 — 在 orchestrator 或 config 中读取，默认 3；用于 SubagentExecutor max_workers
  - DoD: env var 未设置时 max_workers=3；`TRACERESEARCH_MAX_CONCURRENT_RESEARCH_TASKS=1` 时 max_workers=1；非法值 fallback 到 3
  - Tests: 在 integration test 中覆盖 env var parsing
  - Related files: `traceresearch/harness/orchestrator.py`

- [ ] T020 [P0] 回归验证：运行 `python3 -m pytest -m "not llm_smoke"` 确认 100% pass
  - DoD: 所有 existing 和 new tests 无 failure、无 error
  - Tests: `python3 -m pytest -m "not llm_smoke" -v`
  - Related files: All

- [ ] T021 [P0] 回归验证：运行 fixture eval `traceresearch eval --cases-dir eval/cases --source-provider fixture --results-dir eval/results` 确认 5/5 pass
  - DoD: `case_pass_rate=1.0`, Output Determinism=1.0
  - Tests: `traceresearch eval --cases-dir eval/cases --source-provider fixture --results-dir eval/results`
  - Related files: `eval/cases/`, `traceresearch/eval/runner.py`

---

## Phase 7: Polish & Cross-Cutting

> 文档、代码清理、最终检查。

- [ ] T022 [P2] 更新 `traceresearch/agents/__init__.py` 导出 `LeadResearchAgent`、`ResearchTaskAgent`、`SubagentExecutor`、`subagent_models` 的公开符号
  - DoD: `from traceresearch.agents import LeadResearchAgent` 可直接 import
  - Tests: `python3 -c "from traceresearch.agents import LeadResearchAgent, ResearchTaskAgent, SubagentExecutor"`
  - Related files: `traceresearch/agents/__init__.py`

- [ ] T023 [P2] 验证 `max_concurrent_research_tasks=1` 时证据输出与当前 serial loop 完全一致 — 在 integration test 中做逐字段比较
  - DoD: concurrency=1 时 evidence 内容、顺序、ID 与旧 `Researcher` 输出完全相同
  - Tests: `python3 -m pytest tests/integration/test_subagent_research_integration.py -v -k "concurrent_1"`
  - Related files: `tests/integration/test_subagent_research_integration.py`

- [ ] T024 [P2] 代码清理：删除 orchestrator 中旧的 unused import（如果 `Researcher` class 不再被 orchestrator 使用），确保无 dead code
  - DoD: orchestrator.py 中无 unused `Researcher` import；保持向后兼容（`Researcher` class 保留在 codebase 中供 reference）
  - Tests: `python3 -m pytest -m "not llm_smoke" -v`
  - Related files: `traceresearch/harness/orchestrator.py`

---

## Dependency Graph

```
Phase 1 (Foundation)
  └─> Phase 2 (Core Subagent Infrastructure)
      └─> Phase 3 (Lead Research Agent)
          ├─> Phase 4 (Trace Integration)
          │   └─> Phase 6 (Harness Integration)
          ├─> Phase 5 (Partial Failure)
          │   └─> Phase 6 (Harness Integration)
          └─> Phase 6 (Harness Integration & Regression)
              └─> Phase 7 (Polish)
```

**Story dependencies**: US2→US1, US3→US2, US4→US2, US5→US2, US5→US3, US5→US4

## Parallel Opportunities

- Phase 2 内: T005 + T007 可并行（不同测试文件，mock 对象独立）
- Phase 3 内: T009 独立于 T011
- Phase 4 + Phase 5: 可部分并行（US3 trace 和 US4 failure 逻辑正交）
- Within each phase: tests（odd-numbered）和 implementation（even-numbered）需按顺序（TDD）

## Implementation Strategy

### MVP Scope (最小可交付)

- Phase 1 + Phase 2 + Phase 3 + Phase 6 = 核心 subagent 架构
- 可验证：fixture eval 5/5 pass, `python3 -m pytest` pass
- 建议先跑 MVP，再添加 Phase 4 (trace) 和 Phase 5 (partial failure)

### 推荐执行顺序

1. T001-T004 (Foundation) — 并行 T003
2. T005-T008 (US1) — T005 + T007 可并行
3. T009-T011 (US2) — T011 可独立
4. T012-T013 (US3)
5. T014-T016 (US4)
6. T017-T021 (US5 — harness integration + regression)
7. T022-T024 (Polish)
