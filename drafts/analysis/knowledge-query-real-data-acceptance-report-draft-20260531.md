---
title: 知识库真实资料索引验收报告
doc_type: analysis
module: knowledge-query-engine
topic: real-data-index-acceptance
status: draft
created: 2026-05-31
updated: 2026-05-31
owner: self
source: ai
---

# 知识库真实资料索引验收报告

总体状态：`PASS`

## 1. 摘要

| 指标 | 数值 |
| --- | ---: |
| `job_type` | full-rebuild |
| `index_version_key` | full-rebuild-20260531050232 |
| `source_package_version_key` | source-package-real-data-20260531 |
| `before_package_version_key` | None |
| `discovered_file_count` | 17252 |
| `index_candidate_file_count` | 486 |
| `indexed_file_count` | 486 |
| `chunk_count` | 48985 |
| `failed_file_count` | 0 |
| `pending_file_count` | 13 |
| `ignored_file_count` | 16753 |
| `added_file_count` | 486 |
| `modified_file_count` | 0 |
| `deleted_file_count` | 0 |
| `unchanged_file_count` | 0 |
| `retried_file` | None |
| `comparison` | {'before_index_candidate_file_count': 0, 'after_index_candidate_file_count': 486} |
| `index_success_rate` | 100.00% |
| `queue_explain_rate` | 100.00% |
| `accounted_file_count` | 17252 |
| `lost_file_count` | 0 |

## 2. 验收门禁

| 门禁 | 状态 | 实际 | 预期 | 说明 |
| --- | --- | ---: | ---: | --- |
| `index-success-rate` | `PASS` | 100.00% | 95.00% | 可索引文件成功抽取并切分比例不低于 95% |
| `queue-explain-rate` | `PASS` | 100.00% | 100.00% | 失败队列和待处理队列必须 100% 具备可解释原因 |
| `no-silent-loss` | `PASS` | True | True | 发现文件必须全部进入 indexed、failed、pending 或 ignored 之一 |

## 3. 失败原因分布

无。

## 4. 待处理原因分布

| 原因 | 数量 |
| --- | ---: |
| `unsupported-type` | 13 |

## 5. 失败样例

无。

## 6. 待处理样例

| 文件 | 类型 | 摘要 |
| --- | --- | --- |
| `全量法律.zip` | `unsupported-type` | unsupported-file-type |
| `智能监管“两库”规则和知识点/医疗保障基金智能监管规则库、知识库（2025年版）（第三部分）.rar` | `unsupported-type` | unsupported-file-type |
| `智能监管“两库”规则和知识点/第一批/第一批.png` | `unsupported-type` | unsupported-file-type |
| `智能监管“两库”规则和知识点/第七批/第七批.png` | `unsupported-type` | unsupported-file-type |
| `智能监管“两库”规则和知识点/第三批/第三批.png` | `unsupported-type` | unsupported-file-type |
| `智能监管“两库”规则和知识点/第九批/第九批.png` | `unsupported-type` | unsupported-file-type |
| `智能监管“两库”规则和知识点/第二批/第二批.png` | `unsupported-type` | unsupported-file-type |
| `智能监管“两库”规则和知识点/第五批/第五批.png` | `unsupported-type` | unsupported-file-type |
| `智能监管“两库”规则和知识点/第八批/第八批.png` | `unsupported-type` | unsupported-file-type |
| `智能监管“两库”规则和知识点/第六批/第六批.png` | `unsupported-type` | unsupported-file-type |
| `智能监管“两库”规则和知识点/第十一批/第十一批.png` | `unsupported-type` | unsupported-file-type |
| `智能监管“两库”规则和知识点/第十批/第十批.png` | `unsupported-type` | unsupported-file-type |
| `智能监管“两库”规则和知识点/第四批/第四批.png` | `unsupported-type` | unsupported-file-type |

## 7. 下一步判断

当前资料抽取与切分验收通过，下一步进入持久化向量/BM25 索引和真实检索评测。
