# speckit.review

Run the post-implementation review phase for a Spec Kit feature.

## Language Policy

- Use English section headings and stable machine-readable keys.
- Use Chinese for explanatory body text when writing project artifacts.
- Keep AI / Agent technical terms in English, such as `Evidence Store`, `Planner`, `Researcher`, `Verifier`, `Critic`, `Writer`, `Faithfulness`, `Citation Completeness`, `Planner Coverage`, `Trace`, and `Eval Harness`.
- Use English for metric names, YAML keys, JSON keys, file paths, commands, IDs, and code symbols.

## Goal

Review whether the implementation satisfies the SDD artifacts and whether the latest eval results justify completing the current iteration. The output must decide whether to complete, pause, or continue, and if continuing, which phase to return to.

## Inputs

Use the active feature passed by the user, or infer the current active feature under `specs/`.

Read these artifacts when present:

- `specs/<feature>/spec.md`
- `specs/<feature>/plan.md`
- `specs/<feature>/tasks.md`
- `specs/<feature>/eval.md`
- latest files under `eval/results/`
- git diff
- test output if available
- implementation code related to completed tasks

## Responsibilities

1. Check implementation against `spec.md` acceptance criteria.
2. Check implementation against `plan.md` architecture and design decisions.
3. Check `tasks.md` completion state and whether task DoD is satisfied.
4. Summarize tests and eval results.
5. Identify bad cases, regressions, and technical debt.
6. Classify findings as:
   - implementation issue
   - plan/design issue
   - spec/requirement issue
   - eval/test coverage issue
   - known limitation
7. Decide the next phase.
8. Update `specs/<feature>/review.md`.

## Exit Criteria

Set `decision: complete` only when all are true:

- all must-have acceptance criteria in `spec.md` are satisfied
- all P0/P1 tasks in `tasks.md` are complete
- tests pass, or any missing tests are explicitly justified as non-blocking
- eval meets configured thresholds in `eval.md`
- no P0/P1 review findings remain
- remaining issues are documented as known limitations or future enhancements

Set `decision: pause` when a human product/architecture decision is required before continuing.

Set `decision: continue` when the feature needs another iteration.

## Next Phase Rule

When `decision: continue`, choose:

- `tasks`: local implementation gaps only, with no design change required
- `plan`: design, architecture, agent boundary, evidence schema, trace, eval strategy, context engineering, or verifier strategy issues
- `spec`: requirement, scope, user story, or acceptance criteria changes

For Deep Research / multi-agent work, default to `plan` after review when the eval failure is caused by weak decomposition, evidence grounding, source scoring, verifier behavior, context loss, trace design, or report-generation policy.

## Review Artifact Format

Update `specs/<feature>/review.md` using this structure:

```md
# Review

> Language Policy: English headings, Chinese explanatory body, English AI/Agent terms and machine-readable keys.

## Scope

## Spec Compliance

## Plan Compliance

## Task Completion

## Verification Summary

## Eval Summary

## Findings

## Bad Cases

## Root Cause Analysis

## Known Limitations

## Next Actions

## Decision

```yaml
decision: continue | complete | pause
next_phase: spec | plan | tasks | none
reason: "<short reason>"
plan_update_prompt: "<concrete prompt for /speckit.plan, empty unless next_phase is plan>"
tasks_update_prompt: "<concrete prompt for /speckit.tasks, empty unless next_phase is tasks>"
spec_update_prompt: "<concrete prompt for /speckit.specify or manual spec update, empty unless next_phase is spec>"
```
```

## Required Behavior

If the latest eval result is missing, do not mark the feature complete. Set:

```yaml
decision: continue
next_phase: tasks
reason: "No eval result exists; add or run eval before completion."
```

If the latest eval result shows evidence grounding, citation completeness, or hallucination failures in Deep Research output, prefer:

```yaml
decision: continue
next_phase: plan
reason: "Eval failure requires design update for evidence/verifier/context flow."
```

If the feature is complete, set:

```yaml
decision: complete
next_phase: none
reason: "Acceptance criteria, tests, and eval thresholds are satisfied."
```

## Final Response Format

End with:

```text
Review summary:
- Feature: <feature>
- Decision: <continue|complete|pause>
- Next phase: <spec|plan|tasks|none>
- Review file: specs/<feature>/review.md
- Reason: <short reason>
```
