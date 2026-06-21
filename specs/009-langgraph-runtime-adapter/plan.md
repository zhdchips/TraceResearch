# 009 LangGraph Runtime Adapter — Implementation Plan

**Date**: 2026-06-21
**Branch**: 009-langgraph-runtime-adapter

## Architecture Overview

```
ResearchHarness
  ├── mode=runtime (default) → LeadAgentRuntime.run_pipeline()
  ├── mode=tool_controller    → LeadAgentToolController.run_tool_loop()
  └── mode=langgraph (NEW)    → LeadGraphRuntime.run()
                                    └── StateGraph
                                         ├─ plan_research → runtime.plan_research()
                                         ├─ run_research_subagents → runtime.run_research_subagents()
                                         ├─ write_report → runtime.write_report()
                                         ├─ verify_report → runtime.verify_report()
                                         ├─ critique_report → runtime.critique_report()
                                         └─ finalize_run → runtime.finalize_run()
```

## Files to Create

### 1. `traceresearch/agents/graph_state.py`
Lightweight `GraphState` TypedDict used by LangGraph.

```python
class GraphState(TypedDict):
    run_id: str
    run_dir: str
    status: str
    current_step: str
    next_phase: str
    iteration_index: int
    max_iterations: int
    artifact_paths: dict[str, str]
    critique_decision: str
    revision_reason: str
    error_message: str
    # Internal references (not serialized in graph state)
    _runtime_state: Any  # RuntimeState
    _runtime: Any  # LeadAgentRuntime
```

### 2. `traceresearch/agents/lead_graph_runtime.py`
LangGraph runtime adapter with StateGraph construction and node implementations.

Key classes:
- `LeadGraphRuntime(runtime, state, *, trace_writer)` — adapter that builds and runs the graph
- Node functions (module-level for LangGraph compatibility):
  - `_node_plan_research(state)`
  - `_node_run_research_subagents(state)`
  - `_node_write_report(state)`
  - `_node_verify_report(state)`
  - `_node_critique_report(state)`
  - `_node_finalize_run(state)`
- Conditional routing functions:
  - `_route_after_plan(state)`
  - `_route_after_research(state)`
  - `_route_after_critique(state)`

### 3. Updated `traceresearch/harness/orchestrator.py`
Add `_run_langgraph_path()` method to `ResearchHarness`.
Extend `_read_lead_agent_mode()` to accept `"langgraph"`.

### 4. Updated `traceresearch/agents/lead_tool_controller.py`
Extend `_read_lead_agent_mode()` to return `"langgraph"` as valid mode.

### 5. Updated `traceresearch/trace/models.py`
Add `LANGGRAPH = "LangGraph"` to `AgentRole`.

## Files to Create (Spec)

- `specs/009-langgraph-runtime-adapter/spec.md`
- `specs/009-langgraph-runtime-adapter/plan.md` (this file)
- `specs/009-langgraph-runtime-adapter/tasks.md`
- `specs/009-langgraph-runtime-adapter/quickstart.md`
- `specs/009-langgraph-runtime-adapter/review.md`
- `specs/009-langgraph-runtime-adapter/interview.md`
- `specs/009-langgraph-runtime-adapter/resume.md`

## Files to Update

| File | Change |
|------|--------|
| `pyproject.toml` | Add `langgraph>=0.2` dependency |
| `traceresearch/trace/models.py` | Add `LANGGRAPH` to `AgentRole` |
| `traceresearch/agents/lead_tool_controller.py` | Extend `_read_lead_agent_mode()` for `"langgraph"` |
| `traceresearch/harness/orchestrator.py` | Add `_run_langgraph_path()` |

## Files to Create

| File | Purpose |
|------|---------|
| `traceresearch/agents/graph_state.py` | `GraphState` TypedDict + helpers |
| `traceresearch/agents/lead_graph_runtime.py` | `LeadGraphRuntime` with StateGraph |

## Test Files to Create/Update

| File | Purpose |
|------|---------|
| `tests/unit/test_graph_state.py` | Unit tests for graph state serialization |
| `tests/unit/test_lead_graph_runtime.py` | Unit tests for graph construction, routing logic |
| `tests/integration/test_langgraph_integration.py` | Integration tests with fixture provider |

## Dependency Graph

```
pyproject.toml (add langgraph)
    │
    ▼
traceresearch/trace/models.py (add LANGGRAPH AgentRole)
    │
    ▼
traceresearch/agents/graph_state.py (new — GraphState)
    │
    ▼
traceresearch/agents/lead_graph_runtime.py (new — LeadGraphRuntime)
    │
    ▼
traceresearch/agents/lead_tool_controller.py (_read_lead_agent_mode extended)
    │
    ▼
traceresearch/harness/orchestrator.py (_run_langgraph_path added)
    │
    ▼
tests/unit/test_graph_state.py
tests/unit/test_lead_graph_runtime.py
tests/integration/test_langgraph_integration.py
```

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| LangGraph API changes | Medium | Pin version, use stable `StateGraph` API |
| Graph state vs RuntimeState drift | Low | Explicit sync after each node |
| Runtime regression | High | Default mode unchanged; test all 3 modes |
| Infinite loop in REVISE | Medium | Structural check: `iteration_index >= max_iterations → finalize_run` |
