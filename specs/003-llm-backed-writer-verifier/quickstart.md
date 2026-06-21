# Quickstart: LLM-Backed Writer / Verifier

> Language Policy: English headings, Chinese explanatory body, English AI/Agent terms, and English machine-readable keys.

**Feature**: 003-llm-backed-writer-verifier
**Created**: 2026-06-21

## 前提

- 已完成 001/002 的开发环境搭建（Python 3.11+, `pip install -e ".[dev]"`）
- 了解 TraceResearch 的 CLI 命令：`traceresearch run`, `traceresearch eval`

## 5 分钟快速开始

### 1. 配置 LLM API Key

```bash
# 方式 A: 已有 DeepSeek key（Hermes 用户直接可用）
export DEEPSEEK_API_KEY="sk-..."

# 方式 B: 使用通用环境变量
export TRACERESEARCH_LLM_API_KEY="sk-..."
export TRACERESEARCH_LLM_PROVIDER="deepseek"
export TRACERESEARCH_LLM_MODEL="deepseek-chat"
```

### 2. 运行 fixture eval（确认回归基线）

```bash
# fixture eval 默认使用 deterministic mode，不应受影响
traceresearch eval
# 预期输出: case_pass_rate=1.0

python3 -m pytest
# 预期: 100% pass
```

### 3. 运行 LLM-backed Writer（手动 smoke）

```bash
# 用 LLM Writer 跑 fixture evidence
traceresearch run \
  --query "Compare FastAPI, Django-Ninja, and Flask for building REST APIs" \
  --source-provider fixture \
  --case-id case-001 \
  --writer-mode llm

# 检查输出
ls runs/run-*/final_report.md
cat runs/run-*/trace.jsonl | grep '"llm_mode":"llm"'
```

### 4. 运行 LLM-backed Verifier（手动 smoke）

```bash
traceresearch run \
  --query "Compare FastAPI, Django-Ninja, and Flask for building REST APIs" \
  --source-provider fixture \
  --case-id case-001 \
  --verifier-mode llm

# 检查 verification 结果
cat runs/run-*/verification.json
```

### 5. 运行 LLM smoke eval（仅手动）

```bash
traceresearch llm-smoke
# 或
python3 -m pytest tests/llm_smoke/ -m llm_smoke
```

## Mode Selection 优先级

| 优先级 | Writer Mode | Verifier Mode |
|--------|-------------|---------------|
| 1 (最高) | CLI `--writer-mode llm\|deterministic` | CLI `--verifier-mode llm\|deterministic` |
| 2 | 环境变量 `TRACERESEARCH_WRITER_MODE` | 环境变量 `TRACERESEARCH_VERIFIER_MODE` |
| 3 (默认) | `deterministic` | `deterministic` |

**自动 fallback 规则**: Mode 设为 `llm` 但没有 API key 或 LLM 调用失败时 → 自动 fallback 到 deterministic，Trace 记录 WARNING。

## 环境变量完整列表

```bash
# LLM Provider 通用
TRACERESEARCH_LLM_PROVIDER=deepseek          # deepseek | openai | anthropic
TRACERESEARCH_LLM_API_KEY=sk-...             # 通用 API key
TRACERESEARCH_LLM_MODEL=deepseek-chat        # model ID
TRACERESEARCH_LLM_BASE_URL=https://api.deepseek.com
TRACERESEARCH_LLM_TIMEOUT=60                 # 秒

# Writer / Verifier mode
TRACERESEARCH_WRITER_MODE=deterministic      # deterministic | llm
TRACERESEARCH_VERIFIER_MODE=deterministic    # deterministic | llm

# Provider-specific（向后兼容）
DEEPSEEK_API_KEY=sk-...                      # DeepSeek 专用
```

## 和 002 的关系

- LLM mode 和 live web provider (`--source-provider web`) 正交：可以同时使用或单独使用
- `traceresearch run --source-provider web --writer-mode llm` 合法：live 搜索 + LLM 写作
- 不配置 LLM 时，行为与 002 完全一致

## 已知限制

- LLM smoke eval 只做手动运行，不进入 CI
- 第一版只支持 DeepSeek provider
- Evidence 超过 10 条时自动截断
- LLM 输出质量依赖 prompt engineering（后续 feature 持续改进）
