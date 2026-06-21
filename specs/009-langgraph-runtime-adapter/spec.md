# 009 LangGraph Runtime Adapter

**Status**: in-progress
**Parent**: 008-tool-calling-lead-agent
**Date**: 2026-06-21

## Goal

Introduce LangGraph as the orchestration layer for the Lead Agent, replacing the imperative `run_pipeline()` loop with a declarative `StateGraph` while keeping all existing agent implementations (Planner, LeadResearchAgent, Writer, Verifier, Critic) untouched.

## Motivation

The current `LeadAgentRuntime.run_pipeline()` uses a hard-coded `while` loop with ad-hoc conditional branches. While functional, this imperative loop is opaque — it cannot be visualized, stepped, or modified without changing code. A LangGraph `StateGraph` solves this by:

1. **Declarative orchestration** — nodes and edges define the pipeline topology explicitly.
2. **Visualizable** — LangGraph can render the graph as a diagram.
3. **Extensible** — adding a node (e.g., human approval) is a graph edit, not a refactor.
4. **Built-in state persistence** — checkpointing via `MemorySaver` without changing application code.
5. **Interview-ready** — LangGraph is the industry standard for agent orchestration.

## Core Principles

1. **Adapter-first, not rewrite** — LangGraph wraps `LeadAgentRuntime` step methods; it does NOT replace them.
2. **Existing agents untouched** — Planner, LeadResearchAgent, Writer, Verifier, Critic remain unchanged.
3. **LangGraph only for Lead Agent orchestration** — subagent concurrency remains in `SubagentExecutor`.
4. **RuntimeState is still the execution state core** — LangGraph state is a lightweight orchestration wrapper.
5. **All existing modes preserved** — `runtime` (default), `tool_controller`, and the new `langgraph` mode all work.

## User Stories

- **US-001**: As a developer, I want to use LangGraph to orchestrate the research pipeline so I can visualize and debug execution flow.
- **US-002**: As a developer, I want `TRACERESEARCH_LEAD_AGENT_MODE=langgraph` to produce the same artifacts as `runtime` mode.
- **US-003**: As an operator, I want each graph node transition written to trace.jsonl so I can replay the execution path.
- **US-004**: As a reviewer, I want max_iterations enforced at the graph level so infinite loops are structurally impossible.

## Functional Requirements

### FR-001: GraphState
The system SHALL provide a `GraphState` (TypedDict) with fields:
- `run_id`, `run_dir`, `status`
- `current_step`, `next_phase`
- `iteration_index`, `max_iterations`
- `artifact_paths` (dict[str, str])
- `critique_decision`, `revision_reason`
- `error_message`

### FR-002: StateGraph Nodes
The LangGraph StateGraph SHALL contain nodes:
- `plan_research` — calls `runtime.plan_research()`
- `run_research_subagents` — calls `runtime.run_research_subagents()`
- `write_report` — calls `runtime.write_report()`
- `verify_report` — calls `runtime.verify_report()`
- `critique_report` — calls `runtime.critique_report()`
- `finalize_run` — calls `runtime.finalize_run()`

### FR-003: Conditional Routing
The graph SHALL implement conditional edges:
- `plan_research` → `run_research_subagents` (normal) or `finalize_run` (needs_clarification)
- `run_research_subagents` → `write_report` (normal) or `finalize_run` (all failed)
- `write_report` → `verify_report`
- `verify_report` → `critique_report`
- `critique_report` → `finalize_run` (PASS), or route to `run_research_subagents`/`write_report`/`verify_report` based on `next_phase` (REVISE), or `finalize_run` (FAIL)
- Max iterations check before REVISE re-routing

### FR-004: RuntimeState Synchronization
After each node executes, the graph SHALL synchronize `GraphState` fields from `RuntimeState`.

### FR-005: Harness Integration
`ResearchHarness` SHALL support `TRACERESEARCH_LEAD_AGENT_MODE=langgraph`:
- Default mode remains `runtime`
- `langgraph` mode produces identical artifacts to `runtime` mode
- `tool_controller` mode is NOT degraded

### FR-006: Observability
Each graph node SHALL write trace events:
- `LANGGRAPH_NODE_START` before execution
- `LANGGRAPH_NODE_FINISH` after execution
- `LANGGRAPH_EDGE_DECISION` for conditional routing

### FR-007: Max Iterations
The graph SHALL structurally prevent infinite loops via:
- `iteration_index >= max_iterations` check before REVISE re-routing
- Conditional edge that routes to `finalize_run` when cap is reached

### FR-008: Artifact Compatibility
LangGraph mode SHALL produce all 10 required artifacts:
`research_brief.json`, `research_tasks.json`, `evidence.jsonl`, `outline.md`, `draft_report.md`, `verification.json`, `critique.json`, `final_report.md`, `report.json`, `trace.jsonl`

## Key Entities

### GraphState (TypedDict)
- `run_id: str`
- `run_dir: str`
- `status: str`
- `current_step: str`
- `next_phase: str`
- `iteration_index: int`
- `max_iterations: int`
- `artifact_paths: dict[str, str]`
- `critique_decision: str`
- `revision_reason: str`
- `error_message: str`

### LeadGraphRuntime (class)
- `__init__(self, runtime: LeadAgentRuntime, state: RuntimeState)`
- `build_graph() -> StateGraph`
- `run(query, provider, ...) -> RuntimeState`

### GraphNodeTrace (dataclass)
- `node_name: str`
- `event_type: str` (start/finish)
- `timestamp: datetime`
- `decision: str | None`

## Non-Goals

1. No LangGraph checkpointing for resumability (future work).
2. No human-in-the-loop nodes.
3. No LLM-driven graph routing (deterministic conditions only).
4. No multi-graph fan-out (single graph, single thread for orchestration).
5. No changes to Writer/Verifier/Critic business logic.
6. No changes to SubagentExecutor concurrency model.

## Success Criteria

| # | Criterion | Verification |
|---|-----------|-------------|
| SC-001 | Graph construction succeeds with all 6 nodes | Unit test |
| SC-002 | LangGraph mode completes a fixture research run | Integration test |
| SC-003 | LangGraph mode produces all 10 artifacts | Integration test |
| SC-004 | trace.jsonl contains LANGGRAPH node/edge events | Integration test |
| SC-005 | REVISE routes correctly by next_phase | Unit test |
| SC-006 | max_iterations prevents infinite loops | Unit test |
| SC-007 | Default runtime mode still passes all tests | CI |
| SC-008 | tool_controller mode still passes all tests | CI |
