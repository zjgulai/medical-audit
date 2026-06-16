---
title: AI智能审计管理系统项目状态与债务台账
doc_type: workflow
module: project-governance
topic: project-state-and-debt-register
status: stable
created: 2026-06-14
updated: 2026-06-16
owner: self
source: human+ai
---

# AI智能审计管理系统项目状态与债务台账

## 1. 目的

本台账用于冻结当前项目真实状态，统一识别技术债务、工程债务、产品集成债务、项目管理债务、文档管理债务和脆弱点债务。

任何后续计划、开发、部署和验收，都必须先对齐本台账的事实边界：

- `fixture` 只证明链路，不代表真实医院数据验收。
- `fallback` 只证明引用型答案兜底，不代表生成式模型能力可用。
- 静态 UI 和浏览器本地 state 不代表后端持久化能力完成。
- 只读 smoke 不代表写入型业务流验收。
- 生产健康不代表 V1.0 产品闭环完成。

## 2. 当前状态冻结

冻结日期：`2026-06-16`

### 2.1 生产状态

- 生产域名：`https://audit.lute-tlz-dddd.top`
- 服务器：`101.34.52.232`
- 主机名：`VM-0-16-ubuntu`
- 用户：`ubuntu`
- SSH key：`ai_video.pem`，必须保留在本项目本地，不能删除。
- 当前生产部署 SHA：`b425e2123d55a94dc6b6c800b806384eec1de679`
- `medical_audit_app`：running，healthy。
- `medical_audit_pg`：running，healthy。
- `ai_video_nginx`：running，作为共享公网入口。
- PostgreSQL 检索后端：`backend=postgres`，`ready=true`。
- Kimi embedding：`embedding_model=kimi-for-coding`，`embedding_dimension=1024`。
- 当前匹配 embeddings：`49051`。
- 当前 active index：`incremental-20260615-national-regulation-stable-20260615103344`，覆盖 `503` 个 source documents、`49051` 个 chunks 和 `49051` 条 embeddings。
- 最新项目成员生产写入 smoke 报告：`tmp/outputs/production-project-member-write-smoke-20260614.json`，状态 `pass`。
- 最新智能体生产写入 smoke 报告：`tmp/outputs/production-agent-write-smoke-20260614.json`，状态 `pass`。
- 最新 AI 数据分析生产上传解析 smoke 报告：`tmp/outputs/production-analytics-upload-smoke-20260614.json`，状态 `pass`。
- 最新 AI 数据分析上传留存 API 写入报告：`tmp/outputs/production-analytics-retention-write-e2e-20260615.json`，状态 `pass`。
- 最新 AI 数据分析上传留存 UI 联调报告：`tmp/outputs/production-analytics-ui-upload-retention-e2e-20260615.json`，状态 `pass`。
- 最新文档检索生产查询 smoke 报告：`tmp/outputs/production-documents-query-smoke-20260614.json`，状态 `pass`。
- 最新文档检索边界能力生产写入型 E2E 报告：`tmp/outputs/production-documents-index-readiness-e2e-pr103-20260616.json`，状态 `pass`。
- 最新生产基础 E2E smoke 报告：`tmp/outputs/production-e2e-smoke-after-pr103-index-readiness-deploy-20260616.json`，状态 `pass`。
- 最新生产前端语义验收报告：`tmp/outputs/production-frontend-acceptance-after-ssh-stdin-fix-deploy-20260616.json`，状态 `pass`，覆盖 `21` 个路由、`42` 个检查，`p0=[]`，`p1=[]`。
- 最新生产部署后只读核验：远端 `.deploy-sha=b425e2123d55a94dc6b6c800b806384eec1de679`，`medical_audit_app` 和 `medical_audit_pg` 均为 `healthy`，公网 `/api/v1/index/search-backend` 返回 `ready=true`。
- 最新个人材料入索引审批状态机部署结论：PR #103 已生产部署；`department-head` 可人工审批通过或驳回个人材料入索引申请，普通 `auditor` 审批返回 `403`，审批更新和拒绝均写入持久化审计日志。
- 最新部署工具链修复结论：PR #95 和 PR #96 均已合并但生产部署验证失败，原因均为 DB 备份完成后本地 SSH 仍挂起；PR #97 已合并、部署并验证通过，有效修复点为远端脚本式 `_ssh` 调用统一使用 `ssh -n`。
- 最新国家规章平台增量激活后生产 E2E 报告：`tmp/outputs/production-e2e-smoke-after-national-regulation-app-restart-20260615.json`，状态 `pass`。
- 最新索引管理拒绝审计部署后生产 E2E 报告：`tmp/outputs/production-e2e-smoke-after-index-admin-denial-audit-deploy-20260615.json`，状态 `pass`。
- 最新索引管理拒绝审计专项生产 smoke：`tmp/outputs/production-index-admin-denial-audit-smoke-20260615.json`，状态 `pass`；普通审计角色访问 `/api/v1/index/versions/activate` 返回 `403`，并在持久化 `audit_log_events` 中记录 `index-admin-access-denied`。
- 最新索引管理拒绝审计部署状态巡检：`tmp/outputs/tencent-cloud-deployment-state-after-index-denial-deploy-20260615.json`，状态 `pass`，`issues=[]`，`.deploy-sha=a3111bf615995bd03a95514c49447cd82087e5ab`。
- 最新门户配置写入拒绝审计部署后生产 E2E 报告：`tmp/outputs/production-e2e-smoke-after-portal-config-denial-deploy-20260615.json`，状态 `pass`。
- 最新门户配置写入拒绝审计专项生产 smoke：`tmp/outputs/production-portal-config-denial-audit-smoke-20260615.json`，状态 `pass`；`guest` 角色写 `/api/v1/agents` 和 `/api/v1/projects/SELF-CHECK-FUND-20260607/members` 均返回 `403`，并在持久化 `audit_log_events` 中分别记录 `agent-access-denied` 和 `project-member-access-denied`。
- 最新 AI 数据分析留存历史本地联调截图：`tmp/screenshots/tmp-screenshot-analytics-retention-history-20260615.png`。
- 项目成员写入前 DB 备份：`/opt/medical-audit/backups/db/pre-project-member-write-smoke-20260614T212850+0800.sql.gz`，`gzip -t` 通过，权限 `600`，大小 `512950686` bytes，`sha256=2f0c119410ad58690934f555cf6d807a91c70cf6588a8189dcc4d058f0c4b8a0`。
- 项目成员生产写入结果：`CATALOG-LIMIT-202606` 新增 `member-custom-e152673f93f9`，成员数从 `4` 增至 `5`，数据库 `audit_project_members` 当前自定义记录数为 `1`。
- 智能体写入前 DB 备份：`/opt/medical-audit/backups/db/pre-agent-write-smoke-20260614T215017+0800.sql.gz`，`gzip -t` 通过，权限 `600`，大小 `512951265` bytes，`sha256=5d06dd8919f71f7d73446203424e8907dd1fc7677fc2a3d40e819bf6109026db`。
- 智能体生产写入结果：新增 `agent-custom-ec210547464a`，智能体列表从 `3` 增至 `4`，数据库 `audit_agents` 当前自定义记录数为 `1`。
- AI 数据分析生产上传结果：CSV 和 XLSX 上传均返回 `200`、`status=parsed`、`row_count=4`、`column_count=7`、`duplicate_row_count=1`，并识别金额/费用、患者/就诊、医保支付等审计信号；不支持的 `.txt` 扩展返回 `422 unsupported table file extension`。
- AI 数据分析留存历史生产结果：生产已应用 `analytics_upload_records` 表和索引；API 上传记录 `analytics-upload-b3a1898e38d1` 和 UI 上传记录 `analytics-upload-f39d652d3f81` 均完成历史查询、DB 行和宿主机留存文件 `sha256` 校验。
- 文档检索生产查询结果：全库重复收费、法规政策过滤和医保目录过滤 `POST /api/v1/query` 均返回 `200`，每个用例返回 `3` 条引用、证据分组和 `query_log_index`；首个引用 `chunk_id` 对应 `/pages/preview/{chunk_id}` 均返回 `200`。
- 文档检索边界能力生产结果：生产已应用 `document_upload_records` 表和索引；最新人工审批通过路径记录 `document-upload-29e6f19736ed` 和人工驳回路径记录 `document-upload-da1a475b381b` 的 DB 行、宿主机文件和 `sha256` 均校验通过；普通审计员只能读取本人上传，其他普通审计员不可见，管理员可读全部个人上传；`department-head` 可审批通过或驳回，普通 `auditor` 审批返回 `403` 并写入审计日志；审批通过后在生产 `unconfigured` 病毒扫描和 DLP provider 约束下仍保持 `blocked`，仅清除人工审批 blocker；审批驳回后 `index_readiness.status=rejected`、blocker 为 `manual-index-approval-rejected`；`/api/v1/query` 已验证 `source_collection=medical-insurance-laws` 在 citation 和 basis item 中直接回显。

生产结论：当前生产检索、引用、预览、静态门户、文档检索查询、文档来源回显、文档来源权限读取、个人材料留存、个人材料上传治理门禁表达、个人材料人工入索引审批状态机、索引管理拒绝审计、门户配置写入拒绝审计、权限上下文兼容层、任务级复核写入链路、项目成员持久化写入链路、提示词型智能体持久化写入链路、AI 数据分析上传解析链路、AI 数据分析上传留存/历史记录链路和部署脚本 DB 备份后不中断继续执行链路可用；不能据此宣称真实医院审计、真实生成模型、真实登录会话/全站权限体系、生产级病毒扫描、DLP/脱敏改写、对象存储、个人材料实际入索引、下载权限隔离或案件级合规闭环已完成。

### 2.2 本地仓库状态

- 当前工作区：`/Users/pray/project/medical_audit_minimal_pr`
- 当前本地工作分支：以执行时 `git status` 为准；本轮状态同步使用 `codex/*` docs-only 分支。
- 本轮生产部署和文档同步执行 worktree：`/Users/pray/project/medical_audit_minimal_pr`
- 当前文档同步分支：`codex/pr103-production-doc-sync`。
- GitHub `main` 当前已包含 PR #103 代码合并；截至本次核验，本地 `main`、`origin/main` 和生产 `.deploy-sha` 均为 `b425e2123d55a94dc6b6c800b806384eec1de679`。
- 当前生产运行代码 SHA：`b425e2123d55a94dc6b6c800b806384eec1de679`
- 本轮已完成 PR #103 的生产部署和 `/documents` 入索引审批写入型 E2E 验收；PR #101 为已生效生产部署历史记录，PR #95/#96 仍只作为失败验证记录，PR #97 为已生效部署工具链修复。
- 本次功能部署后 `main` 与生产部署 SHA 已重新对齐；后续若合并 docs-only PR，必须重新区分 `main` 领先生产与生产已部署两个事实。
- 当前存在额外 worktree：
  - `/Users/pray/.config/superpowers/worktrees/medical_audit/frontend-plan-02-projects-dashboard`
  - `/Users/pray/project/medical_audit_minimal_pr`
- 当前存在未跟踪资料和草稿目录：
  - `.kiro/`
  - `.playwright-mcp/`
  - `drafts/analysis/analysis-production-acceptance-p0-p1-*.md`
  - `drafts/analysis/analysis-reference-material-*.md`
  - `opendesign/`
  - `ref/`

仓库结论：当前本地状态适合继续做生产验收状态同步；进入功能开发前，仍必须从明确的主线或新 `codex/` 分支开始，避免把历史 worktree、参考材料和草稿混入交付分支。

### 2.3 产品状态

已完成：

- `AI智能审计管理系统` 门户壳层已部署。
- 生产静态页面已覆盖工作台、对话、智能体、智能体广场、知识库、文档、数据分析、图谱、规则、报告、整改、归档、项目、引导自查、知识查询和疑点入口。
- 知识库查询引擎已具备检索、引用型回答、原文预览、索引管理、评测和回滚治理。
- 复核任务台已具备任务级持久化、报告准备度预检、附件归档、正式报告签发冻结、整改跟踪和结案只读锁。
- HIS 数据底座、staging、snapshot、字段映射校验、`CHARGE-RULE-001` fixture 与 staging 执行路径已具备工程基础。
- 智能体持久化已完成生产写入型 E2E；生产 `/api/v1/agents` 返回 `SqlAlchemyAgentStore`，新增智能体刷新后仍可读，数据库 `audit_agents` 已落表。
- 项目成员持久化已完成生产写入型 E2E；`/api/v1/projects` 和 `/api/v1/projects/{project_key}/members` 均返回 `SqlAlchemyProjectMemberStore`，新增成员刷新后仍可读，数据库 `audit_project_members` 已落表。
- AI 数据分析表格上传解析已完成生产上传 E2E；CSV 和 XLSX 由 FastAPI 后端解析并返回字段画像、质量提示、重复行和审计信号。
- AI 数据分析上传留存和历史记录已完成生产部署与写入型 E2E；上传后写入 `analytics_upload_records`，原始文件按 `sha256` 可追溯留存在受控目录，前端 `/analytics` 可展示最近上传历史。
- 文档检索页已完成生产查询 E2E；`/api/v1/query` 可按来源过滤返回引用、证据分组和原文入口，`/pages/preview/{chunk_id}` 生产预览可打开。
- 文档检索搜索历史持久化已完成本地实现和联调；`/api/v1/query` 返回 `query_log_id`，`GET /api/v1/query/logs` 可从 `query_logs` 读取历史，`/documents` 可展示、刷新和回填历史。
- 文档检索剩余边界已完成生产部署和写入型 E2E；`/api/v1/query` 的 `citations` 与 `basis_groups.items` 直接回显 `source_collection`，`/api/v1/documents/permissions` 返回来源集合读权限，`/api/v1/documents/uploads` 支持个人材料留存、刷新后读取和普通审计员/管理员角色隔离，`/documents` 页面可展示权限状态和 `not-indexed` 上传历史。
- 个人材料上传治理 provider 配置层已完成生产部署；默认生产配置下病毒扫描和 DLP adapter 为 `unconfigured`，会以 `index_readiness` 明确阻断个人材料实际入索引，并返回三项 blockers 供前后端和审计日志消费。
- 个人材料人工入索引审批状态机已完成生产部署和写入型 E2E；`department-head` 可审批通过或驳回，普通 `auditor` 审批返回 `403`，审批结果持久化到 `document_upload_records.metadata.index_readiness` 并写入 `audit_log_events`。

未完成：

- 智能体提示词版本治理、上下架、删除/停用和权限生效仍未完成；本轮只验证新增提示词型智能体持久化。
- 项目成员真实权限、邀请审批、成员禁用/移除和权限生效仍未完成；本轮只验证成员新增持久化。
- AI 数据分析病毒扫描、脱敏改写、对象存储、下载权限隔离、正式工作簿治理和长期存储生命周期策略仍未完成。
- 文档检索个人材料当前只完成留存、角色读取隔离、入索引治理门禁表达和人工审批状态机；真实认证、生产级病毒扫描、生产级 DLP/脱敏改写、对象存储、下载权限隔离、个人材料实际入索引流程和生产搜索历史列表/回填专项验收仍未完成。
- 多数门户模块仍由 `web/src/lib/portal-data.ts` 静态数据驱动。
- 生产数据仍以受控脱敏 fixture 为主要业务写入验收样本。
- Kimi 当前只验证为 embedding provider；线上答案生成模型未验证通过。
- 用户、角色、科室、全站权限、证书级电子签章、长期留存介质和真实外部告警端点未闭合。

### 2.4 Phase 1 基线验收状态

验收日期：`2026-06-14`

本轮 Phase 1 已完成，结论为 `pass`。

本地后端基线：

- `uv run ruff check src tests scripts`：通过。
- `uv run mypy src`：通过，`73` 个源码文件无类型错误。
- `uv run pytest`：通过，`241 passed`，`1` 个 `StarletteDeprecationWarning`，当前不阻断。

本地前端基线：

- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test`：通过，`10` 个 test files、`51` 个 tests。
- `pnpm --dir web build:static`：通过，静态构建生成 `20/20` 页面。
- 本轮修复了测试门禁债务：ESLint 忽略 `coverage/**`，Vitest 设置 `testTimeout=30000`，并补齐异步组件测试等待，避免 `act(...)` warning 污染验收信号。

生产只读验收：

- 报告：`tmp/outputs/production-e2e-smoke-phase1-readonly-20260614.json`
- 状态：`pass`
- 覆盖：TLS、health、PostgreSQL 检索、页面渲染、查询引用、原文预览、底稿导出和边缘域名回归。
- 边界：`query-api-with-citations.fallback_used=true`，只证明引用型 fallback 链路健康。

生产前端语义验收：

- 报告：`tmp/outputs/production-frontend-acceptance-phase1-20260614.json`
- 状态：`pass`
- 覆盖：`20` 个路由，桌面和移动共 `40` 次检查。
- 结果：`p0=[]`，`p1=[]`。
- 最新一次语义验收：`tmp/outputs/production-frontend-acceptance-latest.json`，状态 `pass`；`check_count=42`（21 个路由×2 viewport），`summary.api_checks` 中 `/audit/logs` 与 `/audit/logs/export` 均满足 `denied_status=403`、`allowed_status=200`，`p0=[]`、`p1=[]`。

生产写入型验收：

- 写入前 DB 备份：`/opt/medical-audit/backups/db/pre-review-write-smoke-phase1-20260614T105417+0800.sql.gz`
- 备份状态：`gzip -t` 通过，权限 `600`，大小约 `490M`，`sha256=169eeec6a99ff09e1a0a277d75f2f70620d01ff6b71dd03ea4c68a7b98cbb777`。
- 报告：`tmp/outputs/production-e2e-smoke-phase1-review-write-20260614.json`
- 状态：`pass`
- 覆盖：只读 smoke 全部步骤 + 复核任务创建/更新/导出。
- 写入结果：创建并更新 `review-task-0011`，`create_status=200`，`update_status=200`。
- 写入后状态审计：`pass`，`medical_audit_app` 和 `medical_audit_pg` 保持 healthy，检索后端仍 `ready=true`。

Phase 1 结论：工程基线、生产只读链路、门户语义验收和任务级写入型 smoke 均已通过；下一阶段应进入 Phase 2 产品集成债务治理。

### 2.5 Phase 2.1 本地验收状态

验收日期：`2026-06-14`

本轮 Phase 2.1 已完成，结论为 `pass`，范围限定为本地开发和联调环境。

后端集成：

- 新增 `audit_agents` SQLAlchemy 模型和正式 SQL schema。
- 新增 `SqlAlchemyAgentStore`、`InMemoryAgentStore` 和 `/agents` GET/POST API。
- `/agents` 返回系统默认智能体和自定义智能体；默认项标记为 `source=system-default`，自定义项标记为 `source=custom`。
- 新增自定义智能体写入持久化 store，刷新或重新创建 store 后仍可读取。

前端集成：

- `AgentWorkspace` 启动时读取 `/api/v1/agents`。
- 新增智能体必须通过 `createAuditAgent` POST 后端成功后才进入页面列表。
- 后端不可用时只显示默认内容和错误状态，不再伪造本地新增成功。

本地验收：

- `uv run ruff check src tests scripts`：通过。
- `uv run mypy src`：通过，`75` 个源码文件无类型错误。
- `uv run pytest`：通过，`244 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test`：通过，`10` 个 test files、`54` 个 tests。
- `pnpm --dir web build:static`：通过，静态构建生成 `20/20` 页面。
- 本地浏览器联调：Next `127.0.0.1:3030` + FastAPI `127.0.0.1:8021`，`/agents` 页面显示默认智能体、后端连接状态和新增自定义智能体；刷新级 API 校验返回 `store.ready=true`。
- 浏览器截图：`tmp/screenshots/tmp-screenshot-agents-phase2-agent-persistence-20260614.png`。

边界：

- 本轮未执行生产部署。
- 本轮未对生产 PostgreSQL 应用 `audit_agents` schema。
- 本轮 FastAPI 联调使用本地临时 SQLite agent store，仅证明前后端协议和持久化行为。

### 2.6 Phase 2.2 本地验收状态

验收日期：`2026-06-14`

本轮 Phase 2.2 已完成，结论为 `pass`，范围限定为本地开发和联调环境。

后端集成：

- 新增 `audit_project_members` SQLAlchemy 模型和正式 SQL schema。
- 新增 `SqlAlchemyProjectMemberStore`、`InMemoryProjectMemberStore` 和项目成员 API。
- `/projects` 返回系统默认项目，并按自定义成员数量更新 `member_count`。
- `/projects/{project_key}/members` 返回系统默认成员和自定义成员；默认项标记为 `source=system-default`，自定义项标记为 `source=custom`。
- 新增自定义成员写入持久化 store，刷新或重新创建 store 后仍可读取。

前端集成：

- `ProjectManagementWorkbench` 启动时读取 `/api/v1/projects`。
- 切换项目时读取 `/api/v1/projects/{project_key}/members`。
- 新增成员必须通过 `createProjectMember` POST 后端成功后才进入页面列表。
- 后端不可用时只显示默认内容和错误状态，不再伪造本地新增成功。

本地验收：

- `uv run ruff check src tests scripts`：通过。
- `uv run mypy src`：通过，`77` 个源码文件无类型错误。
- `uv run pytest`：通过，`247 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test`：通过，`10` 个 test files、`57` 个 tests。
- `pnpm --dir web build:static`：通过，静态构建生成 `20/20` 页面。
- 本地浏览器联调：Next `127.0.0.1:3030` + FastAPI `127.0.0.1:8021`，`/projects` 页面显示项目后端连接、成员后端连接和新增自定义成员。
- 刷新级 API 校验：FastAPI 与 Next 代理均返回 `store.ready=true`；`CATALOG-LIMIT-202606` 自定义成员排在默认成员前，项目成员数从 `4` 增至 `5`。
- 浏览器截图：`tmp/screenshots/tmp-screenshot-projects-phase2-member-persistence-20260614.png`。

边界：

- 本轮未执行生产部署。
- 本轮未对生产 PostgreSQL 应用 `audit_project_members` schema。
- 本轮 FastAPI 联调使用本地临时 SQLite project member store，仅证明前后端协议和持久化行为。

### 2.7 Phase 2.3 本地验收状态

验收日期：`2026-06-14`

本轮 Phase 2.3 已完成，结论为 `pass`，范围限定为本地开发和联调环境。

后端集成：

- 新增 `/analytics/table-upload` API，统一接收 multipart 表格上传。
- CSV 由 Python `csv` 解析，XLSX 和 XLSM 由 `openpyxl` 解析。
- 后端返回字段画像、字段类型、空值、去重值、样例值、重复行、质量提示、审计线索和建议。
- 不支持的扩展名返回 `422`，空文件、超大文件和无法解析的工作簿不返回伪成功状态。
- API 操作写入 `analytics-table-upload` operation log。

前端集成：

- `DataAnalysisWorkbench` 已移除浏览器本地 CSV parser。
- 上传 CSV、XLSX 或 XLSM 时统一调用 `uploadAnalysisTable` 走 `/api/v1/analytics/table-upload`。
- 页面展示后端返回的字段画像；后端失败时显示失败状态，不再伪造本地解析成功或排队成功。
- 右侧上传入口、终端状态和报告状态已改为后端解析口径。

本地验收：

- `uv run ruff check src tests scripts`：通过。
- `uv run mypy src`：通过，`78` 个源码文件无类型错误。
- `uv run pytest`：通过，`250 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test`：通过，`10` 个 test files、`58` 个 tests。
- `pnpm --dir web build:static`：通过，静态构建生成 `20/20` 页面。
- 本地浏览器联调：Next `127.0.0.1:3030` + FastAPI `127.0.0.1:8021`，`/analytics` 页面上传 CSV 和 XLSX 均通过后端解析并渲染结果。
- 浏览器截图：
  - `tmp/screenshots/tmp-screenshot-analytics-phase23-csv-upload-20260614.png`
  - `tmp/screenshots/tmp-screenshot-analytics-phase23-xlsx-upload-20260614.png`

边界：

- 本轮未执行生产部署。
- 本轮未建立上传文件持久化、历史分析记录、病毒扫描、脱敏留存或对象存储。
- 本轮表格解析为本地瞬时分析能力，仅证明前后端上传解析协议和字段画像展示。

### 2.8 Phase 2.4 本地验收状态

验收日期：`2026-06-14`

本轮 Phase 2.4 已完成，结论为 `pass`，范围限定为本地开发和联调环境。

前端集成：

- `/documents` 已从静态跳转页调整为客户端 API-first 文档检索工作台。
- 文档源卡片可作为 `source_collections` 过滤条件传给后端 `/query`。
- 执行检索后展示后端返回的答案、引用数、引用片段、证据分组和 `/pages/preview/{chunk_id}` 原文入口。
- 搜索历史保留为本页快捷填充，不再伪装为后端历史记录。
- 对话文档和知识库文档示例列表保留为只读入口，继续作为静态示例资产。

本地验收：

- `uv run ruff check src tests scripts`：通过。
- `uv run mypy src`：通过，`78` 个源码文件无类型错误。
- `uv run pytest`：通过，`250 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test`：通过，`10` 个 test files、`58` 个 tests。
- `pnpm --dir web build:static`：通过，静态构建生成 `20/20` 页面。
- 本地浏览器联调：Next `127.0.0.1:3030` + FastAPI `127.0.0.1:8021`，使用本地 fake search engine 验证 `/documents` 选择来源、提交检索、渲染引用和原文入口。
- 浏览器截图：`tmp/screenshots/tmp-screenshot-documents-phase24-api-search-20260614.png`。

边界：

- 本轮未执行生产部署。
- 本轮未新增文档持久化、搜索历史持久化、文档权限模型或个人知识库上传能力。
- 本轮浏览器联调使用本地 fake search engine，仅证明前端页面、Next 代理和 `/query` 协议闭环。

### 2.9 Phase 2.5 AI 数据分析留存历史本地验收状态

验收日期：`2026-06-15`

本轮 Phase 2.5 已完成本地实现和联调，结论为 `pass`，范围限定为本地开发和联调环境。

后端集成：

- 新增 `analytics_upload_records` 数据表和 SQLAlchemy model。
- 新增 `SqlAlchemyAnalyticsUploadStore` 和 `InMemoryAnalyticsUploadStore`。
- `/analytics/table-upload` 上传成功后写入原始文件、`sha256`、相对留存路径、字段画像摘要和上传历史记录。
- 新增 `GET /analytics/table-uploads`，返回最近上传记录和 store 状态。
- 新增 `MEDICAL_AUDIT_ANALYTICS_UPLOAD_ROOT`，未配置时使用 `index_root/analytics-uploads`。

前端集成：

- `/analytics` 页面加载最近上传历史。
- 上传成功后刷新历史列表，并展示 `upload_id`、`sha256` 和“已留存”状态。
- 历史读取失败不阻断文件上传，只显示历史不可用状态。

部署配置：

- 腾讯云 Compose 新增 `/app/analytics-uploads` 挂载。
- `medical-audit.env.example` 新增 `MEDICAL_AUDIT_ANALYTICS_UPLOAD_ROOT_HOST=/opt/medical-audit/analytics-uploads`。
- 部署脚本会创建 `/opt/medical-audit/analytics-uploads`，避免首次挂载目录权限漂移。

本地验收：

- `uv run pytest tests/knowledge_query/test_api.py tests/knowledge_query/test_sql_assets.py`：通过，`34 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `uv run ruff check src tests scripts`：通过。
- `uv run mypy src`：通过，`79` 个源码文件无类型错误。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test`：通过，`10` 个 test files、`65` 个 tests。
- `pnpm web:build:static`：通过，静态构建生成 `20/20` 页面。
- 本地浏览器联调：Next `127.0.0.1:3030` + FastAPI `127.0.0.1:8021`，`/analytics` 上传 `charge-retention-final.csv` 后页面显示“留存：已留存”，历史接口最新记录为 `analytics-upload-28a10ca6ac89`，`row_count=3`，`column_count=5`，`retention_status=retained`，无失败网络响应。
- 浏览器截图：`tmp/screenshots/tmp-screenshot-analytics-retention-history-20260615.png`。

边界：

- 本节只记录本地实现验收；生产部署与写入验收见 2.10。
- 本轮未实现病毒扫描、脱敏改写、对象存储、下载权限隔离或正式工作簿治理。

### 2.10 Phase 2.5 AI 数据分析留存历史生产验收状态

验收日期：`2026-06-15`

本轮 Phase 2.5 已完成生产部署和写入型验收，结论为 `pass`。

生产部署：

- 部署提交：`cbd93324119b28a7097712ea7b50b2d96b72de31`。
- 部署戳：`analytics-retention-20260615`。
- 生产已应用 `analytics_upload_records` 表和索引。
- 宿主机上传留存目录：`/opt/medical-audit/analytics-uploads`，目录权限 `ubuntu:ubuntu 775`。
- 写入前 DB 备份：`/opt/medical-audit/backups/db/pre-deploy-analytics-retention-20260615.sql.gz`，`gzip -t` 通过，`sha256=876bb9ecc1a0a39aa23085688c613000ca44dc4133b428ab2fdb3cb26d66f68d`。

生产验收：

- 部署后基础 smoke：`tmp/outputs/production-e2e-smoke-after-analytics-retention-deploy-20260615.json`，状态 `pass`。
- 部署状态审计：`tmp/outputs/tencent-cloud-deployment-state-after-analytics-retention-deploy-20260615.json`，状态 `pass`，`issues=[]`。
- 生产前端验收：`tmp/outputs/production-frontend-acceptance-after-analytics-retention-deploy-20260615.json`，状态 `pass`，`p0_count=0`、`p1_count=0`。
- API 上传留存写入验收：`tmp/outputs/production-analytics-retention-write-e2e-20260615.json`，状态 `pass`；记录 `analytics-upload-b3a1898e38d1` 的历史、DB 行和宿主机文件 `sha256` 均校验通过。
- UI 上传留存联调：`tmp/outputs/production-analytics-ui-upload-retention-e2e-20260615.json`，状态 `pass`；记录 `analytics-upload-f39d652d3f81` 由 `/analytics` 页面上传产生，历史、DB 行和宿主机文件 `sha256` 均校验通过。
- UI 截图：`tmp/screenshots/production-analytics-ui-upload-retention-20260615.png`。

边界：

- 上传留存文件当前由容器写出，宿主机文件权限为 `root:root 644`；功能可用，但人工清理需要 sudo 或后续补容器用户/文件权限治理。
- 本轮未实现病毒扫描、脱敏改写、对象存储、下载权限隔离、正式工作簿治理或长期存储生命周期策略。

### 2.11 Phase 2.6 文档检索搜索历史本地验收状态

验收日期：`2026-06-15`

本轮 Phase 2.6 已完成本地实现和联调，结论为 `pass`，范围限定为本地开发和联调环境。

后端集成：

- 新增 `QueryHistoryStore` 抽象、`SqlAlchemyQueryHistoryStore` 和 `InMemoryQueryHistoryStore`。
- 复用既有 `query_logs` 表持久化搜索历史，不新增平行表。
- `/query` 写入查询问题、过滤条件、答案摘要和引用 chunk，并在响应中返回 `query_log_id`。
- `GET /query/logs?limit=` 返回最近搜索历史和 store 状态；持久化 store 不可用或读取失败时回退进程内历史并显式标记 `store.ready=false`。
- 历史写入失败不阻断主检索结果，只在 operation payload 中记录结构化 `query_history_error`。

前端集成：

- `/documents` 页面加载 `GET /api/v1/query/logs?limit=8`。
- 查询成功后刷新历史列表。
- 点击历史项可回填问题和来源集合过滤条件。
- 历史读取失败不阻断文档检索，只显示历史不可用状态。

本地验收：

- `uv run pytest`：通过，`255 passed`，`1` 个既有 `StarletteDeprecationWarning`。
- `uv run ruff check src tests scripts`：通过。
- `uv run mypy src`：通过，`80` 个源码文件无类型错误。
- `pnpm --dir web lint`：通过。
- `pnpm --dir web typecheck`：通过。
- `pnpm --dir web test`：通过，`10` 个 test files、`66` 个 tests。
- `pnpm web:build:static`：通过，静态构建生成 `20/20` 页面。
- 本地浏览器联调：Next `127.0.0.1:3030` + FastAPI `127.0.0.1:8021`，使用本地 fixture search engine 和 `tmp/debug` SQLite 验证 `/documents` 初始历史为空、提交检索后历史刷新、刷新页面后历史仍从 `SqlAlchemyQueryHistoryStore` 回读。
- 浏览器截图：`tmp/screenshots/tmp-screenshot-documents-history-persistence-20260615.png`。

边界：

- 本节只记录 PR #81 搜索历史本地实现验收；PR #83 合并后的生产部署和写入型 E2E 见 2.12。
- 本轮未实现个人知识库上传、文档权限模型或响应中的 `source_collection` 直接回显。

### 2.12 Phase 2.6/2.7 文档检索边界能力生产验收状态

验收日期：`2026-06-15`

本轮已完成 PR #83 生产部署和 `/documents` 写入型验收，结论为 `pass`。

生产部署：

- 部署提交：`f864e370abd7309f6222376074b45ef2bc6c0ff4`。
- 部署戳：`20260615T121812+0800`。
- 生产已应用 `document_upload_records` 表和索引。
- 宿主机个人文档留存目录：`/opt/medical-audit/document-uploads`。
- 写入前 DB 备份：`/opt/medical-audit/backups/db/pre-deploy-20260615T121812+0800.sql.gz`，大小 `512967344` bytes。

生产验收：

- 部署后基础 smoke：`tmp/outputs/production-e2e-smoke-after-deploy-20260615T121812+0800.json`，状态 `pass`。
- 部署状态审计：`tmp/outputs/tencent-cloud-deployment-state-after-documents-boundary-deploy-20260615.json`，状态 `pass`，`issues=[]`。
- 生产前端验收：`tmp/outputs/production-frontend-acceptance-after-documents-boundary-deploy-20260615.json`，状态 `pass`，覆盖 `21` 个路由、`42` 个检查，`p0_count=0`、`p1_count=0`。
- `/documents` 写入型 E2E：`tmp/outputs/production-documents-write-e2e-20260615T122620+0800-verified.json`，状态 `pass`。
- 上传记录：`document-upload-1ba9d6e00cb7`，文件名 `production-documents-write-e2e-20260615T122620+0800.txt`，上传人 `documents-e2e-owner-20260615T122620+0800`。
- DB 行验证：`retention_status=retained`、`index_status=not-indexed`、相对路径 `2026/06/15/document-upload-1ba9d6e00cb7.txt`。
- 宿主机文件验证：`/opt/medical-audit/document-uploads/2026/06/15/document-upload-1ba9d6e00cb7.txt`，`sha256=88fe90530c937d6ea6b534dafff636d5b7dec15b7c1131d786e5f00b007b466e`。
- 角色读取隔离：本人列表包含该上传；其他普通审计员列表不包含该上传；管理员列表包含该上传并返回 `can_read_all_personal_uploads=true`。
- 来源集合回显：`/api/v1/query` 使用 `source_collections=["medical-insurance-laws"]` 返回 `citation_count=1`、`basis_item_count=1`，citation 和 basis item 均回显 `medical-insurance-laws`，同时返回 `query_log_id=9d6ec14e-1406-4e15-88b1-5978f6588891`。

2026-06-16 补充部署验收：

- PR #101 已将个人材料上传治理 provider 配置层部署到生产，部署 SHA 为 `6302f0a8baeb5695861f9682090f65786ea6d6e0`。
- 部署后基础 smoke：`tmp/outputs/production-e2e-smoke-after-deploy-20260616T135218+0800.json`，状态 `pass`。
- `/documents` 写入型 E2E：`tmp/outputs/production-documents-write-e2e-20260616T135913+0800-verified.json`，状态 `pass`。
- 最新上传记录：`document-upload-f81adf853774`，文件名 `production-documents-write-e2e-20260616T135913+0800.txt`，上传人 `documents-e2e-owner-20260616T135913+0800`。
- DB 行验证：`retention_status=retained`、`index_status=not-indexed`、相对路径 `2026/06/16/document-upload-f81adf853774.txt`，`metadata.index_readiness.status=blocked`。
- 宿主机文件验证：`/opt/medical-audit/document-uploads/2026/06/16/document-upload-f81adf853774.txt`，`sha256=90639f5b2a37ab3ec322067059e1f27034dcb4cd51b76794221694414e93d39e`。
- 治理门禁验证：默认 `unconfigured` 病毒扫描、默认 `unconfigured` DLP 审查和人工入索引审批均返回 `blocked`，blockers 为 `virus-scan-required`、`dlp-review-required`、`manual-index-approval-required`。

2026-06-16 入索引审批状态机补充部署验收：

- PR #103 已将个人材料人工入索引审批状态机部署到生产，部署 SHA 为 `b425e2123d55a94dc6b6c800b806384eec1de679`。
- 部署后基础 smoke：`tmp/outputs/production-e2e-smoke-after-pr103-index-readiness-deploy-20260616.json`，状态 `pass`。
- 部署状态审计：`tmp/outputs/tencent-cloud-deployment-state-after-pr103-index-readiness-deploy-20260616.json`，状态 `pass`，`issues=[]`。
- `/documents` 入索引审批写入型 E2E：`tmp/outputs/production-documents-index-readiness-e2e-pr103-20260616.json`，状态 `pass`。
- 审批通过路径记录：`document-upload-29e6f19736ed`，文件名 `production-documents-index-approval-pr103-index-readiness-20260616.txt`，上传人 `documents-e2e-owner-pr103-pr103-index-readiness-20260616`。
- 审批通过路径 DB/文件验证：`retention_status=retained`、`index_status=not-indexed`、相对路径 `2026/06/16/document-upload-29e6f19736ed.txt`，`sha256=d1138be8268699bf221138d5eb7d5e91abe0f471db3bac07e5bb9d7f0f63bc34`。
- 审批通过路径状态验证：`manual-index-approval` check 为 `passed`，人工审批 blocker 已清除；由于生产病毒扫描和 DLP provider 仍为 `unconfigured`，整体 `index_readiness.status=blocked`，剩余 blockers 为 `virus-scan-required`、`dlp-review-required`。
- 审批驳回路径记录：`document-upload-da1a475b381b`，文件名 `production-documents-index-rejection-pr103-index-readiness-20260616.txt`，上传人 `documents-e2e-owner-pr103-pr103-index-readiness-20260616`。
- 审批驳回路径 DB/文件验证：`retention_status=retained`、`index_status=not-indexed`、相对路径 `2026/06/16/document-upload-da1a475b381b.txt`，`sha256=c08e90a5a644725dda1effb367f7e17ddc6d87e6cf35e1fd8ba9d92746bb2284`。
- 审批驳回路径状态验证：`index_readiness.status=rejected`、`next_action=review-manual-index-rejection`、blocker 为 `manual-index-approval-rejected`。
- 权限和审计日志验证：普通 `auditor` 审批返回 `403`；`document-upload-index-approval-access-denied` 和 `document-upload-index-readiness-update` 均以 `entity_type=document-upload` 落入持久化审计日志。

边界：

- 上传材料当前为 `not-indexed`，只完成留存、读取隔离、入索引治理门禁表达和人工审批状态机，不进入知识库检索。
- 查询响应仍为 `fallback_used=true`，只证明引用型 fallback 和来源过滤链路健康，不证明真实生成模型能力。
- 本轮不覆盖真实登录会话、组织级权限、生产级病毒扫描、生产级 DLP/脱敏改写、对象存储、下载权限隔离、个人材料实际入索引或长期存储生命周期策略。
- 早先三份 `production-documents-write-e2e-*.json` 失败报告属于检查脚本 SQL quoting 问题，已被 `production-documents-write-e2e-20260615T122620+0800-verified.json` 以显式 DB 行和宿主机文件校验覆盖。

### 2.13 索引管理拒绝审计生产部署状态

验收日期：`2026-06-15`

本轮已将索引管理拒绝审计部署到生产，结论为 `pass`。

部署事实：

- 部署提交：`a3111bf615995bd03a95514c49447cd82087e5ab`。
- 部署戳：`index-admin-denial-audit-20260615`。
- 写入前 DB 备份：`/opt/medical-audit/backups/db/pre-deploy-index-admin-denial-audit-20260615.sql.gz`。
- 应用备份：`/opt/medical-audit/backups/app/pre-deploy-index-admin-denial-audit-20260615.tar.gz`。
- env 备份：`/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-index-admin-denial-audit-20260615`。
- nginx 备份：`/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-index-admin-denial-audit-20260615`。
- web 静态资产备份：`/opt/medical-audit/backups/web/audit-web-pre-deploy-index-admin-denial-audit-20260615.tar.gz`。

验收证据：

- 部署后基础 smoke：`tmp/outputs/production-e2e-smoke-after-index-admin-denial-audit-deploy-20260615.json`，状态 `pass`。
- 部署状态巡检：`tmp/outputs/tencent-cloud-deployment-state-after-index-denial-deploy-20260615.json`，状态 `pass`，`issues=[]`。
- 专项权限 smoke：`tmp/outputs/production-index-admin-denial-audit-smoke-20260615.json`，状态 `pass`。
- 专项权限 smoke 用户：`index-denial-e2e-20260615T120014Z`。
- 普通审计角色访问 `/api/v1/index/versions/activate` 返回 `403`，错误为 `index operation requires it-admin role`。
- 管理员角色查询 `/api/v1/audit/logs?action=index-admin-access-denied&user_identifier=index-denial-e2e-20260615T120014Z` 返回 `200`，`matching_count=1`，store 为 `SqlAlchemyAuditLogStore`。

边界：

- 本轮只补齐索引管理写接口拒绝审计，不等于完成真实登录会话、科室级授权、组织模型或全站 RBAC。
- 生产查询仍为 `fallback_used=true`，不代表真实生成模型能力可用。

### 2.14 国家规章平台文档增量入库与生产激活状态

验收日期：`2026-06-15`

本轮国家规章平台资料补充已完成生产激活，结论为 `pass`。

数据与索引：

- 资料来源：`data/国家规章平台文档.zip`。
- 生产资料路径：`/opt/medical-audit/app/data/医保审核前期资料/全量法律/国家规章平台文档`。
- active index：`incremental-20260615-national-regulation-stable-20260615103344`。
- source package：`source-package-national-regulation-stable-incremental-20260615103344`。
- active 计数：`503` 个 source documents、`49051` 个 chunks、`49051` 条 embeddings。
- 本轮新增国家规章平台入库文档：`17` 个；新增 chunks：`66`。

验收证据：

- 固定 52 case 检索评测：`52/52` 通过。
- 新增文档检索评测：`6/6` 通过。
- 新增文档答案评测：`4/4` 通过；仍为 citation fallback answer，不代表真实生成模型能力可用。
- 生产 E2E：`tmp/outputs/production-e2e-smoke-after-national-regulation-app-restart-20260615.json`，状态 `pass`。

异常与处置：

- 第一次全量重建候选 `full-rebuild-20260615093424` 因固定 52 case 回归为 `51/52` 未激活，并已置为 `inactive`。
- 激活后 `/pages/chat` 曾返回 `500`，日志为 `TemplateNotFound: chat.html`；复核确认不是本地缺模板或 wheel 缺模板，而是运行中 `uvicorn` 子进程持有旧导入路径。
- 已仅重启 `medical_audit_app` 修复；未修改 `medical_audit_pg`、`medical_audit_pgdata` 或共享 `ai_video_nginx`。重启后 `/pages/chat` 内外网均返回 `200`，重启后日志未再出现 `TemplateNotFound`。

### 2.15 门户配置写入拒绝审计生产部署状态

验收日期：`2026-06-15`

本轮已将门户配置写入拒绝审计部署到生产，结论为 `pass`。

部署事实：

- 部署提交：`6ae514cf994ff0d0da612d5ea9bcce82bb7df1bc`。
- 部署戳：`portal-config-denial-audit-20260615`。
- 写入前 DB 备份：`/opt/medical-audit/backups/db/pre-deploy-portal-config-denial-audit-20260615.sql.gz`，大小 `1025903476` bytes。
- 应用备份：`/opt/medical-audit/backups/app/pre-deploy-portal-config-denial-audit-20260615.tar.gz`。
- env 备份：`/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-portal-config-denial-audit-20260615`。
- nginx 备份：`/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-portal-config-denial-audit-20260615`。
- web 静态资产备份：`/opt/medical-audit/backups/web/audit-web-pre-deploy-portal-config-denial-audit-20260615.tar.gz`。

验收证据：

- 部署前状态巡检：`tmp/outputs/tencent-cloud-deployment-state-before-portal-config-denial-deploy-20260615.json`，状态 `pass`，确认部署前 `.deploy-sha=a3111bf615995bd03a95514c49447cd82087e5ab`。
- 部署后基础 smoke：`tmp/outputs/production-e2e-smoke-after-portal-config-denial-deploy-20260615.json`，状态 `pass`。
- 部署状态巡检：`tmp/outputs/tencent-cloud-deployment-state-after-portal-config-denial-deploy-20260615.json`，状态 `pass`，`issues=[]`。
- 生产前端验收：`tmp/outputs/production-frontend-acceptance-after-portal-config-denial-deploy-20260615.json`，状态 `pass`，覆盖 `21` 个路由、`42` 个检查，`p0_count=0`、`p1_count=0`。
- 专项权限 smoke：`tmp/outputs/production-portal-config-denial-audit-smoke-20260615.json`，状态 `pass`。
- 专项权限 smoke 用户：`portal-config-denial-e2e-20260615T122012Z`。
- `guest` 角色访问 `/api/v1/agents` 返回 `403`，错误为 `role is not allowed`。
- `guest` 角色访问 `/api/v1/projects/SELF-CHECK-FUND-20260607/members` 返回 `403`，错误为 `role is not allowed`。
- 管理员角色查询 `/api/v1/audit/logs?action=agent-access-denied&user_identifier=portal-config-denial-e2e-20260615T122012Z` 返回 `200`，`matching_count=1`，store 为 `SqlAlchemyAuditLogStore`。
- 管理员角色查询 `/api/v1/audit/logs?action=project-member-access-denied&user_identifier=portal-config-denial-e2e-20260615T122012Z` 返回 `200`，`matching_count=1`，store 为 `SqlAlchemyAuditLogStore`。

边界：

- 本轮只补齐智能体和项目成员写接口的未知角色拒绝审计，不等于完成真实登录会话、科室级授权、组织模型或全站 RBAC。
- 生产查询仍为 `fallback_used=true`，不代表真实生成模型能力可用。

### 2.16 部署脚本 SSH stdin 修复生产部署状态

验收日期：`2026-06-16`

该轮已将部署脚本 SSH stdin 修复部署到生产，结论为 `pass`。

失败链路：

- PR #95 `codex/deploy-tooling-debt-fix` 已合并到 `main`，merge commit 为 `8281a0ea123cbbd5df519e20fd5c4cdf77b87e30`；生产部署验证失败，DB 备份已完成但本地 SSH 仍挂起，生产 `.deploy-sha` 未更新。
- PR #96 `codex/deploy-pgdump-stdin-fix` 已合并到 `main`，merge commit 为 `33522d24983b188587feed3b9a45cad066c87b4a`；生产部署验证失败，plain `docker exec ... pg_dump` 仍未解决远端脚本消耗 stdin 的根因，生产 `.deploy-sha` 未更新。
- PR #97 `codex/deploy-ssh-stdin-fix` 已合并到 `main` 并完成生产部署，merge commit 为 `4901d6705a60494542f42b98aa0e6766e3224114`；有效修复点为远端脚本式 `_ssh` 调用统一使用 `ssh -n`，`rsync` 传输调用保持原方式。

部署事实：

- 部署提交：`4901d6705a60494542f42b98aa0e6766e3224114`。
- 部署戳：`ssh-stdin-fix-20260616`。
- 写入前 DB 备份：`/opt/medical-audit/backups/db/pre-deploy-ssh-stdin-fix-20260616.sql.gz`，`gzip -t` 通过，大小约 `979M`。
- 应用备份：`/opt/medical-audit/backups/app/pre-deploy-ssh-stdin-fix-20260616.tar.gz`，大小约 `176M`。
- Web 静态资产备份：`/opt/medical-audit/backups/web/audit-web-pre-deploy-ssh-stdin-fix-20260616.tar.gz`，大小约 `430K`。
- 当时远端 `.deploy-sha`、本地 `main` 和 `origin/main` 均为 `4901d6705a60494542f42b98aa0e6766e3224114`。
- `medical_audit_app` 与 `medical_audit_pg` 均为 `running healthy`；共享入口 `ai_video_nginx nginx -t` 通过。

验收证据：

- 部署后基础 smoke：`tmp/outputs/production-e2e-smoke-after-ssh-stdin-fix-deploy-20260616.json`，状态 `pass`。
- 部署状态巡检：`tmp/outputs/tencent-cloud-deployment-state-after-ssh-stdin-fix-deploy-20260616.json`，状态 `pass`，`issues=[]`。
- 生产前端验收：`tmp/outputs/production-frontend-acceptance-after-ssh-stdin-fix-deploy-20260616.json`，状态 `pass`，覆盖 `21` 个路由、`42` 个检查，`p0=[]`、`p1=[]`。

边界：

- 该轮只关闭部署脚本在 DB 备份完成后挂起的工程脆弱点，不代表新增产品功能、权限模型、生成模型、schema 或生产配置能力。
- #95/#96 只作为失败验证和根因收敛记录，不能写成已生效生产部署。

## 3. 债务分级

| 等级 | 定义 | 处理原则 |
| --- | --- | --- |
| P0 | 会导致产品能力被误判、生产交付边界不清、真实业务验收不可执行或安全合规风险扩大的债务 | 先处理，不进入新功能扩张 |
| P1 | 不阻断当前生产运行，但阻断 V1.0 闭环、UAT 或持续开发效率的债务 | 进入最近两个开发批次 |
| P2 | 影响维护成本、认知清晰度、目录卫生和长期扩展性的债务 | 纳入持续治理 |

## 4. P0 债务台账

| 编号 | 类型 | 债务 | 当前证据 | 影响 | 处置计划 | 完成门禁 |
| --- | --- | --- | --- | --- | --- | --- |
| P0-01 | 产品集成债务 | 门户核心模块仍以静态数据和本地 state 为主 | `/agents` 和 `/projects` 已完成生产写入验收；`/analytics` 已完成生产上传解析、上传留存和历史记录验收；`/documents` 已完成生产查询、来源集合回显、文档权限接口、个人材料留存写入型验收、上传治理门禁表达验收和人工入索引审批状态机验收；其余模块仍多依赖 `portal-data` | 页面存在但业务闭环不完整，容易误判为功能已完成 | 下一步补生产级上传文件病毒扫描/DLP/脱敏/对象存储治理、真实认证权限、个人材料实际入索引、知识库/图谱/报告/整改页面 API | 新增/查询/刷新后数据仍存在；上传文件可追溯留存并通过治理门禁和人工审批状态机；前端测试、API 测试和生产写入验收通过 |
| P0-02 | 真实数据债务 | 生产验收主要基于受控脱敏 fixture | 生产文档明确 fixture 只证明链路 | 不能进入真实医院 UAT | 获取院方 DDL、字段字典、脱敏样本，执行 staging 验收 | `his-staging-acceptance` 对真实样本 PASS |
| P0-03 | AI 生成债务 | 线上答案生成 provider 未验证通过 | 2026-06-15 只读复核：生产仅 `KIMI_API_KEY=SET`，全部 `MEDICAL_AUDIT_KB_ANSWER_*` 均为 `UNSET`；本地 Anthropic smoke 使用 `claude-haiku-4-5-20251001` 仍返回 `401 invalid x-api-key`；历史 Kimi chat 403/401、fallback rate 100% | 不能宣称 AI 生成审计结论能力 | 按 `drafts/analysis/analysis-answer-provider-production-gate-plan-draft-20260615.md` 等待新的可用服务端 chat provider key；先跑 smoke 和真实答案评测，再决定是否写入生产 env；未通过前保持引用 fallback 为产品边界 | `answer-provider-smoke`、真实生成评测和生产 `--require-generated-answer` E2E 全部 PASS |
| P0-04 | 权限安全债务 | 真实用户、角色、科室、全站权限未完成 | 当前生产 API 仍主要依赖 `X-Role`、`X-User-Id`、Nginx 注入 `X-API-Key`；2026-06-15 已部署索引管理写接口拒绝审计，生产专项 smoke 证明非 `it-admin` 访问记录 `index-admin-access-denied` 并持久化到 `audit_log_events`；已部署智能体和项目成员写接口的未知角色拒绝审计，生产专项 smoke 证明 `guest` 访问记录 `agent-access-denied` 和 `project-member-access-denied` 并持久化到 `audit_log_events`；真实权限模型架构已固化到 `docs/architecture/architecture-auth-rbac-stable.md`；Phase A 后端兼容层已完成生产部署，新增 `CurrentUser`、`PermissionContext`、`it-admin -> system-admin` 归一化和统一 `auth_source=legacy-header` 审计 payload，生产专项 smoke 已验证旧/新角色兼容和关键写接口拒绝审计 | 无法满足生产级审计系统权限边界 | 下一步落 auth schema、真实会话、前端去硬编码 header、跨模块绕过测试和生产验收 | 未授权路径 401/403；审计日志记录访问拒绝；伪造 `X-Role` 无效；真实会话与角色模型验收通过 |
| P0-05 | 合规闭环债务 | 证书级电子签章、长期留存介质、对象存储和病毒扫描未完成 | 当前仅 HMAC 归档签名和本地附件归档 | 报告与归档不能作为完整合规交付 | 设计签章、对象存储、扫描、留存介质方案 | 归档包、签章、验签和恢复演练通过 |
| P0-06 | 状态源债务 | 本地分支、生产 SHA、远端主线、多个 worktree 容易产生认知漂移 | 本轮已将生产 SHA、`origin/main` 和文档状态同步到 `b425e2123d55a94dc6b6c800b806384eec1de679`；PR #103 为当前已生效生产部署，PR #101 为已生效生产部署历史记录，PR #95/#96 仍为失败验证记录，PR #97 为已生效部署工具链修复；本地仍有多个 worktree 和未跟踪参考目录 | 后续部署可能混入非目标状态 | 后续功能继续从干净 `codex/` 分支切出，部署前核验远端 main、生产 `.deploy-sha`、docs-only 差异和未跟踪排除清单 | `git status` 清晰；PR、部署 SHA、文档一致 |

## 5. P1 债务台账

| 编号 | 类型 | 债务 | 当前证据 | 影响 | 处置计划 | 完成门禁 |
| --- | --- | --- | --- | --- | --- | --- |
| P1-01 | 本地/生产一致性债务 | 本地 Kimi 运行态缺少同生产一致的安全加载流程 | 本地缺少 `KIMI_API_KEY` 时 PostgreSQL backend load 返回 409 | 本地复现生产问题困难 | 建立本地 Kimi profile 文档和安全 env 加载脚本 | 本地只读 UI smoke 可复现生产检索 |
| P1-02 | 知识库资料债务 | `pending_files=13` 未闭合 | 图片需 OCR 或替换，压缩包需解包去重 | 新资料增量发布质量受限 | 执行 pending 文件分类处理和候选索引流程 | pending 队列归零或有明确豁免记录 |
| P1-03 | HIS 产品化债务 | HIS 字段映射、确认、版本发布缺少页面化流程 | CLI 已有，UI 未闭合 | 院方业务人员难以参与字段确认 | 补字段映射 UI、确认记录和版本发布门禁 | 字段映射可由页面提交并进入审计日志 |
| P1-04 | 规则治理债务 | 结构化规则、医院本地覆盖和规则评审发布流程未产品化 | `CHARGE-RULE-001` 已有工程路径，规则库 UI 只读 | 规则变更不可治理 | 建立规则版本、评审、发布、回滚 UI/API | 规则发布和回滚有审计日志 |
| P1-05 | UAT 债务 | 缺少院方 UAT 用例、验收记录和签收材料 | 现有 smoke 主要为工程验收 | 无法形成客户验收证据 | 建立 UAT case matrix、验收脚本和问题闭环 | P0/P1 UAT 问题为 0 |
| P1-06 | 文档同步债务 | 正式文档存在阶段性漂移风险 | 本轮已同步开发计划、部署工作流和本台账，后续仍需随功能落地持续校准 | 新成员和部署决策容易误读 | 持续同步 PRD、开发计划、部署工作流和本台账 | 正式文档状态一致 |

## 6. P2 债务台账

| 编号 | 类型 | 债务 | 当前证据 | 影响 | 处置计划 | 完成门禁 |
| --- | --- | --- | --- | --- | --- | --- |
| P2-01 | 目录治理债务 | 本地存在 `.DS_Store`、缓存、参考材料和多个草稿目录 | 根目录和子目录有本地系统文件及未跟踪目录 | 降低可导航性，增加误提交风险 | 保留必要参考资料，清理或归档无效本地文件 | `git status` 只显示本轮目标资产 |
| P2-02 | 仓库体积债务 | 当前工作区约 `3.7G` | `du -sh .` | clone、索引和扫描成本升高 | 复核 `data/`、`node_modules/`、缓存和历史输出 | 大文件有明确归属和忽略规则 |
| P2-03 | 测试资产债务 | 生产验收脚本已具备，但产品模块联调用例不足 | 前端 acceptance 偏语义可达性 | 难捕捉持久化和权限回归 | 为 agents/projects/analytics 增加 API+UI E2E | 新模块每次 PR 自动跑关键路径 |

## 7. 执行路线

### Phase 0：状态冻结与台账同步

目标：完成当前事实冻结、债务台账、正式文档同步和后续分支边界。

任务：

- 新增本台账。
- 同步开发计划中的当前状态。
- 同步腾讯云部署工作流中的 2026-06-14 生产状态。
- 明确后续功能开发必须从干净 `codex/` 分支开始。

完成门禁：

- `git status --short --branch` 可解释。
- 生产状态审计通过。
- 正式文档不再把已完成门户壳层写成未完成，也不把静态 UI 写成后端闭环。

### Phase 1：基线复核

状态：已完成，完成日期 `2026-06-14`。

目标：确保本地、生产、测试和部署边界一致。

任务：

- 执行 Python `pytest`、`ruff`、`mypy`。
- 执行前端 `lint`、`typecheck`、`test`、`build:static`。
- 执行生产只读 smoke。
- 在备份后执行写入型 smoke。
- 输出基线验收报告。

完成门禁：

- 代码测试已通过，剩余 `StarletteDeprecationWarning` 记录为 P2 依赖观察项。
- 生产只读 smoke 已通过。
- 生产前端语义验收已通过，`p0=[]`，`p1=[]`。
- 写入前 DB 备份已通过完整性校验。
- 生产写入型 smoke 已通过，创建并更新 `review-task-0011`。
- 本地与生产的 Kimi 配置差异仍保持文档化边界：生产 Kimi embedding 可用，本地缺少 `KIMI_API_KEY` 时不能加载 PostgreSQL 检索后端。

### Phase 2：产品集成债务治理

目标：把门户核心页面从 UI 壳层推进到可持久化业务模块。

优先顺序：

1. 智能体 CRUD 和提示词版本：生产写入型 E2E 已完成；提示词版本治理、上下架、删除/停用和权限生效待后续阶段。
2. 项目成员管理 API 和页面持久化：生产写入型 E2E 已完成；真实权限、邀请审批、禁用/移除和成员权限生效待后续阶段。
3. 表格上传分析后端和工作簿解析任务：生产上传解析、上传留存和历史记录写入型 E2E 已完成；病毒扫描、脱敏改写、对象存储、下载权限隔离和正式工作簿治理待后续阶段。
4. 文档检索 API-first 接入：生产查询、搜索历史写入信号、来源集合回显、文档权限接口、个人材料留存写入型 E2E 和人工入索引审批状态机已完成；真实认证、生产级病毒扫描、DLP/脱敏改写、对象存储、下载权限隔离、个人材料实际入索引和生产搜索历史列表/回填专项验收待后续阶段。
5. 知识库、图谱、报告、整改页面逐步接真实 API。

完成门禁：

- 刷新页面后新增数据仍存在。
- API 测试、前端测试和最小 E2E 均通过。
- 生产前端变更必须执行 `pnpm production:frontend-acceptance -- --base-url https://audit.lute-tlz-dddd.top --admin-role it-admin`，且 `p0=[]`、`p1=[]`、审计日志查询和导出 API 均满足无角色 `403`、管理员角色 `200`。
- 页面文案不再暗示未完成能力已经完成。

### Phase 3：真实 HIS 审计 MVP

目标：完成单院真实样本的 HIS 审计闭环。

任务：

- 获取院方 DDL、字段字典、脱敏样本和验收口径。
- 完成字段映射确认和版本发布。
- 执行 staging 导入、snapshot、规则运行、疑点入库。
- 形成复核任务、证据链、底稿和报告草稿。

完成门禁：

- 真实样本 `his-staging-acceptance` PASS。
- `CHARGE-RULE-001` 对真实样本可复核运行。
- 疑点证据链可追溯到原始行、规则版本和知识依据。

### Phase 4：安全与合规闭环

目标：补齐生产审计系统所需的权限和归档能力。

任务：

- 建立用户、角色、部门和权限模型。
- 迁移 API secret、Kimi key、HMAC secret 到服务器级 secret 或 Docker secret。
- 接入对象存储、病毒扫描、证书级电子签章和长期留存介质方案。
- 完成未授权访问、签章验签、归档恢复演练。

完成门禁：

- 权限绕过测试失败即阻断。
- 签章和归档验签可独立复现。
- 备份恢复演练通过。

### Phase 5：UAT 与生产硬化

目标：形成可交付给院方的验收包。

任务：

- 建立 UAT case matrix。
- 建立问题登记、修复、复测和签收流程。
- 执行性能、备份恢复、回滚、监控告警和共享 Nginx 回归。

完成门禁：

- UAT P0/P1 为 0。
- 回滚方案可执行。
- 生产监控、告警、备份、恢复均有证据。

## 8. 后续执行规则

- 新功能开发必须从干净 `codex/` 分支开始。
- 不在生产部署同步中包含 `drafts/`、`ref/`、`opendesign/`、`tmp/`、密钥或 env 文件。
- `ai_video.pem` 保留在本地，不进入 Git，不删除。
- 每次声称完成前必须同时给出代码证据、页面证据、测试证据和生产边界。
- 每次生产写入前必须先有备份和回滚路径。
- 每次文档同步必须明确 `fixture`、`fallback`、`dry-run`、`read-only` 和 `production` 的边界。
