# Feature Specification: Deep Research Multi-Agent MVP

**Feature Branch**: `001-deep-research-multi-agent-mvp`
**Created**: 2026-06-18
**Status**: Draft
**Input**: 用户要求为 TraceResearch 创建第一版 MVP feature specification。系统输入复杂技术/业务研究问题，输出一份带 evidence grounding 的结构化 research report。

> Language Policy: English headings, Chinese explanatory body, English AI/Agent terms, and English machine-readable keys.

## Goal

TraceResearch 第一版 MVP 要构建一个 Deep Research 场景的 multi-agent 研究助手。目标用户输入一个复杂技术或业务研究问题后，系统能够先形成清晰的 `research_brief`，再从多个 perspective 进行资料收集、source summarization、evidence verification、critique 和 outline-first writing，最终输出一份结构化 research report。

本 feature 的核心价值是让用户不仅得到一段总结性回答，还能看到关键结论背后的 evidence grounding、source metadata、unsupported claim 风险和可复盘的 Trace。系统必须优先证明“研究结论可信、可追溯、可评估”，而不是追求复杂 autonomous supervisor 或大规模并行能力。

## User Stories

- As a research user, I want to submit a complex technical or business research question, so that I can receive a structured research report with evidence-backed conclusions.
  - Priority: P0
  - Independent Test: 给定一个 seed eval case，系统能产出 `research_brief`、perspectives、research tasks、verified evidence、outline 和 final report。
  - Acceptance Scenarios:
    1. Given 一个范围明确的问题, When 用户启动 Deep Research run, Then 系统生成包含 objective、scope、perspectives、research tasks 和 success criteria 的 `research_brief`。
    2. Given 已完成研究流程, When 用户查看 final report, Then 报告中的关键 claim 均能追溯到 `Evidence Store` 中的 evidence ID 或 source reference。

- As a research user, I want the system to handle unclear or over-broad questions safely, so that expensive research does not start from an ambiguous request.
  - Priority: P0
  - Independent Test: 输入缺少研究对象、时间范围或输出目标的问题，系统必须返回 clarification request 或记录明确 assumption。
  - Acceptance Scenarios:
    1. Given 用户问题缺少研究对象, When 系统尝试创建 `research_brief`, Then 系统要求用户澄清或记录一个可见 assumption。
    2. Given 用户问题过宽, When 系统继续研究, Then `research_brief` 明确 scope boundaries 和 Non-Goals。

- As a reviewer, I want to inspect evidence and trace artifacts, so that I can understand how each Agent step affected the final report.
  - Priority: P1
  - Independent Test: 任意完成的 run 都能展示每个 Agent role 的输入摘要、输出摘要、状态、失败原因和关键 evidence 产物。
  - Acceptance Scenarios:
    1. Given 一个完成的 run, When reviewer 检查 Trace, Then 能看到 `Planner`、`Researcher`、`Verifier`、`Critic`、`Writer` 的主要 step 和 status。
    2. Given final report 中的一个关键 claim, When reviewer 追溯 evidence ID, Then 能看到 source title、source type、summary、supported claims 和 retrieved_at。

- As an evaluator, I want to run a small fixed eval set, so that MVP behavior can be compared across iterations.
  - Priority: P1
  - Independent Test: 运行 5 个 seed eval cases 后，系统输出每个 case 的 metrics summary 和 bad-case notes。
  - Acceptance Scenarios:
    1. Given 5 个 seed eval cases, When eval run 完成, Then 输出 `planner_coverage`、`perspective_diversity`、`source_relevance`、`source_authority`、`citation_completeness`、`faithfulness`、`unsupported_claim_count`、`critical_hallucination_count` 和 `case_pass_rate`。
    2. Given 某个 case 出现 unsupported claim, When evaluator 查看结果, Then 结果中明确标记失败 claim、相关 evidence gap 和建议 next_phase。

## Edge Cases

- 用户问题缺少研究对象、时间范围或输出目标时，系统必须 clarification 或记录 assumption，不能直接生成确定性 report。
- Search 或 source discovery 结果为空时，系统必须输出 no-evidence reason，并在 final report 中标记 limitation。
- Sources 之间出现冲突时，系统必须保留 conflicting evidence，并避免给出单一确定结论。
- Evidence quality 过低时，Verifier 必须标记 weak support，Writer 不得把相关 claim 写成强结论。
- Context compression 丢失关键事实时，Trace 或 eval bad-case notes 必须暴露该问题，供下一轮 plan/tasks 修复。
- 任一 Agent step 或 tool action 失败时，Trace 必须记录 failure status 和 error summary，run 不得被误标记为完整成功。

## Functional Requirements

- FR-001: 系统 MUST 接收一个复杂技术或业务研究问题，并为每次研究创建唯一的 `run_id`。
- FR-002: 系统 MUST 在研究开始前生成 `research_brief`，至少包含 objective、scope boundaries、assumptions、perspectives、research tasks、success criteria 和 open clarifications。
- FR-003: 系统 MUST 在问题缺少研究对象、时间范围或输出目标时，返回 clarification request 或记录继续研究所依赖的 assumption。
- FR-004: 系统 MUST 包含并区分 `Planner`、`Researcher`、`Verifier`、`Critic` 和 `Writer` 五个 Agent roles。
- FR-005: `Planner` MUST 负责生成 `research_brief`、perspectives 和 research tasks，且每个 research task 必须绑定一个 research objective 或 perspective。
- FR-006: `Researcher` MUST 对分配的 research task 进行 source discovery 和 source summarization，并输出结构化 evidence candidates。
- FR-007: `Evidence Store` MUST 保存 evidence ID、source metadata、authority signal、summary、key points、supported claims、retrieved_at 和 source-to-task 关系。
- FR-008: `Verifier` MUST 检查 evidence quality 和 claim support，并标记 unsupported、weakly-supported 或 citation-mismatched claims。
- FR-009: `Critic` MUST 检查 missing perspectives、weak sources、duplicate content、unsupported claims 和 report limitation coverage。
- FR-010: `Writer` MUST 先生成 outline 或 report plan，再只基于 verified evidence 生成 final report。
- FR-011: Final report MUST 包含 executive summary、research scope、method overview、findings、limitations、evidence references 和 follow-up questions。
- FR-012: Final report 中的关键 claim、comparison、recommendation 和 limitation MUST 绑定 evidence ID 或 source reference。
- FR-013: 系统 MUST 拒绝、降级或重新研究无法被 `Evidence Store` 支撑的关键 claim。
- FR-014: 系统 MUST 为每个 Agent step 和 tool action 记录 Trace，至少包含 `run_id`、`task_id`、`agent_role`、`event_type`、`tool_name`、input summary、output summary、status、latency、token usage 和 error。
- FR-015: 系统 MUST 将 long source content 压缩为 structured evidence summary 后再进入 shared synthesis context。
- FR-016: 系统 MUST 保留中间 artifacts，使 reviewer 能复盘 `research_brief`、evidence、verification result、critique、outline、draft report、final report 和 eval result。
- FR-017: MVP MUST 提供 5 个 seed eval cases，覆盖 framework comparison、high-risk domain design、trend research、source/project research 和 controversial question。
- FR-018: Eval result MUST 输出 metrics summary、case-level pass/fail、bad-case notes 和 suggested next_phase。
- FR-019: 系统 MUST 明确标注 sources insufficient、conflicting evidence、tool failure、context compression loss 和 verification failure 等失败状态。
- FR-020: 系统 MUST 避免直接复制 reference project source code；设计灵感必须保持为项目本地 decision 或 design note。

## Key Entities

- `ResearchRun`: 一次用户 research request 的完整生命周期，包含 `run_id`、input question、status、timestamps、final report 和 eval/review status。
- `ResearchBrief`: `Planner` 产出的研究契约，包含 objective、scope、assumptions、perspectives、research tasks 和 success criteria。
- `ResearchTask`: 面向单个 perspective 或 research objective 的可执行研究单元，关联 Researcher 输出和 evidence candidates。
- `Evidence`: 可追溯资料单元，包含 source metadata、authority signal、summary、key points、supported claims 和 retrieved_at。
- `Claim`: final report 或 draft 中的可验证陈述，必须能关联到 one or more Evidence entries 或被标记为 unsupported。
- `TraceEvent`: Agent step 或 tool action 的复盘记录，用于 bad-case replay 和 review。
- `EvalCase`: 固定评估输入和期望观察点，用于衡量不同迭代的 Deep Research 行为质量。
- `EvalResult`: 针对 run 或 case 的 metrics、pass/fail、bad-case notes 和 suggested next_phase。

## Deep Research / Agent Requirements

- Agent Roles: MVP MUST 包含 `Planner`、`Researcher`、`Verifier`、`Critic` 和 `Writer`。`Planner` 负责 task decomposition 和 perspectives；`Researcher` 负责 search 与 source summarization；`Verifier` 负责 evidence quality 和 claim support；`Critic` 负责 missing perspective、weak reasoning、duplicate section 和 limitation 检查；`Writer` 只能使用 verified evidence 生成 outline 和 final report。
- Evidence Grounding: 关键结论必须能追溯到 `Evidence Store`。Writer 不允许使用未进入 `Evidence Store` 的来源或事实；unsupported claim 必须被拒绝、标注 unknown，或进入 additional research。
- Traceability: 每个 Agent step、research task、tool action、verification result、critique result 和 report generation step 必须有 Trace。Trace 必须足够支持 reviewer 判断失败来自 query ambiguity、planning gap、source quality、context compression、verification 还是 writing。
- Context Engineering: Raw source content 必须停留在 Researcher 或 evidence creation 阶段；共享 synthesis context 只接收 structured evidence summary、verified claims、outline 和 critique。不同 research task 的上下文必须隔离，避免跨 perspective 混入未验证事实。
- Eval Harness: MVP MUST 使用 5 个 seed eval cases 验证 `planner_coverage`、`perspective_diversity`、`source_relevance`、`source_authority`、`citation_completeness`、`faithfulness`、`unsupported_claim_count`、`critical_hallucination_count` 和 `case_pass_rate`。Eval 必须输出可复盘的 metrics 和 bad-case notes。

## Non-Goals

- NG-001: MVP 不提供 Web UI。
- NG-002: MVP 不实现长期 memory 或跨 run 个性化记忆。
- NG-003: MVP 不实现完整 sandbox provider 或执行隔离系统。
- NG-004: MVP 不实现 skills 插件系统、skills marketplace 或动态技能安装。
- NG-005: MVP 不支持多用户、团队权限或组织级协作。
- NG-006: MVP 不支持 PDF 上传或复杂文件解析 pipeline。
- NG-007: MVP 不实现大规模并行调度或复杂 autonomous supervisor loop。
- NG-008: MVP 不接入大型 benchmark；只要求 5 个 seed eval cases。
- NG-009: MVP 不复刻 Open Deep Research、STORM 或 DeerFlow，也不复制其 source code。

## Success Criteria

- SC-001: 在 5 个 seed eval cases 中，100% 的 completed final reports 必须为关键 claim 提供 evidence ID 或 source reference。
- SC-002: 在 5 个 seed eval cases 中，`critical_hallucination_count` 必须为 0。
- SC-003: 至少 4/5 个 seed eval cases 的 `planner_coverage` 达到 pass，且每个 pass case 至少包含 3 个 distinct perspectives。
- SC-004: 至少 4/5 个 seed eval cases 的 `citation_completeness` 达到 pass。
- SC-005: 对每个 completed run，reviewer 必须能在 3 分钟内从 final report 的任一关键 claim 追溯到 supporting evidence 和相关 Trace summary。
- SC-006: 对 unclear 或 over-broad queries，系统必须在 100% 的测试样例中生成 clarification request 或显式 assumption，而不是直接输出 unsupported report。
- SC-007: Eval output 必须覆盖全部 9 个指定 metrics，并为 failed case 记录 bad-case notes 和 suggested next_phase。

## Acceptance Criteria

- AC-001: Given 一个明确的复杂研究问题, When 用户启动 MVP research run, Then 系统生成包含 objective、scope、perspectives、research tasks 和 success criteria 的 `research_brief`。
- AC-002: Given `Planner` 已生成 research tasks, When `Researcher` 执行每个 task, Then 每个 task 至少输出一个 evidence candidate 或一个明确的 no-evidence reason。
- AC-003: Given evidence candidates 已生成, When `Verifier` 运行, Then 每个 key claim 的 support status 被标记为 supported、weakly-supported、unsupported 或 conflicting。
- AC-004: Given verified evidence 可用, When `Writer` 生成 report, Then report 包含 outline-driven sections，并且关键 claim 引用 evidence ID 或 source reference。
- AC-005: Given report draft 包含 unsupported claim, When `Critic` 或 `Verifier` 检查 draft, Then 系统阻止该 claim 进入 final report，或将其标记为 unknown/needs research。
- AC-006: Given 任意 completed run, When reviewer 检查 Trace, Then 能看到每个 Agent role 的 step、status、input summary、output summary 和 error。
- AC-007: Given 5 个 seed eval cases, When eval run 完成, Then 输出 metrics summary、case pass/fail、bad-case notes 和 suggested next_phase。
- AC-008: Given reference design materials, When spec/plan/tasks 使用其思想, Then 输出必须体现项目本地取舍，而不是复制 upstream source code 或盲目复刻完整系统。

## Quality Gates

- QG-001: Implement 后必须运行 tests 或 eval；如果 eval runner 尚未完成，必须至少产出 `eval.md` 说明可运行 eval plan 和缺口。
- QG-002: Deep Research 报告中的关键 claim 必须绑定 evidence；无法绑定的 claim 不得作为确定性结论进入 final report。
- QG-003: Writer 不允许使用未进入 `Evidence Store` 的来源或事实。
- QG-004: 每个 run 必须有 Trace；缺失 Trace 的 run 不得标记为 complete。
- QG-005: Review 必须输出 `decision` 和 `next_phase`。如果 evidence grounding、citation completeness、faithfulness 或 planner coverage 未达标，`next_phase` 必须回到 spec、plan 或 tasks 中对应阶段。
- QG-006: MVP scope 不得加入 Web UI、长期 memory、完整 sandbox、skills 插件系统、多用户、PDF 上传、大规模并行调度或大型 benchmark，除非先修改 spec 并重新通过 review。
- QG-007: Reference projects 只能作为 design reference；任何架构借鉴都必须落到本项目的本地需求、Non-Goals 和 Quality Gates。

## Assumptions

- A-001: MVP 的主要用户是个人研究者或开发者，关注技术/业务研究质量和可复盘性，不要求团队协作能力。
- A-002: MVP 的输入以自然语言 research question 为主，输出以结构化 text research report 为主。
- A-003: MVP 默认至少存在一种可用的 source discovery 能力，但本 spec 不限定具体 provider 或技术实现。
- A-004: MVP 的 eval seed cases 优先用于行为质量回归，不用于公开 leaderboard 或大型 benchmark 对比。
- A-005: 当 source 不足或 evidence 冲突时，系统优先暴露 uncertainty 和 limitation，而不是强行给出确定结论。

## Risks and Open Questions

- Risk-001: Evidence quality 可能受 source discovery 覆盖率影响；MVP 必须通过 source authority、citation completeness 和 bad-case notes 暴露风险。
- Risk-002: Context compression 可能丢失关键细节；MVP 必须通过 Trace、Evidence summary 和 Verifier 检查降低风险。
- Risk-003: Planner 生成的 perspectives 可能覆盖不足；MVP 必须通过 `planner_coverage` 和 `perspective_diversity` eval 指标持续暴露问题。
- Risk-004: Writer 可能生成听起来合理但 evidence 不足的 claim；MVP 必须通过 Evidence-Grounded Output、Verifier、Critic 和 Quality Gates 阻断。
- Open Question-001: 具体 source discovery provider、report artifact 格式和 eval runner 触发命令留给 `/speckit-plan` 阶段决策。
