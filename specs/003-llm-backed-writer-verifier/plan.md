# Implementation Plan: LLM-Backed Writer / Verifier

> Language Policy: English headings, Chinese explanatory body, English AI/Agent terms, and English machine-readable keys.

**Created**: 2026-06-21
**Spec**: [spec.md](./spec.md)
**Branch**: `003-llm-backed-writer-verifier`

## Architecture

### 整体架构变化

001/002 的 Agent 序列保持不变，本次变更集中在两个 Agent slots（Writer / Verifier）的内部实现抽象化：

```
                          ┌──────────────────────────────┐
                          │     ResearchHarness          │
                          │  (DI: WriterProtocol,        │
                          │        VerifierProtocol)     │
                          └──────────┬───────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
     ┌────────▼────────┐   ┌────────▼────────┐   ┌─────────▼─────────┐
     │ Deterministic   │   │  LLM Writer     │   │  LLM Verifier     │
     │ Writer/Verifier │   │  ┌──────────┐   │   │  ┌──────────┐    │
     │ (kept as        │   │  │ LLMProv  │   │   │  │ LLMProv  │    │
     │  fallback)      │   │  │ ider     │   │   │  │ ider     │    │
     └─────────────────┘   │  └────┬─────┘   │   │  └────┬─────┘    │
                           │       │         │   │       │          │
                           │  ┌────▼─────┐   │   │  ┌────▼─────┐    │
                           │  │DeepSeek  │   │   │  │DeepSeek  │    │
                           │  │Provider  │   │   │  │Provider  │    │
                           │  └──────────┘   │   │  └──────────┘    │
                           └─────────────────┘   └──────────────────┘
```

**核心原则**：

- Harness 只依赖 `WriterProtocol` / `VerifierProtocol`，不感知 LLM。
- LLM 组件只依赖 `LLMProvider` protocol，不感知具体 provider（DeepSeek / OpenAI / Anthropic）。
- Deterministic 实现与 LLM 实现是同一 protocol 的两个独立实现，可通过配置互换。
- LLM 调用失败 → 自动 fallback 到 deterministic 实现。

### 模块结构

```
traceresearch/
├── llm/                          # NEW: LLM provider abstraction
│   ├── __init__.py
│   ├── provider.py               # LLMProvider protocol + LLMProviderConfig
│   ├── deepseek_provider.py      # DeepSeek OpenAI-compatible impl
│   └── schemas.py                # LLM output Pydantic schemas
├── agents/
│   ├── __init__.py
│   ├── writer_protocol.py        # WriterProtocol (ABC)
│   ├── verifier_protocol.py      # VerifierProtocol (ABC)
│   ├── writer.py                 # DeterministicWriter (implements WriterProtocol)
│   ├── verifier.py               # DeterministicVerifier (implements VerifierProtocol)
│   ├── llm_writer.py             # NEW: LLMWriter (implements WriterProtocol)
│   └── llm_verifier.py           # NEW: LLMVerifier (implements VerifierProtocol)
├── harness/
│   ├── orchestrator.py           # UPDATED: factory for Writer/Verifier mode selection
│   └── ...
├── trace/
│   ├── models.py                 # UPDATED: add failover event fields
│   └── ...
└── cli.py                        # UPDATED: add --writer-mode, --verifier-mode
```

### 向后兼容设计

- `DeterministicWriter` 和 `DeterministicVerifier` 保持现有类名 `Writer` 和 `Verifier` 作为 public API alias（向后兼容）。
- Harness 构造函数仍接受 `writer=` 和 `verifier=` 可选参数，默认为 deterministic 实现。
- 无 LLM 配置时，系统行为与 002 完全一致。

## Agent Roles

| Role | Responsibility | Inputs | Outputs | Mode |
| --- | --- | --- | --- | --- |
| Planner | 任务拆解与研究维度规划 | user query | research_brief, research_tasks | deterministic (unchanged) |
| Researcher | 多角度检索与资料摘要 | research task, provider | evidence candidates | deterministic / live (unchanged) |
| **Verifier** | **证据质量和 claim 支撑检查** | **verified evidence, draft claims** | **verification result** | **deterministic \| LLM** |
| Critic | 缺失视角、风险、反例检查 | draft report, evidence, verification | critique | deterministic (unchanged) |
| **Writer** | **基于 evidence 生成报告** | **verified evidence, brief, verification** | **draft report, final report** | **deterministic \| LLM** |

> P1: Planner / Researcher / Critic 不受本次变更影响，保持 001/002 行为不变。

## Data Flow

### LLM-backed Write Path

```
ResearchBrief + VerifiedEvidence
    │
    ├──[Writer mode == "llm"]──► LLMWriter._build_prompt()
    │                                │
    │                                ▼
    │                           LLMProvider.complete(prompt, schema=FinalReportSchema)
    │                                │
    │                           ┌────┴──────────────────┐
    │                           ▼                       ▼
    │                      success                  failure
    │                           │                       │
    │                           ▼                       ▼
    │                    parse & validate         fallback → DeterministicWriter.final()
    │                    Pydantic schema                │
    │                           │                       │
    │                           ▼                       ▼
    │                      FinalReport             FinalReport
    │                           │                 (with failover Trace)
    │                           ▼
    │                      Trace: llm_mode, model, token_usage, latency
```

### LLM-backed Verify Path

```
DraftReport.claims + Evidence[]
    │
    ├──[Verifier mode == "llm"]──► LLMVerifier._build_prompt()
    │                                    │
    │                                    ▼
    │                               LLMProvider.complete(prompt, schema=VerificationResultSchema)
    │                                    │
    │                               ┌────┴──────────────────┐
    │                               ▼                       ▼
    │                          success                  failure
    │                               │                       │
    │                               ▼                       ▼
    │                    parse & validate             fallback → DeterministicVerifier.verify()
    │                    - claim_ids match?                 │
    │                    - support_status valid?            │
    │                               │                       │
    │                               ▼                       ▼
    │                          VerificationResult     VerificationResult
    │                                                   (with failover Trace)
```

## LLM Provider Design

### LLMProvider Protocol

```python
class LLMProvider(ABC):
    """与具体 LLM vendor 解耦的 provider abstraction。"""

    @abstractmethod
    def complete(
        self,
        prompt: str,
        response_schema: type[BaseModel],
        system_prompt: str | None = None,
    ) -> BaseModel:
        """调用 LLM 并返回 schema-validated response。
        
        Raises:
            LLMProviderError: 调用失败或 response 不符合 schema 时
        """
```

### LLMProviderConfig

```python
@dataclass
class LLMProviderConfig:
    provider: str                    # "deepseek" | "openai" | "anthropic"
    api_key: str                    # 从环境变量读取
    model: str                      # "deepseek-chat" | "gpt-4o" | ...
    base_url: str                   # API endpoint
    timeout_seconds: float = 60.0
    max_tokens: int = 4096
    temperature: float = 0.0        # 确定性优先
```

### Provider 选择决策

**第一版选择 DeepSeek**（`deepseek-chat` model）：

| 因素 | 评估 |
|------|------|
| API key 可用性 | ✅ `/Users/zhdchips/.hermes` 中已有 `DEEPSEEK_API_KEY`，本地环境直接可用 |
| API 兼容性 | ✅ OpenAI-compatible (`/v1/chat/completions`)，标准 REST API |
| 依赖性 | ✅ 用 `httpx` 直接 HTTP 调用，无需引入 `openai` / `anthropic` SDK |
| 成本 | ✅ 极低成本，适合开发迭代 |
| provider 可换 | ✅ `LLMProvider` protocol 让后续换 Anthropic/OpenAI 只需新加一个实现类 |

### 配置读取

1. `LLMProviderConfig` 从环境变量读取：`TRACERESEARCH_LLM_PROVIDER`、`TRACERESEARCH_LLM_API_KEY`、`TRACERESEARCH_LLM_MODEL` 等
2. 同时支持从 `DEEPSEEK_API_KEY` 等 provider-specific 环境变量读取（兼容 Hermes）
3. 如果 API key 缺失 → `LLMProvider` 构建失败 → Harness 自动使用 deterministic mode

## Writer / Verifier Protocol Design

### WriterProtocol

```python
class WriterProtocol(ABC):
    @abstractmethod
    def draft(self, *, brief: ResearchBrief, evidence: list[Evidence]) -> DraftReport:
        ...

    @abstractmethod
    def final(
        self,
        *,
        brief: ResearchBrief,
        verified_evidence: list[Evidence],
        verification: VerificationResult,
        critique: CritiqueResult,
    ) -> FinalReport:
        ...
```

### VerifierProtocol

```python
class VerifierProtocol(ABC):
    @abstractmethod
    def verify(
        self, *, run_id: str, draft: DraftReport, evidence: list[Evidence]
    ) -> VerificationResult:
        ...
```

### 实现类命名

| Protocol | Deterministic 实现 | LLM-backed 实现 |
|----------|-------------------|-----------------|
| `WriterProtocol` | `Writer`（保留原名，向后兼容） | `LLMWriter` |
| `VerifierProtocol` | `Verifier`（保留原名，向后兼容） | `LLMVerifier` |

- 现有 `Writer` 类保持 class name 不变（既是 protocol 的 deterministic 实现，也作为向后兼容的 public name）。
- `Writer` 在 module level aliased 为 `DeterministicWriter` 以提高可读性。
- `LLMWriter` / `LLMVerifier` 在构造函数中接收 `LLMProvider` 实例。

## LLM Output Schema Design

### Writer LLM Prompt 输出 Schema

```python
class LLMFinalReportSchema(BaseModel):
    """LLM Writer 必须返回的结构。"""
    executive_summary: str = Field(min_length=1)
    findings: list[LLMFindingSchema]
    limitations: list[str]
    evidence_references: list[str]   # "EVID-001: Source Title"
    follow_up_questions: list[str]

class LLMFindingSchema(BaseModel):
    text: str = Field(min_length=1)
    evidence_ids: list[str]          # 必须引用输入 evidence 中的 ID
    confidence: str                  # "high" | "medium" | "low"
```

### Verifier LLM Prompt 输出 Schema

```python
class LLMVerificationResultSchema(BaseModel):
    claim_results: list[LLMClaimJudgmentSchema]
    overall_notes: list[str]

class LLMClaimJudgmentSchema(BaseModel):
    claim_id: str                    # 必须与输入的 claim ID 匹配
    support_status: str              # "supported" | "weakly_supported" | "unsupported" | "conflicting"
    reasoning: str = Field(min_length=1)
```

### Schema Validation 策略

1. LLM 返回 raw JSON → `model_validate_json()` 解析
2. 解析成功 → 额外验证：
   - `claim_ids` 匹配输入（Verifier）
   - `evidence_ids` 来自输入 evidence set（Writer）
   - 所有 required fields 非空
3. 解析失败或 post-validation 失败 → **fallback to deterministic**，Trace 记录 `invalid_llm_response`

## Trace Design

### 新增 Trace 字段

扩展现有 `TraceEvent`，兼容现有字段：

```python
# 新增可选字段（向后兼容）
class TraceEvent(TraceModel):
    # ... existing fields ...
    llm_mode: str | None = None            # "llm" | "deterministic"
    llm_model: str | None = None           # "deepseek-chat" 
    llm_token_usage: TokenUsage | None = None  # reuse existing TokenUsage
    failover_reason: str | None = None     # "timeout" | "invalid_response" | "rate_limit" | "provider_error"
```

### LLM Trace 事件链

一次 LLM-backed Writer/Verifier 调用产生以下 Trace：

```
trace_id=TR-{run_id}-{seq}  agent_role=WRITER  event_type=START
  input_summary="LLM Writer drafting from N evidence items"
  llm_mode="llm"  llm_model="deepseek-chat"

trace_id=TR-{run_id}-{seq+1}  agent_role=WRITER  event_type=TOOL_CALL
  tool_name="llm.complete"
  input_summary="prompt summary (不含完整 prompt)"

trace_id=TR-{run_id}-{seq+2}  agent_role=WRITER  event_type=TOOL_RESULT
  tool_name="llm.complete"
  output_summary="generated M findings, N limitations"
  llm_token_usage={...}  latency_ms=...

# 失败时:
trace_id=TR-{run_id}-{seq+3}  agent_role=WRITER  event_type=WARNING
  output_summary="LLM call failed: timeout after 60s"
  failover_reason="timeout"
  # 然后继续 deterministic Writer 的 Trace
```

## Eval Harness Design

### LLM Smoke Eval（manual only, non-CI）

**Command**:
```bash
python3 -m traceresearch.eval.llm_smoke --cases-dir eval/llm_smoke_cases
```

或者 CLI 入口：
```bash
traceresearch llm-smoke
```

**Eval case 设计**（2-3 cases，使用 fixture evidence 作为输入）:

| Case ID | 目的 | 输入 |
|---------|------|------|
| `llm-smoke-writer` | 验证 LLM Writer 输出质量 | fixture case `case-001` 的 verified evidence |
| `llm-smoke-verifier` | 验证 LLM Verifier 判断准确率 | 混合 correctly-supported / weakly-supported / unsupported claims |
| `llm-smoke-failover` | 验证 LLM 失败时 fallback | mock LLM 返回 invalid JSON / timeout |

**Metrics**:
- `faithfulness`: LLM Writer 的 key claims 是否全有 evidence ID 支撑
- `citation_completeness`: evidence reference 是否完整
- `unsupported_claim_count`: LLM Verifier 是否捕捉到 unsupported claims
- `failover_success`: 模拟失败时是否正确 fallback

**隔离保证**:
- LLM smoke eval tests 放在 `tests/llm_smoke/` 目录
- 使用 `pytest.mark.llm_smoke` marker
- 默认 `python3 -m pytest` 排除 `llm_smoke` marker（在 `pyproject.toml` 中配置 `addopts = "-m 'not llm_smoke'"`）
- LLM smoke eval 只通过 `traceresearch llm-smoke` 手动触发

### Fixture Eval（regression gate）

001 的 fixture eval 完全不变：
```bash
python3 -m pytest                    # 100% pass
traceresearch eval                   # 5/5 pass, Output Determinism=1.0
```

## Technical Decisions

- **TD-001: 第一版 LLM Provider 选择 DeepSeek**
  - 原因：Hermes 已有 API key，OpenAI 兼容 API，成本低
  - 替代方案：MiniMax Anthropic 兼容端点（次选），OpenAI（需额外 key）
  - 扩展性：`LLMProvider` protocol 保证后续换 provider 只加一个类

- **TD-002: 使用 httpx 而非 openai SDK**
  - 原因：DeepSeek API 是简单的 OpenAI-compatible REST API，不需要 SDK 重量级依赖。直接 HTTP call + Pydantic schema validation 更轻量、更可审计
  - 替代方案：`openai` Python SDK with `base_url=https://api.deepseek.com`（更成熟，但增加依赖）
  - 决策：先用 `httpx`，如需 streaming / 复杂 retry 再考虑 SDK

- **TD-003: Python ABC 而非 typing.Protocol**
  - 原因：ABC 支持 `isinstance` 检查、有清晰继承关系、与现有 DI 模式一致。`typing.Protocol` 是 structural subtyping，不需要显式继承，但不适合需要 `isinstance` 检查的场景
  - 替代方案：`typing.Protocol`（更轻量，但缺少运行时检查）

- **TD-004: Pydantic schema validation 作为 LLM output gate**
  - 原因：LLM 输出不可靠，必须在进入系统前做严格 schema validation
  - `BaseModel.model_validate_json()` 保证字段类型正确、required fields 齐全
  - Post-validation 检查 evidence ID / claim ID 一致性
  - 任何验证失败 → fallback deterministic

- **TD-005: 环境变量配置优先于 CLI flag**
  - 原因：与 002 的 `DEEPSEEK_API_KEY` / `.env` 模式一致，避免 CLI 泄露 key
  - CLI 提供 `--writer-mode` / `--verifier-mode` 覆盖（仅接受 "deterministic" | "llm"）
  - 无 LLM key 时 `--writer-mode llm` 自动 fallback 并输出 warning

- **TD-006: Writer 改名策略**
  - 保留现有 `Writer` 类名作为 deterministic 实现，不强制 rename
  - Module 级别添加 `DeterministicWriter = Writer` alias
  - 新增 `LLMWriter` 类
  - 原因：最小化对 001/002 代码的破坏，保持 git blame 清晰

## Failure Handling

| 场景 | 行为 | Trace 记录 |
|------|------|-----------|
| LLM API key 未配置 | 默认使用 deterministic，run 正常进行 | N/A（不进入 LLM path） |
| LLM API key 未配置但 mode="llm" 指定 | 输出 warning，fallback deterministic | `failover_reason="no_api_key"`, `status=WARNING` |
| LLM timeout (>60s) | fallback deterministic | `failover_reason="timeout"`, `llm_model`, `latency_ms` |
| LLM rate limit | fallback deterministic | `failover_reason="rate_limit"` |
| LLM 返回 invalid JSON (parse error) | fallback deterministic | `failover_reason="invalid_response"`, output_summary 含 error |
| LLM 返回 valid JSON 但 claim_ids 不匹配 | fallback deterministic | `failover_reason="schema_mismatch"` |
| LLM 返回 evidence_ids 不在输入集合中 | fallback deterministic (Writer) / 标记为 unsupported (Verifier) | `failover_reason="invalid_evidence_ref"` |
| Evidence 超过 context window | 截断到 top-N（按 relevance score），Trace 记录截断信息 | `output_summary="truncated N evidence items to top K"` |

**关键规则**：任一 LLM 失败 → 整个 run **不 fail**，而是以 deterministic fallback 完成。Run 仍标记为 `COMPLETED`，但 Trace 包含 failover WARNING。

## Test Strategy

### Unit Tests（`tests/unit/`）

| 测试 | 内容 | LLM 依赖 |
|------|------|----------|
| `test_writer_protocol.py` | `Writer` / `LLMWriter` 都满足 `WriterProtocol` | Mock LLM |
| `test_verifier_protocol.py` | `Verifier` / `LLMVerifier` 都满足 `VerifierProtocol` | Mock LLM |
| `test_llm_writer_schema.py` | LLMWriter prompt 构建、schema 解析、evidence ID 验证 | Mock LLM |
| `test_llm_verifier_schema.py` | LLMVerifier prompt 构建、schema 解析、claim ID 匹配 | Mock LLM |
| `test_deepseek_provider.py` | DeepSeekProvider 的 HTTP request 构建、response 解析 | Mock HTTP |
| `test_failover.py` | LLM 各种失败 → fallback deterministic | Mock LLM |
| `test_mode_selection.py` | 环境变量/CLI mode selection 逻辑 | 无 |

### Integration Tests（`tests/integration/`）

| 测试 | 内容 |
|------|------|
| `test_llm_writer_e2e.py` | Mock LLM + fixture evidence → 完整 harness run，检查 artifact |
| `test_llm_verifier_e2e.py` | Mock LLM + fixture claims → 完整 verification flow |
| `test_deterministic_regression.py` | 无 LLM 配置时，所有现有 tests 100% pass |

### LLM Smoke Eval（`tests/llm_smoke/`）

| 测试 | marker |
|------|--------|
| `test_llm_writer_smoke.py` | `@pytest.mark.llm_smoke` |
| `test_llm_verifier_smoke.py` | `@pytest.mark.llm_smoke` |
| `test_llm_failover_smoke.py` | `@pytest.mark.llm_smoke` |

### 回归保证

- `python3 -m pytest`（默认，排除 `llm_smoke`）→ 100% pass
- `traceresearch eval`（fixture eval）→ 5/5 pass, Output Determinism=1.0
- `traceresearch run --source-provider web --query "..."`（live web path）→ 不受影响

## Implementation Phases

### Phase 1: Foundation — LLM Provider Abstraction

1. 创建 `traceresearch/llm/` 模块
2. 实现 `LLMProviderConfig`（从环境变量读取）
3. 实现 `LLMProvider` ABC + `LLMProviderError`
4. 实现 `DeepSeekProvider`（httpx → `/v1/chat/completions`）
5. 添加 `httpx` 依赖到 `pyproject.toml`
6. Unit tests for provider

### Phase 2: Writer / Verifier Protocols

1. 定义 `WriterProtocol` + `VerifierProtocol` ABCs
2. 更新现有 `Writer` / `Verifier` 类，确认满足 protocol（无需代码修改）
3. 添加 `DeterministicWriter = Writer`, `DeterministicVerifier = Verifier` aliases
4. Protocol unit tests

### Phase 3: LLM Writer + LLM Verifier

1. 实现 `LLMWriter`（prompt 构建 + schema validation + fallback）
2. 实现 `LLMVerifier`（prompt 构建 + claim-level judgment + fallback）
3. LLM output Pydantic schemas in `llm/schemas.py`
4. Unit tests with mock LLM

### Phase 4: Harness Integration

1. Harness mode selection factory（环境变量 + CLI flags → Writer/Verifier 实例）
2. CLI 新增 `--writer-mode` / `--verifier-mode`
3. Trace 扩展（`llm_mode`, `llm_model`, `llm_token_usage`, `failover_reason`）
4. Integration tests（mock LLM + fixture evidence）

### Phase 5: LLM Smoke Eval

1. 创建 `tests/llm_smoke/` 目录 + `pytest.mark.llm_smoke`
2. `pyproject.toml` 配置 `addopts = "-m 'not llm_smoke'"`
3. 实现 LLM smoke eval runner
4. 手动 smoke test with real DeepSeek API

### Phase 6: Documentation & Cleanup

1. 更新 `.env.example`（LLM 配置项）
2. 更新 `README.md`（LLM mode 使用方法）
3. 验证全部回归 tests pass

## Risks

- **Risk-001: DeepSeek API 响应格式变化**
  - Mitigation: schema validation + fallback 机制；provider-specific 逻辑封装在 `DeepSeekProvider` 中，易于修复

- **Risk-002: LLM prompt engineering 不够成熟导致输出质量差**
  - Mitigation: 第一版对 prompt 持务实态度，通过 fixture smoke eval 对比 deterministic vs LLM 输出；prompt 改进作为后续 feature

- **Risk-003: `httpx` 依赖引入可能与其他依赖冲突**
  - Mitigation: `httpx` 是纯 Python 库，依赖少，与现有依赖（pydantic, typer）无已知冲突

- **Risk-004: Protocol 抽象引入可能使代码路径变复杂**
  - Mitigation: Harness 现有 DI 模式天然支持；保持 protocol 方法签名与现有 `Writer`/`Verifier` 方法签名一致

- **Risk-005: Context window overflow when evidence count is high**
  - Mitigation: FR-015 要求截断处理；第一期 evidence count 通常 5-10 条，在 DeepSeek 64K context window 安全范围内

## Complexity Tracking

本 feature 不违反 Constitution 的 Operational Constraints：
- 不新增 Agent role
- 不引入 Web UI / memory / sandbox / plugins / multi-user / pdf / benchmark
- Writer / Verifier protocol 仅定义 2-3 个方法，保持简单
- LLM Provider protocol 仅定义 1 个方法 `complete()`

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Research Contract First | ✅ PASS | brief 生成不受 LLM 影响 |
| II. Evidence-Grounded Output | ✅ PASS | LLM Writer 只能使用 verified evidence；输出每个 key claim 绑定 evidence ID |
| III. Traceable Agent Execution | ✅ PASS | LLM 调用记录完整 Trace（mode, model, token_usage, failover_reason） |
| IV. Context Isolation and Compression | ✅ PASS | LLM Writer prompt 只含 evidence summary，不含 raw source |
| V. Eval-Gated Iteration | ✅ PASS | Fixture eval 保持 5/5；LLM smoke eval 作为 manual gate |
