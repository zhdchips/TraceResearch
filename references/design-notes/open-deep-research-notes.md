# Open Deep Research Notes

> Reference path: `references/upstream/open_deep_research`

## Positioning

Open Deep Research is a focused Deep Research agent implementation. It is useful as the primary reference for the end-to-end research loop: clarify scope, generate a research brief, delegate research tasks, compress findings, and generate a final report.

For this project, it should be treated as a workflow reference, not as source code to copy.

## Useful Workflow Ideas

### Clarification Before Research

The system has an explicit `clarify_with_user` step before research starts. It decides whether the user's request is sufficiently scoped.

可借鉴点：

- MVP 可以先做简单规则：当 query 缺少研究对象、时间范围或输出目标时，返回 clarification request。
- 不要默认所有 query 都直接进入 research，因为 Deep Research 的成本较高。

### Research Brief

The system turns conversation messages into a structured `research_brief`. This becomes the contract between the user request and downstream research agents.

可借鉴点：

- 本项目可以让 `Planner` 先生成 `research_brief`，再生成 research dimensions 和 sub-tasks。
- `research_brief` 应该进入 trace，方便 review bad case 时判断问题来自用户表达、Planner，还是后续 Researcher。

### Supervisor and Researcher Split

Open Deep Research separates:

- supervisor / lead researcher: decides what to research and whether research is complete
- researcher: executes focused tool-based research on a specific topic

可借鉴点：

- 本项目的 `Planner` 可以承担 supervisor 的第一阶段职责。
- 第一版不必实现复杂 supervisor loop，但可以保留 `max_research_iterations` 和 `max_concurrent_research_tasks` 配置。

### Parallel Research Units

The supervisor can issue multiple `ConductResearch` tool calls and run allowed research tasks concurrently, bounded by `max_concurrent_research_units`.

可借鉴点：

- MVP 可以先串行执行 research tasks，保留并发配置字段。
- 第二轮再实现并行，避免第一版复杂度过高。
- Eval 要记录并发后的 cost、latency、rate-limit failure。

### Research Compression

Open Deep Research compresses researcher outputs before final synthesis. This is central to context management.

可借鉴点：

- Researcher 不应该把网页原文直接塞给 Writer。
- Researcher 输出应写成 structured evidence summary，包括 source、summary、key excerpts、supported claims。
- Compression 结果必须保留 source ID，否则 Writer 的 citation 会断链。

### Configurable Models and Search Tools

The project separates models for summarization, research, compression, and final report generation. It also abstracts search API and MCP tools.

可借鉴点：

- MVP 可以只配置一个 model 和一个 search tool。
- 但设计上保留 `research_model`、`summary_model`、`writer_model`，便于后续做成本/质量权衡。

## Evaluation Ideas

Open Deep Research uses Deep Research Bench and records results with metrics such as leaderboard score, total tokens, and model settings.

可借鉴点：

- 本项目第一版不需要跑大型 benchmark。
- 先做 5 个 seed cases，指标包括 `planner_coverage`、`source_authority`、`citation_completeness`、`faithfulness`、`unsupported_claim_count`。
- Eval report 需要记录 model、tool config、token/cost/latency，避免只看质量不看成本。

## Not Suitable for MVP

- LangGraph Studio / hosted deployment
- Full MCP compatibility
- Deep Research Bench full 100-case evaluation
- Complex native search provider matrix
- Full supervisor autonomous loop with many concurrent researchers

## Plan Suggestions

- Add `research_brief` as the first structured artifact after user query.
- Make `Planner` output `research_dimensions` and `research_tasks`.
- Make `Researcher` output compressed evidence, not raw notes.
- Add bounded loop controls: `max_research_tasks`, `max_tool_calls_per_task`, `max_context_chars`.
- Add `final_report` generation only from `Evidence Store`.
