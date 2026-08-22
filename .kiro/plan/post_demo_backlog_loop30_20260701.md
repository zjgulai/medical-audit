---
title: "medical_audit Loop 30 post-demo backlog triage"
project: "medical_audit"
created_at: "2026-07-01T12:08:00+08:00"
status: "superseded"
updated: "2026-08-13"
evidence_grade: "planning-from-L3-production-read-only"
deployed_sha: "b1c9a6c229a7880afcbfed35c1903d514914bb15"
source_evidence: "Loop 28 and Loop 29"
---

# Loop 30 Post-Demo Backlog Triage

> 这是 2026-07-01 的历史待办快照，已被 `docs/README.md` 和 `drafts/analysis/project-reanalysis-and-gap-audit-20260813.md` 替代。保留本文仅用于追溯当时决策。

## Decision

This loop is a backlog triage pass. It does not assume real demo feedback has already been collected. It uses the Loop 28 read-only evidence and Loop 29 handoff to define the next safe work queue.

## Evidence Baseline

- Production SHA observed in Loop 28: `b1c9a6c229a7880afcbfed35c1903d514914bb15`
- Deployment-state audit: `status=pass`, app/postgres/clamav healthy, `matching_embedding_count=49051`
- Frontend acceptance: `status=pass`, `23` routes, `46` checks
- Permission readonly smoke: `status=observed`, `issue_count=0`, `production_side_effect=none`, `provider_call_status=not_called`
- Documents readonly probe: `status=pass`, deploy SHA matched expected
- Browser observation: `status=pass`, `issueCount=0`

## Current Severity

| Severity | Status | Evidence |
| --- | --- | --- |
| P0 | none open | Loop 28 deployment, frontend, documents, permission, and browser checks have no blocking issue recorded. |
| P1 | none open | Loop 28 browser and route checks recorded no major user-visible regression. |
| P2 | open as validation lanes | Several higher-confidence gates still require explicit authorization or real user feedback. |
| P3 | open as housekeeping | Evidence consolidation and durable check hardening can wait until after demo feedback. |

## P2 Queue

### P2-A Auth And Session Path

- Problem: the product still has a transition-layer auth model documented around headers and local roles.
- Why it matters: before broader rollout, the team needs a concrete choice for hospital SSO/session, persistent user state, and protected-route semantics.
- Next evidence: architecture decision plus local contract tests; production probe only after implementation and approval.
- Boundary: no env change or production auth change without explicit authorization.

### P2-B Write-Path Acceptance

- Problem: Loop 28 intentionally avoided write-path probes.
- Scope candidates: review task closeout/read-only lock, document upload governance, audit log write/export behavior, and signed artifact paths.
- Next evidence: define a disposable test tenant/project or fixture, backup expectations, rollback path, then run a gated write-path smoke.
- Boundary: this is not covered by Loop 28/29 evidence.

### P2-C Answer Provider Gate

- Problem: Loop 28 recorded `provider_call_status=not_called`; generated answer quality with a live provider is not proven by that loop.
- Next evidence: run answer-provider readiness audit first, then a single provider smoke only after provider-call authorization and cost/credit confirmation.
- Boundary: do not convert fallback/citation-only behavior into a live provider claim.

### P2-D Tab-State Acceptance Hardening

- Problem: the first Loop 28 browser attempt checked `/fund-compliance/review` before switching to `费用表单`.
- Next evidence: add or maintain a durable browser check that clicks the tab before asserting `表1/表2/表3`.
- Boundary: this is test-contract hardening, not a product defect from the final Loop 28 report.

### P2-E Real Demo Feedback Intake

- Problem: no real post-demo feedback has been supplied in this thread yet.
- Next evidence: collect route, screenshot, user role, expected outcome, and observed friction.
- Boundary: do not start more density/copy changes until feedback is concrete.

## P3 Queue

### P3-A Evidence Artifact Consolidation

- Consolidate Loop 16, Loop 18, Loop 28, Loop 29 demo docs after the presentation.
- Keep the latest evidence map, archive older packs if they confuse the route story.

### P3-B Browser Observation Script

- Convert the ad hoc browser sample into a reusable script only if the same checks will be repeated.
- Keep screenshots in `output/` and avoid writing them into the clean release worktree.

### P3-C Planning File Governance

- Decide whether `.kiro/plan` remains local planning state or should be represented in a tracked docs location.
- Do not move files without a separate directory-governance pass.

## Loop 31 Entry Criteria

Start Loop 31 only when one of the following is true:

- real demo feedback is provided with route and screenshot;
- the user explicitly authorizes one P2 validation lane;
- the user asks for a scoped implementation plan.

## Stop Rules

- Stop before provider calls.
- Stop before production writes.
- Stop before env changes.
- Stop before object storage writes.
- Stop before schema migrations.
- Stop before deployment.
