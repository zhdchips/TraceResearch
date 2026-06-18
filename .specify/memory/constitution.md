<!--
Sync Impact Report
Version change: template -> 1.0.0
Modified principles:
- Template Principle 1 -> Research Contract First
- Template Principle 2 -> Evidence-Grounded Output
- Template Principle 3 -> Traceable Agent Execution
- Template Principle 4 -> Context Isolation and Compression
- Template Principle 5 -> Eval-Gated Iteration
Added sections:
- Operational Constraints
- Development Workflow
Removed sections:
- None
Templates requiring updates:
- ✅ updated .specify/templates/plan-template.md
- ✅ updated .specify/templates/spec-template.md
- ✅ updated .specify/templates/tasks-template.md
- ✅ checked .specify/templates/overrides/plan-template.md
- ✅ checked .specify/templates/overrides/spec-template.md
- ✅ checked .specify/templates/overrides/tasks-template.md
- ✅ checked .specify/templates/commands/*.md (directory not present)
Runtime guidance:
- ✅ checked AGENTS.md
- ✅ checked references/AGENTS.md
- ✅ checked references/design-notes/*.md
Follow-up TODOs:
- None
-->

# TraceResearch Constitution

## Core Principles

### I. Research Contract First

Every research run MUST begin with a structured `research_brief` produced from the
user query before tool-based research or report writing starts. The brief MUST
capture the research objective, scope boundaries, required perspectives,
research tasks, success criteria, and open clarifications. If the request lacks
the research object, time range, or output goal, the system MUST ask for
clarification or record the assumption explicitly before continuing.

Rationale: Deep Research failures often start with an ambiguous task. A durable
research contract makes Planner quality reviewable and separates user intent
problems from Researcher, Verifier, Critic, or Writer failures.

### II. Evidence-Grounded Output

The Writer MUST generate final reports only from verified entries in the
`Evidence Store`. Each key claim, comparison, recommendation, and limitation in
the report MUST cite an evidence ID or source reference that can be traced back
to source metadata. Raw source content MUST NOT be passed directly to the Writer
as an unrestricted context dump. Unsupported claims MUST be rejected, marked as
unknown, or returned to research.

Rationale: The project exists to produce trustworthy research artifacts, not
plausible prose. Claim-level grounding and citation completeness are mandatory
quality properties.

### III. Traceable Agent Execution

Every agent step and tool call MUST emit trace records with `run_id`, `task_id`,
`agent_role`, `event_type`, `tool_name`, input summary, output summary, status,
latency, token usage when available, and error details when applicable. Trace
records MUST be durable enough to support bad-case replay, eval diagnosis, and
human review after the run completes.

Rationale: Multi-agent systems are difficult to debug from final output alone.
Traceability makes planner coverage, source selection, context loss, and
verification failures observable.

### IV. Context Isolation and Compression

Research tasks MUST be isolated by role and task boundary. Researchers receive
only the brief, their assigned task, allowed tools, and required output schema.
Long source material MUST be compressed into structured evidence summaries
before it enters shared synthesis context. Long artifacts MUST be persisted by ID
or path rather than repeatedly copied into prompts.

Rationale: Controlled context keeps the system cheaper, more inspectable, and
less likely to mix unsupported facts across perspectives or sub-tasks.

### V. Eval-Gated Iteration

Every implemented feature that affects research behavior, evidence handling,
agent orchestration, report generation, or verification MUST include runnable
tests or eval cases before it is considered complete. The MVP MUST include at
least five seed Deep Research eval cases and report metrics for planner
coverage, perspective diversity, source relevance, source authority, citation
completeness, faithfulness, unsupported claim count, critical hallucination
count, and case pass rate.

Rationale: For AI and Agent software, passing code checks is insufficient. The
system must prove behavior quality with repeatable cases, metrics, traces, and
bad-case analysis.

## Operational Constraints

TraceResearch is a lightweight Deep Research multi-agent system. The MVP scope
MUST stay focused on `Planner`, `Researcher`, `Verifier`, `Critic`, `Writer`,
`Evidence Store`, `Trace Log`, and five seed eval cases.

The MVP MUST NOT include a Web UI, long-term memory, full sandbox provider,
skills marketplace, multi-user runtime, PDF upload pipeline, large benchmark
suite, or complex autonomous supervisor loop unless a later plan documents the
trade-off, added eval coverage, and migration path.

Runtime artifacts MUST use predictable locations, such as `runs/<run_id>/` for
run-local evidence, traces, outlines, drafts, final reports, and eval outputs.
Reference projects under `references/upstream/` are read-only design references;
ideas from them MUST be summarized in `references/design-notes/` before being
used in project design, and source code MUST NOT be copied directly.

## Development Workflow

Specs MUST define the user-facing goal, non-goals, Deep Research / Agent
requirements, evidence grounding requirements, traceability requirements,
context engineering requirements, eval expectations, and measurable acceptance
criteria.

Plans MUST document agent boundaries, data flow, Evidence Store schema, Trace
schema, context policy, eval harness design, failure handling, and complexity
justification for any departure from the MVP scope.

Tasks MUST include implementation work and validation work for evidence,
verification, trace, context compression, eval runner, and review artifacts when
the feature touches those areas. Test-first or eval-first work is mandatory for
behavioral changes, and generated tasks MUST keep user-story or phase boundaries
independently testable.

Reviews MUST check constitution compliance before a feature is marked complete.
If eval results show weak evidence grounding, missing citations, poor planner
coverage, context loss, or hallucinations, the next iteration MUST return to the
appropriate spec, plan, or task phase rather than accepting the feature.

## Governance

This constitution supersedes conflicting project practices. Amendments require a
documented change to this file, a semantic version bump, an updated Sync Impact
Report, and validation of dependent templates and runtime guidance.

Versioning policy:

- MAJOR: Backward-incompatible governance changes, removed principles, or
  redefined non-negotiable quality gates.
- MINOR: New principles, new required sections, or materially expanded guidance.
- PATCH: Clarifications, wording fixes, or non-semantic refinements.

Compliance review is required during planning, task generation, implementation,
eval, and review. Any exception MUST be listed in the plan's Complexity Tracking
section with the reason, the simpler alternative considered, and the validation
added to control the risk.

**Version**: 1.0.0 | **Ratified**: 2026-06-18 | **Last Amended**: 2026-06-18
