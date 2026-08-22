---
title: AI 审计一体化协作平台 API v1
doc_type: api-reference
module: platform-api
status: stable
created: 2026-08-13
updated: 2026-08-15
owner: self
source: human+ai+openapi
---

# AI 审计一体化协作平台 API v1

本文以当前 FastAPI OpenAPI 路由为基线，说明平台 API 族、权限和错误合同。规范前缀是 `/api/v1`；根路径和 `/api/backend` 仅作为兼容入口。

## 访问模式

| 模式 | 用途 | 业务读取 | 业务写入 |
|---|---|---:|---:|
| `header-transition-test` | 本地测试 | 按角色和项目允许 | 按角色和项目允许 |
| `public-shell-readonly` | 生产默认 | 禁止 | 禁止 |

生产模式允许公开 `GET`、`HEAD` 健康、部署元数据和 `/release-manifest.json`。受保护请求统一返回 `503 trusted_identity_required`，并包含 `Cache-Control: no-store`。

## 请求身份

本地测试可使用以下 Header：

| Header | 说明 |
|---|---|
| `X-User-Id` | 本地测试用户标识 |
| `X-Role` | `member`、`director`、`technician` 或 `admin` |
| `X-Tenant-Id` | 受控 API 的租户上下文 |
| `X-Project-Key` | 需要明确项目上下文时使用 |

这些 Header 不是可信认证。生产在 SSO/OIDC 建成前不会接受它们开放业务数据。

## 公开运行接口

| 方法与路径 | 结果 | 副作用 |
|---|---|---|
| `GET /health` | 服务版本和健康状态 | 无 |
| `GET /deployment/metadata` | 部署 SHA、证据边界和 `runtime_access` | 无 |
| `GET /release-manifest.json` | 静态构建身份和文件清单 | 无 |

以上接口也提供 `/api/v1/health` 和 `/api/v1/deployment/metadata`。公开接口不得包含 secret 或真实业务数据。

## 接口族

| 接口族 | 代表路径 | 主要能力 | 主要权限或边界 |
|---|---|---|---|
| 认证与用户 | `GET /auth/session`、`GET /auth/roles`、`POST /auth/users` | 本地会话、用户和角色分配 | 生产受保护；SSO 未就绪 |
| 知识问答 | `GET /query/models`、`POST /query`、`GET /query/logs` | 模型目录、检索问答、历史 | Provider 调用需独立授权 |
| 对话附件 | `POST /chat/attachments/analyze` | 确定性本地分析或受控 Provider 分析 | 上传与 Provider 独立记录 |
| 智能体 | `GET /agents`、`POST /agents`、`POST /agents/{agent_key}/invocations` | 目录、版本、评审、回滚、调用和反馈 | `MANAGE_AGENTS`；部分配置仍为 Preview |
| 智能体市场 | `GET /agent-market/catalog`、`POST /agent-market/templates/{template_id}/install` | 模板目录和安装 | 写入受保护 |
| 数据分析 | `POST /analytics/table-upload`、`GET /analytics/table-uploads` | 表格上传、分析和历史 | 上传产生文件与记录 |
| 文档 | `GET /documents/library`、`GET /documents/search`、`POST /documents/uploads` | 检索、目录、上传、下载和治理 | 个人、项目和治理权限分离 |
| OCR | `GET /ocr/capabilities`、`POST /ocr/extract` | 能力探测和文本识别 | 真实 Provider 未在本轮运行 |
| 合同审计 | `POST /contract-audits`、`GET /contract-audits/{job_id}`、`GET /contract-audits/{job_id}/report` | 创建审计任务、查询状态和报告 | OCR/LLM 调用需独立授权 |
| 知识库 | `GET /knowledge-base/catalog` | collection、文档、chunk、embedding 和索引统计 | 只读；统计按 package 预聚合 |
| 项目 | `POST /projects`、`GET /projects/{project_key}` | 项目、成员、文件和驾驶舱 | 按项目可见性授权 |
| 疑点 | `GET /audit-findings`、`POST /audit-findings/{finding_key}/review-status` | 查询、导入、复核、补证和报告条目 | 不可见资源返回 `404` |
| 复核任务 | `GET /review-tasks`、`POST /pages/review-tasks/{task_id}/status` | 任务、附件、状态、导出和整改 | 按项目、角色和关闭态授权 |
| 报告 | `GET /reports/workbench`、`POST /reports/drafts`、`POST /reports/drafts/{task_id}/signoff` | 模板、草稿、预览、签发和导出 | 仅 `SIGN_REPORTS` 且门禁通过可签发 |
| 整改 | `GET /remediation/workbench`、`POST /remediation/items`、`POST /remediation/items/{item_id}/status` | 整改、附件和状态迁移 | 使用数据库 UUID；按父项目鉴权 |
| 图谱 | `GET /graph/workbench` | 项目证据关系与知识节点 | 只读工作台 |
| 规则 | `GET /rules/workbench` | 规则来源、运行状态和疑点去向 | 当前 `sample_only` |
| 归档 | `GET /archive/workbench` | 归档包、签名链和检查状态 | 当前 `sample_only` |
| 索引 | `GET /index/postgres-status`、`POST /index/rebuild`、`POST /index/versions/activate` | 状态、任务、激活、回滚和评测 | `MANAGE_INDEX`；生产受保护 |
| 审计日志 | `GET /audit/logs`、`GET /audit/logs/export` | 审计事件查询和导出 | `READ_AUDIT_LOGS` |
| 操作日志 | `GET /operation/logs`、`GET /operation/logs/export` | 进程内操作观测 | 生产受保护 |
| 预览 | `GET /preview/{chunk_id}` | 文档定位和预览 | 按文档权限 |

## OpenAPI 逐操作清单

下表是规范前缀 `/api/v1` 的机器对账清单。`docs:lint` 会从 FastAPI OpenAPI 读取当前操作，并逐项核对方法与路径；新增、删除或改名后，代码和本文必须在同一候选中更新。接口出现在清单中只表示代码合同存在，不表示生产业务访问已经开放。

| 方法 | 规范路径 |
|---|---|
| GET | `/api/v1/` |
| GET | `/api/v1/agent-market/catalog` |
| POST | `/api/v1/agent-market/templates/{template_id}/install` |
| GET | `/api/v1/agents` |
| POST | `/api/v1/agents` |
| GET | `/api/v1/agents/{agent_key}` |
| GET | `/api/v1/agents/{agent_key}/feedback` |
| POST | `/api/v1/agents/{agent_key}/feedback` |
| GET | `/api/v1/agents/{agent_key}/invocations` |
| POST | `/api/v1/agents/{agent_key}/invocations` |
| POST | `/api/v1/agents/{agent_key}/lifecycle` |
| GET | `/api/v1/agents/{agent_key}/prompt-versions` |
| POST | `/api/v1/agents/{agent_key}/prompt-versions` |
| POST | `/api/v1/agents/{agent_key}/prompt-versions/review` |
| POST | `/api/v1/agents/{agent_key}/prompt-versions/rollback` |
| POST | `/api/v1/analytics/table-upload` |
| GET | `/api/v1/analytics/table-uploads` |
| GET | `/api/v1/archive/workbench` |
| GET | `/api/v1/audit-findings` |
| POST | `/api/v1/audit-findings/import-preflight` |
| GET | `/api/v1/audit-findings/{finding_key}/export` |
| POST | `/api/v1/audit-findings/{finding_key}/report-entry` |
| POST | `/api/v1/audit-findings/{finding_key}/review-status` |
| POST | `/api/v1/audit-findings/{finding_key}/review-task` |
| POST | `/api/v1/audit-findings/{finding_key}/supplemental-material` |
| GET | `/api/v1/audit/logs` |
| GET | `/api/v1/audit/logs/export` |
| GET | `/api/v1/auth/roles` |
| GET | `/api/v1/auth/session` |
| GET | `/api/v1/auth/users` |
| POST | `/api/v1/auth/users` |
| PATCH | `/api/v1/auth/users/{user_key}` |
| POST | `/api/v1/auth/users/{user_key}/role-assignments` |
| PATCH | `/api/v1/auth/users/{user_key}/role-assignments/{assignment_key}` |
| POST | `/api/v1/chat/attachments/analyze` |
| POST | `/api/v1/contract-audits` |
| GET | `/api/v1/contract-audits/{job_id}` |
| GET | `/api/v1/contract-audits/{job_id}/report` |
| GET | `/api/v1/deployment/metadata` |
| GET | `/api/v1/documents/governance/status` |
| GET | `/api/v1/documents/library` |
| GET | `/api/v1/documents/permissions` |
| GET | `/api/v1/documents/search` |
| GET | `/api/v1/documents/source-collections` |
| GET | `/api/v1/documents/source/{chunk_id}/download` |
| GET | `/api/v1/documents/uploads` |
| POST | `/api/v1/documents/uploads` |
| GET | `/api/v1/documents/uploads/{upload_id}/download` |
| POST | `/api/v1/documents/uploads/{upload_id}/governance` |
| POST | `/api/v1/documents/uploads/{upload_id}/index` |
| POST | `/api/v1/documents/uploads/{upload_id}/index-ingestion` |
| POST | `/api/v1/documents/uploads/{upload_id}/index-readiness/governance-result` |
| POST | `/api/v1/documents/uploads/{upload_id}/index-readiness/manual-approval` |
| GET | `/api/v1/graph/workbench` |
| GET | `/api/v1/health` |
| GET | `/api/v1/index/evaluation/history` |
| GET | `/api/v1/index/evaluation/latest/export` |
| POST | `/api/v1/index/evaluation/run` |
| GET | `/api/v1/index/failures` |
| POST | `/api/v1/index/incremental` |
| GET | `/api/v1/index/jobs` |
| GET | `/api/v1/index/pending` |
| GET | `/api/v1/index/postgres-status` |
| POST | `/api/v1/index/rebuild` |
| POST | `/api/v1/index/retry-file` |
| GET | `/api/v1/index/search-backend` |
| POST | `/api/v1/index/search-backend/postgres` |
| GET | `/api/v1/index/versions` |
| POST | `/api/v1/index/versions/activate` |
| POST | `/api/v1/index/versions/rollback` |
| GET | `/api/v1/knowledge-base/catalog` |
| GET | `/api/v1/ocr/capabilities` |
| POST | `/api/v1/ocr/extract` |
| GET | `/api/v1/operation/logs` |
| GET | `/api/v1/operation/logs/export` |
| GET | `/api/v1/pages/audit-findings` |
| POST | `/api/v1/pages/audit-findings/{finding_key}/review-task` |
| GET | `/api/v1/pages/audit-logs` |
| GET | `/api/v1/pages/chat` |
| GET | `/api/v1/pages/chat/export` |
| GET | `/api/v1/pages/index-admin` |
| GET | `/api/v1/pages/preview/{chunk_id}` |
| GET | `/api/v1/pages/query` |
| GET | `/api/v1/pages/review-tasks` |
| POST | `/api/v1/pages/review-tasks/create` |
| POST | `/api/v1/pages/review-tasks/{task_id}/attachments` |
| POST | `/api/v1/pages/review-tasks/{task_id}/rectification` |
| POST | `/api/v1/pages/review-tasks/{task_id}/report-signoff` |
| POST | `/api/v1/pages/review-tasks/{task_id}/status` |
| GET | `/api/v1/preview/{chunk_id}` |
| GET | `/api/v1/projects` |
| POST | `/api/v1/projects` |
| GET | `/api/v1/projects/{project_key}` |
| GET | `/api/v1/projects/{project_key}/dashboard` |
| GET | `/api/v1/projects/{project_key}/files` |
| POST | `/api/v1/projects/{project_key}/files` |
| GET | `/api/v1/projects/{project_key}/files/{upload_id}/download` |
| GET | `/api/v1/projects/{project_key}/files/{upload_id}/preview` |
| POST | `/api/v1/projects/{project_key}/files/{upload_id}/review` |
| GET | `/api/v1/projects/{project_key}/members` |
| POST | `/api/v1/projects/{project_key}/members` |
| POST | `/api/v1/query` |
| GET | `/api/v1/query/logs` |
| POST | `/api/v1/query/logs/{query_log_id}/review-task` |
| GET | `/api/v1/query/models` |
| GET | `/api/v1/remediation/items` |
| POST | `/api/v1/remediation/items` |
| GET | `/api/v1/remediation/items/{item_id}` |
| GET | `/api/v1/remediation/items/{item_id}/attachments` |
| POST | `/api/v1/remediation/items/{item_id}/attachments` |
| POST | `/api/v1/remediation/items/{item_id}/status` |
| GET | `/api/v1/remediation/workbench` |
| POST | `/api/v1/reports/drafts` |
| POST | `/api/v1/reports/drafts/{task_id}/signoff` |
| GET | `/api/v1/reports/workbench` |
| GET | `/api/v1/reports/workpaper-templates` |
| GET | `/api/v1/review-tasks` |
| GET | `/api/v1/review-tasks/{task_id}/attachments/{attachment_id}/download` |
| GET | `/api/v1/review-tasks/{task_id}/export` |
| GET | `/api/v1/review-tasks/{task_id}/rectification/export` |
| GET | `/api/v1/review-tasks/{task_id}/report-draft` |
| GET | `/api/v1/review-tasks/{task_id}/signed-report` |
| GET | `/api/v1/rules/workbench` |

## 整改合同

### 创建整改项

`POST /api/v1/remediation/items` 必须提供可见的 `project_key`。响应同时返回：

- `id`：数据库 UUID，用于详情、状态和附件 API。
- `item_key`：面向用户的展示 ID。
- `legacy_unscoped`：遗留无项目记录标记。
- `allowed_transitions`：当前用户可执行的状态迁移。
- `can_upload_attachment`：是否可上传附件。

### 状态迁移

| 执行角色 | 合法迁移 |
|---|---|
| 成员 | `pending-rectification → in-rectification → pending-acceptance` |
| 成员 | `rejected → in-rectification` |
| 主任 | `pending-acceptance → accepted` 或 `rejected` |
| 主任 | `accepted → closed` |

`closed` 不可再修改。非法状态返回 `422`；非法迁移或关闭态写入返回 `409`；权限不足返回 `403`。

## 报告签发合同

`POST /api/v1/reports/drafts/{task_id}/signoff` 复用正式签发的项目可见性、关闭态、构建门禁和 `SIGN_REPORTS` 权限。

- 主任可在 `can_sign=true`、`gate_ready=true`、`writes_allowed=true` 时签发。
- 成员、技术人员和管理员不得签发。
- 不可见任务返回 `404`。
- 重复签发或关闭任务返回 `409`。

## 知识库统计合同

`GET /api/v1/knowledge-base/catalog` 按文档预聚合 chunk 和 embedding，并按 package 聚合 active/candidate index 标志。等长文本分别计入 `character_count`；多个 index version 不得放大文档、chunk 或 embedding 数量。

## 通用错误

| HTTP 状态 | 语义 | 恢复方法 |
|---:|---|---|
| `401` | 缺少必要身份或租户上下文 | 补齐本地测试 Header；生产等待可信登录 |
| `403` | 当前角色没有权限 | 使用具备权限的角色，不要修改 Header 冒充生产身份 |
| `404` | 资源不存在或对当前项目不可见 | 核对项目上下文和可见性 |
| `409` | 当前状态不允许操作或依赖未就绪 | 刷新资源状态，按 `allowed_transitions` 重试 |
| `413` | 上传超过大小限制 | 缩小文件；整改附件限制为 20 MiB |
| `422` | 请求字段、状态或文件类型无效 | 按响应 detail 修正请求 |
| `503` | 生产身份门禁或依赖不可用 | 停止业务请求，检查 `runtime_access` 或 Store 状态 |

## 兼容性

响应字段本轮只做兼容性新增。客户端应忽略未知字段，并优先使用服务端返回的能力字段。根路径和 `/api/backend` 仍存在，但新实现不得依赖它们。

## 证据边界

本地 API 与 E2E 使用临时 SQLite 和确定性 Fake Provider 通过。生产业务 API 尚未执行 UAT，状态为 `not_production_verified`。生产部署前不得把本地结果写成生产已通过。
