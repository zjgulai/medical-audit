---
title: H1 strict abstention 生产部署与远端候选分支删除计划
doc_type: deployment-plan
module: knowledge-query
status: superseded
created: 2026-07-22
updated: 2026-08-15
owner: self
source: human+ai
target_sha: 905f9f485dbe1a390fbd1fefea5a89f09722cdf9
evidence_grade: L2-plan
phase_a_status: pass
candidate_deploy_stamp: h1-strict-abstention-905f9f4-20260722T090844Z
---

# H1 strict abstention 生产部署与远端候选分支删除计划

> 从 `/Users/pray/project/medical_audit_h1_fix_20260721` 原样归并的历史独有草稿；2026-08-13 标记为 `superseded`。当前状态以 [文档索引](../../docs/README.md) 为准。

## 1. 当前事实与证据边界

- Fresh GitHub evidence: PR `#259` is merged; merge SHA and remote `main` are `905f9f485dbe1a390fbd1fefea5a89f09722cdf9`.
- Remote candidate branch `codex/h1-strict-output-contract-20260722` still points to `13b0fb1c5f0e318a2e6052105c529d75676f78db`.
- The last recorded L3 production SHA is `18d3ff86170558b0ea20eafc1dbd6e4a32c33a28`; this is historical evidence and must be re-observed before deployment.
- Local/merge evidence is L2 source evidence. Until fresh production read-only inspection runs, production SHA, health, lock, disk and backup state remain unknown-current.
- This plan does not authorize SSH, production reads/writes, backup creation, deployment, provider calls or branch deletion.

## 2. Deployment source preparation

The deploy script requires a clean `main` with `HEAD == origin/main == --approved-sha`. Neither current local clone is ready:

- `/Users/pray/project/medical_audit_h1_fix_20260721` is on the candidate branch and contains three modified planning ledgers plus two untracked drafts after this plan is created.
- `/Users/pray/project/medical_audit` is a stale, heavily dirty independent clone and must not be used.

Preferred preparation after explicit authorization:

1. Record hashes/status for the three planning ledgers and both untracked drafts.
2. Create one named stash limited to those five paths, including untracked files; retain the stash until all deployment work is closed.
3. Switch the H1 clone to local `main`, fetch `origin/main`, and fast-forward only.
4. Require clean status and exact identity:
   `HEAD == origin/main == 905f9f485dbe1a390fbd1fefea5a89f09722cdf9`.
5. After deployment planning/execution closes, switch back to the local candidate branch and apply—not pop—the exact named stash. Stop on any conflict.

Do not create another long-lived clone or worktree. Do not use `--allow-dirty` for execute mode.

## 3. Phase A — fresh production read-only preflight

This phase requires its own SSH/read-only authorization and uses the repository-external `$SSH_KEY_PATH` without reading or printing key contents; this tracked draft does not retain a user-specific absolute path.

1. Run the conditional-L3 deployment-state audit without asserting a target SHA to discover current deploy SHA, release topology, health, lock, backups and embedding readiness.
2. Fail closed unless the observed current SHA is exactly the last verified SHA `18d3ff86170558b0ea20eafc1dbd6e4a32c33a28`. Any drift requires a new plan/authorization.
3. Capture release-guard S0 bound to the observed current SHA and require:
   - `status=pass`, L3 production-read-only;
   - versioned topology is complete;
   - schema/business/object snapshots are valid;
   - collector provider calls `0`, DB writes `false`, no concurrent ambiguity.
4. Run default deploy preflight without `--execute`; require app/PostgreSQL/Nginx presence, `nginx -t`, local health and SSH success.
5. Inspect the deploy lock and proposed backup stamp read-only. Continue only if the lock is absent and all five proposed backup paths plus the completion marker are absent.
6. Do not clear an active or ambiguous lock. A provably stale lock requires an explicit cleanup clause in the execute authorization.

Phase A decision:

- `GO`: every read-only gate passes and observed production SHA is the exact expected old SHA.
- `NO-GO`: drift, partial topology, unhealthy runtime, insufficient disk, active/ambiguous lock, stamp collision, missing key, or any write/provider attempt.

## 4. Phase B — exact-SHA standard deployment

Execution requires a second exact authorization binding target SHA, observed old SHA and a unique deploy stamp generated after Phase A.

Canonical command shape:

```text
uv run python scripts/deploy-tencent-cloud-production.py \
  --execute \
  --confirm-production audit.lute-tlz-dddd.top \
  --approved-sha 905f9f485dbe1a390fbd1fefea5a89f09722cdf9 \
  --ssh-key "$SSH_KEY_PATH" \
  --stamp h1-strict-abstention-905f9f4-20260722T090844Z \
  --report tmp/outputs/production-e2e-smoke-after-deploy-h1-strict-abstention-905f9f4-20260722T090844Z.json
```

Explicitly omitted flags:

- no `--apply-schema`;
- no `--include-query-provider-smoke`;
- no `--include-review-write`;
- no `--confirm-production-write`;
- no `--skip-smoke`, `--skip-web-build`, `--skip-app-rebuild`, `--allow-dirty` or legacy migration flag.

Authorized deployment side effects must be named explicitly:

- acquire/release the owner-bound deployment lock;
- create complete app, env, DB, Nginx and Web backups under the unique stamp;
- remove only same-stamp incomplete artifacts before backup creation;
- run the script's scoped application `rsync --delete` and generated-cache cleanup;
- build and verify frozen app/static assets from the approved SHA;
- rebuild/recreate the app container;
- atomically promote the versioned static release and update Nginx/current link;
- run GET-only smoke with provider `not_called` and database write `false`;
- write the deploy SHA marker only after commit-point verification.

Old backup pruning is not part of this packet.

## 5. Failure and rollback plan

- Before lock acquisition or backup creation: stop with production unchanged.
- Backup failure: stop before sync/activation; retain evidence and do not clear an ambiguous/active lock.
- Failure before activation: script-scoped cleanup only; do not claim deployment.
- Failure after app rebuild/activation but before marker commit: rely on the script's automatic activation restore. If the script reports unknown outcome or manual rollback required, retain the lock and perform read-only reconciliation before any next write.
- Do not issue blind rollback when the marker/current link/transaction state is ambiguous.
- Only after positive reconciliation proves current marker `905f9f...` and the same-stamp transaction points back to `18d3ff...`, a separately authorized rollback may use:

```text
uv run python scripts/deploy-tencent-cloud-production.py \
  --rollback \
  --confirm-production audit.lute-tlz-dddd.top \
  --expected-current-sha 905f9f485dbe1a390fbd1fefea5a89f09722cdf9 \
  --restore-sha 18d3ff86170558b0ea20eafc1dbd6e4a32c33a28 \
  --ssh-key "$SSH_KEY_PATH" \
  --stamp h1-strict-abstention-905f9f4-20260722T090844Z
```

No schema rollback is needed because schema application is excluded.

## 6. Phase C — post-deploy L3 acceptance

1. Require deploy command exit `0`; do not infer success from an intermediate healthy container or completed backup.
2. Run deployment-state audit with:
   - expected deploy SHA `905f9f485dbe1a390fbd1fefea5a89f09722cdf9`;
   - required backup stamp `h1-strict-abstention-905f9f4-20260722T090844Z`;
   - ClamAV sidecar requirement;
   - exact manifest/static/current-link/deploy-marker checks;
   - zero audit delta during the audit itself.
3. Capture release-guard S1 at the new SHA and compare S0→S1. Any schema, business-table or object-storage delta fails closed. A startup-only audit row must be retained and separately classified; it cannot be silently ignored or called a pass.
4. Run GET-only production smoke and permission/catalog read-only checks. Provider status must remain `not_called`; no query/review/document/index/agent write is permitted.
5. Full browser frontend acceptance is a separate L4 `audit-log-only` packet because the hardened flow can write audit events and requires a unique acceptance run ID. It is not included in standard deployment acceptance.
6. Live H1 provider UAT remains a separate exact-SHA/run/model authorization after deployment.

Allowed status after this packet is `deployed_l3_verified`, never `live_uat_passed`.

## 7. Remote candidate branch deletion plan

Deletion is sequenced after Phase C succeeds so the branch remains available during deployment triage.

Preconditions:

1. PR `#259` remains `MERGED` with head `13b0fb1c5f0e318a2e6052105c529d75676f78db` and merge SHA `905f9f485dbe1a390fbd1fefea5a89f09722cdf9`.
2. Remote `main` remains the merge SHA or a descendant containing it.
3. The candidate commit is reachable from remote `main` and no open PR or recovery procedure names the branch as required.
4. Production deployment has reached `deployed_l3_verified`, or the owner explicitly chooses deletion before deployment despite the operational preference to retain it.
5. The local candidate branch and local planning/draft work are outside the deletion scope.

Authorized deletion command:

```text
git push origin --delete codex/h1-strict-output-contract-20260722
```

Post-delete verification:

- `git ls-remote --heads origin codex/h1-strict-output-contract-20260722` returns no ref;
- remote `main` is unchanged;
- PR `#259` and commits `13b0fb1...` / `905f9f4...` remain reachable;
- local branch, named stash and local planning/draft files remain intact.

Recovery, if the ref is needed later:

```text
git push origin 13b0fb1c5f0e318a2e6052105c529d75676f78db:refs/heads/codex/h1-strict-output-contract-20260722
```

Do not delete the local branch, stash, deployment backups or old production backups in this packet.

## 8. Authorization sequence

1. Authorize Phase A production read-only preflight only.
2. Review Phase A evidence and freeze stamp `h1-strict-abstention-905f9f4-20260722T090844Z`.
3. Authorize Phase B deployment with exact old/new SHA, stamp and scoped side effects; optionally include conditional rollback authority.
4. Execute Phase C L3 acceptance.
5. Separately authorize the single remote branch DELETE after the chosen deletion precondition is met.
6. Separately authorize frontend audit-log-only acceptance or H1 live provider UAT if desired.

## 9. Copy-ready authorization templates

Phase A — production read-only preflight:

> 明确授权执行 Loop 72 Phase A 生产只读预检：目标部署 SHA `905f9f485dbe1a390fbd1fefea5a89f09722cdf9`，预期当前生产 SHA `18d3ff86170558b0ea20eafc1dbd6e4a32c33a28`；允许使用仓库外 `$SSH_KEY_PATH` 执行 SSH 只读 deployment-state audit、release-guard S0、部署脚本非 execute preflight、锁/磁盘/五类备份路径和 stamp 冲突检查；允许 preflight 使用 `--allow-dirty` 仅绕过本地 planning/draft 脏状态，不得用于 execute。禁止备份创建、锁清理、文件同步、容器重建、DB/schema/env/runtime 写入、provider、review/document/index/agent 写入、deploy、branch DELETE。任何 SHA、拓扑、健康、锁、磁盘或 stamp 漂移立即停止。

Phase B — exact deployment; Phase A has frozen the stamp:

> 明确授权执行 Loop 72 Phase B 标准生产部署：Phase A 为 GO，当前生产 SHA 为 `18d3ff86170558b0ea20eafc1dbd6e4a32c33a28`，目标 SHA 为 `905f9f485dbe1a390fbd1fefea5a89f09722cdf9`，deploy stamp 为 `h1-strict-abstention-905f9f4-20260722T090844Z`；允许对本地五个 planning/draft 路径创建并保留 named stash、切换并 fast-forward clean `main`，允许部署脚本创建 app/env/DB/Nginx/Web 五类备份、执行脚本限定的 stale same-stamp cleanup 与 app `rsync --delete`、构建 app/static、重建 app、原子切换 versioned static/Nginx/current、GET-only smoke 和 deploy marker 写入；禁止 `--apply-schema`、provider/query/review/document/index/agent 写入、env 修改、旧备份清理和 branch DELETE。失败按计划 fail-closed；未知写入结果保留锁并先只读 reconciliation，不得盲目重试或 rollback。

## 10. Phase A fresh evidence result

- Decision: `GO` for requesting Phase B authorization; this is not deployment authorization and production remains unchanged.
- Conditional-L3 deployment-state audit: `pass`, issues/warnings `0`, exact production SHA/current/manifest/static `18d3ff8...`, app/PostgreSQL/ClamAV/Nginx healthy, embeddings `49051`, audit delta `0`, DB write `false`, provider `not_called`.
- Release-guard S0: `pass`, snapshot ID `17e9e22928781fb0f0fdd692378027f6153c5715e6a1b66dfdd8b2b3ef08f92a`, blocking reasons `0`, collector provider attempts `0`, capture side effect `none`.
- Non-execute deploy preflight: `pass`; no post-deploy report was created, as expected for preflight mode.
- Lock/stamp check: deploy lock absent; five backup candidates, completion marker, transaction directory, incoming release paths and next markers all absent.
- Disk: root filesystem has `54,118,164 KiB` available (about `51.6 GiB`) at `83%` utilization. No cleanup was run or authorized.

Remote branch DELETE — only after the chosen deletion precondition is met:

> 明确授权仅删除远端分支 `codex/h1-strict-output-contract-20260722`：执行前必须确认 PR #259 仍为 MERGED、远端 main 包含 merge SHA `905f9f485dbe1a390fbd1fefea5a89f09722cdf9`、候选 commit `13b0fb1c5f0e318a2e6052105c529d75676f78db` 可从 main/PR 到达，并确认生产已达到 `deployed_l3_verified`；仅允许执行 `git push origin --delete codex/h1-strict-output-contract-20260722` 及删除前后的只读 refs/PR 校验。禁止删除本地分支、named stash、planning/draft 文件、部署备份或任何其他远端 ref；验证失败立即停止。
