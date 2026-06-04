---
title: AI 医疗审计系统 V1.0 开发计划
doc_type: other
module: product
topic: medical-audit-development-plan
status: stable
created: 2026-03-15
updated: 2026-06-04
owner: self
source: human+ai
---

# AI 医疗审计系统 V1.0 开发计划

## 1. 当前基线

本计划以 `AI 医疗审计系统 V1.0 PRD` 为母版，并以当前已部署的 AuditScope 知识库网站为工程基线。

当前已完成：

- 知识库查询引擎已实现 `检索 + 引用型回答 + 原文预览 + 索引管理`。
- 线上入口已部署到 `https://audit.lute-tlz-dddd.top/pages/chat`。
- PostgreSQL + pgvector active index 已上线，当前 active 版本为 `full-rebuild-20260603085815`。
- 当前 active 计数为 `486` 个源文档、`48985` 个 chunks、`48985` 条 embeddings。
- 已具备生产 E2E smoke、视觉基线和增量 dry-run 验收脚本。
- 当前复核任务台已切换为 PostgreSQL 持久化，支持任务创建、状态更新、复核意见、复核结论和任务级导出。
- 已补齐 `review_tasks`、`review_actions`、`review_comments` 的 SQLAlchemy 模型、repository 基础读写和正式 SQL schema；当前仍不能视为生产级案件系统。
- 已补齐 V1.0 第一批业务数据底座：`audit_projects`、`audit_data_snapshots`、`audit_tasks`、`audit_runs`、`audit_rules`、`rule_versions`、`audit_findings`、`finding_evidence_items`，支持项目、快照、任务、运行批次、规则版本、疑点和证据项的最小可追溯链路。

当前未完成：

- HIS DDL、字段映射、脱敏样本导入、数据质量报告和真实数据快照生成。
- 结构化规则执行器、医院本地覆盖规则和规则评审发布流程。
- 生产级疑点清单页面、案件级人工复核、底稿、报告、整改跟踪。
- 用户、角色、科室、权限控制和审计日志。
- 知识库新增源文件后的生产级增量写入和 active 切换闭环。

## 2. 下一阶段目标

下一阶段不继续做泛 UI 打磨，也不优先做多轮聊天。核心目标是把项目从“知识库支撑层”推进到“单院 HIS 专项审计 MVP”。

阶段目标：

- 固化当前知识库查询引擎为可回滚、可验收、可复测的 V0.2 基线。
- 锁定首个 HIS 专项审计场景，并拿到 DDL、字段字典和脱敏样本。
- 建立 V1.0 最小业务数据模型：审计项目、数据快照、规则版本、运行批次、疑点、复核、底稿、整改。
- 实现第一个 0/1 合规判定场景，输出可追溯疑点证据包。
- 将当前 PostgreSQL 任务级复核推进为案件级复核流。
- 形成可供院方 UAT 的任务级底稿和报告导出。

## 3. 产品取舍

### 3.1 优先做

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
- `audit_projects`、`audit_data_snapshots`、`audit_tasks`、`audit_runs`、`audit_rules`、`rule_versions`、`audit_findings`、`finding_evidence_items` 已进入 `sql/knowledge-query-schema.sql`。
- `AuditWorkflowRepository` 已覆盖项目、数据快照、审计任务、规则、规则版本、运行批次、疑点、证据项的基础写入，以及按疑点编号和运行批次追溯查询。
- 当前仍是数据底座切片，不包含权限系统、负责人审核、附件、多实例强一致编号或正式报告门禁。

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
- 实现 HIS 脱敏样本导入。
- 实现审计任务创建和运行批次。
- 实现首个规则执行器。
- 每条疑点输出原始数据行、命中规则、计算过程、知识依据引用。
- 将疑点落库到 `audit_findings`。

验收：

- 同一数据快照 + 同一规则版本可复跑，结果稳定。
- 每条疑点可追溯到数据快照、运行批次、规则版本和知识引用。
- 无法判定时进入 `needs-evidence` 或 `rule-issue`，不静默归为合规。

### Sprint 4：生产级复核与底稿

目标：从当前任务级 PostgreSQL 持久化推进到生产级案件复核流。

任务：

- 已将 `/pages/review-tasks` 改为 PostgreSQL 持久化。
- 支持从查询结果和疑点清单创建复核任务。
- 支持状态流转、复核意见、结论、附件引用。
- 支持任务级底稿 Markdown/JSON 导出。
- 支持负责人确认。

验收：

- 服务重启后复核任务不丢失；多实例部署下的强一致编号和并发冲突处理仍需补齐。
- 复核记录可追溯到用户、时间、任务、疑点、证据包。
- 未复核疑点不能进入正式报告。

### Sprint 5：报告与整改闭环

目标：跑通 PRD 的“底稿/报告 -> 整改跟踪 -> 结案”。

任务：

- 定义报告模板字段。
- 支持任务报告导出。
- 支持整改事项生成。
- 支持整改状态流转。
- 支持任务结案门禁。

验收：

- 报告正文只纳入已确认违规疑点。
- 附录包含复核分布、规则版本、数据快照和知识依据版本。
- 所有整改事项闭环前不能结案。

### Sprint 6：上线加固

目标：达到单院试运行门槛。

任务：

- RBAC：审计员、负责人、信息科、系统管理员。
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
