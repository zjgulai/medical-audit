---
title: "medical_audit production read-only request"
project: "medical_audit"
created_at: "2026-06-30T21:50:00+08:00"
status: "blocked-awaiting-authorization-and-deployed-sha"
evidence_grade: "request-only"
---

# Production Read-Only Request

## Decision Gate

Production read-only observation is blocked until all inputs are present:

- approved release commit SHA;
- confirmation that the approved SHA has been deployed;
- explicit authorization to run GET-only production probes;
- required SSH key or API-key env name, if the selected probe needs it;
- output paths with a unique stamp.

## Forbidden Actions Without Separate Authorization

- production deploy;
- production env write;
- production database write;
- object storage write;
- provider smoke or provider call;
- Docker compose build/restart/up;
- Nginx reload;
- any POST/PUT/PATCH/DELETE smoke.

## Prepared Commands

Set a unique stamp and approved deployed SHA first:

```bash
STAMP="frontend2-loop-$(date +%Y%m%dT%H%M%S%z)"
APPROVED_DEPLOY_SHA="<approved-deployed-sha>"
```

Read-only deployment state audit:

```bash
uv run python scripts/audit-tencent-cloud-deployment-state.py \
  --expected-deploy-sha "$APPROVED_DEPLOY_SHA" \
  --require-clamav-sidecar \
  --expected-dlp-review-provider ruleset-v1 \
  --json-output "tmp/outputs/tencent-cloud-deployment-state-${STAMP}.json" \
  --markdown-output "tmp/outputs/tencent-cloud-deployment-state-${STAMP}.md"
```

Read-only permission smoke:

```bash
corepack pnpm production:permission-readonly
```

Read-only frontend acceptance:

```bash
corepack pnpm production:frontend-acceptance
```

Documents governance read-only probe with deploy SHA comparison:

```bash
uv run python scripts/run-production-documents-readonly-probe.py \
  --base-url https://audit.lute-tlz-dddd.top \
  --expected-deploy-sha "$APPROVED_DEPLOY_SHA" \
  --report "tmp/outputs/production-documents-readonly-${STAMP}.json"
```

## Supported Claims After Successful Execution

If all commands pass and reports are reviewed:

- production GET-only surfaces observed for the approved SHA;
- no production write was performed by these probes;
- document governance status and deployment metadata are observable through read-only endpoints.

## Unsupported Claims Even After Read-Only Success

- production write-path governance E2E is complete;
- provider no-fallback generation is live;
- SSO/session production path is fully closed;
- object storage writeback, redaction, archive signature, or recovery drill has run.
