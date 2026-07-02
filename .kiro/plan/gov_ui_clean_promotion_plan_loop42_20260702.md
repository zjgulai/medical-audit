---
title: "Loop42 Government UI Clean Promotion Plan"
project: "medical_audit"
date: "2026-07-02"
status: "verified-local-plan"
scope: "promotion-plan"
production: "unchanged"
provider_calls: "none"
---

# Loop42 Government UI Clean Promotion Plan

## Objective

Define the clean promotion path for the Loop39, Loop40, and Loop41 government-style UI work. This loop does not stage, commit, push, merge, deploy, probe production, call providers, touch Docker, or run write-path smoke.

## Observed State

- Branch: `codex/frontend-2.0`.
- Current branch is ahead of `origin/codex/frontend-2.0` by `69` commits.
- Git index was empty before this plan: `git diff --cached --name-only` returned no paths.
- Candidate business change set contains `31` paths.
- Local evidence artifacts under `output/` contain `153` untracked files and must be excluded from the promotion set.
- `tmp/outputs/loop41-ui-density/` remains local evidence only and is not part of the promotion set.

## Promotion Candidate Set

### Planning Docs

- `.kiro/plan/findings.md`
- `.kiro/plan/gov_ui_core_pages_batch_loop40_20260701.md`
- `.kiro/plan/gov_ui_remaining_pages_batch_loop41_20260701.md`
- `.kiro/plan/gov_ui_shell_batch_loop39_20260701.md`
- `.kiro/plan/gov_ui_typography_batch_plan_loop38_20260701.md`
- `.kiro/plan/progress.md`
- `.kiro/plan/release_manifest.md`
- `.kiro/plan/task_plan.md`

### Acceptance Scripts

- `scripts/run-production-documents-readonly-probe.py`
- `scripts/run-production-frontend-acceptance.mjs`

### Frontend Routes And Components

- `web/src/app/(workspace)/agent-market/page.tsx`
- `web/src/app/(workspace)/chat/page.tsx`
- `web/src/app/(workspace)/documents/page.tsx`
- `web/src/app/(workspace)/fund-compliance/page.tsx`
- `web/src/app/(workspace)/fund-compliance/review/page.tsx`
- `web/src/app/(workspace)/knowledge-base/page.tsx`
- `web/src/app/(workspace)/reports/page.tsx`
- `web/src/app/globals.css`
- `web/src/app/layout.tsx`
- `web/src/app/login/page.tsx`
- `web/src/components/portal/data-analysis-workbench.tsx`
- `web/src/components/portal/project-management-workbench.tsx`
- `web/src/components/shell/ai-chat-fab.tsx`
- `web/src/components/shell/app-sidebar.tsx`
- `web/src/components/shell/project-context-bar.tsx`
- `web/src/lib/navigation.ts`

### Tests

- `web/src/app/(workspace)/workspace-pages.test.tsx`
- `web/src/app/login/page.test.tsx`
- `web/src/components/shell/workspace-shell.test.tsx`
- `web/src/lib/navigation.test.ts`
- `web/tests/e2e/foundation.spec.ts`

## Excluded From Promotion

- `output/`: local screenshots, metrics, and historical browser evidence.
- `tmp/outputs/`: local evidence output only.
- Any production reports, deployment reports, provider logs, database dumps, object-storage artifacts, or Docker state.

## Verification

- `git diff --check`: pass.
- `git diff --cached --name-only`: empty output, no staged paths.
- `corepack pnpm@9.15.0 --filter medical-audit-web typecheck`: pass.
- `corepack pnpm@9.15.0 --filter medical-audit-web lint`: pass.
- `CI=true corepack pnpm@9.15.0 --filter medical-audit-web test`: pass, `11` files, `94` tests.
- `corepack pnpm@9.15.0 --filter medical-audit-web build`: pass, `23` static pages.

## Recommended Next Loop

Loop43 should be an explicit staging or clean-worktree execution gate:

1. Reconfirm the `31` candidate paths.
2. Keep `output/` and `tmp/outputs/` excluded.
3. Stage the candidate set only if explicitly authorized.
4. Commit locally only if explicitly authorized.
5. Stop before push, merge, deployment, production probe, provider call, Docker change, or write-path smoke unless the user separately authorizes that evidence grade.

## Boundary

- This is a local promotion-plan loop.
- Production remained unchanged.
- No staging, commit, push, merge, deployment, production probe, provider call, env write, object storage write, schema migration, Docker change, or write-path smoke was executed.
