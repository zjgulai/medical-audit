---
title: PPT 生产闭环原子提交计划
doc_type: analysis
module: release
status: promotion-closeout
created: 2026-07-15
updated: 2026-07-15
owner: self
source: human+ai
branch: codex/ppt-production-closure-20260715
evidence_grade: L2-local-validated
draft_pr: 236
promotion_status: draft-pr-open
production_write: false
provider_call: false
database_write: false
deploy_execution: false
---

# PPT 生产闭环原子提交计划

## 目标与边界

- 将 Loop 56 的三个本地闭环按可独立回滚的 concern 提交，并保持每个 staged manifest 可核对。
- push 当前 `codex/ppt-production-closure-20260715`，创建 Draft PR，作为后续 Ready、merge、clean-main deploy preflight 与生产部署的唯一候选入口。
- 本门不 merge、不 deploy、不运行生产业务写入、不调用 provider。

## Commit 1 — 后端持久化业务合同

Reason: 在一个可部署后端单元内同时提供 owner-scoped 历史、人工转任务、受控项目创建、动态项目可见范围和 fail-closed 持久化能力。

Candidate files:

- `docs/api/knowledge-query-contract-p5-stable.md`
- `docs/api/knowledge-query-contract-v1.json`
- `docs/architecture/architecture-auth-rbac-stable.md`
- `src/medical_audit_kb/api/audit_log_store.py`
- `src/medical_audit_kb/api/auth.py`
- `src/medical_audit_kb/api/project_member_store.py`
- `src/medical_audit_kb/api/query_history_store.py`
- `src/medical_audit_kb/api/review_task_store.py`
- `src/medical_audit_kb/api/routes_pages.py`
- `src/medical_audit_kb/api/routes_projects.py`
- `src/medical_audit_kb/api/routes_query.py`
- `src/medical_audit_kb/api/routes_workbench.py`
- `tests/knowledge_query/test_api.py`
- `tests/knowledge_query/test_project_creation_api.py`
- `tests/knowledge_query/test_query_history_review_task.py`

Verification: targeted backend `28`、全量 Pytest `645`、Ruff、Mypy、contract JSON syntax、cached diff check。

## Commit 2 — 项目与历史任务前端交互

Reason: 让前端只在读取与操作级持久化能力同时 ready 时开放项目/成员/历史转任务 mutation，并显式呈现 degraded 状态。

Candidate files:

- `web/src/app/(workspace)/projects/page.test.tsx`
- `web/src/app/globals.css`
- `web/src/components/portal/project-management-workbench.tsx`
- `web/src/components/replica/replica-project-workbench.test.tsx`
- `web/src/components/replica/replica-project-workbench.tsx`
- `web/src/components/replica/replica-shell.test.tsx`
- `web/src/components/replica/replica-shell.tsx`
- `web/src/lib/api-client.test.ts`
- `web/src/lib/api-client.ts`
- `web/src/lib/api-types.ts`
- `web/src/lib/audit-user.test.ts`
- `web/src/lib/audit-user.ts`
- `web/src/lib/portal-data.ts`
- `web/src/lib/reference-replica-data.ts`

Verification: 相关 Vitest、全量 Vitest `295`、typecheck、lint、build `24/24`、cached diff check。

## Commit 3 — 文档统计未知值语义

Reason: 文档数只接受 `document_count`；未知保持 `null/待同步`，真实 `0` 保持 `0`，避免以 chunk 数冒充文档数。

Candidate files:

- `web/src/app/(workspace)/documents/page.test.tsx`
- `web/src/app/(workspace)/documents/page.tsx`
- `web/src/lib/replica-adapters.test.ts`
- `web/src/lib/replica-adapters.ts`

Verification: document/adapter Vitest、typecheck、lint、build `24/24`、cached diff check。

## Commit 4 — 产品与验收依据

Reason: 固化原始 PPT 15 页逐项状态、产品合同、本地证据、未完成业务输入与发布边界，禁止用本地通过冒充已部署。

Candidate files:

- `docs/product/product-prd-medical-audit-v1-stable.md`
- `drafts/analysis/ppt-production-closure-acceptance-matrix-draft-20260715.md`
- `drafts/analysis/ppt-production-closure-atomic-commit-plan-draft-20260715.md`

Verification: frontmatter/manual manifest、`git diff --cached --check`、最终 worktree clean。

## Commit 5 — 推广状态账本

Reason: 在 Draft PR 和 Commit 4 均已真实存在后，记录实际 commit chain、PR head/base、文件数、mergeability、checks 与下一门边界；不得在前一 commit 预写外部结果。

Candidate files:

- `.kiro/plan/findings.md`
- `.kiro/plan/progress.md`
- `.kiro/plan/task_plan.md`
- `drafts/analysis/ppt-production-closure-atomic-commit-plan-draft-20260715.md`

Verification: GitHub state refresh、remote/local head equality、cached diff check、最终 worktree clean。

## Draft PR initial evidence

- PR：`#236`，`https://github.com/zjgulai/medical-audit/pull/236`。
- 初始 base：`main@f2e2c7b7d5746d2ebd0347c42a4b7d427aac1617`。
- 初始 head：`c03b5ab017e697ab18264a1b4fb6bfbe3e5fe1bf`，与远端分支一致。
- 初始 manifest：`3` 个业务 commit、`33` 个文件；GitHub 报告 `MERGEABLE/CLEAN`。
- `statusCheckRollup=[]`，`gh pr checks` 返回“no checks reported”；只能表述为 checks 未配置/未报告。

After Commit 4:

- head：`d6b862cbfcb9173ef820628f906eec90dd8615b4`，local/remote 相等。
- manifest：`4` commits、`36` files；GitHub 仍为 `OPEN/Draft/MERGEABLE/CLEAN`。
- checks 仍为 `0`，没有 CI passed 证据。
- Commit 5 是包含本段推广账本的 commit；其自身 SHA 与最终 push 结果由提交后的 GitHub 外部状态证明，不在文件内预写。

## Promotion gate

1. 四个 commit 均使用显式路径 staging；禁止 `git add .`。
2. 每次 commit 前核对 cached name-status/stat/check，commit 后确认 index 为空。
3. 前三个业务 commit 完成后确认 `origin/main` 是分支祖先，push 当前分支并创建 Draft PR。
4. 读取实际 PR head/base、文件集合、mergeability 和 checks；checks 未配置时按字面报告，再创建第四个产品/验收 docs-only commit 并二次 push。
5. 刷新 Draft PR 状态，创建第五个推广状态账本 commit 并最终 push。
6. 确认五个 commit、完整 manifest、worktree clean 与 Draft PR head 一致。
7. PR Ready、merge、deploy preflight、生产 `--execute` 和生产业务写入继续作为后续独立门。

## 当前边界

- `production unchanged`
- `provider_call=false`
- `database_write=false`
- `deploy_execution=false`
