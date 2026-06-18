# AI Eval Review Extension

This local Spec Kit extension adds two post-implementation phases for AI application development:

- `speckit.eval`: evaluates behavior with cases, metrics, traces, and bad-case analysis.
- `speckit.review`: reviews implementation against SDD artifacts and decides the next phase.

It is designed for Deep Research / multi-agent applications where "code compiles" is not enough. The system should also prove evidence grounding, citation completeness, task coverage, and hallucination control.

## Install

From a Spec Kit project root:

```bash
specify extension add --dev tools/speckit-ai-eval-review
specify extension list
```

If this extension lives outside the project, pass its absolute path:

```bash
specify extension add --dev /absolute/path/to/tools/speckit-ai-eval-review
```

## Commands

Most slash-command integrations expose:

```text
/speckit.eval
/speckit.review
```

Codex skills-mode integrations may expose equivalent skills such as:

```text
$speckit-eval
$speckit-review
```

## Suggested Workflow

Run the local workflow file:

```bash
specify workflow run tools/speckit-ai-eval-review/workflows/ai-app-cycle.yml -i feature=001-deep-research-multi-agent
```

The workflow executes:

```text
implement -> eval -> review -> human gate -> plan
```

Reject the human gate if `review.md` says the feature is complete or paused.

## Optional Spec Kit Template Overrides

This extension also ships opinionated templates for AI application artifacts:

```text
templates/spec-template.md
templates/plan-template.md
templates/tasks-template.md
```

To make a project use them as Spec Kit project-local overrides, copy them into:

```bash
mkdir -p .specify/templates/overrides
cp tools/speckit-ai-eval-review/templates/spec-template.md .specify/templates/overrides/spec-template.md
cp tools/speckit-ai-eval-review/templates/plan-template.md .specify/templates/overrides/plan-template.md
cp tools/speckit-ai-eval-review/templates/tasks-template.md .specify/templates/overrides/tasks-template.md
```

If the extension is stored outside the project, replace `tools/speckit-ai-eval-review` with its absolute path.

The templates enforce:

- English headings
- Chinese explanatory body
- English AI / Agent technical terms
- English metric names, YAML keys, file paths, commands, and IDs
