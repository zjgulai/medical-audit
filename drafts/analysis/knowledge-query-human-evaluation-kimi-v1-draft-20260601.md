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
| `case_count` | 52 |
| `recall_at_k` | 100.00% |
| `citation_hit_rate` | 100.00% |
| `preview_location_success_rate` | 100.00% |

## 3. 未命中样例

| case_id | question | missing_expected_sources |
| --- | --- | --- |
| 无 | 无 | 无 |

## 4. 范围说明

本报告使用固定人工评测集 V1：`configs/evaluation/knowledge-query-human-evaluation-cases-v1.yaml`。当前评测集包含 `52` 个 review case，覆盖智能监管规则、医保目录、风险负面清单和医疗保障相关法规。

本轮扩容后，`human-rule-diagnosis-surgery-mismatch-001` 首次运行未命中。根因不是检索失败，而是 expected rule 使用了规范化转述；源文真实表述为“主要手术操作编码与主要诊断编码不符”。已将该 case 的 `article_or_rule` 调整为源文可匹配表述。
