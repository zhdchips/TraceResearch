# 简历/项目介绍 — TraceResearch

## 一句话概括

从零构建了一个 **Lead Agent + Tool-based Subagents** 双层多智能体深度研究系统，从 CLI 到 LLM 调用、从并发调度到可观测性全链路实现，支持三种编排模式（命令式 pipeline / 工具状态机 / LangGraph 图编排）。

---

## 项目亮点（中文，可直接放进简历）

### TraceResearch — 多智能体深度研究系统

**技术栈**: Python 3.11+, LangGraph, httpx, Pydantic, Typer, ThreadPoolExecutor, JSONL trace

- **Lead Agent + Tool-based Subagents 双层架构**：设计了 Planner → LeadResearchAgent → SubagentExecutor → Writer → Verifier → Critic 六阶段 pipeline，Lead Agent 负责任务编排，Subagent 层通过 ThreadPoolExecutor 并发执行研究任务，支持环境变量控制并发数（`TRACERESEARCH_MAX_CONCURRENT_RESEARCH_TASKS`）

- **LangGraph 编排引擎**：引入 LangGraph `StateGraph` 替换硬编码循环，实现声明式的节点+条件边路由。支持三种模式（runtime / tool_controller / langgraph），通过 `TRACERESEARCH_LEAD_AGENT_MODE` 环境变量一键切换，默认行为不变

- **Context Engineering（上下文工程）**：设计了分层上下文传递机制——Lead Agent 间通过 `RuntimeState` 全量传递，Lead→Subagent 通过 `CompressedResearchContext` 压缩传递（最小权限原则），并实现 `ContextBudget` 控制 prompt 大小（max_evidence_items / max_chars_per_evidence / max_total_chars）

- **状态同步与并发冲突解决**：采用 **Single Writer Ownership Boundary** 模型——Subagent 只产出结果不写全局状态，Lead Agent 单线程合并，EvidenceStore 做去重，TraceWriter 通过 `threading.Lock` 保序写入。避免了分布式锁的复杂性

- **全链路可观测性**：设计了分层 trace 模型（Harness → LangGraph → LeadRuntime → Agents → Subagents），每个 event 包含 `agent_role` / `event_type` / `status` / `error` / `llm_token_usage`。结合 artifact 文件（10 类输出）和 `trace.jsonl`，支持完整的执行复盘

- **评估驱动的迭代开发**：从 001 到 009 共 9 个迭代版本，每个版本有独立的 spec/plan/tasks/review 文档。实现了 eval runner + metrics（perspective_coverage / claim_support_rate / hallucination_rate），fixture 回归测试保证不退化

---

## 技术决策（面试时可展开讲）

| 决策 | 选择 | 原因 |
|------|------|------|
| LLM Provider | DeepSeek (deepseek-chat) via httpx | 轻量 vendor-agnostic，不耦合 SDK |
| Agent 通信 | 直接方法调用（非 message passing） | 确定性高，调试方便 |
| 并发模型 | ThreadPoolExecutor（非 asyncio） | I/O 密集型，简单可控 |
| 状态管理 | dataclass RuntimeState（非外部 DB） | 单次 run 生命周期内，无需持久化 |
| 编排引擎 | LangGraph StateGraph | 声明式、可可视化、面试加分 |
| 可观测性 | 自定义 JSONL TraceWriter | 零依赖、人类可读、支持 jq 查询 |
| Writer/Verifier | Protocol (ABC) + mode factory | 支持 deterministic/LLM 双模式切换 |

---

## 架构演进路线

```
001 MVP        → Planner + Researcher + Writer (固定 pipeline)
002 Live       → 接入真实 source discovery provider (Exa)
003 LLM        → LLMWriter / LLMVerifier 替换 deterministic 实现
004 Subagents  → SubagentExecutor + ThreadPoolExecutor 并发
005 Runtime    → LeadAgentRuntime + RuntimeState 统一状态管理
006 Iterative  → Critique → REVISE 循环 + max_iterations
007 Context    → ContextPack + ContextBudget 上下文压缩
008 Tools      → RuntimeTool 抽象 + 工具状态机
009 LangGraph  → StateGraph 替换命令式循环 ← 当前版本
```
