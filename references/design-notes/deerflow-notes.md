# DeerFlow Notes

> Reference path: `/Users/zhdchips/AIProject/deer-flow`

## Positioning

DeerFlow is best used as the Agent Harness reference. It is broader than Deep Research: it provides a long-running agent runtime with tools, skills, sandbox, memory, sub-agent coordination, context management, and frontend/gateway infrastructure.

For this project, borrow harness principles selectively. Do not attempt to recreate DeerFlow 2.0 in the MVP.

## Useful Harness Ideas

### Harness as Runtime Layer

DeerFlow treats the agent as something that needs a runtime environment, not just prompts and model calls.

可借鉴点：

- 本项目可以 explicitly define an `Agent Harness` layer that owns:
  - tool access
  - trace logging
  - evidence store
  - context compression
  - task state
  - eval hooks

### Long-Running Agent Mental Model

DeerFlow frames useful agents as long-running processes that plan, act, use tools, manage files, store intermediate results, and produce artifacts.

可借鉴点：

- Deep Research 应该保存中间产物，而不是只输出一段答案。
- 每个 run 应有 `run_id` 和 task lifecycle。

### Sub-Agent Isolation

DeerFlow's `task` tool delegates complex work to subagents with separate context. The purpose is to preserve main context and isolate exploration.

可借鉴点：

- 本项目可以把 each research task 当成 isolated sub-task。
- Researcher 只看到自己的 task、brief、allowed tools，不直接看到完整主上下文。
- 最终只把 compressed evidence 汇总回主流程。

### Skills as Task-Specific Instructions

DeerFlow uses skills as task-oriented capability packages.

可借鉴点：

- MVP 不需要实现完整 skill system。
- 可以把 `deep_research` prompt / policy 作为单个 local skill-like instruction。
- 后续可以扩展 `academic-research`、`github-research`、`market-research` 等场景。

### Sandbox and File Workspace

DeerFlow gives agents a workspace for reading/writing outputs and executing actions in controlled environments.

可借鉴点：

- MVP 不需要完整 sandbox。
- 但应该把 artifacts 固定写入 `runs/<run_id>/`，例如 evidence、trace、outline、report。
- 后续如果接入代码/文件分析，再考虑 sandbox。

### Context Engineering

DeerFlow emphasizes controlling what the model sees and when. Techniques include summarization, sub-agent context isolation, and file system as external working memory.

可借鉴点：

- Writer 读取 structured evidence，不读取全部 raw pages。
- Researcher 输出 compressed evidence。
- Long context should be persisted as files and retrieved by ID.

### Traceability

DeerFlow's architecture contains runtime state, middleware, tool execution orchestration, SSE streaming, and tracing hooks.

可借鉴点：

- MVP trace 不需要复杂 observability stack。
- 先实现 `trace.jsonl`:
  - run_id
  - task_id
  - agent_role
  - event_type
  - tool_name
  - input_summary
  - output_summary
  - status
  - latency_ms
  - error

## Not Suitable for MVP

- Full FastAPI gateway and frontend
- Full sandbox provider abstraction
- MCP server management UI
- Long-term memory system
- Channel integrations
- Complete skills marketplace / installer
- Streaming UI

## Plan Suggestions

- Add a small `harness` module for run state, trace, evidence, and artifact paths.
- Treat sub-agent isolation as a design principle even if MVP implementation is function calls.
- Make context compression explicit: raw sources -> evidence summaries -> report.
- Keep a future extension section for sandbox, skills, memory, and UI.
