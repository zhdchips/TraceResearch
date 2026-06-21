# 005 Lead Agent Runtime — Review

**Date**: 2026-06-21  
**Branch**: 004-research-subagents (continuing on same branch for incremental delivery)

## Completed Items

### Phase 0: Trace Model
- [x] T001: Added `LEAD_RUNTIME = "LeadRuntime"` to `AgentRole` enum in `traceresearch/trace/models.py`

### Phase 1: Core Runtime
- [x] T002: Created `RuntimeState` dataclass with all required fields (`run_id`, `run_dir`, `trace_writer`, `research_brief`, `planned_tasks`, `evidence`, `failed_task_ids`, `draft_report`, `verification_result`, `critique_result`, `final_report`, `status`)
- [x] T003: Created `LeadAgentRuntime` class with constructor accepting state + injected agents
- [x] T004: Implemented `_trace_step()` and `_trace_agent()` helpers for recording trace events
- [x] T005: Implemented `plan_research()` step — delegates to `Planner.plan()`
- [x] T006: Implemented `run_research_subagents()` step — delegates to `LeadResearchAgent.conduct_research()`, reuses 004 subagent logic
- [x] T007: Implemented `write_report()` step — delegates to `Writer.draft()`
- [x] T008: Implemented `verify_report()` step — delegates to `Verifier.verify()`, updates `EvidenceStore` statuses
- [x] T009: Implemented `critique_report()` step — delegates to `Critic.review()`
- [x] T010: Implemented `finalize_run()` step — delegates to `Writer.final()`
- [x] T011: Implemented `run_pipeline()` method — runs all 6 steps in sequence with early-return for NEEDS_CLARIFICATION and all-tasks-failed

### Phase 2: Orchestrator Refactoring
- [x] T012: Refactored `_run_with_provider()` to construct `RuntimeState` + `LeadAgentRuntime` and delegate pipeline to the runtime. Method is now ~80 lines (down from ~250).
- [x] T013: Updated `traceresearch/agents/__init__.py` with exports for `LeadAgentRuntime`, `RuntimeState`, `RunContext`

### Phase 3: Unit Tests (28 tests)
- [x] T014: `RuntimeState` creation, defaults, mutation, `RunContext` alias
- [x] T015: `LeadAgentRuntime` initialization with defaults and injected agents
- [x] T016: `plan_research` step — planner call, state update, trace events, NEEDS_CLARIFICATION
- [x] T017: `run_research_subagents` step — lead researcher call, evidence update, trace events
- [x] T018: `write_report`, `verify_report`, `critique_report`, `finalize_run` steps
- [x] T019: `run_pipeline` full flow with all 6 steps
- [x] T020: Error handling — no trace writer, early returns

### Phase 4: Integration Tests (12 tests)
- [x] T021: Full pipeline with fixture provider — evidence, report, all artifacts
- [x] T022: Trace chain — LEAD_RUNTIME events wrapping all internal agents
- [x] T023: 004 regression — RESEARCH_LEAD, RESEARCH_SUBAGENT events preserved, evidence IDs stable, partial failure

## Test Results

### Unit Tests
```
tests/unit/test_lead_agent_runtime.py — 28 passed
```

### Integration Tests
```
tests/integration/test_lead_runtime_integration.py — 12 passed
```

### Full Test Suite
```
python3 -m pytest -m "not llm_smoke" -q
323 passed, 5 deselected
```

One existing test was updated (`test_all_agent_roles_are_available` in `test_trace_models.py`) to include the new `LeadRuntime` role.

### Fixture Eval
```
traceresearch eval — 5/5 cases pass
```
| Case | Result |
|------|--------|
| 001-framework-comparison | PASS |
| 002-financial-grounding | PASS |
| 003-ai-coding-agent-trends | PASS |
| 004-openhands-runtime | PASS |
| 005-rag-2026 | PASS |

## Trace Chain Verified

The trace from a completed run shows:

```
LeadRuntime plan_research START → TOOL_CALL → [Planner START/FINISH] → TOOL_RESULT → FINISH
LeadRuntime run_research_subagents START → TOOL_CALL → [ResearchLead → ResearchSubagent ×4] → TOOL_RESULT → FINISH
LeadRuntime write_report START → TOOL_CALL → [Writer START/FINISH] → TOOL_RESULT → FINISH
LeadRuntime verify_report START → TOOL_CALL → [Verifier START/FINISH] → TOOL_RESULT → FINISH
LeadRuntime critique_report START → TOOL_CALL → [Critic START/FINISH] → TOOL_RESULT → FINISH
LeadRuntime finalize_run START → TOOL_CALL → [Writer START/FINISH] → TOOL_RESULT → FINISH
```

Total: 24 `LeadRuntime` events, plus all internal agent events preserved.

## Changes Summary

### New Files
| File | Lines | Purpose |
|------|-------|---------|
| `traceresearch/agents/lead_runtime.py` | ~330 | `LeadAgentRuntime`, `RuntimeState`, `RunContext` |
| `tests/unit/test_lead_agent_runtime.py` | ~700 | 28 unit tests |
| `tests/integration/test_lead_runtime_integration.py` | ~340 | 12 integration tests |
| `specs/005-lead-agent-runtime/spec.md` | — | Feature specification |
| `specs/005-lead-agent-runtime/plan.md` | — | Implementation plan |
| `specs/005-lead-agent-runtime/tasks.md` | — | Task breakdown |
| `specs/005-lead-agent-runtime/quickstart.md` | — | Quickstart guide |
| `specs/005-lead-agent-runtime/review.md` | — | This review |

### Modified Files
| File | Change |
|------|--------|
| `traceresearch/trace/models.py` | Added `LEAD_RUNTIME` to `AgentRole` enum |
| `traceresearch/harness/orchestrator.py` | Refactored `_run_with_provider()` to delegate to `LeadAgentRuntime` |
| `traceresearch/agents/__init__.py` | Added exports for `LeadAgentRuntime`, `RuntimeState`, `RunContext` |
| `tests/unit/test_trace_models.py` | Updated `test_all_agent_roles_are_available` to include `LeadRuntime` |

## Known Limitations

1. **No iteration loop**: `CritiqueResult.next_phase` and `CritiqueDecision.REVISE` exist in the data model but the runtime does not loop back to earlier stages. This was already the case in 004 and is explicitly out of scope for 005.

2. **LEAD_RUNTIME not in REQUIRED_COMPLETED_RUN_ROLES**: The trace coverage validator does not require `LEAD_RUNTIME` events. This is intentional to avoid breaking tests that depend on the exact role set.

3. **`_trace_agent()` duplicates some `_TraceRecorder` logic**: The runtime has its own trace helpers that overlap with the harness's `_TraceRecorder`. This is acceptable for now — the runtime needs to work independently of the harness in future iterations.

4. **LLM mode detection uses `hasattr`**: Instead of `isinstance(LLMWriter)`/`isinstance(LLMVerifier)` checks (which would create circular imports in the runtime module), the runtime uses `hasattr(self._writer, '_provider')` heuristics. The LLM token usage recording in finalize_run also uses `try/except AttributeError`.

5. **EvidenceStore created twice per run**: Once in `run_research_subagents()` (inside `LeadResearchAgent`) and again in `verify_report()`/`critique_report()`/`finalize_run()` (to read back evidence). This is consistent with 004 behavior.

6. **No `run_pipeline()` early return on all-failure in CLI path**: The orchestrator calls individual step methods (not `run_pipeline()`) to interleave artifact file writing. The all-failure check is in the orchestrator, not inside a single `run_pipeline()` call.

## Boundary with 004

| Concern | 004 | 005 |
|---------|-----|-----|
| Research dispatch | `LeadResearchAgent` + `SubagentExecutor` | Reuses via `run_research_subagents()` |
| RESEARCH_LEAD events | Recorded by `LeadResearchAgent` | Unchanged |
| RESEARCH_SUBAGENT events | Recorded by `LeadResearchAgent` | Unchanged |
| Evidence dedup + ID assignment | `LeadResearchAgent.conduct_research()` | Unchanged |
| Concurrency | `ThreadPoolExecutor` in `SubagentExecutor` | Unchanged |
| Pipeline orchestration | Monolithic `_run_with_provider()` | Delegated to `LeadAgentRuntime` steps |
| Trace events | Per-agent START/FINISH only | Added LEAD_RUNTIME wrapper events |

## Recommendation for Next Phase

**Can proceed to next phase.** The implementation is stable:
- All 323 non-LLM tests pass
- 5/5 fixture eval cases pass
- CLI contract unchanged
- Trace shows full execution chain
- 004 research subagent features fully preserved

Suggested next steps (006+):
1. **Iterative pipeline**: React to `CritiqueResult.next_phase` to loop back to research when gaps are found
2. **Human-in-the-loop**: Optional pause/approve between runtime steps
3. **LLM tool calling**: Real LLM function calling for the lead agent to decide which step to run next
4. **Extract `_TraceRecorder`**: Share trace recording logic between harness and runtime
