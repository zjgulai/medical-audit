---
title: 知识库答案生成质量评测报告
doc_type: analysis
module: knowledge-query-engine
topic: answer-quality-evaluation
status: draft
created: 2026-06-01
updated: 2026-06-01
owner: self
source: ai
---

# 知识库答案生成质量评测报告

说明：当前评测验证 citation-backed answer 的引用约束、拒答门控和关键术语覆盖，不替代专家人工审核。

## 1. 运行配置

| 配置 | 值 |
| --- | --- |
| `index_root` | `tmp/knowledge-query-indexes/real-data-kimi-20260531` |
| `embedding_provider` | `openai` |
| `embedding_model` | `kimi-for-coding` |
| `embedding_dimension` | `1024` |
| `answer_provider` | `openai` |
| `answer_model` | `kimi-for-coding` |

## 2. 指标

| 指标 | 数值 |
| --- | ---: |
| `case_count` | 8 |
| `pass_rate` | 25.00% |
| `citation_marker_rate` | 100.00% |
| `answer_term_coverage_rate` | 100.00% |
| `citation_term_coverage_rate` | 100.00% |
| `refusal_accuracy_rate` | 100.00% |
| `unsupported_claim_free_rate` | 100.00% |
| `generation_success_rate` | 0.00% |
| `fallback_rate` | 100.00% |

## 3. 未通过样例

| case_id | expected_behavior | failure_reasons |
| --- | --- | --- |
| `answer-law-shanghai-fund-dedicated-use-001` | `answer` | `["generation_provider_failed"]` |
| `answer-negative-over-prescription-001` | `answer` | `["generation_provider_failed"]` |
| `answer-catalog-icd-cholera-001` | `answer` | `["generation_provider_failed"]` |
| `answer-catalog-drg-ungrouped-001` | `answer` | `["generation_provider_failed"]` |
| `answer-catalog-drug-ceftriaxone-001` | `answer` | `["generation_provider_failed"]` |
| `answer-rule-drug-interaction-001` | `answer` | `["generation_provider_failed"]` |
