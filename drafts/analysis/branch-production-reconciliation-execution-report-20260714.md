---
title: medical_audit 分支与生产部署对账执行报告
doc_type: analysis-report
module: repository
status: historical_predeploy_snapshot
created: 2026-07-14
updated: 2026-07-14
owner: self
source: fresh-git-github-runtime-evidence
superseded_by: production-deploy-readiness-addendum-20260714.md
---

# medical_audit 分支与生产部署对账执行报告

> 历史快照：本报告正文冻结于部署前审计阶段。当前事实以同目录的 `production-deploy-readiness-addendum-20260714.md` 为准；b88 已于 owner 授权后部署并通过同 SHA 只读验收，随后 release-tooling 修正已形成未提交的本地 promotion 包。

## 1. 部署前结论（历史）

本轮已完成当前可安全执行的完整审计、只读生产核验、本地候选门禁和 TODO 文档收口；b88 候选已达到 `ready_for_owner_authorization`，但没有执行 push、PR 创建、merge、生产备份、生产 SQL、provider call 或生产 deploy。

### 已确认的事实

1. 本快照当时的生产运行的是 `51dfcb816a0c71928c206683f0fa7fef796e895a`，对应 PR #231 的 merge commit。
2. 本快照当时 GitHub `origin/main` 是 `b88ecdff7f773c8990454009d4a2b33ea8fdc2d4`，对应 PR #232 的 merge commit；它比当时生产多 `58` 个 commits、`87` 个文件、`+27,707/-7,206`，在本快照阶段尚未部署到生产。
3. 没有 open PR。明确的未合并交付候选为：
   - PR #186 / `codex/project-governance-20260706`：`CLOSED` 且未 merge，`1` 个 branch-unique commit；
   - `codex/pr232-postmerge-readiness-20260713`：本地-only，`36` 个 branch-unique commits，`8` 个文件，`+18,290/-19`；
   - `codex/ppt-feedback-product-optimization-20260711-continuation`：本地-only，`20` 个 branch-unique commits，`83` 个文件，`+11,390/-22,376`；
   - `codex/merge-release-artifact-ignore-main-20260706`：本地-only，`1` 个 branch-unique commit，但相对 `origin/main` 有 `194` 个文件的历史分叉，不能整支合并。
4. PR #123、#82 也是历史 `CLOSED` 未 merge，但其分支引用已不在当前远端分支矩阵中，应作为历史档案而不是当前 merge 候选。
5. 远端若干 branch tip 不是 `main` ancestor，但对应 PR merge commit 已在生产祖先链中；这是 squash/merge 拓扑差异，不是“尚未合并”。典型包括 PR #187、#188、#189、#203、#204、#205。禁止把这些 branch tip 整支再次合并。
6. 根工作区不能作为发布源：当前本地 `main` 为 `6429b34278cf6d35e3477edc6bc3e5032df652f2`，落后 `origin/main` `172` commits；审计快照时有 `48` 个 tracked status entries、`330` 个 untracked entries，共 `378` 项状态变化。随后本轮新增的报告与 `.omc/RELEASE_RULE.md` 使当前 untracked 计数增加到 `332`，不改变原始快照结论。
7. clean `origin/main@b88ecdff...` 候选已通过全量后端 pytest、静态导出构建、b88 源码 smoke 和部署脚本默认 preflight；这些证据仍属于候选本地门禁或生产只读观测，不是部署证据。

### 生产状态结论

- 严格 SSH + 只读部署状态审计：`PASS`，生产 SHA、app/PostgreSQL/ClamAV、Nginx、挂载、PostgreSQL search backend、`49,051` matching embeddings 均符合当前阈值。
- 严格 `BEGIN READ ONLY` review-task scope 审计：`PASS`，`candidate_count=1`，`conflict_count=0`，`mismatch_count=0`，`multiple_project_count=0`；`transaction_read_only=on`。
- 使用 clean b88 候选源码中的 frontend acceptance runner 对当前生产域名执行：`PASS`，覆盖 `18` routes、desktop/mobile `36` checks，P0/P1 均为 `0`，审计日志无角色 `401`、管理员 `200`；这证明当前生产满足该 hardened runner 的路由/权限检查，不证明 b88 已部署。
- 使用 b88 候选源码中的 production smoke runner 对当前生产执行：`PASS`，证据等级 `L3-production-read-only`，仅 `GET`，`provider_call=false`、`database_write=false`、`production_side_effect=none`。使用修正后的静态导出 shell markers 的 documents probe 也为 `PASS`。
- 之前 `/pages/chat` smoke 失败和 `/documents` 文案 probe 失败是旧脚本/原始 HTML 契约的 false negative：Next client page 的可见文案在浏览器执行后出现，不能要求原始 HTML 包含客户端渲染文本。旧失败报告保留为历史证据，不再作为当前部署阻塞项。

## 2. 证据边界

| 证据 | 新鲜度/等级 | 可支持的说法 | 不能支持的说法 |
|---|---|---|---|
| Git/GitHub ref、PR、merge commit、分支矩阵 | 2026-07-14，`L1-public-or-runtime` | 哪些 PR 已 merge、哪些 PR closed-unmerged、哪些 merge commit 已进入 production 祖先链 | 分支工作区代码质量、生产页面完整验收 |
| clean candidate 本地 lint/type/test/build/E2E | 2026-07-14，`L2-fixture-or-dry-run` | 候选代码在本地门禁通过 | 已部署、真实用户验收、生产写入安全 |
| strict SSH deployment-state audit | 2026-07-14，`L3-production-read-only` | 当前生产 SHA 与容器/索引/挂载/服务健康观测 | deploy 已发生、备份已新建、业务写入可用 |
| strict `BEGIN READ ONLY` candidate audit | 2026-07-14，`L3-production-read-only` | 生产存在 1 条可唯一推断 scope 的候选，数据库未写入 | backfill 已执行、rollback 已证明于生产 |
| clean b88 runner against current production | 2026-07-14，`L3-production-read-only` | 当前生产满足 hardened runner 的 routes/permission checks | b88 已部署、候选源码已在生产运行 |
| current production smoke/documents probes | 2026-07-14，`L3-production-read-only` | 当前生产 TLS、health、search、静态 shell、权限与治理状态通过；探针明确不写生产 | b88 已部署、provider/query/write-path 或生产备份已完成 |

本快照硬边界：`production unchanged`、`provider_call=false`、`database_write=false`、`backup_write=none`、`deploy_execute=false`。该阶段只有本地临时 PostgreSQL 测试写入（已销毁容器）和本地报告文件写入。

## 3. 分支与 PR 对账

### 3.1 当前未合并或未进入生产的交付候选

| 优先级 | 分支/PR | 当前状态 | 证据 | 处理建议 |
|---|---|---|---|---|
| P0 | `codex/pr232-postmerge-readiness-20260713` | 未 merge、未 deploy | `36` branch-only commits；包含约 `5,725` 行 backfill CLI，已有 `577` script tests、Ruff/Mypy 和隔离 PostgreSQL execute/postcheck/rollback 证据 | 建 draft PR；先做独立 review，再决定是否只纳入 backfill 语义切片；禁止直接 deploy |
| P0 | `codex/ppt-feedback-product-optimization-20260711-continuation` | 未 merge、未 deploy | `20` branch-only commits、`83` files、`+11,390/-22,376` | 按功能切片与 `origin/main` 做 semantic diff；禁止 whole-branch merge |
| P1 | PR #186 / `codex/project-governance-20260706` | GitHub `CLOSED` 未 merge、未 deploy | head `af719e3f...`，`patch_unique=1`，无 merge commit | 作为治理档案；如仍需要，重新开小 PR，不恢复旧大分叉 |
| P1 | `codex/merge-release-artifact-ignore-main-20260706` | 本地-only、未 merge、未 deploy | 一个 BM25 fallback unique commit；相对 main 有 `194` files 历史分叉 | 只提取并单测该 fallback commit；不要合并整支 |
| P1 | PR #123、#82 | 历史 closed-unmerged、当前 branch ref 不在远端矩阵 | GitHub PR 记录存在，均无 merge commit | 归档；如功能仍需，按当前 main 重提最小变更 |

### 3.2 已 merge 但 branch tip 不应再次合并

下列 branch tip 不是 `origin/main` ancestor，但各自 PR 的 merge commit 已落在生产祖先链：

- `codex/backend-connectivity-p0-20260706` / PR #187 / merge `9a73d3b7...`；
- `codex/projects-cockpit-production-fix-20260706` / PR #188 / merge `58258277...`；
- `codex/login-hero-contrast-fix-20260706` / PR #189 / merge `1c87ddaa...`；
- `codex/p0-product-linkage-20260708` / PR #203 / merge `ad96341d...`；
- `codex/cross-page-chat-linkage-20260708` / PR #204 / merge `c02f5bf3...`；
- `codex/agent-market-dialog-chat-link-20260708` / PR #205 / merge `73cae3e1...`。

结论：以 PR merge commit / production ancestry 为准，以 branch tip ancestry 为辅；这类 refs 后续只需做 stale-ref cleanup 评估。

### 3.3 PR #232 的 merge 与 deploy 分离

- PR #232：`MERGED`，merge `2026-07-13T06:40:02Z`，merge commit `b88ecdff...`。
- 生产：仍为 PR #231 merge `51dfcb816...`。
- 因而 `PR #232 merged != PR #232 deployed`。是否部署 b88 必须由 owner 另行确认，且只能从 clean pinned main 执行。

## 4. 生产与候选核验结果

### 4.1 当前生产严格部署状态

报告：`tmp/outputs/branch-production-reconciliation-deployment-state-20260714.json`。

- `status=pass`；`deploy_sha=51dfcb816a0c71928c206683f0fa7fef796e895a`；
- app/PostgreSQL/ClamAV `healthy`；Nginx config test、audit frontdoor、Next static、mount、search backend 均通过；
- `matching_embedding_count=49051`；`virus_scan_provider=clamav-sidecar`；`dlp_review_provider=ruleset-v1`；
- 这是生产只读观测，不是 deploy 执行证据。

### 4.2 生产 review-task scope 只读审计

报告：`tmp/outputs/branch-production-reconciliation-candidate-audit-20260714.json`。

- `mode=dry-run`、`transaction_read_only=on`、`evidence_grade=L3-production-read-only`；
- `candidate_count=1`，`snapshot_hash=1acda7ed251d71f8121cb477eff8b7630f3d5936ecde082751733cb08656dcbd`；
- `review_tasks_total=13`、`audit_findings_total=1`、`linked_task_count=1`、`linked_finding_count=1`；
- `linked_missing_count=1`、`unlinked_task_count=12`、`missing_both_count=13`；
- `conflict_count=0`、`mismatch_count=0`、`multiple_project_count=0`；
- `database_write=false`、`backup_write=none`、`production_state=unchanged`。

这只证明“存在 1 条可以进入后续审批的唯一推断候选”，不证明已备份、已写入或已回滚。

### 4.3 当前生产页面 smoke / documents probe

- `tmp/outputs/branch-production-reconciliation-production-smoke-20260714.json`：旧 root smoke 脚本因 `/pages/chat` 原始 HTML 文案契约失败，保留为 false-negative 历史证据。
- `tmp/outputs/branch-production-reconciliation-documents-readonly-20260714.json` 与 `...documents-candidate-probe-20260714.json`：旧脚本要求客户端渲染文案出现在原始 HTML，均只在页面 marker 步骤失败，保留为契约诊断证据。
- `tmp/outputs/branch-production-reconciliation-production-smoke-b88-20260714.json`：从 clean b88 候选源码执行，`status=pass`、`evidence_grade=L3-production-read-only`、TLS/health/search/page-rendering 通过；query/provider/citation/export 明确 `not_run`。
- `tmp/outputs/branch-production-reconciliation-documents-shell-probe-20260714.json`：修正为 Next static-export shell markers（title、`/_next/static/`、documents page chunk）后 `status=pass`；权限、governance、health、search 全部通过；`production_write=false`、`browser_js_executed=false`。

### 4.4 当前生产前端验收（runner 来自 clean b88 源码）

报告：`tmp/outputs/branch-production-reconciliation-frontend-acceptance-candidate-20260714.json`。

- `status=pass`；`route_count=18`、`check_count=36`；desktop/mobile 均覆盖；目标仍是当前生产域名；
- P0/P1 均为 `0`；
- `/audit/logs` 与 `/audit/logs/export` 无权限 `401`，管理员角色 `200`。

### 4.5 b88 候选发布门禁

- clean candidate 全量 `uv run pytest -q`：`PASS`，无失败；仅已有 FastAPI/Starlette deprecation warning。
- `pnpm web:build:static`：`PASS`，Next `15.5.19`，`24/24` static pages，`web/out` `87` files、约 `2.6M`。
- `scripts/deploy-tencent-cloud-production.py` 默认模式：`PASS`，严格 SSH、Nginx syntax、目标主机 preflight 通过；未带 `--execute`。
- 本快照结论：b88 已满足“可由 owner 授权执行部署”的前置门禁；当时生产仍保持 `51df...`，`production unchanged`。

### 4.6 干净部署源

- 保留审计探针改动的 reconciliation clone `/Users/pray/project/medical_audit_release_reconciliation_20260714` 不作为生产执行源；其未提交改动只用于证据工具和 probe 契约修正。
- 新建 `/Users/pray/project/medical_audit_deploy_candidate_20260714`，状态为 `main`、`HEAD==origin/main==b88ecdff...`、clean worktree。
- 在该 clone 安装 `pnpm install --frozen-lockfile`，静态导出通过，随后严格 SSH deploy preflight 通过；输出保存于 `tmp/outputs/branch-production-reconciliation-deploy-preflight-20260714.txt`。
- 该 clone 仍未执行 `--execute`，没有生产写入；owner 执行命令必须使用此 clean `main` clone，并在执行窗口重新 fetch/核 SHA。

### 4.7 新鲜复核与 audit-tool 缺口

- 刷新 `origin/main` 后仍为 `b88ecdff...`，open PR 为 `0`；clean deploy clone 保持 `main`、`HEAD==origin/main`、clean。
- b88 提交版 `audit-tencent-cloud-deployment-state.py` 的一次只读结果为 `pass`，但命令仍显示 `StrictHostKeyChecking=no`，因此该结果只作为诊断，不作为 strict evidence。
- reconciliation clone 的本地 strict patch 通过 focused tests、Ruff、`git diff --check`，并在 `2026-07-14T17:02:58+0800` 生成 strict production read-only pass；新鲜 documents probe 与 b88 smoke 也通过。
- 该 strict audit-tool patch 尚未 push/PR/merge，是独立 tooling promotion gap；b88 deploy script 本身仍使用 strict SSH，clean deploy preflight 不受影响。
- 在最终 clean deploy clone 上补跑 full backend pytest、deployment guard tests、Web lint/typecheck/Vitest（`32/279`）和 in-memory Playwright E2E（`13/13`）；全部通过。
- 所有最终门禁完成后 strict deploy preflight 再次通过，输出为 `tmp/outputs/branch-production-reconciliation-deploy-preflight-rerun-20260714.txt`。

## 5. clean candidate 本地门禁

执行源：临时 detached worktree `/tmp/medical_audit_candidate_b88_20260714`，基线 `origin/main@b88ecdff...`；没有在 dirty root 上做发布验证。

| 门禁 | 结果 |
|---|---|
| `uv run ruff check .` | pass |
| `uv run mypy src` | pass，104 source files |
| `uv run pytest tests/knowledge_query -q --disable-warnings` | pass；collect-only `590` node lines |
| `pnpm --filter medical-audit-web lint` | pass |
| `pnpm --filter medical-audit-web typecheck` | pass |
| `pnpm --filter medical-audit-web test` | pass；32 files / 279 tests |
| `pnpm --filter medical-audit-web build` | pass；Next 15.5.19，24 static pages |
| `uv run python scripts/run-local-fullstack-e2e.py` | pass；13 tests |
| `scripts/deploy-tencent-cloud-production.py` 默认模式 | pass；只读 preflight，明确提示需 `--execute --confirm-production` |

一次带有 `--runInBand` 的 Vitest 命令失败是命令参数不被项目 Vitest 接受，不是测试失败；随后使用项目原生命令重新验证通过。

## 6. 清理与保留清单（P6 manifest）

### KEEP：当前必须保留

- `/Users/pray/project/medical_audit` dirty root：保留所有现有变更，不 reset、不 clean、不覆盖。
- 3 个现有 stash：保留，等待 owner 对应业务确认。
- 4 个未合并候选分支及其有效 worktree：`pr232-postmerge-readiness`、`ppt-feedback-product-optimization...continuation`、`merge-release-artifact-ignore-main`、`project-governance`。
- clean baseline clone `/Users/pray/project/medical_audit_release_reconciliation_20260714`：保留到 owner 完成分支/生产决策。
- 临时候选 worktree `/tmp/medical_audit_candidate_b88_20260714`：在报告交接前保留；交接后可由 owner 单独授权清理。

### ARCHIVE/REFERENCE：不作为 merge 候选

- PR #123、#82 的历史 closed-unmerged 记录；
- 已 merged 但 branch tip 非 ancestor 的 stale topology refs；
- PR #186 的治理提交及其 worktree，除非重新拆成当前 main 上的小 PR。

### DELETE/PRUNE：必须单独授权，当前不执行

- `git worktree prune --dry-run` 报告的 `31` 个 prunable registrations；
- 已被 merge commit 覆盖且不再需要的本地/远端 branch refs；
- 旧 generated output、临时截图、`.next` 和候选 worktree。

删除前必须先生成 owner-approved manifest，逐项确认 branch、worktree、stash、报告文件可回滚；不得以“已 merged”自动删除。

## 7. 完整执行计划 TODO

### 已完成（本轮及此前同一 workstream）

- [x] `BRP-P0-SNAPSHOT`：root binary diff、refs、worktree/stash manifests、untracked archives、Git bundle 已保存并核验。
- [x] `BRP-P0-CLEAN-BASELINE`：clean clone pinned 到 `origin/main@b88ecdff...`。
- [x] `BRP-P1-EVIDENCE-TOOLING`：documents probe 对齐 PR #232 页面 shell；部署审计启用 `BatchMode=yes`、`StrictHostKeyChecking=yes`、`IdentitiesOnly=yes`。
- [x] `BRP-P1-READINESS-REVIEW`：readiness branch 手工安全/正确性审查、577 script tests、Ruff/Mypy、隔离 PostgreSQL 15 execute/postcheck/rollback。
- [x] `BRP-P1-LEGACY-REVIEW`：continuation、BM25、governance、squash-merged、patch-equivalent 分支分类完成。
- [x] `BRP-P2-BACKFILL-LOCAL`：backfill CLI 的本地审查、SQL integration 和 rollback 已完成。
- [x] `BRP-P2-PRODUCTION-READONLY`：strict SSH + read-only SQL candidate audit 完成。
- [x] `BRP-P3-LOCAL-GATES`：clean b88 candidate backend/web/full-stack gates 完成；frontend acceptance runner 另行针对当前生产域名执行并留存 L3 结果。
- [x] `BRP-P3-ZERO-EXECUTE-PREFLIGHT`：部署脚本默认 preflight 完成，未带 `--execute`。
- [x] `BRP-P6-CLEANUP-MANIFEST`：本报告的 KEEP/ARCHIVE/DELETE manifest 完成。
- [x] `BRP-P6-DOC-SYNC`：`.kiro/plan/task_plan.md`、`progress.md`、`findings.md` 已同步。
- [x] `BRP-R1-PR232-REVIEW`：完成 PR #232 的 `58` commits / `87` files release delta、风险面和部署差异审查。
- [x] `BRP-R2-BACKFILL-PR-PACK`：完成 readiness branch 的本地 review package；未创建 PR、未 push、未 merge。
- [x] `BRP-R3-CONTINUATION-SLICES`：完成 continuation branch 的 semantic slice map；禁止 whole-branch merge。
- [x] `BRP-R4-BM25-SLICE`：完成 BM25 fallback 最小 slice 的 focused test + Ruff；是否 cherry-pick 仍由 owner 决策。
- [x] `BRP-R5-PROBE-CONTRACT`：修正 documents probe 为 static-export shell 契约，focused tests/Ruff/生产只读 probe 均通过。
- [x] `BRP-P4-FULL-PYTEST`：clean b88 candidate 全量 pytest 通过。
- [x] `BRP-P4-STATIC-EXPORT`：clean b88 candidate static export 通过，`87` files 产物存在。
- [x] `BRP-P4-SMOKE-B88`：b88 runner 对当前生产执行 L3 GET-only smoke 通过。
- [x] `BRP-P4-DEPLOY-PREFLIGHT`：clean b88 candidate deploy preflight 通过，未执行生产写入。

### 下一阶段：owner review / semantic integration

- [x] `BRP-R1-PR232-REVIEW`：已完成；b88 可作为下一生产候选，但仍需 owner 部署授权。
- [x] `BRP-R2-BACKFILL-PR-PACK`：已完成本地 review package；建 PR/push/merge 不在本轮授权内。
- [x] `BRP-R3-CONTINUATION-SLICES`：已完成 semantic slice map；未合并整支 continuation。
- [x] `BRP-R4-BM25-SLICE`：已完成 focused test/Ruff；cherry-pick 仍是 owner 决策项。
- [x] `BRP-R5-PROBE-CONTRACT`：已完成静态 shell marker 契约修正和生产只读复验。

### 需要明确授权的生产步骤（当前保持 blocked）

- [ ] `BRP-GATE-REMOTE-WRITE`：push、建 PR、merge、删除远端 refs；需要独立授权。
- [ ] `BRP-GATE-PRODUCTION-BACKUP`：新建生产备份；需要独立授权并记录 backup stamp、大小、hash、恢复验证。
- [ ] `BRP-GATE-PRODUCTION-SQL`：生产 backfill execute/rollback；需要独立授权，且必须绑定 fresh snapshot hash、approved SHA、backup manifest。
- [ ] `BRP-GATE-PRODUCTION-DEPLOY`：从 clean `main==origin/main==approved SHA` 执行 `--execute --confirm-production`；需要独立授权。
- [ ] `BRP-GATE-PRODUCTION-ACCEPTANCE`：部署后重新跑 strict deployment-state、production smoke、documents probe、frontend acceptance；所有报告都要带同一 deploy SHA。

## 8. 下一次执行顺序（不跨越授权边界）

1. Owner 确认 b88 `b88ecdff...` 为批准部署 SHA，并确认不把未合并 branch 作为本次发布内容。
2. 在执行窗口重新 fetch、确认 clean pinned `main==origin/main==approved SHA`，并重跑 deploy preflight；dirty root 不参与发布。
3. 若 owner 明确授权部署，按“远端备份（如策略要求）→ `--execute --confirm-production` → strict deployment-state → smoke → documents probe → frontend acceptance”顺序执行；任一步失败就停止，不自动 rollback。
4. backfill 仍是独立 SQL gate；除非 owner 另行授权，不与本次应用部署绑定、不执行 `--apply-schema` 或 `--include-review-write`。
5. 只有生产验收通过且 owner 另行授权，才生成逐项 stale-ref/worktree prune manifest 并执行清理。

## 9. 明确禁止的结论

- 在本快照阶段不能写“PR #232 已部署”；当时生产 SHA 仍为 `51dfcb816...`。
- 不能写“所有分支都已合并”；至少存在上述 4 个当前未合并候选及历史 closed-unmerged PR。
- 在本快照阶段不能写“b88 已部署”；当时生产 SHA 仍为 `51dfcb816...`。
- 可以写“当前生产的 GET-only smoke、静态 shell、权限/治理和 hardened frontend acceptance 通过”，但不能把它等同于 b88 已部署或写路径验收。
- 不能写“backfill 已执行/已回滚”；当前只有生产只读候选审计与本地隔离 PostgreSQL 证据。
- 不能把健康容器、matching embeddings、旧备份存在或本地 preflight 当作 deploy 完成证据。

## 10. 证据文件索引

- `tmp/outputs/branch-production-reconciliation-deployment-state-20260714.json`
- `tmp/outputs/branch-production-reconciliation-candidate-audit-20260714.json`
- `tmp/outputs/branch-production-reconciliation-production-smoke-20260714.json`
- `tmp/outputs/branch-production-reconciliation-documents-readonly-20260714.json`
- `tmp/outputs/branch-production-reconciliation-documents-candidate-probe-20260714.json`
- `tmp/outputs/branch-production-reconciliation-frontend-acceptance-candidate-20260714.json`
- `tmp/outputs/branch-production-reconciliation-production-smoke-b88-20260714.json`
- `tmp/outputs/branch-production-reconciliation-documents-shell-probe-20260714.json`
- `tmp/outputs/branch-production-reconciliation-deploy-preflight-20260714.txt`
- `tmp/outputs/branch-production-reconciliation-deployment-state-strict-rerun-20260714.json`
- `tmp/outputs/branch-production-reconciliation-production-smoke-rerun-20260714.json`
- `tmp/outputs/branch-production-reconciliation-documents-shell-probe-rerun-20260714.json`
- `tmp/outputs/branch-production-reconciliation-strict-audit-tool-only.patch`
- `tmp/outputs/branch-production-reconciliation-deploy-preflight-rerun-20260714.txt`
- `tmp/outputs/branch-production-reconciliation-local-branch-matrix-20260714.tsv`
- `tmp/outputs/branch-production-reconciliation-remote-branch-matrix-20260714.tsv`
- `.omc/RELEASE_RULE.md`
- `.kiro/plan/task_plan.md`
- `.kiro/plan/progress.md`
- `.kiro/plan/findings.md`
