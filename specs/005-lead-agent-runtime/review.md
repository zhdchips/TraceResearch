# 005 Lead Agent Runtime — Review

**Date**: 2026-06-21  
**Branch**: 005-lead-agent-runtime

## Completed Items

### Phase 0: Trace Model
- [x] T001: Added `LEAD_RUNTIME = "LeadRuntime"` to `AgentRole` enum in `traceresearch/trace/models.py`

### Phase 1: Core Runtime
- [x] T002: Created `RuntimeState` dataclass with all required fields
- [x] T003: Created `LeadAgentRuntime` class with constructor accepting state + injected agents
- [x] T004: Implemented `_trace_step()` and `_trace_agent()` helpers
- [x] T005–T010: Implemented all 6 step methods (`plan_research`, `run_research_subagents`, `write_report`, `verify_report`, `critique_report`, `finalize_run`)
- [x] T011: Implemented `run_pipeline()` method with early-return for NEEDS_CLARIFICATION and all-tasks-failed

### Phase 2: Orchestrator Refactoring
- [x] T012: Refactored `_run_with_provider()` to construct `RuntimeState` + `LeadAgentRuntime` and delegate pipeline orchestration to the runtime's individual step methods (not `run_pipeline()`) — the orchestrator calls each step method separately so it can interleave artifact file writes between steps.
- [x] T013: Updated `traceresearch/agents/__init__.py` with exports for 005 types (`LeadAgentRuntime`, `RuntimeState`, `RunContext`) and 004 types (`LeadResearchAgent`, `ResearchTaskAgent`, `SubagentExecutor`, `CandidateEvidenceBatch`, `CompressedResearchContext`, `SubagentStatus`)

### Patch Notes (第二轮小修)

**1. Runtime step failure trace:**
- Each step method now wraps its core logic in try/except.
- On exception: records `LEAD_RUNTIME TOOL_RESULT` (FAILED) + `LEAD_RUNTIME FINISH` (FAILED) with `ErrorInfo(type=<class name>, message=str(exc))`, then re-raises.
- `run_research_subagents` detects all-tasks-failed internally (tasks present, zero evidence) and records FINISH with `status=FAILED` — `run_pipeline` checks `state.status` instead of duplicating the check.
- All 6 steps covered: plan_research, run_research_subagents, write_report, verify_report, critique_report, finalize_run.

**2. Package exports:**
- `traceresearch/agents/__init__.py` now exports both 004 and 005 types.
- `from traceresearch.agents import LeadResearchAgent, ResearchTaskAgent, SubagentExecutor` works.
- `from traceresearch.agents import CandidateEvidenceBatch, CompressedResearchContext, SubagentStatus` works.

**3. LLM observability mode detection:**
- Replaced `hasattr + writer_mode=="llm"` checks with instance-based `_resolve_llm_mode(agent)` helper.
- If the injected writer/verifier instance has `_provider` with `.model` → trace `llm_mode="llm"`, `llm_model=<model>`.
- Otherwise → trace `"deterministic"`.
- `writer_mode` / `verifier_mode` params are kept for backward compat but no longer gate LLM trace detection.
- Direct-injected `LLMWriter` / `LLMVerifier` instances are always traced as llm regardless of the mode string.

**4. Review/docs wording:**
- Clarified that the orchestrator calls runtime **individual step methods** (not `run_pipeline()`) to interleave artifact file writes.
- Added this patch notes section.
- Known Limitations updated.

### Phase 3: Unit Tests (45 tests)
- RuntimeState: 4 tests
- Init: 2 tests
- plan_research: 4 tests
- run_research_subagents: 3 tests
- write_report: 2 tests
- verify_report: 2 tests
- critique_report: 2 tests
- finalize_run: 2 tests
- run_pipeline: 4 tests
- Error handling: 1 test
- AgentRole regression: 2 tests
- **Step failure trace (new):** 6 tests — one per step, verifying FAILED FINISH + ErrorInfo + re-raise
- **All-tasks-failed trace (new):** 2 tests — run_research_subagents records FAILED internally
- **LLM mode detection (new):** 6 tests — _resolve_llm_mode, direct-injected LLMWriter/LLMVerifier trace override
- **Package exports (new):** 3 tests — 005 types, 004 types, 004 model types

### Phase 4: Integration Tests (12 tests)
- Full pipeline with fixture provider: 3 tests
- Trace chain verification: 3 tests
- 004 regression (subagent events, evidence IDs, partial failure): 4 tests
- CLI contract: 2 tests

## Test Results

### Targeted
```
tests/unit/test_lead_agent_runtime.py — 45 passed
tests/integration/test_lead_runtime_integration.py — 12 passed
tests/unit/test_trace_models.py — 14 passed
```

### Full Suite
```
python3 -m pytest -m "not llm_smoke" -q
340 passed, 5 deselected
```

One existing test was updated (`test_all_agent_roles_are_available`) to include `LeadRuntime`. No other existing tests were broken.

### Fixture Eval
```
traceresearch eval — 5/5 pass, case_pass_rate=1.00
```
| Case | Result |
|------|--------|
| 001-framework-comparison | PASS |
| 002-financial-grounding | PASS |
| 003-ai-coding-agent-trends | PASS |
| 004-openhands-runtime | PASS |
| 005-rag-2026 | PASS |

## Changes Summary

### New Files
| File | Lines | Purpose |
|------|-------|---------|
| `traceresearch/agents/lead_runtime.py` | ~660 | `LeadAgentRuntime`, `RuntimeState`, `RunContext`, `_resolve_llm_mode`, `_resolve_llm_token_usage` |
| `tests/unit/test_lead_agent_runtime.py` | ~1100 | 45 unit tests (28 original + 17 new) |
| `tests/integration/test_lead_runtime_integration.py` | ~340 | 12 integration tests |
| `specs/005-lead-agent-runtime/` | — | spec, plan, tasks, quickstart, review |

### Modified Files
| File | Change |
|------|--------|
| `traceresearch/trace/models.py` | Added `LEAD_RUNTIME` to `AgentRole` |
| `traceresearch/harness/orchestrator.py` | Refactored `_run_with_provider()` — calls runtime individual step methods |
| `traceresearch/agents/__init__.py` | Exports 005 + 004 types |
| `tests/unit/test_trace_models.py` | Updated `test_all_agent_roles_are_available` |

## Known Limitations

1. **No iteration loop**: `CritiqueResult.next_phase` exists but the runtime does not loop back — same as 004.
2. **LEAD_RUNTIME not in `REQUIRED_COMPLETED_RUN_ROLES`**: Intentional — avoids breaking trace coverage validation.
3. **Orchestrator uses individual step methods, not `run_pipeline()`**: The harness calls `runtime.plan_research()`, `runtime.run_research_subagents()`, etc. individually to interleave artifact file writes (`research_brief.json`, `outline.md`, `verification.json`, etc.). `run_pipeline()` exists for convenience but is not used in the main CLI path. This boundary is intentional.
4. **EvidenceStore created twice per run**: Once inside `LeadResearchAgent.conduct_research()` and again in `verify_report()`/`critique_report()`/`finalize_run()` for reading back. Consistent with 004.
5. **`_resolve_llm_mode` uses `hasattr`**: The detection relies on the presence of `_provider` with a `.model` attribute. This is reliable for the current `LLMWriter` / `LLMVerifier` implementations.

## Recommendation for Next Phase

**Can proceed to next phase.** All tests pass, no regressions. Suggested for 006+:
1. Iterative pipeline (react to `CritiqueResult.next_phase`)
2. Human-in-the-loop between steps
3. LLM tool calling for lead agent decisions
