# Implementation Plan: Deep Research Multi-Agent MVP

> Language Policy: English headings, Chinese explanatory body, English AI/Agent terms, and English machine-readable keys.

**Branch**: `001-deep-research-multi-agent-mvp`  
**Date**: 2026-06-18  
**Spec**: [spec.md](./spec.md)

## Summary

第一版实现一个本地运行的 Deep Research multi-agent MVP。系统以 CLI 作为入口，接收复杂技术/业务研究问题，生成 `research_brief`、perspectives、research tasks、structured evidence、verification result、critique、outline 和 final report。MVP 的核心目标不是做完整 Web 产品，而是把 constitution 要求的 evidence grounding、Trace、context isolation 和 eval-gated iteration 跑通。

本计划明确采用 deterministic fixture source provider 跑通 5 个 seed eval cases；external live web source provider 只定义接口和 not-configured stub，后续 feature 再接真实搜索服务。

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Pydantic v2 for schema validation, Typer for CLI, pytest for tests, standard JSON/JSONL/Markdown filesystem artifacts  
**Storage**: Local filesystem artifacts under `runs/<run_id>/`, `eval/cases/`, and `eval/results/`; no database in MVP  
**Testing**: pytest unit/integration tests plus eval runner over 5 seed cases  
**Target Platform**: Local developer machine / CLI-first personal research assistant  
**Project Type**: Single Python package with CLI entrypoint  
**Performance Goals**: 5 seed eval cases complete in a bounded local run; each run produces inspectable artifacts without manual post-processing  
**Constraints**: No Web UI, no long-term memory, no full sandbox, no skills plugin system, no multi-user runtime, no PDF upload, no large benchmark, no large-scale parallel scheduling  
**Scale/Scope**: One user, one local run at a time, serial research tasks for MVP

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Research Contract First: PASS. `Planner` produces `research_brief` before source discovery. Ambiguous query handling returns clarification or visible assumptions.
- Evidence-Grounded Output: PASS. `Writer` reads only verified evidence and outline; final report claims must reference evidence IDs.
- Traceable Agent Execution: PASS. Every role/tool step writes JSONL `TraceEvent` records under `runs/<run_id>/trace.jsonl`.
- Context Isolation and Compression: PASS. `Researcher` receives per-task context only; raw source text is compressed into `Evidence` summaries before synthesis.
- Eval-Gated Iteration: PASS. MVP includes 5 seed cases and required metrics in `eval/results/`.

No constitution violations are planned.

## Project Structure

```text
traceresearch/
├── __init__.py
├── cli.py
├── agents/
│   ├── planner.py
│   ├── researcher.py
│   ├── verifier.py
│   ├── critic.py
│   └── writer.py
├── harness/
│   ├── run_state.py
│   ├── artifacts.py
│   └── orchestrator.py
├── evidence/
│   ├── models.py
│   └── store.py
├── source_discovery/
│   ├── base.py
│   ├── fixture_provider.py
│   └── web_stub.py
├── trace/
│   ├── models.py
│   └── writer.py
├── reports/
│   └── renderer.py
└── eval/
    ├── runner.py
    └── metrics.py

eval/
├── cases/
│   ├── 001-framework-comparison.yml
│   ├── 002-financial-grounding.yml
│   ├── 003-ai-coding-agent-trends.yml
│   ├── 004-openhands-runtime.yml
│   └── 005-rag-2026.yml
├── fixtures/
│   └── sources/
└── results/

runs/
└── <run_id>/
    ├── research_brief.json
    ├── research_tasks.json
    ├── evidence.jsonl
    ├── verification.json
    ├── critique.json
    ├── outline.md
    ├── draft_report.md
    ├── final_report.md
    ├── report.json
    └── trace.jsonl

tests/
├── unit/
├── integration/
└── eval/
```

**Structure Decision**: 单包 CLI-first 结构。`traceresearch/` 放产品代码边界，`eval/` 放 seed cases、fixtures 和 results，`runs/` 放运行产物。MVP 不拆 backend/frontend，不引入服务端目录。

## Architecture

系统由 `Agent Harness` 统一编排。Harness 负责创建 `run_id`、artifact paths、Trace writer、Evidence Store，并按固定顺序调用 Agent roles：

1. `Planner` 将 user query 转成 `ResearchBrief` 和 `ResearchTask[]`。
2. `Researcher` 对每个 task 调用 `SourceDiscoveryProvider`，并把 source summaries 压缩成 evidence candidates。
3. `Evidence Store` 去重、分配 evidence ID、保存 source metadata 和 supported claims。
4. `Verifier` 检查 evidence quality、claim support、citation mismatch 和 conflicting evidence。
5. `Critic` 检查 missing perspectives、weak sources、duplicate sections、unsupported claims 和 limitation coverage。
6. `Writer` 先生成 `outline.md`，再只基于 verified evidence 生成 `draft_report.md`、`final_report.md` 和 `report.json`。
7. `Eval Runner` 读取 seed cases，批量运行 pipeline，输出 metrics 和 bad-case notes。

## Source Discovery Provider

第一版采用 provider interface + deterministic provider 的设计：

- `SourceDiscoveryProvider`: 抽象 `search(task, limit)` 和 `fetch(source_ref)`，返回 normalized `SourceResult` / `SourceDocument`。
- `FixtureSourceProvider`: MVP 必须真实跑通的 provider，从 `eval/fixtures/sources/` 读取预置 source metadata 和 excerpts，用于 5 个 seed eval cases。
- `WebSearchProviderStub`: 只定义配置、错误类型和 not-configured 行为；不要求 MVP 接外部搜索服务。

Decision: Eval 和本地 demo 默认使用 `fixture`，确保可重复、可离线、可评估。真实 live web search 留到后续 feature，通过同一 provider contract 接入。

## Agent Roles

| Role | Module | Responsibility | Inputs | Outputs | Tools |
| --- | --- | --- | --- | --- | --- |
| Planner | `traceresearch/agents/planner.py` | 生成 `research_brief`、perspectives、research tasks、clarification/assumption | user query, optional case metadata | `ResearchBrief`, `ResearchTask[]` | model or deterministic planner stub |
| Researcher | `traceresearch/agents/researcher.py` | 调用 source discovery，摘要 source，生成 evidence candidates | one `ResearchTask`, provider results | `EvidenceCandidate[]` | `SourceDiscoveryProvider` |
| Verifier | `traceresearch/agents/verifier.py` | 检查 evidence quality、claim support、conflicts | evidence candidates, draft claims | `VerificationResult` | rule-based verifier first |
| Critic | `traceresearch/agents/critic.py` | 检查 coverage、weak sources、unsupported claims、limitations | brief, evidence, outline/report draft | `CritiqueResult` | rule-based critic first |
| Writer | `traceresearch/agents/writer.py` | outline-first report generation，只读 verified evidence | brief, verified evidence, critique | `outline.md`, reports | template/rule-based writer first |

MVP 中 Planner/Verifier/Critic/Writer 可先用 deterministic rule/template implementation 跑通契约；后续再替换为 model-backed implementation。

## Data Flow

1. User query -> `ResearchRun`
2. `Planner` -> `research_brief.json`, `research_tasks.json`
3. `Researcher` + `SourceDiscoveryProvider` -> `EvidenceCandidate[]`
4. `Evidence Store` -> `evidence.jsonl`
5. `Verifier` -> `verification.json`
6. `Critic` -> `critique.json`
7. `Writer` -> `outline.md`, `draft_report.md`, `final_report.md`, `report.json`
8. `Eval Runner` -> `eval/results/<timestamp>-summary.json`, bad-case notes

## Evidence Store Design

Evidence Store 使用 append-friendly JSONL。每条 evidence 必须可追溯到 source 和 research task。

```yaml
evidence_id: string              # EV-<run_id>-<sequence>
run_id: string
research_task_id: string
perspective: string
source:
  source_id: string
  source_url: string | null
  source_title: string
  source_type: official_doc | paper | repo | blog | news | report | unknown
  publisher: string | null
  published_at: string | null
  retrieved_at: string
authority_score: number          # 0.0-1.0
relevance_score: number          # 0.0-1.0
summary: string
key_points: string[]
supported_claims: string[]
limitations: string[]
status: candidate | verified | rejected
verification_notes: string[]
```

Dedup key: normalized `source_url` when present, otherwise `source_title + publisher + retrieved_at date bucket` for fixture sources.

## Trace Design

Trace 使用 `runs/<run_id>/trace.jsonl`。每个 Agent step 和 provider action 都写入一条事件。

```yaml
trace_id: string                 # TR-<run_id>-<sequence>
run_id: string
task_id: string | null
agent_role: Planner | Researcher | Verifier | Critic | Writer | EvalRunner | Harness
event_type: start | finish | tool_call | tool_result | warning | error
tool_name: string | null
input_summary: string
output_summary: string
status: success | failed | skipped | needs_clarification
latency_ms: integer
token_usage:
  prompt_tokens: integer | null
  completion_tokens: integer | null
  total_tokens: integer | null
error:
  type: string | null
  message: string | null
created_at: string
```

## Eval Harness Design

Seed cases live under `eval/cases/*.yml`; fixture sources live under `eval/fixtures/sources/`; result summaries live under `eval/results/`.

| Case ID | Theme | Expected emphasis |
| --- | --- | --- |
| `001-framework-comparison` | LangGraph vs AutoGen vs CrewAI | perspective coverage, comparison grounding |
| `002-financial-grounding` | financial research agent grounding | uncertainty, source authority, risk language |
| `003-ai-coding-agent-trends` | AI Coding Agent product forms and engineering challenges | trend synthesis, citation completeness |
| `004-openhands-runtime` | OpenHands Agent Runtime design | source/project research, traceability |
| `005-rag-2026` | whether RAG is still important in 2026 | controversial question, balanced evidence |

Metrics:

- `planner_coverage`
- `perspective_diversity`
- `source_relevance`
- `source_authority`
- `citation_completeness`
- `faithfulness`
- `unsupported_claim_count`
- `critical_hallucination_count`
- `case_pass_rate`

Pass threshold for MVP: `critical_hallucination_count == 0`, no key claim without evidence ID, at least 4/5 cases pass planner and citation checks.

## Report Artifact Format

MVP 输出两种 report artifact：

- `final_report.md`: 人类阅读主产物，包含 title、executive summary、scope、method overview、findings、limitations、evidence references、follow-up questions。
- `report.json`: machine-readable report，包含 sections、claims、evidence_ids、unsupported_claims、limitations 和 metrics references。

每个 key claim 在 Markdown 中使用 `[EV-...]` 标注 evidence ID；JSON 中使用 `claims[].evidence_ids[]`。

## Real vs Stubbed Capabilities

Must real-run in MVP:

- CLI run/eval entrypoints
- `run_id` creation and artifact directory creation
- `ResearchBrief`, `ResearchTask`, `Evidence`, `TraceEvent`, `EvalCase`, `EvalResult` schema validation
- `FixtureSourceProvider` source discovery path
- Evidence Store JSONL write/read
- Trace JSONL write/read
- serial Agent Harness orchestration
- final report artifact generation from verified evidence
- eval runner over 5 seed cases with metrics summary

May be mock/stub/template in MVP:

- live web search provider
- model-backed Planner/Researcher/Verifier/Critic/Writer
- sophisticated authority scoring
- claim extraction beyond simple structured claims
- concurrent research task execution
- sandbox, skills, memory, Web UI, PDF parsing

## Technical Decisions

- TD-001: Python 3.11+ single-package CLI。Rationale: 适合快速构建本地 research pipeline、schema validation、file artifacts 和 pytest/eval。Alternatives considered: web service first, notebook-only prototype.
- TD-002: Pydantic v2 schema-first domain models。Rationale: Evidence、Trace、EvalResult 需要强校验和 JSON serialization。Alternatives considered: plain dicts, dataclasses only.
- TD-003: Typer CLI as first interface。Rationale: MVP 不做 Web UI，CLI 足够支持 run/eval/review artifacts。Alternatives considered: REST API, script-only entrypoints.
- TD-004: Filesystem JSONL/Markdown artifacts instead of database。Rationale: 便于调试、review、bad-case replay 和面试展示。Alternatives considered: SQLite, document store.
- TD-005: Fixture source provider first, web provider stub second。Rationale: seed eval 必须稳定可重复，外部搜索集成留给后续。Alternatives considered: first release directly depend on live search.
- TD-006: Rule/template agents first, model-backed agents later。Rationale: 先验证 contracts、artifacts、Trace、evidence grounding 和 eval loop。Alternatives considered: immediately optimize prompts and model routing.

## Failure Handling

- Ambiguous query: `Planner` returns clarification or records assumption; run status becomes `needs_clarification` if research cannot proceed.
- No source results: `Researcher` emits no-evidence reason; Writer must include limitation and avoid unsupported conclusion.
- Conflicting evidence: Evidence keeps conflict notes; Verifier marks related claims `conflicting`; Writer reports uncertainty.
- Weak authority: Verifier marks weak support; Critic blocks strong recommendation language.
- Tool/provider failure: Trace records `error`; harness marks task failed and continues only when report can safely expose limitation.
- Context compression loss: Eval bad-case notes record missing key facts; next phase returns to plan/tasks.
- Unsupported Writer claim: Verifier/Critic blocks finalization or marks claim unknown.

## Test Strategy

- Unit tests: schema validation, evidence dedupe, trace writer, report claim/evidence linking, metrics calculation.
- Integration tests: one fixture run from query to final report; ambiguous query flow; no-source flow; conflicting-evidence flow.
- Eval tests: run all 5 seed cases and assert metrics keys, zero critical hallucinations, and evidence IDs for key claims.
- Bad-case replay: use `runs/<run_id>/trace.jsonl` plus `eval/results/*` to reproduce failure analysis.

## Complexity Tracking

No constitution violations or complexity exceptions are planned.

## Post-Design Constitution Check

- Research Contract First: PASS. `ResearchBrief` schema and Planner boundary are defined in `data-model.md`.
- Evidence-Grounded Output: PASS. Evidence schema, Writer contract, and report artifact format require evidence IDs.
- Traceable Agent Execution: PASS. Trace schema and artifact path are defined.
- Context Isolation and Compression: PASS. Source provider and Researcher boundary keep raw source content out of Writer context.
- Eval-Gated Iteration: PASS. Eval case layout, metrics, thresholds, and quickstart validation are defined.

## Risks

- Risk-001: Fixture provider can hide live web variability. Mitigation: provider contract includes a web stub and future extension point.
- Risk-002: Rule/template agents may underrepresent final model behavior. Mitigation: eval focuses on artifacts and grounding contracts first.
- Risk-003: Authority scoring may be too coarse. Mitigation: expose scoring notes and keep thresholds simple in MVP.
- Risk-004: Markdown-only report may be hard to machine-check. Mitigation: emit `report.json` alongside `final_report.md`.
