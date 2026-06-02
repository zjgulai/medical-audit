---
title: 知识库增量更新计划报告
doc_type: analysis
module: knowledge-query-engine
topic: incremental-plan
status: draft
created: 2026-06-02
updated: 2026-06-02
owner: self
source: ai
---

# 知识库增量更新计划报告

总体状态：`PASS`

## 1. 版本信息

| 字段 | 值 |
| --- | --- |
| `source_root` | `data/医保审核前期资料` |
| `source_package_version_key` | `source-package-real-data-20260602-plan` |
| `active_index_version_key` | `full-rebuild-20260531142344` |
| `active_source_package_version_key` | `source-package-real-data-kimi-20260531` |

## 2. 影响计数

| 指标 | 数值 |
| --- | ---: |
| `discovered_files` | 17252 |
| `active_documents` | 486 |
| `index_candidate_files` | 486 |
| `added_files` | 0 |
| `modified_files` | 0 |
| `deleted_files` | 0 |
| `unchanged_files` | 486 |
| `pending_files` | 13 |
| `ignored_files` | 16753 |
| `failed_files` | 0 |
| `estimated_new_chunks` | 0 |
| `estimated_reused_embeddings` | 48985 |
| `estimated_new_embeddings` | 0 |
| `db_rows_to_activate` | 48985 |
| `db_rows_to_deactivate` | 0 |

## 3. 文件样例

### 新增文件
- 无

### 修改文件
- 无

### 删除文件
- 无

### 待处理文件
- `全量法律.zip` (`unsupported-type`): unsupported-file-type
- `智能监管“两库”规则和知识点/医疗保障基金智能监管规则库、知识库（2025年版）（第三部分）.rar` (`unsupported-type`): unsupported-file-type
- `智能监管“两库”规则和知识点/第一批/第一批.png` (`unsupported-type`): unsupported-file-type
- `智能监管“两库”规则和知识点/第七批/第七批.png` (`unsupported-type`): unsupported-file-type
- `智能监管“两库”规则和知识点/第三批/第三批.png` (`unsupported-type`): unsupported-file-type
- `智能监管“两库”规则和知识点/第九批/第九批.png` (`unsupported-type`): unsupported-file-type
- `智能监管“两库”规则和知识点/第二批/第二批.png` (`unsupported-type`): unsupported-file-type
- `智能监管“两库”规则和知识点/第五批/第五批.png` (`unsupported-type`): unsupported-file-type
- `智能监管“两库”规则和知识点/第八批/第八批.png` (`unsupported-type`): unsupported-file-type
- `智能监管“两库”规则和知识点/第六批/第六批.png` (`unsupported-type`): unsupported-file-type
- `智能监管“两库”规则和知识点/第十一批/第十一批.png` (`unsupported-type`): unsupported-file-type
- `智能监管“两库”规则和知识点/第十批/第十批.png` (`unsupported-type`): unsupported-file-type
- `智能监管“两库”规则和知识点/第四批/第四批.png` (`unsupported-type`): unsupported-file-type

### 失败文件
- 无

## 4. 下一步

结论：未发现索引候选文件变化。无需执行增量构建。
