---
title: 前后端分离路由与数据流盘点
doc_type: route_inventory
module: frontend-backend-separation
status: draft
created: 2026-07-02
updated: 2026-07-02
owner: codex
source: static-source-inventory
evidence_level: local-readonly
---

# 前后端分离路由与数据流盘点

## 事实

- backend 入口是 FastAPI，核心文件为 `src/medical_audit_kb/api/app.py`。
- frontend 入口是 Next.js，核心目录为 `web/src/app/`。
- 当前前端 API client 在 `web/src/lib/api-client.ts`，显式要求 browser/client runtime；server code 不能直接调用相对路径 backend proxy。
- 当前前端类型主要集中在 `web/src/lib/api-types.ts`，静态/模拟产品数据仍集中在 `web/src/lib/portal-data.ts`。
- 后端仍存在 legacy Jinja 页面：`src/medical_audit_kb/api/routes_pages.py` 和 `src/medical_audit_kb/api/templates/`。

## Backend API Families

当前 FastAPI route 文件按能力可分为：

- `routes_auth.py`: `/auth/roles`, `/auth/session`, `/auth/users`, user role assignments。
- `routes_query.py`: `/query`, `/query/logs`, `/operation/logs`, `/audit-findings`, `/audit/logs`。
- `routes_index.py`: `/index/rebuild`, `/index/versions`, `/index/search-backend`, `/index/postgres-status`, evaluation endpoints。
- `routes_documents.py`: `/documents/permissions`, `/documents/governance/status`, `/documents/uploads`, upload governance, indexing, download。
- `routes_agents.py`: `/agents`, prompt versions, lifecycle, invocations, feedback。
- `routes_projects.py`: `/projects`, `/projects/{project_key}/members`。
- `routes_analytics.py`: `/analytics/table-upload`, `/analytics/table-uploads`。
- `routes_workbench.py`: `/graph/workbench`, `/rules/workbench`, `/remediation/workbench`, `/archive/workbench`。
- `routes_preview.py`: `/preview/{chunk_id}`。
- `routes_pages.py`: legacy HTML pages and review-task/report mutation endpoints.

## Frontend Routes

当前 Next 页面包括：

- `/`: `web/src/app/page.tsx`
- `/login`: `web/src/app/login/page.tsx`
- workspace shell: `web/src/app/(workspace)/layout.tsx`
- `/workspace`, `/projects`, `/agents`, `/agent-market`
- `/analytics`, `/documents`, `/knowledge-base`, `/knowledge-query`
- `/findings`, `/fund-compliance`, `/fund-compliance/review`
- `/guided-check`, `/reports`, `/remediation`, `/rules`, `/graph`, `/archive`, `/chat`

## Frontend API Dependencies

当前 `web/src/lib/api-client.ts` 已覆盖：

- backend health: `/api/backend/health`
- search backend: `/api/backend/index/search-backend`
- auth session: `/api/v1/auth/session`
- query: `/api/v1/query`, `/api/v1/query/logs`
- findings: `/api/v1/audit-findings`
- workbench: `/api/v1/reports|graph|rules|remediation|archive/workbench`
- analytics: `/api/v1/analytics/table-upload`, `/api/v1/analytics/table-uploads`
- documents: `/api/v1/documents/permissions`, `/api/v1/documents/uploads`, governance, index
- agents: `/api/v1/agents`, prompt versions, lifecycle, invocations, feedback
- projects: `/api/v1/projects`, project members

主要调用方：

- `web/src/components/query/knowledge-query-workbench.tsx`
- `web/src/components/findings/audit-findings-workbench.tsx`
- `web/src/components/portal/data-analysis-workbench.tsx`
- `web/src/components/portal/project-management-workbench.tsx`
- `web/src/components/portal/agent-workspace.tsx`
- `web/src/components/shell/project-context-bar.tsx`
- workspace pages under `web/src/app/(workspace)/`

## 推断

- 前后端分离的第一阻断点不是“没有 API”，而是 API contract、运行时边界和 legacy Jinja 页面责任没有被明确拆开。
- `api-client.ts` 当前适合 client component 调用；如果新前端使用 server component 或 static export，需要增加 server-safe adapter 或显式禁止 server-side data fetch。
- `portal-data.ts` 中的 `AuditTableTemplate` 与产品侧模板合同有关，应优先纳入新前端信息架构，而不是被当作普通 mock 数据清掉。

## 不确定项

- `routes_pages.py` 中哪些 POST mutation 仍被生产或旧页面使用，尚未逐端点验证。
- Next rewrite/proxy 的最终部署边界尚未在本轮验证。
- 本轮没有运行本地服务、E2E、production readonly smoke，也没有验证生产路径。

## 下一步

- 生成 API contract gap 表：每个 Next 页面绑定需要的 API endpoint、响应类型、mock fallback、错误态、权限头。
- 将 `routes_pages.py` 页面渲染能力标记为 legacy，单独评估 review-task/report mutation 是否迁移到 `/api/v1`。
- 给 `api-client.ts` 拆出 browser-client adapter、server-safe adapter、static-export fallback 三类边界。
