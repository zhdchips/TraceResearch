# Design Reference Summary

## How to Use These References

This project should not copy or recreate Open Deep Research, STORM, or DeerFlow. They should be used as design references:

- Open Deep Research: research loop and evaluation discipline
- STORM: multi-perspective outline-first writing
- DeerFlow: Agent Harness, sub-agent isolation, context engineering, traceability

## Recommended MVP Scope

Implement a lightweight Deep Research multi-agent system with:

- `Planner`
- `Researcher`
- `Verifier`
- `Critic`
- `Writer`
- `Evidence Store`
- `Trace Log`
- 5 seed eval cases

Do not implement in MVP:

- Web UI
- full sandbox
- long-term memory
- full skills plugin system
- multi-user runtime
- large benchmark evaluation
- complex autonomous supervisor loop

## Proposed MVP Flow

```text
User Query
  -> Planner
      -> research_brief
      -> perspectives
      -> research_tasks
  -> Researcher(s)
      -> source search
      -> source summaries
      -> evidence candidates
  -> Evidence Store
      -> dedupe
      -> source metadata
      -> supported claims
  -> Verifier
      -> evidence quality check
      -> claim support check
  -> Critic
      -> missing perspective check
      -> weak-source check
      -> unsupported-claim check
  -> Writer
      -> outline
      -> final report with evidence IDs / citations
  -> Eval Runner
      -> metrics
      -> bad cases
```

## Design Decisions to Put in `plan.md`

### Agent Boundaries

- `Planner` owns task decomposition and perspectives.
- `Researcher` owns search and source summarization.
- `Verifier` owns evidence quality and claim support.
- `Critic` owns missing perspectives, duplicate sections, weak reasoning, and limitations.
- `Writer` owns final report generation but may only use verified evidence.

### Evidence Model

Minimum evidence fields:

```yaml
evidence_id:
source_url:
source_title:
source_type:
authority_score:
summary:
key_points:
supported_claims:
retrieved_at:
research_task_id:
```

### Trace Model

Minimum trace fields:

```yaml
run_id:
task_id:
agent_role:
event_type:
tool_name:
input_summary:
output_summary:
status:
latency_ms:
token_usage:
error:
```

### Context Policy

- Raw source content stays outside the main Writer context.
- Researcher compresses sources into structured evidence.
- Writer reads outline + verified evidence only.
- Long artifacts are persisted to files and referenced by ID.

## Eval Seed Case Themes

Start with 5 cases:

1. Framework comparison: LangGraph vs AutoGen vs CrewAI
2. High-risk domain design: financial research agent grounding
3. Trend research: AI Coding Agent product forms and engineering challenges
4. Source/project research: OpenHands Agent Runtime design
5. Controversial question: whether RAG is still important in 2026

## Metrics

Use simple metrics first:

- `planner_coverage`
- `perspective_diversity`
- `source_relevance`
- `source_authority`
- `citation_completeness`
- `faithfulness`
- `unsupported_claim_count`
- `critical_hallucination_count`
- `case_pass_rate`

## Suggested First Spec Prompt

```text
本项目是一个 Deep Research 场景的 multi-agent 个人项目，不复刻任何开源项目，但参考以下设计：

1. Open Deep Research：research loop，包括 query planning、web search、source summarization、context compression、final report generation。
2. STORM：multi-perspective research 和 outline-first writing。
3. DeerFlow：Agent Harness 思想，包括 sub-agent isolation、traceability、context engineering、skills/sandbox/memory 的长期演进方向。

第一版 MVP 只实现 Planner、Researcher、Verifier、Critic、Writer、Evidence Store、Trace Log 和 5 个 eval seed cases。

第一版不实现 Web UI、长期 memory、完整 sandbox、skills 插件系统、多用户、PDF 上传和大规模并行调度。
```
