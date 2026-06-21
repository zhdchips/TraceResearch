# Plan: 007 Context Engineering

## Implementation Steps

### 1. Create context_engineering.py module

Define data classes:
- ContextBudget
- EvidenceContext
- CritiqueContext
- ContextPack

### 2. Implement context pack builders

Each builder takes the relevant state objects and produces a ContextPack with budget compliance.

### 3. Wire into RuntimeState (optional)

Add `latest_context_pack` to RuntimeState (non-breaking).

### 4. Tests

- Context pack doesn't lose evidence_id
- Budget enforcement (max_evidence_items, max_chars_per_evidence, max_total_chars)
- Long text truncation
- Critique next_phase preserved
- Context pack serializable

## Files to Create/Change

- `traceresearch/agents/context_engineering.py` — new
- `tests/unit/test_context_engineering.py` — new
- `traceresearch/agents/lead_runtime.py` — optional wire-in (add latest_context_pack to RuntimeState)

## Dependencies

- 006 Iterative Lead Runtime
- Evidence models (Evidence, CritiqueResult, etc.)
