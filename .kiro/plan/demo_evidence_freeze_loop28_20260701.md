---
title: "medical_audit Loop 28 demo evidence freeze"
project: "medical_audit"
created_at: "2026-07-01T11:44:00+08:00"
status: "ready"
evidence_grade: "L3-production-read-only"
deployed_sha: "b1c9a6c229a7880afcbfed35c1903d514914bb15"
observation_stamp: "loop28-postdeploy-observe-20260701T114051+0800"
---

# Loop 28 Demo Evidence Freeze

## Production Target

- URL: `https://audit.lute-tlz-dddd.top`
- Deployed SHA: `b1c9a6c229a7880afcbfed35c1903d514914bb15`
- Deploy source: Loop 27 authorized production deployment.
- Observation source: Loop 28 production read-only checks and browser observation.

## Evidence Links

- Deployment-state audit: `/Users/pray/project/medical_audit_minimal_pr/tmp/outputs/tencent-cloud-deployment-state-loop28-postdeploy-observe-20260701T114051+0800.json`
- Deployment-state audit markdown: `/Users/pray/project/medical_audit_minimal_pr/tmp/outputs/tencent-cloud-deployment-state-loop28-postdeploy-observe-20260701T114051+0800.md`
- Frontend acceptance: `/Users/pray/project/medical_audit_minimal_pr/tmp/outputs/production-frontend-acceptance-loop28-postdeploy-observe-20260701T114051+0800.json`
- Permission readonly smoke: `/Users/pray/project/medical_audit_minimal_pr/tmp/outputs/production-permission-readonly-smoke-loop28-postdeploy-observe-20260701T114051+0800.json`
- Documents readonly probe: `/Users/pray/project/medical_audit_minimal_pr/tmp/outputs/production-documents-readonly-probe-loop28-postdeploy-observe-20260701T114051+0800.json`
- Browser observation report: `/Users/pray/project/medical_audit/output/playwright/loop28-postdeploy-observe-20260701T114051+0800-browser/report.json`
- Browser screenshots: `/Users/pray/project/medical_audit/output/playwright/loop28-postdeploy-observe-20260701T114051+0800-browser/`

## Demo Route Order

1. `/workspace`: show project status, user-facing service copy, and current workbench.
2. `/fund-compliance/review`: open `费用表单`, show `表1`, `表2`, `表3`.
3. `/chat`: show `AI 对话` and citation-first workflow.
4. `/agent-market`: show compact marketplace and `已显示前 12 个` density marker.
5. `/documents`: show material and knowledge-base search readiness.

## Speaking Boundaries

- Safe claim: production currently serves deployed SHA `b1c9a6c229a7880afcbfed35c1903d514914bb15`.
- Safe claim: Loop 28 read-only checks passed for deployment state, frontend routes, documents, permission probes, and browser sample states.
- Safe claim: provider calls were not made in Loop 28.
- Do not claim new data ingestion, object storage write, schema migration, or write-path review smoke from Loop 28.

## Screenshots

- `mobile-workspace.png`
- `desktop-workspace.png`
- `mobile-fund-review-forms.png`
- `mobile-chat.png`
- `mobile-agent-market.png`
