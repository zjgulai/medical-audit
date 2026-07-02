---
title: "Loop39 Government UI Shell Batch"
project: "medical_audit"
date: "2026-07-01"
status: "verified-local"
scope: "local-ui"
production: "unchanged"
provider_calls: "none"
---

# Loop39 Government UI Shell Batch

## Objective

Reduce the visible UI density of the current portal shell before wider page-level redesign work. The batch applies government-style constraints to the shared shell first: restrained color tokens, smaller type scale, fewer visible navigation entries, and a simpler top bar.

## First Principles

- Users need to identify the current work area quickly; the shell should not compete with page content.
- Most audit work starts from a small set of high-frequency routes; long-tail modules should stay reachable but should not occupy the main navigation row.
- Medical audit pages need table readability and numeric alignment more than decorative visual effects.
- AI wording should be used only when it helps the operator understand a task boundary.

## Implementation Scope

- Global design tokens and typography in `web/src/app/globals.css`.
- Shell navigation information architecture in `web/src/lib/navigation.ts`.
- Sidebar rendering in `web/src/components/shell/app-sidebar.tsx`.
- Top bar rendering in `web/src/components/shell/project-context-bar.tsx`.
- Site metadata and login-page brand wording in `web/src/app/layout.tsx` and `web/src/app/login/page.tsx`.
- Shell/navigation tests in `web/src/components/shell/workspace-shell.test.tsx` and `web/src/lib/navigation.test.ts`.

## Out Of Scope

- Production deploy, production probe, provider call, env write, schema migration, object storage write, Docker change, or write-path smoke.
- Removing existing routes or backend capability.
- Rewriting page-level business flows outside shell wording and shared typography.

## Acceptance Targets

- Main sidebar shows five common entries: workbench, fund compliance, audit assistant, document evidence, and project archive.
- Additional modules remain addressable through a folded utility section and route lookup.
- Top bar no longer stacks module tags, connection status, draft status, role pills, and tabs in one horizontal row.
- Global typography is smaller and more table-friendly, with tabular numbers for metrics and tables.
- Local tests and browser checks provide fresh evidence before any completion claim.

## Local Verification

- `git diff --check`: pass.
- `CI=true corepack pnpm@9.15.0 --filter medical-audit-web test -- src/components/shell/workspace-shell.test.tsx src/lib/navigation.test.ts`: pass, 2 files, 18 tests.
- `CI=true corepack pnpm@9.15.0 --filter medical-audit-web typecheck`: pass.
- `CI=true corepack pnpm@9.15.0 --filter medical-audit-web lint`: pass.
- `CI=true corepack pnpm@9.15.0 --filter medical-audit-web test`: pass, 11 files, 94 tests.

## Browser Verification

Local URL: `http://localhost:3030`

- `/workspace` desktop `1280x720`: horizontal overflow `0`; main navigation count `5`; screenshot `output/playwright/loop39-gov-shell-20260701T183200+0800/workspace-desktop.png`.
- `/workspace` mobile `390x844`: horizontal overflow `0`; main navigation count `5`; labels `工作台`, `基金合规`, `审计助手`, `文档依据`, `项目归档`; screenshot `output/playwright/loop39-gov-shell-20260701T183200+0800/workspace-mobile.png`.
- `/chat` desktop `1280x720`: horizontal overflow `0`; active main navigation `审计助手`; main navigation count `5`.
- `/fund-compliance/review` desktop `1280x720`: horizontal overflow `0`; active main navigation `基金合规`; H1 `专题审计工作台`; screenshot `output/playwright/loop39-gov-shell-20260701T183200+0800/fund-compliance-review-desktop.png`.

Local browser console notes:

- `favicon.ico` returned 404 in local dev.
- `/api/v1/auth/session`, `/api/backend/health`, and `/api/backend/index/search-backend` returned 500 because the local dev check did not start the backend proxy target. This loop only verifies local UI shell behavior and does not claim backend integration status.
