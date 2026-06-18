# STORM Notes

> Reference path: `references/upstream/storm`

## Positioning

STORM is most useful as a reference for research product shape and information organization. It is less important as a direct multi-agent engineering reference for this MVP.

The key idea to borrow is not its implementation framework, but its "pre-writing before writing" method:

1. collect information through perspective-guided research
2. generate an outline
3. write a long-form article with citations
4. polish the article

## Useful Workflow Ideas

### Two-Stage Writing

STORM separates:

- Pre-writing stage: collect references and generate outline
- Writing stage: generate the full article with citations

可借鉴点：

- 本项目的 `Writer` 不应该直接从 raw research notes 生成报告。
- 应先生成 `outline` 或 `report_plan`，再按 sections 填充 evidence。
- Eval 可以检查 outline 是否覆盖 expected dimensions。

### Perspective-Guided Question Asking

STORM improves depth and breadth by discovering multiple perspectives and using them to guide question asking.

可借鉴点：

- 本项目的 `Planner` 可以输出 `perspectives`，例如 technical, business, risk, comparison, implementation, limitation。
- Research tasks 应绑定 perspective，避免所有 Researcher 都搜同一种 query。

### Simulated Expert Conversation

STORM simulates conversations between a writer and topic experts grounded in Internet sources.

可借鉴点：

- 第一版不需要完整 conversation simulation。
- 可以用轻量替代：让 `Researcher` 针对每个 perspective 生成 2-3 个 research questions，再检索。

### Intermediate Artifacts

STORM writes durable intermediate outputs such as conversation logs, raw search results, generated outline, article draft, references, polished article, and LLM call history.

可借鉴点：

- 本项目应保存:
  - `trace.jsonl`
  - `evidence.jsonl`
  - `outline.md`
  - `draft_report.md`
  - `final_report.md`
  - `eval_report.md`
- 这些产物适合面试共享屏幕展示。

### Multi-Model Configuration

STORM uses different models for conversation simulation, question asking, outline generation, article generation, and polishing.

可借鉴点：

- MVP 可以只用一个 model。
- plan.md 中可以保留分层模型位点，后续做成本优化。

## Evaluation Ideas

STORM's article quality implies eval dimensions beyond factuality:

- outline quality
- breadth of perspectives
- citation coverage
- duplicate content
- article polish / readability

可借鉴点：

- 增加 `outline_coverage` 和 `perspective_diversity` 指标。
- Writer 输出前让 `Critic` 检查 missing perspectives 和 duplicate sections。

## Not Suitable for MVP

- Full simulated conversation system
- Co-STORM human-AI discourse protocol
- Dynamic mind map
- Full Wikipedia-style article polishing pipeline
- DSPy dependency unless the project already chooses it

## Plan Suggestions

- Add `perspectives` to `Planner` output.
- Add `outline` before final report writing.
- Add `Critic` check for missing perspectives and duplicate content.
- Persist intermediate artifacts for debugging and interview demo.
