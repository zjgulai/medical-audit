---
title: Frontend Cutover Production Readonly Audit
doc_type: analysis-report
module: frontend
created: 2026-07-05
updated: 2026-08-13
owner: self
source: human+ai
date: 2026-07-05
project: medical_audit
status: superseded
scope: production-readonly-and-local-baseline
production_write: false
provider_call: false
backend_write: false
deploy: false
---

# Frontend Cutover Production Readonly Audit

## First-Principles Goal

The decision question is not whether the production website is healthy in general. The decision question is whether production is already running the refactored frontend cutover branch, and whether the cutover branch has local page defects that should block review before deployment.

## Evidence Boundary

- Production URL: `https://audit.lute-tlz-dddd.top`
- Local cutover URL: `http://localhost:3032`
- Local branch: `codex/mainline-clean-cutover-20260705`
- Local cutover commit: `876547db refactor(web): cut over mainline to replica frontend`
- Production write: `false`
- Provider call: `false`
- Backend write: `false`
- Deploy: `false`

## Commands Run

```bash
node --check scripts/audit-frontend-cutover-readonly-compare.mjs
pnpm --filter medical-audit-web build
pnpm --filter medical-audit-web exec next start --port 3032
node scripts/audit-frontend-cutover-readonly-compare.mjs --production-base-url https://audit.lute-tlz-dddd.top --local-base-url http://localhost:3032 --timeout-ms 25000
python3 scripts/audit-tencent-cloud-deployment-state.py --ssh-key /Users/pray/project/medical_audit/ai_video.pem --expected-deploy-sha 876547db --json-output tmp/outputs/tencent-cloud-deployment-state-mainline-cutover-20260705T081642Z.json --markdown-output tmp/outputs/tencent-cloud-deployment-state-mainline-cutover-20260705T081642Z.md --backup-limit 3 --local-smoke-limit 3
```

## Browser Readonly Comparison

Report:

- JSON: `tmp/outputs/frontend-cutover-readonly-compare-20260705T081642Z.json`
- Markdown: `tmp/outputs/frontend-cutover-readonly-compare-20260705T081642Z.md`
- Screenshots: `tmp/screenshots/frontend-cutover-readonly-compare-20260705T081642Z/`

Summary:

| Source | Route viewport checks | Navigation issues | HTTP issues | Horizontal overflow | Broken image routes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Production | 42 | 0 | 0 | 0 | 0 |
| Local cutover | 42 | 0 | 0 | 0 | 0 |

Findings:

- `production-content-differs-from-cutover`: 36 observations.
- `production-legacy-behavior-differs-from-cutover`: 20 observations.
- Local cutover P0/P1 findings: 0.

Interpretation:

- Production is reachable and visually stable under this read-only audit.
- Local cutover is reachable and stable under the same route/viewport audit.
- The recorded differences are alignment observations: production still exposes older route behavior and older content surfaces, while local cutover redirects old routes to the refactored pages.

## Deployment State Readonly Observation

Report:

- JSON: `tmp/outputs/tencent-cloud-deployment-state-mainline-cutover-20260705T081642Z.json`
- Markdown: `tmp/outputs/tencent-cloud-deployment-state-mainline-cutover-20260705T081642Z.md`

Observed production state:

| Field | Value |
| --- | --- |
| Production `.deploy-sha` | `735ecc67df9450f1549e9477cac5e9df0a4a0d89` |
| Expected cutover commit | `876547db` |
| App container | `healthy` |
| PostgreSQL container | `healthy` |
| ClamAV container | `healthy` |
| Nginx config test | `true` |
| Public frontdoor | `healthy` |
| Next static | `healthy` |
| Search backend | `ready` |
| Matching embeddings | `49051` |

Interpretation:

- Production is operational.
- Production is not running the local cutover commit.
- This is expected until a separate authorized deployment is executed.

## Next Execution Decision

Recommended next step:

1. Keep this branch as the review candidate.
2. Push/create PR or merge only after reviewer accepts the clean-cutover scope.
3. Deploy only after explicit production authorization.
4. After deploy, rerun:
   - deployment state audit with expected SHA set to the deployed commit,
   - frontend cutover read-only compare,
   - production-specific smoke.
