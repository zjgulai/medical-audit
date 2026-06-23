---
title: AI智能审计管理系统深度一致性诊断与债务整合计划
doc_type: workflow
module: project-governance
topic: deep-audit-and-remediation-plan
status: draft
created: 2026-06-23
updated: 2026-06-23
owner: self
source: human+ai
---

# AI智能审计管理系统深度一致性诊断与债务整合计划

> 本报告是一次独立的全仓深度审计，对齐既有《项目状态与债务台账》(`workflow-project-state-and-debt-register-stable.md`)，但以代码、git、文件系统的实测证据为准做交叉核验，并在其基础上补充、修正和升级风险判断。所有关键数字均来自 `2026-06-23` 当日实测，证据见第 9 节。

---

## 0. 结论速览（先看这一段）

总体判断：**这是一个工程化程度很高、文档纪律极强的项目，发布治理上有一个"已经完成大半、但还差临门一脚"的关键动作没收口。** 产品后端能力扎实、测试门禁完善、债务台账诚实；最大的隐患是 git 状态在多个 worktree 间并存导致的"真相源"混淆，以及关键发布分支只存在于本机、从未推送。

四点核心事实（已实测核验，结论比初判乐观）：

1. **核心代码没有丢失风险——它已被干净提交。** `auth.py`、`routes_auth.py`、`routes_workbench.py`、`docx_export.py`、登录页、全栈 E2E harness 等，虽然在**当前这个**工作目录里显示为 untracked/modified，但它们已经以**逐字节相同**的内容提交在另一个分支 `codex/medical-audit-release-auth-workbench-20260623` 上。该分支 = `main` + 5 个干净提交（`main` 是它的祖先），是一个**合格的发布候选**。
2. **但这个发布候选只在本机，从未推送到任何远端。** 它是 local-only。一旦本机磁盘故障，这份"main+5"的成果就没有异地副本。这是当前**唯一真正高危**的点，且修复成本极低（push 一下）。
3. **当前工作目录停在一个过时、脏的分支上，制造"真相源"混淆。** 这个目录 checkout 在 `codex/answer-provider-gate-plan`（HEAD `b298c6c8`，6-15，落后 main 138 提交），working tree 有 +12,813/−683 + 23 untracked。但这堆改动的**关键代码已被发布候选分支捕获**，所以它本质是一个**可丢弃的陈旧 worktree**，而不是需要抢救的孤本。项目在用 git worktree（`main`、release 分支、frontend-plan 分支各自 checkout）。
4. **发布候选尚未合入 main、未部署。** 生产仍在 `550a4450`，受控鉴权中间件、`/auth/*`、workbench API 都没上生产（Batch 8.2 smoke 因此 fail）。

如果只做一件事：**立刻把 `codex/medical-audit-release-auth-workbench-20260623` 推送到远端。** 这一步把项目从"高危"降到"可控"，耗时一分钟。随后按 Phase A/B 收口（合入 main、清理陈旧 worktree、删冗余分支）。

健康度评分（10 分制，10 为最好）：

| 维度 | 评分 | 一句话 |
| --- | :---: | --- |
| 后端架构与代码质量 | 8 | 分层清晰、store 抽象统一、类型与 lint 全绿 |
| 测试与质量门禁 | 7 | 单测/类型/构建门禁强，但 E2E 与权限/持久化回归偏薄，且 harness 仅在发布分支、未进 CI |
| 产品功能完整性 | 5 | 后端能力强于前端闭环；多数门户页仍是静态壳 |
| 前端/UI 一致性 | 5 | 双前端并存、10 页仍吃静态数据、路由语义重叠 |
| 文档纪律 | 8 | 台账极其详尽诚实；但存在阶段性漂移与个别过时数字 |
| 分支与发布治理 | 5 | 已有干净发布候选(main+5)，但未推远端、未合 main、58 本地/48 远端分支待清理 |
| 安全与合规闭环 | 4 | 权限仍是 header 过渡层、生成模型未上线、签章/对象存储未闭环 |

---

## 1. 项目架构概览

### 1.1 定位

面向医院场景的私有化"AI 智能审计管理系统"，核心闭环：`法规与知识支撑 → 合规判断与风险识别 → 审计底稿与报告 → 整改跟踪`。当前最小落地目标是单院 HIS 数据的医疗/医保审计 MVP。

### 1.2 技术栈与规模（实测）

后端：Python 3.12 / FastAPI / SQLAlchemy 2.0 / Pydantic v2 / PostgreSQL + pgvector，约 **30,344 行**、88 个源码文件（mypy 计）。模块划分清晰：`api/`（路由 + store 层）、`retrieval/`（混合检索、pg 检索、rerank）、`indexing/`（bm25、embeddings、pgvector 导入、增量计划、激活）、`ingestion/`（抽取、分块、清单、pipeline）、`generation/`（答案构建、citation、provider、preflight）、`his/`（DDL 解析、字段映射校验、staging、snapshot、回滚、验收）、`audit/`（CHARGE-RULE-001、日志留存、报告门禁）、`evaluation/`、`db/`、`domain/`、`preview/`、`acceptance/`。

前端：Next.js（App Router）/ TypeScript / Tailwind，约 **11,452 行**（不含测试）、46 个 ts/tsx 文件、18 个 workspace 路由 + 登录页。

部署：腾讯云单机 Docker Compose（`medical_audit_app` + `medical_audit_pg` + 共享 `ai_video_nginx`），域名 `https://audit.lute-tlz-dddd.top`，当前生产 SHA `550a4450`，active index 覆盖 503 文档 / 49051 chunks / 49051 embeddings，Kimi 作为 embedding provider。

### 1.3 架构最大特征：双前端并存（关键债务）

项目同时存在 **两套前端渲染体系**：

- **FastAPI Jinja 模板深页**：`routes_pages.py` 单文件高达 **120 KB**，提供 `/pages/chat`、`/pages/review-tasks`、`/pages/audit-findings`、`/pages/audit-logs` 等服务端渲染页，并承载大量写入型业务逻辑（复核任务、底稿导出、签发冻结等）。
- **Next.js 门户 (`web/`)**：18 个 workspace 路由的 SPA 壳层，通过 `api-client.ts` 调 FastAPI 的 `/api/v1/*`。

这是历史演进的产物（开发计划 §7 仍写着"短期继续用 FastAPI templates，后续需要复杂状态再启动 Next.js"——但 Next.js 实际早已建成）。**双前端意味着：同一业务能力可能有两套入口、两套测试、两处文案，长期维护成本与一致性风险翻倍。** 这是后续 UI 优化必须先决策的根问题（见 7.1）。

### 1.4 请求与鉴权数据流

`app.py` 装配所有 router，并通过一个 **可选** 的 `controlled_api_auth_middleware`（由 `MEDICAL_AUDIT_CONTROLLED_API_AUTH` env 或显式参数开启）做受控 API 鉴权：校验 `X-Tenant-Id`、`X-User-Id`、`X-Role`、`X-Project-Key` 请求头，解析持久化角色，拒绝 `disabled/pending` 用户并写 `authorization-denied` 日志。**该中间件在生产当前为关闭状态**（Batch 8.2 只读 smoke 实测：生产 `/auth/*` 返回 404，缺租户头的读接口仍返回 200）。鉴权目前整体是"header 过渡层"，非真实 SSO / 登录会话。

答案生成走 `answer_generation_provider_from_settings`：默认 `fallback`（返回 None），即引用型兜底。生产实测 `MEDICAL_AUDIT_KB_ANSWER_*` 全部 UNSET、fallback rate 100%——**线上没有真实生成模型**。

---

## 2. 产品形态与一致性诊断

### 2.1 "已完成"的三个真实层级

台账用了非常克制的口径，实测也支持这个分层。把模块按"可信度"分三档：

- **A. 已过生产写入型验收（最可信）**：知识库检索 + 引用回答 + 原文预览、复核任务台（任务级持久化/底稿/签发冻结/整改/结案只读锁）、智能体 CRUD 持久化、项目成员持久化、AI 数据分析上传解析 + 留存/历史、文档检索生产查询 + 来源回显 + 文档权限读取 + 个人材料留存。
- **B. 仅本地实现/联调（前后端协议通了，未上生产）**：本地权限底座（auth_users/roles/departments + `/auth/*`）、受控 API 鉴权中间件、`X-Tenant-Id` 契约、docx 导出、`/reports` API-first、智能体提示词版本治理/审核激活门禁/角色分离。**注意：这一整档的源码大量处于未提交/未跟踪状态（见第 5、6 节）。**
- **C. 仍是静态壳或 fixture**：知识图谱、专题规则库、补证整改、项目档案、引导自查等多数门户页由 `web/src/lib/portal-data.ts`（1793 行）驱动；HIS 链路全部基于受控脱敏 fixture；生成模型为 fallback。

### 2.2 静态数据依赖（UI 一致性核心债务）

实测：`web/src/app` 下 **10 个页面** 仍直接 import `portal-data.ts`——`agent-market`、`archive`、`chat`、`documents`、`graph`、`guided-check`、`knowledge-base`、`remediation`、`reports`、`rules`，外加三个 workbench 组件。这意味着：**页面"看起来完成"，但刷新后数据不来自后端**。这是最容易让人误判产品完成度的地方，也是 UI 优化前必须逐页标注"静态 vs API"的原因。

### 2.3 路由语义重叠（信息架构债务）

存在概念重叠的路由：`agents` vs `agent-market`；`documents` vs `knowledge-base` vs `knowledge-query`；`findings`（Next）vs `/pages/audit-findings`（Jinja）。用户和新成员难以判断"哪个是正主"。UI 重构前需要先做一次信息架构收敛。

### 2.4 文档 vs 现实的漂移点（实测）

台账整体诚实，但交叉核验发现以下偏差，需在文档同步时修正：

1. **开发计划 §7 技术路线过时**：仍称 Next.js"后续再启动"，实际已建成 18 路由的完整前端。
2. **开发计划 §1 索引数字过时**：写 active `full-rebuild-20260603085815` / 486 文档 / 48985 chunks；README 与台账已是 `incremental-20260615-...` / 503 / 49051。
3. **债务台账 P0-05 低估了 main 的进展**：P0-05 称"对象存储未完成"，但 `main` 已合入 PR #152「stage cos-backed personal uploads」、#153「pgvector ingestion」、#147「retrieval isolation by owner」、#149/#150「DLP ruleset production gate」。**台账是从"6-15 工作区视角"写的，没纳入 main 在 6-15→6-19 的 138 个提交。** 这是状态源漂移的直接后果。

---

## 3. 五类债务诊断

下面按你指定的五类做独立诊断。每条给出：证据、影响、与既有台账的关系（新增/升级/确认）。

### 3.1 技术债务（Technical Debt）

| 编号 | 债务 | 证据 | 影响 | 关系 |
| --- | --- | --- | --- | --- |
| T-01 | 双前端体系并存 | `routes_pages.py` 120KB Jinja 深页 + `web/` Next.js 18 路由 | 同能力双入口/双测试/双文案，维护成本翻倍 | 新增 |
| T-02 | 巨型文件 | `routes_pages.py` 120KB、`agent_store.py` 45KB、`portal-data.ts` 1793 行、`workspace-pages.test.tsx` 2315 行 | 单文件过大，审查/改动/合并冲突风险高 | 新增 |
| T-03 | 进程内可变状态 | `ApiState.operation_logs`/`query_logs` 为内存 list，`record_operation` 无界 append | 长跑内存增长；多实例不一致 | 新增 |
| T-04 | 生成模型未上线 | 生产 `ANSWER_*` 全 UNSET，fallback 100% | 不能宣称 AI 生成审计结论 | 确认 P0-03 |
| T-05 | 鉴权为 header 过渡层 | 中间件默认关、生产 `/auth/*` 404、缺租户头读接口仍 200 | 无生产级权限边界 | 确认 P0-04 |
| T-06 | 静态数据驱动 | 10 个页面 import `portal-data.ts` | 业务闭环不完整，易误判 | 确认 P0-01 |
| T-07 | 多实例一致性缺口 | 复核任务编号/并发冲突处理未补（开发计划 Sprint 4 验收自述） | 单机可用，水平扩展不安全 | 确认 |

### 3.2 工程债务（Engineering Debt）

| 编号 | 债务 | 证据 | 影响 | 关系 |
| --- | --- | --- | --- | --- |
| E-01 | **发布候选仅在本机、未推远端** | `release-auth-workbench` = main+5，含全部核心源码，但 `git branch -r` 无此分支 | 磁盘故障即丢失"main+5"成果，无异地副本 | **升级 P0-06（高危但修复成本极低）** |
| E-02 | 工作目录停在陈旧脏分支 | 当前 worktree 在 `answer-provider-gate-plan`（落后 main 138），改动已被发布分支捕获 | "真相源"混淆，易在错误分支上继续改 | 新增 |
| E-03 | 核心代码在当前 worktree 显示为 untracked | `auth.py`/`routes_workbench.py` 等在此目录未跟踪（但已提交在发布分支） | 在此目录误 `checkout/stash` 会丢未提交增量 | 由"致命"修正为"中" |
| E-04 | harness 未进 CI | `run-local-fullstack-e2e.py` 仅在发布分支，无自动化回归 | "验收通过"依赖手工执行 | 升级 P2-03 |
| E-05 | 仅 1 个前端 E2E spec | `web/tests/e2e/foundation.spec.ts` 单文件 | 持久化/权限/写入回归靠手工 + 一次性 harness | 确认 P2-03 |
| E-06 | 本地工作区臃肿 | 工作目录 4.8G：`tmp/` 1.2G、`data/` 722M、`node_modules` 625M、`.venv` 200M | 扫描/索引/导航成本高（clone 体积因 gitignore 可控） | 确认 P2-02 |
| E-07 | 107 处标记 | src+web 非测试代码含 TODO/mock/stub/fallback 等 107 处 | 局部未完成/占位逻辑分散 | 新增 |

正面：mypy / ruff / pnpm lint / typecheck / build 全绿，无 skipped 测试，`ai_video.pem` 与 `*.env` 已正确 gitignore，无跟踪密钥——工程基线本身是健康的，问题集中在"落盘与发布"环节。

### 3.3 项目管理债务（Project-Management Debt）

| 编号 | 债务 | 证据 | 影响 | 关系 |
| --- | --- | --- | --- | --- |
| PM-01 | 分支爆炸 | 58 本地 + 48 远端分支 | 认知过载，难定位有效分支 | 升级 P0-06 |
| PM-02 | 分支语义混乱 | 远端分支几乎全部已并入 main（0 ahead），仅 2 个尚有未并提交；但本地仍保留全部 | 已死分支未清理 | 新增 |
| PM-03 | 当前工作目录停在落后主线的脏分支 | HEAD 落后 main 138 提交（4 天）；但成果已另存于 release 分支 | 真相源混淆，非代码丢失 | 修正 P0-06 |
| PM-04 | 发布候选未推远端、未合 main | `release-auth-workbench`(main+5) local-only，生产仍 `550a4450` | 成果无异地副本、未上线 | 修正 P0-06 |
| PM-05 | 缺院方 UAT 闭环 | 仅工程 smoke，无 UAT case/签收 | 无客户验收证据 | 确认 P1-05 |
| PM-06 | 外部依赖阻塞主线 | HIS DDL/字段字典/脱敏样本未到位（最高优先级 #1/#2） | V1.0 闭环被外部卡住 | 确认 |

### 3.4 文档管理债务（Documentation Debt）

| 编号 | 债务 | 证据 | 影响 | 关系 |
| --- | --- | --- | --- | --- |
| D-01 | 状态源单一视角漂移 | 台账以"6-15 工作区"为准，未含 main 138 提交（如 COS/DLP/隔离） | 决策者误读完成度 | 升级 P1-06 |
| D-02 | 开发计划技术路线过时 | §7 称 Next.js 未启动 | 误导架构判断 | 新增 |
| D-03 | 索引计数不一致 | 开发计划 §1 vs README/台账 | 数字口径不一 | 新增 |
| D-04 | 文档资产巨大且分散 | docs 累计 6747 行 + drafts/ref/opendesign 未跟踪 | 新人难定位权威源 | 确认 P2-01 |
| D-05 | 关键文档未入库 | `workflow-fullstack-completeness-audit-...md` 等为 untracked | 权威计划本身可能丢失 | 新增 |

### 3.5 脆弱点债务（Fragility Debt）

| 编号 | 脆弱点 | 触发条件 | 后果 | 严重度 |
| --- | --- | --- | --- | :---: |
| F-01 | 发布候选无异地副本 | 本机磁盘故障 | "main+5"成果灭失（push 即可消除） | **高** |
| F-02 | 在错误 worktree 继续开发 | 误在陈旧 `answer-provider-gate-plan` 上改 | 增量再次脱离主线，重复混乱 | 中 |
| F-03 | 在陈旧 worktree 误操作 | 此目录 `checkout/stash/reset` | 丢失尚未被发布分支捕获的零散增量 | 中 |
| F-04 | 生产/发布候选不同源 | 以为生产=发布候选 | 误判已上线能力（鉴权/workbench 实际未部署） | 中 |
| F-05 | 内存态状态丢失 | 进程重启 | operation/query 内存日志丢失（已有 DB store 兜底，但双写不一致风险） | 中 |
| F-06 | 共享 Nginx 单点 | `ai_video_nginx` 共享公网入口 | 与其他业务相互影响 | 中 |
| F-07 | docx 冻结哈希基于 Markdown | 报告签发 | 非证书级签章，合规存疑 | 中 |

---

## 4. 脆弱点与缺口清单（按"离生产闭环还差什么"组织）

V1.0 产品闭环尚未补齐的能力缺口（与开发计划"当前未完成"对齐并实测确认）：

- **真实生成模型**：provider 预检、密钥边界、真实答案评测、生产 `--require-generated-answer` E2E 均未通过（P0-03）。
- **真实权限体系**：SSO claims、登录会话签发、正式租户身份来源、网关注入策略、生产权限验收（P0-04）。
- **合规闭环**：证书级非对称电子签章、对象存储、外部杀毒/DLP 服务、长期留存介质、真实外部告警端点（P0-05）。
- **个人材料入索引**：留存与读取隔离已通生产，但"真实入向量索引"未闭环（main 已有 COS/staging 切片，需对齐验收）。
- **HIS 真实数据闭环**：DDL/字段字典/脱敏样本/验收口径未到位 → 字段映射 UI、规则发布 UI、staging 真实验收全部受阻（P0-02、P1-03、P1-04）。
- **页面 API 化**：知识库/图谱/规则/整改/归档等 10 页仍静态（P0-01）。
- **会话系统**：顶部多标签/历史对话仍是前端态，无服务端持久化会话。
- **多实例一致性**：编号强一致、并发冲突处理未补（T-07）。

---

## 5. 当前工作区状态盘点（已大幅澄清）

关键澄清：当前这个工作目录（checkout 在 `codex/answer-provider-gate-plan`，HEAD `b298c6c8`，6-15，远端 `[gone]`）显示的 54 tracked 改动（+12,813/−683）+ 23 untracked，**绝大部分的关键代码已经以逐字节相同的内容被提交在 `release-auth-workbench` 分支上**（已对 `auth.py`、`routes_auth.py`、`routes_workbench.py`、`docx_export.py`、`run-local-fullstack-e2e.py`、`app.py` 做 0-diff 核验）。所以这个目录**不是需要抢救的孤本，而是一个语义已被发布分支取代的陈旧 worktree**。

仍需处理的，是把"陈旧 worktree"与"发布候选"的关系收口：

- **生产关键代码（已在发布分支，无需再抢救，仅需确认未遗漏零散增量）**：`api/auth.py`、`auth_user_store.py`、`routes_auth.py`、`routes_workbench.py`、`docx_export.py`、`scripts/run-local-fullstack-e2e.py`、`run-controlled-api-readonly-permission-smoke.py`、`web/src/app/login/`、`audit-user-context.tsx`、`audit-user.ts`、`web/public/`。
- **非交付物（清理对象，不进任何发布分支）**：`.codex/`、`.kiro/`、`.playwright-mcp/`、`opendesign/`、`ref/`、`drafts/analysis/*`、`tmp/`。
- **建议核验项**：在 release 分支上 `git diff` 对照当前 worktree 全量，确认**没有任何关键改动只存在于陈旧 worktree 而未进发布分支**（已抽核关键文件 0-diff，建议补一次全量对照后即可安全丢弃此 worktree）。

**关于"138 落后 / 26 冲突文件"**：这是针对"把当前陈旧 worktree 直接 merge 进 main"的风险——但**没有必要走这条路**。真正的合并候选是 `release-auth-workbench`（main+5，干净），它本身已包含 main 的 138 提交，合入 main 时**不存在那 26 个冲突**。陈旧 worktree 对照 main 的冲突面只是"为什么不要用它做发布"的佐证，不是要去解决的工作量。

---

## 6. 分支与未合并工作盘点

### 6.1 远端分支（48 个）——基本可安全清理

实测：除 `origin/codex/docs-only-merge-sha-boundary`（领先 main 2 提交）和 `origin/codex/documents-history-production-sync`（1 提交）外，**其余远端 codex 分支均 0 提交领先 origin/main**，即工作已并入 main。它们是历史 PR 分支，**可批量删除**（先确认那 2 个领先分支的内容是否仍需要）。

### 6.2 本地分支（58 个）——多数是已并入的死分支

26 个本地分支"未并入 main"，但绝大多数其实是历史快照。按领先 main 的提交数排序，值得人工确认的只有少数：

| 领先 main | 分支 | 判断 |
| ---: | --- | --- |
| 46 | `codex/opendesign-ui-polish` | UI 设计探索，需确认是否还要（其中含 `opendesign/` 资产） |
| 8 / 7 / 6 / 5 | `review-task-closed-readonly` / `close-gate` / `rectification-tracking` / `report-signoff` | 复核任务系列，疑似已通过其它 PR 并入，需核对 |
| **5** | **`medical-audit-release-auth-workbench-20260623`** | **已核验：= main + 5 干净提交，main 是其祖先，含全部 auth/workbench 代码（与陈旧 worktree 0-diff）。这是真正的发布候选。** |
| 5 | `frontend-plan-02-projects-dashboard` | 前端 dashboard 重构（已在独立 worktree checkout） |
| 1 | `frontend-visual-system-polish` | 视觉系统打磨（与 UI 目标相关） |

`release-auth-workbench` 的 5 个提交：`prepare auth workbench release candidate` / `enforce controlled api auth in production` / `align production acceptance with auth enforcement` / `prevent documents page overflow` / `clip document upload history`。

**已核验结论**：发布候选存在且干净，F-01 从"致命"降为"高"——唯一缺口是它 **从未推送到远端**。`git push -u origin codex/medical-audit-release-auth-workbench-20260623` 即可消除丢失风险，然后走 PR 合入 main。

### 6.3 三源 SHA 对照

| 源 | SHA | 日期 | 相对 main |
| --- | --- | --- | --- |
| 工作分支 HEAD | `b298c6c8` | 6-15 | 落后 138 |
| 本地/远端 main | `950ecbda` | 6-19 | 基准（本地=远端，0/0） |
| 生产 | `550a4450` | 6-19 | 落后 2 |

main 与生产基本同步（生产仅落后 2 个 doc/fix 提交，健康）。真正脱节的是工作分支。

---

## 7. 整合方案与分阶段计划

总原则：**先固本（保住代码、对齐状态源），再谈优化（UI/功能），最后硬化交付（测试/UAT）。** 下面把你的三个目标（UI、功能、测试交付）+ 分支治理映射到分阶段计划。每阶段给出"门禁"，未过门禁不进下一阶段。

### Phase A：发布候选异地落盘与收口（最高优先级，半天，**阻塞一切**）

目标：消灭 F-01/E-01，让已完成的"main+5"成果有异地副本并进入正规发布流。

1. **立刻 push 发布候选**（一分钟，最高优先）：`git push -u origin codex/medical-audit-release-auth-workbench-20260623`。消除唯一高危点。
2. **全量对照确认无遗漏**：在 release worktree 里，`git diff` 对照陈旧 worktree 的全量改动，确认没有任何关键改动只在陈旧 worktree（关键文件已 0-diff 抽核；此步是兜底）。
3. **在 release 分支跑全量门禁**：`ruff`、`mypy src`、`pytest`、`pnpm lint/typecheck/test/build`、`run-local-fullstack-e2e.py`。
4. **走 PR 合入 main**：让 main 重新成为唯一权威 tip（main+5 → main）。
5. **丢弃/归档陈旧 worktree**：确认无遗漏后，删除 `answer-provider-gate-plan` 这个脏 worktree（`git worktree remove`），消除"真相源"混淆。
6. **入库两份权威文档**：`workflow-fullstack-completeness-audit-...md` 和本报告单独 commit 入 `docs/`。

门禁：`release-auth-workbench` 已在远端；全量质量闸绿；PR 合入 main；陈旧 worktree 已移除；`git status` 干净可解释；全新 clone 能启动应用（验证 `app.py` 所有 import 都已入库）。

### Phase B：分支与发布治理（0.5–1 天）

目标：消灭 PM-01/02/03，让分支拓扑可读。

1. 删除 48 个远端分支里已 0-ahead 的（保留待确认的 2 个领先分支）。
2. 删除本地已并入 main 的死分支；保留 ≤5 个真正在用的。
3. 把 release 分支走正常 PR 流程合入 main，使 main 重新成为唯一权威 tip。
4. 同步文档（见 Phase C 文档项），统一状态源。

门禁：`git branch -a` 数量回到可控（个位数活跃分支）；main = 发布候选唯一来源。

### Phase C：文档同步与状态源统一（与 B 并行，0.5 天）

修正 D-01~D-05：把 main 的 138 提交进展（COS/DLP/retrieval-isolation）并入台账；修正开发计划 §7 技术路线与 §1 索引数字；把 untracked 权威文档入库；在台账顶部加"三源 SHA 对照表"作为常驻状态锚点。

### Phase D：测试与交付门禁加固（2–3 天，对应你的目标 3）

目标：把"一次性 harness 验收"升级为"可复现回归门禁"，消灭 E-04/E-05。

1. harness 入库后，将 `run-local-fullstack-e2e.py` 接入 CI/pre-push。
2. 为 A 档已上生产模块（agents/projects/analytics/documents/复核任务）补 **持久化 + 权限** 回归 E2E（刷新后仍在、无角色 403、disabled 用户拒绝）。
3. 拆分 2315 行的 `workspace-pages.test.tsx`，按模块归位。
4. 建立"完成定义"清单模板：代码证据 + 页面证据 + 测试证据 + 生产边界（沿用台账纪律，固化为 PR 模板）。

门禁：每个 A 档模块每次 PR 自动跑关键路径；权限绕过测试失败即阻断。

### Phase E：UI/前端一致性优化（3–5 天，对应你的目标 1）

目标：消灭 T-01/T-06、2.2/2.3 的 IA 问题。

1. **信息架构收敛**：决策双前端去留（建议逐步以 Next.js 为主、Jinja 深页仅保留尚未迁移的写入页），合并语义重叠路由（agents/agent-market、documents/knowledge-base/knowledge-query、findings）。
2. **逐页标注 静态 vs API**：在每个仍吃 `portal-data.ts` 的页面顶部加"数据来源"标识，避免误判；按优先级把 reports（已 API-first）之外的页面排期接真实 API。
3. **视觉系统统一**：评估 `frontend-visual-system-polish` / `opendesign-ui-polish` 分支的可复用资产，沉淀为统一 design token / 组件库，再做视觉打磨。
4. UI 改动一律过 `pnpm production:frontend-acceptance`（桌面+移动、`p0=[]`、`p1=[]`、`h1Count=1`、无横向溢出）。

门禁：无语义重叠路由；每页"数据来源"明确；前端语义验收 p0/p1 为空。

### Phase F：产品功能完整性推进（持续，对应你的目标 2）

按开发计划既有优先级推进，但顺序服从"先补已上生产模块的权限闭环，再补新能力"：

1. 个人材料真实入索引（对齐 main 的 COS/staging 切片）→ 外部杀毒/DLP/对象存储治理。
2. 真实生成模型 provider 生产门禁（按 `analysis-answer-provider-production-gate-plan` 草稿，过预检+真实评测才写 env）。
3. 真实权限体系（SSO/会话/租户来源）→ 生产权限验收。
4. HIS 真实数据闭环（**外部依赖到位后**）：字段映射 UI、规则发布 UI、staging 真实验收、CHARGE-RULE-001 真实样本。
5. 合规闭环：证书级签章、长期留存、外部告警端点。

门禁：沿用台账"每次声称完成必须同时给代码/页面/测试/生产边界四类证据"。

### 关键路径与依赖

```
Phase A（抢救）──┬──> Phase B（分支治理）──> Phase C（文档同步）
                 └──> Phase D（测试门禁）──> Phase E（UI）──> Phase F（功能）
```

A 是所有事情的前置。B/C 可与 D 并行。E 依赖 D 的回归门禁兜底。F 是长期主线，但其中 HIS 部分受外部依赖（DDL/样本）阻塞，应尽早向院方发起。

---

## 8. 风险登记与优先级矩阵

| ID | 风险 | 概率 | 影响 | 等级 | 首要缓解 | 对应阶段 |
| --- | --- | :---: | :---: | :---: | --- | --- |
| R-01 | 发布候选无异地副本，磁盘故障即丢 | 中 | 高 | **P0** | 立刻 push release 分支到远端 | A |
| R-02 | 在错误 worktree 继续开发 / 误操作 | 中 | 中 | P1 | 合 main 后移除陈旧 worktree | A |
| R-03 | 误把发布候选当生产去 hotfix | 中 | 高 | P1 | 状态源锚点 + 部署只从 main | A/C |
| R-04 | 生成模型/权限被误判为已上线 | 中 | 高 | P1 | 文档边界 + 生产 smoke 常态化 | C/D |
| R-05 | 静态页被当成完成功能 | 高 | 中 | P1 | 逐页数据来源标识 | E |
| R-06 | HIS 外部依赖长期不到位 | 中 | 高 | P1 | 尽早发起院方交付模板 | F |
| R-07 | 分支爆炸致认知漂移 | 高 | 中 | P2 | 分支清理 + 命名规范 | B |
| R-08 | 共享 Nginx / 内存态 / 仓库臃肿 | 中 | 中 | P2 | 纳入持续治理 | D/F |

---

## 9. 核验证据（实测，2026-06-23）

- 分支规模：本地 58、远端 48（`git branch | wc -l` / `git branch -r | wc -l`）。
- 远端分支并入度：除 `docs-only-merge-sha-boundary`(+2)、`documents-history-production-sync`(+1) 外均 0-ahead origin/main。
- 三源 SHA：HEAD `b298c6c8`(6-15) 落后 main 138；main=origin/main `950ecbda`(6-19)；生产 `550a4450`(6-19) 落后 main 2。
- 陈旧 worktree：当前目录 54 tracked（+12,813/−683）+ 23 untracked；26 个 dirty 文件与 main 6-15→6-19 改动重叠（仅作"不要用它发布"的佐证）。
- **发布候选已存在且干净**：`release-auth-workbench` 相对 main = `0 left / 5 right`（main 是其祖先，merge-base=main tip `950ecbda`）；`git branch -r` 无此分支（local-only，未推送）。
- **0-diff 核验**：release 分支的 `auth.py`/`routes_auth.py`/`routes_workbench.py`/`docx_export.py`/`run-local-fullstack-e2e.py`/`app.py` 与当前 worktree 逐字节相同（diff 行数=0，auth.py 均 393 行）。
- main 不含 `auth.py`/`routes_workbench.py`（确认这些能力确实尚未进 main）。
- untracked 核心源码（在当前 worktree 未跟踪，但已提交于 release 分支）：`auth.py`、`auth_user_store.py`、`routes_auth.py`、`routes_workbench.py`、`docx_export.py`、`run-local-fullstack-e2e.py`、`run-controlled-api-readonly-permission-smoke.py`、`web/src/app/login/`、`audit-user-context.tsx`、`audit-user.ts`、`web/public/`。
- 后端规模：30,344 行 Python、88 源码文件（mypy）；`routes_pages.py` 120KB。
- 前端规模：11,452 行 TS/TSX（非测试）、18 workspace 路由 + login；`portal-data.ts` 1793 行；10 页 import 它。
- 测试：292 个 python `test_` 函数、91 个 web 测试、1 个前端 E2E spec + 未入库全栈 harness；无 skipped。
- 安全：`ai_video.pem`、`*.env`、`data/*` 已 gitignore；无跟踪密钥。
- 体积：工作目录 4.8G（tmp 1.2G / data 722M / node_modules 625M / .venv 200M）。
- 生成模型：生产 `ANSWER_*` 全 UNSET、fallback 100%（台账 P0-03）。
- 受控鉴权：中间件默认关；生产 `/auth/*` 404、缺租户头读接口 200（台账 Batch 8.2）。
- 文档漂移：开发计划 §7 称 Next.js 未启动（实际已建成）、§1 索引计数与 README/台账不一致；台账 P0-05 未含 main 的 COS/DLP/隔离 PR（#147/#149/#150/#152/#153）。

---

## 10. 一句话行动建议

**现在就执行一条命令**：`git push -u origin codex/medical-audit-release-auth-workbench-20260623`。这把全项目唯一的高危点（main+5 成果只在本机）一分钟内消除。随后按 Phase A 把它合入 main、移除陈旧的 `answer-provider-gate-plan` worktree。在发布候选合入 main 之前，不要从当前这个陈旧工作目录部署生产，也不要在它上面继续开发。
