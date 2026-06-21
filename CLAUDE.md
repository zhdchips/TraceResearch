<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/004-research-subagents/plan.md.

Key design decisions:
- LLM provider: DeepSeek (deepseek-chat) via OpenAI-compatible API
- HTTP client: httpx (not openai SDK) for lightweight vendor-agnostic calls
- Writer/Verifier protocols: Python ABC for runtime isinstance checks
- Mode selection: env vars + CLI flags (--writer-mode, --verifier-mode)
- Fallback: LLM failure → auto deterministic, Trace records failover_reason
- LLM smoke eval: manual only, excluded from default pytest via marker
- Research concurrency: ThreadPoolExecutor, default max_concurrent=3, env var TRACERESEARCH_MAX_CONCURRENT_RESEARCH_TASKS
- Research subagents: LeadResearchAgent dispatches tasks → SubagentExecutor → ResearchTaskAgent per task
- Subagent context: compressed (brief summary + task + provider), no full harness access
- Partial failure: failed tasks don't block successful evidence; Critic records missing perspectives
- Trace: RESEARCH_LEAD + RESEARCH_SUBAGENT events with subagent lifecycle
<!-- SPECKIT END -->
