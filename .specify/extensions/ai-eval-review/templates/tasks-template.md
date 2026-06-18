# Tasks: [FEATURE NAME]

> Language Policy: English headings, Chinese task descriptions, English task IDs / file paths / commands / AI-Agent terms.

## Task Format

Use this format:

```md
- [ ] T001 [P0] [中文任务描述，关键术语保留英文]
  - DoD:
  - Tests:
  - Related files:
```

## Phase 1: Foundation

- [ ] T001 [P0] 初始化项目结构与基础配置
  - DoD: 项目可以安装依赖并运行基础检查。
  - Tests: 运行基础 test / lint / typecheck 命令。
  - Related files:

## Phase 2: Core Multi-Agent Flow

- [ ] T002 [P0] 实现 `Planner` 输出结构化 research plan
  - DoD: 给定 query 可以输出 research dimensions 和 sub-tasks。
  - Tests: 覆盖正常 query、模糊 query、过宽 query。
  - Related files:

- [ ] T003 [P0] 实现 `Researcher` 执行检索并写入 `Evidence Store`
  - DoD: 每个 research task 至少产生结构化 evidence candidates。
  - Tests: 覆盖 source relevance 和空结果处理。
  - Related files:

- [ ] T004 [P0] 实现 `Writer` 基于 `Evidence Store` 生成报告
  - DoD: 报告关键 claim 必须引用 evidence ID。
  - Tests: 检查无 evidence 时拒绝生成 unsupported conclusion。
  - Related files:

## Phase 3: Evidence and Verification

- [ ] T005 [P1] 实现 `Verifier` 检查 claim-level evidence grounding
  - DoD: 能识别 unsupported claim 和 citation mismatch。
  - Tests: 构造 supported / unsupported claims。
  - Related files:

- [ ] T006 [P1] 实现 source scoring 与 citation completeness 检查
  - DoD: eval 能输出 `source_authority` 和 `citation_completeness`。
  - Tests: 覆盖官方文档、博客、未知来源。
  - Related files:

## Phase 4: Trace and Context Engineering

- [ ] T007 [P1] 实现 run trace 记录
  - DoD: 每次 agent/tool 调用记录 task、入参摘要、出参摘要、状态、耗时。
  - Tests: 覆盖成功、失败、重试。
  - Related files:

- [ ] T008 [P2] 实现上下文压缩或子任务隔离策略
  - DoD: 长任务不把所有原文无限追加到主上下文。
  - Tests: 覆盖多轮 research task。
  - Related files:

## Phase 5: Eval and Review

- [ ] T009 [P0] 建设最小 eval runner
  - DoD: 能运行固定 eval cases 并输出 metrics report。
  - Tests: 至少包含 5 个 Deep Research eval cases。
  - Related files:

- [ ] T010 [P0] 接入 `speckit.eval` 与 `speckit.review` 产物
  - DoD: implement 后能生成 / 更新 `eval.md` 和 `review.md`。
  - Tests: 跑通一次 implement -> eval -> review。
  - Related files:
