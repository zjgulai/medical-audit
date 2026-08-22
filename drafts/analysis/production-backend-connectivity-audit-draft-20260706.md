---
title: "生产环境后端联通与虚拟数据排查报告"
doc_type: analysis-report
module: production
status: superseded
created: 2026-07-06
updated: 2026-08-13
owner: self
source: human+ai
project: medical_audit
created_at: "2026-07-06T03:56:48.287046+00:00"
evidence_grade: "L3-production-read-only for GET/browser observations; POST paths not submitted"
source_baseline: "edae456790c2abb3d2ee896179a0b67be3e696fa"
---

# 生产环境后端联通与虚拟数据排查报告

## 结论摘要

- 生产基线：`https://audit.lute-tlz-dddd.top`；源码基线使用干净 worktree `/Users/pray/project/medical_audit-main-deploy-20260706`，HEAD `edae4567`。
- 根目录 `/Users/pray/project/medical_audit` 当前为脏树且落后 `origin/main`，本报告不把它作为源码事实源。
- 矩阵共 `24` 行：`live_db_connected=3`、`persistent_store_connected=5`、`backend_seed_connected=5`、`frontend_static=4`、`ui_shell_only=1`、`write_path_unaudited=6`。
- 浏览器页面上下文 GET 探针 `16/16` 返回 200 JSON；本轮没有提交 POST、上传、创建、安装、保存、归档等业务写入动作。
- 证据边界：GET 页面/API 探针可能产生普通访问日志；本轮没有新增业务对象或上传业务文件。

## P0 缺口

- `/workspace` 项目指标、队列、活动仍来自 `web/src/lib/projects.ts`，需要改为项目驾驶舱 API 聚合。
- `/agent-market` 广场目录和安装入口仍以 `audit-agent-prompts.json` 和本地状态为主，需要服务端市场/安装接口。
- `/documents` 和 `/chat` 的真实问答链路是 POST `/api/v1/query`，本轮为避免写入历史未提交；需要授权 smoke 验证回答、引用和历史回写。
- `/graph`、`/rules`、`/reports`、`/remediation`、`/archive` 虽有 API，但多处来自 `Readonly*Seed` 或静态模板，需要接入项目、规则、疑点、报告、整改、归档真实数据。
- `/fund-compliance`、`/fund-compliance/review`、`/guided-check` 主要是专题静态页面或本地状态，需要专题项目 API、表单 API、单据复核 API。
- `/projects` 列表/成员有后端，但驾驶舱指标仍未与疑点、任务、人员工作量聚合。

## 页面矩阵

| 优先级 | 路由 | 模块 | 状态 | 生产接口证据 | 静态数据 | 下一步 |
|---|---|---|---|---|---|---|
| P0 | `/agent-market` | 智能体广场目录/安装入口 | `frontend_static` 前端静态数据 | 无 | 是 | 把市场目录接 /api/v1/agent-market 或后端 seed registry；安装按钮调用 createAuditAgent。 |
| P0 | `/chat` | AI 问答提交 | `write_path_unaudited` 写入路径未提交 | POST /api/v1/query: 未提交; /api/v1/query/logs?limit=8: 200 store=SqlAlchemyQueryHistoryStore ready=True | 是 | 下一轮在授权测试账号下提交一条可识别 smoke 问题，验证 answer/citations/fallback_used/history。 |
| P0 | `/documents` | 文档检索/历史 | `persistent_store_connected` 持久 store 已接入 | /api/v1/query/logs?limit=8: 200 store=SqlAlchemyQueryHistoryStore ready=True; /api/v1/documents/permissions: 200; /api/v1/documents/uploads: 200 store=SqlAlchemyDocumentUploadStore ready=True; POST /api/v1/query: 未提交 | 是 | 授权后跑一次检索 smoke，校验结果卡片引用与 source_collection；清理 conversationDocuments/knowledgeDocuments 静态兜底。 |
| P0 | `/findings` | 疑点工作台 | `live_db_connected` 真实数据库/索引已接入 | /api/v1/audit-findings: 200 store=SqlAlchemyAuditFindingStore ready=True | 否 | 继续作为后端接入优先页；补复核任务创建按钮的生产写入 smoke。 |
| P0 | `/fund-compliance` | 医保专题首页 | `frontend_static` 前端静态数据 | 无 | 是 | 将专题首页接 findings/rules/projects 聚合；指标来自真实审计专题。 |
| P0 | `/fund-compliance/review` | 专题审计工作台 | `ui_shell_only` 界面壳 | 无 | 是 | 为单据、表单模板、自建表单、复核动作设计并接入专题 API。 |
| P0 | `/graph` | 知识图谱工作台 | `backend_seed_connected` 后端种子数据 | /api/v1/graph/workbench: 200 store=ReadonlyGraphWorkbenchSeed ready=True | 是 | 将节点和边改由项目、知识库、疑点、报告、整改数据聚合生成；保留最小只读图谱方案。 |
| P0 | `/projects` | 项目列表/成员 | `persistent_store_connected` 持久 store 已接入 | /api/v1/projects: 200 store=SqlAlchemyProjectMemberStore ready=True; /api/v1/projects/SELF-CHECK-FUND-20260607/members: 200 store=SqlAlchemyProjectMemberStore ready=True | 是 | 增加项目驾驶舱 API：总审计条数、状态分布、人员工作量，替换 currentSelfCheckProject 静态看板。 |
| P0 | `/reports` | 底稿/报告工作台 | `backend_seed_connected` 后端种子数据 | /api/v1/reports/workbench: 200 store=SqlAlchemyReviewTaskStore ready=True | 是 | 接入 review_task/report_draft/signed_report 数据，明确导出按钮对应真实文件。 |
| P0 | `/rules` | 规则库工作台 | `backend_seed_connected` 后端种子数据 | /api/v1/rules/workbench: 200 store=ReadonlyRulesWorkbenchSeed ready=True | 是 | 接入规则定义表、规则运行记录和疑点生成状态，替换 seed run snapshots。 |
| P0 | `/workspace` | 项目指标/队列/活动 | `frontend_static` 前端静态数据 | 无 | 是 | 新增 /api/v1/projects/{id}/dashboard 或复用 findings/projects 聚合，替换静态指标。 |
| P1 | `/agents` | 创建/版本/上下架/反馈 | `write_path_unaudited` 写入路径未提交 | POST /api/v1/agents: 未提交; POST /api/v1/agents/{agent_id}/prompt-versions: 未提交; POST /api/v1/agents/{agent_id}/lifecycle: 未提交; POST /api/v1/agents/{agent_id}/invocations: 未提交; POST /api/v1/agents/{agent_id}/feedback: 未提交 | 是 | 做独立写入 smoke：创建专用测试智能体、记录调用、反馈、软归档，并提供回滚。 |
| P1 | `/agents` | 我的智能体列表/详情 | `persistent_store_connected` 持久 store 已接入 | /api/v1/agents: 200 store=SqlAlchemyAgentStore ready=True; /api/v1/agents/agent-citation-check: 200 store=SqlAlchemyAgentStore ready=True; /api/v1/agents/agent-citation-check/prompt-versions: 200 store=SqlAlchemyAgentStore ready=True; /api/v1/agents/agent-citation-check/invocations: 200 store=SqlAlchemyAgentStore ready=True; /api/v1/agents/agent-citation-check/feedback: 200 store=SqlAlchemyAgentStore ready=True | 是 | 补充生产 store 类型验收，确保 132 个市场智能体安装后进入同一 store。 |
| P1 | `/analytics` | 表格上传历史 | `persistent_store_connected` 持久 store 已接入 | /api/v1/analytics/table-uploads: 200 store=SqlAlchemyAnalyticsUploadStore ready=True | 是 | 保留历史列表；将模板选择与项目表单模板 API 对齐。 |
| P1 | `/analytics` | 表格分析上传 | `write_path_unaudited` 写入路径未提交 | POST /api/v1/analytics/table-upload: 未提交 | 是 | 用专用样表做上传分析 smoke，验证字段画像、留存、历史回显。 |
| P1 | `/archive` | 归档工作台 | `backend_seed_connected` 后端种子数据 | /api/v1/archive/workbench: 200 store=ReadonlyArchiveWorkbenchSeed ready=True | 是 | 接入真实审计日志、文件 hash、签名链和归档包记录。 |
| P1 | `/chat` | 智能体选择 | `persistent_store_connected` 持久 store 已接入 | /api/v1/agents: 200 store=SqlAlchemyAgentStore ready=True | 是 | 确认 chat 选择项与 /agents 使用同一 store；清理本地 default fallback 展示边界。 |
| P1 | `/documents` | 个人文档上传治理 | `write_path_unaudited` 写入路径未提交 | POST /api/v1/documents/uploads: 未提交; POST /api/v1/documents/uploads/{upload_id}/governance: 未提交; POST /api/v1/documents/uploads/{upload_id}/index: 未提交 | 是 | 使用小型测试文件执行 upload-governance-index-readback 闭环，完成后归档或标记测试数据。 |
| P1 | `/guided-check` | AI 引导自查 | `frontend_static` 前端静态数据 | 无 | 是 | 接入项目任务、证据缺口、智能体模板与风险信号接口。 |
| P1 | `/knowledge-base` | 知识库状态/分类 | `live_db_connected` 真实数据库/索引已接入 | /api/backend/index/search-backend: 200; /api/v1/documents/permissions: 200 | 是 | 将权限分类中的文档数量与 source_collection 实时 count 对齐，去掉前端兜底数字。 |
| P1 | `/knowledge-query` | 独立知识查询 | `write_path_unaudited` 写入路径未提交 | POST /api/v1/query: 未提交 | 否 | 授权后执行一条 smoke 查询并记录 citations/fallback_used。 |
| P1 | `/remediation` | 整改工作台 | `backend_seed_connected` 后端种子数据 | /api/v1/remediation/workbench: 200 store=ReadonlyRemediationWorkbenchSeed ready=True | 是 | 由报告整改事项和复核任务状态生成整改台账。 |
| P1 | `/workspace` | 服务状态卡 | `live_db_connected` 真实数据库/索引已接入 | /api/backend/health: 200; /api/backend/index/search-backend: 200 | 否 | 保留；下一步把项目指标也改为后端聚合。 |
| P2 | `/projects` | 新增成员 | `write_path_unaudited` 写入路径未提交 | POST /api/v1/projects/{project_id}/members: 未提交 | 是 | 授权后用测试成员执行创建-读取-清理或软标记。 |

## 真实接入分层

### 已有真实数据库/索引证据

- `/api/backend/index/search-backend`：生产返回 `ready=true`，`matching_embedding_count=49051`，属于知识库索引可读证据。
- `/api/v1/audit-findings`：生产返回疑点列表和 readiness，源码走 `AuditFindingStore`，属于疑点工作台优先保留链路。
- `/api/v1/documents/uploads`、`/api/v1/analytics/table-uploads`、`/api/v1/agents`、`/api/v1/projects`：生产 GET 可读，属于持久 store 或项目成员 store 的已接入面。

### 后端 API 可达但内容仍是种子/样例

- `/api/v1/graph/workbench`：源码 `ReadonlyGraphWorkbenchSeed`，节点和边来自常量。
- `/api/v1/rules/workbench`：源码 `ReadonlyRulesWorkbenchSeed`，规则、运行快照、门禁来自常量。
- `/api/v1/remediation/workbench`：源码 `ReadonlyRemediationWorkbenchSeed`，整改事项和补证请求来自常量。
- `/api/v1/archive/workbench`：源码 `ReadonlyArchiveWorkbenchSeed`，档案包、签名链、时间线来自常量。
- `/api/v1/reports/workbench`：接口可达，但仍需拆解模板、底稿、报告文件是否来自真实 review task/report store。

### 前端静态或界面壳

- `web/src/lib/projects.ts`：`/workspace` 的项目指标、队列、活动。
- `web/src/lib/portal-data.ts`：引导自查、表单模板、知识库卡片、图谱、规则、报告、整改、归档等大量展示数据。
- `web/src/data/audit-agent-prompts.json`：智能体广场目录。
- `/fund-compliance/review`：自建表单存在于本地 React state，刷新后不会持久化。

## 下一阶段执行建议

1. P0-1：建立 `/api/v1/projects/{project_key}/dashboard`，聚合疑点、复核任务、人员工作量、状态分布，替换 `/workspace` 和 `/projects` 静态看板。
2. P0-2：建立智能体市场后端目录与安装接口，把 `audit-agent-prompts.json` 入库或服务端 seed 化，安装后进入 `/api/v1/agents` 同一 store。
3. P0-3：授权后对 `/chat` 与 `/documents` 执行专用 smoke 查询，验证 `answer`、`citations`、`fallback_used`、`query_history`。
4. P0-4：把 `/graph`、`/rules`、`/reports` 的 `Readonly*Seed` 改成由知识库、规则运行、疑点、复核任务和报告记录聚合。
5. P0-5：为医保专题建立专题项目 API：单据列表、费用表单模板、自建表单、复核动作、底稿生成状态。

## 产物

- 矩阵 JSON：`/Users/pray/project/medical_audit/tmp/outputs/production-backend-connectivity-matrix-20260706.json`
- 原始 API/source 证据：`/Users/pray/project/medical_audit/tmp/outputs/production-backend-connectivity-matrix-20260706.raw.json`
- 浏览器 CLI 网络证据：`/Users/pray/project/medical_audit/tmp/outputs/production-backend-connectivity-browser-cli-20260706/browser-cli-network-summary.json`
- 浏览器同源 API 探针：`/Users/pray/project/medical_audit/tmp/outputs/production-backend-connectivity-browser-cli-20260706/browser-eval-api-probe.json`

## 证据限制

- 本报告不声明所有写入闭环已验收；POST 路径均未提交。
- 浏览器 CLI 的 network 列表主要暴露 Next RSC 导航请求，因此用页面上下文 `fetch` 对 GET API 做补充探针。
- 生产 GET 探针可能被后端记录为普通操作日志，但不新增业务对象。
