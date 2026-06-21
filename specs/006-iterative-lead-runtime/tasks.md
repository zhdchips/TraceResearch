# Tasks: 006 Iterative Lead Runtime

## 006-1: Extend RuntimeState with iteration fields

- Add iteration_index, max_iterations, iteration_history, revision_reason, next_phase
- Read TRACERESEARCH_MAX_RUNTIME_ITERATIONS from env

## 006-2: Implement iteration loop in run_pipeline

- Wrap write/verify/critique in while loop
- Inspect critique.decision after each iteration
- Route based on next_phase
- Guard against infinite loops with max_iterations cap
- Handle unsupported next_phase with warning

## 006-3: Add iteration trace events

- Emit ITERATION_START, ITERATION_DECISION, ITERATION_FINISH events
- Include iteration_index, next_phase, revision_reason in trace

## 006-4: Write unit tests

- test_lead_runtime_iterations.py
- Cover: iteration fields, max_iterations env var, PASS/REVISE/FAIL routing, next_phase routing, infinite loop guard, trace events

## 006-5: Write integration tests

- test_iterative_runtime_integration.py
- Cover: full iteration pipeline with REVISE, unsupported next_phase, max_iterations reached

## 006-6: Run full test suite + fixture eval
