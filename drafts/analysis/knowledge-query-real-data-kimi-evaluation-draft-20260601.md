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
| `index_root` | `tmp/knowledge-query-indexes/real-data-kimi-20260531` |
| `embedding_provider` | `openai` |
| `embedding_model` | `kimi-for-coding` |
| `embedding_dimension` | `1024` |

## 2. 指标

| 指标 | 数值 |
| --- | ---: |
| `case_count` | 100 |
| `recall_at_k` | 100.00% |
| `citation_hit_rate` | 100.00% |
| `preview_location_success_rate` | 100.00% |

## 3. 未命中样例

| case_id | question | missing_expected_sources |
| --- | --- | --- |
| 无 | 无 | 无 |

## 4. 范围说明

本报告使用完整 Kimi 索引产物，评测 case 数为 `100`。当前 `InMemoryVectorIndex` 已启用 NumPy 加速路径，无过滤条件的向量检索使用归一化矩阵和向量化 dot product；带过滤条件的检索仍保留 Python fallback。
