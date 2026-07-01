---
title: "medical_audit Loop 29 demo handoff"
project: "medical_audit"
created_at: "2026-07-01T11:54:00+08:00"
status: "ready"
evidence_grade: "L3-production-read-only"
deployed_sha: "b1c9a6c229a7880afcbfed35c1903d514914bb15"
source_evidence: "Loop 28"
---

# Loop 29 Demo Handoff

## Opening Position

This demo should be presented as a production read-only observed state after the authorized Loop 27 deploy. The verified production SHA is `b1c9a6c229a7880afcbfed35c1903d514914bb15`.

## Route Script

1. `/workspace`
   - Show: project status, service readiness, user-facing copy.
   - Say: the workbench starts from the audit project, not from system internals.
   - Evidence screenshot: `/Users/pray/project/medical_audit/output/playwright/loop28-postdeploy-observe-20260701T114051+0800-browser/mobile-workspace.png`

2. `/fund-compliance/review`
   - Action: switch to `费用表单`.
   - Show: `表1`, `表2`, `表3` as the fee-form contract.
   - Say:疑点和费用表单 are separate user tasks inside the fund-compliance topic.
   - Evidence screenshot: `/Users/pray/project/medical_audit/output/playwright/loop28-postdeploy-observe-20260701T114051+0800-browser/mobile-fund-review-forms.png`

3. `/chat`
   - Show: `AI 对话` and citation-first workflow.
   - Say: answers should stay tied to materials and citations.
   - Evidence screenshot: `/Users/pray/project/medical_audit/output/playwright/loop28-postdeploy-observe-20260701T114051+0800-browser/mobile-chat.png`

4. `/agent-market`
   - Show: compact assistant cards and `已显示前 12 个`.
   - Say: the first screen shows common helpers; search can reach more templates.
   - Evidence screenshot: `/Users/pray/project/medical_audit/output/playwright/loop28-postdeploy-observe-20260701T114051+0800-browser/mobile-agent-market.png`

5. `/documents`
   - Show: material and knowledge-base readiness from the navigation path.
   - Say: document readiness was checked by the Loop 28 documents readonly probe.

## Evidence Map

- Deployment-state audit: `/Users/pray/project/medical_audit_minimal_pr/tmp/outputs/tencent-cloud-deployment-state-loop28-postdeploy-observe-20260701T114051+0800.json`
- Frontend acceptance: `/Users/pray/project/medical_audit_minimal_pr/tmp/outputs/production-frontend-acceptance-loop28-postdeploy-observe-20260701T114051+0800.json`
- Permission readonly smoke: `/Users/pray/project/medical_audit_minimal_pr/tmp/outputs/production-permission-readonly-smoke-loop28-postdeploy-observe-20260701T114051+0800.json`
- Documents readonly probe: `/Users/pray/project/medical_audit_minimal_pr/tmp/outputs/production-documents-readonly-probe-loop28-postdeploy-observe-20260701T114051+0800.json`
- Browser observation report: `/Users/pray/project/medical_audit/output/playwright/loop28-postdeploy-observe-20260701T114051+0800-browser/report.json`

## Safe Claims

- Production served deployed SHA `b1c9a6c229a7880afcbfed35c1903d514914bb15` during Loop 28 observation.
- Loop 28 read-only reports passed deployment state, frontend route acceptance, documents readiness, and browser sample checks.
- Permission probe was GET-only and recorded `production_side_effect=none`.
- Loop 29 packaged the demo handoff only.

## Blocked Claims

- Do not say Loop 29 performed deployment.
- Do not say Loop 29 called a provider.
- Do not say Loop 29 wrote object storage, changed env, migrated schema, or ran write-path review smoke.
- Do not present Loop 28/29 as customer-owned evidence; it is production read-only observation.

## Fallback

- If network is slow, use the screenshots in `/Users/pray/project/medical_audit/output/playwright/loop28-postdeploy-observe-20260701T114051+0800-browser/`.
- If asked about current live state after the demo begins, rerun a new read-only observation loop before making a fresh claim.
