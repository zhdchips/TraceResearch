# 005 Lead Agent Runtime — Implementation Plan

## Architecture

### Before (004)

```
CLI → ResearchHarness._run_with_provider() [monolithic ~250 lines]
       ├─ Planner.plan()
       ├─ LeadResearchAgent.conduct_research()
       ├─ Writer.draft()
       ├─ Verifier.verify()
       ├─ Critic.review()
       └─ Writer.final()
```

### After (005)

```
CLI → ResearchHarness._run_with_provider() [thin ~80 lines]
       ├─ construct RuntimeState
       ├─ construct LeadAgentRuntime
       └─ runtime.run_pipeline()
            ├─ plan_research        [LEAD_RUNTIME trace events]
            │    └─ Planner.plan()  [PLANNER trace events]
            ├─ run_research_subagents  [LEAD_RUNTIME trace events]
            │    └─ LeadResearchAgent.conduct_research()  [RESEARCH_LEAD + RESEARCH_SUBAGENT events]
            ├─ write_report         [LEAD_RUNTIME trace events]
            │    └─ Writer.draft()  [WRITER trace events]
            ├─ verify_report        [LEAD_RUNTIME trace events]
            │    └─ Verifier.verify() [VERIFIER trace events]
            ├─ critique_report      [LEAD_RUNTIME trace events]
            │    └─ Critic.review() [CRITIC trace events]
            └─ finalize_run         [LEAD_RUNTIME trace events]
                 └─ Writer.final()  [WRITER trace events]
```

## Module Layout

### New Files
```
traceresearch/agents/lead_runtime.py     # LeadAgentRuntime + RuntimeState + RunContext
tests/unit/test_lead_agent_runtime.py    # Unit tests
tests/integration/test_lead_runtime_integration.py  # Integration tests
specs/005-lead-agent-runtime/            # Spec artifacts
```

### Modified Files
```
traceresearch/harness/orchestrator.py    # Thinner, delegates to LeadAgentRuntime
traceresearch/agents/__init__.py         # Add exports
traceresearch/trace/models.py            # Add LEAD_RUNTIME to AgentRole
```

## Data Flow

```
RuntimeState (mutable, passed through steps)
  ┌─────────────────────────────────────┐
  │ run_id, run_dir, trace_writer       │ ← set at construction
  │ research_brief                      │ ← set by plan_research()
  │ evidence, failed_task_ids           │ ← set by run_research_subagents()
  │ draft_report                        │ ← set by write_report()
  │ verification_result                  │ ← set by verify_report()
  │ critique_result                     │ ← set by critique_report()
  │ final_report                        │ ← set by finalize_run()
  │ status                              │ ← updated each step
  └─────────────────────────────────────┘
```

## Trace Design

### AgentRole Addition
```python
class AgentRole(StrEnum):
    ...
    LEAD_RUNTIME = "LeadRuntime"   # NEW
```

### Step Lifecycle Events
Each step records 4 events:
1. `START` — step begins, `input_summary` = what's being done
2. `TOOL_CALL` — about to call internal agent, `input_summary` = agent name + args summary
3. `TOOL_RESULT` — internal agent returned, `output_summary` = result summary
4. `FINISH` — step complete, `status` = SUCCESS/FAILED/NEEDS_CLARIFICATION

### Example Trace (plan_research step)
```json
{"agent_role": "LeadRuntime", "event_type": "start", "tool_name": "plan_research", ...}
{"agent_role": "LeadRuntime", "event_type": "tool_call", "tool_name": "plan_research", "input_summary": "calling Planner.plan", ...}
{"agent_role": "Planner", "event_type": "start", ...}
{"agent_role": "Planner", "event_type": "finish", ...}
{"agent_role": "LeadRuntime", "event_type": "tool_result", "tool_name": "plan_research", "output_summary": "created N research tasks", ...}
{"agent_role": "LeadRuntime", "event_type": "finish", "tool_name": "plan_research", ...}
```

### NOT Modified
- `REQUIRED_COMPLETED_RUN_ROLES` does NOT include `LEAD_RUNTIME` — keeps existing trace validation unchanged.
- 004's `RESEARCH_LEAD` and `RESEARCH_SUBAGENT` events are untouched.

## Test Strategy

### Unit Tests (test_lead_agent_runtime.py)
1. `RuntimeState` creation, defaults, field access
2. `LeadAgentRuntime` initialization with injected agents
3. `plan_research` step — calls planner, updates state, records trace
4. `run_research_subagents` step — calls lead_researcher, updates state
5. `write_report` step — calls writer.draft(), updates state
6. `verify_report` step — calls verifier.verify(), updates EvidenceStore
7. `critique_report` step — calls critic.review(), updates state
8. `finalize_run` step — calls writer.final(), updates state
9. `run_pipeline` full flow
10. Trace events contain LEAD_RUNTIME role and correct step names
11. Error handling — step failure records FAILED status
12. Early return on NEEDS_CLARIFICATION
13. Early return on all-tasks-failed

### Integration Tests (test_lead_runtime_integration.py)
1. Full pipeline with fixture provider — produces evidence, report
2. Trace events show LEAD_RUNTIME wrapping internal agents
3. 004 regression — subagent events still present

### Existing Test Preservation
- All `tests/unit/` tests pass unchanged
- All `tests/integration/` tests pass unchanged (some may need minor updates if they depend on orchestrator internals)
- `tests/eval/` tests pass unchanged

## Implementation Tasks

See `tasks.md` for detailed breakdown.

## Design Caveats

1. **RuntimeState is mutable** — steps update state in place. This is simpler than immutable state threading and matches the synchronous single-runtime constraint.
2. **No lead_runtime.py in harness/** — placed in `agents/` to colocate with other agent code. The harness imports it.
3. **_TraceRecorder stays in orchestrator** — the runtime uses its own `_trace_step()` helper. The harness's `_TraceRecorder` remains for HARNESS-level events.
4. **EvidenceStore creation moves to runtime** — `verify_report()` creates `EvidenceStore` from `state.run_dir` to update evidence statuses after verification.
5. **LEAD_RUNTIME not in REQUIRED_COMPLETED_RUN_ROLES** — this avoids breaking existing trace validation tests. LEAD_RUNTIME events are an enhancement, not a coverage requirement.
