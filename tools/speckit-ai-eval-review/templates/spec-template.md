# Feature Specification: [FEATURE NAME]

> Language Policy: English headings, Chinese explanatory body, English AI/Agent terms, and English machine-readable keys.

## Goal

描述这个 feature 要解决的问题、目标用户、核心价值，以及为什么需要用 AI / Agent 能力解决。

## User Stories

- As a [role], I want [capability], so that [outcome].

## Functional Requirements

- FR-001: [中文描述需求，关键术语保留英文]
- FR-002:

## Deep Research / Agent Requirements

- Agent Roles: 明确 `Planner`、`Researcher`、`Verifier`、`Critic`、`Writer` 等角色是否需要，以及各自边界。
- Evidence Grounding: 关键结论必须能追溯到 `Evidence Store`。
- Traceability: 工具调用、子任务状态、输入输出、失败原因必须有 `Trace`。
- Context Engineering: 说明上下文压缩、子 Agent 隔离、摘要或记忆策略的要求。
- Eval Harness: 说明必须如何验证 `Faithfulness`、`Citation Completeness`、`Planner Coverage` 等指标。

## Non-Goals

- NG-001: 本轮明确不做的能力，避免 scope creep。

## Acceptance Criteria

- AC-001: [可验证验收标准]
- AC-002:

## Quality Gates

- Implement 后必须运行 tests 或 eval。
- Deep Research 报告中的关键 claim 必须绑定 evidence。
- Writer 不允许使用未进入 `Evidence Store` 的来源或事实。
- Review 必须输出 `decision` 和 `next_phase`。

## Risks and Open Questions

- Risk-001:
- Question-001:
