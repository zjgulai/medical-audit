---
title: "medical_audit loop engineering release readiness plan"
project: "medical_audit"
created_at: "2026-06-30T21:42:00+08:00"
status: "active"
evidence_grade: "local-fullstack-plus-doc-derived"
---

# medical_audit Loop Engineering Plan

## Goal

Bring the current `codex/frontend-2.0` workstream to a demo-safe and release-candidate-safe state without overstating evidence:

- latest UI/UX routes remain the product baseline;
- local frontend and fixture E2E checks stay green;
- local fullstack and production-read-only checks are run only through explicit evidence gates;
- production writes, provider calls, env changes, and Docker-affecting deploy actions remain blocked until separately authorized.

## Five Components

### 1. Objective Contract

Target outcome: a traceable release-readiness loop that can answer four questions:

- What is ready for tomorrow's demo?
- What is only local or fixture-verified?
- What is still blocked before production rollout?
- What exact evidence is needed to move one grade higher?

Exit criteria for this loop:

- a current task plan and progress ledger exist under `.kiro/plan/`;
- local web validation evidence is fresh;
- dirty worktree and release-candidate blockers are explicitly inventoried;
- next production-read-only or deploy step is framed as a gated action, not implied completion.

### 2. State And Evidence Ledger

Facts verified in this planning pass:

- current branch is `codex/frontend-2.0`;
- worktree is dirty with UI/test changes and untracked `fund-compliance/review`;
- no project-level `AGENTS.md`, `.codex/context-pack.md`, or `.codex/session-thread.md` was found;
- repository docs identify the next major lane as post-deploy production read-only governance verification and clean release path.

Evidence grades:

- local lint/typecheck/unit/build/foundation E2E: local or fixture evidence;
- `.kiro/plan` files: planning state only;
- existing workflow docs: repo-derived planning evidence, not current production observation;
- production read-only: L3 only after fresh GET-only probe;
- authorized live work: L4 only after explicit approval, backup, execution log, and rollback path.

### 3. Constraints And Guardrails

- Do not modify production, remote env, provider credentials, object storage, or shared Docker without explicit task authorization.
- Do not claim production is updated unless a fresh production read-only deployment-state/probe report proves it.
- Do not merge or deploy from the current dirty worktree.
- Preserve user and other-agent changes; do not revert unrelated files.
- All new Markdown must include frontmatter.
- Any file edit to an existing key file requires a backup under `~/.Codex/file-history/`.

### 4. Execution Loop

Each loop iteration uses the same structure:

1. Observe: refresh `git status`, relevant docs, and current route/test state.
2. Decide: pick one smallest batch that raises evidence or removes a blocker.
3. Act: make only scoped changes or run only allowed checks.
4. Verify: run the narrowest useful test first, then broader gates when needed.
5. Record: update `.kiro/plan/progress.md` and keep evidence grade labels explicit.

### 5. Feedback And Escalation

Feedback sources:

- local commands and test reports;
- browser route checks;
- workflow docs and output JSON/MD artifacts;
- production read-only reports when explicitly authorized.

Escalation rules:

- test or build regression: stop feature work, repair or document blocker;
- production-write need: stop and request explicit authorization;
- provider call need: stop and request explicit authorization;
- unclear SSO/session path: keep P0-04 blocked until a path is selected.

## Current Todo

- [x] Bootstrap persistent plan files.
- [x] Run Loop 0 baseline: current dirty worktree, doc-derived blockers, and fresh local validation summary.
- [x] Run Loop 1 local release-candidate gate: verify latest UI/UX baseline against web checks and foundation E2E.
- [x] Run Loop 2 fullstack gate: run `pnpm local:fullstack:e2e` only after confirming local backend dependencies are available.
- [x] Run Loop 3 release manifest plan: define clean branch/worktree, staged file set, validation gates, and deploy preflight requirements.
- [x] Run Loop 4 clean release worktree sync: apply only manifest files into a clean worktree and rerun local gates.
- [x] Run Loop 5 production-read-only request: prepare exact command and blocker list; execute only if explicitly authorized.
- [x] Run Loop 6 local release-candidate commit: stage only manifest files and create clean local commit `8a8592514618`.
- [x] Run Loop 7 gated promotion choice: push clean candidate branch and open Draft PR `#178`.
- [x] Run Loop 8 deploy preflight gate: run default read-only deploy preflight for PR `#178`; production observation still requires an approved deployed SHA.
- [x] Run Loop 9 release decision gate: promote PR `#178` from Draft to ready for review; keep merge/deploy blocked by explicit authorization.
- [x] Run Loop 10 merge decision gate: merge PR `#178` and record merge commit `0cc4bfd287050fa5d9fe763409157d0e276f4ba0`.
- [x] Run Loop 11 production deploy pre-execution gate: align clean main worktree to merge commit, rerun local gates, rerun default deploy preflight, and keep `--execute` unrun pending explicit deploy authorization.
- [x] Run Loop 12 authorized production deploy execution: deploy merge commit `0cc4bfd287050fa5d9fe763409157d0e276f4ba0`, verify deployment state, permission readonly, documents readonly, and capture frontend semantic P1 drift.
- [x] Run Loop 13 frontend acceptance contract alignment: update production frontend acceptance expectations for split `/fund-compliance/review` and simplified `/chat` copy; rerun acceptance and separate old copy drift from the real new-form overflow it exposed.
- [x] Run Loop 13 local hotfix: fix `/fund-compliance/review` new-form popover horizontal overflow and verify desktop/mobile locally.
- [x] Run Loop 14 clean hotfix promotion: apply only Loop 13 hotfix files into clean main worktree, rerun gates, commit/merge, then deploy only through the production execution gate.
- [x] Run Loop 15 demo rehearsal pass: capture browser evidence for the core demo path and list any remaining copy-density or navigation simplification issues without starting another deployment unless required.
- [x] Run Loop 16 demo runbook or P2 polish choice: package the verified demo path for tomorrow's presentation; defer mobile top navigation and agent-market chip density to a post-demo P2 polish batch.
- [x] Run Loop 17 last-minute spot check: immediately before the presentation, run production read-only route/acceptance checks only, with no code or deploy changes unless a P0/P1 issue appears.
- [x] Run Loop 18 demo support pack: keep production frozen for the live presentation, package live route checklist, screenshot fallback paths, evidence chain, and dense-UI/provider-call boundary.
- [x] Run Loop 19 post-demo P2 polish: reduce mobile top navigation density and `agent-market` first-viewport chip density without widening scope into provider calls, data ingestion, schema changes, or deployment.
- [x] Run Loop 20 clean promotion decision: isolate the four-file UI/test delta in `/Users/pray/project/medical_audit_minimal_pr`, rerun local gates, and stop before push/merge/deploy.
- [x] Run Loop 21 production promotion gate: pushed the clean candidate branch, opened/merged PR `#180`, reran deploy preflight, and stopped before production `--execute`.
- [x] Run Loop 22 production deploy execution gate: deployed clean `main` commit `b79a5e499cb99bded782e3ccd9ad4195dcab4e70`, completed post-check/write-sha/smoke tail after the deploy SSH backup handoff stalled, and passed deployment-state audit, production frontend acceptance, permission readonly, documents readonly, and UI density spot checks.
- [x] Run Loop 23 post-deploy observation: reran production read-only state/smoke/permission/documents/browser checks and recorded that production remains healthy at `b79a5e499cb99bded782e3ccd9ad4195dcab4e70`.
- [x] Run Loop 24 user-visible product QA: inspected production UI/UX across core pages and recorded the remaining P2 workspace internal-language copy issue.
- [x] Run Loop 25 only if requested: fix workspace user-facing copy for `后端与索引联通` / `postgres` wording locally, then rerun local and browser gates; do not deploy without a new explicit deploy authorization.
- [x] Run Loop 26 only if requested: decide whether to promote Loop 25 from local candidate to PR/merge/deploy; require explicit authorization before push, merge, or production `--execute`.
- [x] Run Loop 27: executed authorized production deployment for `main@b1c9a6c229a7880afcbfed35c1903d514914bb15`, then passed deployment-state audit, production smoke, frontend acceptance, permission readonly, documents readonly, and targeted workspace copy browser check.
- [x] Run Loop 28: performed read-only post-deploy observation and demo evidence freeze for deployed `main@b1c9a6c229a7880afcbfed35c1903d514914bb15`; no deploy or write-path smoke.
- [x] Run Loop 29: created no-change demo handoff with route script, evidence links, safe claims, Q&A boundaries, and screenshot fallbacks; no deploy or production probe.
- [x] Run Loop 30: created post-demo backlog triage from Loop 28/29 evidence, with no-current P0/P1 findings, P2 authorized validation lanes, and feedback-dependent product polish candidates; no code or production probe.
- [x] Run Loop 31: created feedback intake and P2 lane decision gate; no implementation lane selected and no production/code side effect.
- [x] Run Loop 32: selected P2-D and hardened local component/browser acceptance for `费用表单`, `表1`, `表2`, `表3`, and custom form visibility/selection.
- [x] Run Loop 33: executed targeted local verification for Loop 32 with lint, typecheck, component test, and full foundation browser E2E.
- [x] Run Loop 34: created an atomic staging plan for the current dirty worktree without staging, committing, pushing, merging, or deploying.
- [x] Run Loop 35: selected Group E and created a docs-only staging rehearsal without staging, committing, pushing, merging, or deploying.
- [x] Run Loop 36: execute approved docs-only staging for Group E by staging `.kiro/plan/*.md` and `.kiro/steering/planning-context.md` only; stop before commit, push, merge, deploy, production probe, provider call, or write-path smoke.
- [x] Run Loop 37: commit the staged docs-only unit as one local atomic commit; keep business code unstaged and stop before push, merge, deploy, production probe, provider call, or write-path smoke.
- [x] Run Loop 38: merge typography/font-size requirements into the government-style full-site UI/UX batch plan; keep it docs-only and stop before business-code edits, push, merge, deploy, production probe, provider call, or write-path smoke.
- [x] Run Loop 39: implement Batch 1 global tokens, typography scale, shell/nav simplification, and local responsive/browser verification.
- [x] Run Loop 40: implement Batch 2 core business page first-viewport simplification for fund-compliance, review, chat, and agent-market, then verify locally.
- [x] Run Loop 41: implement Batch 3 remaining dense workspace pages for documents, knowledge-base, analytics, reports/projects, and verify locally before any production or deploy action.
- [x] Run Loop 42: decide the clean promotion path for Loop39-41 UI work; isolate the intended staged set, rerun gates, and stop before push, merge, deploy, production probe, provider call, Docker change, or write-path smoke unless explicitly authorized.
- [x] Run Loop 43: if explicitly authorized, stage the Loop39-42 candidate set only, keep `output/` and `tmp/outputs/` excluded, optionally create a local commit, and stop before push, merge, deploy, production probe, provider call, Docker change, or write-path smoke unless separately authorized.
- [x] Run Loop 44: decide whether to push the local UI commit to a remote branch and open/update PR; require explicit authorization and stop before merge, deploy, production probe, provider call, Docker change, or write-path smoke unless separately authorized.
- [x] Run Loop 45: review PR `#182` conflict status and CI only; decide a conflict-resolution strategy, but stop before resolving conflicts, ready-for-review, merge, deploy, production probe, provider call, Docker change, or write-path smoke unless separately authorized.
- [x] Run Loop 46: if explicitly authorized, resolve PR `#182` conflicts on `codex/frontend-2.0` according to `.kiro/plan/pr182_conflict_strategy_loop45_20260702.md`, rerun local gates, push the conflict-resolution commit, and stop before ready-for-review, merge, deploy, production probe, provider call, Docker change, or write-path smoke unless separately authorized.
- [x] Run Loop 47: review PR `#182` after the conflict-resolution push, wait for GitHub mergeability/check status if needed, and decide whether to move from Draft to ready-for-review; stop before merging, deployment, production probe, provider call, Docker change, or write-path smoke unless separately authorized.
- [x] Run Loop 48: if explicitly authorized, decide the PR `#182` merge gate after confirming head SHA, mergeability, and checks; stop before production deploy, production probe, provider call, Docker change, or write-path smoke unless separately authorized.
- [x] Run Loop 49: if explicitly authorized, run post-merge local gates and deploy preflight for `origin/main`; stop before production `--execute`, production probe, provider call, Docker change, or write-path smoke unless separately authorized.
- [ ] Run Loop 50: if explicitly authorized, decide the production deploy execution gate for `main@4d54922d`; require explicit `--execute --confirm-production` authorization and stop before provider call or write-path smoke unless separately authorized.

## 2026-07-13 Loop 51 Unresolved Quality Debt And Deployment Readiness

Goal:

- Close the four repository-wide Ruff/Mypy findings left after the PPT-grounded product implementation.
- Revalidate the complete local product candidate from the current feature worktree.
- Refresh the release baseline against current `origin/main` without merging or rebasing user-owned work.
- Use `/Users/pray/Downloads/DDDD.pem` only for an SSH read-only production audit and produce an executable deployment, rollback, and acceptance plan.

Acceptance contract:

- `uv run ruff check .` and `uv run mypy src` pass from the feature worktree.
- Relevant targeted tests pass before broader backend/frontend/fullstack gates are run.
- The previously accepted product flows remain green in unit, typecheck, lint, build, local fullstack E2E, and visual acceptance as applicable.
- Remote inspection captures current deployed SHA, service/container health, front-door health, disk pressure, and backup inventory without reading `.env`, credentials, or private-key contents.
- Deployment preflight runs without `--execute`; the final plan names target SHA, backup steps, rollback steps, health gates, and owner-authorization boundary.
- Protected pre-existing dirty files remain untouched and unstaged:
  - `docs/workflows/workflow-answer-provider-production-gate-stable.md`
  - `docs/workflows/workflow-project-state-and-debt-register-stable.md`
  - `drafts/analysis/frontend-cutover-production-readonly-audit-draft-20260705.md`

Execution TODO:

- [x] Phase 0: restore branch/worktree/evidence state, verify SSH-key permissions, and identify the four static-analysis findings.
- [x] Phase 1: reproduce and fix the four Ruff/Mypy findings with narrow code/test changes.
- [x] Phase 2: run targeted then full local regression and refresh acceptance artifacts.
- [x] Phase 3: fetch current remote refs, assess branch divergence, inspect deployment scripts/docs, and run deploy preflight without `--execute`.
- [x] Phase 4: run SSH read-only production audit using the supplied key; do not mutate production, Docker, database, object storage, or provider state.
- [x] Phase 5: synchronize deployment/acceptance records, review the exact diff, and create local task-level commits from clean atomic staged sets.

Evidence boundary:

- Local tests/build/preflight are L1/L2 evidence.
- SSH GET/read-only observation is L3 evidence.
- Production deployment, remote file synchronization, container recreation, database/object-storage writes, provider calls, merge, and push remain blocked pending separate explicit authorization.

## 2026-07-13 Loop 52 PR #232 Review Remediation

Goal:

- 修复 PR #232 独立复审发现的权限隔离、跨身份状态和生产发布门禁问题，并以本地原子 commit 和完整回归证据交付。

Execution TODO:

- [x] 稳定复现并分级独立复审发现，明确 P0/P1 验收标准和外部副作用边界。
- [x] 修复 audit finding/project scope、review task scope、readiness count 和上传身份校验，并补权限回归测试。
- [x] 修复 replica/agent/deep-link/chat 的跨身份状态失效与 stale response 行为，并补前端回归测试。
- [x] 强化生产 deploy execute、GET-only smoke、显式 L4 gate、Nginx fail-closed 和 marker-safe rollback。
- [x] 完成 Ruff、Mypy、Pytest（`590` collected）、脚本测试（`100`）、Web 测试（`32/279`）、typecheck、lint、build（`24/24`）和 local full-stack E2E（`13/13`）。
- [x] 完成三轮独立只读复审；最终无剩余 P0/P1。
- [x] 创建三个本地原子代码 commit，并同步部署计划和项目记录。
- [ ] 下一步须单独授权 push 本地 commit、更新 PR #232 并等待远端复审/检查；不得在同一步隐式 merge 或 deploy。

Evidence boundary:

- 本轮新增证据为 L1/L2 `local_only`；此前 L3 生产只读观察仍是历史独立证据，不能替代本轮代码部署后的生产验收。
- 本轮未产生 L4 证据；`production unchanged`、`provider_call=false`、`database_write=false`、`live_send=false`。

## 2026-07-15 Loop 53 Production Evidence Contract And Deployment

Goal:

- 修正生产权限 smoke 与前端验收对审计日志副作用的错误分类。
- 将完整权限矩阵和完整浏览器验收收敛到显式 L4 `audit-log-only` 授权路径。
- 经 PR 审查合并后，只从 clean `main` 部署精确 merge SHA，并完成分层生产验收。

Execution TODO:

- [x] 确认 PR `#233` 已合并为 `2d790375621bafa3dd564b1a1464f3e229a053a2`，远端分支保留。
- [x] 纠正部署准备证据：此前工具至少产生 69 条审计事件，不能表述为 `database_write=false`。
- [x] 批准并提交方案 A 设计文档 `15fa4ee`。
- [x] 实施权限 smoke 的 2 项公共只读 / 35 项显式写入双模式合同；protected probe 全部退出默认只读 allowlist。
- [x] 实施前端验收默认 fail-closed / 显式 `audit-log-only` 完整验收合同。
- [x] 完成全量本地门禁、人工对抗复核与 bundled Codex review；accepted P0/P1 为 `0`。
- [x] 完成原子 commit、push、Ready PR 与 GitHub merge 审查。
- [x] merge 后在 clean `main` 完成磁盘检查、零执行 preflight 和生产部署；不删除远端分支。
- [x] 部署后分别保存 L3 状态/有限只读证据与 L4 `audit-log-only` 完整验收证据。

Evidence boundary:

- 当前生产运行版本已更新为 `2bba501c93eaf1f6f7485241ec15e0c21c209842`；部署脚本退出 `0`，`deploy_execute=true`。
- 已观察的至少 69 条审计事件保留，不清理、不回填。
- L3 有限只读与 L4 `audit-log-only` 验收均已完成；未执行 schema、SQL backfill、provider call、review/query 写入、live send 或远端分支删除。

## 2026-07-15 Loop 54 Deployment Closure And True-L3 State Audit

Goal:

- 以已部署的 `main@2bba501c93eaf1f6f7485241ec15e0c21c209842` 为生产基线，完成部署计划、TODO、回滚边界和验收矩阵的最终闭环。
- 修复 `audit-tencent-cloud-deployment-state.py` 自称 L3/read-only、实际写入一条 `search-backend-status-view` 审计日志的证据合同错误。
- 用生产审计日志前后 count/latest/fingerprint 全局快照不变和唯一 auditor identity 零事件证明修复后的成功运行可分类为 L3；不因 operator-only 脚本修复而重复重建生产容器。

Execution TODO:

- [x] Phase 0 — 冻结基线：确认 PR `#234` 已合并、生产 marker 与 merge SHA 一致、远端功能分支保留、发布 worktree 干净；隔离原始 dirty worktree。
- [x] Phase 1 — 建立完整计划：补齐部署准备、实施、PR/merge、部署决策、回滚和分层验收门禁。
- [x] Phase 2 — 修复 conditional L3 合同：使用成功路径零日志的 catalog、全表 count/latest/fingerprint 与唯一 auditor identity 组合快照、补强 side-effect 元数据和 fail-closed 校验，并同步稳定 workflow；鉴权失败可能先写日志的限制已显式记录。
- [x] Phase 3 — 本地验证：deployment-state 15 项聚焦验证、127 项脚本测试、全仓 Ruff/Mypy、618 项 Pytest 与 `git diff --check` 全部通过。
- [x] Phase 4 — 独立复审：accepted P0/P1=`0`；认证拒绝、redirect、secret boundary、frontdoor、provider boundary、并发/retention、归因分类和 audit-log 写入路径均已收敛。
- [x] Phase 5 — GitHub 推广准备：原子 commit `1cf7538` 已 push，Draft PR `#235` 精确包含 8 个文件，GitHub 报告 `MERGEABLE/CLEAN`、checks 未配置/未报告；Ready/merge 作为该 PR 外部最终状态执行并在 closeout 记录，不删除远端分支。
- [x] Phase 6 — 部署决策：intended diff 仅含 operator-side 脚本/测试/文档/plan/release rules，`runtime_deploy_required=false`；禁止无意义重建生产 runtime。
- [x] Phase 7 — 生产候选验收：独立 baseline/after 均为 `56066` 且最新时间一致；脚本内 count/latest/fingerprint 不变、唯一 auditor identity `0→0`，生产 marker 仍为 `2bba501...`，四个相关容器健康、49,051 embeddings、`provider_call_status=not_called`。
- [x] Phase 8 — 收尾记录：已同步 `.kiro/plan`、稳定 workflow 和 release rules，保存生产 JSON/Markdown 证据；PR Ready/merge outcome 由 GitHub 外部状态和最终 closeout 给出，避免在待合并 PR 内自称已 merge。

Acceptance matrix:

- Local/L2：全部相关静态检查与自动化测试通过；报告字段必须明确 `evidence_grade=L3-production-read-only`、`production_side_effect=none`、`database_write=false`、`provider_call_status=not_called`、`http_methods=[GET]`。
- PR gate：PR head、review 状态、mergeability 和 checks 分开记录；无 checks 只能表述为“未配置/未报告”。
- Deploy gate：仅 runtime artifact 变化才允许第二次生产部署；部署必须从 clean `main`、`HEAD == origin/main == approved_sha` 执行，先备份再变更，并保留远端分支。
- L3 production acceptance：状态审计前后 `audit_log_events` 的 count、最新时间和 event-id fingerprint 不变，本次唯一 auditor identity 的事件计数前后均为 `0`；marker、容器健康、Nginx、front door、静态资源、PostgreSQL 和 search backend 同时通过。
- L4 production acceptance：本轮默认不重复；只有再次执行完整权限/浏览器矩阵时，才以 `audit-log-only` 明示授权和独立报告保存。

Rollback and stop conditions:

- operator-only 修复回滚：revert PR/commit；不触碰生产文件、容器或 marker。
- runtime 部署回滚：仅在 Phase 6 判定需要部署时使用对应 stamp 的 app/db/env/nginx/web 备份，并在恢复验证通过后更新 marker。
- 任一测试失败、审计 delta/快照/identity 证据不满足、provider attempt、生产 SHA 不符、frontdoor 异常或容器不健康即停止状态升级，保留原始证据，不清理审计日志。

Evidence boundary:

- 当前生产部署已完成；本 Loop 的新目标不是重复部署，而是修复 operator-side 验收工具并证明一次成功运行的全局 audit snapshot 不变且唯一 auditor identity 零事件。
- Phase 7 已证明本次成功运行可分类为 `L3-production-read-only`；仍不得把工具宣传为 all-path read-only，鉴权失败或并发变化会失败关闭并分类为 `audit-log-only` 或 `unknown`。

## 2026-07-15 Loop 56 PPT Production Closure

Goal:

- 将 `/Users/pray/Desktop/audit/前端页面沟通0710.pptx` 的 15 页反馈重新建立为逐页生产闭环矩阵，不再用收敛后的 R01-R19 本地通过替代原始 PPT 业务语义。
- 在当前 `origin/main` 基线实现三个明确缺口：历史对话人工转任务、有权限的新建项目、缺失文档统计与真实 `0` 的区分。
- 对真实数据分析、业务流程图谱、五类未交付正式模板和三个扩展智能体真实调用保持显式阻塞，直到医院输入或独立 provider 授权到位。

Execution TODO:

- [x] Phase 0 — 冻结基线：从 fresh `origin/main` 创建 `codex/ppt-production-closure-20260715`；确认 worktree clean、生产 runtime 仍以 `2bba501...` 为最近验证基线。
- [x] Phase 1 — 建立 15 页逐项验收矩阵：区分代码实现、最终提交覆盖、本地交互、生产路由、生产业务动作和业务输入阻塞。
- [x] Phase 2 — 历史对话人工转任务：复用 query history、project scope、ReviewTaskStore 和权限合同；已完成 owner-scoped lookup、显式项目选择、稳定幂等任务、审计 intent/completion/failure 与 Markdown/DOCX 底稿导出，无自动建任务。
- [x] Phase 3 — 有权限的新建项目：复用现有项目/成员模型；已完成 admin-only API/UI、项目与创建人成员同事务、持久化 project/audit store fail-closed、动态项目跨路由可见和未知成员数语义，无 schema 变更。
- [x] Phase 4 — 文档统计语义：未知统计显示“待同步”，真实 `0` 保持 `0`；catalog/页面 degraded/error 回归已通过主线程复验。
- [x] Phase 5 — 本地验收：相关 backend/frontend tests、全量 Ruff/Mypy/Pytest/Vitest、typecheck、lint、build、local full-stack E2E 与 Playwright 交互矩阵均通过；截图覆盖文档真实 0、项目创建及移动端历史转任务。
- [x] Phase 6 — 独立复审与发布准备：已保存 evidence matrix、检查 38-file 窄 scope worktree、完成多轮 fail-closed 修复与最终复审；accepted P0/P1/P2=`0`，状态为 `ready_for_owner_authorization`。本阶段未 commit、push、开 PR、merge 或 deploy。
- [ ] Phase 7 — 生产与 provider 门禁：生产浏览器完整矩阵只能以明确的 L4 `audit-log-only` 运行；项目创建、转任务、上传和真实 provider smoke 均是独立 L4 业务写入/外部调用，不与本地验收合并执行。

Acceptance contract:

- 原始 PPT 15 页每页都有 `implemented / partial / blocked / not-applicable` 状态及对应代码、测试或生产证据；不得仅引用 R01-R19 汇总 pass。
- 历史对话不会自动创建任务；只有用户显式选择项目并提交时才创建一条可追溯任务，失败不得静默或伪成功。
- 新建项目只有具备明确权限的身份可执行；创建人自动进入可见范围，非成员不可通过直接 URL 读取。
- 文档统计未知、后端 degraded/error 与真实 `0` 三种状态在 API adapter 和页面展示上可区分。
- 本轮所有本地验证保持 `provider_call=false`、`database_write=local-test-only`；未取得独立生产执行证据前保持 `production unchanged`。

Stop conditions:

- 任何实现要求 schema migration、历史生产数据 backfill、读取 secrets、生产 SQL 写入或真实 provider 调用时停止并单独列门。
- 项目创建或转任务若无法复用现有持久化模型与权限合同，不以 fixture/localStorage 伪装完成。
- 最终生产交互矩阵如会写审计日志，只能在显式 L4 `audit-log-only` 授权下执行并记录 delta；不得标为 L3。

## 2026-07-15 Loop 57 PPT Candidate Promotion

Goal:

- 以生产部署为最终目标，把 Loop 56 的 L2 本地候选整理为可审阅、可回滚、可部署的 GitHub Draft PR。
- 保持 PR Ready、merge、clean-main deploy preflight 与生产 `--execute` 为后续独立证据门，不把 Draft PR 创建表述为已部署。

Execution TODO:

- [x] Phase 0 — 恢复 Loop 56 计划与证据，确认当前分支、无 staged 内容、38-file 候选集合和最终全量门禁。
- [x] Phase 1 — 按 `drafts/analysis/ppt-production-closure-atomic-commit-plan-draft-20260715.md` 创建三个显式 manifest 的业务原子 commit；第四个 docs-only 推广证据 commit 在 Draft PR 创建后生成。
- [x] Phase 2 — 确认业务 commit chain 线性、`origin/main` 为祖先，push 当前分支并创建 Draft PR `#236`。
- [x] Phase 3 — 核对实际 head/base、文件清单、mergeability、checks 和生产部署/回滚说明；第四个 docs-only commit `d6b862c` 已创建、push，并由 GitHub 确认为当前 head。
- [x] Phase 4 — 创建本地推广状态账本 commit（即包含本条记录的 commit）；其最终 push 与 remote head equality 由 GitHub 外部状态和最终 closeout 证明，不在 commit 内预写自身 SHA。停在 `ready_for_pr_review`，不在本 Loop 隐式 Ready、merge 或 deploy。

Acceptance contract:

- 禁止 `git add .`；每个 commit 的 staged manifest、stat 和 `git diff --cached --check` 必须在提交前核验。
- Draft PR 必须只包含 Loop 56 的三个产品闭环及其测试/合同/验收记录，不包含 `output/`、临时 SQLite、screenshots 或 secrets。
- 当前生产保持 `production unchanged`、`provider_call=false`、`database_write=false`、`deploy_execution=false`。

## 2026-07-16 Loop 58 Next-Batch Deployment Planning

Goal:

- 将 `codex/production-ui-reconciliation-20260716` 的 `29` 个已提交 commit、当前 UI/acceptance checkpoint 和缺失的部署证据合同收敛为 clean exact-SHA release candidate。
- 在任何生产执行前补齐首次 versioned-release migration readiness、S0/S1/S2 schema/business snapshot、全截图 exact-SHA frontend acceptance 与 run-specific audit attribution。
- 把 local candidate、Draft PR、Ready、merge、production preflight、deploy、L3 验证、L4 `audit-log-only` 验收和业务写入 UAT 保持为独立状态与授权门。

Execution TODO:

- [x] Phase 0 — 恢复 branch/worktree/Task 11 断点，审查部署、回滚和 L3/L4 工具，完成下一批方案与 TODO；本 Phase 仅计划文件写入。
- [x] Phase 1 — 完成 release evidence contract：migration readiness、S0/S1/S2 guard snapshot/compare、schema/business delta、first-migration rollback acceptance；当前证据为 L2 fixture/dry-run。
- [x] Phase 2 — 强化 production frontend gate：全部 `40` 次 execution 截图、expected deploy SHA/public manifest、canonical guard snapshot hash、unique run identity 和 collector/provider scope 分层；保持 L4 `audit-log-only`。
- [x] Phase 3 — 已实施显式 non-regression exception：exact base/tool/command/diagnostic/source fingerprint gate 返回 `allowed-with-label`，六个候选 Python scripts targeted Mypy PASS；不得表述为 full PASS。
- [x] Phase 4 — 已按 evidence/UI/planning 三个显式 manifest 创建本地原子 commit；前两项为 `0d34a94`、`85859a6`，本 planning ledger commit 形成最终 clean exact SHA，提交后的 SHA 由 Git 外部核验。
- [ ] Phase 5 — 从 exact SHA 重跑 L2 全量门禁、release manifest 与 `17 independent + 3 aliases` 三 viewport 本地矩阵；旧 `source_sha=null` matrix 仅保留为 pre-fix evidence。
- [ ] Phase 6 — 经单独授权 push/Create Draft PR；独立复审 accepted P0/P1=`0` 后，再分别取得 Ready 和 merge 授权。
- [ ] Phase 7 — 在 clean `main == origin/main == approved SHA` 下，经 production read-only 授权捕获 S0/topology 并运行 default deploy preflight；`partial_or_unknown` hard stop。
- [ ] Phase 8 — 经 exact-SHA deploy + rollback pre-authorization 执行备份、frozen build、app rebuild、versioned static/Nginx/marker；禁止 schema/provider/review/business writes。
- [ ] Phase 9 — 捕获 S1，运行 conditional L3 deployment-state audit，并证明 S0→S1 schema/business/object zero delta；成功状态仅为 `deployed_l3_verified`。
- [ ] Phase 10 — 分别授权 full permission matrix 和 full frontend acceptance 的 L4 `audit-log-only`；捕获 S2 并证明 S1→S2 只有 run-attributable audit delta，形成 `release_accepted_l4`。
- [ ] Phase 11 — 每个 business-write/provider UAT lane 独立授权、备份、snapshot、fixture、delta、可选 cleanup 与报告。

Current blockers:

- Phase 4 三个 manifest 已冻结；本 planning ledger commit 完成后，最终 clean exact SHA 由 `git rev-parse HEAD` 和空 `git status --short` 外部核验，不在 commit 内自我预写。
- Full route matrix is stale and unbound (`source_sha=null`).
- `mypy src scripts` 保留 `195` 个继承错误/`10` 个 untouched files；D1.1 exact-fingerprint non-regression gate 已通过，但 `mypy_full_pass=false`，历史债务仍未修复。
- D0 SQL/SSH paths are fixture/static verified only because no matching local PostgreSQL container is running; no L3 production capture has executed.
- Object-storage evidence currently covers only the `document_storage_objects` database ledger; COS object enumeration remains unobserved.
- The guard proves only that its collector made no provider attempt. Whole-runtime provider telemetry remains `provider_call_status=not_observed` and must not be promoted to `provider_call=false`.
- SSH provenance/envelope is an operator-workspace evidence contract, not an external signed attestation against a malicious local operator who can replace both code and report; that stronger threat model requires separate architecture/authorization.
- Phase 3 采用显式 non-regression exception；只允许证明当前候选未新增 Mypy 错误，不得声称 `mypy src scripts` full PASS。Phase 4 本地原子 commit 已获本次“自动授权”，但必须等 Phase 3 验证完成后再进入；push、PR、Ready、merge 和生产操作仍为独立门。

Detailed source of truth:

- `docs/superpowers/plans/2026-07-16-production-ui-reconciliation-and-release-integrity.md`, section `2026-07-16 Next-Batch Deployment Plan (Loop 58)`.

Evidence boundary:

- D0 is local implementation evidence only: `L2-fixture-or-dry-run`, `local_only`, `production unchanged`, `provider_attempt_made=false`, `provider_call_status=not_observed`, `collector_provider_call_status=not_called`, `database_write=local-test-only`, `live_send=false`, `deploy_execution=false`.
- Final independent read-only reviews for release guard and frontend acceptance both report `accepted P0/P1=0` with high confidence under the documented controlled-operator threat model.
- No commit, push, PR state change, merge, production probe, backup, Docker/Nginx change, provider call or production write was executed.
