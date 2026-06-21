# 009 LangGraph Runtime Adapter — Interview Q&A

## Q1: Multi-agent 的架构是什么样的？

**TL;DR**: Lead Agent + Tool-based Subagents 两层架构，LangGraph 负责 Lead 层编排。

```
┌──────────────────────────────────────────────────────┐
│                  ResearchHarness                      │
│  (CLI entry → mode dispatch → artifact write)        │
└──────────────┬──────────────┬──────────────┬─────────┘
               │ runtime       │ tool_ctrl     │ langgraph
               ▼               ▼               ▼
┌──────────────────────────────┐  ┌────────────────────┐
│   Lead Agent Layer (串行)     │  │  LangGraph         │
│                              │  │  StateGraph        │
│  Planner ──→ Writer          │  │  ┌──────────────┐  │
│       │        │              │  │  │plan_research │  │
│       ▼        ▼              │  │  │      ↓       │  │
│  LeadResearchAgent  Verifier │  │  │run_subagents │  │
│       │              │        │  │  │      ↓       │  │
│       ▼              ▼        │  │  │ write_report │  │
│  SubagentExecutor   Critic   │  │  │      ↓       │  │
└──────┬───────────────────────┘  │  │verify_report │  │
       │                           │  │      ↓       │  │
       ▼                           │  │   critique   │  │
┌──────────────────────────────┐  │  │      ↓       │  │
│  Research Subagent Layer     │  │  │ finalize_run │  │
│  (并发, ThreadPoolExecutor)   │  │  └──────────────┘  │
│                              │  └────────────────────┘
│  ResearchTaskAgent × N       │
│  (每 task 一个线程)           │
│  → SourceDiscoveryProvider   │
│  → 产出 Evidence             │
└──────────────────────────────┘
```

**两层架构**:
1. **Lead Agent Layer** — 负责整体流程编排：分析问题 → 拆解任务 → 收集证据 → 撰写报告 → 验证 → 批判 → 修改。这一层是串行的（单线程），每个阶段由一个专门的 Agent 负责。
2. **Subagent Layer** — 负责并发执行研究任务。Lead Agent 将问题拆解为多个 ResearchTask 后，SubagentExecutor 用 ThreadPoolExecutor 并发派发给多个 ResearchTaskAgent。每个 subagent 独立调用 source discovery provider 获取数据。

**三个编排模式**:
- `runtime` — 硬编码的 while 循环，LeadtAgentRuntime.run_pipeline()
- `tool_controller` — 工具选择状态机，每次循环调用 select_next_tool()
- `langgraph` — LangGraph StateGraph，声明式节点+条件边

## Q2: 多 Agent 间的上下文如何传递？

**TL;DR**: 分层压缩传递，不是全量共享。

上下文的传递分为三个层次：

### 第一层：Lead Agent 内部 → RuntimeState
`RuntimeState` 是一个 dataclass，携带所有 pipeline 阶段间的共享状态：
- `research_brief` — Planner 产出的研究摘要
- `planned_tasks` — 拆解后的研究任务列表
- `evidence` — 收集到的证据列表
- `draft_report` / `verification_result` / `critique_result` — 各阶段产出
- `iteration_history` — 所有迭代的决策记录

每个阶段读取上游产出、写入自己的结果，形成一条清晰的依赖链。

### 第二层：Lead Agent → Subagent → CompressedResearchContext
Subagent 不接收完整的 RuntimeState，而是接收一个轻量的 `CompressedResearchContext`：
```python
CompressedResearchContext(
    run_id=...,
    brief_summary="Research task: 调查 AI Agent 架构的最新进展",  # 压缩后的任务摘要
    task=ResearchTask(...),   # 具体任务定义
    provider_name="fixture",  # 数据源标识
)
```
这是**故意压缩**的——subagent 只需要知道自己的任务，不需要知道其他 subagent 在做什么。

### 第三层：Context Pack → 未来 LLM Tool-calling
`ContextPack` 是更进一步的上下文工程（007），定义了 budget 约束：
```python
ContextBudget(
    max_evidence_items=20,       # 最多 20 条证据
    max_chars_per_evidence=500,  # 每条证据最多 500 字符
    max_total_chars=8_000,       # 总字符数上限
)
```
用于控制 LLM prompt 大小，防止上下文膨胀。

### 为什么这样设计？
1. **Security**: Subagent 不应该看到完整的 run state（最小权限原则）
2. **Cost**: 减少每个 agent 的 token 消耗
3. **Independence**: Subagent 之间不应该互相依赖或冲突

## Q3: 状态同步是怎么实现的？如何解决并发操作冲突？

**TL;DR**: 单写者模型 (Single Writer per State Layer) + Ownership Boundary。

### 并发模型

```
┌──────────────────────────────────────────┐
│  Lead Agent Layer (单写者)                │
│                                          │
│  只有 LeadAgentRuntime 写入              │
│  RuntimeState                            │
│                                          │
│  ┌────────┐  ┌────────┐  ┌──────────┐   │
│  │Planner │──│ Writer │──│Verifier  │   │
│  └────────┘  └────────┘  └──────────┘   │
│       │           │            │          │
│       ▼           ▼            ▼          │
│  RuntimeState (单线程修改)                │
└──────────────┬───────────────────────────┘
               │ 派发任务（只读）
               ▼
┌──────────────────────────────────────────┐
│  Subagent Layer (多写者，但各自独立)       │
│                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │Subagent 1│ │Subagent 2│ │Subagent 3│ │
│  │(thread 1)│ │(thread 2)│ │(thread 3)│ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ │
│       │             │             │       │
│       ▼             ▼             ▼       │
│  CandidateEvidenceBatch × N              │
│  (各自独立写入，互不干扰)                  │
└──────────────┬───────────────────────────┘
               │ 汇总结果
               ▼
┌──────────────────────────────────────────┐
│  Merge Layer (单写者)                     │
│                                          │
│  LeadResearchAgent 统一汇总              │
│  → EvidenceStore (thread-safe append)    │
│  → Dedup (单线程处理)                     │
│  → TraceWriter (thread-safe via lock)    │
└──────────────────────────────────────────┘
```

### 并发冲突解决方案

1. **Ownership Boundary** — 每层有明确的写权限：
   - Subagent → 只产出 `CandidateEvidenceBatch`，不能写 RuntimeState
   - LeadResearchAgent → 汇总 subagent 结果，写入 EvidenceStore
   - LeadAgentRuntime → 唯一写入 RuntimeState 的组件
   - LangGraph StateGraph → 只做路由，不改业务状态

2. **TraceWriter 线程安全** — 通过 `threading.Lock` 保护：
   ```python
   def append(self, event):
       with self._lock:
           with open(self.path, "a") as f:
               f.write(json.dumps(event) + "\n")
   ```

3. **EvidenceStore 去重** — 基于 `(research_task_id, source_id)` 去重，多个 subagent 如果返回相同的 source，只保留第一个。

4. **Subagent 隔离** — 每个 subagent 独立调用 provider，失败的 subagent 不影响其他。

5. **LangGraph 不做并发** — Graph 节点是逐次执行的（单线程），不引入新的并发复杂度。
6. **In-process adapter** — 当前 LangGraph 是 in-process adapter：GraphState 的 `_runtime_state` / `_runtime` 是进程内对象引用（不可序列化）。RuntimeState 保持执行态，GraphState 只做轻量 routing snapshot。生产级 checkpoint/resume 需要将 RuntimeState 和 artifact 引用外部化，已列入 known limitation，后续迭代再做。

### 为什么不用锁保护 RuntimeState？
因为不需要。RuntimeState 的写操作都发生在 Lead Agent 主线程中（单线程），subagent 只读（且只读 task 定义，不读 RuntimeState）。这是 **ownership boundary** 设计最核心的优势——消除了锁的需求。

## Q4: 多 Agent 的执行链路，是怎么实现监控和可观测性的？

**TL;DR**: TraceWriter (JSONL) + AgentRole 枚举 + 分层事件模型。

### 事件模型

每个 TraceEvent 包含：
- `trace_id` — 全局唯一单调序列号
- `agent_role` — 哪个角色产生的事件（Planner, ResearchLead, ResearchSubagent, Writer, Verifier, Critic, LangGraph, Harness）
- `event_type` — start / finish / tool_call / tool_result / error
- `input_summary` / `output_summary` — 人类可读的摘要
- `status` — success / failed / skipped / needs_clarification
- `error` — 失败时的错误详情
- `llm_mode` / `llm_model` / `llm_token_usage` — LLM 调用专属指标

### 可观测性层次

```
Layer 1: Harness       → HARNESS START/FINISH (run 级别)
Layer 2: LangGraph     → LANGGRAPH START/FINISH (node 级别)
                       → LANGGRAPH TOOL_RESULT (edge decision)
Layer 3: LeadRuntime   → LEAD_RUNTIME START/TOOL_CALL/TOOL_RESULT/FINISH
Layer 4: Agents        → PLANNER / WRITER / VERIFIER / CRITIC
Layer 5: ResearchLead  → RESEARCH_LEAD (dispatch 开始/结束)
Layer 6: Subagents     → RESEARCH_SUBAGENT (每个 task 的开始/结束/错误)
```

### LangGraph 层额外的可观测性 (009 新增)

每个 graph node:
```json
{
  "agent_role": "LangGraph",
  "event_type": "start",
  "tool_name": "plan_research",
  "input_summary": "graph node starting"
}
{
  "agent_role": "LangGraph",
  "event_type": "finish",
  "tool_name": "plan_research",
  "output_summary": "graph node completed"
}
```

每个条件边决策:
```json
{
  "agent_role": "LangGraph",
  "event_type": "tool_result",
  "tool_name": "edge_decision",
  "input_summary": "from=critique_report to=run_research_subagents decision=REVISE next_phase=research iter=1",
  "output_summary": "edge decision: REVISE → research"
}
```

### 可复盘的完整链路

从 `trace.jsonl` 可以重建每次 run 的完整执行路径：
1. 按 `trace_id` 排序即可得到时序
2. 按 `agent_role` 过滤可以看到各层的执行情况
3. `error` 字段记录了所有失败信息
4. `iteration_history` (在 RuntimeState 中) 记录了每次 revise 的原因

### Artifact + Trace 双保险

- **Artifact 文件** (JSON/MD/JSONL) — 业务数据，供下游消费
- **trace.jsonl** — 执行过程，供调试和复盘

两者结合可以回答：
- "为什么这次 critique 决定 revise？" → 看 critique.json + trace 中的决策事件
- "哪个 subagent 超时了？" → 看 trace 中的 RESEARCH_SUBAGENT FAILED 事件
- "LangGraph 这次走了什么路由？" → 看 trace 中的 LangGraph edge_decision 事件
