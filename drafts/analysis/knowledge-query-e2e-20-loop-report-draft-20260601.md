---
title: 知识库查询网站 E2E 20 轮迭代测试记录
doc_type: analysis
module: knowledge-query
topic: e2e-20-loop
status: draft
created: 2026-06-01
updated: 2026-06-01
owner: self
source: human+ai
---

# 知识库查询网站 E2E 20 轮迭代测试记录

## 目标

对知识库查询网站执行 20 轮端到端检查，覆盖查询工作台、索引管理、原文预览、API 状态、CLI smoke、PostgreSQL 连接状态、移动端结构风险、可访问性与质量门禁。

## 约束

- 本次不写入任何 API Key。
- `data/` 作为原始知识库资料源，只读。
- 过程输出进入 `tmp/outputs/`，过程分析进入 `drafts/analysis/`。
- 当前环境未暴露可调用浏览器截图工具，E2E 以 FastAPI `TestClient`、CLI、HTTP smoke 和测试套件为主。

## Loop 记录

### Baseline

- 命令：`uv run pytest tests/knowledge_query/test_pages.py tests/knowledge_query/test_api.py tests/knowledge_query/test_cli.py -v`
- 结果：`26 passed, 1 warning`
- 结论：查询页、索引页、API、CLI 基础链路可用。

### 20-loop baseline harness

- 输出：`tmp/outputs/knowledge-query-e2e-20-loop-baseline-20260601.json`
- 结果：`16 passed / 4 failed`
- 失败集中点：当前导航状态不可见、查询输入未标记必填、状态提示缺少 `role="alert"`、键盘焦点样式缺失。

| Loop | 覆盖点 | Baseline | 优化后 |
| --- | --- | --- | --- |
| 1 | `/health` API 状态 | PASS | PASS |
| 2 | `/` 根路径渲染查询页 | PASS | PASS |
| 3 | `/pages/query` 空状态 | PASS | PASS |
| 4 | 查询页生成引用型回答 | PASS | PASS |
| 5 | `medical-insurance-laws` 来源过滤 | PASS | PASS |
| 6 | `supervision-rules-knowledge` 来源过滤 | PASS | PASS |
| 7 | 查询结果跳转原文预览 | PASS | PASS |
| 8 | 未登记 preview chunk 返回 404 | PASS | PASS |
| 9 | `/pages/index-admin` 索引管理页 | PASS | PASS |
| 10 | `/operation/logs/export` 操作日志导出 | PASS | PASS |
| 11 | `/query` API 引用型回答 | PASS | PASS |
| 12 | `/query` 角色权限拦截 | PASS | PASS |
| 13 | `/preview/{chunk_id}` API 预览链路 | PASS | PASS |
| 14 | 未加载检索后端时页面告警 | PASS | PASS |
| 15 | `/static/app.css` 静态样式加载 | PASS | PASS |
| 16 | 移动端响应式 CSS 规则 | PASS | PASS |
| 17 | 当前导航状态 `aria-current` | FAIL | PASS |
| 18 | 查询输入必填与辅助说明 | FAIL | PASS |
| 19 | 状态告警 `role="alert"` | FAIL | PASS |
| 20 | 键盘焦点 `:focus-visible` | FAIL | PASS |

### 已执行优化

- 查询页、索引管理页、原文预览页新增 skip link 与 `main#main-content`。
- 查询页和索引管理页新增当前导航 `aria-current="page"`。
- 原文预览页新增当前页状态文本，避免导航区域无法表达当前位置。
- 查询输入新增辅助说明、`aria-describedby` 和 `required`，降低空查询误提交。
- 检索后端未加载、PostgreSQL 不可用、查询错误等提示新增 `role="alert"`。
- CSS 新增 `.skip-link`、当前导航样式、字段帮助文本和统一 `:focus-visible` 键盘焦点样式。
- `tests/knowledge_query/test_pages.py` 增加上述 UI 可访问性回归测试。

### 回归结果

- 20-loop 回归输出：`tmp/outputs/knowledge-query-e2e-20-loop-after-ui-a11y-20260601.json`
- 回归结果：`20 passed / 0 failed`
- 页面测试：`uv run pytest tests/knowledge_query/test_pages.py -v`，结果 `7 passed, 1 warning`
- 完整测试：`uv run pytest tests/knowledge_query -v`，结果 `119 passed, 1 warning`
- Ruff：`uv run ruff check .`，结果 `All checks passed`
- Mypy：`uv run mypy src`，结果 `Success: no issues found in 51 source files`

### 真实运行 smoke

- HTTP smoke 输出：`tmp/outputs/knowledge-query-e2e-http-smoke-20260601.json`
- HTTP smoke 结果：`/health`、`/pages/query`、`/pages/index-admin`、`/static/app.css` 全部 `200` 且命中预期内容。
- PostgreSQL 状态输出：`tmp/outputs/knowledge-query-e2e-postgres-status-20260601.json`
- PostgreSQL 状态：`source_documents=486`，`document_chunks=48985`，`chunk_embeddings=48985`，`failed_files=0`，`pending_files=13`。
- Kimi UI smoke 缺密钥验证输出：`tmp/outputs/knowledge-query-e2e-ui-smoke-missing-key-20260601.json`
- Kimi UI smoke 缺密钥验证：未设置 `KIMI_API_KEY` 时后端加载返回 `409`，符合不落盘密钥策略。
- Kimi UI smoke 真实链路输出：`tmp/outputs/knowledge-query-e2e-ui-smoke-kimi-20260601.json`
- Kimi UI smoke 真实链路结果：`success=true`，PostgreSQL 状态、后端加载、查询页和原文预览页均返回 `200`。
- Kimi UI smoke 真实链路数据规模：`source_documents=486`，`document_chunks=48985`，`chunk_embeddings=48985`，`matching_embedding_count=48985`。

### 剩余风险

- 当前环境没有可调用的浏览器截图工具，尚未完成视觉截图级回归。
- 若要执行真实 Kimi 查询链路，需要在运行时注入 `KIMI_API_KEY` 环境变量，不应写入仓库文件。
- TestClient 告警来自 Starlette 对 `httpx` 用法的弃用提示，不影响本次功能验证，但后续依赖升级时需要处理。
