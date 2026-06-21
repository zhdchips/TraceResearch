# Quickstart: 007 Context Engineering

## Build a context pack

```python
from traceresearch.agents.context_engineering import (
    build_research_context,
    build_critique_context,
    ContextPack,
)

# Compress evidence for LLM context
pack = build_research_context(evidence, tasks)

# Preserve critique decision in context
critique_pack = build_critique_context(critique_result)

# Check budget
print(pack.budget)
# ContextBudget(max_evidence_items=20, max_chars_per_evidence=500, max_total_chars=8000)
```

## Test

```bash
pytest tests/unit/test_context_engineering.py -v
```
