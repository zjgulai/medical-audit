---
title: 知识库真实资料检索评测报告
doc_type: analysis
module: knowledge-query-engine
topic: real-data-retrieval-evaluation
status: draft
created: 2026-05-31
updated: 2026-05-31
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
| `case_count` | 10 |
| `recall_at_k` | 100.00% |
| `citation_hit_rate` | 100.00% |
| `preview_location_success_rate` | 100.00% |

## 3. 未命中样例

| case_id | question | missing_expected_sources |
| --- | --- | --- |
| 无 | 无 | 无 |

## 4. 范围说明

本报告使用完整 Kimi 索引产物，但评测 case 数为 `10`。`50` case 评测已尝试执行，受限于当前纯 Python `InMemoryVectorIndex` 对 `48985 × 1024` 向量逐条计算 dot product，运行时间过长，已停止。下一步需要将评测检索后端切换到 NumPy、FAISS 或 pgvector 后，再执行 `50+` case 质量评测。
