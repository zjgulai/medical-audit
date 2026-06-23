---
title: 医保审计系统 Auth Workbench 发布收口计划
doc_type: workflow
module: release
topic: auth-workbench-release-plan
status: stable
created: 2026-06-23
updated: 2026-06-23
owner: self
source: human+ai
---

# 医保审计系统 Auth Workbench 发布收口计划

## 1. 发布目标

本次发布目标是把本地已验证的 UI、账号角色过渡层、`X-Tenant-Id` 契约、受控 API 鉴权、Workbench API、权限只读 smoke 和本地全栈 E2E 能力整理为干净 release candidate，并在授权后部署到 `https://audit.lute-tlz-dddd.top`。

当前执行边界：

- `release_candidate_base=origin/main`。
- `production_current_sha=550a445012267ba1211f5881b1d441264f3a3056`，生产只读巡检已确认 healthy。
- `deploy_execute_status=not_authorized`：未获得单独生产部署授权前，只允许本地质量闸、生产只读审计和部署 preflight。
- `provider_call_status=not_called`：本批不验证生成模型 provider。
- `production_write_status=not_started`：写入型生产验收必须在部署和只读权限门禁通过后单独申请授权。

## 2. Release Manifest

纳入发布：

- 后端认证与权限：`/auth/*` 过渡层、持久化用户/角色/项目 scope、停用用户拒绝、拒绝日志和受控 API 鉴权中间件。
- 租户契约：`X-Tenant-Id` 在后端强制鉴权和前端 API client 统一携带。
- Workbench API：`/graph/workbench`、`/rules/workbench`、`/remediation/workbench`、`/archive/workbench`、`/reports/workbench`。
- 前端入口：登录页、工作区壳层、角色上下文、核心导航、智能体、文档、数据分析、报告、图谱、规则、整改和归档页面的 API-first 显示。
- 脚本与门禁：`scripts/run-local-fullstack-e2e.py`、`scripts/run-controlled-api-readonly-permission-smoke.py`、`pnpm local:permission:readonly`、`pnpm production:permission-readonly`。
- 测试和文档：API、脚本、页面、API client、E2E 测试，以及本发布计划和项目状态同步文档。

排除发布：

- `.codex/`、`.kiro/`、`.playwright-mcp/`、`ref/`、`opendesign/`、`drafts/`、`tmp/`。
- 未纳入 manifest 的参考材料、历史截图、一次性浏览器状态、未审核草稿和本地运行缓存。
- 真实医院 SSO、对象存储、外部杀毒/DLP、证书级电子签章、provider 生成答案和真实医院数据 UAT。

Schema 规则：

- 仅允许 `CREATE TABLE IF NOT EXISTS`、`CREATE INDEX IF NOT EXISTS`、兼容字段和幂等更新。
- 禁止 `DROP TABLE`、`TRUNCATE`、无 guard 的 `DELETE FROM` 和破坏性 `ALTER TABLE DROP`。
- 生产执行前必须先由部署脚本创建 DB 备份；schema 应用失败即停止。

## 3. 部署前 TODO

| 编号 | TODO | 验收口径 |
| --- | --- | --- |
| PRE-01 | 从 `origin/main` 创建干净 release worktree | `git status` 只包含 manifest 内变更；当前脏工作树不参与部署 |
| PRE-02 | 移植 manifest 文件并排除非发布材料 | 未出现 `.codex/.kiro/.playwright-mcp/ref/opendesign/drafts/tmp` |
| PRE-03 | 保留 `origin/main` 的个人材料 readiness 脚本与测试 | `test_audit_production_personal_material_indexing_readiness_*` 存在并通过 |
| PRE-04 | 完成本地质量闸 | ruff、mypy、pytest、web lint/typecheck/test/build、本地 fullstack E2E、本地权限 smoke、`git diff --check` 通过 |
| PRE-05 | 执行生产只读部署状态审计 | expected SHA 和 `matching_embedding_count=49051` 通过 |
| PRE-06 | 执行部署 preflight | 默认 preflight 通过；未使用 `--execute`、`--allow-dirty` |
| PRE-07 | 生成上线审批摘要 | 记录 release SHA、manifest、schema 影响、备份/回滚路径和测试报告 |

### 当前执行状态

截至 2026-06-23 12:43 Asia/Shanghai：

- `PRE-01/PRE-02`：已在 `/Users/pray/project/medical_audit_release_auth_workbench_20260623` 创建 release worktree，分支为 `codex/medical-audit-release-auth-workbench-20260623`，从 `origin/main` 精确移植 manifest。
- `PRE-03`：已恢复 `origin/main` 的个人材料 readiness 脚本与测试，并修复移植过程中覆盖掉的对象存储/governance schema 兼容点。
- `PRE-04`：本地质量闸已通过：`uv run ruff check .`、`uv run mypy src`、`uv run pytest tests/knowledge_query`（344 passed）、`pnpm web:lint`、`pnpm web:typecheck`、`pnpm web:test`（11 files / 91 tests）、`pnpm web:build`、`pnpm local:fullstack:e2e`（16 passed）、`pnpm local:permission:readonly`（35 probes / 0 issues）、`git diff --check`。
- `pnpm local:postgres:readonly`：非阻断 blocked；本机 `localhost:5433` PostgreSQL 连接被拒绝，未记为本地 PostgreSQL 验收通过。
- `PRE-05/PRE-06/PRE-07`：待 release commit 后执行；未执行生产部署，未执行生产写入，未调用生成 provider。

## 4. 部署执行门禁

生产部署必须同时满足：

- 用户单独确认执行生产 `--execute`。
- release worktree `git status` 清晰，不允许 `--allow-dirty`。
- 本地质量闸、生产只读部署状态审计和部署 preflight 全部通过。
- 部署命令包含 `--execute --confirm-production audit.lute-tlz-dddd.top --apply-schema`，默认不包含 `--include-review-write`。

部署后阻断门禁：

1. 生产部署状态审计必须显示 release SHA 已写入 `.deploy-sha`，容器 healthy，Nginx mount 正常，search backend ready。
2. 生产权限只读强制验收必须通过；任何 issue 阻断继续验收。
3. 生产前端验收必须 `status=pass`，且 P0/P1 均为 0。
4. 生产 E2E smoke 只执行默认只读模式；写入型验收另行授权。

## 5. 上线功能测试计划

权限与认证：

- `/api/v1/auth/roles` 和 `/api/v1/auth/session` 返回正常。
- 匿名或缺 `X-Tenant-Id` 访问受控 API 返回 401/403。
- 管理员带齐 `X-User-Id`、`X-Role`、`X-Project-Key`、`X-Tenant-Id` 时返回 200。
- `/audit/logs` 和 `/audit/logs/export` 权限拒绝/允许路径均正确。

页面与 Workbench：

- 覆盖 `/login`、`/workspace`、`/chat`、`/agents`、`/agent-market`、`/documents`、`/analytics`、`/reports`、`/projects`、`/graph`、`/rules`、`/remediation`、`/archive`、`/findings`、`/knowledge-query`。
- 覆盖 `/pages/chat`、`/pages/query`、`/pages/review-tasks`、`/pages/index-admin`、`/pages/audit-logs`。
- `/graph/workbench`、`/rules/workbench`、`/remediation/workbench`、`/archive/workbench`、`/reports/workbench` 生产不应再返回 404。

业务功能：

- AI 对话返回 citations、basis groups 和 preview chunk；如未配置 provider，允许 fallback answer，但必须保留 `no provider call` 边界。
- 智能体广场、我的智能体、版本治理、审批激活、角色禁用态和进入对话链路可用。
- 文档检索的来源过滤、`title_only`、搜索历史、个人材料列表、治理状态和受控下载可用。
- 审计底稿模板 registry、Word 下载和报告记录可用；不宣称电子签章完成。
- 图谱、规则、整改、归档只验收 API-first 只读展示；真实规则运行、整改写入和归档签名生成作为上线后 TODO。

回归与边界：

- 回归检查共享域名：`kg.lute-tlz-dddd.top`、`video.lute-tlz-dddd.top`、`voc.lute-tlz-dddd.top`、`lute-tlz-dddd.top`。
- 页面不得出现 404、500、横向溢出、关键文案缺失或占位词。
- provider 生成答案、真实 SSO、对象存储、外部杀毒/DLP、电子签章和真实医院数据 UAT 不在本批完成口径内。

## 6. 上线后 TODO

| 优先级 | TODO | 边界 |
| --- | --- | --- |
| P0 | 真实医院 SSO claims、正式租户身份来源、账号禁用/移除治理、生产权限复验常态化 | 不阻断本批过渡层上线；阻断真实医院 UAT |
| P0 | 外部杀毒/DLP、脱敏改写、对象存储、个人材料异步向量入索引 | 当前仅本地策略和受控下载 |
| P0 | 证书级电子签章、长期留存介质、归档恢复演练 | 当前报告不作为证书级正式归档 |
| P1 | 图谱/规则/整改/归档从只读 API 推进到真实写入闭环 | 当前只验收 API-first 只读展示 |
| P1 | 智能体正式租户 scope、完整下架/归档治理、生产调用统计 | 当前仍是过渡层和本地租户头契约 |
| P2 | provider 生成答案生产 gate、医院现场操作手册、角色培训和灰度配置 | 当前仅证明 fallback citation answer 和操作入口 |
