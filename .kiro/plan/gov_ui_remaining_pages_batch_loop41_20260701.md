---
title: "Loop41 Government UI Remaining Workspace Pages Batch"
project: "medical_audit"
date: "2026-07-01"
status: "verified-local"
scope: "local-ui"
production: "unchanged"
provider_calls: "none"
---

# Loop41 Government UI Remaining Workspace Pages Batch

## Objective

Execute Batch 3 after Loop39 shell cleanup and Loop40 core-page cleanup. This loop focuses on the remaining dense workspace pages that still exposed backend-style terms, wide table patterns, or too many first-viewport chips.

## Scope

- `web/src/app/(workspace)/documents/page.tsx`
- `web/src/app/(workspace)/knowledge-base/page.tsx`
- `web/src/components/portal/data-analysis-workbench.tsx`
- `web/src/app/(workspace)/reports/page.tsx`
- `web/src/components/portal/project-management-workbench.tsx`
- `web/src/app/(workspace)/workspace-pages.test.tsx`
- `web/tests/e2e/foundation.spec.ts`
- `scripts/run-production-frontend-acceptance.mjs`
- `scripts/run-production-documents-readonly-probe.py`

## Changes

- Documents: changed the page from a three-column dense layout to a single-column evidence search flow; source cards move to the top and expose only user-facing source labels.
- Documents: visible backend terms such as raw source collection ids, `confidence`, `fallback`, and `query_log_index` were replaced with audit-facing labels.
- Knowledge base: renamed the page to `知识库总览`, reduced the metric grid, and replaced the wide catalog table with compact source cards.
- Analytics: changed `上传表格分析工作台` to `费用表单分析`, moved template selection to the top, reduced visible tool-status noise, and kept the three fee templates selectable.
- Reports: changed `底稿生成与报告记录` to `底稿与报告`, moved workflow guidance to a compact top band, renamed `提示词模板生成` to `底稿模板`, and reduced visible evidence binding chips.
- Projects: changed `审计项目管理` to `项目与成员`, moved project switching to a compact top band, and replaced mobile project/member tables with mobile cards while preserving desktop tables.
- Acceptance scripts and tests now use the new visible wording as the contract.

## Out Of Scope

- Route removal, API contract changes, data ingestion changes, schema changes, provider calls, production checks, deployment, Docker changes, or write-path smoke.
- Full backend availability proof; the local browser run used frontend fallback behavior where the backend target on `127.0.0.1:8021` was unavailable.

## Verification

- `git diff --check`: pass.
- `CI=true corepack pnpm@9.15.0 --filter medical-audit-web test -- 'src/app/(workspace)/workspace-pages.test.tsx'`: pass, `30` tests.
- `corepack pnpm@9.15.0 --filter medical-audit-web typecheck`: pass.
- `corepack pnpm@9.15.0 --filter medical-audit-web lint`: pass.
- `CI=true corepack pnpm@9.15.0 --filter medical-audit-web test`: pass, `11` files, `94` tests.
- `corepack pnpm@9.15.0 --filter medical-audit-web build`: pass, `23` static pages.
- Browser metric file: `tmp/outputs/loop41-ui-density/density-report.json`.
- Browser screenshots: `tmp/outputs/loop41-ui-density/*.png`.

## Browser Results

| Route | Viewport | H1 | Overflow X | First-viewport chars | First-viewport nodes |
| --- | --- | --- | ---: | ---: | ---: |
| `/documents` | 1440x1000 | 文档依据检索 | 0 | 293 | 41 |
| `/knowledge-base` | 1440x1000 | 知识库总览 | 0 | 285 | 30 |
| `/analytics` | 1440x1000 | 费用表单分析 | 0 | 643 | 46 |
| `/reports` | 1440x1000 | 底稿与报告 | 0 | 889 | 60 |
| `/projects` | 1440x1000 | 项目与成员 | 0 | 692 | 85 |
| `/documents` | 390x844 | 文档依据检索 | 0 | 189 | 24 |
| `/knowledge-base` | 390x844 | 知识库总览 | 0 | 151 | 18 |
| `/analytics` | 390x844 | 费用表单分析 | 0 | 464 | 24 |
| `/reports` | 390x844 | 底稿与报告 | 0 | 523 | 27 |
| `/projects` | 390x844 | 项目与成员 | 0 | 245 | 27 |

## Local-Dev Note

The browser server emitted local backend proxy messages because this loop did not start the backend service on `127.0.0.1:8021`. This loop is local frontend UI evidence only.

## Boundary

- Local UI and tests only.
- Production remained unchanged.
- No push, merge, deployment, production probe, provider call, env write, object storage write, schema migration, Docker change, or write-path smoke is part of this loop.
