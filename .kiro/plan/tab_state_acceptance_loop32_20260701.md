---
title: "medical_audit Loop 32 tab-state acceptance hardening"
project: "medical_audit"
created_at: "2026-07-01T15:31:00+08:00"
status: "local-test-scope"
evidence_grade: "L1-local-runtime"
lane: "P2-D tab-state acceptance hardening"
production_unchanged: true
deployed_sha: "b1c9a6c229a7880afcbfed35c1903d514914bb15"
---

# Loop 32 Tab-State Acceptance Hardening

## Decision

Loop 32 selects P2-D from the Loop 31 gate because it is the narrowest lane that can improve confidence without production writes, provider calls, deployment, or schema changes.

## Scope

- Route under test: `/fund-compliance/review`.
- User action path: `医保基金使用合规` entry, then `费用表单`, then `表1` / `表2` / `表3`, then `新建表单`.
- Files changed:
  - `web/src/app/(workspace)/workspace-pages.test.tsx`
  - `web/tests/e2e/foundation.spec.ts`
- Files not changed:
  - production deploy scripts;
  - backend/provider code;
  - database/schema files;
  - runtime environment files.

## Acceptance Contract

- `费用表单` tab must become selected after click.
- `表1` starts selected and shows `表1_医保费用汇总表（空白）.xlsx / 汇总表`.
- `表2` can be selected and shows `表2_医保费用分类汇总表（空白）.xlsx / 汇总表`.
- `表3` can be selected and shows `表3_就诊费用明细表（空白）.xlsx / 明细表`.
- `新建表单` exposes the form fields in browser E2E.
- Component coverage also verifies custom form creation and selected `自建` state.

## Evidence Boundary

This loop can support only local/test acceptance claims. It does not refresh production evidence and does not change the deployed version.

## Verification Commands

```bash
pnpm --filter medical-audit-web test -- web/src/app/\(workspace\)/workspace-pages.test.tsx
pnpm --filter medical-audit-web e2e -- web/tests/e2e/foundation.spec.ts --grep "fund compliance topic opens a separate review workbench"
```

## Verification Results

- `CI=true corepack pnpm@9.15.0 --filter medical-audit-web test -- 'src/app/(workspace)/workspace-pages.test.tsx'`: pass, 30 tests.
- `PLAYWRIGHT_REUSE_SERVER=1 CI=true corepack pnpm@9.15.0 exec playwright test tests/e2e/foundation.spec.ts --grep 'fund compliance topic opens a separate review workbench'`: pass, 1 test.
- Dependency recovery note: the Codex runtime `pnpm@11` entrypoint was not used for final verification; final commands used the project-declared `pnpm@9.15.0`.
