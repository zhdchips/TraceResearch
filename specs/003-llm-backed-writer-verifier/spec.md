# Feature Specification: LLM-Backed Writer / Verifier

**Feature Branch**: `003-llm-backed-writer-verifier`
**Created**: 2026-06-21
**Status**: Draft
**Input**: 用户希望在 001/002 已完成的 fixture-first deterministic harness 和 live provider demo readiness 基础上，把当前 deterministic Writer / Verifier 替换为 LLM-backed 实现，同时保留 deterministic fallback 和 fixture regression gate。

> Language Policy: English headings, Chinese explanatory body, English AI/Agent terms, and English machine-readable keys.

## Goal

本 feature 的目标是让 TraceResearch 的 final report writing 和 claim verification 具备 LLM-backed 能力，以生成更自然、更贴近研究报告质量的输出。当前 deterministic Writer 使用模板拼接方式生成报告，deterministic Verifier 只做 evidence ID 存在性检查，两者都无法做语义层面的理解和判断。

核心变化是引入 LLM-backed Writer（基于 verified evidence 生成更自然的 final report）和 LLM-backed Verifier（语义判断 draft claim 是否真的被 evidence 支撑），同时设计一个统一的 abstraction layer（Writer / Verifier 接口），使 deterministic 实现和 LLM-backed 实现可以互换。LLM 调用失败时系统必须安全 fallback 到 deterministic 实现，fixture regression gate 必须保持完全稳定。

本 feature 不实现 LLM-backed Planner 或 Researcher，不做 Web UI，且 LLM smoke eval 仅手动运行，不进入默认 pytest/CI。

## User Scenarios & Testing

### User Story 1 - LLM-backed Writer generates natural report from verified evidence (Priority: P1)

开发者启用 LLM-backed Writer 后，系统使用 LLM 基于 verified evidence 生成结构化的 final report。相比 deterministic 模板拼接，LLM-backed Writer 应能生成更自然的段落、更好的 executive summary、以及对 findings 的语义聚合和解释。

**Why this priority**: Writer 输出是用户可见的核心产物，LLM-backed 改善直接提升最终报告质量，是本 feature 的核心价值。

**Independent Test**: 配置 LLM provider 后，使用 fixture evidence 运行一次 research，对比 deterministic 和 LLM-backed Writer 输出的 final report 质量差异。

**Acceptance Scenarios**:

1. **Given** verified evidence 中有 supported claims, **When** LLM-backed Writer 生成 final report, **Then** final report 包含自然语言的 executive summary、findings、limitations 和 evidence references，且所有 key claims 绑定 evidence ID。
2. **Given** verified evidence 为空或仅有 unsupported claims, **When** LLM-backed Writer 运行, **Then** report 明确指示 no verified findings，不编造无 evidence 支撑的 claim。
3. **Given** LLM 调用失败（timeout、rate limit、provider error）, **When** Writer 检测到错误, **Then** 系统安全 fallback 到 deterministic Writer，Trace 记录 failover reason。

---

### User Story 2 - LLM-backed Verifier semantically judges claim-evidence alignment (Priority: P1)

启用 LLM-backed Verifier 后，系统不仅检查 evidence ID 是否存在，更进一步判断 draft claim 的语义内容是否真的被引用的 evidence 支撑，标记 weakly-supported 或 unsupported 的 claim。

**Why this priority**: Semantic verification 是提升 report 可信度的关键，可捕捉 deterministic Verifier 无法发现的 evidence-claim 不匹配。

**Independent Test**: 对一组包含 correctly-supported、weakly-supported 和 unsupported claims 的 draft，运行 LLM-backed Verifier，检查其分类结果是否与人工判断一致。

**Acceptance Scenarios**:

1. **Given** draft claim 的文本内容与引用的 evidence summary 语义一致, **When** LLM-backed Verifier 检查, **Then** claim 被标记为 SUPPORTED。
2. **Given** draft claim 部分被 evidence 支撑但不完全, **When** LLM-backed Verifier 检查, **Then** claim 被标记为 WEAKLY-SUPPORTED，附带解释。
3. **Given** draft claim 与引用的 evidence 明显矛盾或无关, **When** LLM-backed Verifier 检查, **Then** claim 被标记为 UNSUPPORTED，附带 reasoning。
4. **Given** LLM 调用失败, **When** Verifier 检测到错误, **Then** 系统 fallback 到 deterministic Verifier，Trace 记录 failover reason。

---

### User Story 3 - Deterministic fallback preserves fixture regression stability (Priority: P1)

无论 LLM 是否可用，deterministic Writer / Verifier 必须保持完整的可用性。fixture eval 的 5 个 seed cases 必须继续 5/5 pass，Output Determinism 指标必须保持满分。LLM smoke eval 的失败不得影响 fixture regression gate。

**Why this priority**: 这是用户最核心的约束——不破坏已有质量基线。fixture regression gate 是项目可维护性的基石。

**Independent Test**: 不配置 LLM provider 时，运行 `python3 -m pytest` 和 fixture eval，结果必须与 002 基线一致。

**Acceptance Scenarios**:

1. **Given** LLM provider 未配置或 disabled, **When** 运行 fixture eval, **Then** 5 个 seed cases 保持 5/5 pass，Output Determinism=1.0，所有 9 个 metrics 正常输出。
2. **Given** LLM provider 配置了但 LLM 调用失败, **When** 系统 fallback 到 deterministic path, **Then** run 仍然 complete，Trace 记录 failover event。
3. **Given** live web provider path（002）与 LLM-backed Writer/Verifier 共存, **When** 运行 `--source-provider web`, **Then** 系统行为不因 LLM 配置存在与否而改变 live provider 的逻辑。

---

### User Story 4 - Manual LLM smoke eval runs independently of CI (Priority: P2)

开发者可以通过独立的 manual command 运行 LLM smoke eval，验证 LLM-backed Writer / Verifier 在真实 LLM 下的行为质量。LLM smoke eval 不进入默认 `python3 -m pytest` 或 CI pipeline。

**Why this priority**: LLM smoke eval 依赖外部 LLM 服务和 credential，不确定性高。将其隔离为 manual path 确保 CI 稳定性。

**Independent Test**: 配置 LLM credential 后，运行 manual smoke eval command，检查 eval metrics 和 bad-case notes。

**Acceptance Scenarios**:

1. **Given** LLM credential 配置完成, **When** 运行 LLM smoke eval command, **Then** eval 输出 faithfulness、citation completeness 等 metrics，并记录 bad-case notes。
2. **Given** LLM credential 未配置, **When** 运行 LLM smoke eval command, **Then** 返回明确 "LLM not configured" 信息，不 fallback 到 fixture eval。
3. **Given** 默认 `python3 -m pytest` 运行, **When** LLM smoke eval tests 存在, **Then** LLM smoke eval tests 被 skip 或排除，不影响 test suite pass/fail。

---

### Edge Cases

- LLM provider API key 缺失时，LLM-backed components 必须 fallback 到 deterministic，不得报 fatal error。
- LLM 返回格式不符合预期（missing sections、non-parseable verification result、truncated output）时，系统必须 fallback 到 deterministic 或标记为 limitation，不能将 invalid LLM output 直接写入 final report。
- LLM provider timeout 或 rate limit 时，系统必须记录 latency、error type 到 Trace，并安全 fallback。
- Evidence 数量超过 LLM context window 时，Writer 必须能够安全截断或分批，确保不丢失关键 evidence。
- 同一 claim 引用多个 evidence，其中部分 evidence 被 LLM Verifier 判定不支撑但其他部分支撑时，claim 的最终 support status 必须反映最差情况。
- LLM-backed Writer 生成的 report 可能引入原 evidence 中没有的事实（hallucination），Verifier 或 eval smoke check 必须能检测和标记。
- 用户在不同 run 之间切换 Writer/Verifier mode（deterministic vs LLM-backed）时，两种 mode 的 artifacts 和 Trace 必须明确区分。
- 模拟 LLM 响应的 fixture/mock 环境用于测试时，LLM-backed Writer/Verifier 必须可注入 mock，确保 LLM-dependent 测试不依赖真实 LLM。

## Requirements

### Functional Requirements

- **FR-001**: 系统 MUST 定义 Writer 抽象接口（或协议），使 deterministic Writer 和 LLM-backed Writer 可互换，且 Harness 不感知具体实现。
- **FR-002**: 系统 MUST 定义 Verifier 抽象接口（或协议），使 deterministic Verifier 和 LLM-backed Verifier 可互换，且 Harness 不感知具体实现。
- **FR-003**: LLM-backed Writer MUST 接收 verified evidence 和 research brief 作为输入，输出包含 executive summary、findings、limitations、evidence references 和 follow-up questions 的 final report。
- **FR-004**: LLM-backed Writer 的输出中的每个 key claim MUST 绑定 evidence ID 或被标记为 limitation/follow-up question，不得生成无 evidence 支撑的确定性 claim。
- **FR-005**: LLM-backed Verifier MUST 对每个 draft claim 做语义判断，输出 support status（SUPPORTED / WEAKLY-SUPPORTED / UNSUPPORTED）及 reasoning notes。
- **FR-006**: 系统 MUST 在 LLM 调用失败（timeout、rate limit、provider error、invalid response）时自动 fallback 到对应的 deterministic 实现，并在 Trace 中记录 failover reason 和 error details。
- **FR-007**: 系统 MUST 在 LLM provider 未配置时默认使用 deterministic Writer / Verifier，不尝试 LLM 调用。
- **FR-008**: LLM provider configuration（API key、model selection、timeout、max tokens 等）MUST 通过本地环境配置或配置文件读取，不得要求用户修改 source code。
- **FR-009**: Trace MUST 区分 deterministic Writer/Verifier 和 LLM-backed Writer/Verifier，并记录 LLM mode、model、latency、token usage 和 failover events。
- **FR-010**: 系统 MUST 支持在 run 级别选择 Writer mode 和 Verifier mode（deterministic 或 LLM-backed），两种 mode 产生的 artifacts 必须有明确区分。
- **FR-011**: LLM smoke eval MUST 作为独立 manual command，不进入默认 `python3 -m pytest` 或 CI pipeline。
- **FR-012**: LLM smoke eval MUST 至少覆盖 faithfulness、citation completeness 和 unsupported claim detection 三个维度的检查。
- **FR-013**: 原有 deterministic tests（001 fixture eval、002 live provider tests）MUST 在没有 LLM 配置时保持 100% pass rate。
- **FR-014**: 系统 MUST 提供 mock/fake LLM provider 供测试使用，确保 LLM-dependent 组件可以在没有真实 LLM 的环境中验证 failover 行为和接口契约。
- **FR-015**: LLM-backed Writer 在 evidence 超过 context window 限制时 MUST 做安全截断或分批处理，并记录截断信息到 Trace。
- **FR-016**: 系统 MUST 验证 LLM Verifier 返回的 support status 和 claim IDs 与输入一致，若不一致则视为 invalid response 并触发 fallback。
- **FR-017**: 项目 MUST 提供 `.env.example` 更新（或 LLM configuration documentation），说明 LLM provider 的配置方式，且不包含真实 API key。

### Key Entities

- **WriterInterface / WriterProtocol**: Writer 的抽象接口，定义 `draft(brief, evidence) -> DraftReport` 和 `final(brief, verified_evidence, verification, critique) -> FinalReport` 两个方法签名。
- **VerifierInterface / VerifierProtocol**: Verifier 的抽象接口，定义 `verify(run_id, draft, evidence) -> VerificationResult` 方法签名。
- **LLMWriterConfig**: LLM-backed Writer 的配置，包含 model ID、API endpoint、credential reference、temperature、max tokens、timeout、fallback strategy。
- **LLMVerifierConfig**: LLM-backed Verifier 的配置，包含 model ID、API endpoint、credential reference、timeout、judgment criteria。
- **LLMFailoverEvent**: LLM 调用失败时的 Trace 事件，包含 error type、model、latency、failover destination（deterministic writer/verifier）和 reason。
- **LLMProviderConfig**: 全局 LLM provider 配置，包含 API key environment variable name、base URL、default model 和全局 timeout。

### Deep Research / Agent Requirements

- **Agent Roles**: 本 feature 不新增 Agent role。`Writer` 和 `Verifier` 的职责边界保持 001 中定义不变，仅替换内部实现为 LLM-backed。`Planner`、`Researcher`、`Critic` 保持不变，且本 feature 不修改它们。
- **Evidence Grounding**: LLM-backed Writer 仍只能使用 `Evidence Store` 中的 verified evidence。LLM 调用时的 prompt 必须包含 evidence text 作为 grounding context，并要求 LLM 为每个 key claim 输出 evidence ID reference。LLM 不允许引入未在 evidence 中出现的外部知识作为确定性 claim。
- **Traceability**: LLM-backed 的每个 call 必须在 Trace 中记录：mode（LLM vs deterministic）、model、prompt summary（不含完整 prompt content，避免 Trace 过大）、token usage、latency、failover reason（如适用）。LLM smoke eval 的 eval run 必须有完整 Trace。
- **Context Engineering**: LLM-backed Writer 的 prompt 必须只包含 evidence summaries 和 research brief，不包含原始 source content。当 evidence 总量超过 LLM context window 安全上限时，必须做截断或优先级排序，并在 Trace 中记录 context limitation。
- **Eval Harness**: fixture eval 继续作为 required regression gate；LLM smoke eval 作为 manual validation，检查 faithfulness、citation completeness、unsupported claim detection。LLM smoke eval 结果必须包含 bad-case notes 和 suggested next_phase。

## Non-Goals

- **NG-001**: 本 feature 不实现 LLM-backed Planner 或 Researcher。
- **NG-002**: 本 feature 不提供 Web UI。
- **NG-003**: 本 feature 不移除或削弱 deterministic Writer / Verifier。
- **NG-004**: 本 feature 不做 PDF、HTML export 或 presentation export。
- **NG-005**: 本 feature 不引入 LLM evaluation benchmark 或 leaderboard。
- **NG-006**: 本 feature 不实现多 LLM provider 的自动 failover chain 或 provider ranking。
- **NG-007**: 本 feature 不修改 fixture provider 或 live web provider 的 source discovery 逻辑。
- **NG-008**: 本 feature 不承诺 LLM smoke eval 结果与 fixture eval 一样稳定；LLM 输出不确定性属于预期行为。

## Success Criteria

- **SC-001**: LLM-backed Writer 生成的 final report 中的 key claims 100% 绑定 evidence ID 或被标记为 limitation，fake claim 率（hallucination）为 0。
- **SC-002**: LLM-backed Verifier 在面对 correctly-supported、weakly-supported 和 unsupported claims 的混合测试集时，分类准确率达到 80% 以上（与人工标注对比）。
- **SC-003**: LLM 调用失败时，100% 的 case 安全 fallback 到 deterministic 实现，0 次 fatal crash 或 corrupt artifact。
- **SC-004**: 原有 `python3 -m pytest` pass rate 保持 100%（与 002 基线一致）。
- **SC-005**: 原有 fixture eval 保持 5/5 pass，`case_pass_rate=1.0`，Output Determinism=1.0，9 个 required metrics 正常输出。
- **SC-006**: LLM smoke eval 中的 faithfulness 至少达到 pass threshold（人工 review 确认 key claims 有对应 evidence 支撑）。
- **SC-007**: 开发者可在 5 分钟内通过 README 或文档完成 LLM configuration 和首次 LLM smoke eval 运行。

## Assumptions

- **A-001**: LLM provider 选择在 plan 阶段决策；默认选择 API 兼容性好、有 Python SDK、可通过单个 API key 使用的 provider。
- **A-002**: 本 feature 的 LLM smoke eval 依赖外部 LLM 服务和 credential，因此不作为 CI gate，只做 manual validation。
- **A-003**: 现有 fixture eval 的 5 个 seed cases 足以验证 deterministic fallback 的 regression 稳定性。
- **A-004**: LLM-backed Writer/Verifier 的 prompt engineering 为 plan 阶段决策，本 spec 只定义输入输出 contract。
- **A-005**: Evidence Store 中的 evidence summaries 在 MVP 阶段适合 LLM context window（通常不超过 5-10 条 evidence），大型 research（50+ evidence）的 context management 为后续 feature。
- **A-006**: 用户已有的 live smoke artifact（runs/run-d09f5082）可作为 LLM-backed Writer/Verifier 的 smoke eval input，用于对比 deterministic 和 LLM-backed 输出质量。
- **A-007**: Writer 和 Verifier 的抽象接口设计遵循 001 已确立的 dependency injection 模式（Harness 构造函数接受可选组件）。

## Risks and Open Questions

- **Risk-001**: LLM 输出格式可能不稳定，导致 parse failure 和 fallback；mitigation 是 prompt 中要求结构化输出，并做 post-validation on parse result。
- **Risk-002**: LLM-backed Writer 可能引入 bias 或 "听起来合理但证据不足" 的结论；mitigation 是 LLM-backed Verifier + eval smoke check 的双重检查。
- **Risk-003**: LLM token cost 和 latency 可能影响开发体验；mitigation 是 deterministic fallback 作为默认，LLM mode 仅为 opt-in。
- **Risk-004**: 接口抽象设计不当可能导致 Harness 代码复杂化或破坏现有测试；mitigation 是 plan 阶段明确接口设计，确保向后兼容。
- **Risk-005**: LLM promoter 的 prompt injection 风险（evidence 中包含误导性内容影响 LLM 判断）；mitigation 是 prompt 中明确 instruction hierarchy。
- **Open Question-001**: LLM provider 的具体选择（如 Anthropic Claude、OpenAI GPT 等）和 SDK 集成方式留给 `/speckit-plan` 阶段决策。
- **Open Question-002**: LLM-backed Writer/Verifier 的 mode selection mechanism（CLI flag、config file、环境变量）留给 `/speckit-plan` 阶段设计。

## Quality Gates

- **QG-001**: Implement 后必须运行 `python3 -m pytest`，确认 100% pass。
- **QG-002**: Implement 后必须运行 fixture eval，确认 5 seed cases 5/5 pass，Output Determinism=1.0。
- **QG-003**: LLM smoke eval command 必须可用且文档化，包括 configuration instructions 和 expected output format。
- **QG-004**: LLM failover path 必须验证：mock LLM failure 时系统安全 fallback 到 deterministic，不 crash。
- **QG-005**: LLM-backed Writer 的 key claims 必须 binding evidence ID；无法绑定时标记为 limitation。
- **QG-006**: LLM smoke eval 的 eval result 必须输出 faithfulness、citation completeness 和 unsupported claim 检查。
- **QG-007**: Trace 必须区分 LLM-backed 和 deterministic mode，并记录 failover events。
- **QG-008**: 不得提交真实 LLM API key 到 repository。
