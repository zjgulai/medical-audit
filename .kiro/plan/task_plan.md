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
- [ ] Run Loop 49: if explicitly authorized, run post-merge local gates and deploy preflight for `origin/main`; stop before production `--execute`, production probe, provider call, Docker change, or write-path smoke unless separately authorized.
