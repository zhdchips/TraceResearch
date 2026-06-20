# Implementation Plan: Live Provider Demo Readiness

> Language Policy: English headings, Chinese explanatory body, English AI/Agent terms, and English machine-readable keys.

**Branch**: `002-live-provider-demo-readiness`  
**Date**: 2026-06-20  
**Spec**: [spec.md](./spec.md)

## Summary

本 feature 将 TraceResearch 从 fixture-only deterministic MVP 扩展为可演示的 live web research prototype。核心设计是保留 `FixtureSourceProvider` 作为 regression provider，同时新增一个显式选择的 `web` provider path。用户运行 `traceresearch run --source-provider web` 时，系统从环境变量读取 provider configuration，调用 live web search provider，normalize search results 到现有 `SourceResult` / `SourceDocument` / `Evidence` contract，再沿用 001 已完成的 `Planner -> Researcher -> Evidence Store -> Writer draft claims -> Verifier -> Critic -> Writer final report` flow。

本计划选择 Exa 作为第一版 live provider。Exa `/search` 能在一次调用中返回 web results 与 highlights/summary，结果 schema 对 Deep Research evidence compression 更直接；Tavily 保留为后续可选 provider 方向。Live smoke 是 README/manual validation，不进入默认 pytest/CI gate。Fixture eval 仍作为稳定 quality gate，必须保持 5/5 pass。

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: Existing Pydantic v2, Typer, pytest, PyYAML; use Python standard library HTTP client for Exa REST integration first to avoid introducing SDK install friction  
**Storage**: Local filesystem artifacts under `runs/<run_id>/`, `eval/results/`, `.env.example`, README docs; no database  
**Testing**: pytest unit/integration tests for config, provider errors, response normalization, CLI web path, fixture regression; fixture eval remains required manual/automation gate; live smoke documented and optional  
**Target Platform**: Local developer machine / CLI screen-share demo  
**Project Type**: Single Python package with CLI entrypoint  
**Performance Goals**: Unconfigured web provider fails immediately with clear error; configured live provider respects timeout; fixture test suite remains fast and deterministic; live smoke completes in a bounded manual run when provider/network are available  
**Constraints**: No Web UI, no LLM-backed agents, no PDF/HTML export, no large benchmark, no live web CI gate, no secret commits, no silent fallback from web to fixture  
**Scale/Scope**: One local user, one run at a time, serial research tasks, small live query for demo readiness

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Research Contract First: PASS. Existing `Planner` and `research_brief` remain first step for both fixture and web runs.
- Evidence-Grounded Output: PASS. Live provider results must be normalized into `Evidence Store`; `Writer` still reads only verified evidence.
- Traceable Agent Execution: PASS. Web search/fetch success and failure events must emit `Trace` with provider, result count, latency, and error summaries.
- Context Isolation and Compression: PASS. Exa highlights/summary are used as compressed source excerpts; raw page dumps do not enter Writer context.
- Eval-Gated Iteration: PASS. Existing fixture eval remains stable regression gate; live smoke is documented as non-CI manual validation.

No constitution violations are planned.

## Project Structure

```text
traceresearch/
├── cli.py
├── config.py                       # new env/config helpers
├── harness/
│   └── orchestrator.py             # add provider-aware run entrypoint
├── source_discovery/
│   ├── base.py
│   ├── fixture_provider.py
│   ├── web_stub.py                 # keep explicit not-configured behavior
│   └── exa_provider.py             # new Exa live provider
└── ...

tests/
├── integration/
│   └── test_run_web_provider.py     # mocked live provider / CLI web path
└── unit/
    ├── test_config.py
    ├── test_exa_provider.py
    └── test_provider_factory.py

specs/002-live-provider-demo-readiness/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    ├── cli-contract.md
    ├── env-config-contract.md
    ├── source-provider-contract.md
    └── demo-readiness-contract.md

.env.example                        # new, no real secrets
README.md                           # new demo readiness doc
```

## Architecture

本 feature 不改变 Agent roles，而是让 source discovery provider 从 hardcoded fixture 变为 explicit provider selection:

1. CLI parses `--source-provider fixture|web` and optional config flags if added during tasks.
2. Config layer reads environment:
   - `TRACERESEARCH_WEB_PROVIDER=exa`
   - `EXA_API_KEY`
   - `TRACERESEARCH_WEB_TIMEOUT_SECONDS`
   - `TRACERESEARCH_WEB_MAX_RESULTS`
3. Provider factory returns:
   - `FixtureSourceProvider` for fixture runs.
   - `ExaSearchProvider` when `--source-provider web` and config is present.
   - `WebSearchProviderStub` / `ProviderNotConfiguredError` when web config is missing.
4. `ResearchHarness` runs existing chain with the selected provider. Fixture eval remains bound to `FixtureSourceProvider`.
5. `Researcher` converts provider `SourceResult` / `SourceDocument` into evidence candidates as in 001.
6. `Trace` records provider-specific search/fetch events, result counts, latency, and safe error summaries.
7. README documents fixture demo, live configured demo, unconfigured graceful failure, eval/review workflow, and limitations.

## Agent Roles

| Role | Responsibility | Inputs | Outputs | Tools |
| --- | --- | --- | --- | --- |
| Planner | 继续生成 `research_brief`、perspectives、research tasks、assumptions | user query, optional fixture case metadata | `ResearchBrief`, `ResearchTask[]` | existing deterministic planner |
| Researcher | 使用 selected `SourceDiscoveryProvider` 搜索并压缩 source into evidence candidates | one `ResearchTask`, provider config, provider results | `Evidence[]` candidates | fixture provider or Exa web provider |
| Verifier | 检查 live/fixture evidence 是否支撑 draft claims | draft claims, evidence | `verification.json` | existing deterministic verifier |
| Critic | 检查 weak source、missing perspective、unsupported claims 和 limitations | brief, evidence, verification | `critique.json` | existing deterministic critic |
| Writer | 只基于 verified evidence 输出 final report | brief, verified evidence, critique | `final_report.md`, `report.json` | existing deterministic writer |

No new Agent role is introduced.

## Data Flow

```text
CLI query + source_provider
  -> config loader
  -> provider factory
      -> fixture provider OR Exa provider OR provider_not_configured
  -> Planner
      -> research_brief.json
      -> research_tasks.json
  -> Researcher
      -> provider.search(task, limit)
      -> provider.fetch(source_ref)
      -> compressed evidence candidates
  -> Evidence Store
      -> evidence.jsonl
  -> Writer draft claims
  -> Verifier
      -> verification.json
  -> Critic
      -> critique.json
  -> Writer final report
      -> final_report.md
      -> report.json
  -> Trace Log
      -> trace.jsonl
```

## Source Discovery Provider Decision

第一版 live provider 选择 Exa Search API。

Decision:

- `web` provider defaults to Exa.
- Use REST endpoint `POST https://api.exa.ai/search`.
- Use `x-api-key` header from `EXA_API_KEY`.
- Request body uses query, max results, and `contents.highlights=true` / summary when available.
- Normalize Exa result fields into existing `SourceResult` and `SourceDocument`.

Rationale:

- Exa search endpoint is explicitly designed to search web and extract contents from results in one call.
- Exa response includes title, URL, published date, author, text/highlights/summary, request ID, resolved search type, and cost metadata, which maps naturally to Trace and Evidence Store.
- Exa Python SDK docs recommend highlights for retrieval workflows because it preserves relevant evidence without pulling full page text into every response.
- Avoiding the SDK keeps install path stable in this repo, where local Python build tooling has already shown friction.

Alternatives considered:

- Tavily Search API: Simple and agent-oriented; response has title, URL, content, score, raw content option, and API key auth. Good future option, but Exa highlights/summary and result schema are a better first fit for evidence compression.
- Brave Search API: Strong general search option, but less tailored to evidence snippets/highlights for AI retrieval.
- Keep stub only: insufficient for demo readiness.

## Evidence Store Design

No schema-breaking change is planned. Live evidence uses existing `Evidence` fields:

```yaml
evidence_id: EV-<run_id>-<sequence>
run_id: string
research_task_id: string
perspective: string
source:
  source_id: exa:<stable-hash-or-result-id>
  provider: web
  title: Exa result title
  url: Exa result URL
  source_type: official_doc | paper | repo | blog | news | report | unknown
  publisher: derived domain or author when available
  published_at: Exa publishedDate when available
  retrieved_at: current run timestamp
  snippet: highlight or text excerpt
  provider_rank: result rank
authority_score: heuristic score from source_type/domain metadata
relevance_score: provider score or deterministic fallback
summary: highlight/summary/text excerpt compressed for Writer
key_points: derived from highlights/summary
supported_claims: summary-derived statements
limitations: missing metadata, weak source, no full content, or provider uncertainty
status: candidate | verified | rejected
verification_notes: list
```

Dedup key remains normalized URL when present. Exa result IDs are retained in metadata but URL remains primary dedupe key.

## Trace Design

Trace schema remains the 001 model. Required additions are event semantics:

- `tool_name`: `exa.search`, `exa.fetch`, `web_search`, or `fixture.search`.
- `input_summary`: query/perspective summary without secrets.
- `output_summary`: result count, selected source IDs, no-results reason, or error code.
- `latency_ms`: measured for provider calls.
- `error.type`: `provider_not_configured`, `provider_timeout`, `provider_error`, `provider_no_results`, `provider_rate_limited`, or `source_normalization_error`.
- `error.message`: safe user-facing message without API key or secret.

Secret values must never be written to Trace.

## Eval Harness Design

Regression gates:

- `python3 -m pytest`
- fixture eval command:

```bash
traceresearch eval --cases-dir eval/cases --source-provider fixture --results-dir eval/results
```

Expected fixture result:

- `case_pass_rate == 1.0`
- 5 seed cases run
- 9 required metrics present

Live smoke is manual/demo only:

```bash
export EXA_API_KEY=...
export TRACERESEARCH_WEB_PROVIDER=exa
traceresearch run \
  --query "What changed in AI coding agents during the last 12 months?" \
  --source-provider web \
  --output-dir runs
```

Live smoke checks:

- `final_report.md`, `evidence.jsonl`, `trace.jsonl` exist for configured success.
- final report key claims include `[EV-...]`.
- evidence rows include live source URL/title/retrieved_at.
- trace includes `exa.search` or explicit provider failure.
- unconfigured run returns `provider_not_configured` and does not fallback to fixture.

Live smoke is not part of default pytest/CI because external API availability, quota, and network variability are outside deterministic regression control.

## Technical Decisions

- TD-001: Choose Exa as first live web provider. Rationale: clear search+contents response, highlights suited for evidence compression, good demo fit. Alternatives considered: Tavily, Brave, stub-only.
- TD-002: Use environment variables and `.env.example` for config. Rationale: local demo setup is simple and avoids secret commits. Alternatives considered: config file with secrets, CLI-only key flag.
- TD-003: Use standard-library HTTP client first, not provider SDK. Rationale: avoids adding build/install dependency friction and keeps implementation inspectable. Alternatives considered: `exa-py` SDK.
- TD-004: Keep fixture provider as default regression provider. Rationale: prevents live web variability from destabilizing tests/eval.
- TD-005: Add provider factory instead of embedding provider logic in CLI. Rationale: keeps CLI thin and preserves future provider extensibility.
- TD-006: Web provider failures are explicit terminal/limited states, never silent fallback. Rationale: avoids false confidence during demos and satisfies spec/constitution.
- TD-007: README is a first-class demo artifact. Rationale: the feature goal is interview/demo readiness, not only code behavior.

## Failure Handling

- Missing API key: return `provider_not_configured`, write Trace error, CLI prints status/error, no fixture fallback.
- Timeout: return/raise `provider_timeout`, Trace records latency and safe message; run fails safely or reports no evidence limitation depending on harness stage.
- Provider HTTP error: map 401/403 to configuration/auth error, 429 to rate limit, 5xx to provider error; Trace records code without secret.
- No results: mark task no-evidence or provider_no_results; Writer must not create unsupported claims.
- Partial metadata: keep title/URL/snippet where possible and add limitations.
- Duplicate URLs: existing Evidence Store dedupe prevents repeated evidence.
- Weak relevance: Verifier/Critic marks limitation or weak support.
- Secret exposure risk: config helpers expose `has_api_key` but never dump key; tests assert key absent from errors and Trace.

## Test Strategy

Unit tests:

- `tests/unit/test_config.py`: env parsing, defaults, missing key, timeout/max result validation, no secret in repr/error.
- `tests/unit/test_exa_provider.py`: mocked HTTP success, no results, timeout, auth/rate-limit/server errors, schema normalization.
- `tests/unit/test_provider_factory.py`: fixture/web selection, not-configured behavior, no fallback.
- Existing tests remain unchanged and must pass.

Integration tests:

- `tests/integration/test_run_web_provider.py`: CLI/harness web path with mocked Exa provider or injected fake provider generates required artifacts.
- Unconfigured web provider path returns clear failure and no fixture evidence.
- Fixture run/eval still passes with live env absent.

Manual validation:

- Live smoke command documented in quickstart/README.
- If `EXA_API_KEY` is unavailable during implementation/review, record skip reason and exact command.

Eval/review:

- Run full `python3 -m pytest`.
- Run fixture eval and verify 5/5 pass.
- Do not require live smoke in CI.

## Phase 0 Research

Completed in [research.md](./research.md). All planning unknowns resolved:

- Provider choice: Exa.
- API result mapping: Exa `/search` with highlights/summary to existing source/evidence contract.
- Config and secret strategy: environment variables and `.env.example`.
- Live smoke strategy: manual README path, not CI gate.

## Phase 1 Design Artifacts

- [data-model.md](./data-model.md)
- [contracts/cli-contract.md](./contracts/cli-contract.md)
- [contracts/env-config-contract.md](./contracts/env-config-contract.md)
- [contracts/source-provider-contract.md](./contracts/source-provider-contract.md)
- [contracts/demo-readiness-contract.md](./contracts/demo-readiness-contract.md)
- [quickstart.md](./quickstart.md)
- `AGENTS.md` updated to reference this plan.

## Complexity Tracking

No constitution violations are planned. The feature increases integration complexity by adding a live provider, but it is justified by the explicit demo-readiness goal. Controls:

- fixture provider remains default regression path;
- live smoke is manual only;
- provider failures are explicit;
- source results still enter existing Evidence Store and Trace contracts.

## Post-Design Constitution Check

- Research Contract First: PASS. Provider selection happens after CLI/config, but research still begins with `Planner` and `research_brief`.
- Evidence-Grounded Output: PASS. Exa results are normalized into evidence before Writer sees them.
- Traceable Agent Execution: PASS. Provider search/fetch and errors have explicit Trace requirements.
- Context Isolation and Compression: PASS. Highlights/summary are used as compressed source material.
- Eval-Gated Iteration: PASS. Tests, fixture eval, and manual live smoke are defined.

## Risks

- Risk-001: Exa API or account availability may fail during demo. Mitigation: README includes fixture fallback and unconfigured graceful failure path.
- Risk-002: Live search result quality may be weak. Mitigation: evidence limitations, relevance/authority scores, Verifier/Critic checks.
- Risk-003: Provider schema changes. Mitigation: normalize behind `ExaSearchProvider` and unit-test schema handling.
- Risk-004: Secret leakage. Mitigation: `.env.example`, `.gitignore`, config redaction tests, no secret in Trace.
- Risk-005: Adding web provider may break fixture regression. Mitigation: provider factory tests, full pytest, fixture eval 5/5 gate.
