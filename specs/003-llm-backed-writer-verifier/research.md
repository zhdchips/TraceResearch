# Research Notes: LLM-Backed Writer / Verifier

> Language Policy: English headings, Chinese explanatory body, English AI/Agent terms, and English machine-readable keys.

**Feature**: 003-llm-backed-writer-verifier
**Created**: 2026-06-21

## Decision 1: First LLM Provider → DeepSeek

- **Decision**: 选择 DeepSeek (`deepseek-chat`) 作为第一版 LLM provider
- **Rationale**:
  - `/Users/zhdchips/.hermes/auth.json` 中已有 `DEEPSEEK_API_KEY`，本地环境直接可用
  - OpenAI-compatible API (`/v1/chat/completions`)，标准 REST 接口
  - 成本极低，适合开发迭代
  - 64K context window，足够容纳 5-10 条 evidence summaries
- **Alternatives considered**:
  - **MiniMax Anthropic 兼容端点** (`https://api.minimaxi.com/anthropic`): 也有 key，但 Anthropic API schema 与 OpenAI 差异大，不适合第一版快速实现
  - **Anthropic Claude (direct)**: 无本地 key，需要额外配置
  - **OpenAI GPT-4o**: 无本地 key，成本高

## Decision 2: HTTP Client → httpx

- **Decision**: 使用 `httpx` 直接调用 DeepSeek API，不引入 `openai` SDK
- **Rationale**:
  - DeepSeek API 是简单的 chat completions endpoint，不需要 SDK 的 connection pooling / streaming / tool use 等高级功能
  - `httpx` 是轻量级、纯 Python 的 HTTP client
  - 避免 vendor SDK 锁定：换 Anthropic 时只需实现新的 `LLMProvider` 子类
  - `LLMProvider` protocol 保证 vendor logic 不会泄漏到 Writer/Verifier
- **Alternatives considered**:
  - **`openai` Python SDK + `base_url=https://api.deepseek.com`**: 更成熟（内置 retry, error handling），但引入 ~2MB 依赖，且概念上与 "provider abstraction" 矛盾（SDK 本身绑定 OpenAI 生态）
  - **`requests`**: 同步 API 简化初始实现，但缺少 `httpx` 的 async 未来扩展性
  - **`aiohttp`**: 过度设计，本 feature 不需要 async

## Decision 3: Protocol Type → ABC

- **Decision**: 使用 Python `ABC` 定义 `WriterProtocol` / `VerifierProtocol` / `LLMProvider`
- **Rationale**:
  - 支持 `isinstance(x, WriterProtocol)` 运行时检查
  - 与现有 Harness DI 模式一致
  - 显式继承关系，调试时易于追溯
- **Alternatives considered**:
  - **`typing.Protocol`**: 更 Pythonic（structural subtyping），但缺少运行时 `isinstance` 检查，且 Pydantic 的 `validate_call` 对 Protocol 支持不如 ABC
  - **No protocol, duck typing**: 过于隐式，本 feature 要求明确的可互换性

## Decision 4: Writer Class Naming → Keep `Writer` as deterministic

- **Decision**: 保留现有 `Writer` / `Verifier` 类名不变，新增 `LLMWriter` / `LLMVerifier`
- **Rationale**:
  - 最小化对 001/002 代码的破坏
  - 向后兼容：现有 `from traceresearch.agents.writer import Writer` 继续有效
  - Module 级别添加 `DeterministicWriter = Writer` alias 提高可读性
- **Alternatives considered**:
  - **Rename to `DeterministicWriter`, add `Writer` as alias**: 更清晰但破坏现有 import（001/002 代码需修改）
  - **Keep both as aliases to same class**: Python 支持，但增加模块复杂度

## Decision 5: Configuration Loading → env vars + CLI flags (env priority)

- **Decision**: LLM 配置走环境变量，CLI 提供 `--writer-mode` / `--verifier-mode` 覆盖
- **Rationale**:
  - API key 不应出现在 CLI args（安全问题）
  - 与 002 的 credential 配置模式一致（环境变量 + `.env`）
  - CLI flag 只接受 mode 选择（非敏感信息），方便 demo 时切换
- **Alternatives considered**:
  - **YAML config file**: 增加复杂度，当前规模不需要
  - **CLI-only**: API key 暴露在 shell history 中，不安全

## Decision 6: LLM Prompt Language → English

- **Decision**: LLM prompt 使用全英文
- **Rationale**:
  - DeepSeek / 主流 LLM 在英文 prompt 上的 instruction following 质量更好
  - Research report 输出语言跟随 `research_brief.objective` 的语言
  - 与项目 "English AI/Agent terms" 语言策略一致

## Open Questions (resolved)

| Question | Resolution |
|----------|-----------|
| LLM provider 选择 | DeepSeek (`deepseek-chat`) via OpenAI-compatible API |
| Writer/Verifier mode selection mechanism | 环境变量（默认）+ CLI `--writer-mode` / `--verifier-mode`（覆盖） |
| LLM output validation 策略 | Pydantic `model_validate_json()` + post-validate claim/evidence ID consistency |
| Mock LLM 测试策略 | `LLMProvider` protocol 允许注入 mock；unit test 用 mock，smoke test 用真实 API |
