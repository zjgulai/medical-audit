---
title: AI智能审计管理系统 V1.0 开发计划
doc_type: other
module: product
topic: medical-audit-development-plan
status: stable
created: 2026-03-15
updated: 2026-06-15
owner: self
source: human+ai
---

# AI智能审计管理系统 V1.0 开发计划

## 1. 当前基线

本计划以 `AI智能审计管理系统 V1.0 PRD` 为母版，并以当前已部署的 AuditScope 知识库网站为工程基线。

当前已完成：

- 知识库查询引擎已实现 `检索 + 引用型回答 + 原文预览 + 索引管理`。
- 线上入口已部署到 `https://audit.lute-tlz-dddd.top/pages/chat`。
- PostgreSQL + pgvector active index 已上线，当前 active 版本为 `full-rebuild-20260603085815`。
- 当前 active 计数为 `486` 个源文档、`48985` 个 chunks、`48985` 条 embeddings。
- 已具备生产 E2E smoke、视觉基线和增量 dry-run 验收脚本。
- 当前复核任务台已切换为 PostgreSQL 持久化，支持任务创建、状态更新、复核意见、复核结论和任务级导出。
- 已补齐 `review_tasks`、`review_actions`、`review_comments` 的 SQLAlchemy 模型、repository 基础读写和正式 SQL schema；当前仍不能视为生产级案件系统。
- 已补齐 V1.0 第一批业务数据底座：`audit_projects`、`audit_data_snapshots`、`audit_snapshot_rollbacks`、`audit_tasks`、`audit_runs`、`audit_rules`、`rule_versions`、`audit_findings`、`finding_evidence_items`，支持项目、快照、回滚审计、任务、运行批次、规则版本、疑点和证据项的最小可追溯链路。
- 已新增开发期疑点清单页 `/pages/audit-findings`，支持展示规则疑点、导出单条疑点 JSON，并从疑点创建复核任务。
- 已新增 HIS 输入契约第一批：`his_source_batches`、`his_table_schemas`、`his_field_mappings`，并补齐收费合规字段映射完整性校验器。
- 已新增 HIS DDL 自动解析器和 CLI `his-ddl-parse`，支持从离线 DDL 文本解析表、字段、主键、时间字段、字段注释、DDL hash，并生成 Markdown/JSON 解析报告。
- 已新增 HIS 脱敏样本质量报告 CLI `his-sample-quality`，支持 CSV/JSONL 样本扫描、DDL 对齐、缺失字段、必填空值、重复主键和行数字段画像检查。
- 已新增 HIS 脱敏样本 raw staging 导入 CLI `his-staging-import`，支持默认 dry-run、显式 `--execute` 写入 `his_staging_rows`、按 source batch 和 table schema 绑定原始行、行号、row hash 和文件来源。
- 已新增 `CHARGE-RULE-001` staging 标准输入转换器，可从 `his_staging_rows` 和 `his_field_mappings` 构造 `ChargeDetailRecord`，并复用既有规则执行器产生疑点和 `needs_evidence` 结果。
- 已新增 HIS 数据快照计划 CLI `his-snapshot-plan`，支持在样本质量报告通过后生成 `AuditDataSnapshotCreate` payload、表级 row_counts 和快照 checksum。
- 已新增 HIS 数据快照受控入库 CLI `his-snapshot-apply`，支持默认 dry-run、显式 `--execute` 写入 `audit_data_snapshots`、项目存在性校验、重复 `snapshot_key` 阻断和 Markdown/JSON 入库报告。
- 已新增 `charge-rule-001-staging-run` CLI，支持从 HIS staging 行驱动 `CHARGE-RULE-001` dry-run，并在显式 `--execute` 后写入 `audit_findings` 和 `finding_evidence_items`。
- 已新增 `his-snapshot-rollback-audit` CLI，支持默认 dry-run 计算快照回滚影响面，并在显式 `--execute` 后写入 `audit_snapshot_rollbacks`，不删除历史快照、任务、run 或疑点。
- 已新增 `his-staging-acceptance` CLI，支持只读验收生产 staging 链路，覆盖项目、source batch、staging rows、table schema、字段映射门禁、snapshot、audit task、audit run、rule version、疑点证据和可选回滚目标。
- 已新增 `case-review-report-gate` CLI，支持正式报告前只读门禁，覆盖疑点证据、复核任务绑定、复核状态闭合、复核意见/结论、确认违规底稿和负责人确认。
- 复核任务台已新增任务级报告准备度预检、承办人、底稿状态、底稿编号、底稿说明、负责人确认状态、确认人和确认时间字段，并进入 Markdown/JSON 导出。
- 复核任务台已新增附件清单登记、附件文件归档、任务级报告草稿 Markdown/JSON 导出、正式报告签发冻结、签发后整改跟踪、任务级结案门禁和关闭后只读锁定；确认违规任务必须登记或上传附件后才能通过报告草稿门禁，签发后正式报告正文按 `sha256` 冻结，整改事项绑定已签发报告编号和正文 `sha256`，整改未验收前不得结案，结案后状态、附件、签发和整改写接口均被阻断，并通过 `audit_log_events` 支持持久化操作日志。
- 已新增审计日志台 `/pages/audit-logs`、持久化审计日志查询 API `/audit/logs` 和 JSON 导出 API `/audit/logs/export`，支持按任务、用户、动作和时间范围追踪数据库审计链。
- 已新增审计日志治理策略：仅 `it-admin` 和 `department-head` 可查询或导出持久化审计日志；未授权访问记录为 `audit-logs-access-denied`；响应和导出对敏感字段执行 response-only 脱敏；当前策略保留周期为 `180` 天。
- 已新增 `audit-log-retention` CLI，支持默认 dry-run 生成保留期计划，并在显式 `--execute` 后先写原始 JSONL 归档和 `sha256`，再删除本批次保留期外的 `audit_log_events`。
- 已新增审计日志归档签名链：`audit-log-retention --signature-output` 可写出 detached HMAC-SHA256 签名 manifest，记录 `archive_sha256`、签名主体、`key_id` 和上一签名 `sha256`；`audit-log-archive-verify` 可只读验签并识别归档篡改。
- 已新增审计日志受控归档目录策略：`audit-log-retention --archive-root` 自动生成 `audit-log-events/YYYY/MM/DD/<batch-key>.jsonl` 和同目录签名 manifest，显式归档/签名路径不能逃出归档根目录。
- 已新增审计日志归档根目录巡检 CLI `audit-log-archive-audit`，可递归验签 archive root 下的签名 manifest，识别归档文件缺失、路径逃逸、sha256 不匹配和签名失败。
- 已新增生产侧审计日志归档巡检脚本 `scripts/run-audit-log-archive-audit.py` 和腾讯云 Compose 挂载策略，支持按 cron/systemd timer 执行只读巡检、维护 latest JSON 报告，并在配置 webhook URL 后对失败或脚本异常发送外部告警。
- 已完成 `AI智能审计管理系统` 门户壳层生产部署，当前生产静态路由覆盖 `/workspace`、`/chat`、`/agents`、`/agent-market`、`/knowledge-base`、`/documents`、`/analytics`、`/graph`、`/rules`、`/reports`、`/remediation`、`/archive`、`/projects`、`/guided-check`、`/knowledge-query` 和 `/findings`。
- 已将参考系统 UI 要求转化为门户信息架构，完成侧边导航、多页面工作区、提示词型智能体入口、知识库三类展示、文档检索入口、上传表格分析入口、项目成员管理入口、图谱/规则/报告/整改/归档只读入口。
- 已新增生产前端语义验收脚本 `scripts/run-production-frontend-acceptance.mjs`，覆盖桌面和移动视口下的门户路由、关键文案、文件上传入口、控制项和横向溢出检查。
- 已完成提示词型智能体生产写入型 E2E：`/api/v1/agents` 使用 `SqlAlchemyAgentStore`，新增智能体 `agent-custom-ec210547464a` 后刷新可读，智能体列表从 `3` 增至 `4`。
- 已完成项目成员管理生产写入型 E2E：`/api/v1/projects` 和 `/api/v1/projects/{project_key}/members` 使用 `SqlAlchemyProjectMemberStore`，`CATALOG-LIMIT-202606` 新增成员 `member-custom-e152673f93f9` 后刷新可读，项目成员数从 `4` 增至 `5`。
- 已完成 AI 数据分析生产上传 E2E：`/api/v1/analytics/table-upload` 可解析 CSV 和 XLSX，返回字段画像、重复行、质量提示和金额/就诊/医保支付等审计信号；不支持的扩展名返回 `422`。
- 已完成文档检索生产查询 E2E：全库重复收费、法规政策过滤和医保目录过滤查询均返回引用证据、证据分组和可打开的原文预览。
- AI 数据分析上传留存和历史记录已完成生产部署与写入验收：新增 `analytics_upload_records`、受控上传文件留存、`GET /api/v1/analytics/table-uploads` 历史列表和 `/analytics` 上传历史侧栏；生产 API 上传、页面上传、历史查询、DB 行和宿主机留存文件均已验证。
- 文档检索搜索历史持久化已完成本地实现和联调：`/api/v1/query` 返回 `query_log_id`，`GET /api/v1/query/logs` 可从 `query_logs` 持久化读取历史，`/documents` 可展示、刷新和回填搜索历史；尚未生产部署。
- 真实权限模型与 RBAC 架构基线已固化到 `docs/architecture/architecture-auth-rbac-stable.md`，明确用户、部门、角色、权限矩阵、服务端会话、legacy header 迁移和验收门禁。
- RBAC Phase A 后端兼容层已完成代码实现和本地测试：新增 `CurrentUser`、`PermissionContext`、legacy header 归一化和统一审计 payload；`/agents`、`/projects`、`/documents`、`/query`、`/audit/logs`、`/index` 相关后端入口已收敛到统一用户上下文；尚未生产部署。

当前未完成：

- 门户核心模块的后端持久化和真实业务闭环：`/agents` 和 `/projects` 已完成生产持久化写入验收；`/analytics` 已完成生产上传解析、上传留存和历史记录验收，但病毒扫描、脱敏留存、对象存储、下载权限隔离和正式工作簿治理仍未完成；`/documents` 已完成生产查询验收，搜索历史持久化已完成本地实现但尚未生产部署，仍需个人知识库上传和文档权限模型。
- 智能体提示词版本治理、上下架、删除/停用和权限生效仍未完成；当前只验证新增提示词型智能体持久化。
- 多数门户页面仍由 `web/src/lib/portal-data.ts` 静态数据驱动；当前可作为首期只读展示和验收壳层，不能写成完整业务 API 闭环。
- 顶部多标签和历史对话区仍是门户交互层能力，尚未形成服务端持久化会话系统。
- HIS 字段映射页面、院方字段确认流和映射版本发布流。
- 结构化规则执行器、医院本地覆盖规则和规则评审发布流程。
- 附件对象存储、病毒扫描、权限隔离、电子签章、独立整改数据库表和案件级整改归档流。
- 用户、角色、科室、全站权限控制仍未完成；当前只完成 RBAC 架构基线和 Phase A 后端兼容层，尚未落 auth schema、真实登录会话、前端去硬编码 header、生产部署、跨模块绕过测试、证书级非对称电子签章、审计日志长期保留介质接入和真实外部告警端点配置。
- 知识库新增源文件后的生产级增量写入和 active 切换闭环。
- 真实医院 HIS 数据、院方 UAT 用例、问题登记、复测记录和验收签收材料。
- Kimi Code 当前仅验证为 embedding provider；真实线上答案生成 provider 仍未通过预检和评测。

## 2. 下一阶段目标

V0.3 门户壳层已经部署到生产，提示词型智能体、项目成员管理、AI 数据分析上传解析、上传留存/历史记录和文档检索生产查询已完成生产验收；文档搜索历史已完成本地实现，下一步需要生产部署和写入验收。下一阶段不再继续盲目补页面，而是继续处理产品集成债务：优先完成文档搜索历史生产验收，再推进个人知识库上传、文档权限模型和上传文件治理，把现有审计证据链能力统一到可验收门户。

产品集成债务收敛后，继续把项目从“知识库支撑层 + 门户壳层”推进到“单院 HIS 专项审计 MVP”。

阶段目标：

- 固化当前知识库查询引擎为可回滚、可验收、可复测的 V0.2 基线。
- 收敛 V0.3 产品集成债务：文档搜索历史生产部署验收、个人知识库/权限模型、上传文件病毒扫描/脱敏/对象存储治理、关键门户页面 API 化、智能体提示词版本治理和项目成员权限治理。
- 锁定首个 HIS 专项审计场景，并拿到 DDL、字段字典和脱敏样本。
- 建立 V1.0 最小业务数据模型：审计项目、数据快照、规则版本、运行批次、疑点、复核、底稿、整改。
- 实现第一个 0/1 合规判定场景，输出可追溯疑点证据包。
- 将当前 PostgreSQL 任务级复核推进为案件级复核流。
- 形成可供院方 UAT 的任务级底稿和报告导出。

## 3. 产品取舍

### 3.1 优先做

- `PORTAL-01`：`AI智能审计管理系统` 品牌和门户壳。
- `PORTAL-02`：左侧 9 模块导航和真实页面。
- `PORTAL-03`：顶部多标签工作区。
- `AGENT-01/02/03`：提示词型智能体列表、新增和智能体广场。
- `DOC-01`：参考系统式文档检索首页。
- `DATA-01/02`：上传表格 AI 数据分析和审计数据分析入口。
- `PROJECT-01/02`：项目列表和项目成员管理 UI。
- `HIS-01`：HIS DDL 导入、字段字典、字段映射和脱敏规则。
- `HIS-02`：审计数据快照版本。
- `HIS-03`：专项审计任务。
- `RULE-01`：结构化规则表。
- `RULE-03`：0/1 合规判定。
- `AUDIT-01`：数据库持久化人工复核。
- `AUDIT-02`：底稿生成。
- `REPORT-01`：报告导出。
- `RECT-01`：整改跟踪。
- `KB-05`：索引发布、回滚和 reload 后验收闭环。

### 3.2 暂不做

- 多院多租户。
- 移动端。
- LIS、PACS、财务系统接入。
- 复杂多轮智能体编排。
- 跨行业审计专题交付；财政、农业、国企、采购等专题当前只作为 UI 参考。
- 无引用的生成模型审计结论。
- 复杂风险评分模型。
- 大而全规则后台。
- 全量 OCR 能力。

## 4. 推荐首个专项场景

首个专项场景建议选择“收费合规 / 重复收费与目录限制核验”。

选择理由：

- 与现有知识库资料强相关，已有医保目录、智能监管规则和风险负面清单可作为依据。
- HIS 数据通常可从费用明细、医嘱、诊断、项目目录、科室、患者就诊记录中获得。
- 0/1 判定口径更适合 MVP，不必一开始引入复杂模型评分。
- 疑点证据包容易解释：原始费用行、匹配规则、计算过程、知识依据引用。

备选场景：

- 门诊超量开药。
- 医保目录限制条件核验。
- 诊断编码与手术操作编码不符。

最终场景必须由院方审计科和信息科确认，确认前不进入正式 HIS 开发。

## 5. 里程碑规划

| 里程碑 | 周期 | 目标 | 退出标准 |
| --- | ---: | --- | --- |
| M0 | 1 周 | 固化知识库与部署基线 | 当前变更原子提交，生产 E2E、视觉基线、增量 dry-run、回滚文档通过 |
| M1 | 1-2 周 | 锁定首个专项场景和数据输入 | HIS DDL、字段字典、脱敏样本、报告模板、验收口径确认 |
| M2 | 2 周 | 建立 V1.0 业务数据底座 | 数据快照、规则、任务、运行批次、疑点、复核、底稿、整改 schema 评审通过 |
| M3 | 2-3 周 | 实现首个 0/1 判定场景 | 脱敏样本可导入、可运行、可产出疑点和证据包 |
| M4 | 2 周 | 复核、底稿、报告、整改闭环 | 审计员可复核，负责人可确认，任务底稿和报告可导出 |
| M5 | 1-2 周 | UAT 前加固 | 权限、审计日志、备份、回滚、部署脚本、E2E 套件通过 |

## 6. Sprint 任务拆解

### Sprint 0：当前基线收口

目标：把已上线的知识库网站变成可持续开发的稳定基线。

任务：

- 拆分并提交当前未提交改动，避免 UI、部署、E2E、文档混在一个不可审查变更中。
- 执行并保留 `run-production-e2e-smoke.py`、视觉基线、远端增量 dry-run 结果。
- 已补充索引回滚就绪审计；candidate 激活后已完成真实 rollback rehearsal，并已切回新 active `full-rebuild-20260603085815`。
- 已补充 candidate 发布就绪审计；旧 active-key artifact 和旧 candidate artifact 均被安全阻断，数据库计数未变化。
- package-aware chunk id 修复已部署到腾讯云生产镜像，并重建 fixed candidate `full-rebuild-20260603085815`。
- fixed candidate 的 `pgvector-import` dry-run 和发布就绪审计通过，`chunk_collision_check.collision_count=0`，`safe_to_execute_candidate_write=true`。
- 已执行受控 `pgvector-import --execute --index-version-status candidate`，candidate `full-rebuild-20260603085815` 已写入生产库。
- candidate PostgreSQL 固定 52 case 检索评测通过，`recall@5=100%`、`citation_hit_rate=100%`、`preview_location_success_rate=100%`。
- candidate PostgreSQL fallback 答案评测通过，8 case `pass_rate=100%`，但 `fallback_rate=100%`，不代表真实 chat model 生成能力。
- 已执行受控 `index-activate`，`full-rebuild-20260603085815` 已成为 active，`full-rebuild-20260531142344` 已变为 inactive。
- 激活后运行态 PostgreSQL search backend 已重载，查询引用确认来自新 active 版本。
- 激活后线上综合评测通过：52 case 检索、8 case fallback 答案、UI smoke 均通过阈值。
- 激活后生产只读 E2E smoke 通过，rollback readiness 通过。
- 真实 rollback rehearsal 已执行：先切回旧版本 `full-rebuild-20260531142344`，reload PostgreSQL 后端并通过 smoke/综合评测；再切回 `full-rebuild-20260603085815`，reload PostgreSQL 后端并通过 smoke/综合评测。
- `pending_files=13` 已完成来源分类：`11` 个图片需 OCR 或替换为文本/xlsx 原件，`2` 个压缩包需解包、去重和范围审查。
- 明确 `KIMI_API_KEY` 从远端 env 迁移到 Docker secret 或服务器级 secret 的方案。

验收：

- `ruff format --check .`
- `ruff check .`
- `mypy src tests scripts/...`
- `pytest -q`
- 公网只读 E2E `pass`
- 回滚演练文档化

### Sprint 1：HIS 输入与场景定稿

目标：把外部依赖变成可开发输入。

任务：

- 输出首个专项场景子 PRD。当前候选草稿：`drafts/docs/product-prd-charging-compliance-scenario-draft-20260604.md`。
- 建立 HIS DDL 收集模板。当前交付模板草稿：`drafts/docs/workflow-his-data-delivery-template-draft-20260604.md`。
- 建立字段字典模板：表名、字段名、类型、主键、时间字段、业务含义、脱敏规则。
- 建立脱敏样本交付规范。
- 建立院方验收样本标注规范。
- 确认报告模板和签字流程。

验收：

- 审计科确认审计场景。
- 信息科确认数据表来源。
- 至少拿到一版脱敏样本或可生成等价 fixture 的 DDL。
- 准确率口径明确到“按疑点条目、病例、费用明细或任务”。

### Sprint 2：业务数据模型与迁移

目标：补齐 V1.0 主业务数据库，而不是继续依赖进程内状态。

建议新增表：

| 模块 | 表 |
| --- | --- |
| 用户权限 | `users`、`roles`、`user_roles`、`departments` |
| 审计项目 | `audit_projects`、`audit_tasks`、`audit_runs` |
| 数据快照 | `audit_data_snapshots`、`snapshot_tables`、`snapshot_files` |
| HIS 映射 | `his_table_mappings`、`his_field_mappings` |
| 规则 | `audit_rules`、`rule_versions`、`rule_evidence_links` |
| 疑点 | `audit_findings`、`finding_evidence_items` |
| 复核 | `review_tasks`、`review_actions`、`review_comments` |
| 底稿报告 | `working_papers`、`audit_reports`、`report_exports` |
| 整改 | `rectification_items`、`rectification_events` |
| 审计日志 | `audit_log_events` |

当前已落地：

- `review_tasks`、`review_actions`、`review_comments` 已进入 `sql/knowledge-query-schema.sql`。
- `ReviewTaskRepository` 已覆盖复核任务创建、操作流水追加、评论追加、按 ID 读取和列表读取。
- `audit_projects`、`audit_data_snapshots`、`audit_snapshot_rollbacks`、`audit_tasks`、`audit_runs`、`audit_rules`、`rule_versions`、`audit_findings`、`finding_evidence_items`、`audit_log_events` 已进入 `sql/knowledge-query-schema.sql`。
- `AuditWorkflowRepository` 已覆盖项目、数据快照、快照回滚审计、审计任务、规则、规则版本、运行批次、疑点、证据项的基础写入，以及按疑点编号和运行批次追溯查询。
- `his_source_batches`、`his_table_schemas`、`his_field_mappings` 已进入 `sql/knowledge-query-schema.sql`。
- `HisIngestionRepository` 已覆盖 HIS 交付批次、表结构和字段映射的基础写入，以及按交付批次读取字段映射。
- 收费合规字段映射校验器已覆盖必需字段缺失、重复目标字段、必需字段 nullable、敏感字段缺失脱敏规则，未通过时不得生成正式数据快照。
- `his-ddl-parse` 已覆盖开发期 DDL 自动解析，可生成 HIS 表结构解析报告和可转入 `HisTableSchemaCreate` 的结构化负载。
- `his-sample-quality` 已覆盖开发期脱敏样本质量报告，可在写入 staging 前检查 CSV/JSONL 样本与 DDL 的字段、行数、必填空值和主键重复。
- `his_staging_rows` 已进入 `sql/knowledge-query-schema.sql`，用于按交付批次、表结构、表名、行号、row hash 保存 HIS 脱敏样本原始行。
- `his-staging-import` 已覆盖开发期 raw staging 导入，默认 dry-run，只在显式 `--execute` 后写入 `his_staging_rows`，并在写入前校验样本质量报告、source batch、table schema 和重复 staging 行。
- `charge_rule_001_staging` 已覆盖从 raw staging 到 `ChargeDetailRecord` 的标准输入转换，转换问题按 warning/error 分层，缺少分组字段继续进入规则的 `needs_evidence`，非法数值或日期阻断转换。
- `his-snapshot-plan` 已覆盖开发期快照计划生成，可从通过的样本质量报告生成数据快照 payload 和稳定 checksum。
- `his-snapshot-apply` 已覆盖开发期快照计划受控入库，默认 dry-run，只在显式 `--execute` 后写入 `audit_data_snapshots`，并在写入前校验项目存在性和 `snapshot_key` 唯一性。
- `charge-rule-001-staging-run` 已覆盖开发期 staging 驱动规则运行，默认 dry-run，执行前校验 source batch、snapshot、audit task、audit run、rule version 一致性，显式 `--execute` 后写入疑点和规则依据证据项。
- `his-snapshot-rollback-audit` 已覆盖开发期快照回滚审计，默认 dry-run，执行前校验项目、from/to snapshot、重复 rollback key 和影响面，显式 `--execute` 后只写审计事件，不删除历史数据。
- `his-staging-acceptance` 已覆盖生产 staging 只读验收，执行时不写库，只输出 PASS/FAIL 报告和 JSON 证据。
- `case-review-report-gate` 已覆盖正式报告前只读门禁，执行时不写库，只基于现有疑点、证据、复核任务和任务 metadata 计算 PASS/FAIL。
- `/pages/review-tasks` 已覆盖任务级报告准备度预检、负责人确认记录、附件清单登记、服务端附件文件归档、报告草稿导出、正式报告签发冻结、签发后整改跟踪、任务级结案门禁和关闭后只读锁定，但仍未提供对象存储、病毒扫描、电子签章、独立整改数据库表、案件归档或权限系统。
- 当前仍是数据底座切片，不包含权限系统、多实例强一致编号、对象存储、病毒扫描、电子签章、独立整改数据库表或案件级整改归档流。

验收：

- SQL migration 可重复执行。
- schema 有回滚策略。
- 每个核心表有创建时间、更新时间、状态、版本或责任人字段。
- 关键查询有索引说明。
- 测试覆盖 repository 基础读写。

### Sprint 3：首个规则引擎闭环

目标：实现一个可解释的 0/1 合规判定，而不是生成式判断。

任务：

- 建立规则 DSL 或规则配置最小结构。
- 已建立 HIS 脱敏样本 raw staging 导入入口，样本通过质量门禁后才能写入 `his_staging_rows`。
- 已建立 `CHARGE-RULE-001` staging 标准输入转换入口，规则可以复用 raw staging 转换后的 `ChargeDetailRecord` 执行。
- 已建立收费合规 HIS 字段映射校验门禁，字段映射不完整时阻断后续快照生成。
- 已建立 HIS DDL 自动解析入口，脱敏样本导入前先解析 DDL 并固化字段字典版本。
- 已建立 HIS 脱敏样本质量报告入口，样本未通过字段/必填/主键质量门禁时不进入 staging 或快照生成。
- 已建立 HIS 数据快照计划入口，样本质量报告通过后才能生成 `AuditDataSnapshotCreate` payload。
- 已建立 HIS 数据快照受控入库入口，默认不写库，执行前必须通过 plan、项目存在性和 `snapshot_key` 唯一性校验。
- 已建立 `CHARGE-RULE-001` staging 规则运行入口，默认不写库，执行前必须通过上下文一致性、转换质量和重复疑点门禁。
- 已建立 HIS 数据快照回滚审计入口，默认不写库，执行前必须通过项目、目标快照和重复回滚键门禁。
- 已建立 HIS 生产 staging 只读验收入口，正式执行前必须通过数据链路、字段映射、任务运行、疑点证据和回滚目标门禁。
- 已建立案件级复核报告门禁入口，正式报告前必须通过疑点证据、复核任务、复核结论、底稿和负责人确认门禁。
- 实现审计任务创建和运行批次。
- 已实现 `CHARGE-RULE-001` 开发期最小执行器：合成收费明细 fixture、3 个重复收费正例、3 个可解释反例、2 个 `needs-evidence` 边界样本。
- 已实现规则输出到 `AuditFindingCreate` 的转换，支持将疑点和规则依据证据项写入 `audit_findings`、`finding_evidence_items`。
- 已新增开发期疑点清单页，支持读取 `audit_findings`、展示源记录定位和计算过程、导出疑点 JSON，并从疑点创建复核任务。
- 后续仍需接入真实 HIS 脱敏样本、正式规则配置发布和案件级复核流。

验收：

- 开发期 fixture 已覆盖同一数据快照 + 同一规则版本复跑稳定。
- 开发期 fixture 已覆盖疑点追溯到数据快照、运行批次、规则版本和规则依据证据项。
- 开发期页面已覆盖疑点清单展示、单条疑点 JSON 导出、疑点创建复核任务和 `review_task_id` 回写。
- 无法判定时进入 `needs-evidence` 或 `rule-issue`，不静默归为合规。

### Sprint 4：生产级复核与底稿

目标：从当前任务级 PostgreSQL 持久化推进到生产级案件复核流。

任务：

- 已将 `/pages/review-tasks` 改为 PostgreSQL 持久化。
- 已支持从查询结果和开发期疑点清单创建复核任务。
- 支持状态流转、复核意见、结论、附件清单登记和服务端文件归档。
- 支持任务级底稿 Markdown/JSON 导出。
- 支持任务级报告草稿 Markdown/JSON 导出。
- 支持任务级正式报告签发冻结和正式报告 Markdown/JSON 下载。
- 支持负责人确认。

验收：

- 服务重启后复核任务不丢失；多实例部署下的强一致编号和并发冲突处理仍需补齐。
- 复核记录可追溯到用户、时间、任务、疑点、证据包。
- 未复核疑点不能进入正式报告。

### Sprint 5：报告与整改闭环

目标：跑通 PRD 的“底稿/报告 -> 整改跟踪 -> 结案”。

任务：

- 定义报告模板字段。
- 已支持任务级报告草稿导出和正式报告签发冻结；后续补电子签章和报告模板管理。
- 已支持服务端附件归档；后续补对象存储、病毒扫描和权限隔离。
- 已支持任务级整改事项生成和整改状态流转。
- 后续补独立整改数据库表、责任科室权限、整改附件、验收退回和案件级整改闭环。
- 已支持任务级结案门禁。
- 已支持任务级关闭后只读锁定。
- 已支持任务级关闭后写阻断操作日志，并接入 `audit_log_events` 持久化底座。
- 已支持持久化审计日志查询页和 JSON 导出。
- 已支持审计日志访问角色校验和响应级敏感字段脱敏。
- 已支持审计日志保留期 dry-run 计划、显式归档和归档后清理。
- 已支持审计日志归档 HMAC-SHA256 防篡改签名 manifest 和只读验签命令。
- 已支持审计日志 archive root 标准目录布局和路径逃逸阻断。
- 已支持审计日志 archive root 定期巡检报告。
- 已支持生产侧 archive root 巡检脚本和部署挂载方案；腾讯云 cron 已启用，webhook 告警能力已具备，真实外部告警端点仍需配置和验收。
- 后续补案件级归档、结案审批、全站权限校验、证书级非对称电子签章和长期留存介质接入。

验收：

- 报告正文只纳入已确认违规疑点。
- 附录包含复核分布、规则版本、数据快照和知识依据版本。
- 所有整改事项闭环前不能结案。

### Sprint 6：上线加固

目标：达到单院试运行门槛。

任务：

- RBAC：Phase A 后端兼容层已完成；下一步按 `architecture-auth-rbac-stable.md` 落 auth schema、真实会话和前端去硬编码 header，再关闭浏览器侧 `X-Role` 授权。
- 审计日志：查询、导出、复核、规则更新、索引发布、回滚、报告导出。
- 数据备份和恢复演练。
- 证书续期 dry-run。
- 回滚演练。
- 压测：重点覆盖查询、任务运行、报告导出。
- UAT 脚本和培训材料。

验收：

- 生产 E2E、只读巡检、视觉基线、规则执行 E2E、报告导出 E2E 全部通过。
- P0/P1 问题清单为空。
- 院方签字进入 1 个月试运行。

## 7. 技术路线

当前不建议重启 Java/Vue 架构。原因是当前仓库已形成 Python/FastAPI/PostgreSQL/pgvector 的可运行基线，重启架构会推迟 HIS 审计闭环。

推荐路线：

- 后端继续使用 Python 3.12+、FastAPI、SQLAlchemy 2.0、Pydantic V2。
- 数据库继续使用 PostgreSQL + pgvector。
- 页面短期继续使用 FastAPI templates + CSS，优先完成业务闭环。
- 如果后续需要复杂前端状态管理，再启动 React/Next.js 前端项目，而不是现在迁移。
- 规则执行优先使用结构化规则 + Python 批处理，不引入复杂模型评分。
- 生成模型只用于语言组织和解释，不作为审计结论来源。

## 8. 验收门禁

每个迭代结束必须通过：

- 单元测试和类型检查。
- 数据 migration 可重复执行。
- 固定 E2E smoke。
- 权限和审计日志检查。
- 证据链抽样检查。
- 文档同步检查。

V1.0 总验收必须通过：

- 知识库查询结果可追溯。
- HIS 审计结果可追溯。
- 疑点证据包可复核。
- 底稿和报告可导出。
- 整改事项可关闭。
- 任务可结案。
- 试运行 1 个月问题闭环。

## 9. 当前最高优先级

排序如下：

1. 院方确认首个专项审计场景和 `CHARGE-RULE-001` 判定口径。
2. HIS DDL、字段字典、脱敏样本、验证集和报告模板交付。
3. V1.0 主业务数据库 schema 设计。
4. 收费合规 fixture 与数据质量报告。
5. 首个 0/1 规则执行器。
6. 案件级复核流：权限、负责人确认、附件、多实例并发和正式报告门禁。
7. 底稿、报告、整改闭环。

下一步开发不应继续停留在“知识库网站更精致”层面。当前产品要进入 V1.0，必须转向 HIS 数据、结构化规则、可复核疑点和报告整改闭环。
