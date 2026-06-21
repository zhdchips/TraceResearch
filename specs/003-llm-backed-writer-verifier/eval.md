# Eval Report: LLM-Backed Writer / Verifier

**Feature**: 003-llm-backed-writer-verifier
**Date**: 2026-06-21
**Eval Run**: eval-20260621071226-4feaaa01

## Fixture Eval Regression

| Metric | Value |
|--------|-------|
| **Case pass rate** | 1.0 (5/5) |
| **Planner Coverage** | 1.0 (avg) |
| **Perspective Diversity** | 1.0 (avg) |
| **Source Relevance** | 0.912 (avg) |
| **Source Authority** | 0.848 (avg) |
| **Citation Completeness** | 1.0 (avg) |
| **Faithfulness** | 1.0 (avg) |
| **Unsupported Claim Count** | 0.0 (avg) |
| **Critical Hallucination Count** | 0.0 (avg) |

**Verdict**: ✅ All 5 seed cases pass. Output Determinism = 1.0. No regression from 002 baseline.

## Full Test Suite

| Command | Result |
|---------|--------|
| `python3 -m pytest` | 252 passed, 0 failed |
| `traceresearch eval` | 5/5 pass, case_pass_rate=1.0 |

LLM smoke tests (`tests/llm_smoke/`) are excluded from default pytest via `addopts = "-m 'not llm_smoke'"`.

## Live Web Provider Path

| Test | Result |
|------|--------|
| `traceresearch run --source-provider web --query "test"` | `status=failed, error_type=provider_not_configured` |
| Behavior matches 002 baseline | ✅ Unaffected by LLM config env vars |

## LLM Smoke Eval

| Item | Status |
|------|--------|
| LLM smoke eval infrastructure | ✅ `traceresearch llm-smoke` available |
| Deterministic baseline (no LLM key) | ✅ 3/3 cases pass |
| Real LLM smoke (with key) | ⏳ Not executed — requires DEEPSEEK_API_KEY |

### Manual LLM Smoke Run (when key available)

```bash
export DEEPSEEK_API_KEY="sk-..."
traceresearch llm-smoke
# Expected: 3 cases, LLM-backed smoke with faithfulness/citation/unsupported metrics
```

## Quality Gate Summary

| Gate | Status |
|------|--------|
| QG-001: `python3 -m pytest` 100% pass | ✅ 252/252 |
| QG-002: Fixture eval 5/5 pass | ✅ case_pass_rate=1.0 |
| QG-003: LLM smoke eval command available | ✅ |
| QG-004: LLM failover path verified | ✅ Mock tests pass |
| QG-005: Key claims bind evidence IDs | ✅ Unit + integration tests pass |
| QG-006: LLM smoke eval outputs metrics | ✅ |
| QG-007: Trace distinguishes LLM/deterministic | ✅ |
| QG-008: No real API key committed | ✅ |
