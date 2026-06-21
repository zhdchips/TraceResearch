# 005 Lead Agent Runtime — Tasks

## Phase 0: Trace Model Update (P0)

### T001: Add LEAD_RUNTIME to AgentRole enum
- **File**: `traceresearch/trace/models.py`
- **Change**: Add `LEAD_RUNTIME = "LeadRuntime"` to `AgentRole` enum
- **DoD**: `AgentRole.LEAD_RUNTIME` exists, all existing tests pass
- **Related**: FR-007

## Phase 1: Core Runtime Implementation (P0)

### T002: Create RuntimeState dataclass
- **File**: `traceresearch/agents/lead_runtime.py` (new)
- **Content**: `RuntimeState` dataclass with all required fields
- **Fields**: `run_id`, `run_dir`, `trace_writer`, `research_brief`, `planned_tasks`, `evidence`, `failed_task_ids`, `draft_report`, `verification_result`, `critique_result`, `final_report`, `status`
- **DoD**: Dataclass creatable with defaults, all fields accessible

### T003: Create LeadAgentRuntime class skeleton
- **File**: `traceresearch/agents/lead_runtime.py`
- **Content**: Class with constructor accepting state + injected agents
- **DoD**: Class instantiates, holds references to all agents and state

### T004: Implement _trace_step() helper
- **File**: `traceresearch/agents/lead_runtime.py`
- **Content**: Private method that creates and appends TraceEvent using state.trace_writer
- **DoD**: Trace events recorded with correct agent_role, event_type, tool_name

### T005: Implement plan_research step
- **File**: `traceresearch/agents/lead_runtime.py`
- **Content**: Records 4 trace events, calls Planner.plan(), updates RuntimeState
- **DoD**: Step produces research_brief in state, records LEAD_RUNTIME trace events

### T006: Implement run_research_subagents step
- **File**: `traceresearch/agents/lead_runtime.py`
- **Content**: Records trace events, calls LeadResearchAgent.conduct_research(), updates state with evidence and failed_task_ids
- **DoD**: Reuses 004 code, records LEAD_RUNTIME trace events, RESEARCH_LEAD events preserved

### T007: Implement write_report step
- **File**: `traceresearch/agents/lead_runtime.py`
- **Content**: Records trace events, calls Writer.draft(), updates state
- **DoD**: State has draft_report, LEAD_RUNTIME trace events recorded

### T008: Implement verify_report step
- **File**: `traceresearch/agents/lead_runtime.py`
- **Content**: Records trace events, calls Verifier.verify(), updates EvidenceStore statuses, updates state
- **DoD**: State has verification_result, EvidenceStore updated, LEAD_RUNTIME trace events

### T009: Implement critique_report step
- **File**: `traceresearch/agents/lead_runtime.py`
- **Content**: Records trace events, calls Critic.review(), updates state
- **DoD**: State has critique_result, LEAD_RUNTIME trace events

### T010: Implement finalize_run step
- **File**: `traceresearch/agents/lead_runtime.py`
- **Content**: Records trace events, calls Writer.final(), updates state
- **DoD**: State has final_report, LEAD_RUNTIME trace events

### T011: Implement run_pipeline() method
- **File**: `traceresearch/agents/lead_runtime.py`
- **Content**: Runs all 6 steps in sequence, handles early returns
- **DoD**: Full pipeline runs end-to-end

## Phase 2: Orchestrator Refactoring (P0)

### T012: Refactor _run_with_provider() to use LeadAgentRuntime
- **File**: `traceresearch/harness/orchestrator.py`
- **Change**: Replace inline agent calls with LeadAgentRuntime construction + run_pipeline()
- **Preserve**: HARNESS trace events, trace coverage validation, artifact writing, RunResult construction
- **DoD**: Same behavior, thinner method

### T013: Update agents/__init__.py exports
- **File**: `traceresearch/agents/__init__.py`
- **Change**: Add exports for LeadAgentRuntime, RuntimeState
- **DoD**: `from traceresearch.agents import LeadAgentRuntime` works

## Phase 3: Unit Tests (P0)

### T014: Test RuntimeState
- **File**: `tests/unit/test_lead_agent_runtime.py` (new)
- **Tests**: Creation, defaults, field mutation, JSON serialization
- **DoD**: Tests pass

### T015: Test LeadAgentRuntime initialization
- **File**: `tests/unit/test_lead_agent_runtime.py`
- **Tests**: Constructor with defaults, with injected agents, with trace_writer
- **DoD**: Tests pass

### T016: Test plan_research step
- **File**: `tests/unit/test_lead_agent_runtime.py`
- **Tests**: Calls planner, updates state, records trace, handles NEEDS_CLARIFICATION
- **DoD**: Tests pass

### T017: Test run_research_subagents step
- **File**: `tests/unit/test_lead_agent_runtime.py`
- **Tests**: Calls LeadResearchAgent, updates state with evidence, handles failures
- **DoD**: Tests pass

### T018: Test remaining steps
- **File**: `tests/unit/test_lead_agent_runtime.py`
- **Tests**: write_report, verify_report, critique_report, finalize_run
- **DoD**: Tests pass

### T019: Test run_pipeline full flow
- **File**: `tests/unit/test_lead_agent_runtime.py`
- **Tests**: End-to-end with mocked agents, trace events contain full chain
- **DoD**: Tests pass

### T020: Test error handling
- **File**: `tests/unit/test_lead_agent_runtime.py`
- **Tests**: Step failure records FAILED trace, error info propagated
- **DoD**: Tests pass

## Phase 4: Integration Tests (P0)

### T021: Integration test — full fixture run
- **File**: `tests/integration/test_lead_runtime_integration.py` (new)
- **Tests**: Full pipeline with fixture provider, evidence produced, report written
- **DoD**: Test passes

### T022: Integration test — trace chain
- **File**: `tests/integration/test_lead_runtime_integration.py`
- **Tests**: Trace contains LEAD_RUNTIME events, RESEARCH_LEAD events, RESEARCH_SUBAGENT events
- **DoD**: Test passes

### T023: Integration test — 004 regression
- **File**: `tests/integration/test_lead_runtime_integration.py`
- **Tests**: Existing subagent events still present, evidence IDs stable
- **DoD**: Test passes

## Phase 5: Verification (P0)

### T024: Run full test suite
- **Command**: `python3 -m pytest -m "not llm_smoke" -q`
- **DoD**: All tests pass

### T025: Run fixture eval
- **Command**: `python3 -m traceresearch eval --cases-dir eval/cases --source-provider fixture --results-dir eval/results`
- **DoD**: 5/5 cases pass

### T026: Write review.md
- **File**: `specs/005-lead-agent-runtime/review.md`
- **Content**: Completed items, test results, known limitations, 004 boundary, next phase recommendation
- **DoD**: Documented
