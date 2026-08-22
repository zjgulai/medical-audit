---
title: Phase 7 path migration findings
doc_type: execution-findings
module: repository
status: active
created: 2026-07-18
updated: 2026-08-13
owner: Codex
source: human+ai
---

# Phase 7 path migration findings

## 2026-07-18 recovery checkpoint

- The declared iCloud path is a Git worktree and includes `AGENTS.md` plus `.kiro/plan/`.
- `.git/index.lock` exists, is zero bytes, and `lsof .git/index.lock` returned no holder. Do not remove it until the active branch, Git processes, and migration state are checked.
- No production command, remote Git mutation, source edit, or deployment was executed during this recovery checkpoint.
- Reading migrated tracked text files (`AGENTS.md` and `.kiro/plan/*.md`) did not return content within the observed 20-second window; the `wc` reader was interrupted with exit code 130. This is consistent with an unresolved iCloud hydration or filesystem-read condition, not a repository-state conclusion.
- Metadata confirms that `.git/HEAD`, `.git/config`, and `.git/packed-refs` are also `dataless`; this explains why Git repository commands cannot yet provide a reliable branch or worktree status. A stale zero-byte index lock remains unmodified.
- A targeted `brctl download` request did not make the inspected files resident during this session. The prior independent release candidate under `/Users/pray/project/` is no longer present after the path migration.
- The release candidate was migrated as a sibling at `/Users/pray/Library/Mobile Documents/com~apple~CloudDocs/project/medical_audit_phase7_r1_0f768ff_20260718`. Its Git control files are resident, but `git status --short --branch` did not complete within 20 seconds and was interrupted; candidate state is therefore unverified.
- Two fresh, isolated GitHub clone attempts (full and shallow HTTP/1.1) failed on transport connection timeouts. No candidate was obtained, and the failed partial clones are outside the project root and remain untouched.
- The migrated candidate's `refs/heads/main` is itself `dataless`; even `git rev-parse HEAD` cannot complete. The intended merged SHA cannot be freshly confirmed from this filesystem state.
- GitHub API remained reachable through the authenticated `gh` client and freshly reported remote `main` as `0f768ff1c54831f7f74b3fa99c5744bed2b1f8f7`. GitHub SSH transport is reachable but has no usable local public-key identity; HTTPS Git transport remains unavailable.
- GitHub's tarball content endpoint likewise produced no bytes during a bounded 120-second authenticated request and was interrupted. The API metadata path is reachable; repository-content transfer is blocked. No source candidate can be reconstructed locally until that transport or the iCloud hydration condition recovers.

## 2026-07-18 recovery result

- After local download completed, the migrated primary worktree was confirmed `main...origin/main [behind 172]` with extensive pre-existing tracked and untracked changes. It was not used for release work.
- The migrated clean candidate and its object source used stale absolute Git alternates paths. Both alternates files were backed up beside the originals and updated to their iCloud locations. `git fsck --connectivity-only` then exited 0; dangling historical objects were reported but no integrity failure remained.
- The repaired candidate is clean and both `HEAD` and `origin/main` are `0f768ff1c54831f7f74b3fa99c5744bed2b1f8f7`, matching GitHub's read-only API observation.
- Path migration also left Python console-script shebangs pointing to the old root. `uv sync --frozen --group dev --reinstall` recreated the candidate environment. Fresh local checks passed: Ruff, mypy for 104 source files, full pytest, web lint, web typecheck, 38 Vitest files / 369 tests, and a 24-route Next.js production build.
- Local full-stack Playwright E2E did not enter page assertions because Chromium headless shell was absent. A bounded Playwright Chromium download remained at 0% and was interrupted. This is an environment-only E2E block, not a product pass or failure.
- Authorized S0 production observation passed at `L3-production-read-only`: observed SHA equals expected legacy SHA `1376baef0d8d47f1e1ef60b2cec130451af5af4f`, topology is `legacy_ready`, and the snapshot recorded no database write, guard write, or provider call.
- The deployment script's zero-execute preflight passed. Actual production deployment remains unexecuted and requires a fresh explicit approval for candidate SHA `0f768ff1c54831f7f74b3fa99c5744bed2b1f8f7`.

## 2026-07-18 authorized deployment attempt

- The user explicitly authorized the first legacy-to-versioned deployment for candidate SHA `0f768ff1c54831f7f74b3fa99c5744bed2b1f8f7`, without schema, provider, or review-write flags.
- A fresh S0 production observation passed immediately before execution, confirming the expected legacy SHA and `legacy_ready` topology.
- The deploy script stopped at its first local freshness step: `git fetch --quiet origin +refs/heads/main:refs/remotes/origin/main` failed with `Failed to connect to github.com port 443 after 75003 ms: Couldn't connect to server`.
- No remote backup, synchronization, restart, schema change, provider call, review write, or deployment completion was reported before that failure.
- A second S0 production observation after the failure passed at `L3-production-read-only`; it still observed the legacy SHA and recorded `capture_side_effect: none`, `database_write: false`, and `guard_execution_write: false`.
- Do not retry the deploy until GitHub HTTPS Git transport is restored. The failure recurred after earlier HTTPS clone and content-download failures, so rerunning without an external network-state change would not add evidence.

## 2026-07-18 retry deployment reconciliation

- GitHub HTTPS Git transport recovered and `git ls-remote` returned candidate SHA `0f768ff1c54831f7f74b3fa99c5744bed2b1f8f7`; a fresh S0 again confirmed the expected legacy SHA before retrying the authorized deployment.
- The retry passed local fetch, lock validation, dependency installation, and release build, then started the remote backup worker. The launcher lost reliable polling and the deploy script stopped with the production lock retained rather than proceeding to app or web synchronization.
- Read-only reconciliation proved the backup worker completed successfully: app, env, DB, nginx, and web backups exist for stamp `20260718T174002+0800`; the DB backup reached `4835135173` bytes; its completion marker exists with mode `600`; the worker PID file is absent and its log is empty.
- A post-backup S0 still passed against the legacy SHA. No versioned `current` release target exists, the remote deploy SHA remains legacy, and the release switch did not occur.
- The only unresolved production mutation is the retained `/opt/medical-audit/app.deploy.lock` owner lock. It must not be removed until separately authorized; a new deploy retry also needs a fresh exact authorization after any lock removal.
