---
title: 知识库真实资料检索评测报告
doc_type: analysis
module: knowledge-query-engine
topic: real-data-retrieval-evaluation
status: draft
created: 2026-05-31
updated: 2026-06-01
owner: self
source: ai
---

# 知识库真实资料检索评测报告

说明：当前评测使用真实资料索引产物和 deterministic local embedding，是工程闭环基线，不代表最终模型质量。

当前状态：

- 本地持久化索引已完成：`48985` chunks、`48985` embeddings、`48985` BM25 documents。
- 当前 embedding provider：`fake`。
- OpenAI key 已测试不可用，错误为 `insufficient_quota`。
- Kimi Code OpenAI-compatible provider 已完成 smoke test：base URL `https://api.kimi.com/coding/v1`，model `kimi-for-coding`，dimension `1024`。
- Kimi 小批量索引已完成：`100` chunks、`100` embeddings、`100` BM25 documents。
- Kimi 小批量评测已完成：`10` cases，`recall@5=90%`，`citation_hit_rate=90%`，`preview_location_success_rate=100%`。
- Kimi 全量索引已完成：`48985` chunks、`48985` embeddings、`48985` BM25 documents，失败文件 `0`。
- Kimi 全量索引评测已完成：`100` cases，`recall@5=100%`，`citation_hit_rate=100%`，`preview_location_success_rate=100%`。
- 固定人工评测集 V1 已建立：`52` cases，路径 `configs/evaluation/knowledge-query-human-evaluation-cases-v1.yaml`。
- 固定人工评测集 V1 已完成 Kimi 全量索引评测：`recall@5=100%`，`citation_hit_rate=100%`，`preview_location_success_rate=100%`。
- 固定集首次运行暴露 `A00.0` ICD 编码未命中，已通过医保目录编码 tokenization 和 BM25 精确编码 boost 修复。

## 1. 指标

| 指标 | 数值 |
| --- | ---: |
| `case_count` | 25 |
| `recall_at_k` | 100.00% |
| `citation_hit_rate` | 100.00% |
| `preview_location_success_rate` | 100.00% |

## 2. 未命中样例

| case_id | question | missing_expected_sources |
| --- | --- | --- |
| 无 | 无 | 无 |

## 3. 下一步

下一步不再重复执行全量 embedding 构建。固定评测集已达到 `50+` case，后续应优先引入审计专家人工标注问题，继续暴露真实未命中样例，并开始答案生成质量评估。
