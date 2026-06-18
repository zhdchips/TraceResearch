# Research: Deep Research Multi-Agent MVP

## Decision: Python 3.11+ CLI-first single package

Rationale: MVP 需要快速验证 Agent Harness、schema validation、JSONL artifacts、Markdown report 和 eval runner。Python 生态适合处理本地文件、CLI、测试和后续 LLM/search provider 接入。

Alternatives considered:

- Web service first: 对 MVP 的 evidence/trace/eval 验证没有必要，会引入多余部署和 UI complexity。
- Notebook-only prototype: 方便探索，但不利于 repeatable eval、artifact contracts 和后续 tasks 拆分。

## Decision: Pydantic v2 for domain schemas

Rationale: `ResearchBrief`、`Evidence`、`TraceEvent`、`EvalResult` 都需要 JSON serialization、validation rules 和清晰错误信息。Schema-first 能让 eval 和 report grounding 更可测。

Alternatives considered:

- Plain dicts: 快，但会把字段一致性问题推迟到运行时。
- Dataclasses only: 简洁，但 JSON validation 和 nested model error reporting 不如 Pydantic 直接。

## Decision: Filesystem artifacts over database

Rationale: MVP 的主要需求是可复盘、可分享、可 bad-case replay。`runs/<run_id>/`、`evidence.jsonl`、`trace.jsonl`、`final_report.md` 足够支撑第一版，而且便于 review。

Alternatives considered:

- SQLite: 查询方便，但会增加 migration 和 inspection 成本。
- Document store: 对单用户本地 MVP 过重。

## Decision: FixtureSourceProvider is the first real provider

Rationale: 5 个 seed eval cases 必须稳定、可重复、可离线。Fixture provider 可以真实跑通 source discovery contract、fetch/summary path、Evidence Store 和 eval metrics，而不被外部搜索服务、API key、rate limit 或网页变动影响。

Alternatives considered:

- Live web search first: 更接近真实使用，但会让 MVP 质量判断被网络和 provider 波动污染。
- Fully mocked source discovery: 太弱，无法验证 provider contract 和 evidence artifacts。

## Decision: WebSearchProviderStub defines future live integration

Rationale: MVP 需要明确 source discovery 抽象，但不需要立即绑定某个商业 search API。Stub 负责 not-configured error、provider metadata 和 contract tests，后续可替换成真实 provider。

Alternatives considered:

- No live provider shape: 会导致后续接入时重改 Researcher 边界。
- Choose a specific provider now: 容易过早绑定成本、配额和 API semantics。

## Decision: Rule/template Agent implementations first

Rationale: 计划优先验证 contracts、Evidence Store、Trace、report artifact 和 eval loop。Model-backed agents 可以在相同 module boundary 下替换，但不是 MVP 成败的唯一风险。

Alternatives considered:

- Model-backed first: 更像最终产品，但容易把 schema、trace、eval 缺口藏在 prompt 行为里。
- One monolithic agent: 快，但违背 role isolation 和 traceability。

## Decision: Markdown + JSON report artifacts

Rationale: `final_report.md` 适合人类阅读和 demo，`report.json` 适合 eval 检查 claims、evidence IDs、unsupported claims 和 metrics references。

Alternatives considered:

- Markdown only: 人类友好但难以自动验证。
- JSON only: 可测但不适合作为 research report 交付物。

## Decision: Serial orchestration in MVP

Rationale: 串行执行 research tasks 更容易保证 Trace 清晰、失败处理简单、eval 可重复。并发调度属于明确 Non-Goal。

Alternatives considered:

- Parallel research tasks: 更快，但需要处理 rate limit、partial failure、ordering 和 shared state complexity。
