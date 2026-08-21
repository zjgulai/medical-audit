---
title: 生产证据副作用合同实施与部署计划
doc_type: implementation-plan
module: release-evidence
status: local_validation_and_review_passed_pr_pending
created: 2026-07-15
updated: 2026-08-15
owner: self
source: human+ai
baseline: origin-main@2d790375621bafa3dd564b1a1464f3e229a053a2
production_runtime_sha: b88ecdff7f773c8990454009d4a2b33ea8fdc2d4
evidence_grade: L2-local-validated
deploy_execute: false
---

# 生产证据副作用合同实施与部署计划

## 完成标准

- 权限 smoke 默认仅执行代码审计确认安全的 2 个公共 GET，33 个候选明确 skipped；完整 35 项必须显式授权并提供固定确认值。
- 前端完整浏览器验收默认在任何本地/网络副作用前失败关闭；生产写模式必须双重确认并报告 `audit-log-only`。
- 自动化测试验证 probe 清单、报告合同、生产确认门禁和前端 gate 的不一致拒绝路径。
- Codex review 无可接受的 P0/P1；分支经 Ready PR 合并且远端分支保留。
- 仅从 clean `main` 的精确 merge SHA 部署；备份、运行版本、L3/L4 验收证据分别保存。

## Task 1：实现和局部验证

- 修改 `scripts/run-controlled-api-readonly-permission-smoke.py`。
- 修改 `scripts/run-production-frontend-acceptance.mjs` 与 gate。
- 更新 `tests/knowledge_query/test_scripts.py`、设计 spec 和 `.kiro/plan/*`。
- 运行：

```bash
uv run pytest tests/knowledge_query/test_scripts.py
uv run ruff check scripts/run-controlled-api-readonly-permission-smoke.py tests/knowledge_query/test_scripts.py
uv run mypy scripts/run-controlled-api-readonly-permission-smoke.py
node --check scripts/run-production-frontend-acceptance.mjs
node --check scripts/run-production-frontend-acceptance-gate.mjs
git diff --check
```

## Task 2：全量本地门禁与审查

```bash
uv run ruff check .
uv run mypy src scripts/deploy-tencent-cloud-production.py scripts/run-production-e2e-smoke.py scripts/run-controlled-api-readonly-permission-smoke.py
uv run pytest -q
pnpm web:typecheck
pnpm web:lint
pnpm web:test
pnpm web:build:static
pnpm local:fullstack:e2e
```

随后运行 `codex review --base origin/main`。任何代码修正都必须重跑相关测试和 review。

## Task 3：PR 与 merge

- 原子提交预期文件，不包含 `tmp/`、截图、secret 或其他工作树内容。
- push `codex/evidence-tool-readonly-contract-20260715`，创建 PR 并转 Ready。
- 核对 PR head、base、mergeability、review 和 checks；空 checks 只表述为“未配置/未报告”。
- 使用 merge commit 合并，不传删除分支参数。

## Task 4：clean main 部署准备

merge 后：

```bash
git fetch origin main --prune
git switch main
git pull --ff-only origin main
TARGET_SHA="$(git rev-parse HEAD)"
test "$TARGET_SHA" = "$(git rev-parse origin/main)"
test -z "$(git status --porcelain)"
```

只读检查 SSH key 模式和远端容量；不得读取 key 或 `.env` 内容：

```bash
: "${SSH_KEY_PATH:?Set SSH_KEY_PATH to a repository-external SSH private key path}"
test -r "$SSH_KEY_PATH"
test "$(stat -f '%Lp' "$SSH_KEY_PATH")" = 600
ssh -i "$SSH_KEY_PATH" -o BatchMode=yes -o StrictHostKeyChecking=yes -o IdentitiesOnly=yes \
  ubuntu@101.34.52.232 \
  'set -euo pipefail; df -Pk /opt /var; du -sk /opt/medical-audit/backups /opt/medical-audit/app /var/www/audit'
```

先运行无 `--execute` 的 preflight。正式命令只包含 `--execute`、生产确认、精确批准 SHA、key、stamp 和 report；不得包含 dirty/schema/provider/review/query/skip flags。

## Task 5：部署与回滚门禁

正式执行应依次完成 app/env/db/nginx/web 备份、前端构建、同步、app 单服务重建、健康检查、marker 更新和默认 production smoke。

若失败：保存失败日志，不猜测 marker；先只读获取实际 `.deploy-sha`，再以同一 stamp、实际 current marker 和旧 SHA `b88ecdff7f773c8990454009d4a2b33ea8fdc2d4` 调用 rollback。自动 rollback 不代表 DB/env/nginx 恢复已验证。

## Task 6：部署后证据

- L3：部署脚本默认 smoke、严格 deployment-state audit、有限只读权限 smoke。
- Documents probe 只有在其实际请求路径再次确认无 `record_operation` 后才可标 L3；否则单列 `audit-log-only`。
- L4：完整权限 35 项与完整前端 18 路由/36 检查，显式传：

```bash
--allow-audit-log-writes \
--confirm-production-write audit.lute-tlz-dddd.top
```

最终声明必须分别列出 merge SHA、deploy SHA、脚本最终退出码、备份证据、L3 只读结果、L4 审计日志写入结果，以及任何未验证项。
