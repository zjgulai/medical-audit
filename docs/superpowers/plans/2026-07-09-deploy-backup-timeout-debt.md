---
title: Deploy Backup Timeout Debt Implementation Plan
doc_type: implementation-plan
module: deployment
status: superseded
superseded_by: drafts/analysis/project-reanalysis-and-gap-audit-20260813.md
created: 2026-07-09
updated: 2026-08-22
owner: self
source: human+ai
---

# Deploy Backup Timeout Debt Implementation Plan

> 本计划已停用，不再作为可执行指引。当前权威状态与后续门禁见 [项目全量复盘与差异审计](../../../drafts/analysis/project-reanalysis-and-gap-audit-20260813.md)。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the production deploy script's remote-backup SSH wait debt and produce a current unfinished-task inventory without touching product UI or production data.

**Architecture:** Keep deployment side effects unchanged, but stop depending on one long SSH session for backup completion. Start the remote backup script as a controlled background job, poll a completion marker and required backup files, and fail fast if the job exits before the marker appears.

**Tech Stack:** Python deploy script, pytest script tests, Markdown planning artifact.

## Global Constraints

- Work from a clean `origin/main` worktree, not the dirty repository root.
- No production deploy, no database write, no Docker cleanup in this batch.
- Only modify `scripts/deploy-tencent-cloud-production.py`, `tests/knowledge_query/test_scripts.py`, and one planning/report artifact.
- Keep `medical_audit` Docker/resource boundaries explicit; do not touch other projects.

---

### Task 1: Fix Remote Backup Completion Control

**Files:**
- Modify: `scripts/deploy-tencent-cloud-production.py`
- Test: `tests/knowledge_query/test_scripts.py`

**Interfaces:**
- Consumes: `DeployConfig`, `_ssh_args(config, script)`, `REMOTE_BACKUP_TIMEOUT_SECONDS`, `REMOTE_COMPLETION_CHECK_TIMEOUT_SECONDS`.
- Produces: `_ssh_background_with_completion(config, script, completion_check_script, timeout_seconds, timeout_description, job_name) -> None`.

- [ ] **Step 1: Add tests for background completion polling**

Add tests that prove the backup helper starts a background job, polls until the completion marker passes, and that `_create_remote_backups` routes through the helper with a completion-check script.

- [ ] **Step 2: Run the focused tests and confirm they fail before implementation**

Run:

```bash
uv run pytest tests/knowledge_query/test_scripts.py -k "deploy_tencent_cloud_background_completion or deploy_tencent_cloud_remote_backups" -q
```

Expected before implementation: at least one failure because `_ssh_background_with_completion` does not exist and `_create_remote_backups` still calls `_ssh` directly.

- [ ] **Step 3: Implement the background job helper**

Add a helper that writes the remote script to `/tmp`, starts it with `nohup bash`, writes a pid file, then polls via SSH until either the marker/files pass, the background pid exits without marker, or the timeout is reached.

- [ ] **Step 4: Wire `_create_remote_backups` to the helper**

Replace the direct long `_ssh(... timeout_seconds=REMOTE_BACKUP_TIMEOUT_SECONDS, completion_check_script=...)` call with `_ssh_background_with_completion(...)`.

- [ ] **Step 5: Run focused tests again**

Run:

```bash
uv run pytest tests/knowledge_query/test_scripts.py -k "deploy_tencent_cloud_background_completion or deploy_tencent_cloud_remote_backups" -q
```

Expected after implementation: pass.

### Task 2: Unfinished Task Inventory

**Files:**
- Create: `drafts/analysis/deploy-backup-timeout-debt-and-open-work-inventory-draft-20260709.md`

**Interfaces:**
- Consumes: production SHA evidence, local dirty-root status, current deploy script debt, frontend/backend open lanes.
- Produces: a categorized backlog with evidence level, risk, and next action.

- [ ] **Step 1: Create the inventory draft**

Record facts, inferences, and unknowns separately. Include completed production deployment evidence, the deployment-script debt fixed locally, and remaining product/backend/documentation tasks.

- [ ] **Step 2: Keep the inventory non-operational**

The inventory must not contain commands that imply production writes; it is a planning artifact only.

### Task 3: Validation

**Files:**
- Validate: `scripts/deploy-tencent-cloud-production.py`
- Validate: `tests/knowledge_query/test_scripts.py`
- Validate: `drafts/analysis/deploy-backup-timeout-debt-and-open-work-inventory-draft-20260709.md`

- [ ] **Step 1: Syntax-check the deploy script**

Run:

```bash
python3 -m py_compile scripts/deploy-tencent-cloud-production.py
```

Expected: no output and exit code 0.

- [ ] **Step 2: Run focused pytest**

Run:

```bash
uv run pytest tests/knowledge_query/test_scripts.py -k "deploy_tencent_cloud" -q
```

Expected: pass for deploy-script related tests.

- [ ] **Step 3: Check formatting safety**

Run:

```bash
git diff --check
```

Expected: no whitespace errors.
