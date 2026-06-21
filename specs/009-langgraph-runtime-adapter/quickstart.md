# 009 LangGraph Runtime Adapter — Quickstart

## Prerequisites

```bash
pip install langgraph>=0.2
```

## Run with LangGraph Mode

```bash
# Set the mode to langgraph
export TRACERESEARCH_LEAD_AGENT_MODE=langgraph

# Run a fixture-based research
traceresearch run "What are the latest developments in AI agent architectures?" \
  --source-provider fixture \
  --output-dir output/langgraph_demo

# Or run evaluation with langgraph mode
traceresearch eval \
  --cases-dir eval/cases \
  --source-provider fixture \
  --results-dir eval/results_langgraph
```

## Expected Output

Same artifact structure as `runtime` mode:

```
output/langgraph_demo/<run-id>/
├── research_brief.json
├── research_tasks.json
├── evidence.jsonl
├── outline.md
├── draft_report.md
├── verification.json
├── critique.json
├── final_report.md
├── report.json
└── trace.jsonl
```

## Trace Inspection

LangGraph mode adds `LANGGRAPH` agent role events to `trace.jsonl`:

```bash
# Find graph transition events
cat output/langgraph_demo/<run-id>/trace.jsonl | python3 -c "
import sys, json
for line in sys.stdin:
    e = json.loads(line)
    if e['agent_role'] == 'LangGraph':
        print(f\"{e['event_type']:12s} {e['input_summary']:60s} → {e['output_summary']}\")
"
```

## Switch Between Modes

```bash
# Classic runtime (default)
TRACERESEARCH_LEAD_AGENT_MODE=runtime traceresearch run "..."

# Tool controller (008)
TRACERESEARCH_LEAD_AGENT_MODE=tool_controller traceresearch run "..."

# LangGraph (009)
TRACERESEARCH_LEAD_AGENT_MODE=langgraph traceresearch run "..."
```

## Verify No Regression

```bash
# All non-LLM tests
pytest -m "not llm_smoke" -q

# Specific langgraph tests
pytest tests/unit/test_lead_graph_runtime.py tests/integration/test_langgraph_integration.py -v
```
