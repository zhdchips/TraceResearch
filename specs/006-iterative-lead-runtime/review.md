# Review: 006 Iterative Lead Runtime

## Completed Items

1. RuntimeState iteration fields: iteration_index, max_iterations, iteration_history, revision_reason, next_phase
2. Env var TRACERESEARCH_MAX_RUNTIME_ITERATIONS with default 1
3. Iteration loop in run_pipeline: write → verify → critique, with REVISE routing
4. PASS exits loop, REVISE routes to research/write/verify, FAIL exits
5. Unsupported next_phase logs warning and finalizes
6. Infinite loop prevention: max_iterations hard cap
7. Iteration trace events: START, TOOL_RESULT, FINISH with iteration_loop tool_name
8. Backward compatible: max_iterations=1 preserves single-pass 005 behavior
9. No changes to Planner, Writer, Verifier, Critic, LeadResearchAgent

## Integration Fix (Round 2)

10. **Harness iteration**: ResearchHarness._run_with_provider now wraps write→verify→critique in an iteration loop with trace events
11. **Env var in harness**: TRACERESEARCH_MAX_RUNTIME_ITERATIONS applies to ResearchHarness.run_fixture()
12. **Harness trace**: iteration_loop events emitted by harness (LEAD_RUNTIME + tool_name="iteration_loop")
13. **Artifact writing preserved**: outline.md, draft_report.md, verification.json, critique.json written per iteration

## Test Results

- tests/unit/test_lead_runtime_iterations.py: 22/22 passed
- tests/integration/test_iterative_runtime_integration.py: 3/3 passed
- tests/integration/test_harness_iteration_integration.py (harness tests): 2/2 passed
- Existing 005 tests: 55/55 passed
- Full non-smoke suite: 469/469 passed
- Fixture eval: 5/5 pass_rate=1.00

## Known Limitations

- Iteration only applies to write→verify→critique segment; plan and initial research run once
- No dynamic adjustment of max_iterations mid-pipeline
- revision_reason derived from missing_perspectives only
- Manual step-by-step path (not through harness) won't emit iteration_loop trace events

## Files Changed

- `traceresearch/agents/lead_runtime.py` — RuntimeState + run_pipeline iteration loop
- `traceresearch/harness/orchestrator.py` — iteration loop + trace in _run_with_provider
- `tests/unit/test_lead_agent_runtime.py` — updated trace event count (24→27)
- `tests/unit/test_lead_runtime_iterations.py` — new
- `tests/integration/test_iterative_runtime_integration.py` — new
- `tests/integration/test_harness_iteration_integration.py` — new (harness iteration)
- `specs/006-iterative-lead-runtime/*` — new
