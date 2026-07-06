---
title: medical_audit generated artifacts manifest
status: active
created_at: 2026-07-06
---

# generated artifacts manifest

These directories are generated or temporary evidence outputs. They should not be used as source of truth for implementation.

| Path | Observed role | Action |
| --- | --- | --- |
| `output/` | Playwright and release-convergence evidence | Keep locally, ignore in Git. |
| `web/output/` | UI reference comparison and smoke screenshots | Keep locally, ignore in Git. |
| `web/web/` | Nested generated Playwright output under `web/` | Keep for now; archive or remove after owner review. |
| `.playwright-cli/` | transient browser harness page snapshots | Ignore in Git. |
| `.playwright-mcp/` | transient browser console logs | Ignore in Git. |
| `tmp/outputs/` | deployment/smoke/audit reports | Already under ignored `tmp/`; keep as evidence. |
| `tmp/screenshots/` | local and production screenshots | Already under ignored `tmp/`; keep as evidence. |

Observed sizes during governance pass:

- `web/web`: about 8.6 MB.
- `web/output`: about 231 MB.
- `output`: about 60 MB.
- `.playwright-cli`: about 12 KB.
- `.playwright-mcp`: about 12 KB.

Do not delete these until any referenced evidence has been copied into a formal report or is no longer needed.
