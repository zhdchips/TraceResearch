# 007 Context Engineering

## Feature Summary

Introduce structured context packs to define stable boundaries between what the Lead Agent sees and internal agent state, preparing for future tool-calling while avoiding unbounded prompt growth.

## Motivation

Currently there is no explicit separation between "what the Lead Agent sees" vs "what the subagent receives." Without formal context structures, future LLM-based Lead Agents risk receiving thousands of tokens of raw Evidence/Verification objects. Context packs enforce budgets and structural constraints.

## Design

### ContextPack and StepContext

```python
@dataclass
class ContextPack:
    step: str  # "planning", "research", "writing", "verification", "critique", "decision"
    evidence: list[EvidenceContext]  # compressed evidence view
    critique: CritiqueContext | None
    budget: ContextBudget
    metadata: dict

@dataclass
class EvidenceContext:
    evidence_id: str
    source_title: str
    source_publisher: str | None
    source_url: str | None
    summary: str
    key_points: list[str]
    limitations: list[str]
    # Truncated versions for budget compliance
```

### Context Pack Builders

- `build_planning_context(brief, tasks)` → ContextPack
- `build_research_context(evidence, tasks)` → ContextPack
- `build_writing_context(evidence, draft)` → ContextPack
- `build_verification_context(verification, evidence)` → ContextPack
- `build_critique_context(critique, evidence)` → ContextPack
- `build_lead_decision_context(state)` → ContextPack

### Budget

- `max_evidence_items` — cap on evidence count (default 20)
- `max_chars_per_evidence` — cap on text per evidence item (default 500)
- `max_total_chars` — total character budget (default 8000)

### Evidence Summary Compression

- Preserve: evidence_id, source title/publisher/url, summary, key_points, limitations
- Truncate: long summary text to max_chars_per_evidence

### Critique Context Preservation

- Must preserve: decision, next_phase, missing_perspectives, limitations, failed_task_ids

### Constraints

- No real LLM calls
- No embeddings
- No vector store
- Serializable to dict for potential JSON output
