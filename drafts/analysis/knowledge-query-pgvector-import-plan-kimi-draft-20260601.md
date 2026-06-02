---
title: 知识库 pgvector 导入前校验报告
doc_type: analysis
module: knowledge-query-engine
topic: pgvector-import-plan
status: draft
created: 2026-06-01
updated: 2026-06-01
owner: self
source: ai
---

# 知识库 pgvector 导入前校验报告

总体状态：`PASS`

## 1. 运行配置

| 配置 | 值 |
| --- | --- |
| `index_root` | `tmp/knowledge-query-indexes/real-data-kimi-20260531` |
| `schema_dimension` | `1024` |
| `embedding_provider` | `openai` |
| `embedding_model` | `kimi-for-coding` |
| `embedding_provider_version` | `v1` |
| `embedding_dimension` | `1024` |

## 2. 行数校验

| 资产 | 实际 | 预期 |
| --- | ---: | ---: |
| `chunks.jsonl` | 48985 | 48985 |
| `embeddings.jsonl` | 48985 | 48985 |
| `failed_files.jsonl` | 0 | 0 |
| `pending_files.jsonl` | 13 | 13 |

## 3. 一致性指标

| 指标 | 数值 |
| --- | ---: |
| `duplicate_chunk_id_count` | 0 |
| `duplicate_embedding_chunk_id_count` | 0 |
| `missing_embedding_count` | 0 |
| `orphan_embedding_count` | 0 |
| `invalid_embedding_metadata_count` | 0 |
| `invalid_embedding_dimension_count` | 0 |

## 4. 门禁

| 门禁 | 状态 | 实际 | 预期 | 说明 |
| --- | --- | --- | --- | --- |
| `required-files-present` | `PASS` | `[]` | `[]` | 导入所需 JSONL artifact 必须全部存在 |
| `schema-dimension-compatible` | `PASS` | `1024` | `1024` | summary.embedding_dimension 必须匹配 pgvector schema 维度 |
| `chunk-row-count` | `PASS` | `48985` | `48985` | chunks.jsonl 行数必须匹配 summary.persistent_chunk_count |
| `embedding-row-count` | `PASS` | `48985` | `48985` | embeddings.jsonl 行数必须匹配 summary.embedding_count |
| `failed-file-row-count` | `PASS` | `0` | `0` | failed_files.jsonl 行数必须匹配 summary.failed_file_count |
| `pending-file-row-count` | `PASS` | `13` | `13` | pending_files.jsonl 行数必须匹配 summary.pending_file_count |
| `unique-chunk-ids` | `PASS` | `0` | `0` | chunks.jsonl 中 chunk_id 不允许重复 |
| `unique-embedding-chunk-ids` | `PASS` | `0` | `0` | embeddings.jsonl 中 chunk_id 不允许重复 |
| `embedding-chunk-alignment` | `PASS` | `{"missing_embedding_count": 0, "orphan_embedding_count": 0}` | `{"missing_embedding_count": 0, "orphan_embedding_count": 0}` | 每个 chunk 必须存在且仅存在一条对应 embedding |
| `embedding-provider-metadata` | `PASS` | `0` | `0` | embedding provider、model、provider_version、dimension 必须与 summary 一致 |
| `embedding-vector-dimension` | `PASS` | `0` | `0` | 每条 embedding 向量长度必须等于 summary.embedding_dimension |

## 5. 问题样例

- 无

## 6. 下一步

结论：导入前校验通过，可以进入 PostgreSQL 写入脚本或受控导入执行。
