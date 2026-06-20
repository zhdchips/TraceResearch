# Research: Live Provider Demo Readiness

## Decision: Exa is the first live web search provider

Rationale: Exa 的 `/search` endpoint 明确支持在搜索 web 的同时提取 result contents。官方 response 示例包含 `title`、`url`、`publishedDate`、`author`、`text`、`highlights`、`summary`、`requestId` 和 `costDollars` 等字段，适合直接 normalize 到 TraceResearch 的 `SourceResult`、`SourceDocument` 和 `Evidence`。Exa Python SDK 文档还建议 first integration 使用 `contents={"highlights": True}`，因为 highlights 能保留 relevant evidence，同时避免把 full page text 全量拉进上下文。

Sources:

- Exa Search reference: `https://exa.ai/docs/reference/search`
- Exa Python SDK docs: `https://exa.ai/docs/sdks/python-sdk`

Alternatives considered:

- Tavily Search API: Tavily 的 `/search` endpoint 和 Python SDK 很适合 AI agents，response 示例包含 title、URL、content、score、raw_content 等字段，接入也简单。但本 feature 更重视 evidence compression 与 result contents/highlights，Exa 在这一点上更贴近当前 Evidence Store/Context Engineering 目标。
- Brave Search API: 适合 general search，但 first demo 对 evidence snippets/highlights 的需求更强。
- Stub-only: 无法满足 live demo readiness。

## Decision: Use REST integration before provider SDK

Rationale: 当前项目在本地 editable install 上曾遇到 Python build tooling / SSL 环境问题。为了保持 demo setup 简洁，第一版 live provider 直接使用 Python standard library HTTP client 调 Exa REST API，避免新增 SDK install friction。后续如果需要更完整的 provider features，可以在单独 feature 中考虑 `exa-py`。

Alternatives considered:

- `exa-py` SDK: 官方 SDK 更舒适，但会增加 dependency install 变量。
- `requests` / `httpx`: API 更顺手，但引入新 dependency；当前需求可以由 stdlib 覆盖。

## Decision: Environment-only secret/config management

Rationale: 本 feature 是 local CLI demo readiness，最安全简单的做法是用环境变量和 `.env.example`。真实 API key 只在本地 shell 或 ignored `.env` 中存在，config object 只暴露 `has_api_key`，Trace/CLI/error 不输出 secret。

Planned environment keys:

- `TRACERESEARCH_WEB_PROVIDER=exa`
- `EXA_API_KEY=<local secret>`
- `TRACERESEARCH_WEB_TIMEOUT_SECONDS=10`
- `TRACERESEARCH_WEB_MAX_RESULTS=5`

Alternatives considered:

- CLI `--api-key`: 容易进入 shell history，不作为 first path。
- Tracked config file: secret handling 风险更高。
- Provider-specific `.toml`: 对单 provider demo 过重。

## Decision: Keep fixture regression as default quality gate

Rationale: Live web search 受网络、quota、provider uptime、index freshness 和 ranking 影响，不应影响默认 pytest/CI gate。Fixture eval 已经证明 001 MVP 的 deterministic behavior，必须继续作为 regression baseline。

Alternatives considered:

- Live smoke in default pytest: flakiness risk too high.
- Replace fixture eval with live eval: breaks reproducibility and bad-case comparison.

## Decision: Provider failure is explicit and terminal/limited, never fallback

Rationale: 用户显式选择 `--source-provider web` 时，如果系统 silent fallback 到 fixture，会让 demo 看起来成功但实际没有使用 live web。失败必须在 CLI、Trace 和 artifacts 中可见。

Alternatives considered:

- Fallback to fixture for convenience: rejected because it hides provider failures.
- Retry across multiple live providers: out of scope for this feature.

## Decision: README is part of feature completion

Rationale: 目标是 demo readiness。只有代码能跑还不够，面试官需要快速理解项目定位、architecture、fixture demo、live web demo、eval/review workflow 和 limitations。README 应包含一条 screen-share demo path：先展示 fixture reliability，再展示 live provider configured success 或 unconfigured graceful failure。

Alternatives considered:

- Keep docs only under specs: 不利于 repository reader。
- Only quickstart: 不足以表达项目价值和架构。
