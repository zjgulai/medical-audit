---
title: 知识库真实资料检索评测报告
doc_type: analysis
module: knowledge-query-engine
topic: real-data-retrieval-evaluation
status: draft
created: 2026-06-01
updated: 2026-06-01
owner: self
source: ai
---

# 知识库真实资料检索评测报告

说明：当前评测使用真实资料索引产物和 CLI 指定的 embedding provider。评测 provider 必须与索引构建 provider 保持一致。

## 1. 运行配置

| 配置 | 值 |
| --- | --- |
| `index_root` | `postgres:MEDICAL_AUDIT_KB_DATABASE_URL` |
| `embedding_provider` | `fake` |
| `embedding_model` | `deterministic-token-hashing` |
| `embedding_dimension` | `1024` |

补充说明：当前环境未设置 `KIMI_API_KEY`，因此本次不生成真实 Kimi 查询向量。该报告验证的是 PostgreSQL 数据源加载 `document_chunks` 后的 BM25 检索路径；pgvector 路径已通过库内 embedding self-query smoke test，但固定 52 case 的真实 pgvector+Kimi 评测仍需有效 Kimi embedding key。

## 2. 指标

| 指标 | 数值 |
| --- | ---: |
| `case_count` | 52 |
| `recall_at_k` | 100.00% |
| `citation_hit_rate` | 100.00% |
| `preview_location_success_rate` | 100.00% |

## 3. 未命中样例

| case_id | question | missing_expected_sources |
| --- | --- | --- |
| 无 | 无 | 无 |
