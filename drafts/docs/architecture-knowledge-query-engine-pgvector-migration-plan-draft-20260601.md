---
title: 知识库查询引擎 pgvector 迁移计划
doc_type: architecture
module: knowledge-query-engine
topic: pgvector-migration
status: draft
created: 2026-06-01
updated: 2026-06-01
owner: self
source: human+ai
---

# 知识库查询引擎 pgvector 迁移计划

## 1. 目标

将当前 `tmp/knowledge-query-indexes/real-data-kimi-20260531` 的 JSONL 索引产物迁移到 PostgreSQL + pgvector，降低 API 运行时对 917M 本地 artifact 和内存矩阵加载的依赖。

## 2. 当前约束

- 当前主索引 embedding provider 为 `openai` 兼容协议，model 为 `kimi-for-coding`。
- 当前主索引 embedding dimension 为 `1024`。
- `sql/knowledge-query-schema.sql` 已调整为 `vector(1024)`，并加入 Kimi 专用 HNSW cosine 索引。
- 该 schema 不兼容 `text-embedding-3-small` 的 `1536` 维 embedding。切换 embedding model 时必须新增对应 schema/migration，不能混写不同维度向量。

## 3. 迁移步骤

1. 启动本地 PostgreSQL：

```bash
docker compose -f docker-compose.dev.yaml up -d
```

2. 初始化 schema：

```bash
psql "$DATABASE_URL" -f sql/knowledge-query-schema.sql
```

3. 执行导入前校验，确认 JSONL artifact 与当前 `vector(1024)` schema 兼容：

```bash
uv run medical-audit-kb pgvector-import-plan \
  --index-root tmp/knowledge-query-indexes/real-data-kimi-20260531 \
  --schema-dimension 1024 \
  --output drafts/analysis/knowledge-query-pgvector-import-plan-kimi-draft-20260601.md \
  --json-output tmp/outputs/knowledge-query-pgvector-import-plan-kimi-20260601.json
```

当前结果：

- `ready_for_import`: `true`
- `chunks.jsonl`: `48985`
- `embeddings.jsonl`: `48985`
- `failed_files.jsonl`: `0`
- `pending_files.jsonl`: `13`
- `missing_embedding_count`: `0`
- `orphan_embedding_count`: `0`
- `invalid_embedding_dimension_count`: `0`

4. 执行受控导入 dry-run，确认源文件元数据和写入批次可构建：

```bash
uv run medical-audit-kb pgvector-import \
  --index-root tmp/knowledge-query-indexes/real-data-kimi-20260531 \
  --source-root 'data/医保审核前期资料' \
  --schema-dimension 1024 \
  --output drafts/analysis/knowledge-query-pgvector-import-dry-run-kimi-draft-20260601.md \
  --json-output tmp/outputs/knowledge-query-pgvector-import-dry-run-kimi-20260601.json
```

当前 dry-run 结果：

- `ready_for_write`: `true`
- `source_document_count`: `486`
- `document_chunk_count`: `48985`
- `chunk_embedding_count`: `48985`
- `failed_file_count`: `0`
- `pending_file_count`: `13`
- `source_file_missing_count`: `0`
- `invalid_source_metadata_count`: `0`

5. 显式确认后，添加 `--execute` 将以下文件导入 PostgreSQL：

- `summary.json` → `source_package_versions`、`index_versions`、`index_jobs`
- `chunks.jsonl` → `source_documents`、`document_chunks`
- `embeddings.jsonl` → `chunk_embeddings`
- `failed_files.jsonl` → `failed_files`
- `pending_files.jsonl` → `pending_files`

当前执行结果：

- `executed`: `true`
- `success`: `true`
- `source_documents`: `486`
- `document_chunks`: `48985`
- `chunk_embeddings`: `48985`
- `failed_files`: `0`
- `pending_files`: `13`

6. 导入后执行一致性校验：

- `document_chunks` 数量等于 `48985`
- `chunk_embeddings` 数量等于 `48985`
- `chunk_embeddings.dimension` 全部为 `1024`
- `failed_files` 数量为 `0`
- `pending_files` 数量为 `13`
- `orphan_embedding_count` 数量为 `0`
- `missing_embedding_count` 数量为 `0`

7. 用 SQL 验证向量检索：

```sql
SELECT
    ce.chunk_id,
    1 - (ce.embedding <=> $1::vector) AS score
FROM chunk_embeddings ce
WHERE ce.provider = 'openai'
  AND ce.model_name = 'kimi-for-coding'
  AND ce.dimension = 1024
ORDER BY ce.embedding <=> $1::vector
LIMIT 5;
```

## 4. 门禁

- `answer-provider-smoke` 不通过时，不接入真实生成模型。
- `evaluate-index` 固定 52 case 未达到 `100%` 时，不切换 API 查询路径到 PostgreSQL。
- `evaluate-answers` fallback 8 case 未达到 `100%` 时，不切换 API 查询路径到 PostgreSQL。
- PostgreSQL 查询结果必须保留 `chunk_id`、`source_package_version_key`、`index_version_key` 和 locator。

## 5. 后续实现任务

- 新增 PostgreSQL-backed `VectorIndex` 和 `BM25` 查询实现。
- 为 `source_collection`、年份、地区、文档类型、业务主题过滤设计组合索引或分区策略。
- 将 `PreviewResolver` 从运行态引用注册切换为数据库 locator 查询。
