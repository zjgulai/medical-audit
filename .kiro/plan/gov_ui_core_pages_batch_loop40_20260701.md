---
title: "Loop40 Government UI Core Pages Batch"
project: "medical_audit"
date: "2026-07-01"
status: "verified-local"
scope: "local-ui"
production: "unchanged"
provider_calls: "none"
---

# Loop40 Government UI Core Pages Batch

## Objective

Execute the Batch 2 core business page simplification after Loop39 verified the shared shell. This loop focuses on the first viewport and user-facing language of the most visible product paths.

## Scope

- `web/src/app/(workspace)/fund-compliance/page.tsx`
- `web/src/app/(workspace)/fund-compliance/review/page.tsx`
- `web/src/app/(workspace)/chat/page.tsx`
- `web/src/app/(workspace)/agent-market/page.tsx`
- `web/src/components/shell/app-sidebar.tsx`
- `web/src/components/shell/ai-chat-fab.tsx`
- `web/src/lib/navigation.ts`
- `web/src/app/(workspace)/workspace-pages.test.tsx`
- `web/tests/e2e/foundation.spec.ts`
- `scripts/run-production-frontend-acceptance.mjs`

## Changes

- Topic landing page: first viewport reduced to one title, one short description, three KPI values, and one primary action.
- Review workbench: header gains one plain orientation sentence; workflow tabs use the same square-radius system as the shell.
- Chat page: visible wording moves from `AI/智能体/提示词/知识来源` to `审计助手/核验方法/依据范围`.
- Assistant library: visible wording moves from `智能体广场/审计提示词智能体` to `审计助手库`; search and empty states use user-facing helper language.
- Assistant library cards now behave as compact entry cards: short name, one tag, and open action only. Detailed scene and method stay in the dialog.
- Sidebar utility naming is aligned to `助手库`, and the utility list shows pinned items first with the rest under `全部功能`.
- Mobile floating AI entry is reduced to `44px` with `16px` safe-edge spacing to avoid covering form content.

## Out Of Scope

- Route removal, API contract changes, form behavior changes, schema changes, provider calls, production checks, deployment, Docker changes, or write-path smoke.
- Page families outside Batch 2.

## Acceptance Targets

- `/fund-compliance` first viewport has at most three KPI values and one primary action.
- `/chat` does not expose raw prompt text by default and uses task-oriented labels.
- `/agent-market` keeps card names compact and does not show Markdown artifacts on the grid.
- `/fund-compliance/review` keeps the table/template workflow intact.
- Local tests and browser checks provide fresh evidence before completion.

## Verification

- `git diff --check`: pass.
- `CI=true corepack pnpm@9.15.0 --filter medical-audit-web test`: pass, `11` files, `94` tests.
- `CI=true corepack pnpm@9.15.0 --filter medical-audit-web typecheck`: pass.
- `CI=true corepack pnpm@9.15.0 --filter medical-audit-web lint`: pass.
- Browser artifact directory: `output/playwright/loop40-gov-core-pages-20260701T184500+0800/`.
- Browser metrics file: `output/playwright/loop40-gov-core-pages-20260701T184500+0800/loop40-browser-metrics.json`.

## Browser Results

| Route | Viewport | H1 | Overflow X | First-viewport chars | Notes |
| --- | --- | --- | ---: | ---: | --- |
| `/fund-compliance` | 1280x900 | 医保基金使用合规专项自查 | 0 | 655 | 3 KPI values, one primary action |
| `/fund-compliance/review` | 1280x900 | 专题审计工作台 | 0 | 460 | Review workflow preserved |
| `/chat` | 1280x900 | 审计问答 | 0 | 438 | Raw prompt stays behind details |
| `/agent-market` | 1280x900 | 审计助手库 | 0 | 521 | Reduced from 1276 before compact-card pass |
| `/fund-compliance` | 390x844 | 医保基金使用合规专项自查 | 0 | 203 | Mobile KPI layout stable |
| `/chat` | 390x844 | 审计问答 | 0 | 235 | Floating AI button is 44px |
| `/agent-market` | 390x844 | 审计助手库 | 0 | 293 | Compact entry cards |

Old visible terms checked and absent from page body in the browser pass:

- `智能体广场`
- `审计提示词智能体`
- `查看提示词`
- `知识来源`
- `进入专题工作台`
- `规则导航`
- `B2B`
- `当前智能体`
- `复制原始提示词`
- `搜索智能体`
- `AI 审证对话`
- `助手广场`

## Local-Dev Note

The browser console still records local backend proxy messages for `/auth/session` because this loop did not start the backend service on `127.0.0.1:8021`. These messages are not backend acceptance evidence and were not used to claim fullstack readiness.
