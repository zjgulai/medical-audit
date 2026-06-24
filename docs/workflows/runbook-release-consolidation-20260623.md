---
title: 发布候选收口完整执行手册（在本机执行）
doc_type: workflow
module: project-governance
topic: release-consolidation-runbook
status: draft
created: 2026-06-23
updated: 2026-06-23
owner: self
source: human+ai
---

# 发布候选收口完整执行手册（在本机执行）

> 沙箱无法访问 GitHub 且发布 worktree 不在挂载内，以下全部在你本机执行。
> 已核验：`push` 成功（origin 上已有发布分支）、文档已入库（发布分支 = `main + 6`，tip `c10b3d3b`）、发布分支已逐字节捕获全部新代码。
> 仍待你本机确认/执行：质量闸、合入 main、同步本地 main、生产部署与验收、worktree/分支清理。

## 0. 路径与变量（先设好，后续命令直接用）

```bash
REL=/Users/pray/project/medical_audit_release_auth_workbench_20260623   # 发布分支 worktree
MAINWT=/Users/pray/project/medical_audit_minimal_pr                     # main worktree
STALE=/Users/pray/project/medical_audit                                 # 陈旧 worktree(answer-provider-gate-plan)
BR=codex/medical-audit-release-auth-workbench-20260623
DOMAIN=audit.lute-tlz-dddd.top
```

## 1. 现状核验（确认 push/合并真实状态）

```bash
cd "$REL"
git fetch origin --prune
git log origin/main --oneline -3            # 顶部若已是发布分支合并提交 = 已合入 main
git rev-list --left-right --count origin/main...origin/$BR   # 右值=0 表示发布分支已全部进 main
git status -sb
```

判读：若 `origin/main` 顶部还不是发布分支的合并 → 继续第 3 步合并；若已是 → 跳到第 4 步同步本地 main。

## 2. 在发布分支跑全量质量闸（合并前必须全绿）

```bash
cd "$REL"
uv run ruff check .
uv run mypy src
uv run pytest tests/knowledge_query
pnpm --filter medical-audit-web lint
pnpm --filter medical-audit-web typecheck
pnpm --filter medical-audit-web test
pnpm --filter medical-audit-web build
uv run python scripts/run-local-fullstack-e2e.py
```

预期基线：mypy 88 files、pytest ~288–292 passed、web 91 tests、build 21/21、E2E 16 passed。任一不过先贴输出再合并。

## 3. 合入 main（二选一）

方式 A — GitHub 网页/CLI 开 PR 评审后合并（推荐，留评审痕迹）：

```bash
cd "$REL"
gh pr create --base main --head "$BR" \
  --title "release: auth workbench + controlled api auth" \
  --body "本地权限底座/受控API鉴权/workbench API/docx导出/登录页；含深度审计报告。详见 docs/workflows/workflow-deep-audit-and-remediation-plan-20260623.md"
gh pr merge "$BR" --merge        # 评审通过后执行
```

方式 B — 本地 fast-forward 合并后推送（发布分支已含 main，可 FF）：

```bash
cd "$MAINWT"
git fetch origin --prune
git checkout main && git pull --ff-only origin main
git merge --ff-only "$BR"
git push origin main
```

## 4. 同步所有本地 worktree 的 main

```bash
cd "$MAINWT" && git pull --ff-only origin main
git log main --oneline -1        # 确认本地 main 已是合并后的 tip
# 校验新代码已进 main：
git cat-file -e main:src/medical_audit_kb/api/auth.py && echo "auth.py in main OK"
git cat-file -e main:src/medical_audit_kb/api/routes_workbench.py && echo "routes_workbench in main OK"
```

## 5. 生产部署（默认只读 preflight → 备份 → 写入 → smoke）

> 本次发布**新增 auth 数据表**，部署须带 `--apply-schema`。脚本默认是只读 preflight，`--execute` 才写生产，并要求 `--confirm-production`。SSH key 用项目内 `ai_video.pem`。

```bash
cd "$MAINWT"            # 从干净 main 部署
# 5.1 只读 preflight（不写生产，先看通过）
uv run python scripts/deploy-tencent-cloud-production.py

# 5.2 正式部署（写生产，自动按 stamp 做远端备份；含 schema 应用与部署后 smoke）
uv run python scripts/deploy-tencent-cloud-production.py \
  --execute --confirm-production "$DOMAIN" \
  --apply-schema --include-review-write
```

> 部署前确认：`git status` 干净（脚本默认拒绝 dirty，勿用 `--allow-dirty` 绕过）；`ai_video.pem` 在当前目录；如本次要在生产开启受控 API 鉴权，需同时配置生产 env `MEDICAL_AUDIT_CONTROLLED_API_AUTH` 和 Nginx 头注入（见 `docs/workflows/workflow-tencent-cloud-audit-deployment-stable.md`），否则保持默认关闭以免锁死访问。

## 6. 生产验收（只读 smoke + 部署状态审计 + 前端语义）

```bash
cd "$MAINWT"
# 部署状态只读审计（用合并后的真实 SHA 和当前 embedding 计数 49051）
uv run python scripts/audit-tencent-cloud-deployment-state.py \
  --expected-deploy-sha "$(git rev-parse HEAD)"
# 生产 E2E 只读 smoke（注意当前匹配 embeddings=49051）
uv run python scripts/run-production-e2e-smoke.py --expected-matching-embeddings 49051
# 权限只读 smoke（观测模式）
pnpm production:permission-readonly
# 前端语义验收
pnpm production:frontend-acceptance
```

判读：状态审计 `status=pass`、`issues=[]`；E2E smoke `pass`；前端 `p0=[] p1=[]`。

## 7. 清理（确认合并 + 部署 + smoke 全通过后再做）

```bash
# 7.1 删除陈旧 worktree 和分支（其成果已在 main）
cd "$MAINWT"
git worktree remove "$STALE"
git worktree prune
git branch -D codex/answer-provider-gate-plan

# 7.2 远端：删已合并的历史 PR 分支（保留两个尚有未并提交的）
git branch -r --merged origin/main | sed 's#origin/##' | grep '^ *codex/' \
  | grep -vE 'docs-only-merge-sha-boundary|documents-history-production-sync|medical-audit-release-auth-workbench' \
  | xargs -I{} git push origin --delete {}

# 7.3 本地：删已并入 main 的死分支
git branch --merged main | grep 'codex/' | grep -v 'answer-provider-gate-plan' | xargs -I{} git branch -d {}

# 7.4 复核
git worktree list
git branch -a | wc -l
```

## 8. 完成判据（全绿才算收口）

- `origin/$BR` 已存在；发布分支已合入 main（`origin/main...origin/$BR` 右值=0）。
- 质量闸全绿。
- 生产部署 `status=pass`、新 auth 表已 apply、部署后 smoke `pass`。
- 生产只读权限 smoke / 前端语义验收通过。
- 陈旧 worktree/分支清理完毕，`git branch -a` 数量回到个位数活跃分支。
- 审计报告与本 runbook 已在 main。
