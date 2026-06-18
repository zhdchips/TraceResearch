# Data Model: Deep Research Multi-Agent MVP

## ResearchRun

Fields:

- `run_id`: unique string, required
- `input_query`: string, required
- `status`: `created | needs_clarification | running | completed | failed`
- `created_at`: ISO datetime
- `completed_at`: ISO datetime or null
- `artifact_dir`: path string
- `final_report_path`: path string or null
- `eval_result_path`: path string or null

Relationships:

- Has one `ResearchBrief`
- Has many `ResearchTask`
- Has many `Evidence`
- Has many `TraceEvent`
- May have one `EvalResult`

Validation:

- `run_id` must be stable for all artifacts in a run.
- `completed` requires `final_report_path`, `evidence.jsonl`, and `trace.jsonl`.

## ResearchBrief

Fields:

- `run_id`: string
- `objective`: string
- `scope_boundaries`: string[]
- `assumptions`: string[]
- `open_clarifications`: string[]
- `perspectives`: string[]
- `success_criteria`: string[]
- `research_tasks`: `ResearchTask[]`

Validation:

- Must exist before source discovery starts.
- Must include at least one perspective and one research task when status is not `needs_clarification`.
- Ambiguous input must produce `open_clarifications` or explicit `assumptions`.

## ResearchTask

Fields:

- `research_task_id`: string
- `run_id`: string
- `perspective`: string
- `objective`: string
- `query`: string
- `status`: `pending | running | completed | no_evidence | failed`
- `source_limit`: integer

Relationships:

- Belongs to one `ResearchBrief`
- Produces many `Evidence`
- Has many `TraceEvent`

Validation:

- Must be tied to one perspective or objective.
- `no_evidence` requires a visible reason.

## SourceResult

Fields:

- `source_id`: string
- `provider`: string
- `title`: string
- `url`: string or null
- `source_type`: `official_doc | paper | repo | blog | news | report | unknown`
- `publisher`: string or null
- `published_at`: ISO date or null
- `retrieved_at`: ISO datetime
- `snippet`: string
- `provider_rank`: integer

Validation:

- Fixture sources may omit `url` only when the source is a local fixture with a stable `source_id`.
- `provider_rank` starts at 1 per task result set.

## SourceDocument

Fields:

- `source_id`: string
- `title`: string
- `url`: string or null
- `content_excerpt`: string
- `metadata`: object
- `retrieved_at`: ISO datetime

Validation:

- MVP stores excerpts/summaries, not full raw webpage dumps.

## Evidence

Fields:

- `evidence_id`: string
- `run_id`: string
- `research_task_id`: string
- `perspective`: string
- `source`: `SourceResult`
- `authority_score`: number from 0.0 to 1.0
- `relevance_score`: number from 0.0 to 1.0
- `summary`: string
- `key_points`: string[]
- `supported_claims`: string[]
- `limitations`: string[]
- `status`: `candidate | verified | rejected`
- `verification_notes`: string[]

Relationships:

- Belongs to one `ResearchTask`
- Supports many `Claim`

Validation:

- `verified` evidence requires at least one supported claim or explicit limitation.
- `authority_score` and `relevance_score` must be bounded between 0.0 and 1.0.
- Duplicate sources must reuse or reference existing evidence instead of silently creating conflicting entries.

## Claim

Fields:

- `claim_id`: string
- `run_id`: string
- `text`: string
- `section_id`: string
- `evidence_ids`: string[]
- `support_status`: `supported | weakly_supported | unsupported | conflicting`
- `notes`: string[]

Validation:

- Key claims in final report cannot be `unsupported`.
- `supported` requires at least one verified `evidence_id`.

## VerificationResult

Fields:

- `run_id`: string
- `checked_at`: ISO datetime
- `claim_results`: `Claim[]`
- `unsupported_claim_count`: integer
- `critical_hallucination_count`: integer
- `citation_completeness`: number from 0.0 to 1.0
- `notes`: string[]

Validation:

- `critical_hallucination_count` must be 0 for MVP pass.

## CritiqueResult

Fields:

- `run_id`: string
- `missing_perspectives`: string[]
- `weak_sources`: string[]
- `duplicate_sections`: string[]
- `unsupported_claims`: string[]
- `limitations_to_add`: string[]
- `decision`: `pass | revise | fail`
- `next_phase`: `plan | research | verify | write | eval | complete`

Validation:

- `fail` or `revise` requires `next_phase` other than `complete`.

## TraceEvent

Fields:

- `trace_id`: string
- `run_id`: string
- `task_id`: string or null
- `agent_role`: `Planner | Researcher | Verifier | Critic | Writer | EvalRunner | Harness`
- `event_type`: `start | finish | tool_call | tool_result | warning | error`
- `tool_name`: string or null
- `input_summary`: string
- `output_summary`: string
- `status`: `success | failed | skipped | needs_clarification`
- `latency_ms`: integer
- `token_usage`: object with nullable prompt/completion/total counts
- `error`: object with nullable type/message
- `created_at`: ISO datetime

Validation:

- Every Agent role invocation must emit start and finish or error events.
- Failed events require `error.message`.

## EvalCase

Fields:

- `case_id`: string
- `theme`: string
- `input_query`: string
- `expected_perspectives`: string[]
- `fixture_source_ids`: string[]
- `required_metrics`: string[]
- `pass_conditions`: object

Validation:

- MVP requires exactly 5 seed cases.
- Each case must define fixture sources and required metrics.

## EvalResult

Fields:

- `eval_run_id`: string
- `created_at`: ISO datetime
- `case_results`: object[]
- `metrics_summary`: object
- `case_pass_rate`: number
- `bad_case_notes`: string[]
- `suggested_next_phase`: string

Validation:

- Must include all required metrics from the constitution.
- Failed cases must include bad-case notes.
