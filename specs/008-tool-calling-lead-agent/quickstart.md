# Quickstart: 008 Tool-Calling Lead Agent

## Enable tool controller

```bash
export TRACERESEARCH_LEAD_AGENT_MODE=tool_controller
```

## Use tool controller

```python
from traceresearch.agents.runtime_tools import TOOL_REGISTRY
from traceresearch.agents.lead_tool_controller import LeadAgentToolController

controller = LeadAgentToolController(runtime=runtime, state=state)
state = controller.run_tool_loop(query="...", provider=provider)
```

## Test

```bash
pytest tests/unit/test_runtime_tools.py -v
pytest tests/unit/test_lead_tool_controller.py -v
pytest tests/integration/test_tool_controller_integration.py -v
```
