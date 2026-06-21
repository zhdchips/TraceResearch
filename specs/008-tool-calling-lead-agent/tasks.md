# Tasks: 008 Tool-Calling Lead Agent

## 008-1: Create runtime_tools.py

- RuntimeTool, ToolCall, ToolResult dataclasses
- TOOL_REGISTRY with 6 tools
- is_transition_allowed validator
- get_tool_by_name helper

## 008-2: Create lead_tool_controller.py

- LeadAgentToolController class
- Deterministic tool selection policy
- Tool loop (equivalent to run_pipeline)
- Tool execution trace events

## 008-3: Add env var toggle

- TRACERESEARCH_LEAD_AGENT_MODE (runtime | tool_controller)

## 008-4: Write unit tests

- test_runtime_tools.py: registry, transitions, tool metadata
- test_lead_tool_controller.py: tool selection, loop, trace

## 008-5: Write integration tests

- test_tool_controller_integration.py: full pipeline, REVISE routing, max steps

## 008-6: Run full test suite + fixture eval
