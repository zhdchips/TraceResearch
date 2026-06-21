# 009 LangGraph Runtime Adapter — Review Checklist

## Architecture Review

- [ ] LangGraph only handles orchestration (routing between phases), not business logic
- [ ] All 6 graph nodes delegate to LeadAgentRuntime step methods
- [ ] GraphState is a TypedDict (LangGraph requirement), not a Pydantic model
- [ ] RuntimeState is still the source of truth for execution data
- [ ] GraphState and RuntimeState have a clear sync boundary (after each node)
- [ ] SubagentExecutor concurrency is unchanged
- [ ] EvidenceStore dedup is unchanged

## Mode Compatibility

- [ ] Default mode (`runtime`) unchanged — no new code path entered
- [ ] `tool_controller` mode unchanged — `_run_tool_controller_path()` untouched
- [ ] `langgraph` mode produces identical artifact files
- [ ] `langgraph` mode produces compatible trace.jsonl
- [ ] All 3 modes accept the same CLI arguments

## Graph Correctness

- [ ] START → plan_research edge exists
- [ ] plan_research → run_research_subagents (normal) or finalize_run (needs_clarification)
- [ ] run_research_subagents → write_report (normal) or finalize_run (all failed)
- [ ] write_report → verify_report
- [ ] verify_report → critique_report
- [ ] critique_report → finalize_run (PASS)
- [ ] critique_report → research/write/verify (REVISE based on next_phase)
- [ ] critique_report → finalize_run (FAIL)
- [ ] max_iterations check prevents infinite REVISE loop
- [ ] All paths eventually reach finalize_run → END

## Observability

- [ ] LANGGRAPH agent role added to AgentRole enum
- [ ] Each node start writes a LANGGRAPH trace event
- [ ] Each node finish writes a LANGGRAPH trace event
- [ ] Each conditional edge decision writes a LANGGRAPH trace event
- [ ] Existing LEAD_RUNTIME events are NOT modified
- [ ] Existing RESEARCH_LEAD/RESEARCH_SUBAGENT events are NOT modified

## Test Coverage

- [ ] Unit tests: GraphState serialization/deserialization
- [ ] Unit tests: Graph construction succeeds with all expected nodes
- [ ] Unit tests: Conditional routing for each decision (PASS/REVISE/FAIL)
- [ ] Unit tests: max_iterations stops infinite loop
- [ ] Integration tests: LangGraph mode completes a fixture run
- [ ] Integration tests: LangGraph mode produces all 10 artifacts
- [ ] Integration tests: trace.jsonl contains LANGGRAPH events
- [ ] Regression: `runtime` mode tests pass
- [ ] Regression: `tool_controller` mode tests pass

## Known Limitations

1. No checkpointing/resumability (intentionally deferred).
2. Graph routing is deterministic (no LLM-driven routing).
3. No human-in-the-loop nodes.
4. Single graph instance per run (no multi-graph fan-out).
5. No async LangGraph support (uses sync StateGraph API).
