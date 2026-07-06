---
title: medical_audit worktree manifest
status: active
created_at: 2026-07-06
---

# medical_audit worktree manifest

| Path | Branch / state | HEAD | Status | Recommendation |
| --- | --- | --- | --- | --- |
| `/Users/pray/project/medical_audit` | `main` | `6429b342` | dirty, behind `origin/main` | Keep as historical root; do not develop here until reconciled. |
| `/Users/pray/project/medical_audit-replica-restore-20260706` | `codex/restore-replica-shell-20260706` | `cddaeb8e` | clean at last check | Keep until all post-merge evidence is archived. |
| `/Users/pray/project/medical_audit-main-deploy-20260706` | detached `origin/main` | `edae4567` | clean deploy worktree | Keep until production acceptance evidence is no longer needed. |
| `/Users/pray/project/medical_audit-governance-20260706` | `codex/project-governance-20260706` | `edae4567` + governance commit | active governance branch | Keep until governance PR is merged. |
| `/Users/pray/.config/superpowers/worktrees/medical_audit/mainline-clean-cutover-20260705` | `codex/mainline-clean-cutover-20260705` | `93f5b991` | source reference | Keep as recovery reference until the next stable release. |
| `/private/tmp/medical-audit-replica-mainline-readonly` | detached | `93f5b991` | readonly reference | Remove after confirming no dirty state. |
| `/private/tmp/medical-audit-replica-frontend-readonly` | detached | `49159a8c` | readonly reference | Remove after confirming no dirty state. |
| `/private/tmp/medical-audit-login-gate-579d3983-20260705195621` | detached | `579d3983` | superseded | Remove after confirming no dirty state. |
| `/private/tmp/medical-audit-prod-release-6178cff1` | detached | `55d0bf61` | superseded | Remove after confirming no dirty state. |
| `/Users/pray/project/medical_audit-prod-clean-b5ad9fce` | `codex/production-ui-agents-release-20260706` | `6178cff1` | superseded by `main@edae4567` | Archive diff if dirty, then remove. |
| `/Users/pray/project/medical_audit-main-merge-20260706` | `codex/main-production-ui-agents-merge-20260706` | `39490291` | old merge proof | Archive/remove after confirming no dirty state. |
| `/Users/pray/project/medical_audit-main-ui-production-sync-20260706` | `codex/main-ui-production-sync-20260706` | `65a7ca61` | old sync proof | Archive/remove after confirming no dirty state. |
| `/Users/pray/project/medical_audit-merge-main-20260706` | `codex/merge-release-artifact-ignore-main-20260706` | `4bc22e03` | unrelated KB fallback branch | Keep only if KB owner still needs it; otherwise archive. |
| `/Users/pray/project/medical_audit-prod-replica-main-65a7ca61` | detached | `65a7ca61` | old replica-on-main reference | Remove after confirming no dirty state. |
| `/Users/pray/.config/superpowers/worktrees/medical_audit/main-postmerge-validation-20260705-0925` | detached | `a7a81da6` | old validation reference | Remove after confirming no dirty state. |

## Cleanup rule

Run `git -C <path> status --porcelain` before any worktree removal. If output is non-empty, save `git diff` and `git status --short` under `archive/worktree-manifests/` before removing.
