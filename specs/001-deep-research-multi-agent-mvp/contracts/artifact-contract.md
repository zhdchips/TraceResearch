# Artifact Contract: Deep Research Multi-Agent MVP

## Run Directory

Each run writes artifacts under:

```text
runs/<run_id>/
```

Required files for completed runs:

- `research_brief.json`
- `research_tasks.json`
- `evidence.jsonl`
- `verification.json`
- `critique.json`
- `outline.md`
- `draft_report.md`
- `final_report.md`
- `report.json`
- `trace.jsonl`

## `final_report.md`

Required sections:

- Title
- Executive Summary
- Research Scope
- Method Overview
- Findings
- Limitations
- Evidence References
- Follow-up Questions

Claim citation rule:

- Key claims must include evidence IDs using `[EV-...]`.
- Claims without evidence IDs must be phrased as unknown, limitation, or follow-up question.

## `report.json`

Required shape:

```json
{
  "run_id": "string",
  "title": "string",
  "sections": [
    {
      "section_id": "string",
      "heading": "string",
      "content": "string",
      "claims": [
        {
          "claim_id": "string",
          "text": "string",
          "evidence_ids": ["string"],
          "support_status": "supported"
        }
      ]
    }
  ],
  "limitations": ["string"],
  "unsupported_claims": [],
  "evidence_references": ["string"]
}
```

Validation:

- Completed reports must have zero critical unsupported claims.
- `unsupported_claims` must be empty for pass status.

## `trace.jsonl`

Each line is one `TraceEvent` JSON object. The file must include at least one event for each role used in the run.

## `evidence.jsonl`

Each line is one `Evidence` JSON object. Evidence IDs must be unique within a run.
