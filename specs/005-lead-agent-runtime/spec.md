# 005 Lead Agent Runtime

**Status**: implemented  
**Parent**: 004-research-subagents  
**Date**: 2026-06-21

## Goal

Evolve the existing fixed orchestrator pipeline into a **Lead Agent Runtime** — a unified runtime that manages the full research pipeline (Plan → Research → Write → Verify → Critique → Finalize) as discrete, traceable steps, each with its own lifecycle events.

## Motivation

The current `ResearchHarness._run_with_provider()` is a monolithic 300+ line method that interleaves agent calls, trace recording, artifact writing, and error handling. Each pipeline stage follows the same pattern (START → execute → FINISH) but implements it ad-hoc. The orchestrator has no explicit state object — state flows implicitly through local variables.

A Lead Agent Runtime addresses these issues by:
1. **Explicit state management** — `RuntimeState` carries all run state between steps.
2. **Uniform step lifecycle** — Every step records START / TOOL_CALL / TOOL_RESULT / FINISH trace events.
3. **Thinner orchestrator** — The harness becomes a thin wrapper that constructs the runtime and calls it.
4. **Observability** — Full execution chain visible in traces: LeadAgentRuntime → Planner → LeadResearchAgent → ResearchSubagent → Writer → Verifier → Critic.

## User Stories

- **US-001**: As a developer, I want a `LeadAgentRuntime` class that orchestrates all pipeline stages so I can understand the full execution flow in one place.
- **US-002**: As a developer, I want a `RuntimeState` object that carries all run state between steps so state flow is explicit and testable.
- **US-003**: As an operator, I want each runtime step to record trace events showing its lifecycle so I can debug execution issues.
- **US-004**: As a user, I want the CLI behavior unchanged so existing workflows continue working.

## Functional Requirements

### FR-001: LeadAgentRuntime
The system SHALL provide a `LeadAgentRuntime` class that orchestrates the research pipeline as discrete steps:
- `plan_research(query, eval_case)` — delegates to `Planner.plan()`
- `run_research_subagents(provider, provider_tool_name)` — delegates to `LeadResearchAgent.conduct_research()`
- `write_report()` — delegates to `Writer.draft()`
- `verify_report()` — delegates to `Verifier.verify()`, updates EvidenceStore statuses
- `critique_report()` — delegates to `Critic.review()`
- `finalize_run()` — delegates to `Writer.final()`

### FR-002: RuntimeState
The system SHALL provide a `RuntimeState` dataclass with fields:
- `run_id`, `run_dir`, `trace_writer`
- `research_brief`, `planned_tasks`
- `evidence`, `failed_task_ids`
- `draft_report`, `verification_result`, `critique_result`
- `final_report`, `status`

### FR-003: Step Trace Events
Each runtime step SHALL record:
1. `LEAD_RUNTIME` START with `tool_name` = step name
2. `LEAD_RUNTIME` TOOL_CALL with input summary
3. Internal agent events (PLANNER, RESEARCH_LEAD, etc.)
4. `LEAD_RUNTIME` TOOL_RESULT with output summary
5. `LEAD_RUNTIME` FINISH with status

On failure, SHALL record `LEAD_RUNTIME` FINISH with `FAILED` status and error payload.

### FR-004: Research Step Reuses 004
The `run_research_subagents` step MUST call `LeadResearchAgent.conduct_research()` directly — it MUST NOT reimplement subagent dispatch, concurrency, deduplication, or evidence store writing.

### FR-005: Thinner Orchestrator
`ResearchHarness._run_with_provider()` SHALL be refactored to:
1. Construct `RuntimeState` and `LeadAgentRuntime`
2. Call `runtime.run_pipeline()` or individual step methods
3. Handle CLI-level result construction

### FR-006: CLI Contract Unchanged
`traceresearch run` and `traceresearch eval` SHALL accept the same arguments and produce the same output structure.

### FR-007: Trace Chain
The trace SHALL contain events showing the full execution chain:
`LeadAgentRuntime → Planner → LeadResearchAgent → ResearchSubagent → Writer → Verifier → Critic`

### FR-008: Backward Compatibility
004's `RESEARCH_LEAD` and `RESEARCH_SUBAGENT` trace events SHALL NOT be modified.

### FR-009: Fixture Eval
`traceresearch eval --cases-dir eval/cases --source-provider fixture --results-dir eval/results` SHALL pass 5/5.

### FR-010: Non-LLM Tests
`python3 -m pytest -m "not llm_smoke" -q` SHALL pass with all existing tests green.

## Key Entities

### RuntimeState (dataclass)
- `run_id: str`
- `run_dir: str`
- `trace_writer: TraceWriter | None`
- `research_brief: ResearchBrief | None`
- `planned_tasks: list[ResearchTask]`
- `evidence: list[Evidence]`
- `failed_task_ids: list[str]`
- `draft_report: DraftReport | None`
- `verification_result: VerificationResult | None`
- `critique_result: CritiqueResult | None`
- `final_report: FinalReport | None`
- `status: str`

### LeadAgentRuntime (class)
- Constructor: `(state, *, planner, lead_researcher, writer, verifier, critic)`
- Methods: `plan_research()`, `run_research_subagents()`, `write_report()`, `verify_report()`, `critique_report()`, `finalize_run()`, `run_pipeline()`

### AgentRole Addition
- `LEAD_RUNTIME = "LeadRuntime"` added to `AgentRole` enum.

## Non-Goals

1. No LangGraph integration.
2. No real LLM tool calling (agents call each other directly, not via LLM function calls).
3. No human-in-the-loop (no pause/approve between steps).
4. No distributed execution — single runtime, single process.
5. No Writer/Verifier/Critic business logic changes.
6. No output directory structure changes.
7. No multi-runtime concurrent writes to same `run_dir`.

## Success Criteria

| # | Criterion | Verification |
|---|-----------|-------------|
| SC-001 | `LeadAgentRuntime` class exists with 6 step methods | Code review |
| SC-002 | `RuntimeState` exists with all required fields | Code review |
| SC-003 | Each step records START/TOOL_CALL/TOOL_RESULT/FINISH trace events | Integration test |
| SC-004 | `run_research_subagents` reuses `LeadResearchAgent` | Code review |
| SC-005 | CLI `run` and `eval` work without new required args | Manual + eval test |
| SC-006 | `pytest -m "not llm_smoke" -q` passes | CI |
| SC-007 | `traceresearch eval` passes 5/5 | CI |
| SC-008 | 004 tests continue to pass | CI |
| SC-009 | Trace shows `LEAD_RUNTIME` events wrapping internal agent events | Integration test |
