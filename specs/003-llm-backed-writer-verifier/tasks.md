# Tasks: LLM-Backed Writer / Verifier

> Language Policy: English headings, Chinese task descriptions, English task IDs / file paths / commands / AI-Agent terms.

**Feature**: 003-llm-backed-writer-verifier
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

**Priority**: P0 = 阻塞性 / gates / regression | P1 = 核心功能 | P2 = 文档 / smoke eval / polish

---

## Phase 1: LLM Foundation — Config, Provider, Schemas (Foundational)

> 本阶段构建 LLM provider abstraction 的完整基础设施。完成后可独立验证：import 模块、config 读取、mock HTTP 测试通过。阻塞所有后续 LLM 相关 Phase。

### 1.1 Config & Dependencies

- [x] T001 [P0] 添加 `httpx` 依赖到 `pyproject.toml`，并更新 lock/install
  - DoD: `import httpx` 成功，`pip install -e ".[dev]"` 无报错
  - Tests: `python3 -c "import httpx; print(httpx.__version__)"`
  - Related files: `pyproject.toml`

- [x] T002 [P0] 实现 `LLMProviderConfig` — 从环境变量读取 LLM 配置，含 provider name、api_key、model、base_url、timeout、max_tokens、temperature
  - DoD: `LLMProviderConfig.from_env()` 返回完整配置；无 key 时 `api_key=""` 不抛异常
  - Tests: `python3 -m pytest tests/unit/test_llm_config.py -v`
  - Related files: `traceresearch/llm/__init__.py`, `traceresearch/llm/config.py`, `tests/unit/test_llm_config.py`

### 1.2 LLMProvider Protocol + Error Model

- [x] T003 [P0] 先写 test: `test_llm_provider_protocol.py` — 覆盖 ABC 不可直接实例化、`complete()` 签名、`LLMProviderError` 属性
  - DoD: tests 文件存在，覆盖 protocol contract 的所有约束
  - Tests: `python3 -m pytest tests/unit/test_llm_provider_protocol.py -v`
  - Related files: `tests/unit/test_llm_provider_protocol.py`

- [x] T004 [P0] 实现 `LLMProvider` ABC + `LLMProviderError` — provider_name (property)、model (property)、`complete(prompt, response_schema, system_prompt=None) -> BaseModel`
  - DoD: ABC 不可实例化；`LLMProviderError(reason, provider, model, latency_ms)` 包含所有必需属性；子类未实现 abstract method 报 TypeError
  - Tests: `python3 -m pytest tests/unit/test_llm_provider_protocol.py -v`
  - Related files: `traceresearch/llm/provider.py`

### 1.3 DeepSeekProvider

- [x] T005 [P0] 先写 test: `test_deepseek_provider.py` — 用 `pytest.httpx` (或 `respx`) mock HTTP，覆盖：正常 response 解析、timeout、HTTP 4xx/5xx、rate limit 429、invalid JSON response
  - DoD: test 文件包含 5+ 个 mock scenario，不发起真实网络请求
  - Tests: `python3 -m pytest tests/unit/test_deepseek_provider.py -v`
  - Related files: `tests/unit/test_deepseek_provider.py`

- [x] T006 [P0] 实现 `DeepSeekProvider` — 实现 `LLMProvider`，用 `httpx` POST `/v1/chat/completions`，解析 OpenAI-compatible response，调用 `response_schema.model_validate_json()` 后返回
  - DoD: T005 全部 mock tests pass；response 解析失败抛 `LLMProviderError(reason="invalid_response")`；HTTP timeout 抛 `LLMProviderError(reason="timeout")`；HTTP 429 抛 `LLMProviderError(reason="rate_limit")`
  - Tests: `python3 -m pytest tests/unit/test_deepseek_provider.py -v`
  - Related files: `traceresearch/llm/deepseek_provider.py`

### 1.4 LLM Output Schemas

- [x] T007 [P0] 先写 test: `test_llm_schemas.py` — 覆盖 `LLMFinalReportSchema` / `LLMFindingSchema` / `LLMVerificationResultSchema` / `LLMClaimJudgmentSchema` 的 valid/invalid JSON 解析、required field 缺失、extra field 拒绝、enum value 验证
  - DoD: test 覆盖所有 4 个 schema 的 happy path 和至少 3 种 validation failure
  - Tests: `python3 -m pytest tests/unit/test_llm_schemas.py -v`
  - Related files: `tests/unit/test_llm_schemas.py`

- [x] T008 [P0] 实现 `traceresearch/llm/schemas.py` — 定义 `LLMFinalReportSchema`、`LLMFindingSchema`、`LLMVerificationResultSchema`、`LLMClaimJudgmentSchema`（Pydantic BaseModel，`extra="forbid"`）
  - DoD: T007 全部 tests pass；所有 schema 使用 `StrictModel` 或 `extra="forbid"`；`confidence` 用 `Literal["high","medium","low"]`；`support_status` 用 `Literal["supported","weakly_supported","unsupported","conflicting"]`
  - Tests: `python3 -m pytest tests/unit/test_llm_schemas.py -v`
  - Related files: `traceresearch/llm/schemas.py`

---

## Phase 2: WriterProtocol / VerifierProtocol (Foundational)

> 定义 Writer 和 Verifier 的抽象边界，确认 deterministic 实现满足 protocol。完成后可独立验证：`isinstance(Writer(), WriterProtocol)` 为 True。

### 2.1 WriterProtocol

- [x] T009 [P1] 先写 test: `test_writer_protocol.py` — 验证 `Writer` 满足 `WriterProtocol`（`isinstance` 检查、方法签名匹配、`draft()` 返回 `DraftReport`、`final()` 返回 `FinalReport`）
  - DoD: test 覆盖 protocol conformance 检查
  - Tests: `python3 -m pytest tests/unit/test_writer_protocol.py -v`
  - Related files: `tests/unit/test_writer_protocol.py`

- [x] T010 [P1] 定义 `WriterProtocol` ABC — `draft(brief, evidence) -> DraftReport`、`final(brief, verified_evidence, verification, critique) -> FinalReport`
  - DoD: T009 pass；`WriterProtocol` 是 ABC，不能直接实例化；现有 `Writer` 类通过 `isinstance(x, WriterProtocol)` 检查
  - Tests: `python3 -m pytest tests/unit/test_writer_protocol.py -v`
  - Related files: `traceresearch/agents/writer_protocol.py`, `traceresearch/agents/writer.py`

### 2.2 VerifierProtocol

- [x] T011 [P1] 先写 test: `test_verifier_protocol.py` — 验证 `Verifier` 满足 `VerifierProtocol`（`isinstance` 检查、`verify()` 签名匹配、返回 `VerificationResult`）
  - DoD: test 覆盖 protocol conformance 检查
  - Tests: `python3 -m pytest tests/unit/test_verifier_protocol.py -v`
  - Related files: `tests/unit/test_verifier_protocol.py`

- [x] T012 [P1] 定义 `VerifierProtocol` ABC — `verify(run_id, draft, evidence) -> VerificationResult`
  - DoD: T011 pass；`VerifierProtocol` 是 ABC，不能直接实例化；现有 `Verifier` 类通过 `isinstance` 检查
  - Tests: `python3 -m pytest tests/unit/test_verifier_protocol.py -v`
  - Related files: `traceresearch/agents/verifier_protocol.py`, `traceresearch/agents/verifier.py`

### 2.3 Deterministic Compatibility

- [x] T013 [P1] 在 `writer.py` / `verifier.py` module 级别添加 `DeterministicWriter = Writer` 和 `DeterministicVerifier = Verifier` alias；确认无 LLM 配置时所有现有 tests pass
  - DoD: `from traceresearch.agents.writer import DeterministicWriter` 可用；`python3 -m pytest` 100% pass
  - Tests: `python3 -m pytest tests/ -v --ignore=tests/llm_smoke`
  - Related files: `traceresearch/agents/writer.py`, `traceresearch/agents/verifier.py`

---

## Phase 3: LLM Verifier (US2 — Priority P1)

> 实现语义级 claim verification。user story: "LLM-backed Verifier semantically judges claim-evidence alignment"

### 3.1 LLM Verifier Unit Tests

- [x] T014 [P1] [US2] 先写 test: `test_llm_verifier.py` — 用 mock `LLMProvider`（fake `complete()` 返回预制 JSON），覆盖：
  - SUPPORTED claim: evidence summary 与 claim 语义一致 → support_status=supported
  - WEAKLY_SUPPORTED claim: evidence 部分覆盖 → support_status=weakly_supported
  - UNSUPPORTED claim: evidence 无关 / 矛盾 → support_status=unsupported
  - LLM 返回 invalid JSON → fallback deterministic
  - LLM 返回的 claim_ids 与输入不匹配 → fallback deterministic
  - LLM 抛 `LLMProviderError` → fallback deterministic
  - 空 claims 输入 → 直接返回空 VerificationResult
  - DoD: test 文件覆盖所有 acceptance scenarios + edge cases
  - Tests: `python3 -m pytest tests/unit/test_llm_verifier.py -v`
  - Related files: `tests/unit/test_llm_verifier.py`

### 3.2 LLM Verifier Implementation

- [x] T015 [P1] [US2] 实现 `LLMVerifier` — 实现 `VerifierProtocol`，构造函数接收 `LLMProvider` 和 `LLMVerifierConfig`。`verify()` 方法：
  1. 构建 prompt（包含 claim text + evidence summary + 判断要求）
  2. 调用 `provider.complete(prompt, schema=LLMVerificationResultSchema)`
  3. Post-validate: claim_ids 集合匹配、support_status 合法
  4. Map `LLMClaimJudgmentSchema` → domain `Claim` objects
  5. 失败 → fallback `Verifier().verify()`
  - DoD: T014 全部 tests pass
  - Tests: `python3 -m pytest tests/unit/test_llm_verifier.py -v`
  - Related files: `traceresearch/agents/llm_verifier.py`

---

## Phase 4: LLM Writer (US1 — Priority P1)

> 实现 LLM-backed final report writing。user story: "LLM-backed Writer generates natural report from verified evidence"

### 4.1 LLM Writer Unit Tests

- [x] T016 [P1] [US1] 先写 test: `test_llm_writer.py` — 用 mock `LLMProvider`（fake `complete()` 返回预制 JSON），覆盖：
  - 正常 verified evidence → FinalReport 包含 executive_summary + findings + limitations + evidence_refs + follow_ups
  - 所有 key claims 的 evidence_ids 都来自输入 evidence set（hallucination check）
  - 空 evidence → report 明确指示 no verified findings
  - LLM 返回 invalid JSON → fallback deterministic Writer
  - LLM 返回的 evidence_ids 不在输入集合 → fallback deterministic
  - LLM 抛 `LLMProviderError` (timeout/rate_limit/provider_error) → fallback deterministic
  - Evidence 超过 `max_evidence_items` → 截断到 top-N
  - DoD: test 覆盖所有 acceptance scenarios + evidence ID hallucination check
  - Tests: `python3 -m pytest tests/unit/test_llm_writer.py -v`
  - Related files: `tests/unit/test_llm_writer.py`

### 4.2 LLM Writer Implementation

- [x] T017 [P1] [US1] 实现 `LLMWriter` — 实现 `WriterProtocol`，构造函数接收 `LLMProvider` 和 `LLMWriterConfig`。`final()` 方法：
  1. 截断 evidence 到 `max_evidence_items`
  2. 构建 prompt（evidence summaries + research_brief objective + sections 要求）
  3. 调用 `provider.complete(prompt, schema=LLMFinalReportSchema)`
  4. Post-validate: 每个 finding 的 evidence_ids 都在输入 evidence set 中
  5. Map schema → domain `FinalReport`（markdown + report_json）
  6. 失败 → fallback `Writer().final()`
  - DoD: T016 全部 tests pass
  - Tests: `python3 -m pytest tests/unit/test_llm_writer.py -v`
  - Related files: `traceresearch/agents/llm_writer.py`

---

## Phase 5: Harness Integration + CLI Mode Selection (US1, US2, US3)

> 将 LLM-backed Writer/Verifier 接入 Harness 和 CLI。

### 5.1 Mode Selection Logic

- [ ] T018 [P1] 先写 test: `test_mode_selection.py` — 覆盖：
  - 环境变量 `TRACERESEARCH_WRITER_MODE=llm` + key 存在 → 构建 `LLMWriter`
  - 环境变量 `TRACERESEARCH_VERIFIER_MODE=llm` + key 存在 → 构建 `LLMVerifier`
  - 环境变量 mode=llm 但 key 缺失 → fallback deterministic + WARNING
  - 环境变量未设置 → 默认 deterministic
  - CLI `--writer-mode llm` 覆盖环境变量
  - CLI `--verifier-mode deterministic` 覆盖环境变量
  - DoD: 覆盖所有 mode selection 优先级组合
  - Tests: `python3 -m pytest tests/unit/test_mode_selection.py -v`
  - Related files: `tests/unit/test_mode_selection.py`

- [ ] T019 [P1] 实现 `build_writer(mode, llm_provider)` / `build_verifier(mode, llm_provider)` factory functions in `traceresearch/harness/mode_factory.py`
  - DoD: T018 全部 pass；factory 返回正确的 WriterProtocol/VerifierProtocol 实例
  - Tests: `python3 -m pytest tests/unit/test_mode_selection.py -v`
  - Related files: `traceresearch/harness/mode_factory.py`

### 5.2 CLI Integration

- [ ] T020 [P1] 在 `cli.py` 新增 `--writer-mode` (choices: deterministic|llm, default: deterministic) 和 `--verifier-mode` (choices: deterministic|llm, default: deterministic) 两个 CLI options；传递到 Harness
  - DoD: `traceresearch run --help` 显示新选项；`traceresearch run --writer-mode llm` 不报参数错误
  - Tests: `python3 -m pytest tests/integration/test_cli_llm_modes.py -v`
  - Related files: `traceresearch/cli.py`

- [ ] T021 [P1] 更新 `ResearchHarness.__init__` — 接收 `writer_mode` 和 `verifier_mode` 参数，调用 `mode_factory` 构建对应实例；保留 `writer=` / `verifier=` kwarg（直接注入，优先于 mode）
  - DoD: Harness 可以通过 mode string 或直接实例构建；现有 tests 无修改仍然 pass
  - Tests: `python3 -m pytest tests/unit/test_harness.py tests/integration/ -v --ignore=tests/llm_smoke`
  - Related files: `traceresearch/harness/orchestrator.py`

### 5.3 Harness Integration Tests

- [ ] T022 [P1] [US3] 先写 integration test: `test_llm_harness_integration.py` — mock LLM + fixture evidence → 完整 harness run：
  - `writer_mode=llm` → 产出 `final_report.md`，包含 evidence IDs
  - `verifier_mode=llm` → 产出 `verification.json`，包含 reasoning notes
  - both modes=llm → 完整 end-to-end
  - LLM fail → fallback deterministic, run 仍 COMPLETED
  - 无 LLM 配置 → 默认 deterministic, run 正常
  - DoD: integration test 覆盖所有 harness + mode 组合
  - Tests: `python3 -m pytest tests/integration/test_llm_harness_integration.py -v`
  - Related files: `tests/integration/test_llm_harness_integration.py`

---

## Phase 6: Trace Extension (US3 — Priority P1)

> 扩展 Trace 记录 LLM 调用详情。user story: "Deterministic fallback preserves fixture regression stability"

### 6.1 Trace Model Extension

- [ ] T023 [P1] [US3] 先写 test: `test_trace_llm_fields.py` — 覆盖：
  - `TraceEvent` 支持 `llm_mode`, `llm_model`, `llm_token_usage`, `failover_reason` 可选字段
  - 现有 TraceEvent 不设置这些字段仍然正常序列化/反序列化（向后兼容）
  - `llm_mode` 值限于 `"llm"` | `"deterministic"` | `None`
  - `failover_reason` 值限于已知枚举 + 自定义 string
  - `llm_token_usage` 是 `TokenUsage` 实例（复用现有 model）
  - DoD: test 覆盖新旧字段兼容性
  - Tests: `python3 -m pytest tests/unit/test_trace_llm_fields.py -v`
  - Related files: `tests/unit/test_trace_llm_fields.py`

- [ ] T024 [P1] [US3] 扩展 `traceresearch/trace/models.py` — 给 `TraceEvent` 添加 `llm_mode`, `llm_model`, `llm_token_usage`, `failover_reason` 四个 Optional 字段（默认 None，向后兼容）
  - DoD: T023 pass；`test_trace_writer.py` 和 `test_trace_models.py` 继续 pass
  - Tests: `python3 -m pytest tests/unit/test_trace_llm_fields.py tests/unit/test_trace_writer.py tests/unit/test_trace_models.py -v`
  - Related files: `traceresearch/trace/models.py`

### 6.2 Harness Trace Recording

- [ ] T025 [P1] [US3] 更新 `orchestrator.py` 中的 `_TraceRecorder` — 支持记录 LLM 相关字段到 TraceEvent。在 LLM Writer/Verifier 调用前后写入 LLM START/TOOL_CALL/TOOL_RESULT/WARNING 事件
  - DoD: LLM run 的 `trace.jsonl` 包含 `llm_mode`, `llm_model`, `llm_token_usage`；failover run 包含 `failover_reason`
  - Tests: `python3 -m pytest tests/integration/test_llm_harness_integration.py -v`（检查 trace 内容）
  - Related files: `traceresearch/harness/orchestrator.py`

---

## Phase 7: LLM Smoke Eval (US4 — Priority P2)

> 手动 LLM smoke eval，不进入 CI。user story: "Manual LLM smoke eval runs independently of CI"

### 7.1 Smoke Eval Infrastructure

- [ ] T026 [P2] [US4] 配置 pytest marker `llm_smoke`：在 `pyproject.toml` 添加 `addopts = "-m 'not llm_smoke'"`，创建 `tests/llm_smoke/` 目录和 `conftest.py`（注册 marker）
  - DoD: `python3 -m pytest` 不运行 `llm_smoke` tests；`python3 -m pytest -m llm_smoke` 仅运行 LLM smoke tests
  - Tests: `python3 -m pytest --collect-only -m llm_smoke` 只显示 smoke tests
  - Related files: `pyproject.toml`, `tests/llm_smoke/__init__.py`, `tests/llm_smoke/conftest.py`

- [ ] T027 [P2] [US4] 实现 `traceresearch/eval/llm_smoke.py` — LLM smoke eval runner：加载 smoke cases → 运行 LLM Writer/Verifier → 输出 metrics（faithfulness, citation_completeness, unsupported_claim_count, failover_success）→ 写 JSON result
  - DoD: smoke eval runner 可独立调用；输出 JSON 包含所有 metrics
  - Tests: 手动运行验证
  - Related files: `traceresearch/eval/llm_smoke.py`

### 7.2 Smoke Eval Cases

- [ ] T028 [P2] [US4] 撰写 LLM smoke eval cases — 创建 `eval/llm_smoke_cases/` 目录，包含 3 个 YAML cases：
  - `llm-smoke-writer.yaml`: fixture case-001 evidence → LLM Writer → 检查 output faithfulness + evidence binding
  - `llm-smoke-verifier.yaml`: 预制 mixed claims (supported/weakly_supported/unsupported) → LLM Verifier → 检查分类准确率
  - `llm-smoke-failover.yaml`: mock LLM 返回 invalid JSON → 验证 fallback 成功
  - DoD: 3 个 YAML 文件存在，格式与 `eval/cases/` 一致
  - Tests: `python3 -c "import yaml; [yaml.safe_load(open(f'eval/llm_smoke_cases/{c}')) for c in ['llm-smoke-writer.yaml','llm-smoke-verifier.yaml','llm-smoke-failover.yaml']]"`
  - Related files: `eval/llm_smoke_cases/*.yaml`

- [ ] T029 [P2] [US4] 实现 LLM smoke eval CLI 入口 — `traceresearch llm-smoke` 命令，读取 `eval/llm_smoke_cases/`，运行 `LLMSmokeRunner`，输出 summary 到 `eval/results/`
  - DoD: `traceresearch llm-smoke` 运行成功 or 返回 "LLM not configured"（无 key 时）
  - Tests: 手动运行 `traceresearch llm-smoke`（需 DEEPSEEK_API_KEY）
  - Related files: `traceresearch/cli.py`, `traceresearch/eval/llm_smoke.py`

---

## Phase 8: Regression Gates & Documentation (US3, US4)

> 最终验证：fixture regression、live provider path、文档、review。

### 8.1 Regression Verification

- [ ] T030 [P0] [US3] 运行 fixture eval regression —— 验证 `traceresearch eval` 5/5 pass，Output Determinism=1.0，9 metrics 正常输出
  - DoD: `case_pass_rate=1.0`，无任何 regression
  - Tests: `traceresearch eval` && `python3 -m pytest`
  - Related files: N/A（验证任务）

- [ ] T031 [P0] [US3] 运行 live web provider path 验证 —— `traceresearch run --source-provider web --query "test"` 行为与 002 基线一致（expect `provider_not_configured` 或成功 run），不受 LLM 配置影响
  - DoD: live provider path 不因 LLM mode 环境变量存在而改变行为
  - Tests: `python3 -m pytest tests/integration/test_run_web_provider.py tests/integration/test_web_unconfigured_failure.py -v`
  - Related files: N/A（验证任务）

### 8.2 Documentation

- [ ] T032 [P2] 更新 `.env.example` — 添加 LLM 配置项：`TRACERESEARCH_LLM_PROVIDER`、`TRACERESEARCH_LLM_API_KEY`、`TRACERESEARCH_LLM_MODEL`、`TRACERESEARCH_WRITER_MODE`、`TRACERESEARCH_VERIFIER_MODE`，均使用占位符
  - DoD: `.env.example` 包含 LLM 配置 section，无真实 key
  - Tests: `grep -c "TRACERESEARCH_LLM" .env.example` 返回 >= 3
  - Related files: `.env.example`

- [ ] T033 [P2] 更新 `README.md` — 添加 LLM Mode 使用说明：
  - 配置 LLM provider 的方式（环境变量）
  - `--writer-mode` / `--verifier-mode` 用法
  - LLM smoke eval 触发方式
  - Fallback 行为说明
  - 与 001/002 的关系（正交）
  - DoD: README 中可找到 "LLM Mode" 或等价 section
  - Tests: `grep -i "llm" README.md | head -5`
  - Related files: `README.md`

### 8.3 Eval & Review Artifacts

- [ ] T034 [P1] 撰写 `eval.md` —— 记录 LLM smoke eval 结果（如无 LLM key 则记录未执行原因和手动验收命令）
  - DoD: `eval.md` 包含至少 1 条 smoke eval 记录或 skip reason
  - Tests: `cat specs/003-llm-backed-writer-verifier/eval.md`
  - Related files: `specs/003-llm-backed-writer-verifier/eval.md`

- [ ] T035 [P1] 撰写 `review.md` —— 对照 spec.md 的 Success Criteria 和 Quality Gates 逐项检查，记录 review decision 和 next_phase
  - DoD: `review.md` 包含 decision + next_phase
  - Tests: `cat specs/003-llm-backed-writer-verifier/review.md`
  - Related files: `specs/003-llm-backed-writer-verifier/review.md`

---

## Dependency Graph

```
Phase 1 (T001-T008) [Foundational — LLM Provider]
    │
    ├──► Phase 2 (T009-T013) [Writer/Verifier Protocols]
    │        │
    │        ├──► Phase 3 (T014-T015) [LLM Verifier — US2]
    │        │        │
    │        │        └──► Phase 5 (T018-T022) [Harness + CLI — US1,US2,US3]
    │        │                 │
    │        ├──► Phase 4 (T016-T017) [LLM Writer — US1]  ──┘
    │        │                                            │
    │        └──► Phase 6 (T023-T025) [Trace — US3] ──────┘
    │                                                     │
    └─────────────────────────────────────────────────────┘
                                                          │
                                              Phase 7 (T026-T029) [Smoke Eval — US4]
                                                          │
                                              Phase 8 (T030-T035) [Regression + Docs]
```

**关键依赖**：
- Phase 3 和 Phase 4 依赖 Phase 2（协议定义）
- Phase 5 依赖 Phase 3 + Phase 4（LLM 实现）
- Phase 6 依赖 Phase 5（Trace 记录）
- Phase 7 依赖 Phase 5（smoke eval 需要 Harness 集成）
- Phase 8 依赖所有前序 Phase

## Parallel Execution

| 并行组 | 任务 | 条件 |
|--------|------|------|
| A | T002, T003 | 依赖 T001 |
| B | T005, T007 | 依赖 T004, T002 |
| C | T009, T011 | 依赖 T010 已定义（可同时） |
| D | T014, T016 | 依赖 Phase 2, 无互相依赖 |
| E | T018, T023 | 各自独立 |
| F | T026, T028 | 依赖 Phase 5 |

## Implementation Strategy

### MVP Scope (最小可演示)

Phase 1 → Phase 2 → Phase 4 **only** (LLM Writer) → Phase 5 (CLI) → Phase 8 (verification)

完成后即可以 `traceresearch run --writer-mode llm` 运行 fixture evidence 并生成 LLM-backed report。

### Full Delivery

全部 Phase 1-8，完成后 LLM Writer + LLM Verifier + CLI mode selection + Trace + smoke eval 全部就绪。

### Quick Wins

- Phase 1 完成后可 import LLM module 并验证 config 读取
- Phase 2 完成后可确认 protocol design 正确性
- Phase 3+4 完成后可手动 mock smoke

---

## Task Summary

| Phase | Tasks | Priority | Story |
|-------|-------|----------|-------|
| 1: LLM Foundation | T001-T008 (8) | P0 | — |
| 2: Protocols | T009-T013 (5) | P1 | — |
| 3: LLM Verifier | T014-T015 (2) | P1 | US2 |
| 4: LLM Writer | T016-T017 (2) | P1 | US1 |
| 5: Harness + CLI | T018-T022 (5) | P1 | US1,US2,US3 |
| 6: Trace | T023-T025 (3) | P1 | US3 |
| 7: Smoke Eval | T026-T029 (4) | P2 | US4 |
| 8: Regression + Docs | T030-T035 (6) | P0/P1/P2 | US3,US4 |
| **Total** | **35 tasks** | | |

| Story | Tasks | Independent Test |
|-------|-------|-----------------|
| US1: LLM Writer | T016-T017 | Mock LLM + fixture evidence → FinalReport with evidence IDs |
| US2: LLM Verifier | T014-T015 | Mixed claims → support_status classification accuracy |
| US3: Fallback stability | T022, T023-T025, T030-T031 | `python3 -m pytest` 100% pass, fixture eval 5/5 |
| US4: Manual smoke eval | T026-T029 | `traceresearch llm-smoke` 输出 metrics |
