# Tasks: 007 Context Engineering

## 007-1: Define context data structures

- ContextBudget (max_evidence_items, max_chars_per_evidence, max_total_chars)
- EvidenceContext (compressed evidence)
- CritiqueContext (preserved critique fields)
- ContextPack (step + evidence + critique + budget + metadata)

## 007-2: Implement context pack builders

- build_planning_context
- build_research_context
- build_writing_context
- build_verification_context
- build_critique_context
- build_lead_decision_context

## 007-3: Add budget enforcement

- max_evidence_items cap
- Truncate summary to max_chars_per_evidence
- Enforce max_total_chars

## 007-4: Wire into RuntimeState (optional)

Add latest_context_pack to RuntimeState

## 007-5: Write tests

- EvidenceContext preserves evidence_id
- Budget caps evidence items
- Long text truncated
- Critique next_phase preserved
- ContextPack serializable (to_dict)
