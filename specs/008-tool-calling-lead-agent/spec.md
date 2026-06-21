# 008 Tool-Calling Lead Agent

## Feature Summary

Wrap the existing runtime steps as tool-like abstractions with a deterministic tool controller, preparing the interface for future LLM function calling without changing the pipeline logic.

## Motivation

To evolve from "fixed runtime steps" toward "tool-based subagents," we need:
1. A tool abstraction (RuntimeTool) with name, description, schema, preconditions
2. A tool registry and controller that selects the next tool based on state
3. An env-var toggle to switch between classic runtime and tool-controller paths

## Design

### RuntimeTool

```python
@dataclass
class RuntimeTool:
    name: str
    description: str
    input_schema: dict  # lightweight contract
    allowed_preconditions: list[str]  # state.status values that allow this tool
```

### ToolCall / ToolResult

```python
@dataclass
class ToolCall:
    tool_name: str
    step_name: str
    params: dict
    trace_id: str

@dataclass
class ToolResult:
    tool_name: str
    status: str  # success / failed
    output_summary: str
    error: str | None
```

### Tools (6 runtime tools)

1. `plan_research` — precondition: initialized
2. `run_research_subagents` — precondition: planned
3. `write_report` — precondition: researched
4. `verify_report` — precondition: drafted
5. `critique_report` — precondition: verified
6. `finalize_run` — precondition: critiqued

### Deterministic Tool Policy

State machine transitions:
```
initialized → plan_research → planned
planned → run_research_subagents → researched
researched → write_report → drafted
drafted → verify_report → verified
verified → critique_report → critiqued
critiqued + PASS → finalize_run → completed
critiqued + REVISE → route based on next_phase
```

### Env Var

`TRACERESEARCH_LEAD_AGENT_MODE`:
- `runtime` (default) — classic pipeline path
- `tool_controller` — uses the new tool controller

### Trace Events

Each tool execution records:
- LEAD_RUNTIME TOOL_CALL with tool_name
- LEAD_RUNTIME TOOL_RESULT with tool_name, status, error

### Constraints

- No real LLM function calling
- No LangGraph
- Classic runtime path preserved and default
- CLI contract unchanged
