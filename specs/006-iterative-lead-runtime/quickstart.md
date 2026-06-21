# Quickstart: 006 Iterative Lead Runtime

## Enable iterations

```bash
export TRACERESEARCH_MAX_RUNTIME_ITERATIONS=3
```

## Run pipeline

```python
from traceresearch.agents.lead_runtime import LeadAgentRuntime, RuntimeState

state = RuntimeState(run_id="r1", run_dir="/tmp/r1", max_iterations=3)
runtime = LeadAgentRuntime(state=state)
state = runtime.run_pipeline(query="...", provider=provider)
```

## Test

```bash
pytest tests/unit/test_lead_runtime_iterations.py -v
pytest tests/integration/test_iterative_runtime_integration.py -v
```
