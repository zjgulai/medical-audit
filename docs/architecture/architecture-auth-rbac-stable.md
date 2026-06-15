---
title: AI智能审计管理系统真实权限模型与 RBAC 架构
doc_type: architecture
module: security
topic: auth-rbac
status: stable
created: 2026-06-15
updated: 2026-06-15
owner: self
source: human+ai
---

# AI智能审计管理系统真实权限模型与 RBAC 架构

## 1. 目标

本架构用于替代当前以 `X-Role`、`X-User-Id` 为主的临时权限口径，建立单院私有化部署场景下可审计、可验收、可迁移的真实用户、部门、角色、权限和会话模型。

本架构解决四个问题：

- 用户身份必须由服务端可信会话或认证代理确认，不能由浏览器任意传入。
- 角色必须绑定到真实用户、部门和项目范围，不能只靠字符串判断。
- 写接口必须统一通过权限策略校验，不能散落在各路由函数中。
- 所有授权成功、拒绝、导出、配置变更和敏感读取都必须进入持久化审计日志。

## 2. 当前事实边界

当前系统已有以下权限相关能力：

- `audit_log_events` 已作为持久化审计日志表，`record_operation` 可同步写入数据库日志 store。
- `/audit/logs` 与 `/audit/logs/export` 已限制为 `it-admin` 和 `department-head` 可读，并记录拒绝访问。
- 索引管理写接口已限制 `it-admin`，非授权访问记录 `index-admin-access-denied`。
- 门户配置写接口已对未知角色记录 `agent-access-denied` 和 `project-member-access-denied`。
- 文档上传列表已按 `X-User-Id` 做个人材料读取隔离，`it-admin` 和 `department-head` 可读全部个人上传。

当前不能声明为真实权限系统：

- 前端 `web/src/lib/api-client.ts` 仍硬编码 `X-Role: auditor` 和 `X-User-Id: next-knowledge-query`。
- 后端仍允许客户端直接传入 `X-Role` 与 `X-User-Id`。
- 没有用户、部门、角色、角色绑定、权限项、会话、登录失效、账号禁用和密码或外部身份源校验。
- 权限校验散落在 `role_policy.py`、`document_permissions.py`、`routes_index.py`、`routes_query.py` 等局部模块中。

## 3. 角色模型

V1.0 采用单院 RBAC，不做多院多租户。角色是授权单元，部门和项目是权限范围。

| 角色键 | 产品角色 | 主要权限边界 |
| --- | --- | --- |
| `auditor` | 一线审计员 | 查询知识库、创建复核任务、复核疑点、上传和读取本人材料、创建本人提示词型智能体 |
| `department-head` | 审计科主任/负责人 | 审核确认、查看本科室审计材料、导出正式报告、查看和导出审计日志、确认整改闭环 |
| `info-staff` | 医院信息科 | 查看运行状态、协助 HIS 数据接入、查看数据导入状态、不能确认审计结论 |
| `business-expert` | 业务/审计专家 | 查看规则、评测集、知识依据和模板；可提交规则口径意见，不能发布索引或管理用户 |
| `system-admin` | 系统管理员 | 用户、角色、部门、索引发布、回滚、系统配置、运行状态和审计日志治理 |

历史 `it-admin` 作为兼容角色键，迁移后映射到 `system-admin`。兼容期内 API 可接受 `it-admin`，但审计日志中必须同时记录 `normalized_role=system-admin`。

## 4. 权限矩阵

权限项采用 `resource:action` 格式，代码实现时集中注册，不在路由内临时拼字符串。

| 资源 | 操作 | auditor | department-head | info-staff | business-expert | system-admin |
| --- | --- | --- | --- | --- | --- | --- |
| knowledge-query | query | allow | allow | allow | allow | allow |
| review-task | create | allow | allow | deny | allow | allow |
| review-task | update-own | allow | allow | deny | allow | allow |
| review-task | close | deny | allow | deny | deny | allow |
| audit-finding | read | allow | allow | deny | allow | allow |
| audit-finding | confirm | deny | allow | allow-review-only | allow-review-only | allow |
| report | export-draft | allow | allow | deny | deny | allow |
| report | sign-off | deny | allow | deny | deny | allow |
| rectification | accept | deny | allow | deny | deny | allow |
| document-upload | create-personal | allow | allow | allow-data-material | allow-reference-material | allow |
| document-upload | read-own | allow | allow | allow | allow | allow |
| document-upload | read-all | deny | allow | deny | deny | allow |
| analytics-upload | create | allow | allow | allow-data-material | allow-reference-material | allow |
| agent | create-own | allow | allow | deny | allow | allow |
| agent | manage-all | deny | allow | deny | deny | allow |
| project-member | read | allow | allow | allow | allow | allow |
| project-member | create | deny | allow | deny | deny | allow |
| index | rebuild | deny | deny | deny | deny | allow |
| index | activate | deny | deny | deny | deny | allow |
| audit-log | read | deny | allow | deny | deny | allow |
| audit-log | export | deny | allow | deny | deny | allow |
| auth-user | manage | deny | deny | deny | deny | allow |

`allow-review-only` 表示可提交专家意见，但不能直接改变审计结论状态。

## 5. 数据模型

第一批 schema 只覆盖单院身份和授权，不引入 OAuth、多租户或复杂 ABAC。

| 表 | 用途 | 关键字段 |
| --- | --- | --- |
| `auth_departments` | 医院内部部门 | `department_key`、`name`、`department_type`、`status`、`metadata` |
| `auth_users` | 系统用户 | `user_key`、`login_name`、`display_name`、`department_id`、`status`、`password_hash` 或 `external_subject`、`metadata` |
| `auth_roles` | 系统角色字典 | `role_key`、`name`、`description`、`status` |
| `auth_user_roles` | 用户角色绑定 | `user_id`、`role_id`、`scope_type`、`scope_key`、`granted_by`、`status` |
| `auth_sessions` | 服务端会话 | `session_id_hash`、`user_id`、`issued_at`、`expires_at`、`revoked_at`、`last_seen_at`、`metadata` |
| `auth_permission_events` | 权限变更审计 | `event_type`、`target_user_id`、`actor_user_id`、`role_key`、`scope_type`、`scope_key`、`reason` |

约束：

- `auth_users.login_name` 必须唯一。
- `auth_roles.role_key` 必须唯一。
- 禁用用户不能创建新会话。
- `auth_user_roles` 中同一用户、同一角色、同一范围只能有一条 active 绑定。
- 会话只保存 hash，不保存明文 token。
- 所有权限变更同时写入 `auth_permission_events` 和 `audit_log_events`。

## 6. 会话与认证

V1.0 支持两种部署形态，默认采用服务端会话：

| 模式 | 适用场景 | 要求 |
| --- | --- | --- |
| 服务端登录会话 | 单院私有化默认 | 后端签发 HttpOnly、Secure、SameSite=Lax cookie；会话落表；退出和禁用账号立即失效 |
| 认证代理注入 | 接入院内统一认证 | Nginx 或上游代理验证身份后注入内部可信 header；FastAPI 只信任来自内网代理的签名 header |

禁止：

- 浏览器直接构造 `X-Role` 作为正式权限依据。
- 前端存储可修改的角色或权限列表。
- 未经签名的代理 header 直接进入生产授权判断。

## 7. 后端迁移策略

迁移按四步执行，避免一次性替换导致生产不可用。

### 7.1 Phase A：权限上下文兼容层

新增 `CurrentUser` 和 `PermissionContext`：

- `user_key`
- `display_name`
- `department_key`
- `roles`
- `permissions`
- `auth_source`
- `session_id`

在兼容期内，`CurrentUser` 可从现有 `X-Role`、`X-User-Id` 构造，但必须记录 `auth_source=legacy-header`，并在审计日志 payload 中显式保留。

验收：

- 所有使用 `X-Role` 的路由改为依赖 `get_current_user()`。
- 既有生产 smoke 不回归。
- 审计日志能区分 `legacy-header` 与真实会话。

### 7.2 Phase B：schema 与种子数据

新增 auth schema 和默认种子：

- 默认部门：`audit-office`、`information-office`、`business-expert-group`。
- 默认角色：`auditor`、`department-head`、`info-staff`、`business-expert`、`system-admin`。
- 初始化一个禁用状态的占位管理员，生产启用必须走显式初始化命令。

验收：

- migration 可重复执行。
- `auth_roles` 和 `auth_departments` 种子幂等。
- 未初始化管理员时，生产不能开放用户管理页面。

### 7.3 Phase C：真实登录与会话

新增登录、退出、当前用户 API：

- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`
- `POST /auth/sessions/revoke`

前端 API client 停止硬编码 `X-Role` 和 `X-User-Id`，改为依赖 cookie 会话。

验收：

- 未登录访问写接口返回 `401`。
- 登录后按角色访问。
- 禁用用户和撤销会话立即失效。
- CSRF 风险被明确处理；写接口至少要求同源 cookie 与 CSRF token 或认证代理保护。

### 7.4 Phase D：关闭 legacy header 授权

生产关闭客户端 `X-Role` 兼容模式，只保留测试环境和认证代理签名 header。

验收：

- 浏览器伪造 `X-Role: system-admin` 不能获得管理权限。
- 生产专项 E2E 覆盖未登录、低权限、跨部门和管理员路径。
- `audit_log_events` 能记录所有拒绝路径的用户、角色、权限项、endpoint 和原因。

## 8. API 权限收敛

新增统一授权函数：

```text
require_permission(current_user, permission, resource_scope)
```

路由不再直接判断字符串角色。权限拒绝统一记录：

- `action`: `permission-access-denied`
- `user_identifier`
- `roles`
- `permission`
- `resource_type`
- `resource_id`
- `endpoint`
- `status_code=403`
- `reason`
- `auth_source`

历史专用 action 如 `index-admin-access-denied`、`agent-access-denied`、`project-member-access-denied` 可保留为业务语义事件，但底层必须同时具备统一权限拒绝事件或统一 payload 字段。

## 9. 前端迁移策略

前端分三步改造：

1. 新增 `fetchCurrentUser()` 和全局 `AuthContext`。
2. API client 移除硬编码 `X-Role`、`X-User-Id`。
3. 导航和按钮根据 `permissions` 控制可见性，但后端仍作为唯一授权来源。

前端禁止把按钮隐藏当作权限控制完成。所有写接口必须以后端权限检查为准。

## 10. 验收门禁

真实权限系统进入生产前，必须通过以下门禁：

- 单元测试：角色归一化、权限矩阵、会话失效、账号禁用、跨部门读取。
- API E2E：未登录 `401`、低权限 `403`、授权用户 `200`、伪造 header 无效。
- 前端 E2E：登录态、退出、权限按钮显示、直接访问受限页面。
- 生产 smoke：基础 smoke、前端验收、权限专项 smoke、审计日志查询。
- 文档同步：API 文档、PRD、部署工作流和债务台账同步真实状态。

## 11. 非目标

V1.0 首期不做：

- 多院多租户。
- 复杂 ABAC 规则引擎。
- 外部 OAuth/OIDC 强依赖。
- 手机短信、扫码、人脸识别。
- 患者级行权限表达式引擎。

以上能力如需进入后续版本，必须先完成单院 RBAC 基线。
