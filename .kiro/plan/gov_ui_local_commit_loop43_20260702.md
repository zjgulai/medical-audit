---
title: "Loop43 Government UI Local Commit Gate"
project: "medical_audit"
date: "2026-07-02"
status: "local-commit-gate"
scope: "local-git"
production: "unchanged"
provider_calls: "none"
---

# Loop43 Government UI Local Commit Gate

## Objective

Execute the local Git gate for the government-style UI work planned in Loop42. This loop stages only the intended UI, test, script, and planning files; excludes local browser artifacts; creates a local commit if verification remains green; and stops before push, merge, deployment, production probe, provider call, Docker change, or write-path smoke.

## Staging Contract

Include:

- `.kiro/plan/*.md` entries related to Loop38-43.
- `scripts/run-production-documents-readonly-probe.py`
- `scripts/run-production-frontend-acceptance.mjs`
- `web/src/**` UI and test files from Loop39-41.
- `web/tests/e2e/foundation.spec.ts`

Exclude:

- `output/`
- `tmp/outputs/`
- provider logs, deployment reports, database dumps, object-storage artifacts, Docker state, and production-read-only reports not produced in this loop.

## Required Verification

- `git diff --check`
- `git diff --cached --check`
- `corepack pnpm@9.15.0 --filter medical-audit-web typecheck`
- `corepack pnpm@9.15.0 --filter medical-audit-web lint`
- `CI=true corepack pnpm@9.15.0 --filter medical-audit-web test`
- `corepack pnpm@9.15.0 --filter medical-audit-web build`

## Result

- Staged paths: `33`.
- Staged artifact paths under `output/` or `tmp/outputs/`: `0`.
- Local commit message: `feat: simplify government audit UI`.
- Production remained unchanged.

## Boundary

- Local Git gate only.
- No push, merge, deployment, production probe, provider call, env write, object storage write, schema migration, Docker change, or write-path smoke is part of this loop.
