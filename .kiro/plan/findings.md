---
title: "medical_audit loop findings"
project: "medical_audit"
created_at: "2026-06-30T21:42:00+08:00"
status: "active"
---

# Findings

## 2026-07-21 Loop 60 Initial Findings

- 修复后 L4 失败码已从上一轮的 `deepseek_citation_ids_invalid` 前进到 `deepseek_citation_markers_mismatch`；这证明“`citation_ids` 缺失/空时从正文 marker 推导”的已部署修复命中了原始硬门，但没有解决 provider 同时返回正文 markers 与冗余 `citation_ids` 不一致的合同问题。
- 失败发生在 `risk-negative-list` case；HTTP 为 `200`，citations/basis groups 存在且 collection 单一正确，但 generation 降级为 `retrieval_fallback`。因此当前调查点是 answer-provider response parser 合同，不是检索 collection 选择或 provider transport。
- 生产 raw provider response 未写入报告，且不应为了调试而重试 live call。根因必须从现有脱敏 failure code、parser 分支和最小本地 payload 稳定复现。
- 当前单一待验假说：DeepSeek 正文已包含可校验的严格 `[C<number>]` 引用，但 provider 额外返回的 `citation_ids` 是不完全同步的冗余元数据；parser 将二者集合必须完全相等作为硬门，导致本来可以仅依正文 marker 安全绑定的答案被降级。该假说尚未由代码与 RED 测试确认。

Boundary: findings are local diagnosis hypotheses only; no provider call, production DB read/write, deploy, or external mutation is authorized in Loop 60.

## 2026-07-21 Loop 60 Parser Trace Findings

- `_deepseek_answer_content()` 的当前顺序为：校验 `answer` 和 `citation_ids` 类型 → 从正文提取严格 `[C<number>]` 得到 `visible_ids` → 从非空 `citation_ids` 得到 `claimed_ids`，否则用 `visible_ids` → 先拒绝不可用 ID → 强制 `visible_ids == claimed_ids`。
- `deepseek_citation_markers_mismatch` 同时表示两种情况：`visible_ids` 为空，或 `visible_ids` 非空但与非空 `citation_ids` 不等。当前 L4 报告不包含 raw provider content，所以不能从现有证据区分这两类。
- 上一轮修复只在 `citation_ids` 缺失/空时以 `visible_ids` 代替；如果 provider 仍未在正文输出严格 marker，新修复应继续失败关闭，不能为了 live pass 自动伪造引用。
- 当前根因判断降级为两个竞争假说：H1a=正文 marker 合法但冗余 `citation_ids` 漂移；H1b=正文未包含严格 marker。必须先追踪下游实际使用和安全绑定，再选择可同时保留 H1b 失败门的最小修复。

## 2026-07-21 Loop 60 Root Cause Decision

- `citation_ids` 全仓仅出现在 DeepSeek prompt/parser 和对应 tests；它不参与 answer builder、citation serialization、basis groups 或 API 输出绑定。真正可见、可审计的绑定是 answer 正文 marker 与当次 `Citation` 列表。
- `answer_builder` 已有明确回归，要求接受 `【C1】` 和 `(C1)` 等变体，并拒绝 `VITC1` 等嵌入式字母数字串。DeepSeek parser 单独使用 `\[(C\d+)\]` 严格 regex，导致同一有效 answer 在 provider 层被拒绝、在 builder 层却被设计为应接受。这是可稳定本地复现的确定根因。
- H1a 的冗余元数据漂移同样是合同缺陷：既然 `citation_ids` 不被下游使用，它不应覆盖已通过可用 citation 校验的正文 markers。但如果该字段存在，非法类型和不可用 ID 仍应失败关闭。
- 最小修复合同：抽取单一 marker-label parser 供 provider 和 builder 共用；要求 `visible_ids` 非空且是 `available_ids` 子集；`citation_ids` 仅作可选的格式/可用性校验，不再要求与 `visible_ids` 完全相等。
- 该修复不能证明上一次 raw provider answer 究竟使用了哪种 marker；它修复的是两个已被代码和测试证明的合同冲突，而不将未保存的 raw 内容冒充为已知事实。

## 2026-07-21 Loop 60 RED Evidence

- RED 测试稳定复现了两个独立缺陷：provider 使用窄 regex 拒绝 builder 合同已支持的 marker 变体；冗余 metadata 集合被错误地赋予与正文 marker 相同的权威性。
- 新增的正文越界测试证明，仅检查 `citation_ids` 子集不足以失败关闭：当 metadata 声称 `C1`、正文实际引用 `C2` 时，必须直接校验 `visible_ids` 对 `available_ids` 的子集关系。
- 预期 GREEN 合同保持三道硬门：非空 visible marker、visible marker 全部可用、存在的 metadata 类型合法且其 ID 全部可用。

## 2026-07-21 Loop 60 GREEN Contract

- 共享 parser 保留既有 builder 安全边界：支持方括号、全角方括号、圆括号、全角圆括号及裸 `C<number>`，但拒绝嵌入更大字母数字 token 的伪 marker。
- DeepSeek provider 的安全权威现在是正文中实际可见的 marker；可选 `citation_ids` 仅作为额外结构化声明接受独立类型/可用性校验。
- `41/41` 定向测试通过只证明本地 parser/builder 合同修复，不证明上一轮 raw provider payload 内容，也不构成生产或 live UAT 证据。

## 2026-07-21 Loop 60 Candidate Decision

- 全量 `890/890`、Ruff、Mypy 和 diff-check 均通过，因此候选满足本地 L1/L2 promotion 前质量门。
- 发布必要性成立：变更直接覆盖已在 L4 中触发的 parser failure family，同时保持无 marker 与越界引用失败关闭；不涉及 schema、env、runtime provider 配置或数据迁移。
- 当前证据仍不能承诺新 live UAT 必然通过，因为上一轮 raw provider response 未保留；只有部署 exact merged SHA 后的新授权 L4 才能验证实际 provider 行为。

## 2026-06-30 Initial Inventory

- Branch: `codex/frontend-2.0`.
- Worktree: dirty; tracked UI/test changes and untracked `.kiro/`, `output/`, and `web/src/app/(workspace)/fund-compliance/review/`.
- Project-local `AGENTS.md`, `.codex/context-pack.md`, and `.codex/session-thread.md`: not found during this pass.
- Existing workflow document `docs/workflows/workflow-fullstack-completeness-audit-and-batch-execution-plan-stable.md` says the next lane is P0-05D production read-only governance verification after deployment, plus P0-04 SSO/session path selection and clean release path.
- The latest frontend fixture E2E result from the preceding turn was green, but that is not fullstack or production evidence.

## Evidence Gate

- Maximum current evidence for latest UI/UX in this loop: local/fixture unless refreshed by commands in the current pass.
- Maximum current evidence for document governance production readiness: L2 from repo scripts/docs until a fresh production GET-only probe is executed.
- Production writes, provider calls, object storage writes, and env writes remain out of scope.

## 2026-06-30 Loop 0-2 Verification

- `git diff --check`: passed.
- Bare `pnpm web:lint` and `pnpm web:typecheck`: blocked by Codex runtime pnpm dependency-state check in non-TTY mode; this is a tool invocation issue, not a code-quality failure.
- `corepack pnpm --filter medical-audit-web lint`: passed.
- `corepack pnpm --filter medical-audit-web typecheck`: passed.
- `corepack pnpm --filter medical-audit-web test`: passed, `11` test files and `93` tests.
- `corepack pnpm --filter medical-audit-web build`: passed, `23/23` static pages.
- Foundation Playwright with manually started Next dev server and fixture API routes: passed, `17/17`.
- `uv run python scripts/run-local-fullstack-e2e.py`: initially blocked by the same bare pnpm non-TTY dependency-state check.
- `PATH="/Users/pray/.nvm/versions/node/v22.22.0/bin:$PATH" uv run python scripts/run-local-fullstack-e2e.py`: passed, `17/17`, using temporary in-memory FastAPI backend.
- Ports `3030` and `8021`: no listeners after validation.

Evidence grade after this pass:

- UI/UX frontend routes: local build/unit/browser evidence.
- Full portal foundation flow: local fullstack in-memory evidence.
- Production state: unchanged in this loop; no production read-only probe, production write, provider call, env write, object storage write, or Docker change.

## 2026-06-30 Loop 4 Clean Worktree Verification

Clean release worktree:

- Path: `/Users/pray/project/medical_audit_minimal_pr`
- Branch: `codex/uiux-topic-forms-agents-20260630`
- Base HEAD: `818b42b7c1045308d0e7e191a97c81e015cacc2f`
- Initial state before sync: clean, no untracked files.

Synced only release manifest files:

- `web/src/app/(workspace)/agent-market/page.tsx`
- `web/src/app/(workspace)/chat/page.tsx`
- `web/src/app/(workspace)/fund-compliance/page.tsx`
- `web/src/app/(workspace)/fund-compliance/review/page.tsx`
- `web/src/app/(workspace)/workspace-pages.test.tsx`
- `web/src/components/shell/app-sidebar.tsx`
- `web/src/components/shell/project-context-bar.tsx`
- `web/src/components/shell/workspace-shell.test.tsx`
- `web/tests/e2e/foundation.spec.ts`

Excluded from clean worktree release candidate:

- `.kiro/**`
- `output/**`
- generated Playwright result folders

Validation in `/Users/pray/project/medical_audit_minimal_pr`:

- `git diff --check`: passed.
- `corepack pnpm --filter medical-audit-web lint`: passed.
- `corepack pnpm --filter medical-audit-web typecheck`: passed.
- `corepack pnpm --filter medical-audit-web test`: passed, `11` files and `93` tests.
- `corepack pnpm --filter medical-audit-web build`: passed, `23/23` static pages.
- `PLAYWRIGHT_REUSE_SERVER=1 corepack pnpm --dir web exec playwright test tests/e2e/foundation.spec.ts --project=chromium`: passed, `17/17`.
- `PATH="/Users/pray/.nvm/versions/node/v22.22.0/bin:$PATH" uv run python scripts/run-local-fullstack-e2e.py`: passed, `17/17`.
- Ports `3030` and `8021`: no listeners after validation.

Evidence grade:

- Clean release candidate local evidence is now `local-fullstack`.
- Production remains unchanged and unobserved in this loop.

## 2026-06-30 Loop 6 Local Release-Candidate Commit

Clean worktree commit:

- Path: `/Users/pray/project/medical_audit_minimal_pr`
- Branch: `codex/uiux-topic-forms-agents-20260630`
- Commit: `8a8592514618`
- Message: `feat(frontend): prepare UIUX topic forms agents release`

Staged and committed file set:

- `web/src/app/(workspace)/agent-market/page.tsx`
- `web/src/app/(workspace)/chat/page.tsx`
- `web/src/app/(workspace)/fund-compliance/page.tsx`
- `web/src/app/(workspace)/fund-compliance/review/page.tsx`
- `web/src/app/(workspace)/workspace-pages.test.tsx`
- `web/src/components/shell/app-sidebar.tsx`
- `web/src/components/shell/project-context-bar.tsx`
- `web/src/components/shell/workspace-shell.test.tsx`
- `web/tests/e2e/foundation.spec.ts`

Verification:

- `git diff --cached --name-status`: exactly the manifest file set before commit.
- `git diff --cached --check`: passed before commit.
- `git status --short --branch`: clean after commit.

Boundary:

- No push, merge, deployment, production read-only probe, production write, provider call, env write, object storage write, or Docker operation was executed in Loop 6.

## 2026-06-30 Loop 7 Gated Promotion

Remote branch:

- Origin: `https://github.com/zjgulai/medical-audit.git`
- Branch: `codex/uiux-topic-forms-agents-20260630`
- Upstream: `origin/codex/uiux-topic-forms-agents-20260630`
- Commit: `8a8592514618`

Draft PR:

- URL: `https://github.com/zjgulai/medical-audit/pull/178`
- Number: `178`
- State: `OPEN`
- Draft: `true`
- Base: `main`
- Head: `codex/uiux-topic-forms-agents-20260630`
- GitHub mergeability field: `MERGEABLE`
- Status checks reported by `gh pr view`: none at the time of this loop.

Boundary:

- Loop 7 performed branch push and Draft PR creation only.
- No merge, deployment, production read-only probe, production write, provider call, env write, object storage write, or Docker operation was executed in Loop 7.

## 2026-06-30 Loop 8 Deploy Preflight Gate

Decision gated:

- Whether PR `#178` can move from local-fullstack evidence to deployment preflight evidence.

Preflight command:

```bash
uv run python scripts/deploy-tencent-cloud-production.py \
  --stamp uiux-topic-forms-agents-pr178-preflight-20260630T2218 \
  --report tmp/outputs/production-e2e-smoke-after-deploy-uiux-topic-forms-agents-pr178-preflight-20260630T2218.json
```

Observed output:

- `mode: preflight`
- `target: ubuntu@101.34.52.232`
- `remote_app_dir: /opt/medical-audit/app`
- `remote_web_dir: /var/www/audit`
- `base_url: https://audit.lute-tlz-dddd.top`
- `Preflight passed. Add --execute --confirm-production to deploy.`

PR state after preflight:

- PR: `https://github.com/zjgulai/medical-audit/pull/178`
- State: `OPEN`
- Draft: `true`
- Base: `main`
- Head: `codex/uiux-topic-forms-agents-20260630`
- Head SHA: `8a859251461879ed2ca3727702530cb73451b369`
- Base SHA: `a398c73990ca677ef71ce9796c043553d00403e1`
- GitHub mergeability field: `MERGEABLE`
- Status checks reported by `gh pr view`: none at the time of this loop.

Evidence grade:

- Deploy preflight: `L2-fixture-or-dry-run` plus remote read checks.
- Production update status: unchanged by this loop.

Boundary:

- Loop 8 did not pass `--execute` or `--confirm-production`.
- The report path was supplied but no production smoke report was generated, because smoke only runs after deployment execution.
- No merge, production deployment, production read-only probe after deployed SHA, production write, provider call, env write, object storage write, schema migration, or write-path smoke was executed in Loop 8.

## 2026-06-30 Loop 9 Release Decision Gate

Decision:

- Choose the smallest safe promotion after clean branch, PR creation, and deploy preflight.
- Selected action: move PR `#178` from Draft to ready for review.
- Deferred actions: merge and production deploy execution require separate explicit authorization.

Execution:

```bash
GH_HTTP_TIMEOUT=90 gh pr ready 178
```

Observed state after execution:

- PR: `https://github.com/zjgulai/medical-audit/pull/178`
- State: `OPEN`
- Draft: `false`
- Base: `main`
- Head: `codex/uiux-topic-forms-agents-20260630`
- Head SHA: `8a859251461879ed2ca3727702530cb73451b369`
- Base SHA: `a398c73990ca677ef71ce9796c043553d00403e1`
- GitHub mergeability field: `MERGEABLE`
- Status checks reported by `gh pr view`: none at the time of this loop.
- Local candidate worktree: clean and tracking `origin/codex/uiux-topic-forms-agents-20260630`.

Boundary:

- Loop 9 performed PR ready-for-review promotion only.
- No merge, production deployment, production read-only probe, production write, provider call, env write, object storage write, schema migration, or write-path smoke was executed in Loop 9.

## 2026-06-30 Loop 10 Merge Decision Gate

Decision:

- Merge PR `#178` after ready-for-review and default deploy preflight evidence.
- Keep production deployment as a separate gate.

Execution:

```bash
GH_HTTP_TIMEOUT=90 gh pr merge 178 \
  --merge \
  --match-head-commit 8a859251461879ed2ca3727702530cb73451b369 \
  --subject "Merge PR #178: Frontend 2.0 UIUX release candidate" \
  --body "Merge the clean Frontend 2.0 UIUX release candidate after local fullstack validation and default deploy preflight. Production deploy remains a separate gated action."
```

Observed state after execution:

- PR: `https://github.com/zjgulai/medical-audit/pull/178`
- State: `MERGED`
- Merged at: `2026-06-30T14:28:52Z`
- Merge commit: `0cc4bfd287050fa5d9fe763409157d0e276f4ba0`
- Head SHA: `8a859251461879ed2ca3727702530cb73451b369`
- Base SHA before merge: `a398c73990ca677ef71ce9796c043553d00403e1`
- `origin/main`: `0cc4bfd287050fa5d9fe763409157d0e276f4ba0`
- `git merge-base --is-ancestor 8a859251461879ed2ca3727702530cb73451b369 origin/main`: passed.

Actual PR merge diff from `a398c73990ca677ef71ce9796c043553d00403e1` to `origin/main`:

- `docs/api/api-knowledge-query-engine-stable.md`
- `scripts/run-production-frontend-acceptance.mjs`
- `src/medical_audit_kb/api/routes_pages.py`
- `tests/knowledge_query/test_pages.py`
- `web/src/app/(workspace)/agent-market/page.tsx`
- `web/src/app/(workspace)/chat/page.tsx`
- `web/src/app/(workspace)/fund-compliance/page.tsx`
- `web/src/app/(workspace)/fund-compliance/review/page.tsx`
- `web/src/app/(workspace)/workspace-pages.test.tsx`
- `web/src/components/portal/data-analysis-workbench.tsx`
- `web/src/components/shell/app-sidebar.tsx`
- `web/src/components/shell/project-context-bar.tsx`
- `web/src/components/shell/workspace-shell.test.tsx`
- `web/src/lib/navigation.ts`
- `web/src/lib/portal-data.ts`
- `web/tests/e2e/foundation.spec.ts`

Scope note:

- Loop 6's 9-file manifest was the incremental candidate set over base `818b42b7`.
- PR `#178` merged both `818b42b7` and `8a859251`, so the actual mainline merge diff covers 16 files.

Boundary:

- Loop 10 performed GitHub PR merge only.
- No production deployment, production read-only probe, production write, provider call, env write, object storage write, schema migration, or write-path smoke was executed in Loop 10.

## 2026-06-30 Loop 11 Production Deploy Pre-Execution Gate

Decision:

- Prepare the post-merge mainline for production deploy execution without running production deploy.
- Explicit deploy authorization is still required before passing `--execute`.

Clean main worktree:

- Path: `/Users/pray/project/medical_audit_minimal_pr`
- Branch after alignment: `main`
- HEAD: `0cc4bfd287050fa5d9fe763409157d0e276f4ba0`
- `origin/main`: `0cc4bfd287050fa5d9fe763409157d0e276f4ba0`
- SSH key check: `ai_video.pem` present.
- Worktree status after checks: clean.

Commands and evidence:

- `git checkout main && git pull --ff-only origin main`: fast-forwarded from `a398c739` to `0cc4bfd2`.
- `git diff --check`: passed.
- `corepack pnpm --filter medical-audit-web lint`: passed.
- `corepack pnpm --filter medical-audit-web typecheck`: passed.
- `corepack pnpm --filter medical-audit-web test`: passed, `11` files and `93` tests.
- `corepack pnpm --filter medical-audit-web build`: passed, `23/23` static pages.
- `PATH="/Users/pray/.nvm/versions/node/v22.22.0/bin:$PATH" uv run python scripts/run-local-fullstack-e2e.py`: passed, `17/17`.
- Default deploy preflight command:

```bash
uv run python scripts/deploy-tencent-cloud-production.py \
  --stamp uiux-topic-forms-agents-main-0cc4bfd-preflight-20260630T2240 \
  --report tmp/outputs/production-e2e-smoke-after-deploy-uiux-topic-forms-agents-main-0cc4bfd-preflight-20260630T2240.json
```

Preflight observed:

- `mode: preflight`
- `target: ubuntu@101.34.52.232`
- `remote_app_dir: /opt/medical-audit/app`
- `remote_web_dir: /var/www/audit`
- `base_url: https://audit.lute-tlz-dddd.top`
- `Preflight passed. Add --execute --confirm-production to deploy.`

Cleanup/status checks:

- Port `3030`: no listener after local fullstack run.
- Port `8021`: no listener after local fullstack run.
- Supplied production smoke report path was not created, because deploy execution was not run.

Boundary:

- Loop 11 did not pass `--execute` or `--confirm-production`.
- No production deployment, production read-only probe after deploy, production write, provider call, env write, object storage write, schema migration, or write-path smoke was executed in Loop 11.

## 2026-06-30 Loop 12 Authorized Production Deploy Execution

Authorization:

- User explicitly authorized production deployment execution after providing the exact deploy command.

Deploy command:

```bash
PATH="/Users/pray/.nvm/versions/node/v22.22.0/bin:$PATH" \
uv run python scripts/deploy-tencent-cloud-production.py \
  --execute \
  --confirm-production audit.lute-tlz-dddd.top \
  --stamp uiux-topic-forms-agents-main-0cc4bfd-20260630
```

Execution evidence:

- Mode: `execute`
- Deployed SHA: `0cc4bfd287050fa5d9fe763409157d0e276f4ba0`
- Static frontend export: `23/23` static pages.
- Remote app sync and `/var/www/audit` static sync executed.
- Docker image rebuilt as `medical-audit-kb:prod`.
- `medical_audit_app` recreated and became `healthy`.
- Deployment smoke report: `tmp/outputs/production-e2e-smoke-after-deploy-uiux-topic-forms-agents-main-0cc4bfd-20260630.json`
- Deployment smoke status: `pass`, `9` steps.
- Query smoke used fallback citations: `fallback_used=true`; this does not prove no-fallback answer-provider readiness.

Deployment state audit:

- Report: `tmp/outputs/tencent-cloud-deployment-state-after-uiux-topic-forms-agents-main-0cc4bfd-20260630.json`
- Status: `pass`
- Issues: `[]`
- Warnings: `[]`
- Deploy SHA: `0cc4bfd287050fa5d9fe763409157d0e276f4ba0`
- app/postgres/clamav: `healthy`
- `audit_next_static_healthy=true`
- `audit_mount_present=true`
- `search_backend_ready=true`
- `matching_embedding_count=49051`
- Required backup stamp verified: `uiux-topic-forms-agents-main-0cc4bfd-20260630`

Production read-only probes:

- Permission readonly report: `tmp/outputs/production-permission-readonly-smoke-after-uiux-topic-forms-agents-main-0cc4bfd-20260630.json`
- Permission readonly status: `observed`, `probe_count=35`, `issue_count=0`, `provider_call_status=not_called`, `production_side_effect=none`.
- Documents readonly report: `tmp/outputs/production-documents-readonly-probe-after-uiux-topic-forms-agents-main-0cc4bfd-20260630.json`
- Documents readonly status: `pass`; deploy SHA matched expected, search backend ready, `matching_embedding_count=49051`, no upload/download side-effect endpoints called.

Frontend semantic acceptance:

- Report: `tmp/outputs/production-frontend-acceptance-after-uiux-topic-forms-agents-main-0cc4bfd-20260630.json`
- Status field: `fail`
- `p0=[]`
- `p1` count: `9`
- P1 items are all missing text expectations for `/fund-compliance` and `/chat`.
- Current product shape check:
  - `/fund-compliance`: `200`, contains `医保基金使用合规专项自查`, `进入专题工作台`, `专题规则`.
  - `/fund-compliance/review`: `200`, contains `专题审计工作台`, `待处理清单`.
  - `/chat`: `200`, contains `AI 审证对话`, `进入对话`, `知识来源`.

Interpretation:

- Production deployment itself is verified by deployment-state audit, smoke, documents readonly, and permission readonly.
- Frontend semantic acceptance script still expects old copy on `/fund-compliance` and `/chat`.
- This is a P1 acceptance-contract drift to resolve in the next loop; it is not a P0 availability blocker.

Boundary:

- Loop 12 executed authorized production deployment and read-only probes.
- Loop 12 did not run schema migration, provider call, object storage write, env write, or write-path smoke.

## 2026-06-30 Loop 13 Frontend Acceptance Contract Alignment

Decision:

- Align the frontend acceptance contract with the current product split:
  - `/fund-compliance` is the topic landing page.
  - `/fund-compliance/review` is the review/table/template workbench.
  - `/chat` uses the simplified `AI 审证对话` copy.

Script change:

- Updated `scripts/run-production-frontend-acceptance.mjs` so `/fund-compliance` checks topic landing copy.
- Added `/fund-compliance/review` to the route matrix.
- Added read-only page interactions for `/fund-compliance/review`: click `费用表单`, then expand `新建表单`, then assert form labels and the create control are visible.
- Updated `/chat` assertions to the current simplified copy.

Production read-only result after contract alignment:

- Command: `node scripts/run-production-frontend-acceptance-gate.mjs --output tmp/outputs/production-frontend-acceptance-loop13-contract-alignment-20260630T2315.json --screenshot-dir tmp/screenshots/production-frontend-acceptance-loop13-contract-alignment-20260630T2315`
- Report: `tmp/outputs/production-frontend-acceptance-loop13-contract-alignment-20260630T2315.json`
- Result: `P0=0`, `P1=2`.
- P1 items:
  - `/fund-compliance/review` desktop horizontal overflow after opening `费用表单 -> 新建表单`: `scrollWidth 1657 > clientWidth 1440`.
  - `/fund-compliance/review` mobile horizontal overflow after opening `费用表单 -> 新建表单`: `scrollWidth 623 > clientWidth 390`.

Local source fix:

- File: `web/src/app/(workspace)/fund-compliance/review/page.tsx`.
- Root cause: the `新建表单` absolute popover opened from the right side without a right-edge constraint, so it expanded beyond the viewport.
- Fix: make the `details` wrapper `relative` and align the form with `right-0` while keeping its existing responsive width cap.

Local verification:

- `node --check scripts/run-production-frontend-acceptance.mjs`: passed.
- `git diff --check -- scripts/run-production-frontend-acceptance.mjs web/src/app/(workspace)/fund-compliance/review/page.tsx`: passed.
- `corepack pnpm --filter medical-audit-web typecheck`: passed.
- `corepack pnpm --filter medical-audit-web test -- workspace-pages.test.tsx`: passed, `30` tests.
- Local browser check on `http://127.0.0.1:3030/fund-compliance/review` after opening `费用表单 -> 新建表单`: desktop `scrollWidth=1440/clientWidth=1440`, mobile `scrollWidth=390/clientWidth=390`.
- `corepack pnpm --filter medical-audit-web lint`: passed.
- `corepack pnpm --filter medical-audit-web test`: passed, `11` files and `93` tests.
- `corepack pnpm --filter medical-audit-web build`: passed, `23/23` static pages.

Boundary:

- Production is not yet updated with the Loop 13 source fix.
- Next loop should promote only the two hotfix files through a clean main worktree, then deploy only through the explicit production execution gate.

## 2026-06-30 Loop 14 Clean Hotfix Promotion And Production Deploy

Clean hotfix branch:

- Worktree: `/Users/pray/project/medical_audit_minimal_pr`.
- Base: `main` at `0cc4bfd287050fa5d9fe763409157d0e276f4ba0`.
- Branch: `codex/loop13-frontend-acceptance-hotfix-20260630`.
- Commit: `b66bbeb5` (`fix(frontend): align acceptance and form popover`).
- File set:
  - `scripts/run-production-frontend-acceptance.mjs`
  - `web/src/app/(workspace)/fund-compliance/review/page.tsx`

Clean-worktree validation before merge:

- `git diff --check`: passed.
- `node --check scripts/run-production-frontend-acceptance.mjs`: passed.
- `corepack pnpm --filter medical-audit-web typecheck`: passed.
- `corepack pnpm --filter medical-audit-web test -- workspace-pages.test.tsx`: passed, `30` tests.
- `corepack pnpm --filter medical-audit-web lint`: passed.
- `corepack pnpm --filter medical-audit-web test`: passed, `11` files and `93` tests.
- `corepack pnpm --filter medical-audit-web build`: passed, `23/23` static pages.
- Local browser width check for `费用表单 -> 新建表单`: desktop `scrollWidth=1440/clientWidth=1440`, mobile `scrollWidth=390/clientWidth=390`.

PR and merge:

- PR: `https://github.com/zjgulai/medical-audit/pull/179`.
- PR state before merge: `CLEAN`, no reported status checks.
- Merge commit: `b7c1f4b622a8cb837972dc5b63ed09baa1121530`.

Production deploy:

- Preflight command: `PATH="/Users/pray/.nvm/versions/node/v22.22.0/bin:$PATH" uv run python scripts/deploy-tencent-cloud-production.py --stamp loop13-frontend-hotfix-main-b7c1f4b-preflight-20260630T2328 --report tmp/outputs/production-e2e-smoke-after-deploy-loop13-frontend-hotfix-main-b7c1f4b-preflight-20260630T2328.json`
- Preflight result: passed without `--execute`.
- Execute command: `PATH="/Users/pray/.nvm/versions/node/v22.22.0/bin:$PATH" uv run python scripts/deploy-tencent-cloud-production.py --execute --confirm-production audit.lute-tlz-dddd.top --stamp loop13-frontend-hotfix-main-b7c1f4b-20260630`
- Deploy smoke report: `tmp/outputs/production-e2e-smoke-after-deploy-loop13-frontend-hotfix-main-b7c1f4b-20260630.json`, `status=pass`, `9` steps.
- Deployment state audit: `tmp/outputs/tencent-cloud-deployment-state-after-loop13-frontend-hotfix-main-b7c1f4b-20260630.json`, `status=pass`, `issues=[]`, `warnings=[]`, deployed SHA `b7c1f4b622a8cb837972dc5b63ed09baa1121530`, app/postgres/clamav `healthy`, backup stamp verified.
- Frontend acceptance gate: `tmp/outputs/production-frontend-acceptance-after-loop13-frontend-hotfix-main-b7c1f4b-20260630.json`, `status=pass`, `23` routes, `46` checks, `P0=0`, `P1=0`; `/audit/logs` and `/audit/logs/export` denied without role as `401` and allowed with admin role as `200`.

Boundary:

- Loop 14 deployed the two-file frontend/acceptance hotfix to production.
- No provider call, env write, object storage write, schema migration, or write-path smoke was executed in this loop.

## 2026-07-01 Loop 15 Demo Rehearsal Pass

Decision:

- Verify whether the current production UI is ready for a live demo path without starting another deployment.
- Keep demo screenshot evidence separate from full frontend acceptance and deployment-state evidence.

Production state audit:

- Command: `uv run python scripts/audit-tencent-cloud-deployment-state.py --expected-deploy-sha b7c1f4b622a8cb837972dc5b63ed09baa1121530 --required-backup-stamp loop13-frontend-hotfix-main-b7c1f4b-20260630 --require-clamav-sidecar --json-output tmp/outputs/tencent-cloud-deployment-state-loop15-demo-rehearsal-20260701T003433.json --markdown-output tmp/outputs/tencent-cloud-deployment-state-loop15-demo-rehearsal-20260701T003433.md`
- Result: `status=pass`, issues `[]`, warnings `[]`, deployed SHA `b7c1f4b622a8cb837972dc5b63ed09baa1121530`, app/postgres/clamav `healthy`, search backend ready with `matching_embedding_count=49051`.

Browser demo rehearsal:

- Artifact directory: `output/playwright/loop15-demo-rehearsal-20260701T003433/`.
- Report: `output/playwright/loop15-demo-rehearsal-20260701T003433/report.json`.
- Scope:
  - `/workspace`
  - `/fund-compliance`
  - `/fund-compliance/review`
  - `/fund-compliance/review` after `费用表单 -> 新建表单`
  - `/chat`
  - `/agent-market`
- Viewports: desktop `1440x960`, mobile `390x900`.
- Result: `status=pass-with-notes`, `12` browser checks, no P0/P1 findings, no horizontal overflow.

Screenshot evidence:

- `output/playwright/loop15-demo-rehearsal-20260701T003433/desktop-workspace.png`
- `output/playwright/loop15-demo-rehearsal-20260701T003433/desktop-fund-compliance-topic.png`
- `output/playwright/loop15-demo-rehearsal-20260701T003433/desktop-fund-compliance-review-list.png`
- `output/playwright/loop15-demo-rehearsal-20260701T003433/desktop-fund-compliance-review-form-open.png`
- `output/playwright/loop15-demo-rehearsal-20260701T003433/desktop-chat.png`
- `output/playwright/loop15-demo-rehearsal-20260701T003433/desktop-agent-market.png`
- `output/playwright/loop15-demo-rehearsal-20260701T003433/mobile-workspace.png`
- `output/playwright/loop15-demo-rehearsal-20260701T003433/mobile-fund-compliance-topic.png`
- `output/playwright/loop15-demo-rehearsal-20260701T003433/mobile-fund-compliance-review-list.png`
- `output/playwright/loop15-demo-rehearsal-20260701T003433/mobile-fund-compliance-review-form-open.png`
- `output/playwright/loop15-demo-rehearsal-20260701T003433/mobile-chat.png`
- `output/playwright/loop15-demo-rehearsal-20260701T003433/mobile-agent-market.png`

P2 experience notes:

- Mobile top-band navigation remains visually crowded: the rehearsal report measured `12-13` interactive controls in the top `190px` across the demo routes.
- Desktop `agent-market` is demo-safe but still reads dense: `39` chip-like elements in the first viewport.
- These are not release blockers because the same run observed no P0/P1, no route error, and no horizontal overflow.

Full frontend acceptance:

- Command: `node scripts/run-production-frontend-acceptance-gate.mjs --output tmp/outputs/production-frontend-acceptance-loop15-demo-rehearsal-20260701T003433.json --screenshot-dir tmp/screenshots/production-frontend-acceptance-loop15-demo-rehearsal-20260701T003433`
- Report: `/Users/pray/project/medical_audit_minimal_pr/tmp/outputs/production-frontend-acceptance-loop15-demo-rehearsal-20260701T003433.json`
- Result: `status=pass`, `23` routes, `46` checks, `P0=0`, `P1=0`; `/audit/logs` and `/audit/logs/export` denied without role as `401` and allowed with admin role as `200`.

Boundary:

- Loop 15 was production read-only and browser-only.
- No deployment, provider call, env write, object storage write, schema migration, or write-path smoke was executed.

## 2026-07-01 Loop 16 Demo Runbook

Decision:

- Choose demo runbook packaging over immediate P2 polish because the production site already has deploy-state evidence, full frontend acceptance, and screenshot rehearsal evidence.
- Keep production frozen for the demo unless a P0/P1 issue appears.

Artifact:

- Runbook: `.kiro/plan/demo_runbook_loop16_20260701.md`.

Included in the runbook:

- Demo claim and evidence summary.
- Verified route order:
  - `/workspace`
  - `/fund-compliance`
  - `/fund-compliance/review`
  - `/fund-compliance/review` after `费用表单 -> 新建表单`
  - `/chat`
  - `/agent-market`
- Presenter script for each step.
- Primary screenshot path for each step.
- Mobile screenshot guidance.
- Evidence boundaries and unsupported claims.
- Recovery path if the live network or page load is unstable.
- Post-demo P2 polish recommendations.

Boundary:

- Loop 16 created planning/demo documentation only.
- Production status remains `b7c1f4b622a8cb837972dc5b63ed09baa1121530`.
- No deployment, merge, provider call, env write, object storage write, schema migration, or write-path smoke was executed.

## 2026-07-01 Loop 17 Last-Minute Spot Check

Decision:

- Run one final production read-only spot check for the live demo path.
- Do not merge, deploy, change environment, call providers, write object storage, apply schema changes, or run write-path smoke unless a P0/P1 issue appears.

Production state audit:

- Command: `uv run python scripts/audit-tencent-cloud-deployment-state.py --expected-deploy-sha b7c1f4b622a8cb837972dc5b63ed09baa1121530 --required-backup-stamp loop13-frontend-hotfix-main-b7c1f4b-20260630 --require-clamav-sidecar --json-output tmp/outputs/tencent-cloud-deployment-state-loop17-spot-check-20260701T013243.json --markdown-output tmp/outputs/tencent-cloud-deployment-state-loop17-spot-check-20260701T013243.md`
- Report: `/Users/pray/project/medical_audit_minimal_pr/tmp/outputs/tencent-cloud-deployment-state-loop17-spot-check-20260701T013243.json`
- Result: `status=pass`, issues `[]`, warnings `[]`, deployed SHA `b7c1f4b622a8cb837972dc5b63ed09baa1121530`, app/postgres/clamav `healthy`, search backend ready with `matching_embedding_count=49051`.

Full frontend acceptance:

- Command: `node scripts/run-production-frontend-acceptance-gate.mjs --output tmp/outputs/production-frontend-acceptance-loop17-spot-check-20260701T013243.json --screenshot-dir tmp/screenshots/production-frontend-acceptance-loop17-spot-check-20260701T013243`
- Report: `/Users/pray/project/medical_audit_minimal_pr/tmp/outputs/production-frontend-acceptance-loop17-spot-check-20260701T013243.json`
- Result: `status=pass`, `23` routes, `46` checks, `P0=0`, `P1=0`; `/audit/logs` and `/audit/logs/export` denied without role as `401` and allowed with admin role as `200`.

Quick browser spot check:

- Artifact directory: `output/playwright/loop17-spot-check-20260701T013243/`.
- Report: `output/playwright/loop17-spot-check-20260701T013243/report.json`.
- Scope: `/workspace`, `/fund-compliance`, `/fund-compliance/review`, `/fund-compliance/review` after `费用表单 -> 新建表单`, `/chat`, `/agent-market`, and mobile `/fund-compliance/review` after opening the new-form path.
- Result: `status=pass`, `7` checks, `hard_issue_count=0`, no horizontal overflow.

Boundary:

- Loop 17 was production read-only and browser-only.
- Production status remains `b7c1f4b622a8cb837972dc5b63ed09baa1121530`.
- No deployment, merge, provider call, env write, object storage write, schema migration, or write-path smoke was executed.

## 2026-07-01 Loop 18 Demo Support Pack

Decision:

- Choose demo support packaging over another UI/code batch because the current production version already has deployment-state, full frontend acceptance, and browser spot-check evidence.
- Keep production frozen before the live presentation unless a P0/P1 issue appears.

Artifact:

- Support pack: `.kiro/plan/demo_support_pack_loop18_20260701.md`.

Included in the support pack:

- One-minute opening statement.
- Live route checklist for `/workspace`, `/fund-compliance`, `/fund-compliance/review`, `/chat`, and `/agent-market`.
- Screenshot fallback paths from `output/playwright/loop17-spot-check-20260701T013243/`.
- Evidence chain for deployment state, frontend acceptance, browser spot check, and runbook.
- Answer boundary for dense UI questions.
- Provider-call boundary for live AI generation questions.
- Post-demo P2 polish scope.

Boundary:

- Loop 18 created planning/demo documentation only.
- Production status remains `b7c1f4b622a8cb837972dc5b63ed09baa1121530`.
- No deployment, merge, provider call, env write, object storage write, schema migration, or write-path smoke was executed.

## 2026-07-01 Loop 19 Local P2 UI Polish

Decision:

- Execute the narrow post-demo P2 polish locally because Loop 17/18 had already made production demo-ready.
- Target only two density issues: mobile shell/top navigation and `agent-market` first-viewport chip/card density.
- Keep production unchanged until a separate clean promotion/deploy gate is authorized.

Implementation:

- `web/src/components/shell/app-sidebar.tsx`
  - Mobile primary navigation now prioritizes compact symbols and hides full text labels until `sm`.
  - Links retain `aria-label` so business names remain accessible when the visible mobile label is hidden.
  - The current-topic CTA is hidden on mobile and remains visible on desktop sidebar.
- `web/src/components/shell/project-context-bar.tsx`
  - Mobile top bar hides global search and return-to-workbench button.
  - Audit topic and role label are pushed to larger breakpoints.
  - Role/status controls move behind a compact details menu.
- `web/src/app/(workspace)/agent-market/page.tsx`
  - Default visible agent cards are limited to `12`.
  - Category tabs are a single horizontal row on mobile.
  - Each card shows one primary tag instead of a cluster of tag chips.
- `web/src/app/(workspace)/workspace-pages.test.tsx`
  - Updated marketplace expectations from `24` default cards to `12`.

Verification:

- `git diff --check`: passed.
- `corepack pnpm --filter medical-audit-web lint`: passed.
- `corepack pnpm --filter medical-audit-web typecheck`: passed.
- `corepack pnpm --filter medical-audit-web test`: passed, `11` files and `93` tests.
- `PLAYWRIGHT_REUSE_SERVER=1 corepack pnpm --dir web exec playwright test tests/e2e/foundation.spec.ts --project=chromium`: passed, `17` tests.
- Local browser report: `output/playwright/loop19-p2-polish-20260701T020257/report.json`, `status=pass`.
- Screenshot evidence:
  - `output/playwright/loop19-p2-polish-20260701T020257/mobile-workspace.png`
  - `output/playwright/loop19-p2-polish-20260701T020257/mobile-agent-market.png`
  - `output/playwright/loop19-p2-polish-20260701T020257/desktop-agent-market.png`
- `corepack pnpm --filter medical-audit-web build`: passed, `23/23` static pages.

Boundary:

- Loop 19 is local source and browser evidence only.
- Production status remains `b7c1f4b622a8cb837972dc5b63ed09baa1121530`.
- No deployment, merge, provider call, env write, object storage write, schema migration, or write-path smoke was executed.

## 2026-07-01 Loop 20 Clean Promotion Candidate

Decision:

- Isolate the Loop 19 P2 polish into the clean release worktree before any production discussion.
- Keep `/Users/pray/project/medical_audit`, `/Users/pray/project/medical_audit_minimal_pr`, and production as separate evidence layers.
- Stop before push, PR, merge, deploy, provider call, env write, object storage write, schema migration, or write-path smoke.

Clean worktree:

- Path: `/Users/pray/project/medical_audit_minimal_pr`.
- Base before branch: `main` at `b7c1f4b622a8cb837972dc5b63ed09baa1121530`, equal to `origin/main`.
- Branch: `codex/p2-ui-density-polish-20260701`.
- Commit: `862d357f7ae5f2aac0071b26a79ba016c6d98fcb` (`ui: reduce mobile shell and agent density`).

Included files:

- `web/src/components/shell/app-sidebar.tsx`
- `web/src/components/shell/project-context-bar.tsx`
- `web/src/app/(workspace)/agent-market/page.tsx`
- `web/src/app/(workspace)/workspace-pages.test.tsx`

Verification:

- `git diff --check`: passed.
- `corepack pnpm --filter medical-audit-web lint`: passed.
- `corepack pnpm --filter medical-audit-web typecheck`: passed.
- `corepack pnpm --filter medical-audit-web test`: passed, `11` files and `93` tests.
- `corepack pnpm --filter medical-audit-web build`: passed, `23/23` static pages.
- `PLAYWRIGHT_REUSE_SERVER=0 corepack pnpm --dir web exec playwright test tests/e2e/foundation.spec.ts --project=chromium`: passed, `17` tests.
- `PATH="/Users/pray/.nvm/versions/node/v22.22.0/bin:$PATH" uv run python scripts/run-local-fullstack-e2e.py`: passed, `17` tests.

Boundary:

- Loop 20 produced a clean local candidate only.
- Production status remains `b7c1f4b622a8cb837972dc5b63ed09baa1121530`.
- No push, PR, merge, deployment, provider call, env write, object storage write, schema migration, or write-path smoke was executed.

## 2026-07-01 Loop 21 Production Promotion Gate

Decision:

- Promote the clean Loop 20 candidate through GitHub and deploy preflight only.
- Keep production execution as a separate gate because deploy writes require `--execute --confirm-production audit.lute-tlz-dddd.top`.

GitHub promotion:

- Pushed branch: `codex/p2-ui-density-polish-20260701`.
- PR: `#180`, `https://github.com/zjgulai/medical-audit/pull/180`.
- PR state before merge: ready PR, `MERGEABLE`, no remote status checks reported.
- Merge commit: `b79a5e499cb99bded782e3ccd9ad4195dcab4e70`.
- Clean worktree after merge: `/Users/pray/project/medical_audit_minimal_pr` on `main`, equal to `origin/main`.

Deploy preflight:

- Command: `PATH="/Users/pray/.nvm/versions/node/v22.22.0/bin:$PATH" uv run python scripts/deploy-tencent-cloud-production.py --stamp loop21-p2-ui-density-main-b79a5e4-preflight-20260701T003125Z --report tmp/outputs/production-e2e-smoke-after-deploy-loop21-p2-ui-density-main-b79a5e4-preflight-20260701T003125Z.json`.
- Result: `mode: preflight`, target `ubuntu@101.34.52.232`, base URL `https://audit.lute-tlz-dddd.top`, and `Preflight passed. Add --execute --confirm-production to deploy.`

Boundary:

- Loop 21 merged source to `main` and verified deploy preflight readiness.
- Production status remains `b7c1f4b622a8cb837972dc5b63ed09baa1121530` until a separately authorized production deploy is executed and verified.
- No production deployment, provider call, env write, object storage write, schema migration, or write-path smoke was executed.

## 2026-07-01 Loop 22 Authorized Production Deploy

Decision:

- Execute the separately authorized production deploy for `main` commit `b79a5e499cb99bded782e3ccd9ad4195dcab4e70`.
- Keep deploy execution, script recovery, production smoke, deployment-state audit, frontend acceptance, and readonly probes as separate evidence layers.

Execution:

- Command started: `PATH="/Users/pray/.nvm/versions/node/v22.22.0/bin:$PATH" uv run python scripts/deploy-tencent-cloud-production.py --execute --confirm-production audit.lute-tlz-dddd.top --stamp loop22-p2-ui-density-main-b79a5e4-20260701T003900Z --report tmp/outputs/production-e2e-smoke-after-deploy-loop22-p2-ui-density-main-b79a5e4-20260701T003900Z.json`.
- Frontend build passed during deploy: `23/23` static pages.
- Remote backups completed for app, env, db, nginx, and web under stamp `loop22-p2-ui-density-main-b79a5e4-20260701T003900Z`.
- The deploy SSH backup handoff exceeded the script timeout and later emitted buffered continuation output; by that point rsync, static sync, Docker image build, and `medical_audit_app` recreate had completed.
- The deploy script process was interrupted before its final post-check/write-sha/smoke tail completed. The missing tail was then completed manually with the same checks: app/clamav health checks, compose `ps`, shared nginx `nginx -t`, internal/public health and search endpoints, `/documents`, and `.deploy-sha` write.

Post-deploy evidence:

- Production `.deploy-sha`: `b79a5e499cb99bded782e3ccd9ad4195dcab4e70`.
- Production smoke: `tmp/outputs/production-e2e-smoke-after-deploy-loop22-p2-ui-density-main-b79a5e4-20260701T003900Z.json`, `status=pass`, `9` steps, no failed steps.
- Deployment-state audit: `tmp/outputs/tencent-cloud-deployment-state-after-loop22-p2-ui-density-main-b79a5e4-20260701T003900Z.json`, `status=pass`, app/postgres/clamav `healthy`, search backend ready, `matching_embedding_count=49051`, latest local smoke `pass`.
- Frontend acceptance: `tmp/outputs/production-frontend-acceptance-after-loop22-p2-ui-density-main-b79a5e4-20260701T003900Z.json`, `status=pass`, `23` routes, `46` checks, `P0=0`, `P1=0`; `/audit/logs` and `/audit/logs/export` denied anonymous as `401` and allowed admin as `200`.
- Permission readonly smoke: `tmp/outputs/production-permission-readonly-smoke-after-loop22-p2-ui-density-main-b79a5e4-20260701T003900Z.json`, `status=observed`, `35` GET probes, `issue_count=0`, `production_side_effect=none`, `provider_call_status=not_called`.
- Documents readonly probe: `tmp/outputs/production-documents-readonly-probe-after-loop22-p2-ui-density-main-b79a5e4-20260701T003900Z.json`, `status=pass`, deploy SHA matched expected, backend/search ready, `matching_embedding_count=49051`; upload-list and download-metadata endpoints were skipped because they write audit logs.
- UI density spot check: `tmp/outputs/production-ui-density-spot-after-loop22-p2-ui-density-main-b79a5e4-20260701T012600Z.json`, `status=pass`, `3` production browser checks, horizontal overflow `0`.
- UI density screenshots:
  - `tmp/screenshots/loop22-p2-ui-density-production-spot-20260701T012600Z/mobile-workspace.png`
  - `tmp/screenshots/loop22-p2-ui-density-production-spot-20260701T012600Z/mobile-agent-market.png`
  - `tmp/screenshots/loop22-p2-ui-density-production-spot-20260701T012600Z/desktop-agent-market.png`

Boundary:

- Loop 22 performed an authorized production deploy and GET-only/read-only verification.
- No provider call, env write, object storage write, schema migration, or write-path review smoke was executed.
- The documents probe intentionally skipped GET endpoints known to write audit logs.

## 2026-07-01 Loop 23 Post-Deploy Observation

Decision:

- Run a post-deploy observation loop rather than another code/deploy loop.
- Keep the maximum claim at production read-only stability for this loop, because no new live write was requested or executed.

Evidence:

- Deployment-state audit: `tmp/outputs/tencent-cloud-deployment-state-loop23-postdeploy-observe-20260701T013000Z.json`, `status=pass`, deployed SHA `b79a5e499cb99bded782e3ccd9ad4195dcab4e70`, app/postgres/clamav `healthy`, search backend ready, `matching_embedding_count=49051`.
- Production smoke: `tmp/outputs/production-e2e-smoke-loop23-postdeploy-observe-20260701T013000Z.json`, `status=pass`, `9` steps, no failed steps.
- Permission readonly smoke: `tmp/outputs/production-permission-readonly-smoke-loop23-postdeploy-observe-20260701T013000Z.json`, `status=observed`, `35` GET probes, `issue_count=0`, `production_side_effect=none`, `provider_call_status=not_called`.
- Documents readonly probe: `tmp/outputs/production-documents-readonly-probe-loop23-postdeploy-observe-20260701T013000Z.json`, `status=pass`, deploy SHA matched expected, search backend ready, `matching_embedding_count=49051`; upload-list and download-metadata endpoints remained skipped because they write audit logs.
- Browser CLI snapshot: production `/agent-market` mobile view showed compact symbol navigation and the `已显示前 12 个` marketplace density marker.
- Browser observation report: `output/playwright/loop23-postdeploy-observe-20260701T013000Z/report.json`, `status=pass`, `4` checks, horizontal overflow `0`.
- Browser screenshots:
  - `output/playwright/loop23-postdeploy-observe-20260701T013000Z/mobile-workspace.png`
  - `output/playwright/loop23-postdeploy-observe-20260701T013000Z/mobile-agent-market.png`
  - `output/playwright/loop23-postdeploy-observe-20260701T013000Z/desktop-agent-market.png`
  - `output/playwright/loop23-postdeploy-observe-20260701T013000Z/mobile-fund-review.png`

Boundary:

- Loop 23 was production read-only and browser observation only.
- No code change, merge, deployment, provider call, env write, object storage write, schema migration, or write-path smoke was executed.

## 2026-07-01 Loop 24 User-Visible Product QA

Decision:

- Move from infrastructure/deploy observation to user-visible product QA.
- Keep this loop read-only: browser observation and report generation only.

Scope:

- Production pages checked across mobile/desktop:
  - `/workspace`
  - `/fund-compliance/review`
  - `/fund-compliance/review` after `费用表单 -> 新建表单`
  - `/chat`
  - `/agent-market`
  - `/documents`

Evidence:

- Browser report: `output/playwright/loop24-product-qa-20260701T014200Z/report.json`.
- Status: `pass-with-notes`.
- Summary: `11` browser checks, `P1=0`, horizontal overflow issue count `0`, markdown artifact count `0`, backend/internal language count `2`.
- Agent market: default visible card count `12`, title out-of-range count `0`, markdown artifact count `0`, and `已显示前 12 个` marker present.
- Fund review/forms: `费用表单` tab, `表1/表2/表3`, and `新建表单` panel were visible in mobile observation; no horizontal overflow was recorded.
- Screenshots:
  - `output/playwright/loop24-product-qa-20260701T014200Z/mobile-workspace.png`
  - `output/playwright/loop24-product-qa-20260701T014200Z/desktop-workspace.png`
  - `output/playwright/loop24-product-qa-20260701T014200Z/mobile-fund-review-list.png`
  - `output/playwright/loop24-product-qa-20260701T014200Z/mobile-fund-review-forms-new.png`
  - `output/playwright/loop24-product-qa-20260701T014200Z/desktop-fund-review-forms-new.png`
  - `output/playwright/loop24-product-qa-20260701T014200Z/mobile-chat.png`
  - `output/playwright/loop24-product-qa-20260701T014200Z/desktop-chat.png`
  - `output/playwright/loop24-product-qa-20260701T014200Z/mobile-agent-market.png`
  - `output/playwright/loop24-product-qa-20260701T014200Z/desktop-agent-market.png`
  - `output/playwright/loop24-product-qa-20260701T014200Z/mobile-documents.png`
  - `output/playwright/loop24-product-qa-20260701T014200Z/desktop-documents.png`

Remaining Product Issue:

- P2: `/workspace` still exposes internal-language copy in mobile and desktop observations: `后端与索引联通` and `postgres`. This should be changed to user-facing wording such as `知识库连接正常` / `检索服务可用` in the next local copy-polish loop.

False Positive Corrected:

- An initial rough markdown detector treated patient masking such as `王**` as a markdown `**` artifact. The report was rerun with a stricter detector; final Loop 24 report has markdown artifact count `0`.

Boundary:

- Loop 24 was production read-only browser observation only.
- No code change, merge, deployment, provider call, env write, object storage write, schema migration, or write-path smoke was executed.

## 2026-07-01 Loop 25 Local Fix For Workspace Internal Copy

Finding Updated:

- Loop 24 P2 `workspace internal-language copy` is fixed locally in the clean worktree candidate, not production.

Local Fix:

- Branch: `/Users/pray/project/medical_audit_minimal_pr` on `codex/p2-workspace-copy-polish-20260701`.
- Commit: `582312e9`.
- Replaced backend-facing status copy (`后端与索引联通`, `FastAPI 正常`, `postgres 已就绪`, `48985 vectors`, `系统健康`) with user-facing copy (`知识库连接正常`, `工作台可用`, `材料可检索`, `48,985 条`, `服务状态`).
- Replaced residual summary/activity terms (`索引联通`, `前端联通检测`, `Markdown / JSON 双形态`, `索引变更`) with `资料可检索`, `规则与底稿草案`, and `资料检索状态待确认`.

Verification:

- `rg` old-copy scan under `web/src`: no matches for the targeted internal terms.
- Local gates passed: `git diff --check`, `lint`, `typecheck`, full web test suite (`93` tests), `next build` (`23/23` static pages), Foundation Playwright (`17/17`).
- Browser evidence: `output/playwright/loop25-workspace-copy-polish-local-20260701T021500Z/report.json`, `status=pass`, mobile/desktop workspace checks have no forbidden matches and horizontal overflow `0`.

Boundary:

- Production remains unchanged at deployed SHA `b79a5e499cb99bded782e3ccd9ad4195dcab4e70` until a separate authorized promotion/deploy loop.
- Default fullstack E2E was not rerun because port `3030` is currently occupied by an unrelated Nuxt dev server; no unrelated process, Docker service, or production service was touched.

## 2026-07-01 Loop 26 Promotion Result For Workspace Copy Fix

Finding Status:

- Loop 24 P2 `workspace internal-language copy` has been promoted from local candidate to `main`.
- Production visibility still requires an authorized deployment and production browser verification.

Remote Promotion Evidence:

- PR: `#181`, `https://github.com/zjgulai/medical-audit/pull/181`.
- Merge commit: `b1c9a6c229a7880afcbfed35c1903d514914bb15`.
- PR merged at: `2026-07-01T02:29:59Z`.

Post-Merge Verification:

- `lint`: passed.
- `typecheck`: passed.
- Full web tests: passed (`11` files / `93` tests).
- `next build`: passed (`23/23` static pages).
- Foundation Playwright: passed (`17/17`) using temporary port `3212`; the temporary config was removed.
- Deploy preflight: passed with stamp `loop26-workspace-copy-main-b1c9a6c-preflight-20260701T023500Z`.

Boundary:

- Current evidence supports: `main` contains the workspace copy fix and is preflight-ready.
- Current evidence does not support: production has the workspace copy fix visible to users.
- Required next proof: authorized production deploy for `main@b1c9a6c2`, followed by deployment-state audit, production smoke, frontend acceptance, and targeted `/workspace` browser copy check.

## 2026-07-01 Loop 27 Production Visibility For Workspace Copy Fix

Finding Status:

- Loop 24 P2 `workspace internal-language copy` is now deployed to production and verified through targeted browser observation.
- Current deployed SHA: `b1c9a6c229a7880afcbfed35c1903d514914bb15`.

Production Deployment Evidence:

- Deploy stamp: `loop27-workspace-copy-main-b1c9a6c-20260701T024500Z`.
- Deploy smoke: `tmp/outputs/production-e2e-smoke-after-deploy-loop27-workspace-copy-main-b1c9a6c-20260701T024500Z.json`, `status=pass`, `9` steps.
- Deployment-state audit: `tmp/outputs/tencent-cloud-deployment-state-after-loop27-workspace-copy-main-b1c9a6c-20260701T024500Z.json`, `status=pass`, `issues=0`, `warnings=0`, app/postgres/clamav `healthy`, search backend ready, `matching_embedding_count=49051`.
- Frontend acceptance: `tmp/outputs/production-frontend-acceptance-after-loop27-workspace-copy-main-b1c9a6c-20260701T024500Z.json`, `status=pass`, `23` routes, `46` checks, `P0=0`, `P1=0`.
- Permission readonly smoke: `tmp/outputs/production-permission-readonly-smoke-after-loop27-workspace-copy-main-b1c9a6c-20260701T024500Z.json`, `status=observed`, `35` GET probes, `issue_count=0`, `production_side_effect=none`, `provider_call_status=not_called`.
- Documents readonly probe: `tmp/outputs/production-documents-readonly-probe-after-loop27-workspace-copy-main-b1c9a6c-20260701T024500Z.json`, `status=pass`, deploy SHA matched, search backend ready, `matching_embedding_count=49051`.

Targeted Product Evidence:

- Browser report: `output/playwright/loop27-workspace-copy-production-20260701T032300Z/report.json`, `status=pass`.
- Mobile and desktop `/workspace` show user-facing copy including `知识库连接正常`, `工作台可用`, `材料可检索`, `可引用资料`, and `49,051 条`.
- Forbidden old-copy matches are empty for the targeted terms: `后端与索引联通`, `FastAPI 正常`, `postgres 已就绪`, `48985 vectors`, `vectors`, `系统健康`, `索引联通`, `前端联通`, `索引健康`, `联通检测`, `只读健康检查刷新`, `索引变更`, `Markdown / JSON`.
- Horizontal overflow: `0` on both mobile and desktop targeted checks.
- Screenshots:
  - `output/playwright/loop27-workspace-copy-production-20260701T032300Z/mobile-workspace-production.png`
  - `output/playwright/loop27-workspace-copy-production-20260701T032300Z/desktop-workspace-production.png`

Boundary:

- Production app/static deployment, remote backups, Docker image build, and app container recreate were executed under explicit deploy authorization.
- The post-deploy probes above are read-only or browser checks.
- Provider call, env write, object storage write, schema migration, and write-path review smoke were not executed.

## 2026-07-01 Loop 28 Post-Deploy Observation

Finding Status:

- Production remains on deployed SHA `b1c9a6c229a7880afcbfed35c1903d514914bb15`.
- Loop 28 refreshed L3 production read-only evidence after Loop 27 and created a demo evidence freeze.

Read-Only Evidence:

- Deployment-state audit: `/Users/pray/project/medical_audit_minimal_pr/tmp/outputs/tencent-cloud-deployment-state-loop28-postdeploy-observe-20260701T114051+0800.json`, `status=pass`, `issues=[]`, `warnings=[]`, app/postgres/clamav `healthy`, search backend ready, `matching_embedding_count=49051`.
- Frontend acceptance: `/Users/pray/project/medical_audit_minimal_pr/tmp/outputs/production-frontend-acceptance-loop28-postdeploy-observe-20260701T114051+0800.json`, `status=pass`, `23` routes, `46` checks, `P0=0`, `P1=0`.
- Permission readonly smoke: `/Users/pray/project/medical_audit_minimal_pr/tmp/outputs/production-permission-readonly-smoke-loop28-postdeploy-observe-20260701T114051+0800.json`, `status=observed`, `35` GET probes, `issue_count=0`, `production_side_effect=none`, `provider_call_status=not_called`.
- Documents readonly probe: `/Users/pray/project/medical_audit_minimal_pr/tmp/outputs/production-documents-readonly-probe-loop28-postdeploy-observe-20260701T114051+0800.json`, `status=pass`, deploy SHA matched expected, search backend ready, `matching_embedding_count=49051`.
- Browser observation: `/Users/pray/project/medical_audit/output/playwright/loop28-postdeploy-observe-20260701T114051+0800-browser/report.json`, `status=pass`, `issueCount=0`.

Product Observation:

- `/workspace` mobile/desktop: required user-facing copy present; targeted old internal-copy matches empty; horizontal overflow `0`.
- `/fund-compliance/review` after selecting `费用表单`: `表1`, `表2`, `表3` visible; horizontal overflow `0`.
- `/chat`: `AI 对话` visible; targeted old internal-copy matches empty; horizontal overflow `0`.
- `/agent-market`: `智能体广场` and `已显示前 12 个` visible; markdown-artifact markers empty; horizontal overflow `0`.

Boundary:

- Loop 28 did not change production, code, schema, env, object storage, or provider state.
- A first browser observation pass stopped on default `疑点单据` tab and marked the fee table terms missing; the final browser evidence clicked `费用表单` before asserting `表1/表2/表3` and passed. This is recorded as assertion refinement, not a product regression.

## 2026-07-01 Loop 29 Demo Handoff

Finding Status:

- Demo handoff is packaged from Loop 28 evidence without additional production probes.
- Evidence grade remains `L3-production-read-only`.

Handoff Output:

- `.kiro/plan/demo_handoff_loop29_20260701.md`

Practical Demo Notes:

- Lead with `/workspace` to show product state and user-facing service copy.
- Open `/fund-compliance/review`, switch to `费用表单`, and show `表1/表2/表3` as the audit-table contract surface.
- Use `/chat` for citation-first reasoning, and avoid claiming provider-call activity from Loop 28/29.
- Use `/agent-market` to show compact helper selection, not full agent inventory.
- Use `/documents` to show materials and knowledge-base readiness.

Boundary:

- Loop 29 changed only planning/handoff docs.
- Production, provider, env, object storage, schema, and write-path review state were untouched.

## 2026-07-01 Loop 30 Backlog Triage

Finding Status:

- No P0/P1 product issue is open from the available Loop 28/29 evidence.
- Real demo feedback has not been provided in this thread, so Loop 30 does not invent feedback-derived defects.
- Backlog is organized into authorized validation lanes and feedback-dependent product polish lanes.

Backlog Output:

- `.kiro/plan/post_demo_backlog_loop30_20260701.md`

Triage Result:

- P0: none open from Loop 28/29 evidence.
- P1: none open from Loop 28/29 evidence.
- P2:
  - select real auth/SSO/session path and close header-transition ambiguity;
  - authorize write-path acceptance for review tasks, document upload governance, audit logs, and related locked-state behavior;
  - authorize answer-provider readiness/smoke only when provider calls are allowed;
  - harden acceptance checks around tabbed states such as `费用表单`;
  - collect real demo notes before starting further UI density or copy changes.
- P3:
  - consolidate local evidence artifacts and retire obsolete demo packs after the presentation;
  - turn repeated browser observations into a durable scripted check if needed.

Boundary:

- Loop 30 changed only planning/backlog docs.
- No production probe, code change, provider call, env write, object storage write, schema migration, write-path review smoke, merge, or deployment was executed.

## 2026-07-01 Loop 31 Feedback Intake And Lane Gate

Finding Status:

- Loop 31 converted the backlog into an intake and authorization gate.
- No implementation lane has been selected.
- Real demo feedback remains required before treating any UI/product issue as observed.

Gate Output:

- `.kiro/plan/feedback_intake_loop31_20260701.md`

Lane Gate:

- P2-A auth/session: planning and local contract tests first; production auth changes require explicit approval.
- P2-B write-path acceptance: requires disposable scope, rollback plan, backup expectations, and explicit production-write approval.
- P2-C answer provider: requires provider-call approval and cost/credit confirmation.
- P2-D tab-state acceptance hardening: safest later implementation candidate because it can start as local/test-only work.
- P2-E UI feedback: requires route, screenshot, expected outcome, and user role.

Boundary:

- Loop 31 changed only planning/gate docs.
- No production probe, code change, provider call, env write, object storage write, schema migration, write-path review smoke, merge, or deployment was executed.

## 2026-07-01 Loop 32 P2-D Tab-State Acceptance Hardening

Finding Status:

- Loop 32 selected the local/test-only P2-D lane.
- The `费用表单` flow now has stronger component and browser E2E acceptance around tab state, the three Excel-derived templates, and the custom form entry point.

Evidence Added:

- `.kiro/plan/tab_state_acceptance_loop32_20260701.md`
- `web/src/app/(workspace)/workspace-pages.test.tsx`
- `web/tests/e2e/foundation.spec.ts`

Verification:

- `CI=true corepack pnpm@9.15.0 --filter medical-audit-web test -- 'src/app/(workspace)/workspace-pages.test.tsx'`: pass, 30 tests.
- `PLAYWRIGHT_REUSE_SERVER=1 CI=true corepack pnpm@9.15.0 exec playwright test tests/e2e/foundation.spec.ts --grep 'fund compliance topic opens a separate review workbench'`: pass, 1 test.

Supported Claim:

- Local tests can verify that `/fund-compliance/review` keeps the expected tab semantics for `费用表单`, `表1`, `表2`, `表3`, and custom form creation visibility.

Unsupported Claim:

- This loop does not refresh production evidence and does not prove any production write path.

Boundary:

- No provider call, env write, object storage write, schema migration, write-path smoke, merge, production probe, or deployment was executed.

## 2026-07-01 Loop 33 Targeted Local Verification

Finding Status:

- Loop 33 widened Loop 32 verification to local frontend static gates and the full foundation browser suite.
- The tab-state acceptance changes remained compatible with the broader frontend foundation route checks.

Evidence Added:

- `.kiro/plan/targeted_verification_loop33_20260701.md`

Verification:

- `CI=true corepack pnpm@9.15.0 --filter medical-audit-web lint`: pass.
- `CI=true corepack pnpm@9.15.0 --filter medical-audit-web typecheck`: pass.
- `CI=true corepack pnpm@9.15.0 --filter medical-audit-web test -- 'src/app/(workspace)/workspace-pages.test.tsx'`: pass, 30 tests.
- `PLAYWRIGHT_REUSE_SERVER=1 CI=true corepack pnpm@9.15.0 exec playwright test tests/e2e/foundation.spec.ts`: pass, 17 tests.

Supported Claim:

- The current local frontend worktree passes static checks, the workspace component suite, and the full foundation browser route suite.

Unsupported Claim:

- This loop does not prove production behavior, live provider quality, backend fullstack behavior, or write-path behavior.

Boundary:

- No production probe, provider call, env write, object storage write, schema migration, write-path smoke, merge, or deployment was executed.

## 2026-07-01 Loop 34 Atomic Staging Plan

Finding Status:

- The current dirty worktree contains mixed UI, test, tooling, planning, route, and generated artifact changes.
- Loop34 created an atomic staging plan and did not stage anything.

Evidence Added:

- `.kiro/plan/atomic_staging_loop34_20260701.md`

Inventory:

- 9 tracked modified files.
- `.kiro/`: 14 untracked files, about 180 KB.
- `output/`: 142 untracked files, about 22 MB.
- `web/src/app/(workspace)/fund-compliance/review/page.tsx`: 1 untracked route file.

Recommended Groups:

- Group A: Loop32/33 test acceptance, patch-stage required.
- Group B: topic review product surface.
- Group C: broader frontend-2.0 polish.
- Group D: production acceptance script tooling.
- Group E: planning and evidence docs.
- Group F: generated browser artifacts, excluded from ordinary code commits unless explicitly selected.

Supported Claim:

- The current worktree has a documented staging order and ownership-risk split.

Unsupported Claim:

- No staged diff, commit, push, merge, deployment, production check, backend fullstack proof, provider proof, or write-path proof was created by this loop.

Boundary:

- Plan-only.
- No staging, commit, push, merge, deployment, production probe, provider call, env write, object storage write, schema migration, or write-path smoke was executed.

## 2026-07-01 Loop 35 Docs-Only Staging Rehearsal

Finding Status:

- Loop35 selected Group E from the Loop34 staging split.
- The docs-only candidate set is small enough for a first atomic staging unit and excludes code, scripts, generated browser artifacts, env, schema, provider, and production paths.

Evidence Added:

- `.kiro/plan/docs_staging_rehearsal_loop35_20260701.md`

Candidate Scope:

- `.kiro/plan/*.md`
- `.kiro/steering/planning-context.md`

Rehearsed Command:

- `git add -- .kiro/plan/*.md .kiro/steering/planning-context.md`

Verification:

- Sensitive marker scan over `.kiro/plan` and `.kiro/steering`: no hits.
- Cached diff remained empty during rehearsal.

Supported Claim:

- The docs-only staging unit is defined and ready for explicit staging approval.

Unsupported Claim:

- This loop did not create a staged diff, commit, push, merge, deployment, production check, backend fullstack proof, provider proof, or write-path proof.

Boundary:

- Rehearsal only.
- No staging, commit, push, merge, deployment, production probe, provider call, env write, object storage write, schema migration, or write-path smoke was executed.

## 2026-07-01 Loop 36 Docs-Only Staging Execution

Finding Status:

- Loop36 executes the first atomic unit from the Loop34 split.
- The unit is docs-only and intentionally excludes business code, generated browser artifacts, deployment tooling, env, schema, provider, object storage, Docker, and production paths.

Evidence Added:

- `.kiro/plan/docs_staging_execution_loop36_20260701.md`

Staged Scope:

- `.kiro/plan/*.md`
- `.kiro/steering/planning-context.md`

Verification:

- Cached diff contains 17 staged docs/planning files.
- Cached diff stat is 17 files and 3122 insertions.
- `git diff --cached --check`: pass.
- Sensitive marker scan over `.kiro/plan` and `.kiro/steering`: no hits.
- Out-of-scope staged path check: empty output.

Supported Claim:

- The docs-only governance and evidence files are staged as one atomic git-index unit after cached diff verification.

Unsupported Claim:

- This loop does not establish a code commit, push, merge, deployment, production check, backend fullstack proof, provider proof, or write-path proof.

Boundary:

- Git index staging only.
- No commit, push, merge, deployment, production probe, provider call, env write, object storage write, schema migration, Docker change, or write-path smoke is part of this loop.

## 2026-07-01 Loop 37 Docs-Only Local Commit

Finding Status:

- Loop37 commits the docs-only governance and evidence unit created by Loop36.
- The broader `codex/frontend-2.0` product/code work remains outside the commit.

Evidence Added:

- `.kiro/plan/docs_commit_loop37_20260701.md`

Commit Scope:

- `.kiro/plan/*.md`
- `.kiro/steering/planning-context.md`

Supported Claim:

- The governance/evidence docs are preserved as one local atomic commit after cached diff verification.

Unsupported Claim:

- This loop does not establish push, merge, deployment, production check, backend fullstack proof, provider proof, or write-path proof.

Boundary:

- Local commit only.
- No push, merge, deployment, production probe, provider call, env write, object storage write, schema migration, Docker change, or write-path smoke is part of this loop.

## 2026-07-13 Loop 51 Initial Findings

- The safe implementation checkout is the PPT feature worktree; the repository root contains extensive unrelated user-owned changes and is unsuitable for this batch.
- The three pre-existing dirty documents in the feature worktree are protected and outside the Loop 51 staging manifest.
- The four known repository-wide quality findings are narrow and locally repairable:
  - line wrapping in `src/medical_audit_kb/api/routes_chat.py`;
  - import ordering in `src/medical_audit_kb/ingestion/inventory.py`;
  - explicit `SourceCollection | None` narrowing before `source_collection_definition()`;
  - replacing an unreachable static `Hashable` type branch in `src/medical_audit_kb/indexing/bm25_index.py` with a runtime hashability check.
- The attached key has safe local permissions (`0600`) and is readable. This establishes only local key readiness, not SSH success or production health.
- Previous production/deploy facts in this ledger are historical and cannot be treated as current until a fresh read-only audit is completed.
- Production deployment remains a separate L4 action; this loop currently permits L1/L2 local/preflight evidence and L3 read-only remote evidence only.

### Loop 51 Resolved And Remaining

- Resolved locally: two Ruff findings, two Mypy findings, one stale authorization fixture, strict SSH host verification, and preflight remote-temp-file mutation.
- Current production is healthy and exactly aligned to `origin/main@51dfcb81`; it is not aligned to the PPT feature branch.
- Generic production frontend and permission gates are green, but the documents product-specific probe remains red on new page text. This is a useful deployment-drift signal and must turn green after deployment.
- Capacity is currently sufficient for another normal backup/build cycle, but DB backup retention is the dominant disk consumer. No cleanup is authorized or required in this loop.
- Immediate execute remains blocked by two distinct facts: no clean release checkout and no separate production execute authorization.
- A preflight pass from `--allow-dirty` is L2 preparation evidence only and must never be reused as proof that a dirty checkout is safe to deploy.

## 2026-07-01 Loop 38 Government-Style UI And Typography Batch Plan

Finding Status:

- The user's typography/font-size concern changes the redesign from page polish to design-system work.
- A credible government-style medical-audit UI requires type scale, line-height, numeric alignment, and long-text containment to be planned together with navigation and color.

Evidence Added:

- `.kiro/plan/gov_ui_typography_batch_plan_loop38_20260701.md`

Supported Claim:

- The next implementation loop has a concrete Batch 1 target: global tokens, type scale, shell/nav simplification, and responsive visual verification.

Unsupported Claim:

- This loop does not implement the visual redesign, produce browser screenshots, push commits, merge branches, deploy production, or validate production UI.

Boundary:

- Docs-only planning.
- No business-code edit, push, merge, deployment, production probe, provider call, env write, object storage write, schema migration, Docker change, or write-path smoke is part of this loop.

## 2026-07-01 Loop 39 Government-Style Shell Batch 1

Finding Status:

- The most visible density issue is the shell layer: too many modules, status pills, role controls, topic tags, and tabs compete for the first horizontal band.
- The first implementation batch should simplify the shared shell before page-specific copy and component redesign.

Evidence Added:

- `.kiro/plan/gov_ui_shell_batch_loop39_20260701.md`

Supported Claim:

- Batch 1 reduced shell density locally while preserving route inventory: the main sidebar now has five common entries, utility modules are folded, top-bar status/tabs are removed, and shared typography/token changes passed local checks.
- Local verification passed: `git diff --check`, targeted shell/navigation tests `18`, full unit tests `94`, typecheck, lint, and browser overflow checks for `/workspace`, `/chat`, and `/fund-compliance/review`.

Unsupported Claim:

- This loop does not establish production UI status, production deploy completion, backend integration coverage, provider proof, or write-path proof.
- Local browser console includes expected local-dev proxy responses when the backend target is not started; do not reuse this loop as backend acceptance evidence.

Boundary:

- Local UI/test loop only.
- No push, merge, deployment, production probe, provider call, env write, object storage write, schema migration, Docker change, or write-path smoke is part of this loop.

## 2026-07-02 Loop 48 PR 182 Merge Gate

Finding Status:

- PR `#182` is merged into `main`.
- `origin/main` now contains PR head `fa846ad33f547f72b23b8e35967bf7912fc9ce69`.
- Merge commit is `e2cdb9d1353645fd6b565708cace2f851a452c95`.

Evidence Added:

- PR URL: `https://github.com/zjgulai/medical-audit/pull/182`.
- Merge timestamp: `2026-07-02T02:14:16Z`.
- Main worktree used for post-merge sync: `/Users/pray/project/medical_audit_minimal_pr`.
- Docs backup directory: `/Users/pray/.Codex/file-history/medical_audit-loop48-docs-20260702T101529+0800`.

Supported Claim:

- The government-style frontend UI branch has been merged to `main` through PR `#182`.
- The merge gate did not run production deployment or production observation.

Unsupported Claim:

- This loop does not establish production UI status, production deployment completion, backend integration coverage, provider proof, or write-path proof.
- Empty GitHub status checks should not be described as CI success; they mean no checks were reported for this branch.

Boundary:

- GitHub PR merge gate only.
- No production deployment, production probe, provider call, env write, object storage write, schema migration, Docker change, or write-path smoke is part of this loop.

## 2026-07-02 Loop 49 Post-Merge Local Gates And Deploy Preflight

Finding Status:

- `main@4d54922d` has passed post-merge local frontend gates.
- The production deploy script preflight passed for stamp `loop49-pr182-main-4d54922-preflight-20260702T022100Z`.
- Production has not been updated in this loop.

Evidence Added:

- Head: `4d54922dd5cc0ad2399e1a6b4494d2beeef59df2`.
- Merge commit included in main: `e2cdb9d1353645fd6b565708cace2f851a452c95`.
- Docs backup directory: `/Users/pray/.Codex/file-history/medical_audit-loop49-docs-20260702T101935+0800`.

Supported Claim:

- The merged government-style frontend UI is locally build/test ready and deploy-preflight ready.
- The next useful gate is production `--execute --confirm-production`, but only after explicit authorization.

Unsupported Claim:

- This loop does not establish production UI status, production deployment completion, backend integration coverage, provider proof, or write-path proof.
- Empty preflight report path is not a missing smoke artifact; post-deploy smoke JSON is only expected after deployment execution.

Boundary:

- Local validation plus deploy preflight only.
- No production deployment, production probe, provider call, env write, object storage write, schema migration, Docker change, or write-path smoke is part of this loop.

## 2026-07-02 Loop 46 PR 182 Conflict Resolution Gate

Finding Status:

- PR `#182` now has a local conflict-resolution merge commit on `codex/frontend-2.0`.
- The resolution is intentionally hybrid: it keeps the government-style UI simplification from the PR branch and keeps `main`'s fund-compliance/workspace-copy semantics where those are the newer deployed product contract.
- Local frontend gates and Foundation E2E passed after conflict resolution.

Evidence Added:

- Merge commit: `83d432399b7d0c78f3ac033486f714543c9260df`.
- First verified post-resolution branch head: `4d0368b558e6d4871fd5a3ab7284730526a9b3a4`.
- PR `#182` after GitHub recomputation: `OPEN`, `Draft`, `MERGEABLE`, `CLEAN`, empty status check rollup.
- Backup directory: `/Users/pray/.Codex/file-history/medical_audit-loop46-pre-merge-20260702T085942+0800`.
- Docs backup directory: `/Users/pray/.Codex/file-history/medical_audit-loop46-docs-20260702T090852+0800`.
- Post-push docs backup directory: `/Users/pray/.Codex/file-history/medical_audit-loop46-postpush-docs-20260702T091301+0800`.

Supported Claim:

- The local branch conflict surface is resolved and locally verified for frontend compile/test/build plus Foundation browser coverage.
- The relevant local UI routes still use the latest simplified copy contracts after merging `origin/main`.
- GitHub now reports the PR conflict state clear after the pushed resolution, while the PR remains Draft.

Unsupported Claim:

- This loop does not establish GitHub ready-for-review state, PR merge state, production UI status, production deployment completion, backend integration coverage, provider proof, or write-path proof.
- Local Playwright backend proxy messages are not backend acceptance evidence because the backend target was not started for this loop.

Boundary:

- Local PR-branch conflict-resolution gate only.
- No ready-for-review transition, PR merge, deployment, production probe, provider call, env write, object storage write, schema migration, Docker change, or write-path smoke is part of this loop.

## 2026-07-02 Loop 47 PR 182 Ready-For-Review Gate

Finding Status:

- PR `#182` has moved from Draft to ready-for-review.
- GitHub reports PR `#182` as `OPEN`, `MERGEABLE`, and `CLEAN`.
- The branch still has no configured status checks reported by GitHub.

Evidence Added:

- PR URL: `https://github.com/zjgulai/medical-audit/pull/182`.
- Branch head: `b48a464a3f3f6073b051a1597d6e74e597a8e59d`.
- Base head: `b1c9a6c229a7880afcbfed35c1903d514914bb15`.
- Docs backup directory: `/Users/pray/.Codex/file-history/medical_audit-loop47-docs-20260702T091749+0800`.

Supported Claim:

- PR `#182` is now review-ready and no longer blocked by merge conflicts.
- This is a remote GitHub state change, not a production or deployment state change.

Unsupported Claim:

- This loop does not establish PR merge state, production UI status, production deployment completion, backend integration coverage, provider proof, or write-path proof.
- Empty GitHub status checks should not be described as CI success; they mean no checks were reported for this branch.

Boundary:

- PR review-status gate only.
- No PR merge, deployment, production probe, provider call, env write, object storage write, schema migration, Docker change, or write-path smoke is part of this loop.

## 2026-07-02 Loop 42 Government UI Clean Promotion Plan

Finding Status:

- The Loop39-41 UI work is locally validated, but the current worktree also contains many untracked screenshot and browser-output artifacts.
- Promotion needs a clean candidate set before any staging or commit, otherwise local evidence output can be mixed into the release path.

Evidence Added:

- `.kiro/plan/gov_ui_clean_promotion_plan_loop42_20260702.md`

Supported Claim:

- The intended promotion set is `31` paths across `.kiro/plan`, `scripts`, `web/src`, and `web/tests`.
- `output/` and `tmp/outputs/` are excluded as local evidence artifacts.
- Local verification passed: `git diff --check`, typecheck, lint, full frontend unit tests `94`, and build `23` static pages.

Unsupported Claim:

- This loop does not establish production UI status, production deploy completion, backend integration coverage, provider proof, write-path proof, or PR/merge state.
- This loop did not stage or commit the candidate set.

Boundary:

- Local promotion-plan loop only.
- No staging, commit, push, merge, deployment, production probe, provider call, env write, object storage write, schema migration, Docker change, or write-path smoke is part of this loop.

## 2026-07-02 Loop 43 Government UI Local Commit Gate

Finding Status:

- Loop42 identified a clean promotion set, but the work was not yet staged or committed.
- The current risk is accidental staging of local screenshot and browser-output artifacts.

Evidence Added:

- `.kiro/plan/gov_ui_local_commit_loop43_20260702.md`

Supported Claim:

- The local Git gate is ready to stage only intended UI, script, test, and planning files.
- `output/` and `tmp/outputs/` remain excluded from the planned staged set.

Unsupported Claim:

- This loop does not establish production UI status, production deploy completion, backend integration coverage, provider proof, write-path proof, PR state, merge state, or remote branch state.

Boundary:

- Local Git gate only.
- No push, merge, deployment, production probe, provider call, env write, object storage write, schema migration, Docker change, or write-path smoke is part of this loop.

## 2026-07-02 Loop 44 Government UI Draft PR Publish Gate

Finding Status:

- Local commit `99f5b3f5` was ready for review publishing after Loop43.
- The GitHub connector did not have sufficient permission to create the PR, so the authenticated `gh` fallback was required.

Evidence Added:

- `.kiro/plan/gov_ui_pr_publish_loop44_20260702.md`

Supported Claim:

- Branch `codex/frontend-2.0` was pushed to `origin`.
- Draft PR `#182` was opened against `main`: `https://github.com/zjgulai/medical-audit/pull/182`.
- GitHub connector PR creation failed with `403 Resource not accessible by integration`; `gh pr create --draft` succeeded.
- `gh pr view` reported `mergeable=CONFLICTING` and empty status check rollup after creation.

Unsupported Claim:

- This loop does not establish ready-for-review state, merge state, production UI status, production deploy completion, backend integration coverage, provider proof, or write-path proof.
- This loop does not resolve PR conflicts.

Boundary:

- Draft PR publish gate only.
- No ready-for-review transition, merge, deployment, production probe, provider call, env write, object storage write, schema migration, Docker change, or write-path smoke is part of this loop.

## 2026-07-02 Loop 45 PR 182 Conflict Strategy Gate

Finding Status:

- PR `#182` is not blocked by CI evidence; GitHub reports no checks.
- The blocking issue is a real merge conflict between the government-style UI reduction branch and `main`'s already-merged B2B/workspace-copy lane.
- The conflict is concentrated in 10 frontend/test/acceptance files, not in backend, database, provider, Docker, or production scripts.

Evidence Added:

- `.kiro/plan/pr182_conflict_strategy_loop45_20260702.md`

Supported Claim:

- Draft PR `#182` remains open and draft, with `mergeable=CONFLICTING`.
- The next useful action is local conflict resolution on `codex/frontend-2.0`, not CI debugging.
- A naive "take ours" or "take theirs" resolution would lose product intent: the PR branch has the stronger density/non-AI wording cleanup, while `main` has fund-compliance B2B workbench semantics and deployed workspace-copy wording that should be preserved.

Unsupported Claim:

- This loop does not prove the conflicts are resolved.
- This loop does not establish ready-for-review state, merge state, production UI status, production deployment completion, backend integration coverage, provider proof, or write-path proof.

Boundary:

- PR conflict triage and strategy only.
- No business-code edit, conflict resolution, ready-for-review transition, merge, deployment, production probe, provider call, env write, object storage write, schema migration, Docker change, or write-path smoke is part of this loop.

## 2026-07-01 Loop 41 Government-Style Remaining Workspace Pages Batch 3

Finding Status:

- After Batch 1 and Batch 2, the remaining visible density was concentrated in documents, knowledge-base, analytics, reports, and projects pages.
- The main UI risks were wide table patterns on mobile, raw backend identifiers in document evidence UI, prompt/template terminology in reports, and dense side rails.

Evidence Added:

- `.kiro/plan/gov_ui_remaining_pages_batch_loop41_20260701.md`
- `tmp/outputs/loop41-ui-density/density-report.json`

Supported Claim:

- Batch 3 reduced the remaining workspace-page density locally while preserving routes and business flows.
- Local verification passed: `git diff --check`, focused workspace tests `30`, full unit tests `94`, typecheck, lint, build `23` static pages, and browser overflow checks for 10 desktop/mobile route viewports.
- Browser pass reported horizontal overflow `0` for every checked viewport.

Unsupported Claim:

- This loop does not establish production UI status, production deploy completion, backend integration coverage, provider proof, or write-path proof.
- Local browser console includes expected local-dev proxy messages when the backend target is not started; do not reuse this loop as backend acceptance evidence.

Boundary:

- Local UI/test loop only.
- No push, merge, deployment, production probe, provider call, env write, object storage write, schema migration, Docker change, or write-path smoke is part of this loop.

## 2026-07-01 Loop 40 Government-Style Core Pages Batch 2

Finding Status:

- After the shell cleanup, the next visible density issue was in the core business pages: topic landing metrics, review header copy, chat prompt terminology, and the assistant library card grid.
- The assistant library still read like a prompt catalog until card descriptions were moved into the dialog and the grid was reduced to compact entry cards.

Evidence Added:

- `.kiro/plan/gov_ui_core_pages_batch_loop40_20260701.md`
- `output/playwright/loop40-gov-core-pages-20260701T184500+0800/loop40-browser-metrics.json`

Supported Claim:

- Batch 2 reduced core-page first-viewport density locally while preserving routes and business flows.
- Local verification passed: `git diff --check`, full unit tests `94`, typecheck, lint, and browser overflow checks for 7 desktop/mobile route viewports.
- Browser pass found no checked legacy visible terms in page body and reported horizontal overflow `0` for every checked viewport.

Unsupported Claim:

- This loop does not establish production UI status, production deploy completion, backend integration coverage, provider proof, or write-path proof.
- Local browser console includes expected local-dev proxy messages when the backend target is not started; do not reuse this loop as backend acceptance evidence.

Boundary:

- Local UI/test loop only.
- No push, merge, deployment, production probe, provider call, env write, object storage write, schema migration, Docker change, or write-path smoke is part of this loop.

## 2026-07-13 Loop 52 PR #232 Remediation Findings

Finding Status:

- 初始独立复审发现跨项目 finding 访问、非管理员 readiness 全局计数、上传前身份校验、前端跨身份状态污染和部署门禁不完整等 P1 问题。
- 二次复审进一步发现 review task scope 来源不一致、deep-link 重放、stale install response、默认 smoke 隐含写审计日志和 rollback marker 时序问题。
- 对上述问题逐项补测试和修复后，最终独立复审结论为 PASS，未发现剩余 P0/P1。

Supported Claim:

- audit finding 的读取、导出、页面和四类 mutation 均按调用者可见 project scope 执行；finding-linked review task 使用统一 scope 解析并拒绝冲突。
- analytics upload 在读取或保留上传文件前完成用户身份校验与规范化。
- 前端 replica、agent install/favorite/notice 与请求结果按 role/user generation 隔离，旧身份响应不会覆盖新身份状态。
- 默认生产 smoke 使用 knowledge-base catalog GET 路径；成功鉴权路径不调用 `record_operation`，独立实测 operation log delta 为 `0`。
- execute 只接受 clean `main` 且要求 `HEAD == origin/main == approved_sha`；Nginx 检查和 L4 smoke 均 fail closed。
- rollback 以实际当前 marker 和备份 restore SHA 为准，恢复验证完成后才写回 restored marker。

Residual Risk:

- project-member 的 `(project_key, user_identifier)` 数据库唯一约束尚未实现；需要单独完成历史数据探查、冲突清理、migration 和 rollback 设计。
- 历史 review task 可能存在 finding 关联但两处 dossier scope 都缺失的记录；当前 API 仅在已授权 mutation 时惰性回填，生产部署前仍需只读库存盘点。
- 本轮只完成本地脚本语义、测试和 L2 preflight 证据；没有执行真实生产 rollback，不能把语法/fixture 通过表述为生产回滚已验证。

Boundary:

- 三个修复 commit 均仅存在于本地分支。
- 未执行 push、merge、SSH、deploy、provider call、migration、production write 或 live send。

## 2026-07-15 Loop 53 Production Evidence Side-Effect Findings

Finding Status:

- 旧权限 smoke 的匿名/缺失租户 GET 会由 controlled API middleware 写入 `authorization-denied`。
- `/audit/logs/export` 的成功 GET 会写入 `audit-logs-export`。
- 问题不限于拒绝和导出：`/agents`、`/projects`、`/analytics/table-uploads`、`/graph/workbench`、`/reports/workbench` 等成功 GET 也会调用 `record_operation`。因此 HTTP GET 不是数据库只读的充分条件。
- 完整生产前端浏览器矩阵会加载上述 API，不能诚实标为 L3 `database_write=false`。
- `run-production-e2e-smoke.py` 默认调用链当前不执行遗留 `_check_audit_log_permissions`，其默认 smoke 仍保持该检查为 `not_run`；该不可达代码未来若重新启用，必须进入显式审计日志写模式。

Supported Claim:

- 权限 smoke 的通用只读集合只有 2 个不进入 controlled-auth middleware 的 public probe；默认执行 2、skipped 33、候选总数 35。
- 完整权限矩阵和完整前端浏览器验收可在用户已授权后作为 L4 `audit-log-only` 证据执行，但不得与 L3 只读证据混写。
- 任意目标的写模式缺少 `--confirm-production-write audit.lute-tlz-dddd.top` 时必须在任何网络动作前失败关闭；transport 不跟随 redirect，浏览器阻断跨 origin 请求。
- frontend gate 必须按 runner profile 精确验证 `route × viewport` 集合；报告不保存正文、heading、console/interaction 原文、URL query/fragment 或默认截图。
- 最终人工对抗复核与 bundled Codex `0.144.2` review 均为 PASS，accepted P0/P1 为 `0`；gate 还会拒绝只有 route/viewport 而缺少 status、度量与 issues 的伪完整报告。

Residual Risk:

- `/auth/session` handler 虽不直接调用 `record_operation`，但 disabled/pending persistent profile 等 middleware 拒绝路径会持久化 `authorization-denied`，所以已从只读 allowlist 移除。
- 前端完整验收的 `audit-log-only` 合同依赖页面交互仍为 GET/read 路径；未来新增业务写操作时必须重新审计。
- deploy preflight 不检查磁盘空间；2026-07-15 fresh SSH 显示根盘可用 `75,256,524 KiB`，可读部署备份目录合计 `54,397,672 KiB`，四个核心容器健康。`observations` 子目录无读取权限，容量结论不包含该目录。

Boundary:

- 已观察的至少 69 条审计事件保留，未清理。
- 本节记录时 production runtime 仍为 `b88ecdff7f773c8990454009d4a2b33ea8fdc2d4`；`deploy_execute=false`。

## 2026-07-15 Loop 54 True-L3 Audit Findings

Verified current state:

- PR `#234` 已合并为 `2bba501c93eaf1f6f7485241ec15e0c21c209842`，该 SHA 已部署且与生产 marker 一致。
- 状态审计脚本每次调用一次 `GET /index/search-backend`；该 handler 无条件执行 `record_operation("search-backend-status-view")`，生产 SQL audit store 会插入一条 `AuditLogEvent`。
- 时间窗和计数证据显示 deployment-state audit 前后恰好 `+1`；因此 CLI 的 `read-only` 描述和 workflow 的“不会修改数据库”陈述均不成立。
- 完整前端 L4 验收后审计表为 `56066`；新增 63 条均属于读取视图、权限拒绝或审计导出 action。
- release reconciliation worktree 当前干净并已从 `main` 创建专用分支；原始 worktree 落后 `172` commits 且有大量用户修改，必须隔离。

Decision:

- 修复目标优先是真 L3，而不是仅把脚本重标为 L4。
- 状态来源必须同时满足：不触发 controlled-auth denial 持久化、不调用 `record_operation`、返回 search backend readiness/embedding count、声明 `database_write=false` 与 `provider_call=false`。
- 如果修复只涉及本地 operator script、tests 和 docs，则 `runtime_deploy_required=false`；以一次全局快照不变且唯一 auditor identity 零事件的生产验证闭环，不重复重建生产容器。

Known process gap:

- `.omc/RELEASE_RULE.md` 尚不存在；按 release workflow 需要从当前 repo/CI/deploy 规则生成本地 release rule cache，并明确本项目以 deploy SHA 而非本轮 semver bump 作为发布身份。

Initial implementation trace:

- `run-production-e2e-smoke.py` 已把 `/api/v1/knowledge-base/catalog` 作为默认 search-backend 只读来源，并强制其 `boundaries.database_write is false`、`boundaries.provider_call is false`；可复用该既有合同，避免发明第二套状态语义。
- deployment-state audit 当前报告缺少顶层 evidence/side-effect 字段；真 L3 修复需同时改变数据来源和报告合同，不能只替换 URL。
- 初次全量文档搜索输出过大并被截断；后续改为针对稳定 workflow 和脚本测试的窄行区间读取，不从截断输出下结论。

Catalog contract details:

- `/knowledge-base/catalog` 返回 `search_backend.backend`、`search_backend.ready`、`search_backend.details`，并在 `summary.current_search_embedding_count` 返回 active matching count；这与 deployment-state audit 现有判定所需信息等价。
- 同一响应的 `boundaries` 明确 `production_write=false`、`provider_call=false`、`database_write=false`、`object_storage_write=false`、`query_history_write=false`。
- 现有 deployment-state fixture 仍模拟旧 `/index/search-backend` payload，相关测试尚未断言 URL、边界字段或顶层证据等级；Phase 2 需要先新增这些 RED 合同断言。

Rejected status sources:

- `/index/postgres-status` 虽被 controlled-auth middleware 列为 public，但 handler 成功后无条件记录 `postgres-index-status-view`，不能作为真 L3 来源。
- `/knowledge-base/catalog` 本身不调用 `record_operation`，但它属于 protected prefix；缺租户、无效/disabled identity 会由 middleware 持久化 `authorization-denied`。仅凭成功路径不能给整个工具宣称 fail-closed read-only。
- 下一候选为远端容器内直接只读 PostgreSQL 检查，或新增专用无审计 runtime endpoint；前者不暴露新公网接口且可能避免第二次 runtime deploy，优先评估。

Selected true-L3 design:

- 保留 catalog 对 runtime search-engine readiness 的观测，但改用每次生成的唯一审计身份，避免命中持久化 disabled/pending profile。
- 在请求前后通过 PostgreSQL 容器执行单条 `transaction_read_only=on` 聚合 SQL，同时读取全表 count、最新 `created_at`、有序 event-id fingerprint 和本次唯一 auditor identity 的事件计数；只有全局快照不变、identity 前后均为 `0` 且 catalog 全部 write/provider boundaries 为 false 才允许顶层 `evidence_grade=L3-production-read-only`。
- catalog 原始大响应不写入报告；只规范化保留 backend、ready、安全 embedding metadata、matching count、contract version 和 boundaries。
- count delta 非零、snapshot/identity 变化或任一测量不可用时必须 fail closed，不得输出 L3；该方案不要求新增公网 endpoint，也不要求因 operator-only 变更再次重建生产 runtime。

Independent review limitation:

- 当前实现只能保证“全局快照不变且唯一 auditor identity 前后均无事件才分类为 L3”，不能保证每条失败路径在结构上零写入；controlled-auth 401/403 仍可能先产生一条 `authorization-denied`，随后才被门禁检测。
- `provider_call_status=not_called` 来自 catalog 响应的静态 boundary，并有源码调用链支持，不是外部 provider 计量。
- 全局 count 单独使用会被 retention 删除与新增事件相抵；当前实现额外比较最新时间和有序 event-id fingerprint，并单独归因本次唯一 identity。并发生产流量或 retention 会造成 fail-closed 阻断，不会仅因净计数为 `0` 错误升级为 L3。

Adversarial review findings:

- 第一项 accepted P1：仅比较全表 count 存在“新增 1 + retention 删除 1”净 delta `0` 的 false-positive 风险。修复后使用同一只读 SQL 的 count/latest/fingerprint/identity-count 快照，任一变化均阻断 L3。
- 第二项 accepted P1：旧 `_build_report` 计算了 `audit_frontdoor_healthy` 但未把 false 加入 issues。修复后 `/api/v1/health` 或 `/documents` 失败会追加 `audit-frontdoor-not-ready` 并使报告失败。
- 第三项 accepted P1：旧 remote audit 直接打开 `medical-audit.env` 并以 `docker compose --env-file` 解析 secret-bearing 文件，违反仓库 secret 边界。修复后从运行中 app 容器仅读取固定六项非 secret runtime 配置，Compose 服务从 project/service labels 发现，不再打开 env 文件或枚举完整环境。
- 第四项 accepted P1：audit snapshot 安全但 catalog boundaries 缺失时曾错误输出 `database_write=false`。修复后只有 snapshot/identity 与 boundaries 同时安全才能输出 false；否则为 `unknown`。
- 第五项 accepted P1：纯全局正 delta 曾被错误归因成 `audit-log-only`。修复后只有唯一 identity 从 `0` 增至正数且 boundaries 安全才能输出该分类；纯全局变化为 `unknown`。
- 新增 balanced mutation、auditor-attributed event、missing boundaries 和 unhealthy frontdoor 回归测试；最终精确总数以 Phase 3 全量复验为准。
- 最终独立复审结论：accepted P0/P1=`0`，把握高；`runtime_deploy_required=false`。剩余 P2 为全表有序 fingerprint 在 audit 表大幅增长后的性能成本，应后续监控，不影响当前约 5.6 万行规模的验收。

Production candidate acceptance:

- 独立只读 baseline 与 after 均为 audit count `56066`、latest `2026-07-14 19:51:16.836935+00`；未观察到并发或 retention 漂移。
- candidate audit 内部 before/after count、latest 和 event-id fingerprint 完全一致，本次 UUID auditor identity 事件计数 `0→0`。
- 报告 `status=pass`、`evidence_grade=L3-production-read-only`、`production_side_effect=none`、`database_write=false`、`provider_call_status=not_called`、issues/warnings 为空。
- runtime marker 仍为 `2bba501c93eaf1f6f7485241ec15e0c21c209842`；四个相关容器健康，frontdoor/static/mount/search 通过，matching embeddings `49051`。
- 这是从本地 operator candidate 对现有 production runtime 的 L3 成功运行证据，不表示该 operator commit 已部署到 runtime；本轮 `runtime_deploy_required=false`，production unchanged。

GitHub promotion evidence:

- commit `1cf7538d51d5f1f0eb108ffcad92efc312dfc6a4` 已 push 并创建 Draft PR `#235`。
- GitHub pre-merge state 为 `MERGEABLE/CLEAN`，head/base 精确匹配；status checks 为 `0`，没有 CI 通过证据。
- PR 文件集合与 intended 8-file manifest 完全一致；remote branch retention 保持，未删除任何远端分支。

## 2026-07-15 Loop 56 PPT Production Closure Findings

Verified baseline:

- 附件 15 页曾被收敛为 R01-R19，并在本地报告中全部标记 pass；该报告是 local deterministic / fixture evidence，不能替代原始 PPT 逐页生产 UAT。
- PR `#232` merge commit `b88ecdff7f773c8990454009d4a2b33ea8fdc2d4` 是 PPT 产品实现；它是已部署 SHA `2bba501c93eaf1f6f7485241ec15e0c21c209842` 的祖先。PR `#233/#234/#235` 未改变 `src/` 或 `web/` 产品 runtime。
- 初始 `origin/main@f2e2c7...` 没有 `POST /projects` 或前端 `createProject`；现有项目 API 只包含列表、详情、成员、驾驶舱和新增成员。本 Loop 候选已补齐该缺口，但尚未合入或部署。
- 初始历史对话抽屉只链接回 `/chat?history=...`；没有选择项目并人工转任务的 action/API。本 Loop 候选已补齐该缺口，但尚未合入或部署。
- 初始文档 category adapter 使用 `document_count ?? chunk_count ?? 0`，会把未知统计或 chunk 数错误呈现为文档数。本 Loop 候选现只接受 `document_count`，未知保持 `null`，真实 `0` 保持 `0`。
- 六类报告目录中只有 `workpaper` active，其余五类为 `awaiting-business-template`；业务流程图谱等待医院输入；三个扩展智能体受 feature flag 控制且当前无真实 provider smoke。

Evidence-grade decision:

- 允许声明：PR `#232` 的既有 PPT 产品范围已随生产 SHA `2bba501...` 部署；该生产版本有既有健康证据；本 Loop 三个新缺口仅为 L2 本地候选，尚未合入或部署。
- 禁止声明：原始 PPT 已逐页生产验收；真实医院数据、业务流程图、五类正式模板或三个扩展智能体真实调用已完成。
- 下一最小证据：对三个代码缺口先建立 RED tests，并生成覆盖最终代码的本地 Playwright matrix；生产 L4 验收另行执行。

History-to-task architecture facts:

- `QueryHistoryStore` 当前只有 `add_query` 与全量 `list_queries`，没有按 id/owner 读取；`SqlAlchemyQueryHistoryStore.list_queries` 也未按 `user_identifier` 过滤。人工转任务前必须新增 owner-scoped lookup，禁止用前端 history payload 作为可信证据。
- 持久化 query history 已包含 `id`、`user_identifier`、`question`、`filters`、`answer_summary` 和 `retrieved_chunk_ids`，足以在不改 schema 的情况下形成 conversation-task dossier。
- `ReviewTaskStore` 已支持持久化 `add_task`，且报告草稿创建已有“权限校验 -> project scope -> audit intent -> add task -> audit completed/degraded”的可复用两阶段模式。
- 新 endpoint 应显式接收 `project_key`，从持久化 history 读取内容，以 query owner + project visibility + task permission 三重校验后创建 `source=query-history-manual-task` 的 pending-review task；不得自动批量转换。
- 当前权限枚举没有 `create_review_task` 或 `create_project`；应采用最小权限扩展而不是借用不相干的管理权限。角色分配需 fail closed，并同步前端权限合同。

Project-creation architecture facts:

- `AuditProject` 表和 `AuditWorkflowRepository.create_project` 已存在，因此新建项目不需要 schema migration；表字段覆盖 project key、名称、scenario/status、owner department、created_by、description 和 metadata。
- 当前门户项目列表并不读取 `audit_projects`，而是读取 `DEFAULT_PROJECT_PAYLOADS`；仅调用现有 repository 写入 `audit_projects` 会产生“写入成功但门户不可见”的伪闭环。
- `SqlAlchemyProjectMemberStore` 已持有同一 database URL，并通过 `audit_project_members.project_key` 管理可见范围；最小一致路径是在该 collaboration store 中增加动态 project list/create，并在同一事务中创建 project 与创建人 active/负责人 membership。
- `project_exists`、`project_payloads_with_member_counts` 和 `visible_project_keys` 被 routes_projects、routes_pages、routes_workbench、routes_query 复用；动态项目支持必须同步这些 helper/callers，不能只改 `/projects` 页面。
- 最小权限建议新增 `CREATE_PROJECT`，先只授予 admin；创建项目后 creator 自动可见。后续如业务要求主任可创建，再通过明确权限决策扩展。

Document metric implementation facts:

- `ReplicaDocumentCategory.count` 已改为 `number | null`；只使用 `document_count`，不再以 `chunk_count` 冒充文档数；缺失时保留未知，真实 `0` 保持 `0`。
- 页面总数采用保守聚合：任一分类未知则显示“待同步”，不会把未知相加为 `0`；真实空目录仍显示 `0`。
- targeted frontend regression 已由主线程复验；本地浏览器 `/documents` 已确认真实 `0` 显示为 `0`，混合未知/chunk-only 由单元测试覆盖。

Loop 56 implementation closure:

- 历史转任务新增 owner-scoped history lookup 和 `POST /query/logs/{id}/review-task`。只有用户显式选择可见项目并提交后才创建 `pending-review` 任务；project visibility、task permission 与历史 owner 均 fail-closed。
- UUID 的标准、uppercase 和无连字符写法统一为 canonical UUID；重复提交返回同一 task id，数据库仅保留一条任务。任务 store 失败时审计链以 `create-failed` 终止，不留下伪成功。
- 历史任务采用专用 dossier renderer；JSON、Markdown 与 DOCX 均可导出，DOCX 正文包含历史问题、答案摘要、引用片段与审计范围。
- 项目创建新增 admin-only `POST /projects` 和前端表单；动态项目与创建人成员在同一 transaction 中落库，创建后在 list/detail/members/dashboard/graph/report-draft 等既有可见范围链路可用。
- 项目写路径要求显式持久化 project store 与 audit store；缺失时在业务写入前返回 `503`，不再回退到进程内 store。审计统一记录 `user_identifier`、`role`、`endpoint` 和 `project_key` entity。
- 成员统计读取失败时动态项目返回 `member_count=null`，前端显示“待同步”；项目或历史转任务的 audit degraded 状态不会被成功提示隐藏。

Independent review remediation:

- 三路首轮只读复审发现的 canonical UUID、导出、terminal audit、持久化 project/audit store、审计索引、未知成员数、文档/chunk 语义、移动抽屉滚动、降级提示、表单与安全错误映射问题均已修复并补回归。
- 后续复审补齐 operation-specific capability：项目创建/成员 mutation 同时要求 `store.ready && persistent_writes_ready`；历史转任务同时要求项目读取 ready、持久化项目成员 store 与持久化 review-task store。
- `JsonFileReviewTaskStore` 的坏 JSON、非法 UTF-8、非 object root/tasks/entry、不可写路径与 Unicode 写入均 fail-closed；接口统一返回 `503`，原非法文件不被覆盖，审计仅留下单一 `intent -> create-failed` 终态。
- 最终独立复审结论为 `accepted P0/P1/P2=0`，把握高。`codex review --uncommitted` helper 因本机 CLI/模型版本不匹配未产出结果，未计入通过证据。

Fresh local acceptance:

- 后端 targeted：历史/项目共 `28 passed`；全量 Pytest 收集 `645` 项并通过。
- 前端全量 Vitest：`32 files / 295 tests`。
- `uv run ruff check .`、`uv run mypy src`、`pnpm web:typecheck`、`pnpm web:lint`、`pnpm web:build`（`24/24` pages）和 `git diff --check` 均通过。
- `pnpm local:fullstack:e2e`：`13/13 passed`。
- 本地浏览器：项目创建返回 `201` 且创建人成员为项目负责人；历史转任务返回 `200`、`provider_call=false`、重复 UUID 保持同一 task；移动抽屉 `overflow-y:auto` 且关闭控件可达；Markdown/DOCX 导出均为 `200`。
- 浏览器使用临时本地 SQLite 和显式 SQL stores；因此边界是 `database_write=local-test-only`、`production unchanged`、`provider_call=false`。
- 发布准备状态：`ready_for_owner_authorization`；未 stage、commit、push、开 PR、merge 或 deploy。

## 2026-07-15 Loop 57 PPT Candidate Promotion Findings

Atomicity findings:

- 38-file Loop 56 worktree 加 1 个提交计划文件后，最终 PR 候选预计为 39 files；`output/playwright/**`、临时 SQLite、缓存与 backups 均未进入 manifest。
- 后端、项目/历史前端、文档统计、产品验收依据和推广状态账本按 5 个可独立回滚 concern 拆分；共享文件均整体归入单一 concern，没有同一版本的重复 patch staging。
- 每个 staged set 都核对 name-status、stat 与 cached diff check；每次 commit 后 index 为空，剩余 concern 继续保持 unstaged。
- refined secret scan 未发现 private key、GitHub token、OpenAI-style key 或 Tencent-style key；初次 `sk-` broad match 是 `risk-...` 业务字符串的 false positive。

GitHub findings before final ledger push:

- Draft PR `#236` 已存在，初始 head `c03b5ab...`；产品/验收 docs push 后 head 为 `d6b862c...`，local/remote 相等。
- GitHub 新鲜状态为 `OPEN/Draft/MERGEABLE/CLEAN`，4 commits、36 files；checks count=`0`，不能声称 CI passed。
- PR body 已包含验证证据、生产路径、回滚方案和 PPT 11/12/13/15 的医院输入/provider 阻塞。
- 最终状态账本 commit 的 SHA、push 成功和 PR final head 必须在 commit 之后外部核对；该文件不自我引用未产生的 SHA。

Evidence boundary:

- 当前仅完成 GitHub Draft PR 推广，不是 Ready、merge、deploy preflight 或 production deploy。
- `production unchanged`、`provider_call=false`、`database_write=false`、`deploy_execution=false`。

## 2026-07-16 Loop 58 Next Batch Deployment Planning Intake

Current verified state:

- Active release worktree is `/Users/pray/project/medical_audit_release_reconciliation_20260714` on `codex/production-ui-reconciliation-20260716` at `HEAD=489ff70185c70b008d1d30b41ce239386e9debd9`, descending from `origin/main@1376baef0d8d47f1e1ef60b2cec130451af5af4f` and `29` commits ahead.
- The current candidate contains `12` modified tracked files and remains intentionally uncommitted. Exact-SHA build, commit, push, PR, merge, deploy and production acceptance have not been executed for this candidate.
- Task 11 local checkpoint has fresh route-identity evidence and a mobile history-control safe-area fix. The earlier `task11-local-browser-matrix-current.json` is pre-fix evidence with `source_sha=null`; it cannot be promoted into current acceptance.
- Fresh local gates already cover Web lint/typecheck/Vitest/static export, backend Pytest/Ruff/`mypy src`, focused Playwright and `git diff --check`. `uv run mypy src scripts` still reports `195` errors in `10` pre-existing files outside the current diff and outside `origin/main..HEAD`; this is a named repository gate debt, not a current-candidate regression.
- Loop 54's production SHA is historical evidence only. A future deploy decision must refresh the current production marker, backup inventory, container health and front-door state before using any production baseline claim.

Planning decision:

- Reuse the existing Task 12 exact-SHA deployment contract instead of creating a second competing deploy path.
- Split the next batch into independent authorization/evidence gates: candidate freeze, local commit and review, exact-SHA release proof, Draft PR, Ready/merge decision, clean-main preflight, production deploy, L3 post-deploy state audit, optional L4 `audit-log-only` browser/permission acceptance, and separately authorized business-write/provider lanes.
- Keep rollback identity bound to the pre-deploy marker plus versioned static release and backup stamp; never accept a symbolic `main` target as deployment identity.
- Plan-only boundary for this turn: `local_only`, `production unchanged`, `provider_call=false`, `database_write=false`, `live_send=false`, `deploy_execution=false`.

Tooling note:

- The `planning-with-files` session-catchup command could not run because `/Users/pray/.agents/skills/planning-with-files/assets/scripts/session-catchup.py` is absent. Per the skill's no-repeat rule, the same command was not retried; context reconciliation continues from fresh `git status`, `.kiro/plan` ledgers, the active release plan and current scripts.

Active plan reconciliation:

- Tasks 9 and 10 already define the canonical frozen release-manifest and versioned/atomic static-release path. The next-batch plan should consume those contracts, not invent a parallel rsync/deploy procedure.
- Task 12 already separates Ready, merge and exact-SHA deployment authorization, but its production acceptance wording needs an explicit evidence split: conditional L3 deployment-state audit versus explicit L4 `audit-log-only` full browser/permission acceptance.
- The final `Current decision` line in the active plan still points to Task 1 despite the current Task 11 checkpoint; it is stale and must be replaced with the current `NO-GO` reason and next authorized batch.
- Task 12's before/after snapshot requirement is directionally correct but not yet an operator-ready TODO: the next batch must name snapshot scope, artifact paths, allowed audit delta, prohibited business deltas and stop conditions before any deploy execution can be authorized.

Candidate topology and gate implications:

- `origin/main..HEAD` is a linear `29`-commit chain touching `41` files (`13,319` insertions / `940` deletions) before the current `12`-file uncommitted checkpoint. The release candidate is therefore the whole branch plus the current delta, not merely the latest UI fix.
- The committed branch delta contains Web runtime, release-manifest tooling, hardened deploy/audit operator code, Nginx release policy, tests and workflow docs; it contains no `src/` application-runtime or schema/migration change. App rebuild eligibility must still be recomputed from the final merge SHA before deployment.
- The current local branch has no configured remote feature-branch upstream. Push/Draft PR remains an external side effect requiring separate authorization.
- The production frontend acceptance runner intentionally requires `--allow-audit-log-writes` plus `--confirm-production-write`; even though its browser HTTP method contract is `GET`, its evidence is L4 `audit-log-only`, with `database_write=audit-log-only` and `provider_call_status=not_called`.
- The deploy CLI exposes separate preflight/default, `--execute`, and `--rollback` modes. Production execute requires exact `--approved-sha` plus `--confirm-production audit.lute-tlz-dddd.top`; `--allow-dirty`, `--apply-schema`, provider smoke and review-write flags must remain absent from this batch.

Deploy/rollback implementation facts:

- Execute mode builds from a temporary `git archive` of the approved SHA, then performs remote preflight, lock acquisition, five-category backups, app sync, versioned static staging/verification, optional app rebuild, atomic activation, post-check, smoke and final `.deploy-sha` commit. Preflight mode stops before those writes.
- Any unknown remote write outcome retains the production lock and requires manual reconciliation. Failures after activation/app rebuild/schema side effects also retain the lock and require manual rollback; the plan must not prescribe an automatic retry.
- Rollback is bound to the original deployment `--stamp`, its app/Web backups and transaction directory, plus exact `--expected-current-sha` and `--restore-sha`. It validates the current marker before restoring and rebuilds the app as part of rollback; therefore rollback itself requires separate production-write authorization.
- The current L3 deployment-state auditor snapshots the audit log and release/runtime identity, but the repository has no dedicated operator script for the broader prohibited business-table/object-store before/after matrix required by Task 12. That evidence gap must be closed before full L4 frontend acceptance or the plan must explicitly narrow the acceptance claim.

Independent deployment/acceptance review:

- Two read-only reviews confirmed the current candidate is not yet an operator-ready Task 12 `GO`. Required pre-promotion work is: migration-readiness classification, broad read-only S0/S1/S2 snapshot tooling, full-screenshot enforcement, exact deploy-SHA/public-manifest binding and run-specific frontend acceptance identity.
- The first versioned-release deployment is likely a legacy flat-root migration. This must be proven by a fresh read-only topology probe as exactly one of `legacy_ready`, `versioned_ready` or `partial_or_unknown`; only `legacy_ready` permits `--allow-first-legacy-migration`, while `partial_or_unknown` is a hard stop.
- Current deployment metadata is bound to `MEDICAL_AUDIT_DEPLOY_SHA` at app container build/start. Therefore `--skip-app-rebuild` would create split identity between app metadata and the new marker/public manifest; this batch must rebuild the app unless that runtime contract is separately redesigned first.
- Full frontend acceptance currently covers `17` hardened independent routes and `3` aliases at desktop/mobile (`34 + 6` executions). The gate permits screenshot policy `disabled` or `issues`; this conflicts with the plan's all-page screenshot requirement and must be hardened before production use.
- The frontend runner uses fixed identity `frontend-acceptance-admin`, does not bind its report to expected deploy SHA/public manifest and reports provider status from a static contract. Run-specific attribution and runtime-derived release/provider evidence are required before S1→S2 can prove the allowed audit-log delta.
- Verified schema tables needed for prohibited-delta coverage include `query_logs`, `review_tasks`, `review_actions`, `review_comments`, `audit_projects`, `audit_project_members`, `analytics_upload_records`, `document_upload_records`, `document_storage_objects`, `document_upload_governance_jobs`, `audit_agent_invocations` and `audit_log_events`.
- The default permission observation covers only `2` public GET probes and skips `33`; it is L3-limited observation, not a full permission matrix. Full permission and full browser acceptance remain separate L4 `audit-log-only` lanes.

Plan output:

- The active release plan now contains Loop 58 batches D0-D9, exact state transitions, migration/readiness and rollback gates, S0/S1/S2 evidence, command templates, hard stops and an authorization matrix.
- The stale `next Task 1` decision has been replaced with a current `NO-GO`: the next executable work is D0 local evidence-contract implementation after a new instruction, not commit, merge or deploy.
- Direct deploy and `--skip-app-rebuild` are explicitly rejected for the current contract. Exact-SHA deploy remains blocked until the candidate is clean, D0 exists, the Mypy policy is recorded, the full matrix is SHA-bound, and D5 fresh read-only topology is safe.

## 2026-07-16 Loop 58 D0 Implementation Start

- User authorized the next executable item only: D0 local release-evidence contract implementation. Commit, push, PR, Ready, merge, production observation and production mutation remain outside authorization.
- The stable operator workflow to update for D0 is `docs/workflows/workflow-tencent-cloud-audit-deployment-stable.md`; existing frontend-only workflow examples do not yet encode the new S0/S1/S2 release-guard contract.
- D0 implementation is split into two non-overlapping local lanes: a Python release-guard snapshot/compare tool plus focused tests, and Node frontend acceptance/gate hardening plus focused tests. Both lanes are fixture/dry-run only.
- The deploy activation path already checks the basic legacy/versioned filesystem shape, but it is write-path-local and does not emit a reusable pre-deploy topology classification or broad schema/business/object snapshot. The D0 guard must remain consistent with those checks while adding standalone fail-closed capture/compare evidence.
- Existing first-migration rollback code distinguishes a legacy backup by the absence of `web/out/release-manifest.json`; D0 fixture coverage must therefore verify both versioned identity agreement and the legacy restore shape, not treat rollback exit alone as acceptance.
- The twelve allowlisted tables all have UUID `id` primary keys in `sql/knowledge-query-schema.sql`; each has `created_at`, while mutable review/project/member/storage/governance tables also expose `updated_at`. This supports row-count + ordered-PK fingerprint + max relevant timestamp without inventing table-specific identifiers.
- The existing deployment-state auditor provides a safe SSH/remote-Python pattern and already demonstrates `PGOPTIONS="-c default_transaction_read_only=on"` inside `medical_audit_pg`. The new guard can reuse that operational shape without reading or printing `.env` values.
- Integration review found one plan/code semantic conflict: the migration sentinel records the first successful legacy-to-versioned migration SHA and is intentionally not rotated on later versioned deployments. Therefore `versioned_ready` must require a valid non-symlink sentinel as migration-lineage evidence, while exact equality applies to marker/current/release/manifest; requiring sentinel==current SHA would incorrectly block every second versioned deployment.
- Frontend evidence integration must not reduce “valid PNG” to the 8-byte signature; the gate needs structural PNG/IHDR evidence plus hash/dimensions for each independent execution. The public deployment metadata endpoint proves the app deploy SHA but does not expose the Web `current` symlink, so exact current-target evidence must come from the S1 release guard or remain explicitly unverified.
- The S0 collector cannot depend on the new guard script already existing in the production app directory, because S0 runs before that SHA is deployed. The live capture path must stream a self-contained remote collector over strict SSH (`python3 -`) from the clean local candidate.
- The completed frontend lane now consumes a passing S1 guard with exact current target, derives a run-specific audit user, binds public manifest/app deploy metadata before and after the run, and requires fresh, unique, run-bound structural PNG evidence for all `34` independent plus `6` alias executions.
- Stable deployment workflow has a tested single-source rule: `pnpm production:frontend-acceptance --` may appear exactly once in §7.6.1. New D0 arguments must update that canonical command instead of adding another template elsewhere.
- Maximum evidence grade for this phase is `L2-fixture-or-dry-run`; local code/tests cannot establish L3 or L4.
- Completion contract: migration topology and first-migration rollback are fixture-tested; release guard capture/compare is fail-closed; frontend acceptance requires all screenshots, exact deploy/release identity and a unique run identity; focused and relevant broad local gates pass; planning ledgers reflect remaining blockers.
- The release clone has no physical `AGENTS.md`; the repository contract supplied in the active task remains controlling.
- Pre-edit backup: `/Users/pray/.Codex/file-history/medical-audit-loop58-d0-20260716T152243+0800/`.

## 2026-07-16 Loop 58 D0 Closure Findings

- A report-level `provider_call_status=not_called` was initially too broad: the collector can prove only its own command/endpoint boundary. The final contract records global `provider_call_status=not_observed`, `provider_evidence_source=outside-release-guard-scope`, and separate collector `not_called`/zero-attempt evidence.
- A count/fingerprint-only table snapshot could miss balanced or in-place mutations. The final snapshot adds complete canonical row-content fingerprints; `audit_log_events` additionally carries exact IDs and row hashes so S1→S2 can prove the new global ID set exactly equals the run-user ID set and old rows did not change.
- Schema identity now covers columns, constraints, indexes, ACL, RLS flags/policies, triggers and trigger-function definitions. This is materially stronger than a columns-only fingerprint but remains a database-schema observation, not runtime/provider telemetry.
- Runtime topology must be part of S1→S2 immutability. The final contract observes `.deploy-sha.next`, app status/health/deploy SHA, Nginx config and read-only Web mount, then compares full topology evidence rather than only marker/current strings.
- Screenshot freshness requires more than a PNG signature or one file per route. Filenames now bind run/contract/viewport/route/query; the gate requires unique paths for all `40` executions and validates CRC, IDAT decompression, supported color format, exact dimensions and scanline length.
- Anonymous and missing-role API rejection probes still write audit events in L4. They now retain the run-specific `X-User-Id` while omitting the permission field under test, so their events remain attributable without weakening the denial scenario.
- Object-storage proof remains database-ledger-only. The guard fingerprints `document_storage_objects`; it does not list or hash Tencent COS objects, so COS parity must remain an explicit unverified item or a separately authorized observation lane.
- Follow-up adversarial review proved that `observation_scope`, S0→S1 topology direction and `releases/` root shape must be contract fields, not documentation assumptions. The final guard requires `database-ledger`, permits only deploy transitions ending in `versioned_ready`, and rejects symlink/file/other `releases/` roots.
- S1 must be captured for the exact forthcoming L4 run. The frontend loader now requires the same acceptance run ID/user and a zero-event exact-ID baseline; another run's structurally valid S1 report is rejected.
- L3 source binding now includes the configured production host/user, hidden `capture-live` confirmation, strict outer-SSH transport evidence, SSH exit `0`, current collector source hash and an envelope over snapshot+provenance. This is tamper-evident under the controlled operator-workspace model, not an external signed attestation against a malicious local operator.
- Production scope and time are integrity fields: app/Web/PostgreSQL paths cannot be redirected to shadow targets, hidden capture cannot write a remote output file, and `generated_at` is part of the canonical snapshot/envelope validation.
- The production browser target is now inseparable from the SSH guard: runner and gate accept only the exact normalized HTTPS production origin, reject alternate host/scheme/port/userinfo/path/query/fragment, and require the final report URL to match.
- No matching local PostgreSQL container was available at closure. SQL generation, transaction mode and parser behavior are covered by tests, but a real PostgreSQL execution is not part of the current L2 evidence.
- Fresh local result: `40` guard tests, `22` focused frontend tests and `311` combined related tests passed; Ruff, targeted Mypy, Node syntax and diff checks passed. Final independent reviews report `accepted P0/P1=0`, confidence high. Production, SSH, browser L4, audit-log write, provider and deploy evidence remain absent by design.

## 2026-07-16 Loop 58 Phase 3 Initial Decision

- The selected policy is a fail-closed non-regression gate, not bulk repair of `195` historical errors in `10` untouched files.
- The baseline must be derived from the approved base/current candidate comparison and stored as reviewable repository policy or test data; a raw count-only exception is insufficient because errors can be exchanged while the total remains constant.
- Phase 3 completion requires a fresh failing full command retained as historical-debt evidence plus a separate candidate-delta proof showing no newly introduced Mypy diagnostics.
- Local commit authorization is available only after the policy and its tests pass. Push, PR, Ready, merge, deploy and all production/provider/database side effects remain blocked.
- Installed Mypy is `2.1.0`; repository configuration is strict and currently applies `mypy_path = "src"` without an existing baseline/non-regression mechanism.
- The release clone still has no physical `AGENTS.md` or `.codex/context-pack.md`; the task-supplied repository contract remains controlling.
- Candidate comparison against exact base `1376baef0d8d47f1e1ef60b2cec130451af5af4f` confirms the broad release delta and two D0 untracked Python test/tool files; the exception must include untracked paths when determining candidate-touched files.
- Mypy `2.1.0` supports machine-readable `--output=json`; the fresh repository-wide `uv run mypy src scripts --output=json --no-error-summary` run exits `1` as expected for debt evidence. The raw tool output is too large for reliable visual review, so Phase 3 must consume it structurally and hash canonical diagnostics instead of relying on truncated console text.
- Fresh structured current-candidate evidence is exactly `195` diagnostics in `10` files with canonical diagnostic SHA-256 `fd5876c18cd71cd2e316a2c9c9206a59fc5dc1654143fcfb0242d8d5b566e97f`; Mypy exit is `1` and stderr is empty.
- All ten diagnostic-bearing files are byte-for-byte unchanged in `git diff` from exact base `1376baef0d8d47f1e1ef60b2cec130451af5af4f` through the current working tree. This supports classification as inherited debt, but the gate still needs an isolated base run to prove the diagnostic set itself matches the base under the same tool/config.
- An isolated `git archive` run of exact base `1376baef0d8d47f1e1ef60b2cec130451af5af4f`, using the same Mypy `2.1.0` executable and archived `pyproject.toml`, produced the identical `195` diagnostics, identical per-file counts and identical canonical SHA-256 `fd5876c18cd71cd2e316a2c9c9206a59fc5dc1654143fcfb0242d8d5b566e97f`.
- Official Mypy guidance permits per-module suppression for gradual adoption, but this release gate will not alter `strict`, add `ignore_errors`, or add `type: ignore`; it will preserve the full failing command and compare an exact machine-readable baseline. Mypy also documents that the flags implied by `strict` can change across versions, so the baseline must bind the tool version.
- The candidate has four tracked changed Python scripts plus untracked `scripts/audit-production-release-guard-snapshot.py`. A fresh targeted Mypy run across all five reports `Success: no issues found in 5 source files`.
- The formal Loop 58 D1 policy currently says “changed Python files” while D2 says “every changed Python script”; implementation will use the explicit five-script set for Mypy and rely on Ruff/Pytest for changed test files, then synchronize D1 wording to remove ambiguity.
- The implemented gate adds itself to the candidate set, so the final targeted Mypy set contains six scripts, not the five observed before implementation.
- The gate binds exact base SHA, Mypy version, command, exit `1`, global/per-file diagnostic fingerprints, current/base source hashes and unchanged debt-file paths. Any improvement, diagnostic exchange, tool drift or debt-file touch fails closed and requires explicit baseline refresh; it never emits `mypy src scripts PASS`.

## 2026-07-16 Loop 58 Phase 3/4 Closure Findings

- Exact isolated-base and current-candidate Mypy observations match at `195` diagnostics / `10` files / SHA-256 `fd5876c18cd71cd2e316a2c9c9206a59fc5dc1654143fcfb0242d8d5b566e97f`; the repository-wide command still exits `1` and is not a PASS.
- The non-regression gate returns only `allowed-with-label`, while all six candidate-changed Python scripts pass targeted Mypy. Focused tests cover count-preserving diagnostic replacement, diagnostic removal, tool/exit/stderr/ancestry drift, source-hash drift, touched debt files and malformed JSON.
- Atomic commit 1 `0d34a94` contains only the ten evidence/tool/test/workflow files. Atomic commit 2 `85859a6` contains only the eight UI/chrome/mobile files. The final planning manifest contains only the three `.kiro` ledgers, formal plan and atomic commit plan.
- All staged groups passed exact manifest, cached check and refined added-content secret scans. Ignored output, `tmp/`, screenshots, SQLite, build output and caches remained untracked/unstaged.
- Phase 5 remains the next local evidence gate: clean exact-SHA full local gates, release manifest and SHA-bound three-viewport route matrix. Push, PR, Ready, merge and all production/provider/database actions remain blocked.

## 2026-07-16 Loop 59 Final Sprint Production Audit — Initial Findings

- User requested a fresh deployment recommendation plus production investigation of knowledge-base access, 100+ agents, and all-page visual consistency/professionalism before the final sprint plan is approved.
- Current candidate is `codex/production-ui-reconciliation-20260716@846aa89187867339feb6d6c90c102ca1336e4105`; its upstream ref is identical and Draft PR `#239` remains the promotion vehicle. The candidate has fresh exact-SHA L2 evidence but has not been merged or deployed.
- The release worktree has no tracked or staged delta at audit start. Unexpected helper-generated untracked `.claude/`, `AGENTS.md`, and `CLAUDE.md` remain outside scope and must not be read, modified, staged, or deleted.
- The primary `/Users/pray/project/medical_audit` worktree contains extensive user-owned changes and artifacts, so this audit will use the isolated release worktree and will not touch the primary dirty tree.
- Evidence gate: public/browser and strict SSH/SQL observations may reach `L3-production-read-only`; they cannot prove the unmerged candidate is deployed. Any audit route that writes audit logs is L4 and remains excluded unless separately authorized.
- Deployment decision is initially `blocked-pending-fresh-L3`: first establish current deployed SHA/topology, knowledge/index availability, actual agent catalog/inventory counts and page-level production visual findings.
- `planning-with-files/references/planning-rules.md` is absent from the installed skill package. The audit follows the fully read `SKILL.md`, including plan restoration, two-action findings updates, phase logging, and fail-closed handling of failed commands.
- Pre-edit planning-file backup artifact: `medical-audit-loop59-final-sprint-20260716T234356+0800` (operator-local location intentionally omitted).
- Production contract review confirms `run-production-frontend-acceptance.mjs` is not read-only: its complete flow can write audit-log records and requires explicit `--allow-audit-log-writes` plus production confirmation. It is excluded from the current L3 audit.
- `audit-production-release-guard-snapshot.py capture` is the preferred fresh L3 path because it streams the current collector over strict SSH, uses `SERIALIZABLE READ ONLY DEFERRABLE`, fingerprints schema/business tables, and does not rely on the older production checkout containing the new script.
- `audit-tencent-cloud-deployment-state.py` is only conditionally L3: it must prove global audit snapshot unchanged and unique auditor identity zero events. A failing/auth-denied path cannot be assumed read-only.
- The release guard covers the knowledge database ledger and `audit_agent_invocations`, but its current fixed table list does not include `audit_agents`; a separate strict read-only SQL query is required to prove actual production agent inventory and whether “100+” means persisted agents, version-controlled market templates, or only UI catalog cards.
- Public `/api/v1/knowledge-base/catalog` is documented as GET-only with `database_write=false` and provider not called, making it an appropriate direct knowledge-backend observation alongside SSH database evidence.
- The existing latest artifacts show production-related runs against `main@1376bae` on 2026-07-16, but they are historical leads only. Fresh public and SSH observations are still required before any deployment recommendation.
- Operator credential readiness was verified locally; workstation path and file metadata are intentionally omitted, and credential content was not read.
- Fresh public front-door observation: `/health`, `/knowledge-base`, and `/agent-market` all returned HTTP `200` over HTTPS. This proves route availability only, not backend knowledge retrieval or agent execution.
- The first direct catalog GET without tenant context returned `401` with `X-Tenant-Id header is required`. Because an authentication-denied path may write an audit event, this attempt cannot be labeled proven zero-write; it is recorded as `database_write=unknown` pending strict SSH audit evidence. The same unauthenticated request will not be repeated.
- Public `/release-manifest.json` did not parse as JSON. This is consistent with the current production generation predating the candidate's versioned release-manifest contract, but the exact HTTP status/topology still requires a static status check plus SSH release-guard capture.
- The release-manifest `jq` command exited `5`; no retry with the same assumption will be made. The next check will separate HTTP metadata from body parsing.
- Static metadata check resolved the manifest ambiguity: production `/release-manifest.json` returns HTTP `200 text/html`, `6947` bytes, not the candidate's JSON manifest. This is an HTML fallback and proves the current production static topology is still pre-versioned/legacy from the candidate's perspective.
- The freshest prior conditional-L3 report (2026-07-16 02:29 CST) observed production at `1376baef0d8d47f1e1ef60b2cec130451af5af4f`, all relevant containers healthy, Nginx/front door healthy, PostgreSQL search ready, and `49,051` matching embeddings with audit snapshot delta `0`. It remains historical until refreshed now.
- The freshest prior L3 smoke intentionally skipped query/citation/chat export because they require production write/provider authorization. Therefore it proves backend readiness, not end-to-end knowledge answer quality.
- The freshest prior full frontend acceptance was L4 `audit-log-only`, covered `18` routes / `36` desktop-mobile checks and had no P0/P1. Its screenshot policy was `all_issues`, not an all-route visual corpus, so it does not answer the user's current all-page professional-layout question.
- Current production route HTML contains the login shell and client-side auth gate even on `/knowledge-base`; HTTP `200` alone can therefore hide whether the authenticated workbench/backend is usable.
- Fresh S0 release-guard capture failed before any database snapshot with remote `Python 3.10` error: `ImportError: cannot import name 'UTC' from 'datetime' (/usr/lib/python3.10/datetime.py)`. The candidate collector imports `datetime.UTC`, which requires Python 3.11+, while the production host executes the streamed collector with Python 3.10.
- This is a real deployment-readiness P1: the mandatory first-migration S0 guard cannot run in the actual production interpreter. The failed command opened SSH and started Python but did not reach collector/database logic; no production mutation was requested. It will not be retried unchanged.
- Next evidence path changes to the already production-compatible conditional-L3 deployment-state auditor for current health/knowledge evidence, while the final sprint must replace `datetime.UTC` with a Python-3.10-compatible timezone contract and add a 3.10 compatibility gate before deployment.
- Fresh conditional-L3 deployment-state audit completed with `database_write=false`, audit-log count/fingerprint unchanged (`56,347` rows before/after), unique auditor event count `0→0`, `provider_call_status=not_called`, and GET-only HTTP scope.
- Runtime health is currently good at deployed marker `1376baef0d8d47f1e1ef60b2cec130451af5af4f`: app/PostgreSQL/ClamAV/Nginx containers healthy, Nginx config valid, front door healthy, read-only Web mount present, and the knowledge catalog reports PostgreSQL ready with `49,051` matching 1024-dimensional embeddings.
- The audit overall status is `fail`, not pass, because the candidate's hardened auditor requires versioned-release integrity while production is still legacy: no `current` release target, no JSON manifest, no manifest file set, no versioned Nginx release route, old HTML cache policy, and no verifiable immutable static asset path.
- This failure is expected evidence of first-migration readiness work still being required; it must not be described as current production outage. Public pages and backend health are available, but release integrity for the next deploy is unproven.
- Fresh L3 report paths: `tmp/outputs/tencent-cloud-deployment-state-loop59-final-audit-20260716T235500+0800.json` and `.md` counterpart.
- The “100+ agents” claim is currently contradicted by the candidate source contract. The raw prompt spreadsheet export contains `169` rows / `132` unique category-title pairs, but it is source material, not an enabled agent catalog.
- The actual version-controlled market catalog exports exactly `3` backend-aligned medical agents by default. An opt-in extension flag adds only `3` individually approved validation agents, for a maximum current UI catalog of `6`; tests explicitly enforce these counts.
- Production persisted-agent count and invocation coverage still require strict read-only SQL. Even if the database has custom rows, the present UI/build contract does not expose 100+ approved agents, so “100+ agents are operating normally in production” is already unsupported and must be treated as a product/data activation gap rather than a health check pass.
- Agent GET/detail/invocation endpoints record operations, so API-based enumeration is not eligible for the current zero-write audit. Database inventory will be used instead.
- Fresh strict PostgreSQL inventory ran inside `SERIALIZABLE READ ONLY DEFERRABLE` with `transaction_read_only=on` and exited `0`.
- Production contains `304` persisted `audit_agents`: `13 active`, `21 inactive`, and `270 archived`; categories are `303` business and `1` research. This is historical inventory, not 304 currently usable agents.
- All `13` active persisted rows have `source=agent-market`; they reference only `7` distinct template IDs. The other `291` rows are inactive/archived, including one archived production smoke agent.
- Production has `1,707` recorded invocations across only `7` agent keys. Three default agents account for `1,601` invocations, one older custom agent for `103`, and three other custom agents for one invocation each. Latest recorded invocation is `2026-07-09 03:11:54+00`.
- Current evidence therefore rejects “100+ agents are all operating normally in production.” The database has 100+ historical rows, but only 13 active market installations, 7 distinct template IDs, and 7 ever-invoked agent keys. Identity-level duplicate analysis is still needed before classifying the 13/7 gap as a defect rather than legitimate per-user/project installs.
- Identity-level read-only aggregation confirms an actual duplicate problem: the 13 active rows collapse to 7 actor/project/template identity groups; 3 groups contain duplicates, with 6 excess rows and a maximum group size of 4. The candidate idempotency fix prevents/reports this shape but does not clean existing production rows.
- Knowledge coverage SQL also ran in `SERIALIZABLE READ ONLY DEFERRABLE` with `transaction_read_only=on`. Only `5` source collections currently contain documents/embeddings: `medical-insurance-laws`, `supervision-rules-knowledge`, `medical-insurance-catalog`, `risk-negative-list`, and `personal-materials`.
- Those five collections contain `20,054` documents, `923,288` chunks/embeddings in the historical database, but only `49,055` embeddings are attached to active index versions. The runtime catalog reports `49,051` matching search embeddings; the four-row difference aligns with the isolated personal-material collection and should not be called a mismatch without a retrieval-scope check.
- The code registry defines `25` source collections, so `20` registered policy/management/other collections have no production rows. “All knowledge bases are accessible and normal” is therefore unsupported: the active medical core is ready, but broad registry coverage is incomplete, and end-to-end answer/citation quality has not been exercised because that path writes query history and may invoke a provider.
- The same-SHA production L4 acceptance from 2026-07-16 02:29 covered all 18 production routes at desktop/mobile: every navigation returned `200`, no navigation/console/request/interaction failures were recorded, and all 36 checks reported zero horizontal overflow and no P0/P1.
- That report captured screenshots only for issues, and there were no issues; it therefore proves mechanical route/layout invariants but cannot support a qualitative claim that every page is visually consistent or professionally polished.
- A new authenticated production all-page capture would cause audit-log writes and remains outside the current L3 authorization. The safe visual fallback is a real-browser static-structure matrix that injects only localStorage auth and blocks all `/api/v1/**` requests, then combines its screenshots with the live same-SHA route metrics. This can grade shell/layout professionalism but not data-populated interaction quality.
- The safe Playwright fallback completed 20 routes × 3 viewports = 60 executions. All navigations were 200 with no root horizontal overflow, missing heading, short body or page error; 249 console errors came from the intentionally intercepted API requests and are not production backend failures.
- Mobile `/medical-audit`, including aliases landing there, has nested-tab clipping that root-level overflow checks miss: tab button right edges reached `394`, `490`, `586` and `682` at a `390` px viewport. Component-level bounding-box/internal-scroll assertions are required.
- Mobile global navigation consumes roughly 350–420 px before route content. `/archive` is approximately 5,240 px high and visibly compressed; `/guided-check` is about 4,745 px and `/knowledge-base` about 3,338 px. Floating history controls also overlap route content on several mobile pages.
- Desktop visual language is coherent, but `/medical-audit` uses three concurrent navigation layers and leaves only about 812 px of a 1440 px viewport for the working canvas. Main content left/width patterns also diverge across standard, rules, medical-audit and chat layouts.
- Archive, analytics, graph and reports expose internal English roles, paths, provider flags or raw API/error text. Empty/degraded states are structurally consistent but not final-polish professional.
- Final visual verdict: desktop structural consistency is an acceptable candidate baseline; mobile professional readiness is NO-GO; data-populated authenticated quality remains unverified until separately authorized L4 acceptance.
- Final deploy verdict is NO-GO. There is no current P0 outage, but P1 closure is required for Python 3.10 S0 compatibility, legacy migration readiness, active-agent duplicate governance, mobile clipping/overlap/readability and the declared knowledge-coverage scope.
- The final sprint is frozen as Batch A-H in `drafts/analysis/loop59-final-sprint-production-readiness-plan-draft-20260716.md`; next work is local P1 closure, not Ready/merge/deploy.
- Batch A code search confirms the production compatibility failure is narrow and reproducible: `scripts/audit-production-release-guard-snapshot.py` imports `datetime.UTC` and uses it only for `datetime.now(UTC)`; the collector otherwise avoids a Python 3.11-only syntax requirement in the inspected path.
- The production acceptance runner already enumerates element-level overflow offenders, but issue classification still promotes only root `horizontalOverflow`. The detector must separately fail on clipped/off-viewport interactive controls and overlay intersections.
- Existing E2E tests already use `boundingBox()` for shell/history geometry, providing a project-local pattern for component-level mobile layout assertions rather than introducing a new browser dependency.
- `/archive` actually renders `ReplicaArchiveWorkbench`, not the older `ArchiveWorkbench` compatibility component. Mobile archive fixes and user-facing copy must target `web/src/components/replica/replica-archive-workbench.tsx` plus its shared record/panel CSS.
- `/medical-audit` contains two tab layers: top-level `.replica-medical-tabs` and rule-filter `.replica-medical-rule-tabs`. The observed `394/490/586/682` right edges align with the rule-filter buttons, so a wrap/grid mobile contract is preferable to clipping or silently relying on horizontal scroll.
- The shell history control is a fixed `.replica-history-fab`, while the route content lives underneath the shared workspace. The fix should reserve mobile bottom space and reposition/compact the control instead of hiding the feature.
- The current `max-width: 560px` contract explicitly sets both medical tab rows to `overflow-x:auto` with `min-width:96px` buttons. This creates the observed off-viewport controls by design; Batch A will replace that rule with full-width grids/wrapping at phone width.
- Late official visual overrides enlarge the medical icon rail/rules columns on desktop (`88px + 284px`), explaining the cramped 1440px work area. The P1 mobile fix can remain narrow; desktop rail consolidation is retained as P2 unless it blocks the exact-SHA visual review.
- Archive/analytics/report expose backend boundary fields directly in primary content. The established fail-closed semantics can be preserved while moving raw backend/flag values into an optional diagnostics disclosure and presenting Chinese user-facing status text by default.
- Agent cleanup cannot safely mean “archive duplicate rows only”: `_find_market_agent_install` matches actor/project/template across all statuses, so archived duplicates would still keep the identity ambiguous. The dry-run manifest must explicitly propose one survivor plus identity detachment for non-survivors, while preserving rows/invocations for audit history; actual mutation remains a later L4 database lane.
- A deterministic survivor policy can be reviewed without writes: prefer the row with the most invocations, then the newest `updated_at`, newest `created_at`, and stable `agent_key` tie-break. The report must expose the policy and every candidate, not emit executable UPDATE/DELETE SQL.
- Knowledge UI already receives registry counts and per-item document/chunk metrics. Batch A can freeze the release claim to `core-5` while displaying dynamic `populated / registered` coverage and an explicit partial-coverage label; it must not hardcode `5/25` as a runtime fact.
- The workstation has a real Python `3.10.19` at `/opt/homebrew/opt/python@3.10/bin/python3.10`, resolved through `uv python find 3.10`. The new regression executes the full fixture `capture` CLI under that interpreter, so it covers import, timestamp generation, argument handling, snapshot normalization and report emission rather than a source-text approximation.
- Ruff `UP017` assumes the repository's Python 3.12 floor and therefore conflicts with this intentionally streamed-to-Python-3.10 operator script. A local `UTC_TIMEZONE = timezone.utc` compatibility constant avoids suppressing Ruff globally or weakening the project Python requirement.
- Because Ruff applies `UP017` at the `timezone.utc` assignment too, this production compatibility boundary needs an explicit one-line exception with rationale. That preserves full linting everywhere else and makes the Python 3.10 exception reviewable.
- The final compatibility form is `UTC_TIMEZONE = timezone.utc` with a one-line `UP017` rationale, used by `datetime.now(UTC_TIMEZONE)`. It passed the real Python 3.10 CLI capture, Ruff and targeted Mypy without changing the repository-wide `requires-python >=3.12` policy.
- Candidate code already positions the mobile history control inside the brand header and has an existing geometry E2E contract. The production overlap came from the older deployed SHA; Batch A should verify this candidate behavior rather than add a redundant shell rewrite.
- The phone-specific `.replica-main-nav` override reduces navigation from three to two columns, causing the 6-row/large-first-fold mobile header. Keeping three columns at 390px is the narrow fix because the existing icon+Chinese labels fit the available cell width.
- Production acceptance still defines only desktop/mobile and a 40-execution signed evidence contract. Changing that to 60 is a broader Batch B evidence-contract migration touching runner, gate, workflow and screenshot fixtures; Batch A will first add component overflow/occlusion classification without silently changing the current signed count.
- The new detector test reproduces the exact false-negative shape: `horizontalOverflow=false` while an interactive button ends at x=682 in a 390px viewport, plus a floating control covering a route control. Current classification returns `[]`, proving the gate gap before implementation.
- The hardened detector now independently emits P1 `interactive-control-overflow` and `floating-control-occlusion`. Report evidence is sanitized to tag/geometry only, avoiding control text, selectors or sensitive route content in acceptance JSON.
- The archive component can preserve operational evidence without exposing it as primary copy: user-facing cards now lead with project, archive/report number and Chinese state; raw IDs, storage roots, hashes and backend flags remain available under explicit diagnostic disclosures.
- `ReplicaAdapterIssue` exposes `surface`, `code`, `message` and optional `status`; it has no `read` field. Graph diagnostic list identity should bind `issue.code + index` while the raw message stays inside the disclosure.
- The candidate's market-install lookup includes all statuses, not only active rows. The duplicate inventory SQL and analyzer must therefore collect every `source=agent-market` row and distinguish `active_duplicate_group_count` from all-status `ambiguous_identity_group_count`; otherwise a cleanup could leave archived ambiguity behind.
- The dry-run report intentionally documents identity field names but hashes actor/project values. Privacy validation must assert fixture values such as `director-1` and the project name are absent, not forbid the literal schema key `created_by` in the policy contract.
- The implemented survivor policy now explicitly prefers an active installation before invocation count and timestamps. This avoids choosing an archived row when a usable active row exists; any non-survivor action remains `detach-market-identity-and-archive`, with row and invocation history preserved.
- Knowledge release scope is now `core-5`, not `full-25`. Runtime UI derives populated and registered counts from catalog metrics, marks unknown metrics as unknown, and explicitly says the current release does not promise full registry coverage.
- CSS cascade review found no later rule that restores the removed two-column phone navigation or horizontally scrolling medical tabs. The late official navigation override adjusts spacing only, so the Batch A three-column/grid contracts remain effective at `390px`.
- A fresh `git diff --check` passed after the implementation set; no whitespace error is present before broad regression.
- The first broad backend/static pass found one formatting-only Ruff `E501` in the new detector regression; release-guard/duplicate tests, targeted Mypy and Node syntax were already green. The long JavaScript fixture string is split without changing the asserted behavior.
- The first real-browser phone check found a second floating control not covered by the original production observation: `.replica-medical-ai-fab` intersected the first medical view tabs at `390×900`. The root and new tab geometry were otherwise green. The assistant action is therefore moved into the medical main flow at tablet/phone widths and registered with the same occlusion detector instead of accepting an unmeasured overlay.
- Detector revalidation exposed a clipped-DOM false positive: an offscreen rule button inside the `max-height` rules scroller still has a bounding box even though it is not painted in the viewport. The occlusion lane now treats only `fixed`, `absolute` and `sticky` marked elements as floating; the responsive medical assistant is `static`, while its desktop fixed form remains audited.
- One combined patch for the detector helper, test and ledgers was rejected before writing because a function-context hunk was too broad. It was split into narrow script, export and test/ledger patches; no partial edit from the rejected form was retained.
- The first 60-execution local matrix reported positioned-control occlusions on eight viewport/route pairs. A direct desktop reproduction proved the cause: the shell history FAB remained fixed outside the sidebar and, on `/medical-audit`, directly intersected the fixed medical AI button. The history trigger is now owned by the navigation rail: bottom-aligned inside the desktop sidebar and inside the mobile brand header, never over route content.
- Manual review of the first post-fix desktop screenshot caught a chrome-only collision the route detector intentionally does not classify: both the history trigger and the medical-topic entry used sidebar `bottom:18px`. The history trigger is now placed 86px above the topic entry, with a collapsed-sidebar icon-only contract; this must be browser-rechecked before closure.
- Expanded/collapsed browser measurement then found a pre-existing late-cascade defect: clicking “收起侧栏” hid labels but the official `.replica-app-shell` rule kept the rail at 256px instead of 92px. A final high-specificity collapsed-shell grid contract restores the intended 92px width; geometry must be remeasured.
- Final CSS review scopes the 92px collapsed grid to `min-width:901px`; otherwise a desktop-collapsed state preserved across a resize could override the one-column mobile shell. Mobile continues to use the existing one-column contract.
- Final browser geometry confirms the collapsed rail is exactly `92px`; the history trigger is icon-only with `clientWidth=scrollWidth=65`, history/topic gap is `12px`, and overlap is false. The final post-edit route matrix is again `60/60` across `1440×1100`, `1280×800` and `390×900`.
- The matrix intentionally blocks `/api/v1/**` and therefore proves static shell/route/error-state layout only. Its local proxy/console failures are expected harness effects, not production backend observations; populated authenticated professionalism remains a separate exact-SHA/L4 lane.
- Batch A can close at `L2-fixture-or-dry-run` with local accepted P0/P1=`0` for its defined contracts. It cannot change the production verdict because production still runs the legacy SHA and no repaired Python 3.10 S0, deploy, L3 or L4 run was executed.
- Final boundary audit is clean: tracked added-content secret candidates `0`, scoped untracked secret candidates `0`, generated agent inventory SQL write-statement candidates `0`, strict `SERIALIZABLE READ ONLY DEFERRABLE` plus `transaction_read_only` contract present, index empty and `git diff --check` green.
- The owner explicitly authorized the next executable item, so Batch A may now be frozen as local atomic commits while push, PR state changes, merge, SSH, deploy and all production/provider/database side effects remain excluded.
- Atomic freeze group 1 is `02256fe` with exactly six audit-tool/test files. Its staged secret scan was `0`; the 319-test related path exited `0`, and focused Ruff, targeted Mypy, Node syntax and cached diff checks passed.
- Atomic freeze group 2 is `1c2d0e4` with exactly fourteen UI/test files. Its staged secret scan was `0`; `38` Vitest files / `363` tests, Web typecheck, lint and cached diff checks passed.
- The physical workspace still contains helper-generated untracked `.claude/`, `.playwright-cli/`, root `AGENTS.md` and `CLAUDE.md`. Exact-SHA Batch B must therefore execute from an isolated clean source export and must not call the primary dirty tree clean.
- Three browser-harness assumptions failed once and were replaced rather than repeated: `run-code` requires a `(page) =>` function, `routeCheckProfiles` is keyed by profile rather than an array, and the CLI function sandbox does not expose Node's `URL`; the matrix now reads `location.pathname` inside the page.

## 2026-07-17 Loop 59 Batch B Exact-SHA Closure Findings

- The final local candidate is `a3407a4b44766733c294d394181df3e64bb5f9b6`, six commits ahead of the current remote branch. It contains a 25-file candidate diff; helper-generated `.claude/`, `.playwright-cli/`, root `AGENTS.md` and `CLAUDE.md` remain untouched and untracked.
- Final B1 ran from an isolated detached clean clone. Backend reports `854 passed` with one existing Starlette/httpx deprecation warning; Web reports `38` files / `364` tests; typecheck, lint, full Ruff, Node syntax and `git diff --check` pass.
- Repository-wide Mypy debt is not renamed as a pass. The exact non-regression gate returns `allowed-with-label`, historical diagnostics remain `195` with SHA-256 `fd5876c18cd71cd2e316a2c9c9206a59fc5dc1654143fcfb0242d8d5b566e97f`, and candidate-changed Python scripts pass targeted Mypy.
- Final B2 release export contains 24 generated pages. The actual deploy validator accepts an 87-file manifest bound to `a3407a4b...`; manifest SHA-256 is `3cc15e4ed8a5eedbbf9c7a489b4658923e64b1a3a17df64c773242399798d265`, Node is `v22.22.0`, pnpm is `9.15.0`, all four public build variables are null, and the favicon contract points to `/brand/auditscope-logo.png`.
- Final B3 is green at desktop/tablet/mobile `20/20` each for 17 independent routes plus 3 aliases. There are 60 unique screenshot paths and 60 unique byte hashes at exact dimensions `1440×1100`, `1280×800` and `390×900`; root overflow, interactive overflow, floating-control occlusion, alias-path, heading and thin-body failures are all empty.
- The final harness intercepts `**/api/**`, not only `/api/v1/**`. All `270` captured console errors are attributable to this local 503 fixture; unexpected console errors and page errors are both empty. This is local static/error-state evidence, not production backend evidence.
- Contact-sheet and key-page review produce a final visual verdict of `92/100`, `pass`, accepted P0/P1=`0`. The responsive shell, mobile medical tools, archive/report empty states and cross-page hierarchy are coherent enough for PR promotion; authenticated populated production visual acceptance remains unproven.
- A visible-text scan across 16 primary routes initially found one raw endpoint on `/medical-audit`: `读取 /api/v1/audit-findings`. The final two-file commit `a3407a4` replaces primary metric implementation/API text with user-facing sync states while keeping the actual backend failure inside the existing collapsed diagnostic disclosure; focused test is `6/6` and the final visible scan is `0`.
- The first focused test after that copy change failed because an old assertion still required `SqlAlchemyAuditFindingStore` to be visible. The contract was corrected to require the three user-facing sync labels and forbid the implementation name in primary content; the same test then passed. No production behavior was exercised.
- One direct Playwright `run-code` attempt used top-level statements and returned `SyntaxError: Unexpected token 'const'`. Inspection of the installed CLI contract showed that `run-code` requires an async `(page) =>` function; the repeat used the documented function-file form and completed successfully.
- Earlier Batch B retries also exposed three tooling-only assumptions that were corrected once: the deploy validator dynamic import must register its module in `sys.modules`; contact-sheet generation must use system Python with PIL rather than the project `uv` environment; and API interception must cover `/api/backend/**` as well as `/api/v1/**`.
- Exact candidate evidence is L2 only. The production marker remains the legacy `1376baef...`; no push, Draft PR update, Ready, merge, SSH, fresh S0, deploy, production/database/object write, provider call or live send occurred during Batch B.
- Boundary: `production unchanged`, `deploy_execution=false`, `database_write=false`, `provider_attempt_made=false`, `provider_call_status=not_observed`, `live_send=false`.

## 2026-07-17 Loop 59 Batch C1 Draft PR Promotion Findings

- Exact candidate `a3407a4b44766733c294d394181df3e64bb5f9b6` is now the remote head of `codex/production-ui-reconciliation-20260716`; the push was a normal fast-forward from `846aa89187867339feb6d6c90c102ca1336e4105`.
- PR #239 remains `OPEN` and Draft after the body update. Fresh GitHub state reports base=`main`, head exact match, mergeable=`MERGEABLE`, merge state=`CLEAN`, CodeRabbit=`SUCCESS`, and no review decision.
- There are no repository-native `.github/workflows`, so the external CodeRabbit success cannot establish full test/CI coverage or replace independent review.
- The PR body now preserves the L2 ceiling and explicitly separates Ready, merge, S0/preflight, deploy, L3/L4 acceptance, database cleanup, knowledge activation and provider-backed UAT.
- A JavaScript wrapper syntax error occurred before the first `apply_patch` call because unescaped Markdown backticks terminated the template literal. No file or PR change occurred in that failed attempt; the corrected string-array patch was verified before the authorized GitHub edit.
- Batch C1 does not change the deploy verdict: `NO-GO` remains until independent review, Ready/merge gates, clean-main S0 and first-migration preflight are completed under their own authorization.
- Boundary: GitHub branch push and Draft PR body update executed; `production unchanged`, `deploy_execution=false`, `database_write=false`, `provider_attempt_made=false`, `provider_call_status=not_observed`, `live_send=false`.

## 2026-07-17 Loop 59 Batch C2 Independent Review Findings

- The exact review target must be the detached clean candidate, not the primary dirty ledger worktree; otherwise post-candidate planning changes would contaminate the PR review scope.
- In this environment, a plain `codex review --base origin/main` can recursively activate the `codex-review` skill inside the reviewer. The observed process tree reached three nested Codex review groups, so the run was terminated and cannot count as accepted/clean review evidence.
- The interrupted reviewer had inspected agent-install identity, personal-material permissions, release smoke redirects, versioned Nginx root and knowledge core-5 coverage, and its focused 53-test command passed. No final finding list was emitted before termination.
- The invalid recursive run is retained only as tooling history. A clean C2 result required a non-recursive isolated reviewer plus manual verification of every emitted finding.
- The isolated reviewer finding is valid: Nginx compares the complete multipart request body to `client_max_body_size`, while the browser/backend 20 MiB constants apply only to the file payload. Exact-boundary files therefore need proxy envelope headroom.
- The chosen fix is at the correct ownership boundary: Nginx allows `21m`, while both UI and backend retain the intended 20 MiB file limit. This avoids weakening the application payload policy and gives 1 MiB for multipart headers/boundaries.
- The P2 fix was committed atomically as local candidate `ce639ae1959bfb0a59a4f0ebc4ddd2e50f374712`. Fresh exact-SHA evidence is green: Pytest JUnit reports `854` tests / `0` failures / `0` errors / `0` skips; Web reports `38` files / `364` tests; Ruff, `mypy src`, Web typecheck and lint pass.
- The exact Mypy non-regression gate remains `allowed-with-label`: `195` inherited diagnostics, fingerprint `fd5876c18cd71cd2e316a2c9c9206a59fc5dc1654143fcfb0242d8d5b566e97f`, targeted changed scripts pass, and `mypy_full_pass=false` remains explicit.
- The 24-page release build and actual deploy validator accept an 87-file manifest bound to `ce639ae...`; manifest SHA-256=`eba2f4b464f70aecaad6f4f413839cf4e7a88e971bbd173e77804142cb7fa1b7`.
- The final isolated non-recursive Codex review exited `0` and reported no discrete actionable correctness issue. C2 local review/remediation is complete with accepted P0/P1/P2=`0` after the fix.
- GitHub remains unchanged: remote branch and Draft PR #239 still point to `a3407a4...`, while local branch is one commit ahead. The fix is not part of the PR until a separately gated push/PR refresh occurs; current production remains unchanged.
- Boundary: `production unchanged`, `deploy_execution=false`, `database_write=false`, `provider_attempt_made=false`, `provider_call_status=not_observed`, `live_send=false`.

## 2026-07-17 Loop 59 Batch C2 Exact-SHA Visual Refresh Findings

- The next safe local evidence gap is explicit in the plan: the 60-route structural matrix is still bound to `a3407a4...`, while the reviewed local candidate is `ce639ae...`.
- `tmp/loop59-c2-ce639ae` is a clean detached clone at exact SHA `ce639ae1959bfb0a59a4f0ebc4ddd2e50f374712`; `npx` is available through Node `v22.22.0`.
- The old Batch B artifact directory retains 60 screenshots and three contact sheets, but its temporary matrix harness/report is not a committed release artifact. The exact-SHA refresh must reconstruct the runner from the current acceptance contract and keep all new files under `tmp/loop59-c2-ce639ae/output/playwright/`.
- The optional `planning-with-files` reference `references/planning-rules.md` is absent from the installed skill package. The fully read main `SKILL.md` remains usable; this is a tooling-documentation gap, not a product or release blocker.
- Evidence ceiling remains `L2-fixture-or-dry-run`; production APIs must be locally intercepted and no GitHub or production state may change during this refresh.
- The committed acceptance module exports `routeCheckProfiles`, `aliasRouteChecks`, `classify`, `screenshotFileName` and viewport metadata, but its executable path intentionally refuses local targets because full production acceptance is an L4 audit-log-writing flow. Reusing its CLI entrypoint would violate the evidence boundary.
- The safe local path is Playwright CLI with a named isolated session: serve the already validated `web/out`, mock `**/api/**` to a deterministic local 503 fixture, seed only the two workspace localStorage keys used by the app, import the committed route contracts/classifier into a temporary runner, and capture all 20 contracts at desktop/tablet/mobile.
- The runner must add the local-only `1280×800` tablet viewport because the production acceptance module exports only desktop/mobile. It must record path/search identity, chrome title, body/heading/control semantics, root and interactive overflow, nested medical-tab geometry, positioned-control occlusion, console/page errors, screenshot dimensions and SHA-256.
- The local clean-URL server pilot is valid: `GET /login` returned `200`, the exported HTML contains `登录工作台`, and the CLI browser observed `/login`, the correct heading, `clientWidth=scrollWidth=390` at the mobile viewport.
- The named Playwright session accepted the deterministic `**/api/**` 503 route. This proves the CLI/session/mock primitives needed for the full matrix without opening the production L4 runner.
- One CLI VM probe attempted to dynamically import the committed acceptance module and failed with `ERR_VM_DYNAMIC_IMPORT_CALLBACK_MISSING`. The same approach will not be retried. Contracts will instead be serialized to plain runner data and independently fingerprinted from the committed exports with normal Node outside the VM.
- The generated temporary runner is syntax-valid and contains exactly 20 route definitions. Normal Node serialized the committed contract as `17 independent + 3 aliases`, route order matched the runner, and the contract fingerprint is `164b6aae2773e6bb2c5e24da8e07009a461cdc839d763c5a831f3502369e81c9`.
- Playwright CLI `--raw` returns the function result as direct JSON, so the full report can be captured mechanically without parsing dashboard prose or reading helper-owned `.playwright-cli/` artifacts.
- The first full runner execution is invalid as acceptance evidence: it reported 57 semantic failures and only 7 unique screenshot hashes because `serve -s` returned `web/out/index.html` for every clean URL. Direct proof: `/medical-audit` response SHA-256 equaled `index.html` (`7489546e...`) instead of `medical-audit.html` (`17785a4f...`), and the sampled `/medical-audit` screenshot visibly showed the login page.
- This is a harness/server routing failure, not a 19-page product regression. The invalid report/screenshots must be retained with an explicit invalid label, and the rerun must use clean-URL static serving without SPA fallback.
- The corrected server initially received one readiness-race curl before its listener was ready; the retry waited for startup and then proved `/medical-audit` bytes exactly equal `web/out/medical-audit.html` (`17785a4f...`) with `Content-Disposition: medical-audit.html`.
- Corrected-mode browser pilot is green at mobile: HTTP `200`, path `/medical-audit`, heading `医保审计`, expected body text present, chrome title `医保审计专题`, and root width `390/390`. The full rerun is now authorized within the local L2 boundary.
- The corrected full run produced real page evidence: geometry/P0 browser layers are green, but the success-only committed semantics flagged `/reports` and `/archive` at all three viewports under the deliberate API 503 fixture.
- Source and focused tests prove both observed states are intentional fail-closed product behavior: reports renders `报表工作台读取失败，请稍后重试。`; archive renders `归档工作台暂不可用` plus `归档 API 读取失败，页面不会注入本地样例或旧数据。` The candidate has no `web/` diff from `a3407a4...`, so this is not a C2 UI regression.
- For this local API-blocked matrix only, the temporary runner now accepts either the committed success-state semantics or those two explicit tested error states. This extension is labeled in the report and does not alter or weaken the L4 production acceptance contract.
- The one duplicate screenshot hash is expected and explainable: tablet `/workspace` redirects to `/chat`, producing the same rendered state as tablet `/chat`; 60 unique paths remain present.
- Focused mobile verification of the fixture extensions is green: both routes returned HTTP `200` at their expected paths, reports exposed both the explicit read-failure and retry copy, archive exposed both the fail-closed title and no-fixture detail, and neither page had root overflow.
- User clarified visual priority: desktop web is the primary acceptance surface; phone mobile is secondary, and tablet is supplemental.
- Desktop-first manual review rejects the initial `92/pass` visual conclusion. `/analytics` exposes the raw implementation flag `analytics store ready` in primary content; `/knowledge-base` exposes `后端目录`; `/medical-audit` exposes `专题接口暂不可用` and `疑点接口读取异常`; `/archive` exposes `归档 API 读取失败`.
- These are professional-copy P2 findings, not geometry failures. Raw provider/API/backend details may remain only under collapsed diagnostics; primary hospital-user copy must be localized before visual acceptance can return above the 90-point threshold.
- The exact 17-route desktop visible-text scan reported 6 strings on 4 routes and no visible leak from closed diagnostic disclosures. This confirms the remediation boundary is primary copy, not removal of evidence/debug detail.
- Source review found three additional primary-state variants that the single 503 browser snapshot did not exercise: medical-audit loading copy, dashboard recovery copy and organization fallback also used `接口`. They belong to the same narrow professional-copy root cause and were changed in the same source/test batch.
- Focused tests passed at 4 files / 25 tests after replacing primary `analytics store ready`, `后端目录`, `归档 API`, `疑点接口` and `专题接口` wording. Full Web and browser gates are still required before the visual verdict can be raised.
- At local exact SHA `3840c12...`, desktop structural acceptance is `20/20` and mobile structural acceptance is `20/20`, with all overflow/occlusion/unexpected-console/page-error counters at zero. The first desktop run's sole semantic failure was a stale temporary archive regex expecting the old copy; updating that fixture expectation made the rerun green without product code changes.
- The broader desktop+mobile visible scan is intentionally stricter and exposed 7 additional unique user-visible implementation phrases across 6 routes. This invalidates a premature `finding_count=0` claim but does not invalidate the structural results.
- The same root cause appears in status, error and boundary descriptions: `检索后端`, `只读 API`, `受控 API`, `读取后端字段画像`, `规则 API`, backend authorization wording and `整改 API`. All seven were replaced with business-facing Chinese while preserving behavioral and permission boundaries.
- Focused tests for the second remediation passed at 6 files / 60 tests. A new local commit, exact static export, desktop/mobile visible scan and manual visual review are still required before raising the verdict above `87/revise`.
- The second remediation is frozen as local exact candidate `7a44c191501b19a24aae72c408f010054022d7d5`. Compared with `ce639ae...`, only Web copy/test files changed; the previously validated backend/release-guard tree is unchanged.
- Exact candidate Web evidence is green: 38 files / 364 tests, typecheck, lint, 24-page release export and 87-file manifest. Manifest SHA-256 is `18b90e172231ae6337dc56f47d109ad7efcf7f25e037379fa878be46b92ddd05`.
- Desktop primary, mobile secondary and tablet supplemental structural reports are each `20/20`; every geometry/error counter is zero. The 60 screenshot paths resolve to 55 hashes because five alias contracts intentionally render their target page exactly.
- The expanded visible-copy scan covers 17 independent routes at desktop and mobile and now returns `finding_count=0`. This closes both the initial six strings and the later seven unique strings without removing collapsed diagnostic evidence.
- Manual contact-sheet review restores the strict visual verdict to `93/100`, `pass`, accepted P0/P1=`0`. The result is limited to L2 API-blocked static/error states; authenticated populated production remains unproven.
- GitHub remains at Draft PR #239 head `a3407a4...`. Local branch is three commits ahead; existing CodeRabbit/mergeability status does not cover `7a44c191...` until an independently authorized push/PR refresh.
- Fresh remote verification confirms the external gate has not moved: PR #239 remains `OPEN`/Draft and `MERGEABLE/CLEAN` with CodeRabbit `SUCCESS`, but `headRefOid=a3407a4...`; local exact candidate `7a44c191...` is not remotely reviewed.
- C2-PROMOTE authorization is explicit and bounded: push/update Draft PR only. The candidate is a normal fast-forward of 3 commits / 18 files; secret-marker scan is zero. Existing CodeRabbit success must be treated as stale immediately after push until the new head receives fresh status.
- C2-PROMOTE succeeded without widening scope. New remote/PR head is exactly `7a44c191...`; CodeRabbit's fresh start time is after the push and its state is `SUCCESS`, while PR remains `OPEN`/Draft and `MERGEABLE/CLEAN`.
- The updated PR body preserves the critical truth boundaries: 854 backend tests belong to `ce639ae...` with an unchanged backend tree through `7a44c191...`; Web/build/manifest/browser evidence is exact-head; API-blocked visual evidence stays L2 and does not become production acceptance.
- C3 Ready can be evaluated next, but neither fresh CodeRabbit success nor mergeability is merge authorization or deploy evidence.
- C3-READY gate is allowed-with-label because exact head, fresh CodeRabbit success, clean mergeability and L2 evidence labeling are current. Ready only advertises review readiness; it does not raise evidence above L2 or authorize merge/production.
- Marking the PR Ready retriggered CodeRabbit and temporarily changed merge state from `CLEAN` to `UNSTABLE` while the check is `PENDING`. The merge gate must wait for the new exact-head/Ready-context result instead of inheriting the earlier Draft-context success.
- C3-READY itself is verified complete at exact head. Eight minutes of bounded observation did not produce a terminal CodeRabbit result; therefore the only honest merge-gate status is `check_pending`, not pass or fail.
- A later read-only follow-up at 2026-07-17 15:44 CST again observed the same Ready-context CodeRabbit run as `PENDING`. Two short watch windows showed `0 failing` and `1 pending`; this is additional evidence of an unresolved external gate, not evidence that the check passed or that merge is authorized.

## 2026-07-17 Loop 59 C3 CodeRabbit Remediation Findings

- The Ready-context check eventually converged to `SUCCESS`, `MERGEABLE/CLEAN`, but the submitted review contained 18 actionable inline comments and one test suggestion. A green status context is therefore necessary but not sufficient for merge readiness.
- All comments were verified rather than applied mechanically. The proposed `sourceCollection` assertion was invalid for the actual type; the production contract derives collection identity from `id`, so the missing-required-core test was added at that real boundary.
- The duplicate-agent cleanup must never reactivate an all-dormant identity group. Market ambiguity must be computed from all-status inventory while displayed cards remain active-only, otherwise archived duplicates can leak an apparently installable mapping.
- Production execute must reject `--skip-app-rebuild`; workspace aliases belong to server-side redirects; read workbenches must fail closed when runtime stores are not ready; failed/pending reads must not render synthetic zero metrics.
- Personal-material generation needs invalidation on role changes, and permission evidence must be bound through an explicit client-to-API role mapping (`admin→it-admin`, `technician→technician`, `director→department-head`, `member→auditor`). Direct namespace comparison was a real P1 found by isolated review after CodeRabbit remediation.
- Desktop web remains the primary visual surface, phone mobile is the secondary gate and tablet is supplemental. The final local matrix is `20/20` for each viewport with zero geometry/browser-error failures; 34 desktop/mobile independent-route text scans found zero visible implementation-copy leaks.
- The browser and test evidence applies to the uncommitted local working tree only. Remote PR head and CodeRabbit result remain bound to `7a44c191...`; no exact-SHA claim can be made for the remediation until an authorized atomic commit is created and rebuilt.
- Production knowledge coverage and 100+ agent operational claims were not refreshed in this remediation lane. The last L3 findings remain the applicable observation, not a current-turn re-acceptance.
- Boundary remains `production unchanged`, `deploy_execution=false`, `database_write=false`, `provider_attempt_made=false`, `provider_call_status=not_observed`, `live_send=false`.

## 2026-07-17 Loop 59 C3 Exact-SHA Browser Regression Findings

- A contact-sheet visual pass did not prove floating-control non-occlusion. The first committed exact-SHA matrix found four intersections that were absent from the earlier narrative verdict; automated geometry evidence correctly overruled the manual summary.
- The root cause was anchoring the desktop history trigger to the route-content bottom-right at `right=26/bottom=26`. That location competes with route CTAs, cards and the medical AI control. Keeping the trigger fixed but inside the desktop navigation rail removes the shared ownership conflict.
- The corrected contract is desktop-only: expanded rail `left=12/bottom=86/width=232`, collapsed rail `left=24/width=44`; mobile keeps the existing topbar control. The final matrix proves zero route-content intersections at desktop, mobile and tablet.
- Runtime candidate `9d9b192...` passes Web `369/369`, 24-page/87-file release build, desktop/mobile/tablet `60/60`, visible-copy `34/0`, lint, typecheck and diff-check. The release manifest is bound to the candidate and hashes to `f1c8df9a6ceca62f92bb525eb691a69ef63a39b27bed1dc1523c4f1f19e3bbf0`.
- Remote PR #239 still points to `7a44c191...`; no remote check covers `9d9b192...` until a separately authorized push/PR refresh occurs.

## 2026-07-17 Loop 59 Final Review Closure Findings

- The review correctly detected that completed local remediation and pending promotion had been collapsed into one unchecked item. Promotion has since completed, so the truthful final split is: local remediation checked, PR refresh checked, C3-MERGE unchecked.
- The review correctly detected ambiguous screenshot attribution. The accepted post-remediation corpus was regenerated at evidence head `1b3e44a80f9cd5c89341b51f334c698b66de11e3`; the docs-only closure does not change the `web/` tree.
- Workstation backup locations and credential file metadata are not release evidence. Loop 59 ledgers now retain non-sensitive artifact IDs only and omit credential path/mode/size details.
