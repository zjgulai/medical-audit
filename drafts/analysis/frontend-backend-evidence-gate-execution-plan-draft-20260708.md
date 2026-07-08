---
title: 前后端证据门禁修复执行计划
doc_type: execution-plan
module: frontend-backend
status: draft
created: 2026-07-08
updated: 2026-07-08
owner: codex
source: local-clean-worktree
---

# 前后端证据门禁修复执行计划

## 目标

把当前重构前端的“页面已渲染”和“真实后端数据已接通”拆成可见证据，防止知识库、文档检索、知识图谱等页面在 API 不可用、fixture 兜底或只读种子数据时被误判为生产数据闭环。

## 本轮范围

- 在干净 `origin/main` worktree 上实施，不触碰根目录脏树。
- 只改前端运行时证据显示、图谱 seed 判定和相关测试。
- 不改 UI 主风格、不改生产数据、不执行生产部署。

## 已执行

- 新增 `ReplicaRuntimeBadge`，统一显示 `后端数据`、`后端+本地`、`本地样例`、`后端种子数据`。
- 知识库页、文档检索页、知识图谱页增加可见数据来源标签。
- 图谱 adapter 识别 `Readonly*Seed`，追加 `backend-seed-data` issue。
- 图谱页在 seed 数据下显示明确提示：当前不是持久业务关系。
- 增加运行时单测，锁定 `ReadonlyGraphWorkbenchSeed` 不可被当作普通 API 联通。

## 验收记录

- `corepack pnpm test`：19 files / 95 tests passed。
- `corepack pnpm typecheck`：通过。
- `corepack pnpm lint`：通过。
- `corepack pnpm build`：通过，生成 24 个静态页面。
- 本地浏览器验收：登录后 `/knowledge-base`、`/documents`、`/graph` 均显示页面主体和 `本地样例` 标签。

## 2026-07-08 复核记录

- PR 状态：#199 `Expose replica data source evidence`，`OPEN / CLEAN`，base 为 `main`，head 为 `codex/frontend-backend-evidence-gate-20260708`。
- 本地验证：
  - `corepack pnpm web:test`：19 files / 95 tests passed。
  - `corepack pnpm web:typecheck`：通过。
  - `corepack pnpm web:lint`：通过。
  - `corepack pnpm web:build:static`：通过，生成 24 个静态页面。
- 本地浏览器验收模式：`frontend-only-next-start`，服务地址 `http://localhost:3030`，通过 localStorage 注入项目自身的登录态。
- 页面证据：
  - `/knowledge-base`：进入工作区页面，主标题为 `知识库分类`，可见 `本地样例` 标签，badge 为 `本地样例3 项待接入`。
  - `/documents`：进入工作区页面，主标题为 `文档检索`，可见 `本地样例` 标签，badge 为 `本地样例3 项待接入`。
  - `/graph`：进入工作区页面，主标题为 `知识图谱`，可见 `本地样例` 标签，badge 为 `本地样例1 项待接入`。
- 边界说明：本轮浏览器验收只启动 Next 预览，未启动 8021 后端；本地 API 代理噪声按 `backend_absent_transport_noise` 归类，不作为生产联通结论。

## 下一步 TODO

- [x] 推送分支并创建 PR。
- [x] 复跑 PR 分支前端测试、类型检查、lint、静态构建。
- [x] 在认证态下完成本地浏览器验收。
- [ ] PR 合并前确认 CI 与 review。
- [ ] 合并到 `main` 后从干净 `main` 执行生产部署。
- [ ] 生产浏览器验收 `/knowledge-base`、`/documents`、`/graph` 的数据来源标签。
- [ ] 下一批后端接入：让知识库和文档页在生产返回 `后端数据` 或 `后端+本地`，让图谱从真实知识库、引用、疑点、整改和报告关系生成。
