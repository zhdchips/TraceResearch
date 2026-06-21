# Data Model: LLM-Backed Writer / Verifier

> Language Policy: English headings, Chinese explanatory body, English AI/Agent terms, and English machine-readable keys.

**Feature**: 003-llm-backed-writer-verifier
**Created**: 2026-06-21

## Entity Overview

本次 feature 引入的新实体全部围绕 LLM 配置、输出 schema 和 failover trace：

```
┌─────────────────────────────────────────────────────────────┐
│                     LLM 配置层                               │
│  LLMProviderConfig ──► DeepSeekProvider                     │
│  LLMWriterConfig                                           │
│  LLMVerifierConfig                                          │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                     LLM 输出 Schema 层                       │
│  LLMFinalReportSchema    (Writer output)                    │
│  LLMFindingSchema        (single finding)                   │
│  LLMVerificationResultSchema  (Verifier output)             │
│  LLMClaimJudgmentSchema  (single claim judgment)            │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                     Trace 扩展                               │
│  TraceEvent 新增字段: llm_mode, llm_model,                  │
│  llm_token_usage, failover_reason                           │
└─────────────────────────────────────────────────────────────┘
```

---

## New Entities

### LLMProviderConfig

LLM provider 的配置实体，从环境变量读取。

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `provider` | `str` | ✅ | provider 名称: `"deepseek"`, `"openai"`, `"anthropic"` |
| `api_key` | `str` | ✅ | API key（从环境变量读取，不写文件） |
| `model` | `str` | ✅ | model ID: `"deepseek-chat"`, `"gpt-4o"` |
| `base_url` | `str` | ✅ | API endpoint URL |
| `timeout_seconds` | `float` | ❌ (default: 60.0) | HTTP 请求超时 |
| `max_tokens` | `int` | ❌ (default: 4096) | max completion tokens |
| `temperature` | `float` | ❌ (default: 0.0) | 确定性优先 |

**环境变量映射**:

| Config Field | Env Var (优先级 1) | Fallback Env Var |
|-------------|---------------------|------------------|
| `provider` | `TRACERESEARCH_LLM_PROVIDER` | `"deepseek"` (default) |
| `api_key` | `TRACERESEARCH_LLM_API_KEY` | `DEEPSEEK_API_KEY` |
| `model` | `TRACERESEARCH_LLM_MODEL` | `"deepseek-chat"` |
| `base_url` | `TRACERESEARCH_LLM_BASE_URL` | `"https://api.deepseek.com"` |

**Validation**:
- `api_key` 非空，否则标记为 `unconfigured`
- `base_url` 必须是 valid URL
- `timeout_seconds` > 0

---

### LLMWriterConfig

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mode` | `str` | ✅ | `"deterministic"` \| `"llm"` |
| `fallback_on_failure` | `bool` | ❌ (default: True) | LLM 失败时是否 fallback |
| `max_evidence_items` | `int` | ❌ (default: 10) | 截断阈值 |

---

### LLMVerifierConfig

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mode` | `str` | ✅ | `"deterministic"` \| `"llm"` |
| `fallback_on_failure` | `bool` | ❌ (default: True) | LLM 失败时是否 fallback |
| `confidence_threshold` | `float` | ❌ (default: 0.5) | WEAKLY_SUPPORTED 判定阈值 |

---

## LLM Output Schemas

### LLMFinalReportSchema

Writer LLM 的输出必须符合此 schema：

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `executive_summary` | `str` | ✅ | 总结性概述 |
| `findings` | `list[LLMFinding]` | ✅ | 研究发现列表 |
| `limitations` | `list[str]` | ✅ | 已知局限 |
| `evidence_references` | `list[str]` | ✅ | 格式: `"EVID-xxx: title"` |
| `follow_up_questions` | `list[str]` | ✅ | 后续研究问题 |

### LLMFindingSchema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | `str` | ✅ | finding 文本 |
| `evidence_ids` | `list[str]` | ✅ | 必须引用输入中的 evidence ID，非空 |
| `confidence` | `str` | ✅ | `"high"` \| `"medium"` \| `"low"` |

**Validation**:
- `evidence_ids` 中每个 ID 必须在输入的 evidence set 中存在
- `confidence` 只能是 3 个枚举值之一

---

### LLMVerificationResultSchema

Verifier LLM 的输出必须符合此 schema：

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `claim_results` | `list[LLMClaimJudgment]` | ✅ | 每个 claim 的判断 |
| `overall_notes` | `list[str]` | ✅ | 整体观察 |

### LLMClaimJudgmentSchema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `claim_id` | `str` | ✅ | 必须与输入的 claim ID 一一对应 |
| `support_status` | `str` | ✅ | `"supported"` \| `"weakly_supported"` \| `"unsupported"` \| `"conflicting"` |
| `reasoning` | `str` | ✅ | 判断依据 |

**Validation**:
- claim_results 中的 `claim_id` 集合必须与输入 claims 的 `claim_id` 集合一致（无遗漏、无多余）

---

## Trace 扩展

### TraceEvent 新增字段

现有 `TraceEvent` model 新增 4 个可选字段（向后兼容）：

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `llm_mode` | `str \| None` | ❌ | `"llm"` \| `"deterministic"` \| `None` (non-LLM events) |
| `llm_model` | `str \| None` | ❌ | e.g. `"deepseek-chat"` |
| `llm_token_usage` | `TokenUsage \| None` | ❌ | reuse existing `TokenUsage` model |
| `failover_reason` | `str \| None` | ❌ | `"timeout"` \| `"invalid_response"` \| `"rate_limit"` \| `"no_api_key"` \| `"schema_mismatch"` |

> 所有新字段都是 `None`-able，确保现有 Trace 写入和读取代码零破坏。

---

## 关系图

```
LLMProviderConfig ──configures──► DeepSeekProvider ──implements──► LLMProvider (ABC)
                                                                      │
                                              ┌───────────────────────┤
                                              ▼                       ▼
                                        LLMWriter              LLMVerifier
                                           │                       │
                                      implements              implements
                                           │                       │
                                           ▼                       ▼
                                     WriterProtocol         VerifierProtocol
                                           │                       │
                              ┌────────────┼───────┐               │
                              ▼            ▼       ▼               ▼
                           Writer      LLMWriter  Writer      LLMVerifier
                       (deterministic)          (deterministic)

LLMFinalReportSchema  ◄── LLMWriter 解析 LLM 输出
LLMVerificationResultSchema ◄── LLMVerifier 解析 LLM 输出

TraceEvent.llm_mode / .llm_model / .llm_token_usage / .failover_reason
    ◄── LLMWriter / LLMVerifier 写入 Trace
```
