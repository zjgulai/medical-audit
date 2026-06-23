---
title: 发布候选收口执行手册（在本机执行）
doc_type: workflow
module: project-governance
topic: release-consolidation-runbook
status: draft
created: 2026-06-23
updated: 2026-06-23
owner: self
source: human+ai
---

# 发布候选收口执行手册（在本机执行）

> 沙箱环境无法访问 GitHub（代理 403），发布分支 worktree 也不在沙箱挂载内，因此以下命令请在你本机（`/Users/pray/...`）执行。
> 已完成的只读核验结论：发布分支 `codex/medical-audit-release-auth-workbench-20260623` = `main` + 5 个干净提交，且**已逐字节捕获陈旧 worktree 的全部新代码**（auth/workbench/docx/登录页/E2E 脚本等均 0-diff）。未进发布分支的只有非交付物（`.codex/ .kiro/ drafts/ opendesign/ ref/`）和新审计报告。

## 当前 worktree 布局（实测）

| worktree 路径 | 分支 | 状态 |
| --- | --- | --- |
| `/Users/pray/project/medical_audit` | `codex/answer-provider-gate-plan` (b298c6c8, 落后 main 138) | 陈旧脏 worktree，成果已被发布分支捕获，待丢弃 |
| `/Users/pray/project/medical_audit_release_auth_workbench_20260623` | `codex/medical-audit-release-auth-workbench-20260623` (main+5) | **发布候选**，未推远端 |
| `/Users/pray/project/medical_audit_minimal_pr` | `main` (950ecbda) | |
| `~/.config/superpowers/worktrees/.../frontend-plan-02-projects-dashboard` | `codex/frontend-plan-02-projects-dashboard` | |

## Step 1 — 立刻推送发布候选（最高优先，消除唯一高危点）

```bash
cd /Users/pray/project/medical_audit_release_auth_workbench_20260623
git push -u origin codex/medical-audit-release-auth-workbench-20260623
```

完成后 `release-auth-workbench` 即有 GitHub 异地副本，F-01 解除。

## Step 2 — 把新审计报告纳入发布分支

报告与本手册当前在陈旧 worktree 内：
`/Users/pray/project/medical_audit/docs/workflows/workflow-deep-audit-and-remediation-plan-20260623.md`
`/Users/pray/project/medical_audit/docs/workflows/runbook-release-consolidation-20260623.md`

```bash
cd /Users/pray/project/medical_audit_release_auth_workbench_20260623
cp /Users/pray/project/medical_audit/docs/workflows/workflow-deep-audit-and-remediation-plan-20260623.md docs/workflows/
cp /Users/pray/project/medical_audit/docs/workflows/runbook-release-consolidation-20260623.md docs/workflows/
git add docs/workflows/workflow-deep-audit-and-remediation-plan-20260623.md docs/workflows/runbook-release-consolidation-20260623.md
git commit -m "docs: add deep audit report and release consolidation runbook"
git push
```

## Step 3 — 在发布分支跑全量质量闸（不要在陈旧 worktree 跑）

```bash
cd /Users/pray/project/medical_audit_release_auth_workbench_20260623
uv run ruff check .
uv run mypy src
uv run pytest tests/knowledge_query
pnpm --filter medical-audit-web lint
pnpm --filter medical-audit-web typecheck
pnpm --filter medical-audit-web test
pnpm --filter medical-audit-web build
uv run python scripts/run-local-fullstack-e2e.py
```

预期（对照台账历史基线）：mypy 88 files、pytest ~288–292 passed、web 91 tests、build 21/21、E2E 16 passed。

## Step 4 — 开 PR 合入 main（人工评审后再合，不要自动合）

```bash
cd /Users/pray/project/medical_audit_release_auth_workbench_20260623
gh pr create --base main --head codex/medical-audit-release-auth-workbench-20260623 \
  --title "release: auth workbench + controlled api auth (main+5)" \
  --body "发布候选：本地权限底座/受控API鉴权/workbench API/docx导出/登录页。已通过全量质量闸。详见 docs/workflows/workflow-deep-audit-and-remediation-plan-20260623.md。"
```

## Step 5 — 合并并生产部署后，再清理（务必在确认无遗漏后）

```bash
# 确认发布候选已合入 main 且生产部署+只读 smoke 通过后：
git worktree remove /Users/pray/project/medical_audit   # 丢弃陈旧 answer-provider-gate-plan worktree
git branch -D codex/answer-provider-gate-plan            # 删除陈旧分支（其成果已在 main）
```

> 注意：`git worktree remove` 会删除该 worktree 目录下的未提交内容。执行前确认陈旧 worktree 里没有你还想保留的零散改动（核验已确认所有新代码均已进发布分支；剩余 untracked 仅为 `.codex/ .kiro/ drafts/ opendesign/ ref/` 等非交付物，按需另行备份 `ref/` 参考资料和 `opendesign/` 设计资产）。

## Step 6 — 分支治理（Phase B，可在主线收口后进行）

```bash
# 远端：删除已 0-ahead origin/main 的历史 PR 分支（保留 docs-only-merge-sha-boundary、documents-history-production-sync 待确认）
git branch -r --merged origin/main | grep 'origin/codex/' | sed 's#origin/##' \
  | grep -vE 'docs-only-merge-sha-boundary|documents-history-production-sync' \
  | xargs -I{} git push origin --delete {}

# 本地：删除已并入 main 的死分支（先 review 列表，再删）
git branch --merged main | grep codex/ | xargs -I{} git branch -d {}
```

## 完成判据

- `release-auth-workbench` 已在 GitHub；
- 全量质量闸绿；
- PR 评审通过并合入 main；
- 生产从 main 部署并通过只读 smoke；
- 陈旧 worktree/分支已移除，`git worktree list` 与 `git branch -a` 清爽可解释。
