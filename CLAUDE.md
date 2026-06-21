<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/003-llm-backed-writer-verifier/plan.md.

Key design decisions:
- LLM provider: DeepSeek (deepseek-chat) via OpenAI-compatible API
- HTTP client: httpx (not openai SDK) for lightweight vendor-agnostic calls
- Writer/Verifier protocols: Python ABC for runtime isinstance checks
- Mode selection: env vars + CLI flags (--writer-mode, --verifier-mode)
- Fallback: LLM failure → auto deterministic, Trace records failover_reason
- LLM smoke eval: manual only, excluded from default pytest via marker
<!-- SPECKIT END -->
