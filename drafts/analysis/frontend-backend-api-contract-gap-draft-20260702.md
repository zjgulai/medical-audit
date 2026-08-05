---
title: 前后端分离 API Contract Gap 盘点
doc_type: contract_gap
module: frontend-backend-separation
status: draft
created: 2026-07-02
updated: 2026-07-03
owner: codex
source: api-client-routes-static-inventory
evidence_level: local-readonly-plus-docs-only-edit
---

# 前后端分离 API Contract Gap 盘点

## 本轮事实

- `web/src/lib/api-client.ts` 是当前前端真实 backend 调用集中入口。
- `api-client.ts` 通过 `assertBackendProxyClientRuntime()` 明确禁止 server runtime 调用。
- `web/next.config.ts` 在非 static export 模式下把 `/api/backend/:path*` 与 `/api/v1/:path*` rewrite 到 `MEDICAL_AUDIT_API_BASE_URL`。
- FastAPI 在 `src/medical_audit_kb/api/app.py` 中对同一组 router 同时挂载裸路径、`/api/v1` 和 `/api/backend`。
- `routes_pages.py` 仍提供 Jinja 页面与 review-task/report/rectification 相关 mutation endpoint。
- 本地 in-memory/test `ApiState` OpenAPI 枚举结果：`openapi_path_count=237`，已核对前端 contract path `27` 个，`missing_count=0`。
- 同一 OpenAPI 枚举中，legacy Jinja / review-task 相关 path 为 `19` 个；这是 legacy 迁移线的第一批边界。
- `scripts/audit-frontend-backend-api-contract-schema.py` 已对 33 个前端 API contract 做 top-level schema diff：`aligned_count=7`，`field_mismatch_count=3`，`schema_gap_count=23`，`missing_response_schema_count=25`。
- `web/src/lib/api-endpoints.ts` 已集中当前 browser API client endpoint；本轮保持路径语义不变，尚未执行 `/api/backend` 到 `/api/v1` 的 prefix 收敛。
- `web/src/lib/api-client.server.ts` 已建立 server-safe absolute URL 基础 adapter；`web/src/lib/api-client.static.ts` 已建立 static export fail-closed adapter。

## Contract Gap Matrix

| Surface | Frontend function | Endpoint | Backend source | Type source | Current status | Next action |
| --- | --- | --- | --- | --- | --- | --- |
| Dashboard status | `fetchBackendHealth` | `/api/backend/health` | `app.py` | `BackendHealthResponse` | covered via proxy | 决定是否保留 `/api/backend` 作为 health-only 兼容入口 |
| Search status | `fetchSearchBackendStatus` | `/api/backend/index/search-backend` | `routes_index.py` | `SearchBackendStatusResponse` | covered but prefix mixed | 新前端优先改用 `/api/v1/index/search-backend` 或明确例外 |
| User/session shell | `fetchAuthSession` | `/api/v1/auth/session` | `routes_auth.py` | `AuthSessionResponse` | covered, browser-only | 增加 server-safe session contract 或保持 client shell fetch |
| Knowledge query | `runKnowledgeQuery` | `/api/v1/query` | `routes_query.py` | `QueryRequest`, `QueryResponse` | covered, product-critical | 补错误态、引用来源、provider-call boundary 文档 |
| Query history | `fetchQueryHistory` | `/api/v1/query/logs?limit=8` | `routes_query.py` | `QueryHistoryResponse` | covered with hardcoded limit | 把 limit 参数纳入 typed request |
| Findings | `fetchAuditFindings` | `/api/v1/audit-findings` | `routes_query.py` | `AuditFindingsResponse` | covered | 明确 review_status 枚举与空态 |
| Reports | `fetchReportWorkbench` | `/api/v1/reports/workbench` | `routes_pages.py` | `ReportWorkbenchResponse` | covered but legacy file-owned | 迁出到 dedicated API route 或标记为 compatibility API |
| Graph | `fetchGraphWorkbench` | `/api/v1/graph/workbench` | `routes_workbench.py` | `GraphWorkbenchResponse` | covered | 保持 readonly contract，补 schema snapshot |
| Rules | `fetchRulesWorkbench` | `/api/v1/rules/workbench` | `routes_workbench.py` | `RulesWorkbenchResponse` | covered | 保持 readonly contract，补 schema snapshot |
| Remediation | `fetchRemediationWorkbench` | `/api/v1/remediation/workbench` | `routes_workbench.py` | `RemediationWorkbenchResponse` | covered | 明确整改状态枚举与后续 mutation lane |
| Archive | `fetchArchiveWorkbench` | `/api/v1/archive/workbench` | `routes_workbench.py` | `ArchiveWorkbenchResponse` | covered | 明确归档包下载/签名是否仍是 legacy |
| Analytics upload | `uploadAnalysisTable` | `/api/v1/analytics/table-upload` | `routes_analytics.py` | `TableAnalysisUploadResponse` | covered, multipart | 补文件大小、类型、失败 payload contract |
| Analytics history | `fetchAnalysisUploadHistory` | `/api/v1/analytics/table-uploads` | `routes_analytics.py` | `TableAnalysisUploadHistoryResponse` | covered | 增加分页或 limit contract |
| Document permissions | `fetchDocumentPermissions` | `/api/v1/documents/permissions` | `routes_documents.py` | `DocumentPermissionsResponse` | covered | 明确权限头与只读/写入边界 |
| Document uploads | `fetchDocumentUploads` | `/api/v1/documents/uploads` | `routes_documents.py` | `DocumentUploadListResponse` | covered | 增加分页、过滤、治理状态枚举 |
| Document upload | `uploadPersonalDocument` | `/api/v1/documents/uploads` | `routes_documents.py` | `DocumentUploadResponse` | covered, multipart | 补文件约束、重复上传、权限失败 contract |
| Document governance | `updateDocumentUploadGovernance` | `/api/v1/documents/uploads/{uploadId}/governance` | `routes_documents.py` | `DocumentUploadGovernanceRequest`, `DocumentUploadResponse` | covered, mutation | 明确 manual review 与 production write boundary |
| Document indexing | `indexPersonalDocument` | `/api/v1/documents/uploads/{uploadId}/index` | `routes_documents.py` | `DocumentUploadResponse` | covered, mutation | 明确 indexing side effect 与 provider_call=false 条件 |
| Agents list | `fetchAgents` | `/api/v1/agents` | `routes_agents.py` | `AgentsResponse` | covered | 明确权限头、分类枚举、空态 |
| Agent detail | `fetchAuditAgent` | `/api/v1/agents/{agentId}` | `routes_agents.py` | `AgentDetailResponse` | covered | 统一 frontend `agentId` 与 backend `agent_key` 命名 |
| Agent create | `createAuditAgent` | `/api/v1/agents` | `routes_agents.py` | `AgentCreateRequest`, `AgentCreateResponse` | covered, mutation | 明确 prompt 审核、敏感字段、权限失败 |
| Agent prompt versions | prompt version functions | `/api/v1/agents/{agentId}/prompt-versions*` | `routes_agents.py` | prompt version request/response types | covered, mutation | 明确 review/rollback/activation 状态机 |
| Agent lifecycle | `updateAuditAgentLifecycle` | `/api/v1/agents/{agentId}/lifecycle` | `routes_agents.py` | `AgentLifecycleRequest`, `AgentCreateResponse` | covered, mutation | 明确 soft archive 与不可物理删除边界 |
| Agent invocation | invocation functions | `/api/v1/agents/{agentId}/invocations` | `routes_agents.py` | invocation request/response types | covered, mutation | 明确是否会触发 provider call；默认不声明 provider call |
| Agent feedback | feedback functions | `/api/v1/agents/{agentId}/feedback` | `routes_agents.py` | feedback request/response types | covered, mutation | 明确 rating 枚举与审计日志 |
| Projects | `fetchProjects` | `/api/v1/projects` | `routes_projects.py` | `ProjectsResponse` | covered | 明确项目状态枚举、默认项目选择 |
| Project members | member functions | `/api/v1/projects/{projectId}/members` | `routes_projects.py` | member request/response types | covered, naming mismatch | 统一 `projectId` 与 backend `project_key` 命名 |
| Legacy review tasks | none in Next client | `/pages/review-tasks*`, `/review-tasks/*` | `routes_pages.py` | not centralized in `api-types.ts` | legacy-migration | 设计 `/api/v1/review-tasks` contract 后再迁移 UI |
| Legacy report signoff | none in Next client | `/pages/review-tasks/{task_id}/report-signoff` | `routes_pages.py` | not centralized in `api-types.ts` | legacy-migration | 迁移为 report workflow mutation API |
| Legacy rectification | none in Next client | `/pages/review-tasks/{task_id}/rectification` | `routes_pages.py` | not centralized in `api-types.ts` | legacy-migration | 迁移为 remediation mutation API |
| Product templates | static imports | no backend endpoint | `portal-data.ts` | `AuditTableTemplate` | static-data gap | 决定模板是前端 fixture、后端 config，还是 API-backed catalog |

## Cross-cutting Gaps

- Runtime gap: 当前 `api-client.ts` 只能在 browser/client runtime 调用，server component 需要 absolute URL adapter。
- Prefix gap: 现有代码同时使用 `/api/backend` 与 `/api/v1`，新前端应收敛到 `/api/v1`，把 `/api/backend` 留作兼容或 health lane。
- Schema gap: `api-types.ts` 是手写 TypeScript 类型；本轮已完成 top-level 自动比对，结果显示 23 个 schema gap 和 3 个字段差异，深层嵌套字段仍未覆盖。
- Error gap: 当前 client 只抛出 `Backend request failed`，缺少 typed error payload、用户可见错误分类和权限失败语义。
- Mutation boundary gap: document indexing、agent invocation、review/signoff/rectification 等动作需要明确 side effect 层级。
- Static export gap: `MEDICAL_AUDIT_NEXT_EXPORT=1` 时 rewrites 被禁用，动态 API 页面必须有明确 fallback 或构建期禁用策略。

## P3 多 active 知识库契约补充

当前后端事实：

- `/api/v1/query` 请求已支持 `source_collections`、`years`、`regions`、`document_types`、`business_topics`、`topic`、`title_only`、`agent`。
- 未传 `source_collections` 时，后端按角色权限计算 `effective_source_collections`，因此三库同时 active 后默认检索会覆盖角色允许的多个二级库。
- `/api/v1/query` 响应已返回 `basis_groups` 与 `citations`，每条 evidence 都包含 `source_collection`、`locator`、`index_version_key`、`source_package_version_key`。
- 三库 active 后端链路已通过固定专家评测：`configs/evaluation/knowledge-query-medical-three-libraries-active-expert-cases-v1.yaml`，`24` cases recall/citation/preview 均为 `100%`。

当前前端事实：

- `web/src/lib/api-types.ts` 的 `QueryResponse` 已承接 `basis_groups`、`citations`、`index_version_key`、`source_package_version_key`。
- `web/src/lib/api-types.ts` 的 `QueryRequest` 已补齐后端支持的 `years`、`regions`、`document_types`、`business_topics`。
- `web/src/components/query/knowledge-query-workbench.tsx` 已提供 source collection 多选、年份、地区、文档类型、业务主题过滤输入，并继续固定发送 `topic: "medical-insurance-fund"`。
- `CitationRow` 已展示 `source_collection`、locator、chunk id、`index_version_key` 和 `source_package_version_key`，满足多 active 版本追溯的基本展示。

P3-API-CONTRACT 结论：

- 事实：后端多 active 检索能力已具备，前端基础类型对 citation/index metadata 已部分承接。
- 推断：前端重写时不需要新增后端查询 endpoint；应优先完善 `QueryRequest` 类型、查询过滤 UI、citation 版本显示和 typed error。
- `effective_source_collections` 已显式加入 `/query` response，前端查询工作台已展示“实际检索范围”。

P3-API-CONTRACT TODO：

- [x] `QueryRequest` 前端类型补齐 `years`、`regions`、`document_types`、`business_topics`，并补单元测试。
- [x] 知识查询 UI 增加“实际检索范围”展示；后端 `/query` response 增加 `effective_source_collections`。
- [x] `CitationRow` 展示 `index_version_key` 与 `source_package_version_key`，用于多 active 版本追溯。
- [x] 查询失败改为 typed query state：`409 search engine not initialized`、`404 no cited evidence found`、`400 unknown topic`、`403 source collection denied`。
- [x] source collection 默认策略在前端文案中明确：不勾选时为角色允许范围，不等同于“未过滤单库”。
- [ ] 在前端重写任务中保留三库 fixed expert eval 作为后端回归门槛，不用 UI 截图或 mock 结果替代。

P3-FRONTEND-TYPES 验证：

- `npm test -- knowledge-query-workbench.test.tsx api-client.test.ts`
- 结果：`2 passed` test files，`33 passed` tests。

## 下一步 Todo

- [x] 读取 FastAPI OpenAPI schema，确认当前前端 contract path 在 schema 中均存在。
- [x] 将 OpenAPI schema 与 `api-types.ts` 做 top-level 字段级 endpoint/type 对照。
- [x] 给当前 browser API client 建立 endpoint registry，避免路径继续散落在 `api-client.ts`。
- [x] 建立 server/static runtime adapter 基础文件与单元测试。
- [x] 将三库同时 active 后的 `/query` 契约差距纳入前端重写 TODO。
- [ ] 为 25 个缺少 response schema 的 endpoint 补 response model 或 compatibility schema。
- [x] 对 `QueryRequest` 补齐前端缺失字段：`business_topics`、`document_types`、`regions`、`years`。
- [x] 对 `QueryResponse` 补齐 `effective_source_collections`，并在查询工作台展示实际检索范围。
- [x] 对查询异常态补充 typed client error 和 UI 文案。
- [ ] 对 `TableAnalysisUploadResponse` 和 `AgentPromptVersionCreateRequest` 的 required/optional 差异做 contract 决策。
- [ ] 将页面或 server component 迁移到 `api-client.server.ts` / `api-client.static.ts` 等价 adapter。
- [ ] 为 legacy review-task/report/rectification 设计 `/api/v1` contract 草案。
- [ ] 为 product templates 决定 ownership：frontend fixture、backend config、DB-backed catalog 三选一。

## 本轮未验证

- 未运行本地服务或浏览器 E2E。
- 未生成持久 OpenAPI snapshot。
- 未做深层 nested schema diff。
- 未检查生产只读路径。
- 未执行任何 production write、provider call 或 deploy。

## P3-QUERY-ERRORS 验证

- `uv run pytest tests/knowledge_query/test_api.py -k 'query_endpoint_returns_citation_answer_and_records_query_log or query_endpoint_excludes_personal_materials_from_default_retrieval'`：`2 passed`
- `COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm --filter medical-audit-web test -- api-client.test.ts knowledge-query-workbench.test.tsx`：`2` test files / `34` tests passed
- `uv run ruff check src/medical_audit_kb/api/routes_query.py tests/knowledge_query/test_api.py`：passed
- `COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm --filter medical-audit-web typecheck`：passed
- `git diff --check -- ...`：passed for scoped touched files
