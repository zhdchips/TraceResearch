# speckit.eval

Run the evaluation phase for an AI application developed with Spec Kit.

## Language Policy

- Use English section headings and stable machine-readable keys.
- Use Chinese for explanatory body text when writing project artifacts.
- Keep AI / Agent technical terms in English, such as `Evidence Store`, `Planner`, `Researcher`, `Verifier`, `Critic`, `Writer`, `Faithfulness`, `Citation Completeness`, `Planner Coverage`, `Trace`, and `Eval Harness`.
- Use English for metric names, YAML keys, JSON keys, file paths, commands, IDs, and code symbols.

## Goal

Determine whether the implemented system behavior is good enough using explicit cases, metrics, traces, and bad-case analysis. Do not treat successful code execution as sufficient for AI application quality.

## Inputs

Use the active feature passed by the user, or infer the current active feature under `specs/`.

Read these artifacts when present:

- `specs/<feature>/spec.md`
- `specs/<feature>/plan.md`
- `specs/<feature>/tasks.md`
- `specs/<feature>/eval.md`
- implementation code
- tests
- trace logs
- existing eval result files

## Responsibilities

1. Identify the behavior that must be evaluated from `spec.md` and `plan.md`.
2. Run available tests, eval commands, or demo scripts.
3. If no eval runner exists, create or update `specs/<feature>/eval.md` with a minimal runnable evaluation plan.
4. If an eval runner exists, run it and summarize the result.
5. Save durable eval output under `eval/results/` when practical.
6. Capture bad cases with root-cause hypotheses.
7. Do not implement feature code unless the user explicitly asks.

## Deep Research Multi-Agent Evaluation Dimensions

For Deep Research / multi-agent systems, evaluate:

- Planner coverage: whether the planner decomposes the query into necessary research dimensions.
- Research diversity: whether researchers search from multiple useful angles.
- Source relevance: whether gathered sources directly support the task.
- Source authority: whether official docs, papers, primary sources, or reputable sources are preferred.
- Evidence grounding: whether important claims in the final report are backed by evidence.
- Citation completeness: whether key conclusions include citations or evidence IDs.
- Faithfulness: whether the report avoids claims not present in the evidence store.
- Critic usefulness: whether verifier/critic feedback catches missing views, weak sources, or unsupported claims.
- Context behavior: whether summarization, compression, or sub-agent isolation loses important task state.
- Cost and latency: tool calls, token usage, retries, and runtime where available.

## Minimum Eval Artifact

Ensure `specs/<feature>/eval.md` contains at least:

```md
# Eval Plan

> Language Policy: English headings, Chinese explanatory body, English AI/Agent terms and machine-readable keys.

## Scope

## Metrics

## Cases

## Commands

## Latest Result

## Bad Cases

## Next Review Focus
```

## Suggested Metric Names

Use simple numeric or pass/fail metrics first:

- `case_pass_rate`
- `planner_coverage`
- `source_relevance`
- `source_authority`
- `citation_completeness`
- `faithfulness`
- `unsupported_claim_count`
- `critical_hallucination_count`
- `avg_latency_seconds`
- `total_tool_calls`

## Completion Rules

If evaluation cannot be run, explain exactly why and create the missing eval task in `tasks.md` or `eval.md`.

If evaluation can be run, record:

- command
- result
- metrics
- failed cases
- suspected root causes
- recommended review focus

## Final Response Format

End with:

```text
Eval summary:
- Feature: <feature>
- Commands run: <commands or none>
- Result files: <paths>
- Pass/fail summary: <summary>
- Key bad cases: <summary>
- Recommended review focus: <summary>
```
