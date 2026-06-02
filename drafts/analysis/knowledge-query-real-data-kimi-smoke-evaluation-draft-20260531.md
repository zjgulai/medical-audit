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
| `index_root` | `tmp/knowledge-query-indexes/real-data-kimi-smoke-20260531` |
| `embedding_provider` | `openai` |
| `embedding_model` | `kimi-for-coding` |
| `embedding_dimension` | `1024` |

## 2. 指标

| 指标 | 数值 |
| --- | ---: |
| `case_count` | 10 |
| `recall_at_k` | 90.00% |
| `citation_hit_rate` | 90.00% |
| `preview_location_success_rate` | 100.00% |

## 3. 未命中样例

| case_id | question | missing_expected_sources |
| --- | --- | --- |
| `real-data-auto-0001` | 三亚市爱国卫生管理办法_20230921中第一条的审核要求是什么？ | `["全量法律/三亚市爱国卫生管理办法_20230921.md"]` |
