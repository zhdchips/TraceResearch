# Eval Plan

> Language Policy: English headings, Chinese explanatory body, English AI/Agent terms and machine-readable keys.

本 artifact 由 `$speckit-ai-eval-review-eval` workflow 约束驱动，用于记录 US4 Seed Eval and Iteration Review 的第一版可运行 eval 方案。

## Scope

本轮 eval 覆盖 Deep Research multi-agent MVP 的 fixture-only 行为：`Planner` decomposition、`Researcher` source discovery、`Evidence Store` grounding、`Verifier` support checks、`Critic` review、`Writer` final report，以及 `Trace` / artifact 可复盘性。

MVP eval 不覆盖 live web search、Web UI、long-term memory、完整 sandbox、skills plugin system、多用户、PDF 上传、大规模并行调度或大型 benchmark。

## Metrics

- `planner_coverage`: 衡量 `Planner` 是否覆盖 seed case 的 expected perspectives。
- `perspective_diversity`: 衡量 plan 中是否至少包含 3 个 distinct perspectives。
- `source_relevance`: verified evidence 的平均 relevance score。
- `source_authority`: verified evidence 的平均 authority score。
- `citation_completeness`: final `report.json` 中 key claims 含 evidence IDs 的比例。
- `faithfulness`: key claims 的 evidence IDs 是否都能映射到 verified evidence，且无 unsupported claims。
- `unsupported_claim_count`: final report 中 unsupported claims 数量。
- `critical_hallucination_count`: unsupported 或 missing evidence 造成的 critical grounding failure 数量。
- `case_pass_rate`: seed cases 的 pass ratio。

## Cases

- `001-framework-comparison`: 比较 LangGraph、AutoGen、CrewAI 的 research agent 构建取舍。
- `002-financial-grounding`: 检查 financial research agent 的 grounding、risk language 和 authority。
- `003-ai-coding-agent-trends`: 综合 AI Coding Agent product forms 和工程挑战。
- `004-openhands-runtime`: 分析 OpenHands Agent Runtime 的 architecture 和 traceability。
- `005-rag-2026`: 处理 RAG 是否仍重要的争议型问题，强调 balance 和 evidence grounding。

## Commands

```bash
python3 -m pytest tests/eval/test_metrics.py
python3 -m pytest tests/eval/test_eval_runner.py
traceresearch eval --cases-dir eval/cases --source-provider fixture --results-dir eval/results
```

## Latest Result

当前 T040-T045 实现阶段先通过 pytest 覆盖 eval runner 和 metrics 行为。Durable result 写入 `eval/results/<eval_run_id>-summary.json` 的命令已经在 CLI 中提供；正式保存最新 eval summary 将在 T048/T049 运行完整 eval/review workflow 时执行。

## Bad Cases

当前 bad-case 记录策略：

- case-level `passed=false` 时写入 `bad_case_notes`。
- missing verified evidence 会标记为 faithfulness failure。
- unsupported claims 会同时提高 `unsupported_claim_count` 与 `critical_hallucination_count`。
- planner perspective gap 会标记 `planner_coverage` failure，并建议回到 `eval` phase 继续分析 case 或 planner 行为。

## Next Review Focus

下一轮 review 应重点检查：

- `EvalRunner` 的 `bad_case_notes` 是否足够定位 root cause。
- `case_pass_rate` 和 per-metric pass/fail 是否能支撑 `$speckit-ai-eval-review-review` 的 `decision`。
- 后续 live web provider 接入后，`source_relevance` / `source_authority` 是否仍稳定。
- `Trace` 是否能解释每个 failed case 的 Planner、Researcher、Verifier、Critic、Writer 责任边界。
