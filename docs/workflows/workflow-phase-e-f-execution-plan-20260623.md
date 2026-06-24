---
title: Phase E（UI一致性）与 Phase F（产品功能完整性）细化执行计划
doc_type: workflow
module: project-governance
topic: phase-e-f-execution-plan
status: draft
created: 2026-06-23
updated: 2026-06-23
owner: self
source: human+ai
---

# Phase E / Phase F 细化执行计划

> 承接 `workflow-deep-audit-and-remediation-plan-20260623.md`。Phase A–D（抢救/分支治理/文档同步/发布合入主线/生产部署+enforce 验证）已完成。本文件把 Phase E（UI/前端一致性）和 Phase F（产品功能完整性）拆成可执行、可验收的细粒度任务。
> 基线：`origin/main = 2db21a5e`，生产已部署 `c10b3d3b` 并 enforce 鉴权。

## 0. 执行纪律（每个代码切片都遵守）

- 每个切片从 `origin/main` 拉干净 `codex/` 分支，**不在陈旧 worktree 上写代码**（本次事故的根因就是陈旧 worktree 堆积）。
- 切片完成必须四证齐全：代码 + 页面截图/验收 + 测试 + 生产边界声明。
- 前端切片合并前过：`pnpm --filter medical-audit-web lint/typecheck/test/build` + `pnpm local:fullstack:e2e`；上生产后过 `pnpm production:frontend-acceptance`（`p0=[] p1=[]`）。
- 后端切片合并前过：`uv run ruff check . && uv run mypy src && uv run pytest`。
- 生产写入前必须有 DB 备份与回滚路径（沿用 deploy 脚本 stamp 备份）。

## 1. 数据源现状矩阵（E 阶段事实基线，实测）

| 页面 | 数据源 | 说明 |
| --- | --- | --- |
| `workspace` | API | 工作台 |
| `chat` | 混合 | 调 `/query` + portal-data 兜底 |
| `agents`(我的智能体) | 混合(组件) | `agent-workspace.tsx` 调 `/agents` + portal-data |
| `agent-market`(智能体广场) | **纯静态** | 仅 portal-data |
| `knowledge-base`(知识库) | **纯静态** | 仅 portal-data |
| `documents`(文档检索) | 混合 | 调 `/query` `/query/logs` + portal-data 示例 |
| `analytics`(AI数据分析) | 混合(组件) | `data-analysis-workbench.tsx` 调 `/analytics/*` |
| `graph`(知识图谱) | 混合 | 调 workbench + portal-data |
| `reports`(审计底稿) | 混合 | 已 API-first `/reports/workbench` + 样例兜底 |
| `projects`(项目管理) | 混合(组件) | `project-management-workbench.tsx` 调 `/projects` |
| `guided-check`(引导自查) | **纯静态** | 仅 portal-data |
| `rules`(专题规则库) | 混合 | 调 workbench + portal-data |
| `remediation`(补证整改) | 混合 | 调 workbench + portal-data |
| `archive`(项目档案) | 混合 | 调 workbench + portal-data |
| `findings` | 孤儿路由 | **不在侧边导航**，疑似遗留/开发页 |
| `knowledge-query` | 孤儿路由 | **不在侧边导航**，疑似遗留/开发页 |

三类纯静态壳：`agent-market`、`knowledge-base`、`guided-check`（最易被误判为已完成，优先处理）。
两个孤儿路由：`findings`、`knowledge-query`（IA 收敛对象）。

## 2. Phase E：UI / 前端一致性

### E1 信息架构收敛 + 静态数据盘点（分析切片，本轮已做）
- 目标：冻结路由地图、处置孤儿路由、确定静态→API 迁移顺序。
- 产出：本文件第 1 节矩阵 + 下列处置决议。
- 决议：
  - `findings` / `knowledge-query` 孤儿路由 → 二选一：纳入导航并接 API，或下线重定向到 `documents`/`workspace`。建议下线（功能已被 `documents` + `/pages/audit-findings` 覆盖）。
  - `agents` vs `agent-market` 保留（语义不同：我的智能体 vs 模板广场），但在文案上明确区分。
  - 迁移优先级（静态→API）：`knowledge-base` → `graph` → `rules` → `remediation` → `archive` → `agent-market` → `guided-check`。
- 验收：路由地图无孤儿；矩阵入文档。
- 状态：**已完成（本轮）**。

### E2 双前端边界冻结（决策切片）
- 目标：决定 Jinja `/pages/*` 深页与 Next 门户的长期边界，避免双维护。
- 改动点：列出 `routes_pages.py` 仍承载的写入型页面（复核任务、审计日志、索引管理），逐一标"保留 Jinja / 迁移 Next"。
- 建议：写入型重业务页（review-tasks/audit-logs/index-admin）短期保留 Jinja；展示型逐步并入 Next。
- 验收：边界表入架构文档，后续新功能只进 Next。

### E3 逐页"数据来源"标识（代码切片，低风险，建议首个代码切片）
- 目标：在每页顶部加一个明确的"数据来源：实时/示例"徽标，消灭"静态被当完成"。
- 改动点：新增 `<DataSourceBadge source="api|static|hybrid" />` 组件；先接 3 个纯静态页 + 7 个混合页。
- 验收：每页可见数据来源；`frontend-acceptance` 仍 `p0=[] p1=[]`。
- 风险：低（纯展示层）。

### E4 静态页接真实 API（逐页切片）
- 现状澄清：7 个"混合页"(archive/chat/documents/graph/reports/rules/remediation)本就已调 workbench/query API，非纯静态；真正的纯静态页只有 knowledge-base、agent-market、guided-check。
- 已完成：
  - `knowledge-base`：改写为客户端组件，主数据用 `fetchDocumentPermissions()`(真实来源集合)+ `fetchSearchBackendStatus()`(真实索引状态)，静态逐库统计降级为标注"示例编目"。徽标 hybrid。
  - `agent-market`：新增"系统已发布智能体(实时)"区，用 `fetchAgents()` 过滤 `source==="system-default"`；静态模板降级为"示例模板(套用入口)"，保留 `/agents?template=` 套用流。徽标 hybrid。
- 维持静态（合理）：`guided-check` 是固定的自查流程定义，无真实后端数据源，接 API 无意义；保留 E3 静态徽标如实标注。
- 改动点原则：前端优先用既有 `api-client` 端点替换 `portal-data`，portal-data 仅作 loading/error 兜底；不为接 API 而强加无真实数据源的后端端点。
- 验收：刷新后主数据来自后端；前端 lint/typecheck/test/build + 生产 frontend-acceptance 通过；文案不再暗示未完成=完成。

### E5 视觉系统统一（设计 token / 组件库切片）
- 目标：消灭散落样式，沉淀统一 token 与组件。
- 输入：评估 `opendesign/`（未跟踪设计资产）与 `codex/frontend-visual-system-polish`、`codex/opendesign-ui-polish` 分支的可复用部分。
- 改动点：抽 `globals.css` token；统一卡片/表格/状态徽标/页头组件。
- 验收：视觉回归截图；无横向溢出；`h1Count=1`。

### E6 前端验收门常态化（CI 切片）
- 把 `pnpm local:fullstack:e2e` + `production:frontend-acceptance` 接入 pre-push / CI。
- 验收：每次前端 PR 自动跑关键路径。

## 3. Phase F：产品功能完整性

### F1 个人材料真实入向量索引（对齐 main 的 COS/staging）
- 现状：main 已有 COS staging（PR #146/#152/#153）、retrieval isolation（#147）、DLP ruleset（#149/#150）、clamav 生产在线。
- 目标：打通"个人上传 → 杀毒/DLP → 入向量索引 → 检索按 owner 隔离"端到端。
- 验收：上传材料可被本人检索到、他人不可见；生产写入型 E2E。

### F2 真实生成模型 provider 生产门禁（P0-03）
- 依据 `drafts/analysis/analysis-answer-provider-production-gate-plan-*`。
- 步骤：provider 候选 + 密钥边界 → `answer-provider-smoke` → 真实生成评测 → 生产 `--require-generated-answer` E2E → 才写生产 env。
- 验收：真实生成评测通过；未通过前保持引用 fallback 为产品边界。

### F3 真实权限体系（P0-04 收口）
- 现状：header 过渡层 + 生产 enforce 已生效（本轮）。
- 目标：补真实登录会话签发、医院 SSO claims、正式租户身份来源、网关注入策略。
- 验收：真实会话 smoke；未授权 401/403；停用用户拦截；生产权限验收。

### F4 HIS 真实数据闭环（受外部依赖阻塞，尽早发起）
- 前置：院方 DDL、字段字典、脱敏样本、验收口径（最高优先级 #1/#2）。
- 切片：字段映射 UI → 院方字段确认流 → 映射版本发布 → staging 真实验收 → CHARGE-RULE-001 真实样本运行。
- 验收：`his-staging-acceptance` 对真实样本 PASS；疑点证据链可追溯。

### F5 合规闭环（P0-05）
- 切片：证书级非对称电子签章 → 对象存储归档 → 长期留存介质 → 真实外部告警端点。
- 验收：归档包/签章/验签/恢复演练通过。

### F6 案件级复核流 + 多实例一致性
- 目标：任务级 → 案件级复核；编号强一致、并发冲突处理。
- 验收：多实例下编号不冲突；未复核疑点不进正式报告。

## 4. 推荐执行顺序

1. E1（已完成）→ E3（数据来源徽标，低风险见效快）→ E2（边界冻结）。
2. F2（生成模型门禁，解锁产品核心卖点）与 E4（静态页接 API）并行。
3. F1（个人材料入索引，main 已有底座，收口快）。
4. F3（权限收口）。
5. F4（HIS，外部依赖到位即启动）、F5、F6。

## 5. 执行方式（本环境约束下）
- 沙箱无法 push、无法访问其它 worktree、无法跑真实生产。代码切片采用：在干净 `codex/` 分支上由助手产出改动 → 用户本机 lint/test/build/push → 生产验收 → 逐切片确认（与本次发布相同的协作模式）。
