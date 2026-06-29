---
title: 知识库查询引擎 API 文档
doc_type: api
module: knowledge-query-engine
topic: knowledge-query-engine-api
status: stable
created: 2026-05-31
updated: 2026-06-22
owner: self
source: human+ai
---

# 知识库查询引擎 API 文档

## 1. 基础信息

- 服务框架：`FastAPI`
- 默认配置：`configs/knowledge-query-engine-dev.yaml`
- 健康检查：`GET /health`
- 权限头：`X-User-Id`、`X-Role`

当前医院角色：

- `admin` / `管理员`：账号、权限、成员分配、索引维护、审计日志读取。
- `technician` / `技术人员`：数据和索引维护、智能体配置，不能签发底稿。
- `director` / `主任`：复核、签发、审计日志读取、项目级材料读取。
- `member` / `普通成员`：审证、补证、草稿和个人材料上传。

兼容旧角色值：

- `auditor` 等价于 `member`。
- `it-admin` 等价于 `admin`。
- `department-head` 等价于 `director`。

索引管理操作允许 `X-Role: admin`、`X-Role: technician` 或兼容旧值 `X-Role: it-admin`。需要权限的写接口优先读取 `auth_users` 中当前 `X-User-Id` 对应的 `active/global` 角色授权；没有持久化 profile 时继续兼容 `X-Role`。缺少 `X-Role` 且无法从持久化 profile 解析角色时返回 `401`；角色存在但无动作权限、或持久化 profile 处于 `disabled/pending` 时返回 `403`，并记录 `authorization-denied` 操作日志。

权限底座边界：

- `auth_departments`、`auth_users`、`auth_user_role_assignments` 已作为最小持久化权限底座进入 schema。
- `/auth/session`、`/auth/roles`、`/auth/users` 和 `/auth/users/{user_key}/role-assignments` 已提供 header 过渡层 API；`/auth/session` 已接受 `X-Project-Key` 和本地 `X-Tenant-Id`，并返回项目授权 scope 和 `tenant_id`。
- `require_permission` 已优先使用持久化用户的 `active/global/project` 角色授权，并拒绝 `disabled/pending` 用户访问受控写入口。
- `/query`、`/documents/permissions`、`/documents/uploads`、`/audit/logs`、`/audit/logs/export` 和 `/pages/audit-logs` 已接入持久化用户优先解析；命中持久化 profile 时以 `active/global/project` 角色和用户状态为准，未命中时继续兼容 `X-Role`。
- `/auth/users/{user_key}` 支持软禁用/恢复用户，`/auth/users/{user_key}/role-assignments/{assignment_key}` 支持撤销/恢复角色授权；当前不做物理删除。
- 受控 API 鉴权中间件的本地强制模式已要求 `X-Tenant-Id`，但当前不存储密码、token、private key 或 SSO 凭据；真实医院 SSO、登录会话签发、正式租户身份来源和科室层级同步仍未完成。

### 权限接口

#### `GET /auth/roles`

返回医院四类角色、权限动作和旧角色兼容映射。无需写权限。

#### `GET /auth/session`

基于 `X-User-Id`、`X-Role`、`X-Project-Key` 和 `X-Tenant-Id` 返回当前 header 过渡层会话、权限动作、兼容旧角色、项目授权 scope、本地 `tenant_id` 和持久化用户 profile。若 `X-User-Id` 命中持久化用户且存在 `active/global/project` 角色授权，返回角色以持久化授权为准，并通过 `auth_source` 标明来源；缺少 `X-Role` 且没有持久化授权时按普通成员只读 session 处理，不代表正式登录。

#### `GET /auth/users`

返回用户、科室和角色授权列表。需要 `manage_project_members` 权限，即 `admin/管理员` 或兼容旧值 `it-admin`。未授权返回 `401/403` 并记录 `authorization-denied`。

#### `POST /auth/users`

创建最小用户 profile。需要 `manage_project_members` 权限。

请求体：

```json
{
  "display_name": "医保办主任",
  "department_key": "medical-insurance-office",
  "status": "active"
}
```

#### `PATCH /auth/users/{user_key}`

更新最小用户 profile。需要 `manage_project_members` 权限。当前用于软禁用、恢复、调整展示名、科室和 metadata；不删除账号。

请求体示例：

```json
{
  "status": "disabled"
}
```

#### `POST /auth/users/{user_key}/role-assignments`

给用户分配医院角色。需要 `manage_project_members` 权限。

请求体：

```json
{
  "role": "director",
  "scope_type": "project",
  "scope_key": "CATALOG-LIMIT-202606",
  "status": "active"
}
```

#### `PATCH /auth/users/{user_key}/role-assignments/{assignment_key}`

更新角色授权。需要 `manage_project_members` 权限。当前用于将授权状态设置为 `revoked` 或恢复为 `active`；不删除授权记录。

请求体示例：

```json
{
  "status": "revoked"
}
```

### 智能体接口

#### `GET /agents`

返回可用于新对话选择的 active 提示词型智能体。前端通过 `X-User-Id`、`X-Role` 传入当前角色时，后端会按 `allowed_roles` 过滤可见范围；未传 header 的兼容读取仍返回 active 默认智能体和 active 自定义智能体。

响应字段补充：

- `prompt_version`：当前提示词版本号。
- `prompt_version_key`：当前提示词版本标识，格式为 `{agent_id}@v{version}`。
- `prompt_versions`：提示词版本数组，包含 `version`、`prompt`、`change_summary`、`created_by`、`created_at`。
- `visibility_scope`：`project` 或 `system`。
- `allowed_roles`：允许选择该智能体的医院角色。
- `status`：`active`、`inactive` 或 `archived`。列表只返回 `active`。

#### `GET /agents/{agent_key}`

返回单个智能体详情。该接口可读取 `inactive/archived` 自定义智能体，用于历史对话追溯；默认系统智能体也可按固定 key 查询。不存在时返回 `404`。

#### `GET /agents/{agent_key}/prompt-versions`

返回单个智能体的提示词版本历史。该接口用于前端版本对比和回滚前核验；默认系统智能体返回 `v1` 合成版本，自定义智能体读取 `audit_agent_prompt_versions`。

#### `POST /agents`

创建提示词型智能体。需要 `manage_agents` 权限，普通成员无权发布系统级或项目级智能体。请求体在原有字段基础上支持：

```json
{
  "visibility_scope": "project",
  "allowed_roles": ["admin", "technician", "director", "member"]
}
```

创建成功后写入 `audit_agents`，并在 `audit_agent_prompt_versions` 创建 `v1` 提示词版本。该接口仍不执行外部 AI provider 调用。

#### `POST /agents/{agent_key}/prompt-versions`

新增提示词版本并把智能体当前 prompt 更新到新版本。需要 `manage_agents` 权限。

请求体：

```json
{
  "prompt": "更新后的提示词",
  "change_summary": "说明本次提示词变更原因"
}
```

成功后记录 `agent-prompt-version-create` 操作日志。

#### `POST /agents/{agent_key}/prompt-versions/rollback`

按历史版本回滚提示词。需要 `manage_agents` 权限。回滚会生成一个新的当前版本，`change_summary` 记录为回滚来源，不覆盖历史版本。

请求体：

```json
{
  "version": 1
}
```

成功后记录 `agent-prompt-version-rollback` 操作日志。

#### `POST /agents/{agent_key}/lifecycle`

更新自定义智能体生命周期。需要 `manage_agents` 权限。`inactive` 或 `archived` 后不会进入 `GET /agents` 的新对话选择列表，但仍可通过 `GET /agents/{agent_key}` 追溯。

请求体：

```json
{
  "status": "inactive",
  "reason": "提示词待复核"
}
```

成功后记录 `agent-lifecycle-update` 操作日志。

#### `GET /agents/{agent_key}/invocations`

返回单个智能体最近调用记录。需要 `manage_agents` 权限，用于管理员、技术人员或主任复盘智能体使用情况。

#### `POST /agents/{agent_key}/invocations`

登记一次智能体使用记录。需要 `query_knowledge` 权限，不执行外部模型调用。

请求体：

```json
{
  "invocation_source": "agent-workspace",
  "question": "目录限制核验试用",
  "conversation_ref": "local-chat-draft",
  "metadata": {}
}
```

成功后写入 `audit_agent_invocations` 并记录 `agent-invocation-create` 操作日志。

#### `GET /agents/{agent_key}/feedback`

返回单个智能体最近效果反馈。需要 `manage_agents` 权限。

#### `POST /agents/{agent_key}/feedback`

提交智能体效果反馈。需要 `query_knowledge` 权限，`rating` 仅允许 `effective`、`needs_review`、`unsafe`。

请求体：

```json
{
  "invocation_id": "可选调用记录 ID",
  "rating": "needs_review",
  "comment": "需要补充目录限制原文适用条件。",
  "metadata": {}
}
```

成功后写入 `audit_agent_feedback` 并记录 `agent-feedback-create` 操作日志。

## 2. 页面入口

### `GET /`

渲染对话审证工作台，与 `GET /pages/chat` 使用同一处理逻辑。

### `GET /pages/chat`

服务端模板对话审证页。

Query 参数：

- `question`：自然语言问题，可为空。
- `source_collection`：可重复传入，值为来源集合枚举。

页面展示：

- 对话输入区
- 最近对话
- 推荐追问
- 引用型回答
- 证据质量状态
- 分组依据
- 原文预览入口
- 创建复核任务入口
- 审计底稿 Markdown/Word/JSON 导出入口

### `GET /pages/chat/export`

导出当前单轮对话的审计底稿，支持 JSON、Markdown 和 Word/docx。该接口会重新执行一次引用型查询，因此要求检索后端已加载；没有引用依据时不生成底稿。

Query 参数：

- `question`：必填，自然语言问题。
- `source_collection`：可重复传入，值为来源集合枚举。
- `format`：`json`、`markdown` 或 `docx`，默认 `json`。

导出内容：

- 问题、回答、置信度、生成方式和复核门禁。
- 人工复核清单。
- 证据分组。
- 每条引用的 `citation_id`、`chunk_id`、`index_version_key`、`source_package_version_key`、`score`、`locator` 和 `preview_url`。

响应：

- `format=json`：`application/json`，下载文件名 `auditscope-dossier.json`。
- `format=markdown`：`text/markdown`，下载文件名 `auditscope-dossier.md`。
- `format=docx`：`application/vnd.openxmlformats-officedocument.wordprocessingml.document`，下载文件名 `auditscope-dossier.docx`。docx 内容由同一份 Markdown 底稿即时转换，不新增外部 provider 调用。

状态码：

- `200`：导出成功。
- `409`：检索后端未加载。
- `404`：没有找到可引用依据。

### `GET /pages/review-tasks`

服务端模板复核任务台。默认使用 PostgreSQL `review_tasks`、`review_actions` 持久化任务记录和状态流转，用于把单轮对话底稿沉淀为可追踪复核项；测试和应急路径仍保留 JSON store，但不作为生产默认存储。

当前边界：该任务台已经具备数据库持久化、任务级报告准备度预检、负责人确认记录、附件清单登记、附件文件归档、任务级导出、报告草稿导出、任务级正式报告签发冻结、签发后整改跟踪、任务级结案门禁和关闭后只读锁定，但仍不替代完整案件系统、权限系统、对象存储、病毒扫描、电子签章、独立整改数据库表或案件归档流。

页面展示：

- 任务总数、开放任务、报告就绪、待补证据、关闭任务统计。
- 复核任务列表。
- 每个任务的问题、创建时间、更新时间、引用数量、承办人、报告门禁预检、结案门禁预检和结案只读提示。
- 复核状态、承办人、复核意见、复核结论、底稿状态、底稿编号、底稿说明、负责人确认状态、确认人、确认时间、手工附件清单、附件文件上传归档、报告标题、报告摘要和整改建议编辑表单。
- 任务级 Markdown/Word/JSON 导出入口。
- 报告草稿 Markdown/Word/JSON 导出入口。确认违规任务必须具备复核结论、底稿就绪、负责人确认和至少 1 条附件登记后才能导出报告草稿。
- 正式报告签发入口。签发会冻结当前报告草稿 Markdown 正文并保存 `sha256`，签发后不能重复签发。
- 整改跟踪入口。正式报告签发后才能生成整改事项，整改事项绑定已签发报告编号和正文 `sha256`。
- 结案门禁和关闭后只读锁定。确认违规、已签发或已生成整改事项的任务，必须在整改状态为 `accepted` 后才能保存为 `closed`；任务一旦进入 `closed`，状态更新、附件上传、正式报告签发和整改更新写接口均返回 `409`，并记录 `review-task-readonly-write-blocked` 操作日志。配置了数据库日志 store 时，该事件会同步写入 `audit_log_events`，页面查看、附件下载和导出仍允许。

### `GET /reports/workpaper-templates`

返回审计底稿 Word 模板 registry 元数据，覆盖三张医保费用模板：

- `表1_医保费用汇总表-模版.xlsx`
- `表2_医保费用分类汇总表-模版.xlsx`
- `表3_就诊费用明细表-模版.xlsx`

响应字段：

- `format`：固定为 `workpaper-template-registry-v1`。
- `registry_status`：当前模板 registry 状态。
- `items`：模板列表，包含 `source_file_name`、`source_table`、`sheet_name`、`expected_columns`、`key_checks`、`evidence_bindings`、`prompt` 和 `chat_href`。
- `store`：当前 registry 来源，现阶段为本地静态模板 registry。

当前边界：该接口提供可复用模板元数据和字段绑定，不读取生产文件、不执行模板文件上传、不调用外部 provider，也不代表电子签章或证书级正式报告模板。

### `GET /reports/workbench`

返回 Next `/reports` 页面使用的报告工作台数据，包含模板 registry、复核任务映射出的报告记录、证据来源和统计。

响应字段：

- `format`：固定为 `report-workbench-v1`。
- `workpaper_templates`：同一套模板 registry 元数据。
- `report_entries`：由 `review_tasks` 生成的报告记录，包含报告状态、编号、门禁摘要、附件数、任务 Word 下载链接和报告 Word 下载链接。
- `report_evidence_sources`：由复核任务底稿、附件和报告门禁映射出的证据来源。
- `metrics`：报告数、已签发报告数、门禁阻断数、纳入疑点数和可下载报告 docx 数。

下载链接行为：

- `download_links.task_docx` 始终指向 `/review-tasks/{task_id}/export?format=docx`。
- `download_links.report_docx` 仅在报告草稿已过门禁或正式报告已签发时提供；未过门禁时为 `null`。
- 已签发报告的 `report_docx` 指向冻结正文的 `/review-tasks/{task_id}/signed-report?format=docx`。

当前边界：该接口只做本地 API-first 聚合和下载链接编排；docx 仍由既有 Markdown 即时转换，不新增 provider 调用，不代表生产验收、电子签章或对象存储归档。

### `POST /pages/review-tasks/create`

从当前问题创建复核任务。该接口读取 `application/x-www-form-urlencoded` 表单，会重新执行一次引用型查询并保存当时的审计底稿快照。

Form 字段：

- `question`：必填，自然语言问题。
- `source_collection`：可重复传入，值为来源集合枚举。

状态码：

- `303`：创建成功，跳转 `/pages/review-tasks`。
- `409`：检索后端未加载。
- `404`：没有找到可引用依据。
- `422`：缺少问题或来源集合枚举非法。

### `POST /pages/review-tasks/{task_id}/status`

更新复核任务状态、承办人、复核意见、复核结论、底稿状态和负责人确认记录。

Form 字段：

- `status`：必填，允许值为 `pending-review`、`confirmed-violation`、`rule-issue`、`data-issue`、`needs-evidence`、`not-violation`、`closed`。
- `assigned_to`：可选，任务承办人。
- `reviewer_note`：可选，人工复核意见。
- `conclusion`：可选，复核结论。
- `workpaper_status`：可选，允许值为 `missing`、`draft`、`ready`、`not-required`。
- `workpaper_id`：可选，底稿编号或外部底稿位置。
- `workpaper_note`：可选，底稿说明。
- `owner_signoff_status`：可选，允许值为 `not-requested`、`requested`、`approved`、`rejected`。
- `owner_confirmed_by`：可选，负责人确认人。
- `owner_confirmed_at`：可选，负责人确认时间，建议使用 ISO 8601。
- `attachment_manifest`：可选，外部附件清单文本。每行格式为 `附件名称 | 位置或编号 | 说明`。该字段用于登记外部材料位置，已上传归档文件不会被状态保存表单覆盖。
- `report_title`：可选，报告草稿标题。
- `report_summary`：可选，报告草稿摘要。
- `rectification_request`：可选，报告草稿整改建议。

状态码：

- `303`：保存成功，跳转 `/pages/review-tasks`。
- `404`：任务不存在。
- `409`：尝试结案但整改尚未验收，或任务已结案只读锁定。
- `422`：状态、底稿状态、负责人确认状态非法，或缺少状态字段。

### `POST /pages/review-tasks/{task_id}/attachments`

上传并归档复核任务附件文件。文件保存到服务端 `settings.index_root/review-task-attachments/{task_id}/`，任务 `dossier.attachments` 写入附件元数据。

Form 字段：

- `attachment_file`：必填，multipart 文件字段。
- `attachment_title`：可选，附件标题；为空时使用原始文件名。
- `attachment_note`：可选，附件说明。

归档元数据：

- `attachment_id`：服务端生成的附件编号。
- `status`：`uploaded`。
- `original_filename`、`media_type`、`byte_size`、`sha256`、`storage_path`、`uploaded_at`。

限制：

- 单文件最大 `20 MiB`。
- 空文件返回 `422`。
- 文件路径由服务端生成，不使用客户端原始文件名作为存储路径。

状态码：

- `303`：上传成功，跳转 `/pages/review-tasks`。
- `404`：任务不存在。
- `409`：任务已结案只读锁定。
- `413`：附件超过大小限制。
- `422`：附件为空或缺少文件字段。

### `GET /review-tasks/{task_id}/attachments/{attachment_id}/download`

下载已归档附件。接口只读取 `settings.index_root/review-task-attachments/` 内的归档文件；没有 `storage_path` 的外部登记附件不能下载。

状态码：

- `200`：下载成功。
- `404`：任务、附件元数据或归档文件不存在。

### `GET /review-tasks/{task_id}/export`

导出任务级复核记录，支持 JSON、Markdown 和 Word/docx。

Query 参数：

- `format`：`json`、`markdown` 或 `docx`，默认 `json`。

导出内容：

- `review-task-v1` 任务元数据。
- 任务状态、承办人、复核意见、复核结论和任务级 `report_gate` 预检结果。
- `dossier.workpaper` 底稿状态和 `dossier.owner_signoff` 负责人确认记录。
- `dossier.attachments` 附件登记清单。
- `dossier.report_draft` 报告草稿字段。
- 创建任务时保存的 `audit-dossier-v1` 底稿快照。

响应：

- `format=json`：`application/json`，下载文件名 `{task_id}.json`。
- `format=markdown`：`text/markdown`，下载文件名 `{task_id}.md`。
- `format=docx`：`application/vnd.openxmlformats-officedocument.wordprocessingml.document`，下载文件名 `{task_id}.docx`。

状态码：

- `200`：导出成功。
- `404`：任务不存在。

### `GET /review-tasks/{task_id}/report-draft`

导出任务级报告草稿，支持 JSON、Markdown 和 Word/docx。该接口只在任务级 `report_gate.ready_for_report=true` 时可用；确认违规任务必须完成复核状态闭合、复核意见、复核结论、底稿就绪、负责人确认和附件登记。

Query 参数：

- `format`：`json`、`markdown` 或 `docx`，默认 `markdown`。

导出内容：

- `review-task-report-draft-v1` 报告草稿元数据。
- 报告标题、复核摘要、复核意见、复核结论和整改建议。
- 底稿编号、负责人确认和附件清单。
- `source_task` 原始任务导出快照，保留引用链、知识库版本和任务门禁。

响应：

- `format=json`：`application/json`，下载文件名 `{task_id}-report-draft.json`。
- `format=markdown`：`text/markdown`，下载文件名 `{task_id}-report-draft.md`。
- `format=docx`：`application/vnd.openxmlformats-officedocument.wordprocessingml.document`，下载文件名 `{task_id}-report-draft.docx`。

状态码：

- `200`：导出成功。
- `404`：任务不存在。
- `409`：任务未通过报告门禁。

### `POST /pages/review-tasks/{task_id}/report-signoff`

签发任务级正式报告。该接口只在任务级报告门禁通过后可用；签发后会冻结当前报告草稿 Markdown 正文，写入 `dossier.signed_report`。

Form 字段：

- `signed_by`：必填，签发人。
- `signoff_note`：可选，签发说明。

签发元数据：

- `format`：`review-task-signed-report-v1`。
- `report_id`：服务端生成的正式报告编号。
- `signed_by`、`signed_at`、`signoff_note`。
- `content_sha256`、`content_byte_size`、`content_media_type`。
- `attachment_count`。
- `content`：签发时冻结的 Markdown 正文。

状态码：

- `303`：签发成功，跳转 `/pages/review-tasks`。
- `404`：任务不存在。
- `409`：任务未通过报告门禁、该任务已经签发，或任务已结案只读锁定。
- `422`：缺少签发人。

### `GET /review-tasks/{task_id}/signed-report`

下载已签发正式报告，支持 JSON、Markdown 和 Word/docx。下载内容来自签发时冻结的 `dossier.signed_report.content`，不会因后续编辑报告草稿而变化；docx 是从冻结 Markdown 正文即时生成，签发正文 `content_sha256` 仍以冻结 Markdown 为准。

Query 参数：

- `format`：`json`、`markdown` 或 `docx`，默认 `markdown`。

响应：

- `format=json`：`application/json`，下载文件名 `{task_id}-signed-report.json`。
- `format=markdown`：`text/markdown`，下载文件名 `{task_id}-signed-report.md`。
- `format=docx`：`application/vnd.openxmlformats-officedocument.wordprocessingml.document`，下载文件名 `{task_id}-signed-report.docx`。

状态码：

- `200`：下载成功。
- `404`：任务不存在。
- `409`：任务尚未签发。

### `POST /pages/review-tasks/{task_id}/rectification`

生成或更新任务级整改事项。该接口只在正式报告已经签发后可用，整改事项会绑定 `dossier.signed_report.report_id` 和 `content_sha256`，用于证明整改来源来自已冻结报告正文。

Form 字段：

- `rectification_status`：必填，允许值为 `pending-rectification`、`in-progress`、`submitted`、`accepted`、`returned`。
- `responsible_department`：可选，责任科室。
- `responsible_owner`：可选，责任人。
- `due_date`：可选，整改期限，建议使用 `YYYY-MM-DD`。
- `action_request`：可选，整改要求；为空时沿用报告草稿中的整改建议。
- `progress_note`：可选，本次进度说明、验收说明或退回原因。

整改元数据：

- `format`：`review-task-rectification-v1`。
- `rectification_id`：服务端生成的整改编号。
- `status`、`status_label`。
- `responsible_department`、`responsible_owner`、`due_date`。
- `action_request`、`progress_note`。
- `source_report_id`、`source_report_sha256`。
- `event_count`、`events`：每次状态保存追加一条事件，记录前后状态、时间、操作人和说明。

状态码：

- `303`：保存成功，跳转 `/pages/review-tasks`。
- `404`：任务不存在。
- `409`：正式报告尚未签发，或任务已结案只读锁定。
- `422`：整改状态非法或缺少必填字段。

### `GET /review-tasks/{task_id}/rectification/export`

导出任务级整改跟踪记录，支持 JSON 和 Markdown 两种格式。

Query 参数：

- `format`：`json` 或 `markdown`，默认 `json`。

响应：

- `format=json`：`application/json`，下载文件名 `{task_id}-rectification.json`。
- `format=markdown`：`text/markdown`，下载文件名 `{task_id}-rectification.md`。

状态码：

- `200`：导出成功。
- `404`：任务不存在。
- `409`：整改事项尚未生成。

### `GET /pages/query`

服务端模板简版查询页。

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
- `Release Console`：发布 candidate、回滚历史版本、重载 PostgreSQL 后端、打开 smoke question
- `Acceptance Panel`：运行发布后固定检索评测、答案评测和 UI smoke 预览验收
- 验收历史：展示最近报告，并提供 `GET /index/evaluation/history` JSON 列表入口
- 操作日志导出入口

## 3. 查询接口

### `POST /query`

认证行为：

- 接口读取 `X-User-Id`、`X-Role`；若 `X-User-Id` 命中 `auth_users` 且存在 `active/global` 角色授权，以持久化角色为准。
- 持久化 profile 为 `disabled/pending` 时返回 `403`；没有持久化 profile 时继续兼容旧 `X-Role`，缺省按 `member/auditor` 处理。
- 查询日志记录使用解析后的 `user_identifier`，并在进程内日志中保留 `effective_role` 和 `auth_source`。

请求体：

```json
{
  "question": "超量开药的审核依据是什么？",
  "top_k": 5,
  "source_collections": ["supervision-rules-knowledge"],
  "years": [2024],
  "regions": ["国家"],
  "document_types": ["rule"],
  "business_topics": ["prescription-audit"],
  "title_only": false
}
```

过滤说明：

- `title_only=true` 时，后端只在索引元数据中的 `title`、`document_title`、`title_path`、`file_name`、`source_path` 和 locator 对应字段上匹配问题关键词；正文命中不会单独进入结果。
- `title_only` 默认 `false`，保持既有全文检索行为。

返回体核心字段：

- `answer`：引用型回答正文。
- `confidence`：`high | medium | low`。
- `fallback_used`：是否使用 fallback 答案。
- `basis_groups`：按证据类型分组的依据；每条 `items` 直接回显 `source_collection`。
- `citations`：引用列表，含 `chunk_id`、`source_collection`、locator、索引版本和资料包版本。
- `query_log_index`：本次查询日志索引。
- `query_log_id`：持久化查询历史 ID；当查询历史 store 不可用或写入失败时为 `null`，主查询结果不因历史写入失败而中断。

错误：

- `403`：角色无查询权限。
- `404`：未找到可引用依据。
- `409`：检索引擎未初始化。

### `GET /query/logs`

返回最近查询日志，默认 `limit=20`，允许范围 `1..100`：

```json
{
  "items": [
    {
      "id": "47de2cc5-8d88-43e9-888b-42775d2060e4",
      "user_identifier": "next-knowledge-query",
      "question": "医保基金审核依据如何留痕？",
      "filters": {
        "top_k": 8,
        "source_collections": [],
        "years": [],
        "regions": [],
        "document_types": [],
        "business_topics": [],
        "title_only": false
      },
      "answer_summary": "问题：医保基金审核依据如何留痕？...",
      "retrieved_chunk_ids": ["11111111-1111-4111-8111-111111111111"],
      "citation_count": 1,
      "created_at": "2026-06-15T03:14:48Z"
    }
  ],
  "store": {
    "ready": true,
    "backend": "SqlAlchemyQueryHistoryStore"
  }
}
```

说明：

- PostgreSQL 后端使用既有 `query_logs` 表持久化查询问题、过滤条件、答案摘要和引用 chunk。
- 如果服务未配置查询历史 store，接口回退返回进程内最近日志，`store.ready=false`、`store.backend="memory"`。
- 如果查询历史 store 读取失败，接口同样回退到进程内最近日志，`store.ready=false`，并返回结构化 `error.error_type`，不暴露数据库连接串或异常正文。

## 4. 文档接口

### `GET /documents/permissions`

返回当前角色可读取的文档来源集合和个人材料上传权限。`personal-materials` 只允许显式选择，
不会进入默认查询来源集合；普通成员为本人材料显式查询，主任/管理员可按权限读取全部个人材料。

请求头：

- `X-User-Id`：当前用户标识；命中持久化用户时优先使用其 `active/global` 角色授权和用户状态。
- `X-Role`：`member`、`admin`、`technician`、`director`，或兼容旧值 `auditor`、`it-admin`、`department-head`；缺省按 `member/auditor` 处理。

响应示例：

```json
{
  "role": "auditor",
  "source_collections": [
    {
      "source_collection": "medical-insurance-laws",
      "label": "法规政策",
      "scope": "公开知识库",
      "access": "read"
    },
    {
      "source_collection": "personal-materials",
      "label": "个人材料",
      "scope": "个人上传材料",
      "access": "explicit-owner-read"
    }
  ],
  "upload_permissions": {
    "can_upload_personal": true,
    "can_read_all_personal_uploads": false,
    "can_govern_personal_uploads": false
  }
}
```

错误：

- `403`：角色无查询权限。
- `403`：持久化用户 profile 处于 `disabled/pending`。

### `GET /documents/uploads`

返回个人材料留存记录。

请求头：

- `X-User-Id`：当前用户标识；缺省为 `anonymous`。
- `X-Role`：`member`、`admin`、`technician`、`director`，或兼容旧值 `auditor`、`it-admin`、`department-head`。

Query 参数：

- `limit`：返回数量，范围 `1` 到 `100`，默认 `20`。

权限行为：

- 命中持久化用户时，列表读取以持久化 `active/global` 角色为准；例如持久化主任即使 header 仍是 `auditor`，也可读取全部个人材料。
- 持久化用户处于 `disabled/pending` 时返回 `403`。
- `member/auditor` 和 `technician` 只读取自己上传的个人材料。
- `admin/it-admin` 和 `director/department-head` 可读取全部个人材料留存记录。
- `admin/it-admin`、`technician` 和 `director/department-head` 可治理个人材料入索引状态；`member/auditor` 不能治理。

响应核心字段：

- `items`
- `store.ready`
- `store.backend`
- `permissions`

每条 `items` 记录包含：

- `id`
- `name`
- `extension`
- `size_bytes`
- `size_kb`
- `sha256`
- `storage_path`
- `visibility`
- `status`
- `created_by`
- `created_at`
- `retention_status`
- `index_status`
- `governance_status`
- `governance_note`
- `governed_by`
- `governed_at`
- `security_scan_status`
- `security_scan_provider`
- `dlp_status`
- `security_findings`
- `download_url`

### `POST /documents/uploads`

上传个人材料并写入受控留存目录。支持 multipart 上传。

上传限制：

- 文件字段名：`file`
- 支持扩展名：`pdf`、`md`、`txt`、`csv`、`xlsx`、`xlsm`
- 最大文件大小：`20MB`

持久化行为：

- 配置 `document_upload_store` 后，接口会把原始上传文件写入受控留存目录，并写入 `document_upload_records`。
- 留存目录优先使用 `MEDICAL_AUDIT_DOCUMENT_UPLOAD_ROOT`，未配置时使用 `index_root/document-uploads`。
- 文件名使用系统生成的 `document-upload-*` 记录号，不复用原始文件名作为物理文件名。
- 数据库记录保存原始文件名、扩展名、大小、`sha256`、相对留存路径、`visibility=private`、`status=retained`、上传用户、`metadata.index_status=not-indexed`、`metadata.governance_status=pending-review`、本地策略扫描状态和 DLP 标记。
- `security_scan_provider=local-policy` 表示仅执行本地关键词/文件类型策略检查；这不是外部杀毒引擎或医院级 DLP 服务。

### `GET /documents/uploads/{upload_id}/download`

下载个人材料留存文件。读取权限与列表一致但更严格按单条记录判断：

- 上传本人可下载自己的材料。
- `admin/it-admin` 和 `director/department-head` 可下载全部个人材料。
- 其他普通成员不可见，返回 `404` 并记录 `authorization-denied`，避免暴露他人上传记录是否存在。

响应头：

- `Content-Disposition`：使用原始文件名下载。
- `X-Document-Upload-Id`
- `X-Document-Security-Scan`
- `X-Document-DLP-Status`

成功下载会记录 `document-upload-download` 操作日志。

### `POST /documents/uploads/{upload_id}/governance`

更新个人材料治理状态。需要管理员、技术人员或主任角色；普通成员不能调用。

请求体：

```json
{
  "governance_status": "approved-for-index",
  "note": "已完成材料治理。"
}
```

状态映射：

- `pending-review` -> `index_status=not-indexed`
- `approved-for-index` -> `index_status=index-ready`
- `blocked` -> `index_status=blocked`

接口返回与 `POST /documents/uploads` 相同的 `item`、`store` 和 `permissions` 结构，并记录 `document-upload-governance-update` 操作日志。若本地策略扫描或 DLP 标记为待复核，接口会阻断 `approved-for-index`，返回 `409`，并记录 `document-upload-governance-blocked`。

当前边界：

- 本接口只完成个人材料留存、列表读取、受控下载、本地策略扫描/DLP 标记和本地治理状态标记，不把上传材料写入检索索引。
- `index-ready` 表示材料已通过本地治理、可进入后续索引任务队列，不代表真实向量索引已有该文件内容。
- 本接口不执行外部杀毒引擎扫描、真实医院 DLP 服务、脱敏改写、对象存储上传或生命周期清理。
- 当前权限模型已优先读取本地持久化用户、全局/项目角色授权和本地租户头契约，但仍通过 `X-Role`、`X-User-Id`、`X-Project-Key` 和 `X-Tenant-Id` 作为过渡输入，不等于真实登录会话、医院 SSO、正式租户身份来源和科室级权限体系。

状态码：

- `200`：留存成功。
- `409`：上传 store 未配置。
- `413`：文件超过大小限制。
- `422`：扩展名不支持或空文件。

## 5. 数据分析接口

### `POST /analytics/table-upload`

接收审计表格并生成字段画像、质量提示、重复行统计和审计信号。支持 multipart 上传。

上传限制：

- 文件字段名：`file`
- 支持扩展名：`csv`、`xlsx`、`xlsm`
- 最大文件大小：`20MB`

成功响应核心字段：

- `name`
- `size_kb`
- `extension`
- `sheet_name`
- `columns`
- `row_count`
- `empty_cell_count`
- `duplicate_row_count`
- `quality_findings`
- `audit_signals`
- `recommendations`
- `upload_id`
- `sha256`
- `retention_status`
- `created_at`

持久化行为：

- 配置 `analytics_upload_store` 后，接口会把原始上传文件写入受控留存目录，并写入 `analytics_upload_records`。
- 留存目录优先使用 `MEDICAL_AUDIT_ANALYTICS_UPLOAD_ROOT`，未配置时使用 `index_root/analytics-uploads`。
- 文件名使用系统生成的 `analytics-upload-*` 记录号，不复用原始文件名作为物理文件名。
- 数据库记录保存原始文件名、扩展名、大小、`sha256`、相对留存路径、sheet、行列统计、空值/重复行统计、审计信号和分析摘要。
- 已配置 store 时，留存或记录写入失败会导致本次上传失败，不返回“已分析但未留存”的成功状态。

当前边界：

- 本接口不执行病毒扫描、脱敏改写、权限隔离下载或正式审计任务生成。
- 当前未提供上传文件下载接口；留存文件用于受控审计追溯和后续治理能力扩展。

状态码：

- `200`：解析和留存成功。
- `413`：文件超过大小限制。
- `422`：扩展名不支持、空文件、编码不支持或工作簿无法解析。

### `GET /analytics/table-uploads`

返回最近上传留存记录。

Query 参数：

- `limit`：返回数量，范围 `1` 到 `100`，默认 `20`。

响应核心字段：

- `items`
- `store.ready`
- `store.backend`

每条 `items` 记录包含：

- `id`
- `name`
- `extension`
- `size_bytes`
- `size_kb`
- `sha256`
- `storage_path`
- `sheet_name`
- `row_count`
- `column_count`
- `empty_cell_count`
- `duplicate_row_count`
- `status`
- `created_by`
- `created_at`
- `retention_status`
- `audit_signals`

## 6. 原文预览接口

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

## 7. 索引接口

### `POST /index/rebuild`

全量重建索引。需要 `X-Role: admin`、`X-Role: technician` 或兼容旧值 `X-Role: it-admin`。

```json
{
  "package_version_key": "source-package-20260531"
}
```

### `POST /index/incremental`

基于当前快照执行增量索引。需要 `X-Role: admin`、`X-Role: technician` 或兼容旧值 `X-Role: it-admin`。如果没有历史快照，返回 `409`。

### `POST /index/retry-file`

重试单个文件。需要 `X-Role: admin`、`X-Role: technician` 或兼容旧值 `X-Role: it-admin`。

```json
{
  "package_version_key": "source-package-20260531",
  "relative_path": "全量法律/example.md"
}
```

### `GET /index/versions`

返回索引版本列表，并记录操作日志。

### `POST /index/versions/activate`

显式激活一个 PostgreSQL index version。需要 `X-Role: admin`、`X-Role: technician` 或兼容旧值 `X-Role: it-admin`。

请求体：

```json
{
  "index_version_key": "candidate-version-key"
}
```

响应体：

```json
{
  "result": {
    "success": true,
    "index_version_key": "candidate-version-key",
    "vector_provider": "openai",
    "vector_model": "kimi-for-coding",
    "previous_status": "candidate",
    "deactivated_index_version_keys": ["old-active-version-key"]
  },
  "next_steps": [
    "reload-postgres-search-backend",
    "run-ui-smoke",
    "run-fixed-evaluation"
  ]
}
```

错误：

- `401`：缺少 `X-Role`。
- `403`：角色无索引管理权限。
- `409`：目标版本不存在，或状态不允许激活。
- `503`：PostgreSQL 写入失败。

### `POST /index/versions/rollback`

显式回滚到历史 PostgreSQL index version。需要 `X-Role: admin`、`X-Role: technician` 或兼容旧值 `X-Role: it-admin`。

请求体：

```json
{
  "index_version_key": "previous-active-version-key"
}
```

约束：

- 目标版本必须是 `inactive` 或 `active`。
- `candidate` 不能作为 rollback 目标。
- 回滚后必须重新调用 `/index/search-backend/postgres` 重载运行态检索后端。

### `POST /index/evaluation/run`

运行发布后固定验收。需要 `X-Role: admin`、`X-Role: technician` 或兼容旧值 `X-Role: it-admin`，并要求 API 进程内检索后端已加载。

请求体默认值：

```json
{
  "retrieval_cases_file": "configs/evaluation/knowledge-query-human-evaluation-cases-v1.yaml",
  "answer_cases_file": "configs/evaluation/knowledge-query-answer-evaluation-cases-v1.yaml",
  "max_retrieval_cases": 52,
  "max_answer_cases": 8,
  "top_k": 5,
  "smoke_question": "医保基金审核依据",
  "min_recall_at_k": 1.0,
  "min_answer_pass_rate": 1.0
}
```

验收内容：

- `evaluate-postgres-index` 等价的固定检索评测，使用当前运行态 `search_engine`。
- `evaluate-answers` fallback 答案级评测，验证引用标记、答案术语、引用术语和拒答行为。
- UI smoke 预览检查：用 `smoke_question` 检索、构造引用型回答、解析第一条引用原文预览。

响应体核心字段：

```json
{
  "status": "pass",
  "retrieval": {"case_count": 52, "recall_at_k": 1.0},
  "answer": {"case_count": 8, "pass_rate": 1.0},
  "ui_smoke": {
    "success": true,
    "question": "医保基金审核依据",
    "citation_count": 5,
    "preview_path": "/pages/preview/{chunk_id}",
    "confidence": "high"
  },
  "thresholds": {
    "min_recall_at_k": 1.0,
    "min_answer_pass_rate": 1.0
  },
  "report": {
    "run_id": "uuid",
    "generated_at": "2026-06-02T00:00:00+00:00",
    "path": "tmp/knowledge-query-indexes/evaluation-runs/index-evaluation-run-YYYYMMDDTHHMMSSZ-uuid.json",
    "download_path": "/index/evaluation/latest/export",
    "history_path": "/index/evaluation/history",
    "history": {
      "backend": "postgres",
      "persisted": true,
      "table": "index_evaluation_runs",
      "run_id": "uuid"
    }
  },
  "history": {
    "backend": "postgres",
    "persisted": true,
    "table": "index_evaluation_runs",
    "run_id": "uuid"
  }
}
```

约束：

- 该接口不重建索引、不切换 active version，只验证当前 API 进程已加载的检索后端。
- 验收结果会写入当前 API 进程内 `evaluation_runs`、`index_root/evaluation-runs/` JSON 报告，并在 PostgreSQL 后端运行时写入 `index_evaluation_runs` 历史表。
- JSON 报告用于下载和数据库不可用时的容灾列表；PostgreSQL 历史表用于管理页历史查询。如需 Markdown 审计材料，仍使用 CLI 的 `--output` 和 `--json-output` 生成长期报告。
- `status=fail` 表示至少一个门禁未达阈值；接口仍返回 `200`，失败细节在对应字段中。

错误：

- `401`：缺少 `X-Role`。
- `403`：角色无索引管理权限。
- `409`：检索后端未加载、评测集文件不可用、评测集格式错误或没有可引用依据。

### `GET /index/evaluation/history`

返回最近发布后验收历史。

行为：

- PostgreSQL 可用时读取 `index_evaluation_runs`，按 `created_at DESC` 返回最近 `20` 条。
- PostgreSQL 不可用时降级读取 `index_root/evaluation-runs/` JSON 报告列表。
- 返回字段包含 `run_id`、`status`、`generated_at`、`retrieval_case_count`、`answer_case_count`、`ui_smoke_success`、`report_path`、`download_path` 和 `source`。
- 记录 `index-evaluation-history-view` 操作日志。

### `GET /index/evaluation/latest/export`

导出最近一次发布后验收 JSON 报告。

行为：

- 优先读取 `index_root/evaluation-runs/` 中最新 `index-evaluation-run-*.json`。
- 返回完整验收报告，包含 `request`、`search_backend`、`retrieval`、`answer`、`ui_smoke`、`thresholds` 和 `report` 元数据。
- 记录 `index-evaluation-report-export` 操作日志。

错误：

- `404`：尚未生成任何验收报告。

### `GET /index/jobs`

返回索引任务列表，并记录操作日志。

### `GET /index/failures`

返回失败文件队列，并记录操作日志。

### `GET /index/pending`

返回待处理文件队列，并记录操作日志。

### `GET /index/postgres-status`

返回 PostgreSQL 中已导入索引的只读状态摘要：

```json
{
  "available": true,
  "row_counts": {
    "source_package_versions": 1,
    "source_documents": 486,
    "document_chunks": 48985,
    "chunk_embeddings": 48985,
    "index_versions": 1,
    "index_jobs": 1,
    "failed_files": 0,
    "pending_files": 13
  },
  "embedding_sets": [
    {
      "provider": "openai",
      "model_name": "kimi-for-coding",
      "provider_version": "v1",
      "dimension": 1024,
      "embedding_count": 48985
    }
  ],
  "index_versions": [],
  "source_packages": []
}
```

错误：

- `503`：PostgreSQL 不可连接、schema 未初始化或状态查询失败。

### `GET /index/search-backend`

返回当前 API 运行态检索后端状态：

```json
{
  "backend": "none",
  "ready": false,
  "details": {}
}
```

### `POST /index/search-backend/postgres`

显式加载 PostgreSQL + pgvector 检索后端。需要 `X-Role: admin`、`X-Role: technician` 或兼容旧值 `X-Role: it-admin`。

Kimi 主索引运行参数：

```json
{
  "embedding_provider": "openai",
  "embedding_model": "kimi-for-coding",
  "embedding_dimension": 1024,
  "api_key_env": "KIMI_API_KEY",
  "embedding_base_url": "https://api.kimi.com/coding/v1",
  "embedding_batch_size": 16
}
```

约束：

- 该接口只切换当前 API 进程内运行态，不修改配置文件。
- `api_key_env` 只传环境变量名，不传 key 明文。
- 当前 PostgreSQL schema 固定为 Kimi `1024` 维主索引，不能用 `text-embedding-3-small` 的 `1536` 维配置加载。
- 加载前会检查 `chunk_embeddings` 中是否存在匹配的 provider、model、provider version 和 dimension；不匹配时返回 `409`。
- 未设置对应环境变量时返回 `409`，不会静默降级。
- 默认 `create_app()` 不自动加载 PostgreSQL 后端，避免配置与数据库向量模型不一致导致假成功。

加载成功后，`details.matching_embedding_count` 必须大于 `0`。当前生产 Kimi 主索引期望值为 `49051`。

## 8. 操作日志接口

### `GET /operation/logs`

返回查询、预览、索引管理和复核任务操作日志。当前接口返回 API 进程内最近操作；同一 `record_operation` 入口会在配置 `audit_log_store` 时把事件同步写入 `audit_log_events`。复核任务结案后被只读锁阻断的写请求会记录为 `review-task-readonly-write-blocked`，payload 包含 `task_id`、`task_status`、`attempted_action`、`endpoint`、`status_code`、`reason`、`user_identifier` 和 `role`。

### `GET /operation/logs/export`

导出操作日志 JSON，并记录 `operation-logs-export` 操作。

### `GET /audit/logs`

查询持久化审计日志 `audit_log_events`。需要 `read_audit_logs` 权限，即持久化 `admin/director` 角色或兼容旧值 `X-Role: it-admin`、`X-Role: department-head`；其他角色返回 `403`，并记录 `authorization-denied`。持久化 profile 为 `disabled/pending` 时同样返回 `403`。支持按 `action`、`entity_type`、`entity_id`、`user_identifier`、`created_from`、`created_to` 和 `limit` 过滤。该接口读取数据库日志 store；未配置时返回空列表和 `store.ready=false`，不把进程内临时日志伪装成持久化审计链。响应会对 `api_key`、`authorization`、`credential`、`password`、`secret`、`token` 等敏感字段做 response-only 脱敏，当前策略保留周期为 `180` 天，保留期外事件通过 `medical-audit-kb audit-log-retention` 执行显式归档和清理。

### `GET /audit/logs/export`

导出持久化审计日志 JSON。需要 `read_audit_logs` 权限；持久化 `admin/director` 角色优先于兼容 header，未授权返回 `401/403` 并记录 `authorization-denied`。授权导出会记录 `audit-logs-export` 操作。未配置数据库日志 store 时返回 `409`。默认导出上限为 `500` 条，可按同一组过滤参数缩小范围。导出结果同样应用 response-only 脱敏策略。

### `GET /pages/audit-logs`

审计日志台页面。需要持久化 `admin/director` 角色或认证代理/API client 注入兼容旧值 `X-Role: it-admin`、`X-Role: department-head` 后才展示事件；未授权或已停用用户仍返回页面，但只显示权限提示，不渲染事件、payload 或 metadata。用于按任务、用户、动作和时间范围追踪查询、导出、复核、签发、整改和结案阻断事件，并提供当前筛选结果的 JSON 导出入口。

当前未完成：证书级非对称签名/电子签章、长期留存介质迁移和外部告警接入。后台自动清理不作为默认安全路径；生产执行必须先显式归档再删除数据库中过期事件。

## 9. CLI 命令

### `medical-audit-kb acceptance-run`

对资料目录执行只读抽取和切分验收，输出 Markdown/JSON 报告。

核心参数：

- `--source-root`
- `--output`
- `--json-output`
- `--package-version-key`

### `medical-audit-kb index-build`

构建本地持久化索引 artifact。

核心参数：

- `--source-root`
- `--index-root`
- `--json-output`
- `--package-version-key`
- `--embedding-provider`: `fake | openai`
- `--embedding-model`
- `--embedding-dimension`
- `--api-key-env`
- `--embedding-base-url`
- `--embedding-batch-size`
- `--max-chunks`: 限制本次构建写入的 chunk 数，用于外部 embedding smoke test
- `--resume`: 复用已有匹配的 `embeddings.jsonl` 行，只追加缺失 embedding

说明：`openai` 表示 OpenAI-compatible `/v1/embeddings` 协议，不限定只能使用 OpenAI 官方服务。

### `medical-audit-kb evaluate-index`

加载本地持久化索引并运行检索评测。

核心参数：

- `--source-root`
- `--index-root`
- `--output`
- `--json-output`
- `--cases-file`: 固定评测集 YAML/JSON；提供后不再自动生成 material cases
- `--max-cases`
- `--top-k`
- `--query-terms`
- `--embedding-provider`: `fake | openai`
- `--embedding-model`
- `--embedding-dimension`
- `--api-key-env`
- `--embedding-base-url`
- `--embedding-batch-size`

说明：

- 评测真实向量索引时，查询 embedding provider 必须与索引构建 provider 保持一致。
- 固定人工评测集当前路径：`configs/evaluation/knowledge-query-human-evaluation-cases-v1.yaml`，当前为 `52` 条 review case。

### `medical-audit-kb index-incremental-plan`

从 PostgreSQL 当前 active index version 读取上一版 `source_documents`，与当前 `source-root` manifest 对比，生成只读增量影响计划。该命令不写数据库，不生成 embedding。

核心参数：

- `--source-root`
- `--package-version-key`
- `--database-url-env`: 默认 `MEDICAL_AUDIT_KB_DATABASE_URL`
- `--output`
- `--json-output`

输出核心字段：

- `added_files`
- `modified_files`
- `deleted_files`
- `unchanged_files`
- `pending_files`
- `ignored_files`
- `failed_files`
- `estimated_new_chunks`
- `estimated_reused_embeddings`
- `estimated_new_embeddings`
- `db_rows_to_activate`
- `db_rows_to_deactivate`

2026-06-02 增量计划历史验证结果：

- 报告：`drafts/analysis/knowledge-query-incremental-plan-current-draft-20260602.md`
- JSON：`tmp/outputs/knowledge-query-incremental-plan-current-20260602.json`
- `added_files`: `0`
- `modified_files`: `0`
- `deleted_files`: `0`
- `unchanged_files`: `486`
- `pending_files`: `13`
- `estimated_new_embeddings`: `0`

### `medical-audit-kb evaluate-postgres-index`

加载 PostgreSQL + pgvector 检索路径并运行固定评测集。当前实现中，向量召回来自 `chunk_embeddings` 的 pgvector cosine search；BM25 词法召回从数据库 `document_chunks` 构建内存索引，以保持中文分词和编码精确匹配逻辑一致。

核心参数：

- `--source-root`
- `--database-url-env`: 默认 `MEDICAL_AUDIT_KB_DATABASE_URL`
- `--output`
- `--json-output`
- `--cases-file`: 固定评测集 YAML/JSON
- `--max-cases`
- `--top-k`
- `--index-version-status`: `active | candidate | inactive`，默认 `active`
- `--index-version-key`: 可选，限定评测某个 `index_versions.version_key`
- `--embedding-provider`: `fake | openai`
- `--embedding-model`
- `--embedding-dimension`
- `--api-key-env`
- `--embedding-base-url`
- `--embedding-batch-size`

当前验证结果：

- pgvector self-query smoke：`tmp/outputs/knowledge-query-postgres-vector-self-query-smoke-20260601.json`，`passed=true`
- PostgreSQL 数据源 BM25 固定 52 case：`drafts/analysis/knowledge-query-postgres-bm25-evaluation-v1-draft-20260601.md`
- BM25 固定 52 case 指标：`recall@5=100%`，`citation_hit_rate=100%`，`preview_location_success_rate=100%`
- candidate-only PostgreSQL 固定 52 case：`tmp/outputs/knowledge-query-postgres-candidate-fixed-evaluation-20260603.json`
- candidate-only 指标：`index_version_key=full-rebuild-20260603085815`，`recall@5=100%`，`citation_hit_rate=100%`，`preview_location_success_rate=100%`

限制：当前 shell 未设置 `KIMI_API_KEY`，因此尚未运行固定 52 case 的真实 pgvector+Kimi 查询向量评测。

### `medical-audit-kb audit-log-retention`

对 `audit_log_events` 执行保留期归档和清理。默认 dry-run，只输出 Markdown/JSON 计划，不写归档文件、不删除数据库行；只有显式传入 `--execute` 时才会先写 JSONL 归档，再删除本批次过期事件。

核心参数：

- `--database-url-env`: 默认 `MEDICAL_AUDIT_KB_DATABASE_URL`
- `--retention-days`: 默认 `180`
- `--now`: 可选 ISO-8601 时间，用于测试或固定审计 cutoff
- `--limit`: 单批最多处理的过期事件数，默认 `1000`
- `--archive-root`: 可选，受控归档根目录；提供后自动生成标准归档路径
- `--archive-batch-key`: 可选，归档批次名，只允许字母、数字、点、下划线和连字符
- `--archive-output`: 未提供 `--archive-root`，且 `--execute` 存在过期事件时必填
- `--signature-output`: 可选，写出 detached 签名 manifest
- `--signing-secret-env`: 可选，从环境变量读取 HMAC 签名密钥；密钥不写入 manifest
- `--signing-key-id`: 可选，签名密钥标识；启用签名时必填
- `--signing-subject`: 可选，记录签名主体
- `--previous-signature-sha256`: 可选，记录上一份签名 manifest 的 `sha256`，用于形成链式留痕
- `--output`
- `--json-output`
- `--execute`: 执行写归档和删除；不传时为 dry-run
- `--create-schema`: 仅用于本地 fixture

输出核心字段：

- `mode`: `dry-run | execute`
- `cutoff`
- `expired_event_count`
- `archived_event_count`
- `deleted_event_count`
- `archive_root`
- `archive_layout`
- `archive_batch_key`
- `archive_output`
- `archive_sha256`
- `signature_manifest_output`
- `signature_manifest_sha256`
- `signature_algorithm`
- `previous_signature_sha256`
- `action_counts`
- `entity_type_counts`

归档文件为原始审计事件 JSONL，用于受控证据留存，不应用 response-only 脱敏。该文件必须存放在限制访问的归档介质；普通页面查询和 API 导出仍只返回脱敏结果。提供 `--archive-root` 后，默认路径为 `audit-log-events/YYYY/MM/DD/<batch-key>.jsonl`，签名模式默认同目录生成 `<batch-key>.signature.json`；如果同时传入 `--archive-output` 或 `--signature-output`，路径必须位于 `--archive-root` 内。签名 manifest 当前使用标准库 `HMAC-SHA256`，用于防篡改校验和链式留痕；它不等同于证书级非对称电子签章。

### `medical-audit-kb audit-log-archive-verify`

验证审计日志归档 JSONL 与 detached 签名 manifest 是否匹配，并检查 HMAC 签名是否有效。该命令只读，不修改数据库或归档文件；验证失败返回退出码 `2`，并在 Markdown/JSON 报告中列出阻断问题。

核心参数：

- `--archive-output`
- `--signature-manifest`
- `--signing-secret-env`
- `--output`
- `--json-output`

输出核心字段：

- `status`
- `archive_sha256_valid`
- `canonical_payload_sha256_valid`
- `signature_valid`
- `previous_signature_sha256`
- `issues`

### `medical-audit-kb audit-log-archive-audit`

递归巡检受控 `archive-root` 下的审计日志签名 manifest，逐个确认签名 manifest 位于归档根目录内、manifest 指向的归档文件仍位于归档根目录内、归档文件存在、归档 `sha256` 匹配且 HMAC 签名有效。该命令只读，不修改数据库、归档文件或签名 manifest。

核心参数：

- `--archive-root`
- `--signing-secret-env`
- `--min-manifest-count`: 默认 `0`；生产巡检建议设置为本期预期最小签名数量
- `--output`
- `--json-output`

输出核心字段：

- `status`
- `manifest_count`
- `verified_count`
- `failed_count`
- `missing_archive_count`
- `path_escape_count`
- `entries`
- `issues`

生产调度入口：`scripts/run-audit-log-archive-audit.py`。该脚本读取 `MEDICAL_AUDIT_AUDIT_LOG_ARCHIVE_ROOT`、`MEDICAL_AUDIT_AUDIT_LOG_ARCHIVE_REPORT_DIR`、`MEDICAL_AUDIT_AUDIT_LOG_SIGNING_SECRET_ENV` 和 `MEDICAL_AUDIT_AUDIT_LOG_MIN_MANIFEST_COUNT`，生成带时间戳的 Markdown/JSON 报告，并同步维护 `audit-log-archive-audit-latest.md` 与 `audit-log-archive-audit-latest.json`。脚本退出码保持与 CLI 一致，适合作为 cron/systemd timer 的告警依据。若配置 `MEDICAL_AUDIT_AUDIT_LOG_ALERT_WEBHOOK_URL`，脚本会在巡检失败或脚本异常时发送最小 JSON webhook 告警；默认成功不发送，手动验收可通过 `--send-success-alert` 测试通道。

### `medical-audit-kb ui-smoke`

通过 `TestClient` 执行真实 UI 查询闭环 smoke：

1. 读取 `/index/postgres-status`。
2. 以 `it-admin` 调用 `/index/search-backend/postgres` 加载 PostgreSQL 检索后端。
3. 请求 `/pages/query`，触发真实查询 embedding。
4. 从查询页提取第一条 `/pages/preview/{chunk_id}` 链接。
5. 请求原文预览页并写出 JSON 结果。

核心参数：

- `--question`
- `--json-output`
- `--embedding-provider`: 默认 `openai`
- `--embedding-model`: 默认 `kimi-for-coding`
- `--embedding-dimension`: 默认 `1024`
- `--api-key-env`: 默认 `KIMI_API_KEY`
- `--embedding-base-url`: 默认 `https://api.kimi.com/coding/v1`
- `--embedding-batch-size`: 默认 `16`

退出码：

- `0`：PostgreSQL 状态、后端加载、查询页和预览页全部通过。
- `2`：任一门禁失败。当前常见原因是 `KIMI_API_KEY` 未设置。

### `scripts/capture-chat-workbench-visual-baseline.py`

在已启动且检索后端 ready 的本地服务上捕获 `/pages/chat` 桌面与移动视觉基线。该脚本不接收 API key，也不加载后端，只读取 `/index/search-backend` 状态、访问对话审证页、截图并检查关键文案和横向溢出。

示例：

```bash
uv run python scripts/capture-chat-workbench-visual-baseline.py \
  --base-url http://127.0.0.1:8021 \
  --report tmp/outputs/knowledge-query-chat-visual-baseline-latest.json
```

默认输出：

- `tmp/screenshots/knowledge-query-chat-visual-baseline-desktop.png`
- `tmp/screenshots/knowledge-query-chat-visual-baseline-mobile.png`
- `tmp/outputs/knowledge-query-chat-visual-baseline-latest.json`

退出码：

- `0`：后端 ready、桌面/移动关键文案存在、无横向溢出。
- `2`：后端未 ready、关键文案缺失或出现横向溢出。

### `medical-audit-kb evaluate-answers`

加载本地持久化索引并运行答案级评测，验证引用标记、关键术语覆盖、拒答准确率和无依据结论控制。

核心参数：

- `--index-root`
- `--cases-file`: 答案级评测集 YAML/JSON
- `--output`
- `--json-output`
- `--max-cases`
- `--top-k`
- `--embedding-provider`: `fake | openai`
- `--embedding-model`
- `--embedding-dimension`
- `--api-key-env`
- `--embedding-base-url`
- `--embedding-batch-size`
- `--answer-provider`: `fallback | openai | anthropic`
- `--answer-model`
- `--answer-api-key-env`
- `--answer-base-url`
- `--answer-max-output-tokens`
- `--answer-temperature`
- `--allow-answer-fallback`: 显式允许真实生成 provider 失败后仍按 fallback 结果通过答案质量评测

说明：

- 固定答案级评测集当前路径：`configs/evaluation/knowledge-query-answer-evaluation-cases-v1.yaml`，当前为 `8` 条 review case。
- 当前 Kimi 全量索引 fallback 答案级评测结果：`pass_rate=100%`，`citation_marker_rate=100%`，`answer_term_coverage_rate=100%`，`citation_term_coverage_rate=100%`，`refusal_accuracy_rate=100%`，`unsupported_claim_free_rate=100%`。
- 当前 Kimi Code 真实生成评测结果：`pass_rate=25%`，`generation_success_rate=0%`，`fallback_rate=100%`；6 个应回答 case 均因 `403 access_terminated_error` 进入 `generation_provider_failed`，2 个拒答 case 通过。
- 当前答案构造使用问题焦点词筛选引用，优先聚焦 `A00.0`、`0000` 等领域编码，避免把相邻目录项误带入答案。

### `medical-audit-kb answer-provider-smoke`

在运行完整答案级评测前，对 OpenAI-compatible chat provider 执行单条引用预检。

核心参数：

- `--output`
- `--json-output`
- `--answer-provider`: `openai | anthropic`
- `--answer-model`
- `--answer-api-key-env`
- `--answer-base-url`
- `--answer-max-output-tokens`
- `--answer-temperature`

退出码：

- `0`：provider 请求成功，且回答包含 `[C1]` 引用标记和关键术语。
- `2`：provider 请求失败，或回答未满足引用门禁。

当前 provider 预检结果：

- Kimi Code：`FAIL`，错误为 `403 access_terminated_error`。
- Anthropic：`FAIL`，当前环境变量存在但返回 `401 authentication_error: invalid x-api-key`。

后续更换 chat model 或 key 时，必须先跑该命令，再跑 `evaluate-answers`。

### `medical-audit-kb pgvector-import-plan`

读取本地持久化索引 artifact，执行 PostgreSQL + pgvector 导入前校验，不连接数据库、不写入数据。

核心参数：

- `--index-root`
- `--output`
- `--json-output`
- `--schema-dimension`: 当前 Kimi 主索引使用 `1024`

校验内容：

- `summary.json`、`chunks.jsonl`、`embeddings.jsonl`、`failed_files.jsonl`、`pending_files.jsonl` 必须存在。
- `summary.embedding_dimension` 必须匹配 `--schema-dimension`。
- `chunks.jsonl`、`embeddings.jsonl`、失败队列、待处理队列行数必须匹配 `summary.json`。
- `chunk_id` 不允许重复。
- 每个 chunk 必须存在且仅存在一条 embedding。
- embedding provider、model、provider version、dimension 必须与 `summary.json` 一致。
- 每条 embedding 向量长度必须等于 `summary.embedding_dimension`。

退出码：

- `0`：所有导入前门禁通过。
- `2`：至少一个门禁失败，不允许进入 PostgreSQL 写入。

当前 Kimi 主索引导入前校验结果：

- 报告：`drafts/analysis/knowledge-query-pgvector-import-plan-kimi-draft-20260601.md`
- JSON：`tmp/outputs/knowledge-query-pgvector-import-plan-kimi-20260601.json`
- `ready_for_import`: `true`
- `chunks.jsonl`: `48985`
- `embeddings.jsonl`: `48985`
- `failed_files.jsonl`: `0`
- `pending_files.jsonl`: `13`

### `medical-audit-kb pgvector-import`

从本地持久化索引 artifact 构建 PostgreSQL + pgvector 写入批次。默认只执行 dry-run，不连接数据库、不写入数据；只有显式传入 `--execute` 才写入 PostgreSQL。执行写入时默认把 `index_versions.status` 写为 `candidate`，不直接污染当前 active 检索版本。

核心参数：

- `--index-root`
- `--source-root`: 原始资料根目录，用于计算 `source_documents.sha256` 和 `size_bytes`
- `--output`
- `--json-output`
- `--schema-dimension`: 当前 Kimi 主索引使用 `1024`
- `--batch-size`
- `--database-url-env`: 默认 `MEDICAL_AUDIT_KB_DATABASE_URL`
- `--index-version-status`: `candidate | active`，默认 `candidate`
- `--execute`: 显式执行数据库写入；不传该参数时为 dry-run

写入策略：

- 使用确定性 UUID 写入 `source_package_versions`、`source_documents`、`document_chunks`、`index_versions`、`index_jobs` 和队列表。
- `document_chunks.id` 保留 JSONL artifact 中的 `chunk_id`，保证引用和 embedding 外键可追溯。
- `chunk_embeddings.embedding` 以 `%s::vector` 写入，要求当前 schema 已初始化 `vector(1024)`。
- 写入使用 `ON CONFLICT`，重复执行同一资料包导入应更新而不是重复插入。
- 新导入默认状态为 `candidate`。candidate 版本必须通过评测后，再用 `medical-audit-kb index-activate` 切换为 active。
- 生产发布新 candidate 前必须执行 `scripts/audit-index-candidate-release-readiness.py`；若 `index_version_key` 已存在或等于 active，禁止执行写入。
- 新生成 artifact 的 `chunk_id` 必须绑定 `source_package_version_key`；旧 artifact 若在不同 `source_package_version_key` 下复用 active chunk id，发布门禁必须阻断。
- 只有明确执行历史修复或一次性初始化时，才允许使用 `--index-version-status active`。

当前 Kimi 主索引 dry-run 结果：

- 报告：`drafts/analysis/knowledge-query-pgvector-import-dry-run-kimi-draft-20260601.md`
- JSON：`tmp/outputs/knowledge-query-pgvector-import-dry-run-kimi-20260601.json`
- `mode`: `dry-run`
- `executed`: `false`
- `ready_for_write`: `true`
- `source_document_count`: `486`
- `document_chunk_count`: `48985`
- `chunk_embedding_count`: `48985`
- `failed_file_count`: `0`
- `pending_file_count`: `13`
- `source_file_missing_count`: `0`
- `invalid_source_metadata_count`: `0`

历史 Kimi 主索引执行结果：

- 报告：`drafts/analysis/knowledge-query-pgvector-import-execute-kimi-draft-20260601.md`
- JSON：`tmp/outputs/knowledge-query-pgvector-import-execute-kimi-20260601.json`
- `mode`: `execute`
- `executed`: `true`
- `success`: `true`
- `source_documents`: `486`
- `document_chunks`: `48985`
- `chunk_embeddings`: `48985`
- `failed_files`: `0`
- `pending_files`: `13`
- `orphan_embedding_count`: `0`
- `missing_embedding_count`: `0`
- `invalid_dimension_count`: `0`

说明：该历史导入发生在 candidate/activate 流程落地之前；后续生产 active 版本已由 2026-06-15 国家规章平台稳定增量版本替换。后续新资料包导入必须先写 candidate。

### `medical-audit-kb index-activate`

将一个候选 index version 原子切换为 active。该命令会把同 `vector_provider` + `vector_model` 下旧 active version 置为 `inactive`，再把目标版本置为 `active`。

核心参数：

- `--index-version-key`
- `--database-url-env`: 默认 `MEDICAL_AUDIT_KB_DATABASE_URL`
- `--output`
- `--json-output`

行为约束：

- 目标版本必须存在，且当前状态必须为 `candidate` 或 `active`。
- 同一 provider/model 下只允许一个 active 版本。
- 激活命令会写数据库，执行前必须已经完成导入校验、检索评测、答案评测和 UI smoke。
- 激活后必须重新加载 API 进程内 PostgreSQL 检索后端，否则运行中服务仍可能持有旧 BM25 内存索引。

当前验证结果：

- 已在真实 PostgreSQL 上对当前 active 版本执行事务内 rollback 验证，SQL 可执行且未落库变更。

### `medical-audit-kb index-rollback`

将一个历史 index version 恢复为 active。该命令会把同 `vector_provider` + `vector_model` 下当前 active version 置为 `inactive`，再把目标版本置为 `active`。

核心参数：

- `--index-version-key`
- `--database-url-env`: 默认 `MEDICAL_AUDIT_KB_DATABASE_URL`
- `--output`
- `--json-output`

行为约束：

- 目标版本必须存在，且当前状态必须为 `inactive` 或 `active`。
- `candidate` 不能作为 rollback 目标；candidate 必须先完成发布门禁，再通过 `index-activate` 激活。
- 同一 provider/model 下只允许一个 active 版本。
- 回滚命令会写数据库，执行前必须确认目标版本曾通过历史验收，且回滚后必须重新加载 API 进程内 PostgreSQL 检索后端。

输出：

- Markdown：知识库索引版本回滚报告。
- JSON：`success`、`index_version_key`、`previous_status`、`deactivated_index_version_keys`。

当前验证结果：

- 已在真实 PostgreSQL 上对当前 active 版本执行事务内 rollback 验证，SQL 可执行且未落库变更。
