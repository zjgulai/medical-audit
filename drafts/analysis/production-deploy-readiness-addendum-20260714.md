---
title: medical_audit 生产部署就绪补充报告
doc_type: analysis-report
module: repository
status: superseded_postmerge_audit_log_side_effect
superseded_by: drafts/analysis/project-reanalysis-and-gap-audit-20260813.md
superseded_date: 2026-08-16
created: 2026-07-14
updated: 2026-08-15
owner: self
source: fresh-clean-candidate-and-production-readonly-evidence
---

# medical_audit 生产部署就绪补充报告

> 本报告已标记 `superseded`，用于 2026-07-14 历史归档；当前候选请以 `drafts/analysis/project-reanalysis-and-gap-audit-20260813.md` 与 `2026-08-15+` 生产/本地证据为准。

## 结论

`origin/main@b88ecdff7f773c8990454009d4a2b33ea8fdc2d4` 已在 owner 授权后从 clean deploy clone 执行生产部署。部署 stamp 为 `20260714T172146+0800`；远端 `.deploy-sha`、备份清单和独立 strict audit 均确认生产已运行 b88。PR #233 后续已转为 Ready 并以 merge commit `2d790375621bafa3dd564b1a1464f3e229a053a2` 合入 `main`；post-merge clean-main preflight 已完成，但未再次部署。部署准备现因 evidence tooling 错误标注副作用而阻断：permission/frontend acceptance 实际写入至少 `69` 条生产审计日志，不能继续称为 L3 read-only。生产 runtime SHA 仍为 b88；SQL backfill、provider/query/citation/review write 仍未执行。

## 已验证证据

| 门禁 | 结果 | 证据层级 | 边界 |
|---|---|---|---|
| PR #232 release delta | `58` commits、`87` files、`+27,707/-7,206`；未发现新增 SQL migration 或 schema drop | `L1` / `L2` | b88 已获授权并部署 |
| 后端全量测试 | clean b88 `uv run pytest -q` exit `0` | `L2-fixture-or-dry-run` | 不证明生产运行 |
| 静态导出 | `pnpm web:build:static` pass；Next `15.5.19`、`24/24` pages、`87` files、约 `2.6M` | `L2-fixture-or-dry-run` | 不证明已同步到生产 |
| 生产 smoke | b88 runner 对当前生产 `status=pass`，TLS/health/search/page-rendering 通过 | `L3-production-read-only` | GET-only；query/provider/citation/export `not_run` |
| documents probe | 修正为 static-export shell markers 后 `status=pass`；权限、治理、health、search 通过 | `L3-production-read-only` | raw HTML 不承担浏览器可见文案验收 |
| 前端验收 | `18` routes、desktop/mobile `36` checks、P0/P1 `0`、audit logs `401/200` | `L3-production-read-only` | 修正 b88 页面契约后针对已部署 b88 运行 |
| deploy preflight | 严格 SSH、Nginx syntax 和目标主机 preflight pass | `L2` + `L3` readonly | 执行前门禁 |
| remote backup | app/env/database/Nginx/web 备份齐全；marker `complete`；数据库 `4,835,102,942` bytes | `L4-authorized-live` | stamp `20260714T172146+0800` |
| production deploy | clean b88 source 同步、Docker rebuild/recreate、`.deploy-sha` 写入成功 | `L4-authorized-live` | outer zsh capture wrapper 收尾时报 `read-only variable: status`，由独立远端证据闭环 |
| post-deploy strict state | b88 SHA、容器、Nginx、mount、frontdoor、search、DLP、`49,051` embeddings 全通过 | `L3-production-read-only` | same SHA |
| permission readonly | `status=observed`、`35` probes、`issue_count=0`、GET-only | `L3-production-read-only` | no side effect |
| frontend acceptance | 修正 b88 页面契约后 `18` routes / `36` checks、P0/P1 `0`、audit logs `401/200` | `L3-production-read-only` | analytics/projects/reports 旧文案断言已识别为工具漂移 |

## 本批新鲜复核与工具缺口

- `origin/main` 已因 PR #233 merge 前进到 `2d790375621bafa3dd564b1a1464f3e229a053a2`；PR head `1ad11a7...` 已包含在该 merge commit 中，生产 runtime 仍为已部署的 b88。
- b88 提交版 `audit-tencent-cloud-deployment-state.py` 的只读结果为 `pass`，但实际 SSH 参数仍是 `StrictHostKeyChecking=no`；该结果只作诊断，不作为 strict evidence。
- reconciliation clone 的本地 strict patch（`BatchMode=yes`、`StrictHostKeyChecking=yes`、`IdentitiesOnly=yes`）已并入四文件本地 promotion 包；focused/full tests、Ruff、`node --check`、`git diff --check` 均通过。
- 该 promotion 包在 `2026-07-14T18:16:07+0800` 重新执行 strict production audit：SHA 为已部署的 `b88...`，required backup stamp、容器、Nginx、挂载、frontdoor、search、`49,051` embeddings、DLP `ruleset-v1` 全部通过。
- 同一 promotion 源的 corrected documents probe 与 hardened frontend acceptance 均通过；documents 明确 `production_write=false` / `provider_call=false`，frontend 为 `18` routes / `36` checks、P0/P1 `0`、权限 `401/200`。
- 该 audit-tool strict patch 已随 BRP-R8 四文件包 commit、push，并通过 PR #233 merge 到 `main`；这项 Git 变更未触发部署，不改变当前生产仍运行 b88 的事实。
- 在实际 clean deploy clone 上补跑：full backend pytest、deployment guard tests、Web lint/typecheck/Vitest（`32/279`）、in-memory Playwright E2E（`13/13`）均通过。
- 所有最终本地门禁完成后，strict SSH deploy preflight 再次 exit `0`，输出保存于 `tmp/outputs/branch-production-reconciliation-deploy-preflight-rerun-20260714.txt`。
- 实际生产执行后，远端 `.deploy-sha` 为 b88，backup marker 为 `complete`；strict state、smoke、permission、documents、frontend acceptance 证据已分别落盘。
- 首次 frontend acceptance 的六个 P1 是验收工具对已退役 `内测中|待开通` 文案的旧断言；b88 组件测试明确要求这些页面不再出现该文案。最小契约修正只用于 acceptance tooling，不改变生产 runtime。
- promotion 分支位于 `/Users/pray/project/medical_audit_release_reconciliation_20260714` 的 `codex/release-reconciliation-20260714`；`HEAD==origin/codex/release-reconciliation-20260714==1ad11a7...`，远端分支按要求保留。PR #233 的四文件 `+112/-14` 已通过 merge commit `2d79037...` 合入 `main`。
- 完整 review patch 已保存为 `tmp/outputs/branch-production-reconciliation-tooling-promotion-20260714.patch`；`git apply --reverse --check` 通过，SHA-256 为 `4bdc87169c8891f89a24f317cd7de50ef3b41d2eea13b97a8a61157571b29bc8`。

## 分支处理结论

- `codex/pr232-postmerge-readiness-20260713`：完成本地 review package；不创建 PR、不 push、不 merge，不作为 b88 部署的一部分。
- `codex/ppt-feedback-product-optimization-20260711-continuation`：只保留 semantic slice 候选，禁止 whole-branch merge。
- `codex/merge-release-artifact-ignore-main-20260706`：BM25 fallback focused test/Ruff 通过，是否 cherry-pick 由 owner 单独决定，不并入本次 b88 发布。
- `codex/project-governance-20260706` 及历史 closed-unmerged PR：归档参考，不恢复旧分支拓扑。

## 执行前必要条件（已完成，保留为审计记录）

1. owner 已明确批准 SHA `b88ecdff7f773c8990454009d4a2b33ea8fdc2d4` 作为本次生产候选。
2. 执行窗口已从干净 clone `/Users/pray/project/medical_audit_deploy_candidate_20260714` 重新确认 `main == origin/main == approved SHA`。
3. 默认 deploy preflight 已通过；未使用 dirty root 或 `--allow-dirty`。
4. 生产备份已在 stamp `20260714T172146+0800` 下完成并经 strict audit 核验。
5. backfill 保持独立 SQL gate；本次未带 `--apply-schema`、`--include-review-write` 或 `--include-query-provider-smoke`，未执行 provider/query/write-path smoke。

## 实际执行命令摘要

以下命令从 clean deploy clone 执行；外层日志包装器在子进程完成后因使用 zsh 只读变量 `status` 报错，远端 SHA、备份 marker、post-check 与独立 strict audit 构成最终结果证据：

```bash
cd /Users/pray/project/medical_audit_deploy_candidate_20260714
git fetch origin --prune
git switch main
git pull --ff-only origin main
HOME=/private/tmp/medical-audit-known-home.lbIBOo uv run python scripts/deploy-tencent-cloud-production.py \
  --ssh-key "$SSH_KEY_PATH" \
  --execute \
  --confirm-production audit.lute-tlz-dddd.top \
  --approved-sha b88ecdff7f773c8990454009d4a2b33ea8fdc2d4 \
  --stamp 20260714T172146+0800
```

执行后必须用同一 `<STAMP>` 和 deploy SHA 复核 deployment-state、production smoke、documents probe、frontend acceptance；任一步失败即停止，不自动 rollback。`--include-query-provider-smoke` 和 `--include-review-write` 只有在另行授权真实写路径后才能添加。

## 当前未完成 / blocked TODO

- [x] `BRP-GATE-REMOTE-WRITE`：commit、push、Ready transition 和 PR #233 merge 已分别授权并完成；远端 branch/ref 删除明确排除且未执行。
- [x] `BRP-GATE-PRODUCTION-BACKUP`：stamp `20260714T172146+0800` 的 app/env/database/Nginx/web 备份已完成并由 strict audit 校验。
- [ ] `BRP-GATE-PRODUCTION-SQL`：backfill execute/rollback 仍未授权；只读 candidate audit 已通过。
- [x] `BRP-GATE-PRODUCTION-DEPLOY`：owner 已授权；b88 已部署并由独立 remote SHA/strict state 证据确认。
- [x] `BRP-GATE-PRODUCTION-ACCEPTANCE`：同一 b88 SHA 的 strict state、smoke、permission、documents、frontend acceptance 均通过。
- [x] `BRP-R8-TOOLING-PROMOTION-PACK`：strict audit、documents probe、frontend acceptance 契约及回归测试已形成 clean-b88 本地 review package，并通过本地与生产只读复验。
- [x] `BRP-R9-DRAFT-PR`：commit `1ad11a7...` 已 push，draft PR #233 已创建并完成审查。
- [x] `BRP-R6-STRICT-AUDIT-TOOL-PROMOTION`：PR #233 已转为 Ready 并 merge 到 `main@2d790375621bafa3dd564b1a1464f3e229a053a2`；未与生产部署混合。
- [ ] `BRP-R13-POSTMERGE-DEPLOY-PREP`：focused gates、strict zero-execute preflight、strict state/documents L3 gates 已通过；permission/frontend acceptance 因审计日志副作用误标而阻断 closeout。
- [ ] `BRP-R13-EVIDENCE-TOOL-SIDE-EFFECT-FIX`：readonly mode 必须跳过副作用 endpoint，或明确声明 `database_write=audit-log-only` 并要求独立授权；需增加回归测试。
- [ ] `BRP-GATE-PR233-PRODUCTION-DEPLOY`：blocked；不得基于当前错误的 read-only 标签进入部署。

## 证据文件

- `tmp/outputs/branch-production-reconciliation-production-smoke-b88-20260714.json`
- `tmp/outputs/branch-production-reconciliation-documents-shell-probe-20260714.json`
- `tmp/outputs/branch-production-reconciliation-production-smoke-rerun-20260714.json`
- `tmp/outputs/branch-production-reconciliation-documents-shell-probe-rerun-20260714.json`
- `tmp/outputs/branch-production-reconciliation-deployment-state-strict-rerun-20260714.json`
- `tmp/outputs/branch-production-reconciliation-deployment-state-strict-rerun-20260714.md`
- `tmp/outputs/branch-production-reconciliation-strict-audit-tool-only.patch`
- `tmp/outputs/branch-production-reconciliation-deploy-preflight-20260714.txt`
- `tmp/outputs/branch-production-reconciliation-deploy-preflight-rerun-20260714.txt`
- `tmp/outputs/branch-production-reconciliation-frontend-acceptance-candidate-20260714.json`
- `tmp/outputs/branch-production-reconciliation-deployment-state-20260714.json`
- `tmp/outputs/branch-production-reconciliation-candidate-audit-20260714.json`
- `docs/superpowers/plans/2026-07-13-ppt-feedback-production-deployment.md`
- `.omc/RELEASE_RULE.md`

## 边界声明

`production_sha=b88ecdff7f773c8990454009d4a2b33ea8fdc2d4` · `provider_call=false` · `database_write=false` · `live_send=false`。BRP-R8 的 commit/push/draft PR 与后续 Ready/merge 是分别授权的 Git-only side effects；SQL backfill、provider/query/citation/review writes、deploy rerun、remote ref deletion 未执行。

## 部署后证据文件

- `tmp/outputs/production-deploy-execution-20260714T172146+0800.log`
- `tmp/outputs/production-deploy-state-post-20260714.json`
- `tmp/outputs/production-deploy-state-post-20260714.md`
- `tmp/outputs/production-smoke-post-20260714.json`
- `tmp/outputs/production-permission-readonly-post-20260714.json`
- `tmp/outputs/documents-probe-post-20260714.json`
- `tmp/outputs/production-frontend-acceptance-post-contract-20260714.json`
- `tmp/outputs/production-frontend-acceptance-contract-fix-20260714.patch`
- `tmp/outputs/branch-production-reconciliation-deployment-state-promotion-20260714.json`
- `tmp/outputs/branch-production-reconciliation-deployment-state-promotion-20260714.md`
- `tmp/outputs/branch-production-reconciliation-documents-promotion-20260714.json`
- `tmp/outputs/branch-production-reconciliation-frontend-acceptance-promotion-20260714.json`
- `tmp/outputs/branch-production-reconciliation-tooling-promotion-20260714.patch`

## PR #233 merge closeout

当前状态为 `merged_production_unchanged_remote_branch_retained`：

- PR #233 head 为 `1ad11a708dbef577a71980fd410db9d984c976ff`；经 owner 独立授权后已转为 Ready，并于 `2026-07-14T14:56:54Z` 以 merge commit `2d790375621bafa3dd564b1a1464f3e229a053a2` 合入 `main`。
- GitNexus 将四文件变更评为 `low` risk，未识别受影响执行流；三个非测试变更符号的 upstream impact 均为 `LOW`。
- 独立 `codex review` 完成。其唯一 P1 建议认为 raw `/documents` shell marker 会通过登录壳；该建议经核验后不接受，因为此 probe 已明确只负责 route-specific static shell，Playwright gate 独立负责客户端渲染与可见语义，且两项均为部署验收必跑门禁并已新鲜通过。
- 本地全量门禁通过：Ruff、Mypy `106` source files、Pytest `593` tests、Web lint/typecheck、Vitest `32/279`、Next static export `24/24`。
- 未带 `--execute` 的 strict deploy preflight 通过。生产 strict state、documents、permission readonly、frontend acceptance 均针对当前 b88 新鲜通过；production SHA 仍为 b88。
- 本次没有执行生产部署。后续若部署，execute 门禁仍要求 clean `main` 且 `HEAD==origin/main==approved_sha`，并需新的 owner 授权。
- 本 PR 只改 release-evidence tooling/tests，不建议为此单独重部署业务 runtime；优先随下一次 owner 授权的 runtime release 一并同步。
- 远端分支未删除；`refs/heads/codex/release-reconciliation-20260714` 仍指向 `1ad11a7...`。
- merge 后 GET-only probe 再次确认 production SHA 仍为 b88，且 `production_write=false` / `provider_call=false`。

新增证据：

- `/Users/pray/project/medical_audit_release_reconciliation_20260714/tmp/outputs/pr233-production-state-20260714T211100+0800.json`
- `/Users/pray/project/medical_audit_release_reconciliation_20260714/tmp/outputs/pr233-production-state-20260714T211100+0800.md`
- `/Users/pray/project/medical_audit_release_reconciliation_20260714/tmp/outputs/pr233-production-documents-readonly-20260714T210847+0800.json`
- `/Users/pray/project/medical_audit_release_reconciliation_20260714/tmp/outputs/production-permission-readonly-smoke-latest.json`
- `/Users/pray/project/medical_audit_release_reconciliation_20260714/tmp/outputs/production-frontend-acceptance-latest.json`
- `/Users/pray/project/medical_audit_release_reconciliation_20260714/tmp/outputs/pr233-postmerge-production-unchanged-20260714T2257+0800.json`

边界：`production unchanged` · `merge_execute=true` · `draft_ready_transition=true` · `deploy_execute=false` · `database_write=false` · `provider_call=false` · `live_send=false` · `remote_ref_delete=false`。

## PR #233 post-merge clean-main 部署准备

当前状态为 `deployment_preparation_blocked_by_audit_log_side_effect_misclassification`：

- clean candidate 为 `/Users/pray/project/medical_audit_release_reconciliation_20260714` 的 `main@2d790375621bafa3dd564b1a1464f3e229a053a2`；`HEAD==origin/main`、worktree clean。
- merge commit tree 与已完成独立审查的 PR head tree 完全一致，未引入额外 code delta；因此没有重复执行无新增价值的 Codex review。
- targeted Ruff、Mypy `106` source files、script tests `103/103`、Node syntax 和 `git diff --check` 通过。
- 不带 `--execute` 的 strict SSH deploy preflight 通过；Nginx、容器、health、catalog GET 均通过。
- strict production state 与 documents probe 通过：生产仍为 b88，required backup stamp 存在，app/PostgreSQL/ClamAV/Nginx 健康，DLP `ruleset-v1`，search ready，`49,051` embeddings，`production_write=false`，`provider_call=false`。
- hardened Playwright production acceptance 功能上通过 `18` routes / `36` checks，`P0=0`、`P1=0`；但 `/audit/logs/export` 会写 `audit-logs-export` 事件，不能标为纯只读。
- 标准 10 秒 permission smoke 两次均为 `issue_count=0`，但都记录 authenticated `/graph/workbench` timeout observation；独立 GET 为 `200 / 8.55s`，20 秒诊断复核为 `35/35`、零 issue、零 observation。
- source inspection 确认 permission smoke 的匿名/缺 tenant 请求会写 `authorization-denied` 审计事件，而报告仍输出 `production_side_effect=none`。只读日志查询在本阶段窗口内确认至少 `69` 条可归因写入：`68` 条 authorization-denied 和 `1` 条 audit-logs-export。
- 未执行日志删除或回滚。必须先修正 evidence-tool side-effect contract，或取得对 write-enabled acceptance 的明确授权，才能恢复部署准备结论。

新增证据：

- `/Users/pray/project/medical_audit_release_reconciliation_20260714/tmp/outputs/pr233-postmerge-clean-main-state-20260714T2305+0800.json`
- `/Users/pray/project/medical_audit_release_reconciliation_20260714/tmp/outputs/pr233-postmerge-clean-main-state-20260714T2305+0800.md`
- `/Users/pray/project/medical_audit_release_reconciliation_20260714/tmp/outputs/pr233-postmerge-clean-main-documents-20260714T2305+0800.json`
- `/Users/pray/project/medical_audit_release_reconciliation_20260714/tmp/outputs/production-permission-readonly-smoke-latest.json`
- `/Users/pray/project/medical_audit_release_reconciliation_20260714/tmp/outputs/pr233-postmerge-clean-main-permission-timeout20-20260714T2317+0800.json`
- `/Users/pray/project/medical_audit_release_reconciliation_20260714/tmp/outputs/production-frontend-acceptance-latest.json`

证据门禁：`blocked` · strict state/documents=`L3-production-read-only` · permission/frontend=`audit-log-write-side-effect` · `production_runtime unchanged` · `candidate_sha=2d790375621bafa3dd564b1a1464f3e229a053a2` · `production_sha=b88ecdff7f773c8990454009d4a2b33ea8fdc2d4` · `deploy_execute=false` · `backup_write=false` · `database_write=audit-log-only` · `audit_log_write_count_at_least=69` · `provider_call=false` · `live_send=false` · `remote_ref_delete=false`。
