---
title: 知识库 pgvector 受控导入报告
doc_type: analysis
module: knowledge-query-engine
topic: pgvector-import
status: draft
created: 2026-06-01
updated: 2026-06-01
owner: self
source: ai
---

# 知识库 pgvector 受控导入报告

总体状态：`PASS`

## 1. 运行配置

| 配置 | 值 |
| --- | --- |
| `mode` | `execute` |
| `executed` | `True` |
| `index_root` | `tmp/knowledge-query-indexes/real-data-kimi-20260531` |
| `source_root` | `data/医保审核前期资料` |
| `batch_size` | `500` |

## 2. 写入准备指标

| 指标 | 数值 |
| --- | ---: |
| `ready_for_import` | `True` |
| `ready_for_write` | `True` |
| `source_document_count` | 486 |
| `document_chunk_count` | 48985 |
| `chunk_embedding_count` | 48985 |
| `failed_file_count` | 0 |
| `pending_file_count` | 13 |
| `source_file_missing_count` | 0 |
| `invalid_source_metadata_count` | 0 |

## 3. 数据库写入后校验

| 指标 | 数值 |
| --- | ---: |
| `source_package_versions` | 1 |
| `source_documents` | 486 |
| `document_chunks` | 48985 |
| `chunk_embeddings` | 48985 |
| `index_versions` | 1 |
| `index_jobs` | 1 |
| `failed_files` | 0 |
| `pending_files` | 13 |
| `orphan_embedding_count` | 0 |
| `missing_embedding_count` | 0 |
| `invalid_dimension_count` | 0 |

Provider 分布：

| provider | model_name | provider_version | dimension | count |
| --- | --- | --- | ---: | ---: |
| `openai` | `kimi-for-coding` | `v1` | 1024 | 48985 |

来源分布：

| source_collection | document_count | chunk_count |
| --- | ---: | ---: |
| `medical-insurance-catalog` | 9 | 7480 |
| `medical-insurance-laws` | 433 | 22704 |
| `risk-negative-list` | 3 | 33 |
| `supervision-rules-knowledge` | 41 | 18768 |

索引状态：

- `idx_chunk_embeddings_kimi_cosine_hnsw`: 存在
- `idx_document_chunks_metadata_gin`: 存在
- `idx_document_chunks_locator_gin`: 存在
- `idx_query_logs_filters_gin`: 存在
- database size: `764 MB`
- `chunk_embeddings` total size: `654 MB`
- HNSW index size: `382 MB`

向量检索 smoke query 已通过：使用库内任一 embedding 作为 query vector，最近结果第一条 cosine distance 为 `0.00000000`。

导入前快照：

- `archive/snapshots/postgres-pre-pgvector-import-20260601160814.sql`
- `archive/snapshots/postgres-schema-before-pgvector-import-20260601160829.sql`

## 4. 问题样例

- 无

## 5. 下一步

结论：PostgreSQL 写入和数据库行数校验已完成。下一步实现 PostgreSQL-backed 检索路径，并用固定 52 case 验证数据库检索质量。
