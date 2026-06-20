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

Latest eval result:

- `result_file`: `eval/results/eval-20260620091948-58965334-summary.json`
- `eval_run_id`: `eval-20260620091948-58965334`
- `command`: `traceresearch eval --cases-dir eval/cases --source-provider fixture --results-dir eval/results`
- `test_command`: `python3 -m pytest`
- `test_result`: `71 passed`
- `case_count`: `5`
- `case_pass_rate`: `1.0`
- `failed_case_ids`: `[]`
- `bad_case_notes`: `[]`
- `suggested_next_phase`: `complete`

Metric summary from latest result:

| Metric | Value | Pass/Fail Interpretation |
| --- | ---: | --- |
| `planner_coverage` | `1.0` | PASS，5 个 seed cases 的 expected perspectives 均被 `Planner` 覆盖。 |
| `perspective_diversity` | `1.0` | PASS，每个 passing case 至少包含 3 个 distinct perspectives。 |
| `source_relevance` | `0.912` | PASS，fixture evidence 与 task/query 相关性充足。 |
| `source_authority` | `0.848` | PASS，fixture source authority 达到 MVP threshold。 |
| `citation_completeness` | `1.0` | PASS，final report key claims 均包含 evidence IDs。 |
| `faithfulness` | `1.0` | PASS，claims 的 evidence IDs 均可映射到 verified evidence，且无 unsupported final claims。 |
| `unsupported_claim_count` | `0.0` | PASS，没有 unsupported claims 进入 final report。 |
| `critical_hallucination_count` | `0.0` | PASS，没有 critical hallucination。 |
| `case_pass_rate` | `1.0` | PASS，5/5 seed cases 通过。 |

## Bad Cases

Latest eval 未发现 failing case：

- `failed_case_ids`: `[]`
- `bad_case_notes`: `[]`
- Suspected root causes: 无当前阻塞 root cause。已有 synthetic tests 覆盖 missing evidence、unsupported claims、planner coverage failure，并确认这些路径会写入 `bad_case_notes`。

保留的 bad-case 观察机制：

- case-level `passed=false` 时写入 `bad_case_notes`。
- missing verified evidence 会标记为 `faithfulness` failure。
- unsupported claims 会同时提高 `unsupported_claim_count` 与 `critical_hallucination_count`。
- planner perspective gap 会标记 `planner_coverage` failure，并建议回到 `eval` phase 继续分析 case 或 planner 行为。

## Next Review Focus

当前 iteration 推荐进入 final review，并以 `$speckit-ai-eval-review-review` 判断是否 complete。

下一阶段如果开启新 feature，review focus 建议放在：

- live web provider 接入后，`source_relevance` / `source_authority` 是否仍稳定。
- model-backed `Planner` / `Writer` 替换 deterministic implementation 后，`Faithfulness` 和 `Citation Completeness` 是否保持 1.0。
- `Trace` 在真实 tool latency、provider failure、partial evidence gap 下是否足够支持 bad-case replay。
- `Critic` 对 weak source、conflicting evidence、over-strong conclusion 的拦截能力是否需要更细粒度 metrics。
