---
title: 前后端完整分离执行计划与 Todo
doc_type: execution_plan
module: frontend-backend-separation
status: draft
created: 2026-07-02
updated: 2026-07-02
owner: codex
source: main-only-baseline-after-branch-consolidation
evidence_level: local-git-readonly-plus-static-source-inventory
---

# 前后端完整分离执行计划与 Todo

## 起点事实

- [x] 当前工作区：`/Users/pray/project/medical_audit`。
- [x] 当前分支：`main`。
- [x] 当前本地与远端分支集合：仅 `main` 与 `origin/main`。
- [x] 当前 `HEAD`: `6429b34278cf6d35e3477edc6bc3e5032df652f2`。
- [x] 已完成分支治理备份：`/Users/pray/.Codex/file-history/medical_audit-main-only-merge-20260702T141240Z`。
- [x] 本轮执行未做 deploy、production write、provider call、runtime switch。

## 第一性原理

1. Source of truth 只能有一个：代码主线只保留 `main`，产品运行时主体验只保留 Next 前端，后端只暴露 API contract。
2. 合并与重构不是同一件事：分支治理先确保可恢复、可验证、无多头；前后端分离再按 contract 与 runtime 边界推进。
3. 前端不能依赖后端实现细节：前端只依赖稳定 request/response schema、权限头、状态码、错误态和上传/下载语义。
4. 后端不能继续承担主产品 UI：`routes_pages.py` 与 Jinja templates 进入 legacy lane，只保留诊断、回退或待迁移能力。
5. 每一步必须可逆且可验收：每个 slice 都有明确输入、输出、测试命令和停止条件。
6. 证据层不能混用：docs-only、local test、local fullstack、production readonly、authorized live side effect 分开记录。

## 目标架构

- Backend: FastAPI，主 API 前缀为 `/api/v1`，保留 `/api/backend` 作为兼容或代理入口，但新产品代码优先面向 `/api/v1` contract。
- Frontend: Next.js 独立应用，主体验在 `web/src/app/` 与 `web/src/components/`，不再把 Jinja 页面作为主 UI 增量入口。
- Contract: `web/src/lib/api-types.ts`、后端 Pydantic response model、OpenAPI schema 三者需要收敛，避免 TypeScript 类型只靠手写同步。
- Runtime: browser client、server component、static export 三种访问模式显式分层。
- Product contract: 优先服务 `B2B医疗版`、Excel-template、audit-table、findings、documents、reports、remediation 的主流程。

## 总 Todo

### T0: Main-only 基线治理

- [x] 合并并删除多余分支，最终只保留 `main`。
- [x] 保存被删除 ref、worktree diff、untracked 文件与 stash 备份。
- [x] 验证 `git status --short --branch` 为 `## main...origin/main` clean。
- [x] 验证 `git ls-remote --heads origin` 仅有 `refs/heads/main`。
- [x] 停止使用长期 feature branch；后续默认在 `main` 上按小 slice 修改、验证、提交。

### T1: Contract inventory

- [x] 建立 backend routes、legacy templates、Next pages、frontend API client 的路由与数据流盘点。
- [x] 产物：`drafts/analysis/frontend-backend-separation-route-inventory-draft-20260702.md`。
- [x] 启动 API contract gap 表。
- [x] 用本地 in-memory/test `ApiState` 枚举 FastAPI OpenAPI：237 个 path；已核对 27 个前端 contract path，missing count 为 0。
- [x] 标记 legacy Jinja / review-task 相关 OpenAPI path：19 个。
- [x] 新增本地 schema diff 工具：`scripts/audit-frontend-backend-api-contract-schema.py`。
- [x] 对 33 个前端 API contract 做 top-level request/response schema 对照：7 个 aligned，3 个 field mismatch，23 个 schema gap，25 个 endpoint 缺少可对照 response schema。
- [ ] 把每个前端调用绑定到：endpoint、后端 route 文件、request type、response type、调用页面、运行时模式、权限头。
- [ ] 标记每个 endpoint 的状态：covered、needs hardening、runtime gap、legacy migration、static-data gap。
- [ ] 单独列出 `routes_pages.py` 中仍有 mutation 语义的 legacy endpoint。

### T2: API contract 收敛

- [ ] 明确 `/api/v1` 是新前端唯一主 contract；`/api/backend` 只用于 health、兼容或调试。
- [ ] 为 auth/session、projects、agents、documents、query、findings、analytics、workbench families 建立 contract checklist。
- [x] 将前端手写 `api-types.ts` 与 OpenAPI top-level request/response schema 做差异检查。
- [x] 校验 OpenAPI endpoint presence，确认当前前端引用的 27 个 contract path 均存在。
- [ ] 生成持久 OpenAPI snapshot，作为后续 contract test 输入。
- [x] 做 top-level 字段级 schema diff，确认当前仍存在 contract hardening gap。
- [ ] 补深层嵌套字段 diff，覆盖 item、store、metrics、permissions 等 nested object/array contract。
- [ ] 定义统一错误态：401/403/404/409/422/500 的前端表现与后端 payload。
- [ ] 定义上传/下载语义：multipart upload、download URL、权限头、文件大小和失败提示。

### T3: Runtime 边界拆分

- [ ] 保留现有 `api-client.ts` 的 browser/client-only 能力，但改名或拆分为 browser adapter。
- [x] 建立 `web/src/lib/api-endpoints.ts`，集中当前 browser API client 的 endpoint registry，保持现有路径语义不变。
- [x] 新增 `web/src/lib/api-client.server.ts` server-safe 基础 adapter，只允许 absolute backend URL，并从环境变量读取。
- [x] 新增 `web/src/lib/api-client.static.ts` static export fail-closed adapter。
- [ ] 明确 static export 模式下哪些页面使用 fixture/fallback，哪些页面必须延后到 hydrated client adapter。
- [ ] 为 Next rewrite 写 contract tests，覆盖 `MEDICAL_AUDIT_API_BASE_URL` 与 `MEDICAL_AUDIT_NEXT_EXPORT=1`。
- [ ] 禁止 server component 直接调用相对路径 `/api/v1/*`。

### T4: Legacy Jinja 迁移线

- [ ] 将 `routes_pages.py` 中只负责页面渲染的 endpoint 标记为 legacy UI。
- [ ] 将 review-task、report signoff、rectification、attachment 等 mutation endpoint 拆成 `/api/v1/review-tasks/*` contract 草图。
- [ ] 确认旧页面是否仍被生产只读路径访问；未授权前不做 production write 或迁移删除。
- [ ] 给 legacy 页面设定冻结规则：只修 blocking regression，不继续扩张业务 UI。

### T5: 前端重写第一阶段

- [ ] 固化 workspace shell：导航、顶部状态、项目上下文、权限状态、搜索后端状态。
- [ ] 以 audit-table 和 `AuditTableTemplate` 为主流程重写首屏与基金合规复核入口。
- [ ] 把静态 `portal-data.ts` 拆为 product fixture 与 API-backed adapter 两层。
- [ ] 保留用户已可用的 documents、query、findings、reports、remediation、rules、graph、archive 页面，但统一错误态、加载态和空态。
- [ ] 不做营销式 landing page；第一屏必须是可操作产品工作台。

### T6: 后端 API 硬化

- [ ] 为 contract-critical endpoint 补 response model 或 schema snapshot。
- [ ] 为 mutation endpoint 增加权限、审计日志、幂等或冲突处理说明。
- [ ] 保留 production readonly/protected endpoint gate。
- [ ] provider call、runtime switch、生产写入继续单独授权。

### T7: 验证门禁

- [ ] Docs-only slice: `git diff --check`、frontmatter 检查、链接路径检查。
- [ ] Frontend type gate: `pnpm web:typecheck`。
- [x] Frontend targeted unit gate: `./node_modules/.bin/vitest run src/lib/api-endpoints.test.ts src/lib/api-client.test.ts`。
- [x] Frontend targeted type gate: `./node_modules/.bin/tsc --noEmit`。
- [x] Frontend runtime adapter unit gate: `./node_modules/.bin/vitest run src/lib/api-client.server.test.ts src/lib/api-client.static.test.ts`。
- [ ] Frontend full unit gate: `pnpm web:test`。
- [ ] Frontend build gate: `pnpm web:build`。
- [ ] Backend unit gate: `uv run pytest`。
- [ ] Local fullstack gate: `pnpm local:fullstack:e2e`。
- [ ] Browser E2E gate: `pnpm web:e2e`。
- [ ] Production readonly gate: 需要单独授权，执行后仍只能声明 readonly evidence，不能声明 deploy 或 live mutation。

### T8: 完成定义

- [ ] `main` 仍是唯一长期分支。
- [ ] 新前端主工作流不依赖 Jinja 页面。
- [ ] 新前端所有 backend 调用都有 contract、类型、错误态、权限头和测试覆盖。
- [ ] 后端 legacy 页面进入冻结或迁移完成状态。
- [ ] local type/test/build/fullstack 证据齐全。
- [ ] 生产只读验证与 deploy/production mutation 分层记录。

## 当前正在执行的最小闭环

- [x] `slice-01-api-inventory`: 已完成路由与数据流盘点。
- [x] `slice-02-contract-boundary`: 已创建 contract gap 草图。
- [x] `slice-02-contract-boundary`: 完成 OpenAPI endpoint presence 验证。
- [x] `slice-02-contract-boundary`: 完成 OpenAPI/schema top-level 字段级差异验证。
- [x] `slice-03-client-runtime-boundary`: 建立 endpoint registry，为 browser/server/static adapter 拆分做路径集中化。
- [x] `slice-03-client-runtime-boundary`: 建立 server/static adapter 基础文件和测试。
- [ ] `slice-03-client-runtime-boundary`: 将具体页面或 server component 调用迁移到 server/static adapter。
- [ ] `slice-04-product-shell`: 从 audit-table 主流程开始重写首屏体验。

## 不确定项

- 未验证当前生产是否仍有人直接访问 legacy Jinja 页面。
- 未生成持久 OpenAPI snapshot；本轮只生成 ignored `tmp/outputs` 审计输出。
- 未完成深层 nested schema diff。
- 未运行本地服务、E2E、production readonly smoke。
- `api-types.ts` 与后端 response model 尚未完全一致；本轮证据显示仍有 response schema gap 和字段 requiredness gap。
