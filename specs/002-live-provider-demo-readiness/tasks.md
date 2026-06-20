# Tasks: Live Provider Demo Readiness

> Language Policy: English headings, Chinese task descriptions, English task IDs / file paths / commands / AI-Agent terms.

**Input**: Design documents from `specs/002-live-provider-demo-readiness/`  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`  
**Priority Rule**: Fixture regression is protected first. Live smoke is manual/demo validation and MUST NOT enter the default pytest gate.

## Phase 1: Setup and Regression Guardrails

**Purpose**: 建立 live provider feature 的基础配置文件和回归边界，避免后续实现误提交 secret 或破坏 001 artifacts。

- [X] T001 [P] [P0] 创建 live provider 示例配置 in `.env.example`
  - DoD: `.env.example` 包含 `TRACERESEARCH_WEB_PROVIDER=exa`、空 `EXA_API_KEY=`、`TRACERESEARCH_WEB_TIMEOUT_SECONDS=10`、`TRACERESEARCH_WEB_MAX_RESULTS=5`，且无真实 secret。
  - Tests: 手动检查 `.env.example` 不含真实 key；后续由 T006/T032 覆盖。
  - Related files: `.env.example`, `specs/002-live-provider-demo-readiness/contracts/env-config-contract.md`

- [X] T002 [P] [P0] 校验 secret ignore policy in `.gitignore`
  - DoD: `.env`、`.env.*` 被 ignore，`.env.example` 允许提交，`runs/*` 继续 ignore。
  - Tests: `git check-ignore .env`; `git check-ignore runs/example-run/artifact.json`; `git check-ignore -v .env.example` 应确认 `.env.example` 未被忽略。
  - Related files: `.gitignore`, `.env.example`

- [X] T003 [P] [P0] 记录 baseline fixture regression commands in `specs/002-live-provider-demo-readiness/quickstart.md`
  - DoD: quickstart 明确 `python3 -m pytest`、fixture eval、unconfigured web check、configured live smoke 均有命令；live smoke 标记为 manual only。
  - Tests: Markdown review；后续 T037/T038 执行命令验证。
  - Related files: `specs/002-live-provider-demo-readiness/quickstart.md`

---

## Phase 2: Foundational Tests First

**Purpose**: 先写测试锁定 env/config、provider factory、Exa normalization、error mapping 和 CLI contract，再进入实现。

- [X] T004 [P] [P0] 编写 config/env loading unit tests in `tests/unit/test_config.py`
  - DoD: 覆盖默认 provider、missing/blank `EXA_API_KEY`、timeout/max results defaults、非法 timeout/max results、config repr/error 不泄露 secret。
  - Tests: `python3 -m pytest tests/unit/test_config.py`，实现前允许失败。
  - Related files: `tests/unit/test_config.py`, `traceresearch/config.py`, `specs/002-live-provider-demo-readiness/contracts/env-config-contract.md`

- [X] T005 [P] [P0] 编写 provider factory unit tests in `tests/unit/test_provider_factory.py`
  - DoD: 覆盖 `fixture` 返回 `FixtureSourceProvider`、`web` missing key 返回/抛出 `provider_not_configured`、`web` configured 返回 Exa provider、unsupported provider 明确失败、web 失败不 fallback fixture。
  - Tests: `python3 -m pytest tests/unit/test_provider_factory.py`，实现前允许失败。
  - Related files: `tests/unit/test_provider_factory.py`, `traceresearch/source_discovery/factory.py`, `traceresearch/source_discovery/fixture_provider.py`, `traceresearch/source_discovery/exa_provider.py`

- [X] T006 [P] [P0] 编写 Exa provider normalization unit tests in `tests/unit/test_exa_provider.py`
  - DoD: 使用 mocked Exa response 覆盖 title/url/publishedDate/author/text/highlights/summary/requestId/costDollars 到 `SourceResult` / `SourceDocument` 的映射。
  - Tests: `python3 -m pytest tests/unit/test_exa_provider.py`，实现前允许失败。
  - Related files: `tests/unit/test_exa_provider.py`, `traceresearch/source_discovery/exa_provider.py`, `specs/002-live-provider-demo-readiness/contracts/source-provider-contract.md`

- [X] T007 [P] [P0] 编写 provider error mapping unit tests in `tests/unit/test_web_error_mapping.py`
  - DoD: 覆盖 missing key、timeout、401/403 auth、429 rate limit、5xx provider error、empty results、schema normalization error，且 error message 不含 `EXA_API_KEY` 值。
  - Tests: `python3 -m pytest tests/unit/test_web_error_mapping.py`，实现前允许失败。
  - Related files: `tests/unit/test_web_error_mapping.py`, `traceresearch/source_discovery/base.py`, `traceresearch/source_discovery/exa_provider.py`, `traceresearch/source_discovery/web_stub.py`

- [X] T008 [P] [P0] 编写 CLI web contract tests in `tests/integration/test_cli_web_provider.py`
  - DoD: 覆盖 `traceresearch run --source-provider web` unconfigured failure output、mocked configured success output、no fixture fallback signal。
  - Tests: `python3 -m pytest tests/integration/test_cli_web_provider.py`，实现前允许失败。
  - Related files: `tests/integration/test_cli_web_provider.py`, `traceresearch/cli.py`, `specs/002-live-provider-demo-readiness/contracts/cli-contract.md`

- [X] T009 [P] [P0] 编写 mocked web provider integration test in `tests/integration/test_run_web_provider.py`
  - DoD: mocked provider run 生成 `research_brief.json`、`evidence.jsonl`、`trace.jsonl`、`final_report.md`、`report.json`，final report key claims 包含 `[EV-...]`，Trace 包含 web provider step。
  - Tests: `python3 -m pytest tests/integration/test_run_web_provider.py`，实现前允许失败。
  - Related files: `tests/integration/test_run_web_provider.py`, `traceresearch/harness/orchestrator.py`, `traceresearch/source_discovery/base.py`

- [X] T010 [P] [P1] 编写 README/demo readiness content tests in `tests/unit/test_readme_demo_readiness.py`
  - DoD: 测试 README 包含 project positioning、architecture、fixture demo、live web demo、secret handling、eval/review workflow、limitations、interview demo path；`.env.example` 不含真实 key。
  - Tests: `python3 -m pytest tests/unit/test_readme_demo_readiness.py`，实现前允许失败。
  - Related files: `tests/unit/test_readme_demo_readiness.py`, `README.md`, `.env.example`, `specs/002-live-provider-demo-readiness/contracts/demo-readiness-contract.md`

---

## Phase 3: Foundational Implementation

**Purpose**: 实现所有 user stories 共用的 config、error、factory 和 Exa provider 基础能力。完成后 user story work 可以独立推进。

- [X] T011 [P0] 实现 `LiveProviderConfig` env loader in `traceresearch/config.py`
  - DoD: 从环境变量读取 provider、API key、timeout、max results；支持 defaults；missing key 映射为 not configured；repr/error redacts secret。
  - Tests: `python3 -m pytest tests/unit/test_config.py`
  - Related files: `traceresearch/config.py`, `tests/unit/test_config.py`

- [X] T012 [P0] 扩展 provider error taxonomy in `traceresearch/source_discovery/base.py`
  - DoD: 定义/支持 `provider_timeout`、`provider_error`、`provider_rate_limited`、`provider_no_results`、`source_normalization_error` 等安全错误类型，不破坏既有 `ProviderNotConfiguredError`。
  - Tests: `python3 -m pytest tests/unit/test_web_error_mapping.py tests/unit/test_web_stub.py`
  - Related files: `traceresearch/source_discovery/base.py`, `traceresearch/source_discovery/web_stub.py`, `tests/unit/test_web_error_mapping.py`, `tests/unit/test_web_stub.py`

- [X] T013 [P0] 实现 provider factory in `traceresearch/source_discovery/factory.py`
  - DoD: `fixture` 返回 `FixtureSourceProvider`；`web` 根据 config 返回 `ExaSearchProvider` 或明确 `ProviderNotConfiguredError`；任何 web failure 不 fallback fixture。
  - Tests: `python3 -m pytest tests/unit/test_provider_factory.py`
  - Related files: `traceresearch/source_discovery/factory.py`, `traceresearch/source_discovery/fixture_provider.py`, `traceresearch/source_discovery/exa_provider.py`, `tests/unit/test_provider_factory.py`

- [X] T014 [P0] 实现 ExaSearchProvider HTTP/search/fetch skeleton in `traceresearch/source_discovery/exa_provider.py`
  - DoD: 使用 stdlib HTTP client 调用 Exa `/search`；支持 timeout/max results；`fetch` 可返回 search 缓存的 normalized document；不引入 SDK dependency。
  - Tests: `python3 -m pytest tests/unit/test_exa_provider.py`
  - Related files: `traceresearch/source_discovery/exa_provider.py`, `tests/unit/test_exa_provider.py`

- [X] T015 [P0] 实现 Exa response normalization in `traceresearch/source_discovery/exa_provider.py`
  - DoD: Exa `results[]` 映射到 `SourceResult` / `SourceDocument`；source_id 稳定；snippet 使用 highlights/summary/text；source_type/publisher/relevance/authority metadata 可供 Researcher 使用。
  - Tests: `python3 -m pytest tests/unit/test_exa_provider.py`
  - Related files: `traceresearch/source_discovery/exa_provider.py`, `traceresearch/evidence/models.py`, `tests/unit/test_exa_provider.py`

- [X] T016 [P0] 实现 provider error mapping in `traceresearch/source_discovery/exa_provider.py`
  - DoD: timeout、401/403、429、5xx、empty results、bad schema 均映射到安全错误；error/Trace payload 不包含 API key。
  - Tests: `python3 -m pytest tests/unit/test_web_error_mapping.py tests/unit/test_exa_provider.py`
  - Related files: `traceresearch/source_discovery/exa_provider.py`, `traceresearch/source_discovery/base.py`, `tests/unit/test_web_error_mapping.py`

**Checkpoint**: Config/factory/provider foundation ready. No CLI or harness behavior should be changed until tests are in place.

---

## Phase 4: User Story 2 - Fixture Regression Stability (Priority: P0)

**Goal**: 先保护 001 的 deterministic fixture behavior，确保 live provider work 不破坏 71 个测试和 5/5 fixture eval。

**Independent Test**: 未配置 `EXA_API_KEY` 时运行 `python3 -m pytest` 和 fixture eval，仍保持全绿与 5/5 pass。

- [X] T017 [P] [P0] [US2] 编写 fixture regression tests in `tests/integration/test_fixture_regression_after_web.py`
  - DoD: 覆盖 fixture run 在 live env 缺失/存在时都使用 fixture provider；fixture artifacts 不含 web provider source IDs；case_id fixture path 不受 web config 影响。
  - Tests: `python3 -m pytest tests/integration/test_fixture_regression_after_web.py`，实现前允许失败。
  - Related files: `tests/integration/test_fixture_regression_after_web.py`, `traceresearch/cli.py`, `traceresearch/harness/orchestrator.py`, `traceresearch/source_discovery/factory.py`

- [X] T018 [P0] [US2] 确保 fixture CLI path 继续通过 provider factory in `traceresearch/cli.py`
  - DoD: `traceresearch run --source-provider fixture` 仍可运行；`case_id` fixture eval path 保持不变；web env 不影响 fixture behavior。
  - Tests: `python3 -m pytest tests/integration/test_fixture_regression_after_web.py tests/integration/test_run_fixture_case.py`
  - Related files: `traceresearch/cli.py`, `traceresearch/source_discovery/factory.py`, `tests/integration/test_fixture_regression_after_web.py`

- [X] T019 [P0] [US2] 保持 fixture eval runner 强制使用 FixtureSourceProvider in `traceresearch/eval/runner.py`
  - DoD: `traceresearch eval --source-provider fixture` 不读取 live provider key；5 seed cases 仍 deterministic。
  - Tests: `python3 -m pytest tests/eval/test_eval_runner.py tests/eval/test_metrics.py`
  - Related files: `traceresearch/eval/runner.py`, `tests/eval/test_eval_runner.py`, `eval/cases/`, `eval/fixtures/sources/`

- [X] T020 [P0] [US2] 运行 full fixture regression suite in `tests/`
  - DoD: 当前 71 个测试继续全绿；若测试数增加，全部通过。
  - Tests: `python3 -m pytest`
  - Related files: `tests/`, `pyproject.toml`, `traceresearch/`

**Checkpoint**: 001 regression protected before live web path is enabled.

---

## Phase 5: User Story 1 - Live Web-Backed Research Run (Priority: P0)

**Goal**: 配置有效 live provider 后，`traceresearch run --source-provider web` 能使用 mocked/live-compatible Exa source results 生成 grounded research artifacts。

**Independent Test**: 使用 mocked Exa/provider 执行 web run，验证 `final_report.md`、`evidence.jsonl`、`trace.jsonl`、`report.json` 存在，且 key claims 有 evidence IDs。

- [X] T021 [P0] [US1] 添加 provider-aware harness entrypoint in `traceresearch/harness/orchestrator.py`
  - DoD: 新增可接收 selected `SourceDiscoveryProvider` 的 run path；保留 `run_fixture` wrapper；不改变 Agent order。
  - Tests: `python3 -m pytest tests/integration/test_run_web_provider.py tests/integration/test_run_fixture_case.py`
  - Related files: `traceresearch/harness/orchestrator.py`, `tests/integration/test_run_web_provider.py`, `tests/integration/test_run_fixture_case.py`

- [X] T022 [P0] [US1] 更新 Researcher/provider metadata handling in `traceresearch/agents/researcher.py`
  - DoD: live `SourceDocument.metadata` 可生成 authority/relevance、summary、key_points、supported_claims、limitations；fixture metadata 不回归。
  - Tests: `python3 -m pytest tests/integration/test_run_web_provider.py tests/unit/test_fixture_provider.py`
  - Related files: `traceresearch/agents/researcher.py`, `traceresearch/source_discovery/exa_provider.py`, `tests/integration/test_run_web_provider.py`

- [X] T023 [P0] [US1] 增强 Trace provider tool naming in `traceresearch/harness/orchestrator.py`
  - DoD: Trace 对 fixture 使用 `fixture.search`，对 live web 使用 `exa.search` 或 `web_search`；output_summary 包含 result count/evidence IDs；latency 字段保留安全值。
  - Tests: `python3 -m pytest tests/integration/test_run_web_provider.py tests/integration/test_artifact_inspection.py`
  - Related files: `traceresearch/harness/orchestrator.py`, `traceresearch/trace/models.py`, `tests/integration/test_run_web_provider.py`

- [X] T024 [P0] [US1] 接通 CLI `--source-provider web` configured success path in `traceresearch/cli.py`
  - DoD: CLI 使用 provider factory；configured web path 调 harness 并打印 `run_id/status/artifact_dir`；fixture path 保持；unsupported provider 明确失败。
  - Tests: `python3 -m pytest tests/integration/test_cli_web_provider.py tests/integration/test_run_web_provider.py`
  - Related files: `traceresearch/cli.py`, `traceresearch/source_discovery/factory.py`, `traceresearch/harness/orchestrator.py`, `tests/integration/test_cli_web_provider.py`

- [X] T025 [P0] [US1] 验证 mocked web artifacts grounding in `tests/integration/test_run_web_provider.py`
  - DoD: 测试断言 live/mock final report key claims 有 `[EV-...]`；evidence rows 包含 live title/url/retrieved_at；trace 有 web provider step。
  - Tests: `python3 -m pytest tests/integration/test_run_web_provider.py`
  - Related files: `tests/integration/test_run_web_provider.py`, `runs/`, `traceresearch/harness/orchestrator.py`

**Checkpoint**: US1 independently demoable with mocked provider and ready for manual live smoke.

---

## Phase 6: User Story 3 - Safe Web Provider Failure Handling (Priority: P1)

**Goal**: 缺 key、timeout、no results、provider error 都要清晰失败或降级，不 fallback 到 fixture，不泄露 secret。

**Independent Test**: 不配置 `EXA_API_KEY` 运行 web provider path，CLI 输出 `provider_not_configured`，Trace/error 安全，且未产生 fixture evidence。

- [X] T026 [P] [P1] [US3] 编写 unconfigured web failure integration tests in `tests/integration/test_web_unconfigured_failure.py`
  - DoD: 覆盖 missing/blank `EXA_API_KEY`，CLI 输出 `status=failed`、`error_type=provider_not_configured`，不创建 fixture evidence，不 fallback。
  - Tests: `python3 -m pytest tests/integration/test_web_unconfigured_failure.py`，实现前允许失败。
  - Related files: `tests/integration/test_web_unconfigured_failure.py`, `traceresearch/cli.py`, `traceresearch/source_discovery/factory.py`

- [X] T027 [P] [P1] [US3] 编写 no-results and provider-error integration tests in `tests/integration/test_web_provider_failures.py`
  - DoD: 使用 mocked Exa/provider 覆盖 timeout、rate limit、5xx、empty results；断言 safe error/no-evidence reason 可观察，report 不含 unsupported deterministic conclusion。
  - Tests: `python3 -m pytest tests/integration/test_web_provider_failures.py`，实现前允许失败。
  - Related files: `tests/integration/test_web_provider_failures.py`, `traceresearch/source_discovery/exa_provider.py`, `traceresearch/harness/orchestrator.py`

- [X] T028 [P1] [US3] 实现 unconfigured web failed-run handling in `traceresearch/cli.py`
  - DoD: missing key path 输出 clear status/error；必要时写 minimal failed run Trace；不调用 fixture provider；不吞异常。
  - Tests: `python3 -m pytest tests/integration/test_web_unconfigured_failure.py tests/unit/test_provider_factory.py`
  - Related files: `traceresearch/cli.py`, `traceresearch/source_discovery/factory.py`, `traceresearch/source_discovery/web_stub.py`, `tests/integration/test_web_unconfigured_failure.py`

- [X] T029 [P1] [US3] 实现 provider no-results/error safe artifacts in `traceresearch/harness/orchestrator.py`
  - DoD: provider no-results/error 时 Trace 记录原因；run 不误标 completed；若生成 report，只能包含 limitation/follow-up，不包含 unsupported conclusion。
  - Tests: `python3 -m pytest tests/integration/test_web_provider_failures.py tests/unit/test_web_error_mapping.py`
  - Related files: `traceresearch/harness/orchestrator.py`, `traceresearch/source_discovery/exa_provider.py`, `tests/integration/test_web_provider_failures.py`

- [X] T030 [P1] [US3] 增加 secret redaction regression assertions in `tests/unit/test_web_error_mapping.py`
  - DoD: 测试确认 fake API key 不出现在 CLI output、Trace error message、exception repr、report artifacts。
  - Tests: `python3 -m pytest tests/unit/test_web_error_mapping.py tests/integration/test_web_unconfigured_failure.py`
  - Related files: `tests/unit/test_web_error_mapping.py`, `tests/integration/test_web_unconfigured_failure.py`, `traceresearch/config.py`, `traceresearch/source_discovery/exa_provider.py`

**Checkpoint**: US3 independently validates graceful web failure behavior.

---

## Phase 7: User Story 4 - README and Demo Readiness (Priority: P1)

**Goal**: 新读者或面试官只看 README 就能理解项目价值、架构、fixture demo、live demo、eval/review workflow、limitations 和 screen-share demo path。

**Independent Test**: README content test 通过，manual review 可按 README 执行 fixture demo 与 unconfigured/live web path。

- [X] T031 [P1] [US4] 创建 root README demo guide in `README.md`
  - DoD: README 包含 project positioning、architecture overview、fixture demo、live web demo、secret handling、eval/review workflow、artifact inspection、limitations、interview screen-share path。
  - Tests: `python3 -m pytest tests/unit/test_readme_demo_readiness.py`
  - Related files: `README.md`, `tests/unit/test_readme_demo_readiness.py`, `specs/002-live-provider-demo-readiness/contracts/demo-readiness-contract.md`

- [X] T032 [P1] [US4] 更新 `.env.example` documentation alignment in `.env.example`
  - DoD: `.env.example` 与 README/contract 中 env keys 一致；无真实 secret；包括 comments 说明 live smoke manual only。
  - Tests: `python3 -m pytest tests/unit/test_readme_demo_readiness.py tests/unit/test_config.py`
  - Related files: `.env.example`, `README.md`, `tests/unit/test_readme_demo_readiness.py`

- [X] T033 [P1] [US4] 写入 live smoke manual notes in `specs/002-live-provider-demo-readiness/eval.md`
  - DoD: `eval.md` 说明 fixture eval 是 required gate；live smoke 是 manual/non-CI；包含 configured success 命令、unconfigured failure 命令、记录结果/skip reason 的格式。
  - Tests: Markdown review；后续 T039/T040 执行命令并更新 result。
  - Related files: `specs/002-live-provider-demo-readiness/eval.md`, `README.md`, `specs/002-live-provider-demo-readiness/quickstart.md`

**Checkpoint**: US4 independently satisfies demo-readiness documentation.

---

## Final Phase: Polish, Eval, and Review

**Purpose**: 汇总验证、fixture regression、manual live smoke 记录、eval/review artifacts，并确认未实现 Non-Goals。

- [ ] T034 [P0] 运行 full pytest regression in `tests/`
  - DoD: 所有 tests 通过；必须保持 001 原有测试不破坏，新增测试也通过。
  - Tests: `python3 -m pytest`
  - Related files: `tests/`, `traceresearch/`, `pyproject.toml`

- [ ] T035 [P0] 运行 fixture eval regression and save summary in `eval/results/`
  - DoD: `traceresearch eval --cases-dir eval/cases --source-provider fixture --results-dir eval/results` 生成 summary；5 seed cases 5/5 pass；9 metrics present。
  - Tests: `traceresearch eval --cases-dir eval/cases --source-provider fixture --results-dir eval/results`; JSON validation script from quickstart.
  - Related files: `eval/results/`, `eval/cases/`, `eval/fixtures/sources/`, `traceresearch/eval/runner.py`

- [ ] T036 [P0] 验证 unconfigured web smoke in `specs/002-live-provider-demo-readiness/eval.md`
  - DoD: `unset EXA_API_KEY` 后运行 `traceresearch run --source-provider web`，记录 `provider_not_configured`、no fallback 结果到 eval notes。
  - Tests: `unset EXA_API_KEY && traceresearch run --query "What changed in AI coding agents during the last 12 months?" --source-provider web --output-dir runs`
  - Related files: `specs/002-live-provider-demo-readiness/eval.md`, `README.md`, `traceresearch/cli.py`

- [ ] T037 [P1] 记录 configured live smoke result or skip reason in `specs/002-live-provider-demo-readiness/eval.md`
  - DoD: 如果本地有 `EXA_API_KEY`，运行 live smoke 并记录 artifact path；如果没有 key，记录 skip reason 和 exact command；不将 live smoke 加入 pytest gate。
  - Tests: Manual `traceresearch run --source-provider web` with `EXA_API_KEY` when available; otherwise document not run.
  - Related files: `specs/002-live-provider-demo-readiness/eval.md`, `README.md`, `runs/`

- [ ] T038 [P1] 执行 secret scan and tracked-file review in repository root
  - DoD: 确认 tracked files 不含真实 API key；`.env` 未被跟踪；Trace/report 不包含 secret；记录检查结果。
  - Tests: `git status --short`; `git ls-files | rg '(^|/)\\.env$'` should return empty; targeted `rg` for fake/real key patterns where safe。
  - Related files: `.env.example`, `.gitignore`, `README.md`, `specs/002-live-provider-demo-readiness/review.md`

- [ ] T039 [P1] 更新 review artifact in `specs/002-live-provider-demo-readiness/review.md`
  - DoD: review 包含 decision、next_phase、findings、bad cases、known limitations、next actions；若 fixture eval 或 grounding gate 失败，不得 complete。
  - Tests: Markdown review; verify decision block exists.
  - Related files: `specs/002-live-provider-demo-readiness/review.md`, `specs/002-live-provider-demo-readiness/eval.md`, `eval/results/`

- [ ] T040 [P1] 验证 Non-Goals 未越界 in `specs/002-live-provider-demo-readiness/review.md`
  - DoD: review 明确未实现 LLM-backed agents、Web UI、PDF/HTML export、大规模 benchmark、live web CI gate；若代码引入这些范围，必须回到 spec/plan。
  - Tests: Code/doc review; `rg -n "Web UI|PDF|HTML export|LLM-backed|benchmark" specs/002-live-provider-demo-readiness README.md traceresearch tests`
  - Related files: `specs/002-live-provider-demo-readiness/review.md`, `README.md`, `traceresearch/`

---

## Dependencies & Execution Order

### Phase Dependencies

- Phase 1 Setup: 无依赖，可立即开始。
- Phase 2 Foundational Tests First: 依赖 Phase 1；必须先写测试。
- Phase 3 Foundational Implementation: 依赖 Phase 2 tests；阻塞所有 User Stories。
- Phase 4 US2 Fixture Regression: 依赖 Phase 3；优先于 live success，保护 001 既有 71 tests 和 fixture eval。
- Phase 5 US1 Live Web Run: 依赖 Phase 3；建议在 US2 checkpoint 后推进。
- Phase 6 US3 Failure Handling: 依赖 Phase 3；可与 US1 部分并行，但 final review 前必须完成。
- Phase 7 US4 README/Demo: 依赖 Phase 1/2；可与 US1/US3 后半段并行。
- Final Phase: 依赖所有 User Stories。

### User Story Dependencies

- US2 (P0 Fixture Regression): 最高保护优先级；确认 fixture path 不回归。
- US1 (P0 Live Web Run): 依赖 config/factory/provider foundation；提供 demo success path。
- US3 (P1 Safe Failure Handling): 依赖 web provider path；提供 unconfigured/error demo path。
- US4 (P1 README/Demo): 依赖 commands and validation flow；可并行编写并最终同步真实结果。

### Critical Execution Chain

```text
T004-T010 tests
  -> T011 config
  -> T012 errors
  -> T013 provider factory
  -> T014-T016 Exa provider
  -> T017-T020 fixture regression checkpoint
  -> T021-T025 live web success path
  -> T026-T030 failure handling
  -> T031-T033 README/eval docs
  -> T034-T040 final validation/review
```

## Parallel Opportunities

- T001-T003 can run in parallel.
- T004-T010 can run in parallel because they create separate test files.
- T011 and T012 can run in parallel after tests are written; T013 depends on both.
- T014/T015/T016 are tightly related and should be sequential within `exa_provider.py`.
- T017 can run before T018/T019; T020 waits for US2 implementation.
- T026/T027 can be written in parallel.
- T031/T032/T033 can run in parallel with late US1/US3 implementation once command shape is stable.

## Parallel Example: Foundational Tests

```text
Task: "T004 [P] [P0] 编写 config/env loading unit tests in tests/unit/test_config.py"
Task: "T005 [P] [P0] 编写 provider factory unit tests in tests/unit/test_provider_factory.py"
Task: "T006 [P] [P0] 编写 Exa provider normalization unit tests in tests/unit/test_exa_provider.py"
Task: "T007 [P] [P0] 编写 provider error mapping unit tests in tests/unit/test_web_error_mapping.py"
Task: "T008 [P] [P0] 编写 CLI web contract tests in tests/integration/test_cli_web_provider.py"
Task: "T009 [P] [P0] 编写 mocked web provider integration test in tests/integration/test_run_web_provider.py"
```

## Parallel Example: Documentation and Demo

```text
Task: "T031 [P1] [US4] 创建 root README demo guide in README.md"
Task: "T032 [P1] [US4] 更新 .env.example documentation alignment in .env.example"
Task: "T033 [P1] [US4] 写入 live smoke manual notes in specs/002-live-provider-demo-readiness/eval.md"
```

## Implementation Strategy

### MVP First

1. Complete Phase 1-3 foundation with tests first.
2. Complete US2 fixture regression checkpoint before live web behavior is considered done.
3. Complete US1 mocked/configured web path.
4. Complete US3 safe failure path.
5. Complete US4 README/demo readiness.
6. Run final pytest, fixture eval, unconfigured web smoke, optional configured live smoke, eval/review.

### Scope Guardrails

- Do not implement LLM-backed agents.
- Do not add Web UI.
- Do not add PDF/HTML export.
- Do not move live smoke into default pytest/CI.
- Do not remove fixture deterministic tests or fixture eval.
- Do not commit real API keys.

### Suggested Implementation Batches

- Batch A: T001-T016 config/factory/provider foundation.
- Batch B: T017-T020 fixture regression protection.
- Batch C: T021-T030 live success and failure paths.
- Batch D: T031-T040 README, eval, review, validation.
