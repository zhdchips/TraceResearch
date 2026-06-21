# Review: 008 Tool-Calling Lead Agent

## Completed Items

1. RuntimeTool, ToolCall, ToolResult dataclasses
2. TOOL_REGISTRY with 6 tools (plan, research, write, verify, critique, finalize)
3. Transition validation: is_transition_allowed, get_next_status
4. LeadAgentToolController with deterministic select_next_tool policy
5. Tool loop: run_tool_loop mirrors run_pipeline but uses tool selection
6. REVISE routing: research/write/verify next_phase → correct tool
7. Unsupported next_phase → finalize_run
8. Max steps enforcement
9. Tool execution trace: LEAD_RUNTIME TOOL_CALL + TOOL_RESULT
10. Env var toggle: TRACERESEARCH_LEAD_AGENT_MODE (runtime | tool_controller)
11. Runtime mode is default, classic path preserved
12. No real LLM function calling, no LangGraph

## Integration Fix (Round 2)

13. **Harness integration**: ResearchHarness reads TRACERESEARCH_LEAD_AGENT_MODE. When "tool_controller", delegates to LeadAgentToolController.run_tool_loop()
14. **Artifact writing in tool controller path**: artifacts (research_brief.json, outline.md, draft_report.md, verification.json, critique.json, final_report.md, report.json) all written from state after tool loop
15. **max_iterations respected in select_next_tool**: when _iteration_count >= max_iterations and decision is REVISE, forces "finalize_run" instead of routing
16. **_iteration_count tracking**: persisted on controller instance, checked in both run_tool_loop and select_next_tool

## Test Results

- tests/unit/test_runtime_tools.py: 26/26 passed
- tests/unit/test_lead_tool_controller.py: 27/27 passed
- tests/integration/test_tool_controller_integration.py: 3/3 passed
- tests/integration/test_harness_iteration_integration.py (tool controller tests): 4/4 passed
- Full non-smoke suite: 469/469 passed
- Fixture eval: 5/5 pass_rate=1.00

## Known Limitations

- Deterministic policy only; LLM-based tool selection not implemented
- Tool schema is lightweight (dict), not JSON Schema
- No parallel tool execution
- No error recovery beyond finalize on failure
- Tool controller and classic runtime path are separate code paths (some duplication)

## Files Changed

- `traceresearch/agents/runtime_tools.py` — new
- `traceresearch/agents/lead_tool_controller.py` — max_iterations fix + _iteration_count
- `traceresearch/harness/orchestrator.py` — tool_controller path + _run_tool_controller_path + _wrap_up_run
- `tests/unit/test_runtime_tools.py` — new
- `tests/unit/test_lead_tool_controller.py` — new
- `tests/integration/test_tool_controller_integration.py` — new
- `tests/integration/test_harness_iteration_integration.py` — harness tool controller tests
- `specs/008-tool-calling-lead-agent/*` — new
