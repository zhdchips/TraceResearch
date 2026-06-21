# Plan: 006 Iterative Lead Runtime

## Implementation Steps

### 1. Extend RuntimeState (lead_runtime.py)

Add fields:
- `iteration_index: int = 0`
- `max_iterations: int = 1`
- `iteration_history: list[dict] = field(default_factory=list)`
- `revision_reason: str | None = None`
- `next_phase: str | None = None`

### 2. Add env var config (config.py or lead_runtime.py)

Read `TRACERESEARCH_MAX_RUNTIME_ITERATIONS` with default 1.

### 3. Modify run_pipeline for iteration loop

Wrap steps 3-5 (write → verify → critique) in a while loop with iteration tracking. After critique, inspect decision and next_phase. Loop back or finalize.

### 4. Add iteration trace helper

Add `_trace_iteration` method or extend `_trace_step` to emit iteration lifecycle events.

### 5. Tests

- `test_lead_runtime_iterations.py` — unit tests for iteration fields, loop logic, trace events
- `test_iterative_runtime_integration.py` — integration test with REVISE decision

### 6. Review

- Verify all existing tests pass
- Verify fixture eval still works
- Document limitations

## Files to Change

- `traceresearch/agents/lead_runtime.py` — RuntimeState + run_pipeline iteration loop
- `tests/unit/test_lead_runtime_iterations.py` — new
- `tests/integration/test_iterative_runtime_integration.py` — new

## Dependencies

Depends on 005 LeadAgentRuntime. No new dependencies.
