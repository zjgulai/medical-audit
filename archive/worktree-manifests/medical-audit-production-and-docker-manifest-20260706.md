---
title: medical_audit production and docker manifest
status: active
created_at: 2026-07-06
evidence_grade: production-read-only
---

# medical_audit production and docker manifest

## Local Docker boundary

Only the local compose project `medical_audit` is in scope.

| Resource | Observed state | Action |
| --- | --- | --- |
| `medical-audit-kb-postgres` | running, healthy, port `5433->5432` | Keep. |
| `medical_audit_default` | local compose network | Keep. |
| `medical_audit_kb_pgdata` | local postgres volume | Keep unless separately authorized. |

Other running Docker projects belong to other repos and are out of scope.

## Production Docker boundary

Only these production resources are in scope for medical_audit governance:

| Resource | Observed state | Action |
| --- | --- | --- |
| `medical_audit_app` | running, healthy | Keep. |
| `medical_audit_pg` | running, healthy | Keep. |
| `medical_audit_clamav` | running, healthy | Keep. |
| `medical_audit_pgdata` | production DB volume | Keep. |
| `medical_audit_clamav_data` | production AV data volume | Keep. |
| `medical_audit_internal` | internal bridge network | Keep. |
| `lighthouse_ai_video_net` | shared external gateway network | Read-only verification only. |

## Production storage observation

Read-only SSH observation on 2026-07-06:

- `/opt/medical-audit`: about 63 GB before redeploy; about 48 GB of backups before the `main@edae4567` backup completed.
- `/var/www/audit`: about 1.9 MB before redeploy.
- Root filesystem had about 100 GB free during deployment.

Backup cleanup should target old backup archives only after a separate deletion manifest and explicit authorization. Do not run broad Docker prune or remove volumes.

## Deployment-state reports

Fresh reports generated at:

- `/Users/pray/project/medical_audit/tmp/outputs/tencent-cloud-deployment-state-governance-20260706.json`
- `/Users/pray/project/medical_audit-main-deploy-20260706/tmp/outputs/tencent-cloud-deployment-state-main-edae4567-replica-governance-20260706.json`

Key read-only result after `main@edae4567` deployment:

- deployment-state script status: `pass`
- deploy sha observed: `edae456790c2abb3d2ee896179a0b67be3e696fa`
- search backend ready: true
- matching embeddings: 49051
- Nginx config test: true
- audit static mount present: true

Note: the audit script's legacy `documents` frontdoor assertion still checks old page copy, so UI acceptance must come from the browser acceptance suite, not that legacy text assertion.
