---
title: "Loop 58 Phase 4 atomic local commit plan"
doc_type: "analysis-draft"
module: "release"
status: "complete"
created: "2026-07-16"
updated: "2026-07-16"
owner: "self"
source: "human+ai"
---

# Loop 58 Phase 4 Atomic Local Commit Plan

## Boundary

Owner authorization covers local staging and local commits for this candidate. It does not authorize push, PR creation/state change, merge, SSH, deploy, production/database writes, provider calls or live sends.

Ignored `output/`, `tmp/`, `web/out/`, screenshots, SQLite files, caches and `__pycache__` remain outside every manifest. Never use `git add .`.

## Commit 1 — release evidence closure

Reason: make migration/release snapshots, exact-SHA frontend acceptance and the explicitly labeled Mypy-debt gate independently reviewable and revertible.

Manifest:

- `configs/mypy-non-regression-baseline-v1.json`
- `scripts/audit-production-release-guard-snapshot.py`
- `scripts/check-mypy-non-regression.py`
- `scripts/run-production-frontend-acceptance-gate.mjs`
- `scripts/run-production-frontend-acceptance.mjs`
- `tests/knowledge_query/test_mypy_non_regression.py`
- `tests/knowledge_query/test_release_guard_snapshot.py`
- `tests/knowledge_query/test_production_frontend_acceptance_workflow.py`
- `tests/knowledge_query/test_scripts.py`
- `docs/workflows/workflow-tencent-cloud-audit-deployment-stable.md`

Verification before commit:

- `uv run python scripts/check-mypy-non-regression.py`
- `uv run pytest -q tests/knowledge_query/test_mypy_non_regression.py tests/knowledge_query/test_release_guard_snapshot.py tests/knowledge_query/test_scripts.py tests/knowledge_query/test_production_frontend_acceptance_workflow.py`
- `uv run ruff check .`
- targeted Mypy is enforced by the non-regression gate
- `node --check` for both frontend acceptance scripts
- cached manifest/name-status/stat/check and refined high-risk secret scan

Commit message: `feat: bind release acceptance evidence`

## Commit 2 — route/chrome/mobile checkpoint

Reason: keep the user-visible route identity and mobile safe-area correction separate from operator evidence tooling.

Manifest:

- `web/src/app/(workspace)/findings/page.tsx`
- `web/src/app/(workspace)/workspace/page.tsx`
- `web/src/app/globals.css`
- `web/src/components/replica/replica-shell.test.tsx`
- `web/src/components/replica/replica-shell.tsx`
- `web/src/lib/reference-replica-data.ts`
- `web/tests/e2e/foundation.spec.ts`
- `web/tests/e2e/local-acceptance-fullstack.spec.ts`

Verification before commit:

- relevant replica-shell component tests
- `pnpm web:typecheck`
- `pnpm web:lint`
- cached manifest/name-status/stat/check and refined high-risk secret scan

Commit message: `fix: preserve workspace route identity`

## Commit 3 — planning ledger

Reason: record the selected Mypy policy, evidence grade, authorization boundaries, exact manifests and remaining production gates without mixing status prose into code commits.

Manifest:

- `.kiro/plan/task_plan.md`
- `.kiro/plan/findings.md`
- `.kiro/plan/progress.md`
- `docs/superpowers/plans/2026-07-16-production-ui-reconciliation-and-release-integrity.md`
- `drafts/analysis/loop58-phase4-atomic-commit-plan-draft-20260716.md`

Verification before commit:

- Markdown frontmatter/path checks
- cached manifest/name-status/stat/check and refined high-risk secret scan

Commit message: `docs: freeze loop 58 local candidate`

## Execution Result

- Commit 1: `0d34a94`, exact 10-file manifest.
- Commit 2: `85859a6`, exact 8-file manifest.
- Commit 3: this five-file planning manifest; its final SHA and clean-worktree state are verified externally after the commit rather than self-referenced here.
- Pre-staging evidence: `322` Python evidence tests passed; Ruff, Node syntax and Mypy non-regression gate passed; Web `38` files / `352` tests, typecheck and lint passed.
- Every cached diff had exact manifest equality, `git diff --cached --check` PASS and refined added-content `secret_candidates=0`.

## Stop conditions

- Any staged path is absent from its manifest or belongs to another group.
- Any ignored/generated/sensitive artifact appears in the index.
- A required focused gate fails.
- The Mypy gate reports anything other than `allowed-with-label` with `mypy_full_pass=false`.
- A commit would require patch staging inside a mixed file that has not been reviewed.
