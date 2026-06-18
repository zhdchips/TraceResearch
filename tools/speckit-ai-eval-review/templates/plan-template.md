# Implementation Plan: [FEATURE NAME]

> Language Policy: English headings, Chinese explanatory body, English AI/Agent terms, and English machine-readable keys.

## Architecture

描述系统整体架构、主要模块、模块边界和运行链路。

## Agent Roles

| Role | Responsibility | Inputs | Outputs | Tools |
| --- | --- | --- | --- | --- |
| Planner | 任务拆解与研究维度规划 | user query | research plan | none / model |
| Researcher | 多角度检索与资料摘要 | research task | evidence candidates | search / fetch |
| Verifier | 证据质量和 claim 支撑检查 | evidence / draft claims | verification result | evaluator |
| Critic | 缺失视角、风险、反例检查 | draft report | critique | model |
| Writer | 基于 evidence 生成报告 | verified evidence | final report | none |

## Data Flow

1. User query -> Planner
2. Planner -> Research tasks
3. Researcher -> Evidence Store
4. Verifier / Critic -> Quality signals
5. Writer -> Final report with citations

## Evidence Store Design

说明 evidence 的结构、去重、来源可信度、引用 ID、claim-level grounding 是否支持。

Suggested fields:

```yaml
evidence_id:
source_url:
source_title:
source_type:
authority_score:
summary:
supported_claims:
retrieved_at:
```

## Trace Design

说明如何记录:

- run_id
- agent_role
- task_id
- tool_name
- tool_args
- tool_result_summary
- status
- latency_ms
- token_usage
- error

## Eval Harness Design

说明 eval case、指标、运行命令、结果保存位置和阈值。

Suggested metrics:

- `case_pass_rate`
- `planner_coverage`
- `source_relevance`
- `source_authority`
- `citation_completeness`
- `faithfulness`
- `unsupported_claim_count`
- `critical_hallucination_count`

## Technical Decisions

- TD-001: [技术选型 / 取舍 / 原因]

## Failure Handling

说明工具失败、来源不足、证据冲突、上下文压缩丢信息、Writer 生成 unsupported claim 时如何处理。

## Test Strategy

说明 unit tests、integration tests、eval runner、golden cases 和 bad case replay。

## Risks

- Risk-001:
