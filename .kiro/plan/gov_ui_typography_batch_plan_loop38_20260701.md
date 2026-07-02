---
title: "medical_audit Loop 38 government-style UI and typography batch plan"
project: "medical_audit"
created_at: "2026-07-01T17:43:00+08:00"
status: "planning-only"
evidence_grade: "repo-and-reference-derived"
source_loop: "Loop 37 docs-only local commit"
business_code_changed: false
production_unchanged: true
deployed_sha: "b1c9a6c229a7880afcbfed35c1903d514914bb15"
---

# Loop 38 Government-Style UI And Typography Batch Plan

## Design Read

Reading this as a regulated medical-audit workspace for hospital audit staff and administrators, with a trust-first public-service visual language, leaning toward a restrained government service system rather than an AI SaaS template.

Dial settings:

- `design_variance=3`: stable, regular, institution-first.
- `motion_intensity=2`: minimal motion, state changes only.
- `visual_density=5`: operationally useful, but not visually crowded.

## Merged Requirement

The typography layer is part of the batch redesign plan, not a later polish item.

The plan now treats these as one coupled system:

- information architecture;
- shell and navigation hierarchy;
- page template density;
- color and surface tokens;
- typography family, size, line-height, numeric alignment, and responsive scaling;
- copy simplification and backend-language removal;
- browser evidence and overflow acceptance.

## Reference Translation

The external government-style reference is translated into reusable product constraints:

- Trust: official blue, white surfaces, stable title hierarchy, limited accent use.
- Order: one navigation level in the first viewport, clear page title, fewer chips.
- Service clarity: task-first labels, visible primary action, no raw implementation vocabulary.
- Readability: fewer cards, more tables/lists where the job is comparison or review.
- Accessibility: visible focus, keyboard-safe controls, responsive navigation, long text containment.

The reference content, image assets, and topic scope are not copied into this product.

## Typography Contract

### Font Family

Use a system-first Chinese UI stack:

```css
--audit-font-sans: "PingFang SC", "Noto Sans CJK SC", "Microsoft YaHei", "SF Pro Text", system-ui, sans-serif;
--audit-font-mono: "SF Mono", "JetBrains Mono", "Roboto Mono", monospace;
```

Rules:

- no decorative serif for this product;
- no mixed display font for emphasis;
- no oversized marketing-style hero typography inside operational pages;
- use mono only for IDs, amounts, dates, version keys, and counts that need alignment.

### Type Scale

Desktop target:

- Page title: `24px / 32px`, weight `650`.
- Section title: `18px / 28px`, weight `650`.
- Card title: `15px / 22px`, weight `650`.
- Body: `14px / 24px`, weight `400`.
- Meta/helper: `12px / 18px`, weight `400`.
- Table header: `13px / 20px`, weight `650`.
- Table cell: `14px / 22px`, weight `400`.
- KPI value: `24px / 32px`, weight `650`, tabular numbers.

Mobile target:

- Page title: `22px / 30px`.
- Section title: `17px / 26px`.
- Body: `14px / 23px`.
- Meta/helper: `12px / 18px`.
- Table cell: keep `14px`, allow horizontal table scroll only inside table shell.

Rules:

- no viewport-width font scaling;
- all letter spacing remains `0`;
- headings use `text-wrap: balance` where supported;
- text containers use `min-w-0`, `truncate`, `line-clamp`, or `break-words`;
- table and KPI numbers use `font-variant-numeric: tabular-nums`.

## Batch Design Actions

### Batch 1: Global Tokens And Shell

Files:

- `web/src/app/globals.css`
- `web/src/components/shell/workspace-shell.tsx`
- `web/src/components/shell/app-sidebar.tsx`
- `web/src/components/shell/project-context-bar.tsx`
- `web/src/lib/navigation.ts`

Actions:

- remove grid/radial AI-style background;
- replace with flat public-service background and restrained white surfaces;
- reduce shadow strength and keep border-led hierarchy;
- cap desktop navigation height at 64-72px;
- collapse secondary/system routes behind a management menu;
- remove topic/status chip crowding from the top bar;
- apply the typography scale and tabular number utility globally.

Acceptance:

- desktop top bar stays one line at `1024px`;
- mobile first viewport shows page title and main task within the first screen;
- no horizontal shell overflow;
- no visible backend vocabulary in ordinary user shell.

### Batch 2: Core Business Pages

Files:

- `web/src/app/(workspace)/fund-compliance/page.tsx`
- `web/src/app/(workspace)/fund-compliance/review/page.tsx`
- `web/src/app/(workspace)/chat/page.tsx`
- `web/src/app/(workspace)/agent-market/page.tsx`

Actions:

- topic page first viewport: title, batch, 3 KPI max, one primary action;
- move rule navigation and modules into tabs or secondary sections;
- review page prioritizes table, filters, and detail drawer;
- AI page hides raw prompt by default and shortens instructional copy;
- agent market becomes audit assistant library with short names, one-line scene, and drawer detail.

Acceptance:

- first viewport has at most one primary button, three status pills, four KPI values, and two short explanatory lines;
- no prompt raw text visible on card grid;
- agent cards remain readable at mobile width;
- all action labels are task-oriented.

### Batch 3: Knowledge, Evidence, And Archive Pages

Files:

- `web/src/app/(workspace)/documents/page.tsx`
- `web/src/app/(workspace)/knowledge-base/page.tsx`
- `web/src/app/(workspace)/rules/page.tsx`
- `web/src/app/(workspace)/reports/page.tsx`
- `web/src/app/(workspace)/archive/page.tsx`
- `web/src/app/(workspace)/graph/page.tsx`

Actions:

- unify page header and section layout;
- replace internal labels with user-facing evidence language;
- use lists/tables instead of repeated cards where users compare records;
- add consistent empty and loading states;
- constrain long titles and source names.

Acceptance:

- page headers share title/body/action rhythm;
- tables use the same header/cell typography;
- long document names do not stretch layout;
- source/status labels map to user-facing terms.

### Batch 4: Verification And Release Boundary

Local checks:

- `lint`
- `typecheck`
- focused component tests for shell, workspace, and topic pages;
- Playwright desktop/mobile screenshots for `workspace`, `fund-compliance`, `fund-compliance/review`, `chat`, `agent-market`, `documents`;
- horizontal overflow scan;
- first-viewport density scan.

Evidence boundary:

- local code and browser checks only until a separate deploy gate is selected;
- production remains unchanged until explicit deploy execution authorization.

## Copy Replacement Table

- `AI智能审计管理系统` -> `医保智能审计平台`
- `智能体` -> `审计助手`
- `提示词` -> `核验方法`
- `后端` -> `服务状态` or hidden
- `索引` -> `依据同步`
- `hybrid` -> `多来源依据`
- `fallback` -> `默认配置`
- `连接检测中` -> move to diagnostics, not top bar

## Next Loop Entry

Loop 39 should implement Batch 1 only:

- global tokens;
- typography scale;
- shell/nav simplification;
- local shell tests and responsive screenshot verification.

Do not start Batch 2 until Batch 1 has a fresh local visual and responsive proof.
