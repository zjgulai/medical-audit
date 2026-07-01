---
title: "medical_audit Loop 36 docs-only staging execution"
project: "medical_audit"
created_at: "2026-07-01T17:11:00+08:00"
status: "staged-docs-only"
evidence_grade: "metadata-and-git-index-check"
source_loop: "Loop 35 docs-only staging rehearsal"
staging_executed: true
commit_executed: false
production_unchanged: true
deployed_sha: "b1c9a6c229a7880afcbfed35c1903d514914bb15"
---

# Loop 36 Docs-Only Staging Execution

## Decision

Loop 36 executes the Group E docs-only staging unit prepared by Loop 34 and rehearsed by Loop 35.

This loop is limited to the git index. It stages planning and steering Markdown only.

## Staged Scope

Command:

```bash
git add -- \
  .kiro/plan/*.md \
  .kiro/steering/planning-context.md
```

Expected staged file family:

- `.kiro/plan/*.md`
- `.kiro/steering/planning-context.md`

## Explicit Exclusions

- `web/**`
- `scripts/**`
- `output/**`
- environment files
- schema and migration files
- provider configuration
- object storage paths
- Docker or production deployment paths

## Verification Checklist

After staging, verify:

```bash
git diff --cached --name-status
git diff --cached --stat
git diff --cached --check
run the local standard sensitive-marker scan over `.kiro/plan` and `.kiro/steering`
git status --short --branch
```

Pass criteria:

- cached diff contains docs and planning files only;
- cached diff check passes;
- sensitive marker scan has no hits;
- business code, generated browser output, deployment scripts, env, schema, provider, and production paths remain outside the staged unit.

## Verification Result

- `git diff --cached --name-status`: 17 staged files, all under `.kiro/plan` or `.kiro/steering`.
- `git diff --cached --stat`: 17 files, 3122 insertions.
- `git diff --cached --check`: pass.
- Sensitive-marker scan over `.kiro/plan` and `.kiro/steering`: no hits.
- Out-of-scope staged path check: empty output.
- Remaining unstaged work is limited to prior `web/`, `scripts/`, `output/`, and review route changes from the broader `codex/frontend-2.0` worktree.

## Boundary

- `staging_executed=true`
- `commit_executed=false`
- `production_unchanged=true`
- no push, merge, deploy, production probe, provider call, env write, object storage write, schema migration, Docker change, or write-path smoke is part of this loop.
