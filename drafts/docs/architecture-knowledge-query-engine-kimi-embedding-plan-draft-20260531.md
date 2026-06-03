---
title: 第三方 Embedding Provider 接入计划草稿
doc_type: architecture
module: knowledge-query-engine
topic: kimi-compatible-embedding-provider
status: draft
created: 2026-05-31
updated: 2026-06-01
owner: self
source: human+ai
---

# Kimi-Compatible Embedding Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用 Kimi 或其他第三方 OpenAI-compatible embedding API 替换当前 fake embedding，生成真实语义向量索引并完成真实检索评测。

**Architecture:** 保持现有 `OpenAICompatibleEmbeddingProvider` 抽象不变，通过 CLI 参数传入 base URL、model、dimension 和 api key env。执行顺序为 smoke test、小批量构建、小批量评测、全量构建、全量评测，任何一步失败都停止，不进入下一步。

**Tech Stack:** Python 3.12、uv、httpx、现有 `medical_audit_kb` CLI、OpenAI-compatible `/v1/embeddings`。

---

## 1. 前置输入

需要用户提供或确认以下信息：

- `KIMI_API_KEY`：第三方 API key，只放环境变量。
- `KIMI_EMBEDDING_BASE_URL`：`https://api.kimi.com/coding/v1`。
- `KIMI_EMBEDDING_MODEL`：`kimi-for-coding`。
- `KIMI_EMBEDDING_DIMENSION`：`1024`。
- 成本与限流：每分钟请求数、每分钟 token 数、每日额度。

如果第三方服务不支持 `/v1/embeddings`，本计划暂停，改为新增专用 provider adapter。

## 2. Task 1: Provider Smoke Test

**Files:**

- Modify: none
- Output: terminal only

- [x] Step 1: 设置临时环境变量。

```bash
export KIMI_API_KEY='实际 key'
export KIMI_EMBEDDING_BASE_URL='https://api.kimi.com/coding/v1'
export KIMI_EMBEDDING_MODEL='kimi-for-coding'
export KIMI_EMBEDDING_DIMENSION='1024'
```

- [x] Step 2: 执行最小 smoke test。

```bash
KIMI_API_KEY="$KIMI_API_KEY" uv run python - <<'PY'
import os
from medical_audit_kb.indexing.embeddings import OpenAICompatibleEmbeddingProvider

provider = OpenAICompatibleEmbeddingProvider.from_env(
    api_key_env="KIMI_API_KEY",
    model_name=os.environ["KIMI_EMBEDDING_MODEL"],
    dimension=int(os.environ["KIMI_EMBEDDING_DIMENSION"]),
    base_url=os.environ["KIMI_EMBEDDING_BASE_URL"],
    batch_size=1,
)
embedding = provider.embed_texts(["医保审核知识库 smoke test"])[0]
print({"ok": True, "model": provider.model_name, "dimension": len(embedding)})
PY
```

Expected: 输出 `ok=True` 且 `dimension` 等于 `KIMI_EMBEDDING_DIMENSION`。

- [x] Step 3: 如果返回认证、额度、限流、协议错误，停止并记录错误，不进入全量构建。

Actual: Kimi Code `/embeddings` 返回 `200`，`kimi-for-coding` 实际返回模型标识 `bge_m3_embed`，向量维度 `1024`。项目内 `OpenAICompatibleEmbeddingProvider` smoke test 返回 `ok=True`。

## 3. Task 2: 小批量真实 Embedding 构建

**Files:**

- Create: `tmp/knowledge-query-indexes/real-data-kimi-smoke-20260531/`
- Create: `tmp/outputs/knowledge-query-real-data-kimi-smoke-index-summary-20260531.json`

- [x] Step 1: 先构建小批量索引。已实现 `--max-chunks`，并将限制下推到 pipeline，达到限制后停止继续解析后续文件。
- [x] Step 2: 修改 `src/medical_audit_kb/indexing/persistent_index.py`，为 `build_persistent_index` 增加 `max_chunks: int | None = None`。
- [x] Step 3: 修改 `src/medical_audit_kb/cli.py`，为 `index-build` 增加 `--max-chunks`。
- [x] Step 4: 增加测试 `tests/knowledge_query/test_persistent_index.py`，断言 `max_chunks=1` 时只写入 1 条 embedding。
- [x] Step 5: 运行小批量构建。
- [x] Step 6: 为全量外部 embedding 增加 `--resume`，复用已有 `embeddings.jsonl` 并只追加缺失 embedding。

```bash
uv run medical-audit-kb index-build \
  --source-root 'data/医保审核前期资料' \
  --index-root tmp/knowledge-query-indexes/real-data-kimi-smoke-20260531 \
  --json-output tmp/outputs/knowledge-query-real-data-kimi-smoke-index-summary-20260531.json \
  --package-version-key source-package-real-data-kimi-smoke-20260531 \
  --embedding-provider openai \
  --embedding-model "$KIMI_EMBEDDING_MODEL" \
  --embedding-dimension "$KIMI_EMBEDDING_DIMENSION" \
  --api-key-env KIMI_API_KEY \
  --embedding-base-url "$KIMI_EMBEDDING_BASE_URL" \
  --embedding-batch-size 16 \
  --max-chunks 100
```

Expected: `embedding_count=100`，命令退出码为 `0`。

Actual: `persistent_chunk_count=100`，`embedding_count=100`，`bm25_document_count=100`，`embedding_dimension=1024`，命令退出码为 `0`。

## 4. Task 3: 小批量评测

**Files:**

- Create: `drafts/analysis/knowledge-query-real-data-kimi-smoke-evaluation-draft-20260531.md`
- Create: `tmp/outputs/knowledge-query-real-data-kimi-smoke-evaluation-20260531.json`

- [x] Step 1: 对小批量索引运行 smoke 评测。

```bash
uv run medical-audit-kb evaluate-index \
  --source-root 'data/医保审核前期资料' \
  --index-root tmp/knowledge-query-indexes/real-data-kimi-smoke-20260531 \
  --output drafts/analysis/knowledge-query-real-data-kimi-smoke-evaluation-draft-20260531.md \
  --json-output tmp/outputs/knowledge-query-real-data-kimi-smoke-evaluation-20260531.json \
  --max-cases 10 \
  --top-k 5 \
  --embedding-provider openai \
  --embedding-model "$KIMI_EMBEDDING_MODEL" \
  --embedding-dimension "$KIMI_EMBEDDING_DIMENSION" \
  --api-key-env KIMI_API_KEY \
  --embedding-base-url "$KIMI_EMBEDDING_BASE_URL" \
  --embedding-batch-size 16
```

Expected: 报告生成成功，`preview_location_success_rate=100%`。

Actual: 报告已生成。`case_count=10`，`recall@5=90%`，`citation_hit_rate=90%`，`preview_location_success_rate=100%`。该 smoke 样本仅覆盖排序靠前的 `2` 个法规文件，不能作为全量质量判断。

## 5. Task 4: 全量真实 Embedding 构建

**Files:**

- Create: `tmp/knowledge-query-indexes/real-data-kimi-20260531/`
- Create: `tmp/outputs/knowledge-query-real-data-kimi-index-summary-20260531.json`

- [x] Step 1: 确认小批量构建和评测通过。
- [x] Step 2: 确认 API 额度足够覆盖 `48985` chunks。
- [x] Step 3: 执行全量构建。

```bash
uv run medical-audit-kb index-build \
  --source-root 'data/医保审核前期资料' \
  --index-root tmp/knowledge-query-indexes/real-data-kimi-20260531 \
  --json-output tmp/outputs/knowledge-query-real-data-kimi-index-summary-20260531.json \
  --package-version-key source-package-real-data-kimi-20260531 \
  --embedding-provider openai \
  --embedding-model "$KIMI_EMBEDDING_MODEL" \
  --embedding-dimension "$KIMI_EMBEDDING_DIMENSION" \
  --api-key-env KIMI_API_KEY \
  --embedding-base-url "$KIMI_EMBEDDING_BASE_URL" \
  --embedding-batch-size 64 \
  --resume
```

Expected: `embedding_count=48985`，`bm25_document_count=48985`，失败文件仍为 `0`。

Actual: `embedding_count=48985`，`bm25_document_count=48985`，`failed_file_count=0`，`pending_file_count=13`，artifact size 约 `917M`。构建使用 `--resume`，本次 `embedding_created_count=48985`，`embedding_reused_count=0`。

## 6. Task 5: 全量真实检索评测

**Files:**

- Create: `drafts/analysis/knowledge-query-real-data-kimi-evaluation-draft-20260531.md`
- Create: `tmp/outputs/knowledge-query-real-data-kimi-evaluation-20260531.json`

- [x] Step 1: 执行全量索引评测。

```bash
uv run medical-audit-kb evaluate-index \
  --source-root 'data/医保审核前期资料' \
  --index-root tmp/knowledge-query-indexes/real-data-kimi-20260531 \
  --output drafts/analysis/knowledge-query-real-data-kimi-evaluation-draft-20260531.md \
  --json-output tmp/outputs/knowledge-query-real-data-kimi-evaluation-20260531.json \
  --max-cases 100 \
  --top-k 5 \
  --query-terms 医保 医疗保障 医保基金 超量 规则 处方 药品 基金 \
  --embedding-provider openai \
  --embedding-model "$KIMI_EMBEDDING_MODEL" \
  --embedding-dimension "$KIMI_EMBEDDING_DIMENSION" \
  --api-key-env KIMI_API_KEY \
  --embedding-base-url "$KIMI_EMBEDDING_BASE_URL" \
  --embedding-batch-size 16
```

Expected: 报告生成成功，记录 `recall@5`、`citation_hit_rate`、`preview_location_success_rate`。

Actual: 报告已生成。`case_count=100`，`recall@5=100%`，`citation_hit_rate=100%`，`preview_location_success_rate=100%`。

Note: `InMemoryVectorIndex` 已加入 NumPy 加速路径，无过滤条件的向量检索使用归一化矩阵和向量化 dot product；带过滤条件的检索仍保留 Python fallback。

## 7. Task 6: 文档与提交

**Files:**

- Modify: `docs/workflows/workflow-knowledge-query-engine-operations-stable.md`
- Modify: `docs/architecture/architecture-knowledge-query-engine-stable.md`
- Modify: `drafts/analysis/knowledge-query-real-data-retrieval-evaluation-draft-20260531.md`

- [x] Step 1: 将实际 Kimi provider 配置、构建耗时、embedding 数量和评测结果写入文档。
- [x] Step 2: 运行全量验证。

```bash
uv run ruff check .
uv run mypy src
uv run pytest tests/knowledge_query -v
```

Expected: `ruff` 通过，`mypy` 通过，pytest 全部通过。

- [ ] Step 3: 提交并推送。

```bash
git add .
git commit -m "接入第三方 embedding 索引计划与真实资料评测文档"
git push
```
