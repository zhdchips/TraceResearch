# Plan: 008 Tool-Calling Lead Agent

## Implementation Steps

### 1. Create runtime_tools.py

Define:
- `RuntimeTool` dataclass
- `ToolCall` dataclass
- `ToolResult` dataclass
- `TOOL_REGISTRY` — dict of 6 RuntimeTool definitions
- `is_transition_allowed(current_status, tool_name)` validator

### 2. Create lead_tool_controller.py

Define:
- `LeadAgentToolController` class
- Deterministic `select_next_tool(state)` method
- `execute_tool(tool_name, runtime, ...)` method
- `run_tool_loop(state, runtime, ...)` — the tool-loop equivalent of run_pipeline
- Tool execution trace events

### 3. Add env var toggle

Read `TRACERESEARCH_LEAD_AGENT_MODE`:
- `runtime` → use run_pipeline (default)
- `tool_controller` → use tool controller

### 4. Wire in (optional)

Add optional tool_controller mode to run_pipeline or provide separate entry point.

### 5. Tests

- Tool registry contains 6 tools
- Invalid transition rejected with error
- Deterministic tool policy runs full pipeline
- REVISE next_phase routing works
- Max steps enforcement
- Fixture eval still passes

## Files to Create

- `traceresearch/agents/runtime_tools.py` — new
- `traceresearch/agents/lead_tool_controller.py` — new
- `tests/unit/test_runtime_tools.py` — new
- `tests/unit/test_lead_tool_controller.py` — new
- `tests/integration/test_tool_controller_integration.py` — new
