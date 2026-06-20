# Tasks: Deep Research Multi-Agent MVP

> Language Policy: English headings, Chinese task descriptions, English task IDs / file paths / commands / AI-Agent terms.

**Input**: Design documents from `specs/001-deep-research-multi-agent-mvp/`  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`  
**Execution Rule**: 所有 P0/P1 任务必须完成并通过 tests/eval 后，才能运行 `$speckit-ai-eval-review-review` 判断是否 complete。

## Task Format

每个任务必须保持以下格式：

```md
TASK LINE: - [ ] T001 [P] [US1] Description with file path
  - DoD:
  - Tests:
  - Related files:
```

`[P]` 表示可并行；`[US1]` 等 story label 只用于 User Story phase。P0/P1 优先级写在任务描述中。

## Phase 1: Setup

**Purpose**: 建立 Python CLI-first 项目骨架、开发工具和目录结构。

- [X] T001 P0: 初始化 Python project metadata in `pyproject.toml`
  - DoD: 定义 project name、Python 3.11+、dependencies `pydantic`/`typer`、dev dependency `pytest`，并提供 `traceresearch` CLI entrypoint。
  - Tests: 运行 `python3 -m pip install -e ".[dev]"` 能安装 editable package。
  - Related files: `pyproject.toml`

- [X] T002 P0: 创建 package/module 目录骨架 in `traceresearch/`
  - DoD: 创建 `traceresearch/__init__.py`、`agents/`、`harness/`、`evidence/`、`source_discovery/`、`trace/`、`reports/`、`eval/`，每个 package 包含 `__init__.py`。
  - Tests: 运行 `python3 -c "import traceresearch"` 成功。
  - Related files: `traceresearch/__init__.py`, `traceresearch/agents/__init__.py`, `traceresearch/harness/__init__.py`

- [X] T003 P0: 创建 tests 目录骨架 in `tests/`
  - DoD: 创建 `tests/unit/`、`tests/integration/`、`tests/eval/`，并放置最小 smoke test。
  - Tests: 运行 `pytest` 时 smoke test pass。
  - Related files: `tests/unit/test_imports.py`, `tests/integration/`, `tests/eval/`

- [X] T004 [P] P1: 创建 artifact 目录占位和 gitkeep in `eval/results/`
  - DoD: 创建 `eval/cases/`、`eval/fixtures/sources/`、`eval/results/`、`runs/` 目录，并避免提交运行时大产物。
  - Tests: 运行 `find eval runs -maxdepth 2 -type d` 能看到计划目录。
  - Related files: `eval/cases/.gitkeep`, `eval/fixtures/sources/.gitkeep`, `eval/results/.gitkeep`, `runs/.gitkeep`

## Phase 2: Foundational

**Purpose**: 完成所有 User Story 都依赖的 schema、artifact、provider、Trace 和 seed eval 基础。

- [X] T005 P0: 实现 domain schemas in `traceresearch/evidence/models.py`
  - DoD: 定义 `ResearchRun`、`ResearchBrief`、`ResearchTask`、`SourceResult`、`SourceDocument`、`Evidence`、`Claim`、`VerificationResult`、`CritiqueResult`、`EvalCase`、`EvalResult`，字段与 `data-model.md` 对齐。
  - Tests: 新增 schema validation tests，覆盖 required fields、enum、score 范围和 unsupported claim 规则。
  - Related files: `traceresearch/evidence/models.py`, `tests/unit/test_models.py`, `specs/001-deep-research-multi-agent-mvp/data-model.md`

- [X] T006 [P] P0: 实现 Trace schema in `traceresearch/trace/models.py`
  - DoD: 定义 `TraceEvent`，包含 `trace_id`、`run_id`、`task_id`、`agent_role`、`event_type`、`tool_name`、`input_summary`、`output_summary`、`status`、`latency_ms`、`token_usage`、`error`、`created_at`。
  - Tests: 覆盖 failed event 必须有 `error.message`，每个 enum value 可序列化。
  - Related files: `traceresearch/trace/models.py`, `tests/unit/test_trace_models.py`

- [X] T007 P0: 实现 artifact path manager in `traceresearch/harness/artifacts.py`
  - DoD: 能基于 `run_id` 创建 `runs/<run_id>/`，返回所有 required artifact paths，并阻止 path traversal。
  - Tests: 覆盖 run directory creation、required filenames、重复调用幂等。
  - Related files: `traceresearch/harness/artifacts.py`, `tests/unit/test_artifacts.py`, `specs/001-deep-research-multi-agent-mvp/contracts/artifact-contract.md`

- [X] T008 P0: 实现 JSONL Trace writer in `traceresearch/trace/writer.py`
  - DoD: 支持 append `TraceEvent` 到 `trace.jsonl`，并能读回 events；失败写入必须保留 error summary。
  - Tests: 覆盖 start/finish/error 写入、JSONL 逐行可解析、事件顺序保持。
  - Related files: `traceresearch/trace/writer.py`, `tests/unit/test_trace_writer.py`

- [X] T009 P0: 实现 Evidence Store read/write/dedupe in `traceresearch/evidence/store.py`
  - DoD: 支持写入 `evidence.jsonl`、按 `evidence_id` 查找、按 source dedupe、更新 status 和 verification notes。
  - Tests: 覆盖 JSONL read/write、URL dedupe、fixture title dedupe、verified/rejected status。
  - Related files: `traceresearch/evidence/store.py`, `tests/unit/test_evidence_store.py`

- [X] T010 P0: 定义 SourceDiscoveryProvider base contract in `traceresearch/source_discovery/base.py`
  - DoD: 定义 `search(task, limit)` 和 `fetch(source_ref)` provider interface，返回 `SourceResult[]` / `SourceDocument`，错误类型包含 `provider_not_configured`。
  - Tests: Contract test 验证 fixture/web providers 必须实现 search/fetch。
  - Related files: `traceresearch/source_discovery/base.py`, `tests/unit/test_source_provider_contract.py`, `specs/001-deep-research-multi-agent-mvp/contracts/source-provider-contract.md`

- [X] T011 [P] P0: 创建 eval case framework-comparison in `eval/cases/001-framework-comparison.yml`
  - DoD: case 包含 `case_id`、theme、input_query、expected_perspectives、fixture_source_ids、required_metrics、pass_conditions。
  - Tests: EvalCase loader 能加载并校验该 case。
  - Related files: `eval/cases/001-framework-comparison.yml`, `tests/eval/test_eval_case_loading.py`

- [X] T012 [P] P0: 创建 framework-comparison fixture sources in `eval/fixtures/sources/001-framework-comparison.yml`
  - DoD: 至少包含 LangGraph、AutoGen、CrewAI 三类 source fixture，每条有 source metadata、excerpt、supported_claims、authority signal。
  - Tests: FixtureSourceProvider 能 search/fetch 该 case 全部 fixture sources。
  - Related files: `eval/fixtures/sources/001-framework-comparison.yml`, `tests/unit/test_fixture_provider.py`

- [X] T013 [P] P0: 创建 eval case financial-grounding in `eval/cases/002-financial-grounding.yml`
  - DoD: case 覆盖 high-risk financial research grounding、uncertainty、source authority 和 risk language。
  - Tests: EvalCase loader 校验 expected perspectives 和 pass conditions。
  - Related files: `eval/cases/002-financial-grounding.yml`, `tests/eval/test_eval_case_loading.py`

- [X] T014 [P] P0: 创建 financial-grounding fixture sources in `eval/fixtures/sources/002-financial-grounding.yml`
  - DoD: fixture sources 覆盖 official/regulatory/reputable report 类型，并包含 limitation/conflicting evidence 示例。
  - Tests: FixtureSourceProvider 能返回 authority_score 输入信号。
  - Related files: `eval/fixtures/sources/002-financial-grounding.yml`, `tests/unit/test_fixture_provider.py`

- [X] T015 [P] P0: 创建 eval case ai-coding-agent-trends in `eval/cases/003-ai-coding-agent-trends.yml`
  - DoD: case 覆盖 AI Coding Agent product forms、engineering challenges、trend synthesis 和 citation completeness。
  - Tests: EvalCase loader 校验 required metrics 完整。
  - Related files: `eval/cases/003-ai-coding-agent-trends.yml`, `tests/eval/test_eval_case_loading.py`

- [X] T016 [P] P0: 创建 ai-coding-agent-trends fixture sources in `eval/fixtures/sources/003-ai-coding-agent-trends.yml`
  - DoD: fixture sources 至少覆盖 product form、engineering challenge、risk/limitation 三类 evidence。
  - Tests: FixtureSourceProvider fetch 返回 content_excerpt 和 supported_claims。
  - Related files: `eval/fixtures/sources/003-ai-coding-agent-trends.yml`, `tests/unit/test_fixture_provider.py`

- [X] T017 [P] P0: 创建 eval case openhands-runtime in `eval/cases/004-openhands-runtime.yml`
  - DoD: case 覆盖 source/project research、runtime design、traceability 和 Agent Runtime terminology。
  - Tests: EvalCase loader 校验 fixture_source_ids 存在。
  - Related files: `eval/cases/004-openhands-runtime.yml`, `tests/eval/test_eval_case_loading.py`

- [X] T018 [P] P0: 创建 openhands-runtime fixture sources in `eval/fixtures/sources/004-openhands-runtime.yml`
  - DoD: fixture sources 包含项目/文档/架构信息，支持 runtime design claims。
  - Tests: FixtureSourceProvider search 能按 task perspective 过滤或排序。
  - Related files: `eval/fixtures/sources/004-openhands-runtime.yml`, `tests/unit/test_fixture_provider.py`

- [X] T019 [P] P0: 创建 eval case rag-2026 in `eval/cases/005-rag-2026.yml`
  - DoD: case 覆盖 controversial question、balanced evidence、limitations 和 follow-up questions。
  - Tests: EvalCase loader 校验 conflicting/balanced pass conditions。
  - Related files: `eval/cases/005-rag-2026.yml`, `tests/eval/test_eval_case_loading.py`

- [X] T020 [P] P0: 创建 rag-2026 fixture sources in `eval/fixtures/sources/005-rag-2026.yml`
  - DoD: fixture sources 同时包含 supporting、challenging、nuanced evidence，避免单边结论。
  - Tests: FixtureSourceProvider fetch 能返回 conflicting evidence 标记。
  - Related files: `eval/fixtures/sources/005-rag-2026.yml`, `tests/unit/test_fixture_provider.py`

- [X] T021 P0: 实现 FixtureSourceProvider in `traceresearch/source_discovery/fixture_provider.py`
  - DoD: 能读取 `eval/cases/*.yml` 和 `eval/fixtures/sources/*.yml`，按 case/task 返回 deterministic `SourceResult[]` 并 fetch `SourceDocument`。
  - Tests: 覆盖 5 个 seed cases 的 search/fetch、无 source、source_id 不存在。
  - Related files: `traceresearch/source_discovery/fixture_provider.py`, `tests/unit/test_fixture_provider.py`

- [X] T022 [P] P1: 实现 WebSearchProviderStub in `traceresearch/source_discovery/web_stub.py`
  - DoD: 选择 `web` provider 且未配置时返回 `provider_not_configured`，写入 Trace error，不 fallback 到 fixture。
  - Tests: 覆盖 not-configured error、Trace error event、CLI failed status。
  - Related files: `traceresearch/source_discovery/web_stub.py`, `tests/unit/test_web_stub.py`

## Phase 3: User Story 1 - Structured Evidence-Grounded Report (Priority: P0)

**Goal**: 用户输入明确复杂问题后，系统产出 `research_brief`、perspectives、research tasks、verified evidence、outline 和 final report。  
**Independent Test**: 使用 `001-framework-comparison` fixture case 跑通 `traceresearch run`，并验证 `final_report.md` 的 key claims 含 `[EV-...]`。

### Tests for User Story 1

- [X] T023 [P] [US1] P0: 编写 CLI run integration test in `tests/integration/test_run_fixture_case.py`
  - DoD: 测试执行 fixture run 后生成 required artifacts，并校验 `final_report.md` 与 `report.json` 存在。
  - Tests: `pytest tests/integration/test_run_fixture_case.py`
  - Related files: `tests/integration/test_run_fixture_case.py`, `specs/001-deep-research-multi-agent-mvp/contracts/cli-contract.md`
  - Note: failure is expected until T025-T032 implement the Planner/Researcher/Writer/Verifier/Critic/Harness/CLI run chain.

- [X] T024 [P] [US1] P0: 编写 report evidence linking test in `tests/integration/test_report_grounding.py`
  - DoD: 测试每个 key claim 至少有一个 verified evidence ID，unsupported claim 不进入 final report。
  - Tests: `pytest tests/integration/test_report_grounding.py`
  - Related files: `tests/integration/test_report_grounding.py`, `specs/001-deep-research-multi-agent-mvp/contracts/artifact-contract.md`
  - Note: failure is expected until T025-T032 implement the Planner/Researcher/Writer/Verifier/Critic/Harness/CLI run chain.

### Implementation for User Story 1

- [X] T025 [US1] P0: 实现 Planner in `traceresearch/agents/planner.py`
  - DoD: 对明确 query 生成 `ResearchBrief`、至少 3 个 perspectives、research tasks 和 success criteria。
  - Tests: 覆盖 normal query、case metadata 输入、research task perspective 绑定。
  - Related files: `traceresearch/agents/planner.py`, `tests/unit/test_planner.py`

- [X] T026 [US1] P0: 实现 Researcher source summarization in `traceresearch/agents/researcher.py`
  - DoD: 对每个 `ResearchTask` 调用 provider search/fetch，输出 `Evidence` candidates，不把 raw source dump 传给 Writer。
  - Tests: 覆盖 source discovery、空结果 no-evidence reason、summary/key_points/supported_claims。
  - Related files: `traceresearch/agents/researcher.py`, `tests/unit/test_researcher.py`

- [X] T027 [US1] P0: 实现 Writer outline and draft claims in `traceresearch/agents/writer.py`
  - DoD: Writer 第一阶段只生成 `outline.md` 和 draft claims package，不生成 final report；draft claims 包含 claim_id、text、candidate evidence IDs。
  - Tests: 覆盖 outline sections、draft claims JSON shape、无 evidence 时不生成强结论。
  - Related files: `traceresearch/agents/writer.py`, `tests/unit/test_writer_draft.py`

- [X] T028 [US1] P0: 实现 Verifier claim support check in `traceresearch/agents/verifier.py`
  - DoD: 接收 Writer draft claims 后输出 `VerificationResult`，标记 supported、weakly_supported、unsupported、conflicting。
  - Tests: 覆盖 supported/unsupported/conflicting claims、citation_completeness、critical_hallucination_count。
  - Related files: `traceresearch/agents/verifier.py`, `tests/unit/test_verifier.py`

- [X] T029 [US1] P0: 实现 Critic post-verification review in `traceresearch/agents/critic.py`
  - DoD: Critic 在 Verifier 之后运行，检查 missing perspectives、weak sources、duplicate sections、unsupported claims、limitations，并输出 next_phase。
  - Tests: 覆盖 weak-source、missing-perspective、unsupported-claim、limitation-to-add。
  - Related files: `traceresearch/agents/critic.py`, `tests/unit/test_critic.py`

- [X] T030 [US1] P0: 实现 Writer final report generation in `traceresearch/agents/writer.py`
  - DoD: Writer final 阶段只读取 verified evidence、VerificationResult 和 CritiqueResult，输出 `final_report.md` 与 `report.json`，key claims 均含 evidence IDs。
  - Tests: 覆盖 final report required sections、claim evidence IDs、unsupported_claims empty for pass。
  - Related files: `traceresearch/agents/writer.py`, `tests/unit/test_writer_final.py`

- [X] T031 [US1] P0: 实现 Harness execution order in `traceresearch/harness/orchestrator.py`
  - DoD: 固定执行顺序为 `Planner -> Researcher -> Evidence Store -> Writer draft claims -> Verifier -> Critic -> Writer final report`，并为每步写 Trace。
  - Tests: integration test 断言 Trace 中 role/event 顺序符合该链路。
  - Related files: `traceresearch/harness/orchestrator.py`, `tests/integration/test_orchestrator_order.py`

- [X] T032 [US1] P0: 实现 CLI run command in `traceresearch/cli.py`
  - DoD: `traceresearch run --query ... --source-provider fixture --case-id ...` 创建 run artifacts，并打印 run_id/status/artifact_dir。
  - Tests: CLI runner test 覆盖 success、provider not configured、artifact paths。
  - Related files: `traceresearch/cli.py`, `tests/integration/test_cli_run.py`

## Phase 4: User Story 2 - Safe Ambiguous Query Handling (Priority: P0)

**Goal**: 对 unclear 或 over-broad queries，系统 clarification 或记录 visible assumptions，不能直接产出 unsupported report。  
**Independent Test**: 输入缺少研究对象/时间范围/输出目标的问题，run status 为 `needs_clarification` 或 artifacts 中有明确 assumptions。

### Tests for User Story 2

- [ ] T033 [P] [US2] P0: 编写 ambiguous query tests in `tests/integration/test_ambiguous_query.py`
  - DoD: 覆盖缺 research object、缺 time range、缺 output goal、over-broad query 四类输入。
  - Tests: `pytest tests/integration/test_ambiguous_query.py`
  - Related files: `tests/integration/test_ambiguous_query.py`, `specs/001-deep-research-multi-agent-mvp/spec.md`

### Implementation for User Story 2

- [ ] T034 [US2] P0: 实现 Planner ambiguity policy in `traceresearch/agents/planner.py`
  - DoD: Planner 能返回 `open_clarifications` 或 explicit `assumptions`，并避免对无法界定的问题生成确定性 research tasks。
  - Tests: 单测覆盖 clarification 和 assumption 两种路径。
  - Related files: `traceresearch/agents/planner.py`, `tests/unit/test_planner_ambiguity.py`

- [ ] T035 [US2] P0: 实现 needs_clarification run handling in `traceresearch/harness/orchestrator.py`
  - DoD: 当 Planner 判定无法安全继续时，Harness 写 `research_brief.json`、`trace.jsonl`，run status 为 `needs_clarification`，不调用 Researcher/Writer。
  - Tests: Integration test 断言无 evidence/report final artifacts，Trace status 正确。
  - Related files: `traceresearch/harness/orchestrator.py`, `tests/integration/test_ambiguous_query.py`

## Phase 5: User Story 3 - Reviewer Evidence and Trace Inspection (Priority: P1)

**Goal**: Reviewer 能从 final report 的 key claim 追溯到 Evidence Store 和 Trace。  
**Independent Test**: 任意 completed run 中，抽取一个 `[EV-...]` 能在 `evidence.jsonl` 中找到，并能在 `trace.jsonl` 看到相关 Agent step。

### Tests for User Story 3

- [ ] T036 [P] [US3] P1: 编写 artifact inspection tests in `tests/integration/test_artifact_inspection.py`
  - DoD: 测试从 `final_report.md` evidence ID 追溯到 `evidence.jsonl` 和相关 `trace.jsonl` events。
  - Tests: `pytest tests/integration/test_artifact_inspection.py`
  - Related files: `tests/integration/test_artifact_inspection.py`, `specs/001-deep-research-multi-agent-mvp/contracts/artifact-contract.md`

### Implementation for User Story 3

- [ ] T037 [US3] P1: 实现 artifact read helpers in `traceresearch/harness/run_state.py`
  - DoD: 提供读取 run status、evidence by ID、trace events、report paths 的 helpers，供 quickstart/review/eval 使用。
  - Tests: 覆盖 completed/failed/needs_clarification run artifact 读取。
  - Related files: `traceresearch/harness/run_state.py`, `tests/unit/test_run_state.py`

- [ ] T038 [US3] P1: 增强 report renderer evidence references in `traceresearch/reports/renderer.py`
  - DoD: `final_report.md` 的 Evidence References section 列出 evidence ID、source title、source type、retrieved_at 和 limitation notes。
  - Tests: Snapshot 或 string tests 覆盖 Evidence References section。
  - Related files: `traceresearch/reports/renderer.py`, `tests/unit/test_report_renderer.py`

- [ ] T039 [US3] P1: 实现 Trace coverage validation in `traceresearch/trace/writer.py`
  - DoD: completed run 必须至少包含 Planner、Researcher、Verifier、Critic、Writer 和 Harness 的 Trace events。
  - Tests: 覆盖缺失 role Trace 时 validation failed。
  - Related files: `traceresearch/trace/writer.py`, `tests/unit/test_trace_writer.py`

## Phase 6: User Story 4 - Seed Eval and Iteration Review (Priority: P1)

**Goal**: Evaluator 能运行 5 个 seed eval cases，保存 metrics summary 和 bad-case notes，并进入 eval/review workflow。  
**Independent Test**: `traceresearch eval --cases-dir eval/cases --source-provider fixture --results-dir eval/results` 运行 5 cases，输出全部 metrics。

### Tests for User Story 4

- [ ] T040 [P] [US4] P1: 编写 eval metrics tests in `tests/eval/test_metrics.py`
  - DoD: 覆盖 `planner_coverage`、`perspective_diversity`、`source_relevance`、`source_authority`、`citation_completeness`、`faithfulness`、`unsupported_claim_count`、`critical_hallucination_count`、`case_pass_rate`。
  - Tests: `pytest tests/eval/test_metrics.py`
  - Related files: `tests/eval/test_metrics.py`, `traceresearch/eval/metrics.py`

- [ ] T041 [P] [US4] P1: 编写 eval runner integration test in `tests/eval/test_eval_runner.py`
  - DoD: 测试 5 个 seed cases 都被执行，且结果写入 `eval/results/`。
  - Tests: `pytest tests/eval/test_eval_runner.py`
  - Related files: `tests/eval/test_eval_runner.py`, `eval/cases/`, `eval/fixtures/sources/`

### Implementation for User Story 4

- [ ] T042 [US4] P1: 实现 metrics calculator in `traceresearch/eval/metrics.py`
  - DoD: 计算 plan/spec 要求的 9 个 metrics，并输出 numeric/pass-fail summary。
  - Tests: 单测覆盖 passing、failing、missing evidence、unsupported claims。
  - Related files: `traceresearch/eval/metrics.py`, `tests/eval/test_metrics.py`

- [ ] T043 [US4] P1: 实现 eval runner in `traceresearch/eval/runner.py`
  - DoD: 加载 `eval/cases/*.yml`，逐 case 调用 Harness，写入 `eval/results/<eval_run_id>-summary.json` 和 bad-case notes。
  - Tests: Integration test 覆盖 5 seed cases、failed case notes、suggested_next_phase。
  - Related files: `traceresearch/eval/runner.py`, `tests/eval/test_eval_runner.py`

- [ ] T044 [US4] P1: 实现 CLI eval command in `traceresearch/cli.py`
  - DoD: `traceresearch eval --cases-dir eval/cases --source-provider fixture --results-dir eval/results` 可运行，并打印 pass/fail summary。
  - Tests: CLI runner test 覆盖 eval command output 和 result file path。
  - Related files: `traceresearch/cli.py`, `tests/eval/test_cli_eval.py`

- [ ] T045 [US4] P1: 创建 eval workflow artifact in `specs/001-deep-research-multi-agent-mvp/eval.md`
  - DoD: `eval.md` 包含 Scope、Metrics、Cases、Commands、Latest Result、Bad Cases、Next Review Focus，并引用 `$speckit-ai-eval-review-eval`。
  - Tests: Markdown check 确认 required headings 和真实 skill 名存在。
  - Related files: `specs/001-deep-research-multi-agent-mvp/eval.md`, `.agents/skills/speckit-ai-eval-review-eval/SKILL.md`

## Final Phase: Polish, Eval, and Review

**Purpose**: 完成 cross-cutting validation、文档同步、真实 eval/review workflow。

- [ ] T046 P1: 更新 quickstart implementation notes in `specs/001-deep-research-multi-agent-mvp/quickstart.md`
  - DoD: quickstart 命令与最终 CLI 一致，并包含 run/eval/inspect evidence grounding 的实际路径。
  - Tests: 手动执行 quickstart 命令或记录未执行原因。
  - Related files: `specs/001-deep-research-multi-agent-mvp/quickstart.md`, `traceresearch/cli.py`

- [ ] T047 P1: 运行完整 test suite and fix failures in `tests/`
  - DoD: `pytest` 全部通过；如存在不可运行测试，必须在任务备注中说明阻塞原因。
  - Tests: `pytest`
  - Related files: `tests/`, `pyproject.toml`

- [ ] T048 P1: 运行 seed eval suite and save result in `eval/results/`
  - DoD: `traceresearch eval --cases-dir eval/cases --source-provider fixture --results-dir eval/results` 生成 summary，且包含 9 个 required metrics。
  - Tests: 检查 `eval/results/<eval_run_id>-summary.json` 存在并通过 JSON/schema validation。
  - Related files: `eval/results/`, `traceresearch/eval/runner.py`, `traceresearch/eval/metrics.py`

- [ ] T049 P1: 运行 `$speckit-ai-eval-review-eval` and update eval artifact in `specs/001-deep-research-multi-agent-mvp/eval.md`
  - DoD: 使用真实扩展 skill `$speckit-ai-eval-review-eval` 总结 tests/eval 命令、metrics、failed cases、bad-case root cause 和 recommended review focus。
  - Tests: `eval.md` Latest Result 更新，且引用最新 `eval/results/` 文件。
  - Related files: `specs/001-deep-research-multi-agent-mvp/eval.md`, `.agents/skills/speckit-ai-eval-review-eval/SKILL.md`, `eval/results/`

- [ ] T050 P1: 运行 `$speckit-ai-eval-review-review` and create review artifact in `specs/001-deep-research-multi-agent-mvp/review.md`
  - DoD: 使用真实扩展 skill `$speckit-ai-eval-review-review` 生成 review，包含 `decision`、`next_phase`、findings、bad cases 和 next actions。
  - Tests: `review.md` 包含 Required Behavior 的 YAML decision block；若无 latest eval result，不得标记 complete。
  - Related files: `specs/001-deep-research-multi-agent-mvp/review.md`, `.agents/skills/speckit-ai-eval-review-review/SKILL.md`

## Dependencies & Execution Order

### Phase Dependencies

- Phase 1 Setup: 无依赖。
- Phase 2 Foundational: 依赖 Phase 1；阻塞所有 User Story。
- Phase 3 US1: 依赖 Phase 2；提供核心 MVP run。
- Phase 4 US2: 依赖 T025 Planner 和 T031 Harness，可与 US1 后半部分交错但必须在 final review 前完成。
- Phase 5 US3: 依赖 T007/T008/T009 和 US1 completed run artifacts。
- Phase 6 US4: 依赖 5 个 eval cases、fixture sources、US1 harness 和 report artifacts。
- Final Phase: 依赖所有 P0/P1 implementation tasks。

### Critical Execution Chain

```text
T025 Planner
  -> T026 Researcher
  -> T009 Evidence Store
  -> T027 Writer draft claims
  -> T028 Verifier
  -> T029 Critic
  -> T030 Writer final report
  -> T031 Harness order validation
```

### User Story Dependencies

- US1: MVP primary flow，必须先完成。
- US2: 可在 US1 Planner/Harness 基础上并行推进 ambiguity handling。
- US3: 依赖 US1 生成可检查的 Evidence/Trace/Report artifacts。
- US4: 依赖 US1 可运行 pipeline 与 Phase 2 seed eval cases。

## Parallel Opportunities

- T004、T006、T010 可在 T001-T003 后并行。
- T011-T020 seed eval cases 与 fixture sources 可并行创建，但 T021 需要它们完成后验证。
- T023 和 T024 可并行编写。
- T028 Verifier 与 T029 Critic 的单元测试可先并行设计，但实现链路中 Critic 必须在 Verifier 后执行。
- T040 和 T041 可并行编写。

## Parallel Example

```text
Task: "T011 创建 eval/cases/001-framework-comparison.yml"
Task: "T013 创建 eval/cases/002-financial-grounding.yml"
Task: "T015 创建 eval/cases/003-ai-coding-agent-trends.yml"
Task: "T017 创建 eval/cases/004-openhands-runtime.yml"
Task: "T019 创建 eval/cases/005-rag-2026.yml"
```

```text
Task: "T012 创建 eval/fixtures/sources/001-framework-comparison.yml"
Task: "T014 创建 eval/fixtures/sources/002-financial-grounding.yml"
Task: "T016 创建 eval/fixtures/sources/003-ai-coding-agent-trends.yml"
Task: "T018 创建 eval/fixtures/sources/004-openhands-runtime.yml"
Task: "T020 创建 eval/fixtures/sources/005-rag-2026.yml"
```

## Implementation Strategy

### MVP First

1. 完成 T001-T022 foundation。
2. 完成 T023-T032 US1，跑通单个 fixture run。
3. 完成 T033-T035 US2，阻止 ambiguous query 生成 unsupported report。
4. 完成 T036-T039 US3，确保 reviewer 能追溯 evidence/Trace。
5. 完成 T040-T045 US4，跑通 5 seed eval cases。
6. 完成 T046-T050，运行 `$speckit-ai-eval-review-eval` 和 `$speckit-ai-eval-review-review`。

### Validation Gates

- 任一 completed report 不得包含无 evidence ID 的 key claim。
- `critical_hallucination_count` 必须为 0 才能进入 complete review。
- 缺少 latest eval result 时，review 必须 `decision: continue` 且 `next_phase: tasks`。
- evidence grounding、citation completeness、faithfulness 失败时，review 默认回到 `plan`。

## Task Summary

- Total tasks: 50
- Setup: 4
- Foundational: 18
- US1: 10
- US2: 3
- US3: 4
- US4: 6
- Final: 5
- Suggested MVP scope: T001-T035 gives a runnable core flow plus safe ambiguity handling; full feature complete requires T001-T050.
