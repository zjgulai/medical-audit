---
title: 分支整合与前后端分离执行 Todo
doc_type: execution_todo
module: branch-governance-frontend-backend-separation
status: draft
created: 2026-07-02
updated: 2026-07-02
owner: codex
source: codex-branch-cleanup-20260702
evidence_level: local-git-readonly-plus-branch-mutation
---

# 分支整合与前后端分离执行 Todo

## 当前基线

- [x] 主工作区切换到 `codex/frontend-backend-separation-20260702`。
- [x] 基线提交为 `origin/main@735ecc67df9450f1549e9477cac5e9df0a4a0d89`。
- [x] 脏 worktree 与分支 ref 已备份到 `/Users/pray/.Codex/file-history/medical_audit-branch-cleanup-20260702T135550Z`。
- [x] 本地已删除已合并或 patch-equivalent 的历史分支。
- [ ] 新重构分支尚未 push。
- [x] 未执行 merge、deploy、production write、provider call 或 runtime switch。

## T0: 安全边界

- [x] 保留 `main` worktree `/Users/pray/project/medical_audit_minimal_pr` 的未提交修改，不自动 stage、stash 或删除。
- [x] 保留 `codex/frontend-plan-02-projects-dashboard` worktree 的未提交修改，不自动覆盖。
- [x] 保留 `codex/kb-classification` worktree `/Users/pray/project/ma-kb`，不删除目录。
- [x] 保留 `codex/release-prep-20260627` worktree，不把 release/preflight 线混入前端重构线。
- [x] 已有远端删除前 ref manifest 与 `ls-remote` 证据；后续任何 worktree remove 或 branch force-delete 仍需明确可恢复路径。

## T1: 远端历史分支清理

可执行删除条件：PR 已合并，或与 `origin/main` 无文件差异，且不属于 closed-unmerged 文档分支。

- [x] 删除 `origin/codex/answer-provider-gate-plan`。
- [x] 删除 `origin/codex/frontend-2.0`。
- [x] 删除 `origin/codex/kb-base-classification`。
- [x] 删除 `origin/codex/loop13-frontend-acceptance-hotfix-20260630`。
- [x] 删除 `origin/codex/personal-material-live-gate-sql-fix-20260628`。
- [x] 删除 `origin/codex/personal-material-live-gate-state-sync-20260629`。
- [x] 删除 `origin/codex/personal-material-live-retrieval-gate-20260628`。
- [x] 删除 `origin/codex/uiux-topic-forms-agents-20260630`。
- [x] 删除后执行 `git fetch --prune origin` 并验证远端列表。

暂不删除：

- [ ] 保留 `origin/codex/kb-classification`，因为仍有历史拓扑 diff 且本地 `ma-kb` worktree 占用。
- [ ] 保留 `origin/codex/docs-only-merge-sha-boundary`，因为 PR closed 未合并，需要文档差异评审。
- [ ] 保留 `origin/codex/documents-history-production-sync`，因为 PR closed 未合并，需要文档差异评审。

## T2: 本地 worktree 与分支收敛

- [x] `codex/frontend-plan-02-projects-dashboard`: 已确认是 5 commit / 9 file 小范围前端会话线，worktree 另有 6 个未提交文件；不删除，进入摘取评审。
- [x] `codex/kb-classification`: 已确认 PR #159/#160 合并过，但仍有历史拓扑 diff 且 `/Users/pray/project/ma-kb` 占用；不删除。
- [x] `codex/release-prep-20260627`: 已确认是 2 commit / 60 file release/preflight 线；保留为发布参考，不合并到新重构分支。
- [x] `codex/opendesign-ui-polish`: 已确认是 46 commit / 5746 file 旧大分叉；只摘取设计经验，不整分支 merge。
- [x] `codex/answer-provider-gate-plan`: 已确认是 1 local-only commit / 125 file 旧计划/治理分支；只摘取仍有效的 provider gate 文档经验。

## T3: 待评审分支摘取清单

- [ ] 从 `codex/frontend-plan-02-projects-dashboard` 摘取候选：
  - `web/src/lib/guided-check-session.ts`
  - `web/src/lib/guided-check-session.test.ts`
  - `web/src/lib/chat.ts`
  - `web/src/app/(workspace)/guided-check/page.tsx`
- [ ] 从 `codex/opendesign-ui-polish` 摘取候选：
  - 左侧导航、顶部状态栏、工作台密度、表格优先的信息架构经验。
  - 不复制旧大分叉代码结构。
- [ ] 从 closed docs 分支摘取候选：
  - 只保留仍能解释生产 SHA 边界、文档检索历史状态的事实。
  - 不把过期 production 状态写入当前结论。

当前评审结论：

- [x] `frontend-plan-02-projects-dashboard` 的可摘取价值集中在 guided-check session persistence 与恢复测试；适合等 API contract 明确后按文件摘取。
- [x] `opendesign-ui-polish` 的可摘取价值是信息架构与工作台密度，不是代码合并来源。
- [x] `release-prep-20260627` 的可摘取价值是本地/生产 gate 脚本经验，不属于前端重写的实现输入。
- [x] closed docs 分支只允许作为历史状态核对材料，不允许覆盖当前 `735ecc67` 生产对齐事实。

## T4: 前后端分离重构主线

目标：后端成为 FastAPI/API contract 层，前端成为独立 Next.js 应用体验层；Jinja/template 页面降为 legacy 或诊断入口，不作为主产品体验继续扩张。

- [x] 建立当前路由与数据流 inventory：
  - backend: `src/medical_audit_kb/api/routes_*.py`
  - legacy templates: `src/medical_audit_kb/api/templates/`
  - frontend app: `web/src/app/`
  - frontend data adapters: `web/src/lib/api-client.ts`, `web/src/lib/api-types.ts`, `web/src/lib/portal-data.ts`
- [ ] 定义 API contract 分层：
  - auth/session/current-user
  - project/workspace summary
  - audit findings/cases
  - knowledge query/documents/index status
  - guided-check/remediation/report workflow
  - agent prompts and task status
- [ ] 前端环境边界：
  - 本地 dev 使用 `pnpm web:dev`。
  - API base URL 通过环境变量或 Next proxy 显式配置。
  - static export 与 dynamic API 访问路径分离。
- [ ] 后端边界：
  - `/api/v1` 作为主 API 前缀。
  - 保留生产 readonly/protected endpoint gate。
  - 不在前端重构中引入 provider call、runtime switch 或生产写入。
- [ ] 前端重写第一阶段：
  - 固化 shell、导航、工作台密度、表格主流程。
  - 优先实现 `B2B医疗版` 的 Excel-template/audit-table 产品合同。
  - 将 mock/static portal data 与真实 API adapter 分层。
- [ ] 验证门禁：
  - `pnpm web:typecheck`
  - `pnpm web:test`
  - `pnpm web:e2e`
  - `uv run pytest`
  - `pnpm web:build`
  - `uv run python scripts/run-local-fullstack-e2e.py`
  - 生产只读检查必须单独授权和单独记录。

第一批技术切片：

- [x] `slice-01-api-inventory`: 生成 backend routes、legacy templates、Next pages、frontend API client 的路由-数据流矩阵，见 `drafts/analysis/frontend-backend-separation-route-inventory-draft-20260702.md`。
- [ ] `slice-02-contract-boundary`: 以 `web/src/lib/api-types.ts` 和 `src/medical_audit_kb/api/routes_*.py` 为输入，定义前端可依赖的 API contract 缺口。
- [ ] `slice-03-client-runtime-boundary`: 解决当前 `api-client.ts` 只能在 browser/client runtime 调用的问题，明确 server component、client component、static export 三种访问边界。
- [ ] `slice-04-product-shell`: 以 `AuditTableTemplate`、audit finding table、workspace shell 为主流程，重写首屏与工作台，不先扩张营销式页面。
- [ ] `slice-05-local-gates`: 在新分支上先通过 `pnpm web:typecheck`、`pnpm web:test`、`uv run pytest`，再考虑 fullstack/e2e。

## T5: 当前执行停止点

- [x] 完成远端已合并历史分支删除后，重新输出 `git branch -a` 与 `git worktree list --porcelain`。
- [ ] 不做业务代码实现，直到 T4 inventory 和 API contract 草图确认。
- [ ] 不 merge、不 deploy、不执行生产写入、不调用 provider。
