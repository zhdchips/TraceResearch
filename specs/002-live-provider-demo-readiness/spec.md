# Feature Specification: Live Provider Demo Readiness

**Feature Branch**: `002-live-provider-demo-readiness`  
**Created**: 2026-06-20  
**Status**: Draft  
**Input**: 用户要求在已完成的 fixture-first deterministic Deep Research harness 基础上，开启新 feature `002-live-provider-demo-readiness`，让项目进化为可演示的真实 research prototype。

> Language Policy: English headings, Chinese explanatory body, English AI/Agent terms, and English machine-readable keys.

## Goal

本 feature 的目标是让 TraceResearch 从 fixture-only MVP 进化为可面试演示的真实 research prototype。用户应能继续使用稳定的 `FixtureSourceProvider` 跑 regression eval，同时可以在配置真实 search credential 后，通过 `traceresearch run --source-provider web` 对一个真实 research query 生成带 `Evidence Store`、`Trace Log` 和 structured final report 的 artifacts。

核心价值不是把系统升级成完整 production search product，而是证明现有 `Agent Harness`、source discovery abstraction、evidence grounding、Trace 和 eval workflow 能从 deterministic fixtures 平滑扩展到 live web source discovery，并且在未配置、超时、无结果、provider error 等情况下保持可解释、可复盘、不会 silent fallback。

## User Stories

- As a demo operator, I want to run a live web-backed Deep Research query from the CLI, so that I can show TraceResearch researching current public sources instead of only fixture data.
  - Priority: P0
  - Independent Test: 在配置有效 search credential 后，运行一个明确的 research query，系统生成 `final_report.md`、`evidence.jsonl`、`trace.jsonl` 和 source metadata，并且 final report 的 key claims 包含 evidence IDs。
  - Acceptance Scenarios:
    1. Given 有效的 live provider configuration, When operator 运行 `traceresearch run --source-provider web` 和一个明确 query, Then 系统完成 run 并生成 inspectable artifacts。
    2. Given live run 已完成, When reviewer 从 final report 选择任意 key claim, Then 能在 `evidence.jsonl` 中找到对应 evidence，并在 `trace.jsonl` 中看到 live provider search/fetch step。

- As a maintainer, I want fixture regression behavior to remain stable, so that adding live search does not make existing MVP quality gates flaky.
  - Priority: P0
  - Independent Test: 不配置任何 live provider credential 时，原有 `python3 -m pytest` 和 fixture eval 仍然通过，且 5 个 seed eval cases 仍保持 5/5 pass。
  - Acceptance Scenarios:
    1. Given 没有 live provider credential, When maintainer 运行 fixture tests/eval, Then 系统仍使用 `FixtureSourceProvider` 并保持 deterministic results。
    2. Given 用户显式选择 `--source-provider fixture`, When live provider configuration 存在或不存在, Then fixture run 不受 live configuration 影响。

- As a demo operator, I want clear setup and failure messages for live provider configuration, so that I can prepare and recover a screen-share demo without digging through source code.
  - Priority: P1
  - Independent Test: 缺少 credential、provider timeout、provider error、no results 等路径均返回明确 status/error，并写入 Trace；README 说明如何配置和验证。
  - Acceptance Scenarios:
    1. Given 未配置 live provider API key, When operator 运行 `traceresearch run --source-provider web`, Then 系统返回 `provider_not_configured`，不 silent fallback 到 fixture。
    2. Given live provider 返回 no results 或 error, When run 结束, Then CLI 和 Trace 明确记录原因，final report 不生成 unsupported conclusion。

- As an evaluator or interviewer, I want a README and demo path that explain project value, architecture, fixture demo, live demo, eval/review workflow, and limitations, so that I can understand the project quickly during an interview.
  - Priority: P1
  - Independent Test: 新读者只看 README 即可完成 fixture demo path，理解 live demo prerequisites，知道 eval/review artifacts 在哪里，并能看到明确 limitations。
  - Acceptance Scenarios:
    1. Given 面试官打开 repository, When 阅读 README, Then 能在 5 分钟内理解项目定位、architecture、demo commands、eval result 和 limitations。
    2. Given operator 准备共享屏幕, When 按 README demo path 操作, Then 能展示 fixture regression、live web demo 或未配置 credential 的 graceful failure。

## Edge Cases

- Live provider API key 缺失、为空、格式明显无效时，系统必须返回 `provider_not_configured` 或等价明确错误，不得 silent fallback 到 fixture。
- Live provider request timeout 时，系统必须记录 timeout error、provider name、query summary 和 latency，并安全终止或降级为 no-evidence limitation。
- Live provider 返回空结果时，系统必须输出 no-results reason，避免生成确定性 unsupported claims。
- Live provider 返回部分缺失 metadata、重复 URL、不可用 URL 或低质量 snippet 时，系统必须保留可用 metadata、去重或标记 limitation。
- Live provider 返回非研究相关结果时，Verifier/Critic 或 eval smoke check 必须能暴露 low relevance 风险。
- Fixture eval 与 live smoke eval 必须分离；live provider 波动不得导致默认 regression gate 不稳定。
- 真实 API key、request logs 中的 secret、或 `.env` 文件不得被提交到 repository。

## Functional Requirements

- FR-001: 系统 MUST 保留 `FixtureSourceProvider` 作为 deterministic regression provider。
- FR-002: 系统 MUST 提供一个 live web search provider capability，可通过 `--source-provider web` 被显式选择。
- FR-003: 系统 MUST 从本地环境配置读取 live provider credential、provider selection、timeout 和 max results，且不得要求用户修改 source code。
- FR-004: 系统 MUST 提供 `.env.example`，列出必需和可选的 live provider configuration，并且不得包含真实 secret。
- FR-005: 当缺少 live provider credential 时，系统 MUST 返回明确 `provider_not_configured` status/error，并写入可用于 `Trace` 的 error details。
- FR-006: 当 live provider timeout、network error、rate limit、provider error 或 no results 时，系统 MUST graceful handling，并在 CLI output、Trace 和 run artifacts 中暴露原因。
- FR-007: 系统 MUST NOT 在用户选择 `--source-provider web` 且 live provider 失败时 silent fallback 到 fixture。
- FR-008: Live provider search results MUST 被 normalized 为现有 source/evidence contract 可消费的 source metadata。
- FR-009: Live run MUST 继续生成 `research_brief.json`、`research_tasks.json`、`evidence.jsonl`、`trace.jsonl`、`final_report.md` 和 `report.json`，除非失败发生在无法安全研究之前。
- FR-010: Live final report 的 key claims MUST 绑定 `Evidence Store` 中的 evidence IDs 或被降级为 limitation/follow-up question。
- FR-011: `Trace` MUST 区分 fixture provider 与 live web provider，并记录 search/fetch step、status、latency、error summary 和 result count。
- FR-012: 原有 fixture tests 和 fixture eval MUST 保持默认稳定回归路径。
- FR-013: 系统 MUST 提供 live smoke validation command 或文档化手动验收流程，但 live smoke MUST NOT 成为默认 CI gate。
- FR-014: 根目录 README MUST 说明项目定位、architecture、run commands、fixture demo、live web demo、eval/review workflow、limitations 和 interview demo path。
- FR-015: README MUST 明确 secret handling：真实 API key 只放本地环境或 ignored `.env`，不得提交。
- FR-016: Live demo readiness MUST include a visible success/failure story：成功时展示 grounded report artifacts；未配置时展示 clear configuration error。

## Key Entities

- `LiveProviderConfig`: 表示 live web provider 的本地配置，包括 provider name、credential presence、timeout、max results 和 optional endpoint settings，不包含明文 secret 输出。
- `LiveSourceResult`: 从真实 web provider 返回并 normalized 后的 source result，至少包含 source ID、title、URL、snippet、publisher/source type guess、retrieved_at、rank 和 provider metadata。
- `ProviderError`: 表示 live provider failure 的结构化错误，包括 error code、message、retryability、provider name、latency 和 safe user-facing summary。
- `DemoRun`: 面向 README 和 interview demo 的一次可复盘 run，包含 query、provider mode、artifact directory、expected inspection path 和 known limitations。

## Deep Research / Agent Requirements

- Agent Roles: 本 feature 不新增新的 Agent role。`Planner`、`Researcher`、`Verifier`、`Critic`、`Writer` 的边界必须保持 001 中定义的固定职责；变化集中在 `Researcher` 使用的 source discovery provider。
- Evidence Grounding: live web source 进入 Writer 前必须先压缩并写入 `Evidence Store`。Writer 只能使用 verified evidence 生成 final report；live provider 不得绕过 Evidence Store。
- Traceability: live provider 的 search/fetch、timeout、no results、provider error、normalization result count 和 selected source IDs 必须写入 `Trace`，以便 bad-case replay。
- Context Engineering: raw live source excerpts 或 snippets 必须在 Researcher/source normalization 阶段压缩为 structured evidence summary；不得把未经压缩的大段 raw page content 直接传给 Writer。
- Eval Harness: fixture eval 继续作为 required regression gate；live smoke 作为 manual/demo validation，至少覆盖 one successful live query when configured 和 provider_not_configured path when unconfigured。Live smoke 结果应检查 `Faithfulness`、`Citation Completeness`、evidence IDs、source metadata 和 Trace coverage。
- Failure Policy: live provider 不确定性必须被显式暴露。无结果、弱来源、冲突来源或 provider failure 时，report 必须呈现 limitation 或停止生成 final report，而不是输出 unsupported conclusion。

## Non-Goals

- NG-001: 本 feature 不实现完整 LLM-backed `Planner`、`Writer`、`Verifier` 或 `Critic`。
- NG-002: 本 feature 不提供 Web UI。
- NG-003: 本 feature 不做 PDF、HTML export 或 presentation export。
- NG-004: 本 feature 不引入大规模 benchmark 或 live web CI gate。
- NG-005: 本 feature 不移除或削弱 fixture deterministic tests/eval。
- NG-006: 本 feature 不实现多 provider marketplace、provider ranking marketplace 或自动 provider fallback chain。
- NG-007: 本 feature 不存储真实 API key，不提交 `.env`，不记录 secret 到 Trace 或 report。
- NG-008: 本 feature 不承诺 live web results 与 fixture eval 一样稳定；live smoke 只验证 demo readiness。

## Acceptance Criteria

- AC-001: Given 未配置 live provider credential, When 用户运行 `traceresearch run --source-provider web`, Then CLI 返回明确 `provider_not_configured` 或等价 configuration error，Trace 记录 error，且不会 fallback 到 fixture。
- AC-002: Given 配置有效 live provider credential, When 用户运行至少一个明确 research query with `--source-provider web`, Then 系统生成 completed run artifacts，包括 `final_report.md`、`evidence.jsonl` 和 `trace.jsonl`。
- AC-003: Given live run completed, When reviewer 检查 final report 的任一 key claim, Then claim 包含 evidence ID，并能在 `evidence.jsonl` 找到 source title、URL 或 source reference、retrieved_at、summary 和 supported claims。
- AC-004: Given live provider timeout、provider error 或 no results, When run finishes or fails safely, Then CLI、Trace 和 artifacts 包含明确 failure/no-evidence reason，final report 不包含 unsupported deterministic conclusion。
- AC-005: Given 没有 live provider credential, When maintainer 运行 `python3 -m pytest`, Then 原有 tests 仍然全绿。
- AC-006: Given maintainer 运行 fixture eval, When eval completes, Then 5 个 seed cases 仍然 5/5 pass，并包含 9 个 required metrics。
- AC-007: Given repository reader 打开 README, When 按 demo path 操作, Then 能运行 fixture demo，并理解 live web demo 的 configuration、success path、failure path 和 limitations。
- AC-008: Given repository review, When 检查 tracked files, Then `.env.example` 存在且不包含真实 secret，真实 `.env` 或 API key 不被提交。

## Success Criteria

- SC-001: 未配置 live credential 时，100% 的 web-provider runs 返回明确 configuration error，并且 0 次 silent fallback 到 fixture。
- SC-002: 配置有效 live credential 后，至少 1 个 live research query 能生成 `final_report.md`、`evidence.jsonl` 和 `trace.jsonl`，并且 final report key claims 100% 带 evidence IDs 或被标记为 limitation/follow-up。
- SC-003: 原有 `python3 -m pytest` 通过率保持 100%。
- SC-004: 原有 fixture eval 保持 5/5 pass，`case_pass_rate=1.0`，并继续输出 9 个 required metrics。
- SC-005: README 中的 fixture demo path 可在 5 分钟内由新读者完成，live demo path 明确区分 configured success 和 unconfigured graceful failure。
- SC-006: Live provider failure cases 的 user-facing error、Trace error 和 artifact limitation 三者至少有两处可观察到同一 failure reason。
- SC-007: Review 时未发现真实 API key、secret-bearing `.env` 或 provider credential 被提交。

## Assumptions

- A-001: 目标用户是项目作者、面试官或技术 reviewer，使用本地 CLI 进行 screen-share demo。
- A-002: Live provider 的具体供应商选择在 plan 阶段决策；默认选择集成成本低、结果结构清晰、可通过单个 API key 使用的 provider。
- A-003: 本 feature 的 live smoke validation 允许依赖外部网络和 provider account，因此不作为默认 CI gate。
- A-004: Existing fixture eval 是稳定质量基线，任何 live provider work 都不得破坏它。
- A-005: Live provider 返回的 snippets/excerpts 足以生成 MVP 级 evidence summaries；完整网页抓取和复杂网页清洗留到后续 feature。
- A-006: Secret handling 采用本地环境变量或 ignored `.env`，README 和 `.env.example` 只提供占位符。

## Quality Gates

- QG-001: Implement 后必须运行 `python3 -m pytest`，并记录结果。
- QG-002: Implement 后必须运行 fixture eval，确认 5 seed cases 仍为 5/5 pass。
- QG-003: 必须验证 unconfigured web provider path 返回 `provider_not_configured` 或等价明确错误，且不 fallback 到 fixture。
- QG-004: 如果可获得 live provider credential，必须记录一条 live smoke run artifact path；如果不可获得，必须记录未执行原因和手动验收命令。
- QG-005: Live final report 的 key claims 必须绑定 `Evidence Store` evidence IDs；无法绑定时必须降级为 limitation 或 follow-up。
- QG-006: Trace 必须覆盖 live provider search/fetch 或 failure path。
- QG-007: README 和 `.env.example` 必须完成后才能 review；任何真实 secret 出现在 tracked files 中均阻塞 completion。

## Risks and Open Questions

- Risk-001: Live provider 结果波动可能导致 demo 不稳定；mitigation 是保留 fixture demo 作为 reliable path，并把 live smoke 标记为 non-CI gate。
- Risk-002: Provider API quota、rate limit 或网络问题可能影响面试演示；mitigation 是 README 提供 unconfigured graceful failure story 和 fixture fallback demo。
- Risk-003: Live snippets 质量不足可能削弱 evidence grounding；mitigation 是 Verifier/Critic 必须暴露 low relevance/weak source limitation。
- Risk-004: Secret handling 错误可能泄露 API key；mitigation 是 `.env.example`、`.gitignore`、README secret policy 和 review gate。
- Risk-005: Provider-specific schema 可能污染 generic source discovery boundary；mitigation 是 plan 阶段明确 normalization contract，fixture provider 继续使用同一 contract。
