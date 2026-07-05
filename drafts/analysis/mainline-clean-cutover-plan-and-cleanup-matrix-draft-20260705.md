---
title: Mainline Clean Cutover Plan And Cleanup Matrix
date: 2026-07-05
project: medical_audit
status: verified-local
scope: local-integration
production_changed: false
---

# Mainline Clean Cutover Plan And Cleanup Matrix

## First-Principles Target

The new refactored website becomes the only frontend product line. Old frontend pages are not incrementally patched; they are either redirected to the new product surface or removed when no longer referenced.

Backend and knowledge-base changes from `codex/frontend-ai-replica-20260703` are included in this mainline integration because the new frontend is allowed to drive the next backend contract.

## Execution Boundaries

- Worktree: `/Users/pray/.config/superpowers/worktrees/medical_audit/mainline-clean-cutover-20260705`
- Branch: `codex/mainline-clean-cutover-20260705`
- Base: `main`
- Included local commit: `chore: ignore local evidence artifacts`
- Included refactor branch: `codex/frontend-ai-replica-20260703`
- Production side effect: none
- Backup: `/Users/pray/.Codex/file-history/medical_audit/20260705T1542-mainline-cutover-premerge.tar.gz`

## Route Cutover Matrix

| Old route | New behavior | Reason |
| --- | --- | --- |
| `/` | redirect to `/chat` | Remove old dashboard shell from default entry. |
| `/workspace` | redirect to `/chat` | Remove old project dashboard workspace. |
| `/findings` | redirect to `/medical-audit` | Findings are now part of the medical audit topic workbench. |
| `/fund-compliance` | redirect to `/medical-audit` | Legacy fund topic is replaced by the refactored topic workbench. |
| `/fund-compliance/review` | redirect to `/medical-audit` | Legacy review table is replaced by the refactored topic workbench. |
| `/guided-check` | redirect to `/chat` | Guided self-check becomes an AI chat entry pattern. |
| `/knowledge-query` | redirect to `/documents` | Query workbench is replaced by document search and knowledge pages. |
| `/rules` | redirect to `/knowledge-base` | Rule review moves into knowledge-base backed evidence surfaces. |
| `/remediation` | redirect to `/medical-audit` | Remediation is part of the audit topic workflow. |
| `/archive` | redirect to `/reports` | Archive/report work is consolidated under workpaper/report surfaces. |

## Removed Legacy Frontend Surfaces

- Old dashboard shell: `web/src/components/dashboard/*`
- Old workspace shell: `web/src/components/shell/*` except `brand-logo.tsx`
- Old findings workbench: `web/src/components/findings/*`
- Old query workbench: `web/src/components/query/*`
- Old portal workbenches: `web/src/components/portal/*`
- Old UI primitives used only by legacy pages: `web/src/components/ui/*`
- Old navigation/project/workflow helpers: `web/src/lib/navigation.ts`, `web/src/lib/projects.ts`, `web/src/lib/workflow.ts`
- Old static prompt dump: `web/src/data/audit-agent-prompts.json`

## Kept Frontend Surfaces

- Refactored shell: `web/src/components/replica/*`
- Refactored data contracts and adapters: `web/src/lib/api-*`, `web/src/lib/replica-adapters.ts`, `web/src/lib/reference-replica-data.ts`
- Refactored product pages: `/chat`, `/agents`, `/agent-market`, `/knowledge-base`, `/documents`, `/analytics`, `/graph`, `/reports`, `/projects`, `/medical-audit`
- Login brand asset: `web/src/components/shell/brand-logo.tsx`

## Verification TODO

1. Completed: import/reference scan after cleanup.
2. Completed: frontend typecheck, lint, unit tests, and build.
3. Completed: KB/backend contract tests.
4. Completed: local production-style frontend smoke.
5. Pending external gate: after production login wall is removed, run authenticated read-only production baseline comparison.

## Verification Evidence

All evidence below is local or local production-style validation. It does not imply a production deploy.

| Layer | Command | Result |
| --- | --- | --- |
| Import cleanup | `rg "@/components/(dashboard|shell/(ai-chat-fab|app-sidebar|audit-user-context|project-context-bar|workspace-shell)|findings|portal|query|ui)|@/lib/(audit-user|navigation|projects|workflow|portal-data)|audit-agent-prompts|WorkspaceShell|ProjectDashboard|AuditFindingsWorkbench|KnowledgeQueryWorkbench|StatusPill|DataSourceBadge|ModuleCard" web/src web/tests web/scripts -S` | No legacy references returned. |
| Frontend typecheck | `pnpm web:typecheck` | Passed. |
| Frontend lint | `pnpm web:lint` | Passed. |
| Frontend unit tests | `pnpm web:test` | Passed: 10 files, 59 tests. |
| Frontend production build | `pnpm web:build` | Passed: 24 app routes generated. |
| KB/backend tests | `uv run pytest tests/knowledge_query` | Passed: 435 tests, 1 dependency warning. |
| Production-like smoke | `pnpm web:smoke:prodlike` | Passed: build, 29 interaction steps, 7 Playwright E2E tests. |

## Explicit Non-Goals For This Cutover

- No production write.
- No provider call.
- No backend write.
- No deploy.
- No cleanup in the original dirty worktree.
