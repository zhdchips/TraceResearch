# 005 Lead Agent Runtime — Quickstart

## What Changed

The pipeline orchestration moved from `ResearchHarness._run_with_provider()` (monolithic method) to `LeadAgentRuntime` (step-based runtime).

**No CLI changes.** `traceresearch run` and `traceresearch eval` work exactly as before.

## Key New Types

### RuntimeState
```python
from traceresearch.agents.lead_runtime import RuntimeState

state = RuntimeState(
    run_id="run-abc123",
    run_dir="/tmp/runs/run-abc123",
    trace_writer=trace_writer,
)
```

### LeadAgentRuntime
```python
from traceresearch.agents.lead_runtime import LeadAgentRuntime

runtime = LeadAgentRuntime(state=state)
state = runtime.run_pipeline(query="...", provider=provider)
```

## Trace Events

Each runtime step now records `LeadRuntime` events:
```json
{"agent_role": "LeadRuntime", "event_type": "start", "tool_name": "plan_research"}
{"agent_role": "LeadRuntime", "event_type": "tool_call", "tool_name": "plan_research"}
{"agent_role": "LeadRuntime", "event_type": "tool_result", "tool_name": "plan_research"}
{"agent_role": "LeadRuntime", "event_type": "finish", "tool_name": "plan_research"}
```

## Running Tests

```bash
# All non-LLM tests
python3 -m pytest -m "not llm_smoke" -q

# Just runtime tests
python3 -m pytest tests/unit/test_lead_agent_runtime.py -q
python3 -m pytest tests/integration/test_lead_runtime_integration.py -q

# Fixture eval
python3 -m traceresearch eval --cases-dir eval/cases --source-provider fixture --results-dir eval/results
```
