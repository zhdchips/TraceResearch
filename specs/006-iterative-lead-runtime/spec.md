# 006 Iterative Lead Runtime

## Feature Summary

Add a finite iteration loop to LeadAgentRuntime so the Critique → Revise → Re-research/Re-write/Re-verify cycle can run automatically within a bounded number of iterations.

## Motivation

005's `run_pipeline` is a single-pass pipeline. When the Critic returns REVISE, the runtime has no mechanism to loop back and improve the output. This feature adds bounded iteration without changing the internal agent logic.

## Design

### RuntimeState Additions

- `iteration_index: int` — current iteration (0-indexed)
- `max_iterations: int` — cap on iterations (default 1, configurable via env var)
- `iteration_history: list[dict]` — record of each iteration's decision/next_phase/revision_reason
- `revision_reason: str | None` — why the last critic requested revision
- `next_phase: str | None` — what phase to jump back to

### Env Var

- `TRACERESEARCH_MAX_RUNTIME_ITERATIONS` — default 1 (single pass, no iteration). Set higher for multi-pass.

### Iteration Logic

1. After `critique_report()`, check `critique.decision`:
   - `PASS` → proceed to `finalize_run()`, exit loop
   - `REVISE` → if `iteration_index < max_iterations - 1`, loop back based on `next_phase`:
     - `research` → re-run `run_research_subagents → write_report → verify_report → critique_report`
     - `write` → re-run `write_report → verify_report → critique_report`
     - `verify` → re-run `verify_report → critique_report`
     - unsupported → log warning, finalize
   - `FAIL` → finalize_run, exit

2. Guard against infinite loop: max_iterations hard cap. If we hit max_iterations, finalize regardless.

### Trace Events

Each iteration emits:
- `ITERATION_START` — iteration_index, next_phase, revision_reason
- `ITERATION_DECISION` — critic decision, next_phase
- `ITERATION_FINISH` — iteration_index, status

These use the existing LEAD_RUNTIME agent_role with tool_name = "iteration_loop" and custom event types.

### Constraints

- Does NOT change Planner, Writer, Verifier, Critic, LeadResearchAgent internals
- Does NOT change CLI contract
- Does NOT break 005 failure trace behavior
- max_iterations=1 preserves single-pass behavior (backward compatible)
