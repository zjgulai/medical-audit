---
title: 知识库查询引擎 API 文档
doc_type: api
module: knowledge-query-engine
topic: knowledge-query-engine-api
status: stable
created: 2026-05-31
updated: 2026-05-31
owner: self
source: human+ai
---

# 知识库查询引擎 API 文档

## 1. 基础信息

- 服务框架：`FastAPI`
- 默认配置：`configs/knowledge-query-engine-dev.yaml`
- 健康检查：`GET /health`
- 权限头：`X-User-Id`、`X-Role`

允许查询角色：

- `auditor`
- `it-admin`
- `department-head`

索引管理操作只允许 `X-Role: it-admin`。

## 2. 页面入口

### `GET /`

跳转式渲染最小查询页，与 `GET /pages/query` 使用同一处理逻辑。

### `GET /pages/query`

服务端模板查询页。

Query 参数：

- `question`：自然语言问题，可为空。
- `source_collection`：可重复传入，值为来源集合枚举。

页面展示：

- 自然语言输入框
- 来源过滤
- 引用型回答
- 分组依据
- 原文预览入口
- 最近查询日志

### `GET /pages/index-admin`

服务端模板索引管理页。

页面展示：

- 数据源状态
- 索引版本
- 重建任务
- 失败队列
- 待处理队列
- 评测状态
- 操作日志导出入口

## 3. 查询接口

### `POST /query`

请求体：

```json
{
  "question": "超量开药的审核依据是什么？",
  "top_k": 5,
  "source_collections": ["supervision-rules-knowledge"],
  "years": [2024],
  "regions": ["国家"],
  "document_types": ["rule"],
  "business_topics": ["prescription-audit"]
}
```

返回体核心字段：

- `answer`：引用型回答正文。
- `confidence`：`high | medium | low`。
- `fallback_used`：是否使用 fallback 答案。
- `basis_groups`：按证据类型分组的依据。
- `citations`：引用列表，含 `chunk_id`、locator、索引版本和资料包版本。
- `query_log_index`：本次查询日志索引。

错误：

- `403`：角色无查询权限。
- `404`：未找到可引用依据。
- `409`：检索引擎未初始化。

### `GET /query/logs`

返回查询日志：

```json
{
  "items": []
}
```

## 4. 原文预览接口

### `GET /preview/{chunk_id}`

查询后才能预览，因为预览引用由查询结果注册到运行态。

返回体核心字段：

- `source_path`
- `media_type`
- `preview_text`
- `locator`
- `highlights`
- `page_number`
- `line_start`
- `line_end`
- `sheet_name`
- `row_number`

错误：

- `404`：引用不存在或源文件不存在。
- `422`：locator 无法解析。

## 5. 索引接口

### `POST /index/rebuild`

全量重建索引。需要 `X-Role: it-admin`。

```json
{
  "package_version_key": "source-package-20260531"
}
```

### `POST /index/incremental`

基于当前快照执行增量索引。需要 `X-Role: it-admin`。如果没有历史快照，返回 `409`。

### `POST /index/retry-file`

重试单个文件。需要 `X-Role: it-admin`。

```json
{
  "package_version_key": "source-package-20260531",
  "relative_path": "全量法律/example.md"
}
```

### `GET /index/versions`

返回索引版本列表，并记录操作日志。

### `GET /index/jobs`

返回索引任务列表，并记录操作日志。

### `GET /index/failures`

返回失败文件队列，并记录操作日志。

### `GET /index/pending`

返回待处理文件队列，并记录操作日志。

## 6. 操作日志接口

### `GET /operation/logs`

返回查询、预览、索引管理等操作日志。

### `GET /operation/logs/export`

导出操作日志 JSON，并记录 `operation-logs-export` 操作。
