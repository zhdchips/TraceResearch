# 009 LangGraph Runtime Adapter — Tasks

## Phase 1: Spec & Docs (task-001)

- [x] T001: Create spec.md, plan.md, tasks.md, quickstart.md, review.md, interview.md, resume.md

## Phase 2: Dependencies & Models (task-002)

- [ ] T002: Add `langgraph>=0.2` to `pyproject.toml` dependencies
- [ ] T003: Add `LANGGRAPH = "LangGraph"` to `AgentRole` in `trace/models.py`
- [ ] T004: Create `traceresearch/agents/graph_state.py` with `GraphState` TypedDict and helpers

## Phase 3: Core Implementation (task-003)

- [ ] T005: Create `traceresearch/agents/lead_graph_runtime.py` with:
  - `LeadGraphRuntime` class
  - 6 node functions (plan, research, write, verify, critique, finalize)
  - 3 conditional routing functions (after_plan, after_research, after_critique)
  - Graph builder (`_build_graph()`)
  - Trace integration (node start/finish, edge decisions)

## Phase 4: Harness Integration (task-004)

- [ ] T006: Extend `_read_lead_agent_mode()` to include `"langgraph"`
- [ ] T007: Add `_run_langgraph_path()` to `ResearchHarness`
- [ ] T008: Wire langgraph mode in `_run_with_provider()` branch

## Phase 5: Observability (task-005)

- [ ] T009: Each node writes LANGGRAPH START/FINISH trace events
- [ ] T010: Each conditional edge writes LANGGRAPH TOOL_RESULT with decision metadata
- [ ] T011: Graph state → trace event mapping documented

## Phase 6: Tests (task-006)

- [ ] T012: Create `tests/unit/test_graph_state.py`
- [ ] T013: Create `tests/unit/test_lead_graph_runtime.py`
- [ ] T014: Create `tests/integration/test_langgraph_integration.py`

## Phase 7: Verification (task-007)

- [ ] T015: Run `pytest -m "not llm_smoke" -q` — all existing + new tests pass
- [ ] T016: Run `traceresearch eval` — no regression
- [ ] T017: Verify langgraph mode produces all 10 artifacts
