---
title: "medical_audit Loop 34 atomic staging plan"
project: "medical_audit"
created_at: "2026-07-01T16:52:00+08:00"
status: "plan-only"
evidence_grade: "L1-local-runtime-from-loop33"
production_unchanged: true
staging_executed: false
deployed_sha: "b1c9a6c229a7880afcbfed35c1903d514914bb15"
---

# Loop 34 Atomic Staging Plan

## Decision

Loop 34 prepares an atomic staging plan only. It does not run `git add`, create a commit, push, merge, deploy, or touch production.

## Current Worktree Inventory

Tracked modified files:

- `scripts/run-production-frontend-acceptance.mjs`
- `web/src/app/(workspace)/agent-market/page.tsx`
- `web/src/app/(workspace)/chat/page.tsx`
- `web/src/app/(workspace)/fund-compliance/page.tsx`
- `web/src/app/(workspace)/workspace-pages.test.tsx`
- `web/src/components/shell/app-sidebar.tsx`
- `web/src/components/shell/project-context-bar.tsx`
- `web/src/components/shell/workspace-shell.test.tsx`
- `web/tests/e2e/foundation.spec.ts`

Untracked groups:

- `.kiro/`: planning and evidence notes, 14 files, about 180 KB.
- `output/`: Playwright screenshots and reports, 142 files, about 22 MB.
- `web/src/app/(workspace)/fund-compliance/review/page.tsx`: review workbench page, 1 file.

## Concern Groups

### Group A: Loop 32/33 Test Acceptance

Candidate purpose: preserve the verified `费用表单` / `表1` / `表2` / `表3` / custom-form acceptance contract.

Candidate files:

- `web/src/app/(workspace)/workspace-pages.test.tsx`
- `web/tests/e2e/foundation.spec.ts`
- `.kiro/plan/tab_state_acceptance_loop32_20260701.md`
- `.kiro/plan/targeted_verification_loop33_20260701.md`

Staging note:

- Both test files contain broader frontend-2.0 changes, so they should be patch-staged or reviewed as a combined test-modernization unit.
- Verification from Loop 33 applies to the full current worktree. After patch staging, rerun the targeted component test and foundation E2E before committing.

### Group B: Topic Review Product Surface

Candidate purpose: preserve the separate `/fund-compliance/review` workbench and the topic entry page it depends on.

Candidate files:

- `web/src/app/(workspace)/fund-compliance/review/page.tsx`
- `web/src/app/(workspace)/fund-compliance/page.tsx`
- Related navigation/shell files only if their diff is intentionally part of the product surface.

Staging note:

- This is a product/UI unit, not the same commit as the Loop32/33 test-only hardening unless the owner wants one bundled review.
- Run local browser checks around `/fund-compliance` and `/fund-compliance/review` before committing this group.

### Group C: Broader Frontend-2.0 Polish

Candidate purpose: preserve UI simplification and copy/navigation polish outside the topic review page.

Candidate files:

- `web/src/app/(workspace)/agent-market/page.tsx`
- `web/src/app/(workspace)/chat/page.tsx`
- `web/src/components/shell/app-sidebar.tsx`
- `web/src/components/shell/project-context-bar.tsx`
- `web/src/components/shell/workspace-shell.test.tsx`

Staging note:

- Keep this separate from Group A so test hardening can be reviewed without bundling broad UI copy and shell changes.

### Group D: Production Acceptance Script

Candidate file:

- `scripts/run-production-frontend-acceptance.mjs`

Staging note:

- Treat this as tooling. It should not be grouped with UI or test changes until its intended production acceptance delta is reviewed.

### Group E: Planning And Evidence Docs

Candidate files:

- `.kiro/plan/progress.md`
- `.kiro/plan/task_plan.md`
- `.kiro/plan/release_manifest.md`
- `.kiro/plan/findings.md`
- `.kiro/plan/post_demo_backlog_loop30_20260701.md`
- `.kiro/plan/feedback_intake_loop31_20260701.md`
- `.kiro/plan/tab_state_acceptance_loop32_20260701.md`
- `.kiro/plan/targeted_verification_loop33_20260701.md`
- `.kiro/plan/atomic_staging_loop34_20260701.md`

Staging note:

- These can be a docs-only commit if the team wants to preserve loop governance separately.
- Older demo docs under `.kiro/plan/` should be reviewed by date and included only if still useful for audit traceability.

### Group F: Generated Browser Artifacts

Candidate path:

- `output/playwright/**`

Staging note:

- Do not include the whole `output/` tree in a normal code commit.
- If evidence artifacts must be preserved, select only final JSON summaries or move screenshots to an agreed artifact store.

## Recommended Commit Order

1. Docs-only loop governance: Group E, only after reviewing which older `.kiro/plan` files should be retained.
2. Test acceptance hardening: Group A with patch staging, then rerun Loop32/33 verification commands.
3. Product surface: Group B, then run targeted `/fund-compliance` and `/fund-compliance/review` browser checks.
4. Broader frontend polish: Group C, then run full frontend local gates.
5. Tooling: Group D, with a focused dry-run or read-only acceptance proof.

## Verification Baseline

Loop 33 full-worktree verification:

- `CI=true corepack pnpm@9.15.0 --filter medical-audit-web lint`: pass.
- `CI=true corepack pnpm@9.15.0 --filter medical-audit-web typecheck`: pass.
- `CI=true corepack pnpm@9.15.0 --filter medical-audit-web test -- 'src/app/(workspace)/workspace-pages.test.tsx'`: pass, 30 tests.
- `PLAYWRIGHT_REUSE_SERVER=1 CI=true corepack pnpm@9.15.0 exec playwright test tests/e2e/foundation.spec.ts`: pass, 17 tests.

## Stop Rules

- Do not run broad `git add .`.
- Do not commit generated `output/` artifacts without explicit artifact policy.
- Do not promote local verification to production evidence.
- Do not deploy, push, merge, call providers, change env, write object storage, run schema migration, or run production write-path smoke from this plan.
