---
title: "medical_audit Loop 31 feedback intake and lane gate"
project: "medical_audit"
created_at: "2026-07-01T13:43:00+08:00"
status: "ready-for-input"
evidence_grade: "intake-gate-no-new-runtime-evidence"
deployed_sha: "b1c9a6c229a7880afcbfed35c1903d514914bb15"
source_evidence: "Loop 28, Loop 29, Loop 30"
---

# Loop 31 Feedback Intake And Lane Gate

## Purpose

Loop 31 creates the intake surface for real demo feedback or a single scoped implementation lane. It does not select a lane by itself and does not change production or business code.

## Feedback Intake Form

For each feedback item, collect:

- `route`: the exact page or flow, such as `/workspace` or `/fund-compliance/review`.
- `viewport`: desktop, mobile, projector, or unknown.
- `user_role`: director, auditor, admin, technical reviewer, or other.
- `observed`: what the user saw.
- `expected`: what the user expected.
- `evidence`: screenshot, recording timestamp, or quoted feedback.
- `severity_hint`: P0, P1, P2, or P3.
- `demo_context`: live demo, private review, internal rehearsal, or production check.

## Lane Decision Table

| Lane | When To Choose | Minimum Evidence | Authorization Needed |
| --- | --- | --- | --- |
| P2-A Auth/session | Feedback or release need concerns login, roles, SSO, or route protection. | Desired auth model and local contract impact. | Required before env or production auth changes. |
| P2-B Write-path acceptance | Need to prove review tasks, document upload governance, audit logs, or signed artifacts. | Disposable tenant/project, rollback plan, and exact smoke scope. | Required before any production write. |
| P2-C Answer provider | Need to prove live provider answer quality beyond fallback/citation behavior. | Provider readiness report and cost/credit confirmation. | Required before any provider call. |
| P2-D Tab-state acceptance hardening | Need durable checks for `费用表单`, `表1/表2/表3`, or other tabbed flows. | Route, tab action, expected text, and local browser target. | Local/test-only authorization is enough to plan; production probe still separate. |
| P2-E UI feedback polish | Real demo feedback identifies density, copy, navigation, or flow friction. | Route, screenshot, expected outcome, user role. | Required before code changes. |

## Recommended Default

If no new feedback is supplied, the safest next executable lane is P2-D tab-state acceptance hardening, because it can be scoped to local/test code around the already observed `费用表单` interaction. It still needs explicit approval before implementation.

## Evidence Boundary

- Loop 28 supports production read-only observations.
- Loop 29 supports demo handoff only.
- Loop 30 supports backlog triage only.
- Loop 31 supports intake and lane selection only.

## Stop Rules

Stop and ask before:

- provider calls;
- production writes;
- env changes;
- object storage writes;
- schema migrations;
- deployment;
- business-code edits.

## Loop 32 Entry Criteria

Loop 32 can begin when one input is provided:

- a real feedback item using the intake form;
- explicit authorization for one lane in the decision table;
- a narrowed implementation request with evidence target and boundary.
