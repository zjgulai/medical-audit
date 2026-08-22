---
title: "Frontend Interaction Gap Audit And Remediation Plan"
doc_type: analysis-plan
module: frontend
created: 2026-07-04
updated: 2026-08-13
owner: self
source: human+ai
project: "medical_audit"
created_at: "2026-07-04T15:48:00+08:00"
status: "superseded"
evidence_level: "local-browser-plus-maintained-e2e-plus-local-frontend-gates"
branch: "codex/frontend-ai-replica-20260703"
boundary:
  production: "production unchanged"
  provider_call: "no provider call"
  database_write: "none"
  backend_runtime: "127.0.0.1:8021 not started"
  deploy: "not executed"
---

# Frontend Interaction Gap Audit And Remediation Plan

## First-Principles Contract

A user-facing interaction is acceptable only when it has all four parts:

1. Clear trigger: the user can identify what to click, type, close, or submit.
2. Deterministic result: the action changes route, state, selection, modal, or feedback.
3. Recovery path: the user can cancel, close, go back, or understand why a gated action did not run.
4. Evidence boundary: local preview, fixture fallback, API read, mutation, provider call, and production result are not collapsed.

This audit compares the current AI replica/Next frontend against the older boundary docs:

- Jinja deep pages keep write-heavy audit closure flows.
- Next portal owns navigation, dashboard, read/light interactions, and replica pages.
- Loop 1 froze the 9-page replica baseline.
- Loop 2 classified fixture-only, partial-schema-gap, new-api-needed, and mutation-gated surfaces.

## Evidence

- Accepted browser audit report: `web/output/playwright/interaction-audit-20260704T-interaction-gap-afterfix/report.json`
- Accepted screenshots: `web/output/playwright/interaction-audit-20260704T-interaction-gap-afterfix/*.png`
- Maintained Playwright interaction spec: `web/tests/e2e/interaction-contract.spec.ts`
- Maintained Playwright foundation spec refreshed for the current replica UI: `web/tests/e2e/foundation.spec.ts`
- Scope: 20 routes, 56 interaction checks.
- Accepted result: 52 pass, 4 warn, 0 fail.
- Local gates after repair:
  - `corepack pnpm --filter medical-audit-web lint`: pass.
  - `corepack pnpm --filter medical-audit-web typecheck`: pass.
  - `corepack pnpm --filter medical-audit-web test`: pass, 18 files / 119 tests.
  - `corepack pnpm --filter medical-audit-web build`: pass, 24 static pages.
  - `PLAYWRIGHT_USE_SYSTEM_CHROME=1 PLAYWRIGHT_REUSE_SERVER=1 corepack pnpm --filter medical-audit-web exec playwright test tests/e2e/interaction-contract.spec.ts --project=chromium`: pass, 3 tests.
  - `PLAYWRIGHT_USE_SYSTEM_CHROME=1 PLAYWRIGHT_REUSE_SERVER=1 corepack pnpm --filter medical-audit-web exec playwright test tests/e2e/foundation.spec.ts --project=chromium`: pass, 17 tests.
  - `PLAYWRIGHT_USE_SYSTEM_CHROME=1 PLAYWRIGHT_REUSE_SERVER=1 corepack pnpm --filter medical-audit-web exec playwright test --project=chromium`: pass, 20 tests.

## Route Summary

| Route | Primary H1 | Buttons | Links | Overflow | Runtime Signal |
| --- | --- | ---: | ---: | ---: | --- |
| `/login` | 欢迎登录 | 2 | 1 | 0 | clean |
| `/workspace` | 医保基金使用合规专项自查 | 12 | 11 | 0 | backend 8021 offline console 500 x2 |
| `/chat` | 您好，有什么我能帮您的吗？ | 25 | 11 | 0 | clean |
| `/agents` | 我的智能体 | 40 | 11 | 0 | clean |
| `/agent-market` | 智能体广场 | 29 | 11 | 0 | clean |
| `/knowledge-base` | 知识库总览 | 22 | 11 | 0 | clean |
| `/documents` | 文档检索 | 25 | 11 | 0 | clean |
| `/analytics` | AI数据分析 | 16 | 11 | 0 | clean |
| `/graph` | 知识图谱 | 22 | 11 | 0 | clean |
| `/reports` | 底稿与报告 | 13 | 11 | 0 | clean |
| `/projects` | 项目管理 | 14 | 11 | 0 | clean |
| `/medical-audit` | 医保审计 | 40 | 11 | 0 | clean |
| `/fund-compliance` | 基金合规自查 | 12 | 17 | 0 | clean |
| `/fund-compliance/review` | 专题审计工作台 | 17 | 11 | 0 | clean |
| `/guided-check` | AI 引导自查工作台 | 12 | 20 | 0 | clean |
| `/rules` | 审计规则与依据总览 | 12 | 20 | 0 | backend 8021 offline console 500 x2 |
| `/remediation` | 整改事项与补证闭环 | 12 | 20 | 0 | backend 8021 offline console 500 x1 |
| `/archive` | 项目档案与审计日志归档 | 12 | 20 | 0 | backend 8021 offline console 500 x2 |
| `/findings` | 规则命中疑点工作台 | 12 | 11 | 0 | backend 8021 offline console 500 x1 |
| `/knowledge-query` | 引用优先的知识查询 | 13 | 12 | 0 | clean |

## Interaction Flow Summary

| Surface | Flow | Result |
| --- | --- | --- |
| `/login` | Toggle password visibility | pass, local state changes password field type. |
| `/login` | Submit login | pass after repair, redirects to `/workspace` without account/password query params. |
| Shell | Main nav to `/chat`, `/agents`, `/agent-market`, `/knowledge-base`, `/documents`, `/analytics`, `/graph`, `/reports`, `/projects`, `/medical-audit` | pass, route changes match href. |
| Shell | Collapse sidebar | pass, visible shell state changes. |
| Shell | Close active page tag | pass after repair, close control is a real button and hides current tag. |
| Shell | History item click | warning, current items are button-shaped but do not load a conversation or navigate. |
| `/chat` | Send question | pass, creates local preview and preserves no-provider boundary. |
| `/chat` | Upload attachment | source check confirms local gated notice, audit selector used old label in accepted run. |
| `/agents` | View detail, edit, history, delete, create | pass, all remain local state with no backend lifecycle write. |
| `/agent-market` | Search and create copy | pass, copy action remains local and no backend write. |
| `/knowledge-base` | Search, new knowledge base, view card | pass, catalog actions are local gated states. |
| `/documents` | History chip, title-only toggle, search, clear history | pass by source behavior; accepted audit recorded a weak visual-diff warning for clear history. |
| `/analytics` | Switch chart tab, start analysis | pass, local result state; no upload/backend call. |
| `/graph` | Search/filter, new graph | pass by source behavior; accepted audit recorded a weak visual-diff warning for one filter state. |
| `/reports` | Generate without selection, select history, generate with selection | pass, local preview only. |
| `/projects` | Search, new project modal, cancel, modify modal, confirm | pass, local modal state and no project API write. |
| `/medical-audit` | Switch audit dimension, risk filter, finding detail, confirm violation, AI drawer, AI message, three form tabs | pass, local no-provider/no-backend boundary preserved. |
| `/fund-compliance` | Enter review | pass, route changes to `/fund-compliance/review`. |
| `/fund-compliance/review` | Rule/form tabs, table 2/3 tabs, new custom form create | pass, three Excel-style templates plus custom form path remain usable. |

## Findings

### Fixed In This Loop

1. P0 Login leaked password in URL.
   - Evidence before fix: `/workspace?account=demo_user&password=demo_password`.
   - Fix: remove `name` attributes from credential fields and handle submit with `window.location.assign("/workspace")`.
   - Verification: accepted browser audit shows target URL `http://127.0.0.1:3030/workspace`.

2. P1 Page tag close icon was decorative only.
   - Evidence before fix: `.replica-page-tag-close` was a non-focusable `span`.
   - Fix: replace it with a real `button` labelled `关闭{tag}页签`, preserving visual style.
   - Verification: accepted browser audit marks `shell / close-page-tag` pass; new component test covers close behavior.

### Remaining Gaps

1. P0 Local fullstack boundary is still open but now visibly bounded.
   - `/workspace`, `/rules`, `/remediation`, `/archive`, and `/findings` show console 500s when backend `127.0.0.1:8021` is not running.
   - This is not a frontend build failure. The visible UI now labels offline read surfaces as local samples instead of implying normal connectivity.
   - Remaining risk: without Playwright route mocks or a running backend, the browser network layer can still record failed read requests.

2. P1 Shell history semantics are now deterministic.
   - History entries navigate to `/chat?history={id}`.
   - Remaining contract work: the chat page does not yet hydrate a specific historical conversation from the query string.

3. P1 Many replica actions are intentionally local gates.
   - Agents create/edit/delete, marketplace copy, knowledge base create/view, analytics upload/generation, graph create, reports generation, and projects create/modify are not real writes.
   - This is acceptable only if the UI consistently says local preview/no write; otherwise users will overestimate readiness.

4. P1 Old Jinja/Next overlap remains a product navigation debt.
   - `/chat`, `/reports`, `/findings`, `/knowledge-query`, and Jinja deep pages still represent overlapping concepts.
   - The older architecture doc says write-heavy closure flows stay in Jinja; current replica pages should not imply they own those writes.

5. P2 Permanent E2E coverage is not yet product-grade.
   - The temporary audit runner proved the interaction surface, but it should be promoted into a maintained Playwright test only after selectors and backend-mode assumptions are cleaned up.

## Remediation TODO

### Batch 1 Completed

- [x] Repair login credential leakage.
- [x] Repair page tag close affordance.
- [x] Add targeted tests for login submit boundary and tag close.
- [x] Run local browser audit before/after.
- [x] Run frontend lint/typecheck/test/build.

### Batch 2 Recommended Next

- [x] Add backend-offline graceful UI for routes that call `/health`, `/index/search-backend`, `/rules/workbench`, `/remediation/workbench`, and `/archive/workbench`.
- [x] Decide shell history semantics: history entries now navigate to `/chat?history={id}`.
- [ ] Normalize all local-gated actions to one visible pattern: action accepted locally, remote write not executed, next owner/API needed.
- [x] Add a maintained Playwright spec for login, shell history, shell close, backend-offline read surfaces, medical-audit drawer/forms, and fund-compliance form creation.
- [x] Refresh the foundation Playwright spec to match the current AI replica UI instead of obsolete portal copy and legacy backend workflows.
- [ ] Re-run with local backend `8021` started to separate frontend interaction health from API contract health.

### Batch 3 Contract Work

- [ ] Convert fixture-only knowledge-base catalog to a read API only after catalog ownership is settled.
- [ ] Define marketplace clone/install contract before wiring `创建副本`.
- [ ] Define graph creation contract before wiring `新建图谱`.
- [ ] Define report-generation job contract before wiring true one-click workpaper generation.
- [ ] Keep Jinja write-heavy review/signoff/export flows explicitly linked or clearly outside the replica pages.

## Stop Rules

- Do not claim fullstack readiness from this audit alone.
- Do not claim production updated.
- Do not wire mutation/provider/upload actions without explicit authorization.
- Do not stage this mixed dirty worktree wholesale.
