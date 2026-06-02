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
| `mode` | `dry-run` |
| `executed` | `False` |
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

## 3. 问题样例

- 无

## 4. 下一步

结论：dry-run 已通过。下一步在确认数据库连接和备份后添加 `--execute` 执行写入。
