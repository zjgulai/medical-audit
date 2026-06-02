---
title: 答案生成 Provider 预检报告
doc_type: analysis
module: knowledge-query-engine
topic: answer-provider-preflight
status: draft
created: 2026-06-01
updated: 2026-06-01
owner: self
source: ai
---

# 答案生成 Provider 预检报告

总体状态：`FAIL`

## 1. 配置

| 配置 | 值 |
| --- | --- |
| `provider` | `anthropic` |
| `model_name` | `claude-sonnet-4-5-20250929` |
| `provider_version` | `2023-06-01` |

## 2. 门禁

| 检查项 | 结果 |
| --- | --- |
| `citation_marker_present` | `False` |
| `required_term_present` | `False` |

## 3. 输出

- `answer`: 无
- `error`: answer generation request failed: 401 {"type":"error","error":{"type":"authentication_error","message":"invalid x-api-key"},"request_id":"req_011CbbrwUcFZBCXXhEBcZ1ij"}
