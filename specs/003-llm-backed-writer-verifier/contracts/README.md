# Interface Contracts: LLM-Backed Writer / Verifier

> Language Policy: English headings, Chinese explanatory body, English AI/Agent terms, and English machine-readable keys.

**Feature**: 003-llm-backed-writer-verifier
**Created**: 2026-06-21

本文件定义本次 feature 引入的 3 个 public interface contracts。所有实现（deterministic / LLM-backed）必须满足这些 contracts。

---

## Contract 1: WriterProtocol

### Purpose

定义 Writer 角色的行为边界：接收 evidence 并生成 draft / final report。

### Signature

```python
from abc import ABC, abstractmethod
from traceresearch.evidence.models import (
    ResearchBrief, Evidence, VerificationResult, CritiqueResult
)
from traceresearch.agents.writer import DraftReport, FinalReport


class WriterProtocol(ABC):
    """Writer protocol — deterministic and LLM-backed implementations MUST satisfy this."""

    @abstractmethod
    def draft(self, *, brief: ResearchBrief, evidence: list[Evidence]) -> DraftReport:
        """Generate outline and draft claims from evidence.
        
        Preconditions:
          - brief: 已完成 planning 的 research_brief（不含 open_clarifications）
          - evidence: Researcher 产出的 evidence candidates 列表
        
        Postconditions:
          - 返回的 DraftReport 包含 outline_markdown 和 claims
          - 每个 claim 绑定至少一个 evidence_id
        """
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
        """Generate final report from verified evidence.
        
        Preconditions:
          - verified_evidence: 经过 Verifier 标记为 VERIFIED 的 evidence
          - verification: Verifier 的完整输出（含每个 claim 的 support status）
          - critique: Critic 的完整输出（含 missing perspectives, limitations）
        
        Postconditions:
          - FinalReport.markdown 包含所有标准 sections（executive summary, findings, limitations, evidence refs, follow-ups）
          - FinalReport.report_json 包含 structured data
          - 每个 key claim 绑定 evidence_id 或被标记为 limitation
          - 不得编造 evidence 中不存在的 claim
        """
        ...
```

### Implementations

| Implementation | Class | Notes |
|---------------|-------|-------|
| Deterministic | `Writer` | 001 MVP 模板拼接实现，保持原名 |
| LLM-backed | `LLMWriter` | 新增，依赖 `LLMProvider` |

### Error Handling

- Deterministic Writer: 不抛异常（纯数据转换）
- LLM Writer: 调用失败时 fallback 到 `Writer.final()`（如果 `fallback_on_failure=True`），否则抛 `LLMProviderError`

---

## Contract 2: VerifierProtocol

### Purpose

定义 Verifier 角色的行为边界：检查 draft claims 是否被 evidence 支撑。

### Signature

```python
from abc import ABC, abstractmethod
from traceresearch.evidence.models import Evidence, VerificationResult
from traceresearch.agents.writer import DraftReport


class VerifierProtocol(ABC):
    """Verifier protocol — deterministic and LLM-backed implementations MUST satisfy this."""

    @abstractmethod
    def verify(
        self, *, run_id: str, draft: DraftReport, evidence: list[Evidence]
    ) -> VerificationResult:
        """Verify draft claims against evidence.
        
        Preconditions:
          - draft: Writer.draft() 的输出，包含 claims 列表
          - evidence: Evidence Store 中的所有 evidence
        
        Postconditions:
          - 返回 VerificationResult，包含每个 claim 的 support status
          - 每个 claim 的 claim_id 与输入一致
          - unsupported_claim_count 正确统计
          - citation_completeness 在 [0.0, 1.0] 范围内
          - supported claim 必须有至少一个 evidence_id
        """
        ...
```

### Implementations

| Implementation | Class | Notes |
|---------------|-------|-------|
| Deterministic | `Verifier` | 001 MVP rule-based 实现（检查 evidence ID 存在性），保持原名 |
| LLM-backed | `LLMVerifier` | 新增，语义级判断 claim-evidence 对齐 |

### Error Handling

- Deterministic Verifier: 不抛异常（纯数据验证）
- LLM Verifier: 调用失败时 fallback 到 `Verifier.verify()`（如果 `fallback_on_failure=True`），否则抛 `LLMProviderError`

---

## Contract 3: LLMProvider

### Purpose

定义 LLM provider 的抽象边界：解耦 Writer/Verifier 与具体 LLM vendor。

### Signature

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel


class LLMProviderError(Exception):
    """LLM provider 调用失败。"""
    def __init__(self, reason: str, provider: str, model: str, latency_ms: float):
        self.reason = reason
        self.provider = provider
        self.model = model
        self.latency_ms = latency_ms
        super().__init__(f"LLM call failed: {reason} ({provider}/{model})")


class LLMProvider(ABC):
    """LLM provider abstraction — vendor-agnostic contract."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """e.g. "deepseek" """
        ...

    @property
    @abstractmethod
    def model(self) -> str:
        """e.g. "deepseek-chat" """
        ...

    @abstractmethod
    def complete(
        self,
        prompt: str,
        response_schema: type[BaseModel],
        system_prompt: str | None = None,
    ) -> BaseModel:
        """Call LLM and return schema-validated response.
        
        Preconditions:
          - prompt: user message content
          - response_schema: Pydantic model class 用于解析 LLM 输出
          - system_prompt (optional): system-level instruction
        
        Postconditions:
          - 返回 response_schema 的实例（已通过 Pydantic 验证）
          - 或抛 LLMProviderError
        
        Implementation requirements:
          - LLM 输出 JSON 必须能被 response_schema.model_validate_json() 解析
          - 解析失败 → LLMProviderError(reason="invalid_response")
          - HTTP timeout → LLMProviderError(reason="timeout")
          - Rate limit → LLMProviderError(reason="rate_limit")
          - 不重试（retry 策略留给 caller）
        """
        ...
```

### Implementations

| Implementation | Provider | API |
|---------------|----------|-----|
| `DeepSeekProvider` | deepseek | `POST https://api.deepseek.com/v1/chat/completions` |

### Error Types

| Reason | 触发条件 |
|--------|---------|
| `"no_api_key"` | API key 为空 |
| `"timeout"` | HTTP 请求超时 |
| `"rate_limit"` | HTTP 429 |
| `"invalid_response"` | JSON parse error 或 schema validation error |
| `"provider_error"` | HTTP 4xx/5xx（非 429） |

---

## Pre/Post Condition Mapping to Spec FRs

| Contract | Pre/Post Condition | Spec FR |
|----------|-------------------|---------|
| WriterProtocol.draft() | claims bind evidence_id | FR-004 |
| WriterProtocol.final() | no fabricated claims | FR-004 |
| VerifierProtocol.verify() | semantic judgment with reasoning | FR-005 |
| LLMProvider.complete() | schema-validated response | FR-006, FR-016 |
| WriterProtocol (all) | swappable deterministic / LLM | FR-001 |
| VerifierProtocol (all) | swappable deterministic / LLM | FR-002 |
