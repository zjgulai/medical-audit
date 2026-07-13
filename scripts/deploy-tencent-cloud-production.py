#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

DEFAULT_HOST = "101.34.52.232"
DEFAULT_USER = "ubuntu"
DEFAULT_DOMAIN = "audit.lute-tlz-dddd.top"
DEFAULT_REMOTE_APP_DIR = "/opt/medical-audit/app"
DEFAULT_REMOTE_WEB_DIR = "/var/www/audit"
DEFAULT_BASE_URL = f"https://{DEFAULT_DOMAIN}"
REMOTE_BACKUP_TIMEOUT_SECONDS = 45 * 60
REMOTE_COMPLETION_CHECK_TIMEOUT_SECONDS = 60
REMOTE_COMPLETION_POLL_SECONDS = 5

APP_RSYNC_EXCLUDES = (
    ".DS_Store",
    ".deploy-sha",
    ".git",
    ".git/",
    ".kiro/",
    ".playwright-mcp/",
    ".venv/",
    ".codegraph/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    "__pycache__/",
    "node_modules/",
    "web/.next/",
    "web/node_modules/",
    "web/test-results/",
    "web/playwright-report/",
    "drafts/",
    "tmp/",
    "data/",
    "archive/",
    "opendesign/",
    "ref/",
    "*.pyc",
    "*.pem",
    "*.key",
    "*.env",
    "*.uploading.cfg",
)


class DeployError(RuntimeError):
    pass


@dataclass(frozen=True)
class DeployConfig:
    repo_root: Path
    ssh_key: Path
    ssh_user: str
    ssh_host: str
    remote_app_dir: str
    remote_web_dir: str
    base_url: str
    stamp: str
    execute: bool
    rollback: bool
    allow_dirty: bool
    skip_web_build: bool
    skip_app_rebuild: bool
    apply_schema: bool
    skip_smoke: bool
    include_query_provider_smoke: bool
    include_review_write: bool
    confirm_production_write: str
    approved_sha: str
    expected_current_sha: str
    restore_sha: str
    report_path: Path

    @property
    def ssh_target(self) -> str:
        return f"{self.ssh_user}@{self.ssh_host}"


def main() -> int:
    try:
        config = _config_from_args(_parse_args())
        _print_plan(config)
        _validate_local_state(config)
        if config.rollback:
            _run_remote_rollback(config)
            return 0
        _run_remote_preflight(config)
        if not config.execute:
            print("Preflight passed. Add --execute --confirm-production to deploy.")
            return 0
        _build_static_frontend(config)
        _create_remote_backups(config)
        _cleanup_remote_sync_artifacts(config)
        _sync_application(config)
        _sync_static_frontend(config)
        if config.apply_schema:
            _apply_schema(config)
        _rebuild_application(config)
        _run_remote_post_checks(config)
        _write_remote_deploy_sha(config)
        _run_production_smoke(config)
    except DeployError as exc:
        print(f"deploy failed: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"command failed with exit code {exc.returncode}", file=sys.stderr)
        return exc.returncode or 1
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Deploy AuditScope to Tencent Cloud. The default mode is read-only "
            "preflight; production writes require --execute and confirmation."
        ),
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--execute",
        action="store_true",
        help="Run write operations against production after preflight succeeds.",
    )
    mode_group.add_argument(
        "--rollback",
        action="store_true",
        help="Restore app/web and deploy SHA from one verified pre-deploy backup stamp.",
    )
    parser.add_argument(
        "--confirm-production",
        default="",
        help=f"Required with --execute. Must equal {DEFAULT_DOMAIN}.",
    )
    parser.add_argument(
        "--approved-sha",
        default="",
        help=(
            "Required with --execute. The fresh local main HEAD and origin/main must both "
            "equal this full commit SHA."
        ),
    )
    parser.add_argument(
        "--expected-current-sha",
        default="",
        help="Required with --rollback. Rollback stops unless remote .deploy-sha equals it.",
    )
    parser.add_argument(
        "--restore-sha",
        default="",
        help="Required with --rollback. Must match .deploy-sha inside the app backup.",
    )
    parser.add_argument(
        "--ssh-key",
        default=os.environ.get("MEDICAL_AUDIT_DEPLOY_SSH_KEY", "ai_video.pem"),
        help="Path to the SSH key. Defaults to ./ai_video.pem or env override.",
    )
    parser.add_argument("--ssh-user", default=DEFAULT_USER)
    parser.add_argument("--ssh-host", default=DEFAULT_HOST)
    parser.add_argument("--remote-app-dir", default=DEFAULT_REMOTE_APP_DIR)
    parser.add_argument("--remote-web-dir", default=DEFAULT_REMOTE_WEB_DIR)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--stamp",
        default=time.strftime("%Y%m%dT%H%M%S%z"),
        help="Deployment stamp used for remote backup and local report names.",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Allow deploying from a dirty git worktree.",
    )
    parser.add_argument(
        "--skip-web-build",
        action="store_true",
        help="Reuse the existing web/out directory instead of building it.",
    )
    parser.add_argument(
        "--skip-app-rebuild",
        action="store_true",
        help="Only sync files and static assets; do not rebuild/restart app.",
    )
    parser.add_argument(
        "--apply-schema",
        action="store_true",
        help="Apply sql/knowledge-query-schema.sql to production after sync.",
    )
    parser.add_argument(
        "--skip-smoke",
        action="store_true",
        help="Skip local production E2E smoke after deployment.",
    )
    parser.add_argument(
        "--include-query-provider-smoke",
        action="store_true",
        help=(
            "After deployment, opt in to query/provider smoke that may write query/audit "
            "history. Requires --confirm-production-write."
        ),
    )
    parser.add_argument(
        "--include-review-write",
        action="store_true",
        help="Include the write-path review task flow in production smoke.",
    )
    parser.add_argument(
        "--confirm-production-write",
        default="",
        help=(
            "Required with live query/provider or review smoke. Must equal the production "
            f"domain {DEFAULT_DOMAIN}."
        ),
    )
    parser.add_argument(
        "--report",
        default="",
        help=(
            "Local smoke report path. Defaults to "
            "tmp/outputs/production-e2e-smoke-after-deploy-<stamp>.json."
        ),
    )
    return parser.parse_args()


def _config_from_args(args: argparse.Namespace) -> DeployConfig:
    repo_root = Path(__file__).resolve().parents[1]
    ssh_key = Path(str(args.ssh_key)).expanduser()
    if not ssh_key.is_absolute():
        ssh_key = repo_root / ssh_key
    rollback = bool(args.rollback)
    execute = bool(args.execute)
    if (execute or rollback) and args.confirm_production != DEFAULT_DOMAIN:
        raise DeployError(
            f"live deployment actions require --confirm-production {DEFAULT_DOMAIN}",
        )
    approved_sha = _validated_sha(
        args.approved_sha,
        option="--approved-sha",
        required=execute,
    )
    expected_current_sha = _validated_sha(
        args.expected_current_sha,
        option="--expected-current-sha",
        required=rollback,
    )
    restore_sha = _validated_sha(
        args.restore_sha,
        option="--restore-sha",
        required=rollback,
    )
    include_query_provider_smoke = bool(args.include_query_provider_smoke)
    include_review_write = bool(args.include_review_write)
    if include_review_write and not include_query_provider_smoke:
        raise DeployError(
            "--include-review-write requires --include-query-provider-smoke",
        )
    confirm_production_write = str(args.confirm_production_write).strip()
    if include_query_provider_smoke and confirm_production_write != DEFAULT_DOMAIN:
        raise DeployError(
            f"live smoke requires --confirm-production-write {DEFAULT_DOMAIN}",
        )
    report_arg = str(args.report).strip()
    if not report_arg:
        report_path = repo_root / "tmp" / "outputs" / (
            f"production-e2e-smoke-after-deploy-{args.stamp}.json"
        )
    else:
        report_path = Path(report_arg).expanduser()
        if not report_path.is_absolute():
            report_path = repo_root / report_path
    return DeployConfig(
        repo_root=repo_root,
        ssh_key=ssh_key,
        ssh_user=str(args.ssh_user),
        ssh_host=str(args.ssh_host),
        remote_app_dir=str(args.remote_app_dir).rstrip("/"),
        remote_web_dir=str(args.remote_web_dir).rstrip("/"),
        base_url=str(args.base_url).rstrip("/"),
        stamp=str(args.stamp),
        execute=execute,
        rollback=rollback,
        allow_dirty=bool(args.allow_dirty),
        skip_web_build=bool(args.skip_web_build),
        skip_app_rebuild=bool(args.skip_app_rebuild),
        apply_schema=bool(args.apply_schema),
        skip_smoke=bool(args.skip_smoke),
        include_query_provider_smoke=include_query_provider_smoke,
        include_review_write=include_review_write,
        confirm_production_write=confirm_production_write,
        approved_sha=approved_sha,
        expected_current_sha=expected_current_sha,
        restore_sha=restore_sha,
        report_path=report_path,
    )


def _validated_sha(value: object, *, option: str, required: bool) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        if required:
            raise DeployError(f"{option} requires a full 40-character commit SHA")
        return ""
    if re.fullmatch(r"[0-9a-f]{40}", normalized) is None:
        raise DeployError(f"{option} requires a full 40-character commit SHA")
    return normalized


def _print_plan(config: DeployConfig) -> None:
    mode = "rollback" if config.rollback else "execute" if config.execute else "preflight"
    print(f"mode: {mode}", flush=True)
    print(f"target: {config.ssh_target}", flush=True)
    print(f"remote_app_dir: {config.remote_app_dir}", flush=True)
    print(f"remote_web_dir: {config.remote_web_dir}", flush=True)
    print(f"base_url: {config.base_url}", flush=True)


def _validate_local_state(config: DeployConfig) -> None:
    if not config.ssh_key.exists():
        raise DeployError(f"SSH key not found: {config.ssh_key}")
    if config.rollback:
        return
    if not (config.repo_root / "configs/deploy/tencent-cloud/docker-compose.prod.yaml").exists():
        raise DeployError("production compose file is missing")
    if not (config.repo_root / "scripts/run-production-e2e-smoke.py").exists():
        raise DeployError("production smoke script is missing")
    _run_capture(["git", "rev-parse", "--is-inside-work-tree"], cwd=config.repo_root)
    dirty = _run_capture(["git", "status", "--porcelain"], cwd=config.repo_root).strip()
    if config.execute and config.allow_dirty:
        raise DeployError("production execute forbids --allow-dirty")
    if dirty and not config.allow_dirty:
        raise DeployError("git worktree is dirty; commit changes or pass --allow-dirty")
    if config.execute:
        _validate_release_source(config)
    if config.execute and config.skip_web_build and not (config.repo_root / "web/out").is_dir():
        raise DeployError("web/out is missing; remove --skip-web-build or build first")


def _validate_release_source(config: DeployConfig) -> None:
    _run(
        [
            "git",
            "fetch",
            "--quiet",
            "origin",
            "+refs/heads/main:refs/remotes/origin/main",
        ],
        cwd=config.repo_root,
    )
    branch = _run_capture(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
        cwd=config.repo_root,
    ).strip()
    if branch != "main":
        raise DeployError(f"production execute requires main branch; current branch: {branch}")
    head_sha = _run_capture(["git", "rev-parse", "HEAD"], cwd=config.repo_root).strip()
    origin_main_sha = _run_capture(
        ["git", "rev-parse", "origin/main"],
        cwd=config.repo_root,
    ).strip()
    if head_sha != origin_main_sha:
        raise DeployError(
            f"production execute requires HEAD == origin/main; HEAD={head_sha} "
            f"origin/main={origin_main_sha}",
        )
    if head_sha != config.approved_sha:
        raise DeployError(
            f"production execute target does not match approved SHA: {config.approved_sha}",
        )


def _run_remote_preflight(config: DeployConfig) -> None:
    script = f"""
set -euo pipefail
test -d {shlex.quote(config.remote_app_dir)}
test -f {shlex.quote(config.remote_app_dir)}/configs/deploy/tencent-cloud/medical-audit.env
test -d {shlex.quote(config.remote_web_dir)}
docker inspect medical_audit_app >/dev/null
docker inspect medical_audit_pg >/dev/null
docker inspect ai_video_nginx >/dev/null
docker exec ai_video_nginx nginx -t
curl -fsS http://127.0.0.1:18080/health >/dev/null
auth_headers=(
  -H 'X-User-Id: deploy-smoke-admin'
  -H 'X-Role: it-admin'
  -H 'X-Project-Key: SELF-CHECK-FUND-20260607'
  -H 'X-Tenant-Id: hospital-demo'
)
curl -fsS "${{auth_headers[@]}}" \
  http://127.0.0.1:18080/knowledge-base/catalog >/dev/null
"""
    _ssh(config, script)


def _build_static_frontend(config: DeployConfig) -> None:
    if config.skip_web_build:
        print("skip web build", flush=True)
        return
    _run(["pnpm", "web:build:static"], cwd=config.repo_root)


def _create_remote_backups(config: DeployConfig) -> None:
    backup_marker = f"/tmp/medical-audit-deploy-backups-{config.stamp}.complete"
    app_backup = f"/opt/medical-audit/backups/app/pre-deploy-{config.stamp}.tar.gz"
    env_backup = (
        f"/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-{config.stamp}"
    )
    db_backup = f"/opt/medical-audit/backups/db/pre-deploy-{config.stamp}.sql.gz"
    nginx_backup = (
        f"/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-{config.stamp}"
    )
    web_backup = (
        f"/opt/medical-audit/backups/web/audit-web-pre-deploy-{config.stamp}.tar.gz"
    )
    stale_backup_cleanup_script = f"""
set -euo pipefail
rm -f {shlex.quote(backup_marker)} \
  {shlex.quote(app_backup)} \
  {shlex.quote(env_backup)} \
  {shlex.quote(db_backup)} \
  {shlex.quote(nginx_backup)} \
  {shlex.quote(web_backup)}
"""
    script = f"""
set -euo pipefail
stamp={shlex.quote(config.stamp)}
backup_marker={shlex.quote(backup_marker)}
rm -f "$backup_marker"
mkdir -p /opt/medical-audit/backups/app \
  /opt/medical-audit/backups/env \
  /opt/medical-audit/backups/db \
  /opt/medical-audit/backups/nginx \
  /opt/medical-audit/backups/web \
  /opt/medical-audit/analytics-uploads \
  /opt/medical-audit/document-uploads
tar --exclude='.git' --exclude='.venv' --exclude='tmp' --exclude='data' \
  -czf /opt/medical-audit/backups/app/pre-deploy-${{stamp}}.tar.gz \
  -C /opt/medical-audit app
cp {shlex.quote(config.remote_app_dir)}/configs/deploy/tencent-cloud/medical-audit.env \
  /opt/medical-audit/backups/env/medical-audit.env.pre-deploy-${{stamp}}
docker exec medical_audit_pg sh -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | gzip > /opt/medical-audit/backups/db/pre-deploy-${{stamp}}.sql.gz
cp /opt/ai-video/deploy/lighthouse/nginx.conf \
  /opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-${{stamp}}
tar -czf /opt/medical-audit/backups/web/audit-web-pre-deploy-${{stamp}}.tar.gz \
  -C /var/www audit
printf 'complete\\n' > "$backup_marker"
"""
    completion_check_script = f"""
set -euo pipefail
backup_marker={shlex.quote(backup_marker)}
test -s "$backup_marker"
test -s {shlex.quote(app_backup)}
test -s {shlex.quote(env_backup)}
test -s {shlex.quote(db_backup)}
test -s {shlex.quote(nginx_backup)}
test -s {shlex.quote(web_backup)}
"""
    _ssh(config, stale_backup_cleanup_script)
    _ssh_background_with_completion(
        config,
        script,
        timeout_seconds=REMOTE_BACKUP_TIMEOUT_SECONDS,
        completion_check_script=completion_check_script,
        timeout_description="remote backups",
        job_name=f"medical-audit-deploy-backups-{config.stamp}",
    )


def _sync_application(config: DeployConfig) -> None:
    remote = f"{config.ssh_target}:{config.remote_app_dir}/"
    args = [
        "rsync",
        "-az",
        "--delete",
        "--itemize-changes",
        "-e",
        _ssh_transport(config),
    ]
    for pattern in APP_RSYNC_EXCLUDES:
        args.extend(["--exclude", pattern])
    args.extend([f"{config.repo_root}/", remote])
    _run(args, cwd=config.repo_root)


def _cleanup_remote_sync_artifacts(config: DeployConfig) -> None:
    script = f"""
set -euo pipefail
git_file={shlex.quote(config.remote_app_dir)}/.git
if [ -f "$git_file" ]; then
  rm -f "$git_file"
fi
web_parent_dir={shlex.quote(config.remote_app_dir)}/web
web_out_dir={shlex.quote(config.remote_app_dir)}/web/out
test -d "$web_parent_dir"
if [ -e "$web_out_dir" ] || [ -L "$web_out_dir" ]; then
  if ! rm -rf "$web_out_dir"; then
    sudo -n rm -rf "$web_out_dir"
  fi
fi
if ! mkdir -p "$web_out_dir"; then
  sudo -n install -d -o "$(id -u)" -g "$(id -g)" "$web_out_dir"
fi
if [ ! -w "$web_out_dir" ]; then
  sudo -n chown -R "$(id -u):$(id -g)" "$web_out_dir"
fi
src_dir={shlex.quote(config.remote_app_dir)}/src
test -d "$src_dir"
find "$src_dir" -type f \\( \
  -name '*.pyc' -o \
  -name '*.pyo' -o \
  -name '*.uploading.cfg' \
\\) -print -delete
find "$src_dir" -type d -name __pycache__ -empty -print -delete
"""
    _ssh(config, script)


def _sync_static_frontend(config: DeployConfig) -> None:
    web_out = config.repo_root / "web" / "out"
    if not web_out.is_dir():
        raise DeployError("web/out is missing after build")
    remote = f"{config.ssh_target}:{config.remote_web_dir}/"
    _run(
        [
            "rsync",
            "-az",
            "--delete",
            "--itemize-changes",
            "-e",
            _ssh_transport(config),
            f"{web_out}/",
            remote,
        ],
        cwd=config.repo_root,
    )


def _apply_schema(config: DeployConfig) -> None:
    psql_command = 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'
    script = f"""
set -euo pipefail
docker exec -i medical_audit_pg sh -lc {shlex.quote(psql_command)} \
  < {shlex.quote(config.remote_app_dir)}/sql/knowledge-query-schema.sql
"""
    _ssh(config, script)


def _write_remote_deploy_sha(config: DeployConfig) -> None:
    sha = _current_deploy_sha(config)
    script = f"""
set -euo pipefail
printf '%s\\n' {shlex.quote(sha)} > {shlex.quote(config.remote_app_dir)}/.deploy-sha
"""
    _ssh(config, script)


def _rebuild_application(config: DeployConfig) -> None:
    if config.skip_app_rebuild:
        print("skip app rebuild", flush=True)
        return
    sha = _current_deploy_sha(config)
    container_id_format = "{{.Id}}"
    health_format = "{{.State.Health.Status}}"
    script = f"""
set -euo pipefail
export MEDICAL_AUDIT_DEPLOY_SHA={shlex.quote(sha)}
cd {shlex.quote(config.remote_app_dir)}
postgres_id_before="$(docker inspect medical_audit_pg \
  --format {shlex.quote(container_id_format)})"
test -n "$postgres_id_before"
clamav_service_present=0
clamav_id_before=""
if docker compose -f configs/deploy/tencent-cloud/docker-compose.prod.yaml \
  --env-file configs/deploy/tencent-cloud/medical-audit.env config --services \
  | grep -Fx clamav >/dev/null; then
  clamav_service_present=1
  clamav_id_before="$(docker inspect medical_audit_clamav \
    --format {shlex.quote(container_id_format)})"
  test -n "$clamav_id_before"
  test "$(docker inspect medical_audit_clamav \
    --format {shlex.quote(health_format)})" = "healthy"
fi
docker compose -f configs/deploy/tencent-cloud/docker-compose.prod.yaml \
  --env-file configs/deploy/tencent-cloud/medical-audit.env build app
docker compose -f configs/deploy/tencent-cloud/docker-compose.prod.yaml \
  --env-file configs/deploy/tencent-cloud/medical-audit.env up -d --no-deps app
test "$(docker inspect medical_audit_pg \
  --format {shlex.quote(container_id_format)})" = "$postgres_id_before"
if [ "$clamav_service_present" -eq 1 ]; then
  test "$(docker inspect medical_audit_clamav \
    --format {shlex.quote(container_id_format)})" = "$clamav_id_before"
fi
"""
    _ssh(config, script)


def _current_deploy_sha(config: DeployConfig) -> str:
    return _run_capture(["git", "rev-parse", "HEAD"], cwd=config.repo_root).strip()


def _run_remote_post_checks(config: DeployConfig) -> None:
    health_format = "{{.State.Health.Status}}"
    script = f"""
set -euo pipefail
cd {shlex.quote(config.remote_app_dir)}
for attempt in $(seq 1 60); do
  app_health="$(docker inspect medical_audit_app \
    --format {shlex.quote(health_format)} 2>/dev/null || true)"
  if [ "$app_health" = "healthy" ]; then
    break
  fi
  sleep 2
done
test "$(docker inspect medical_audit_app \
  --format {shlex.quote(health_format)})" = "healthy"
if docker compose -f configs/deploy/tencent-cloud/docker-compose.prod.yaml \
  --env-file configs/deploy/tencent-cloud/medical-audit.env config --services \
  | grep -Fx clamav >/dev/null; then
  for attempt in $(seq 1 60); do
    clamav_health="$(docker inspect medical_audit_clamav \
      --format {shlex.quote(health_format)} 2>/dev/null || true)"
    if [ "$clamav_health" = "healthy" ]; then
      break
    fi
    sleep 2
  done
  test "$(docker inspect medical_audit_clamav \
    --format {shlex.quote(health_format)})" = "healthy"
fi
docker compose -f configs/deploy/tencent-cloud/docker-compose.prod.yaml \
  --env-file configs/deploy/tencent-cloud/medical-audit.env ps
docker exec ai_video_nginx nginx -t
curl -fsS http://127.0.0.1:18080/health >/dev/null
auth_headers=(
  -H 'X-User-Id: deploy-smoke-admin'
  -H 'X-Role: it-admin'
  -H 'X-Project-Key: SELF-CHECK-FUND-20260607'
  -H 'X-Tenant-Id: hospital-demo'
)
curl -fsS "${{auth_headers[@]}}" \
  http://127.0.0.1:18080/knowledge-base/catalog >/dev/null
curl -fsS "${{auth_headers[@]}}" \
  {shlex.quote(config.base_url)}/api/v1/knowledge-base/catalog >/dev/null
curl -fsS {shlex.quote(config.base_url)}/api/v1/health >/dev/null
curl -fsS "${{auth_headers[@]}}" {shlex.quote(config.base_url)}/documents >/dev/null
"""
    _ssh(config, script)


def _run_production_smoke(config: DeployConfig) -> None:
    if config.skip_smoke:
        print("skip production smoke", flush=True)
        return
    config.report_path.parent.mkdir(parents=True, exist_ok=True)
    args = [
        sys.executable,
        str(config.repo_root / "scripts/run-production-e2e-smoke.py"),
        "--base-url",
        config.base_url,
        "--report",
        str(config.report_path),
    ]
    if config.include_query_provider_smoke:
        args.extend(
            [
                "--include-query-provider-smoke",
                "--confirm-production-write",
                config.confirm_production_write,
            ],
        )
    if config.include_review_write:
        args.append("--include-review-write")
    _run(args, cwd=config.repo_root)


def _run_remote_rollback(config: DeployConfig) -> None:
    app_backup = f"/opt/medical-audit/backups/app/pre-deploy-{config.stamp}.tar.gz"
    web_backup = f"/opt/medical-audit/backups/web/audit-web-pre-deploy-{config.stamp}.tar.gz"
    safe_stamp = _safe_remote_job_name(config.stamp)
    container_id_format = "{{.Id}}"
    health_format = "{{.State.Health.Status}}"
    script = f"""
set -euo pipefail
remote_app_dir={shlex.quote(config.remote_app_dir)}
remote_web_dir={shlex.quote(config.remote_web_dir)}
app_backup={shlex.quote(app_backup)}
web_backup={shlex.quote(web_backup)}
expected_current_sha={shlex.quote(config.expected_current_sha)}
restore_sha={shlex.quote(config.restore_sha)}
test -s "$app_backup"
test -s "$web_backup"
test -s "$remote_app_dir/.deploy-sha"
test "$(cat "$remote_app_dir/.deploy-sha")" = "$expected_current_sha"
tar -tzf "$app_backup" >/dev/null
tar -tzf "$web_backup" >/dev/null
restore_root="$(mktemp -d /opt/medical-audit/rollback-{safe_stamp}.XXXXXX)"
preserved_env="$(mktemp)"
trap 'rm -rf "$restore_root" "$preserved_env"' EXIT
cp "$remote_app_dir/configs/deploy/tencent-cloud/medical-audit.env" "$preserved_env"
tar -xzf "$app_backup" -C "$restore_root"
tar -xzf "$web_backup" -C "$restore_root"
test -d "$restore_root/app"
test -d "$restore_root/audit"
test -s "$restore_root/app/.deploy-sha"
test "$(cat "$restore_root/app/.deploy-sha")" = "$restore_sha"
rsync -a --delete \
  --exclude '.deploy-sha' \
  --exclude 'configs/deploy/tencent-cloud/medical-audit.env' \
  "$restore_root/app/" "$remote_app_dir/"
cp "$preserved_env" "$remote_app_dir/configs/deploy/tencent-cloud/medical-audit.env"
chmod 600 "$remote_app_dir/configs/deploy/tencent-cloud/medical-audit.env"
rsync -a --delete "$restore_root/audit/" "$remote_web_dir/"
cd "$remote_app_dir"
postgres_id_before="$(docker inspect medical_audit_pg --format {shlex.quote(container_id_format)})"
clamav_id_before=""
if docker inspect medical_audit_clamav >/dev/null 2>&1; then
  clamav_id_before="$(docker inspect medical_audit_clamav \
    --format {shlex.quote(container_id_format)})"
fi
export MEDICAL_AUDIT_DEPLOY_SHA="$restore_sha"
docker compose -f configs/deploy/tencent-cloud/docker-compose.prod.yaml \
  --env-file configs/deploy/tencent-cloud/medical-audit.env build app
docker compose -f configs/deploy/tencent-cloud/docker-compose.prod.yaml \
  --env-file configs/deploy/tencent-cloud/medical-audit.env up -d --no-deps app
for attempt in $(seq 1 60); do
  app_health="$(docker inspect medical_audit_app \
    --format {shlex.quote(health_format)} 2>/dev/null || true)"
  if [ "$app_health" = "healthy" ]; then
    break
  fi
  sleep 2
done
test "$(docker inspect medical_audit_app --format {shlex.quote(health_format)})" = "healthy"
test "$(docker inspect medical_audit_pg \
  --format {shlex.quote(container_id_format)})" = "$postgres_id_before"
if [ -n "$clamav_id_before" ]; then
  test "$(docker inspect medical_audit_clamav \
    --format {shlex.quote(container_id_format)})" = "$clamav_id_before"
fi
docker exec ai_video_nginx nginx -t
curl -fsS http://127.0.0.1:18080/health >/dev/null
printf '%s\\n' "$restore_sha" > "$remote_app_dir/.deploy-sha"
test "$(cat "$remote_app_dir/.deploy-sha")" = "$restore_sha"
"""
    _ssh(config, script)


def _ssh(
    config: DeployConfig,
    script: str,
    *,
    timeout_seconds: int | None = None,
    completion_check_script: str | None = None,
    timeout_description: str = "remote script",
) -> None:
    print(
        "+ ssh "
        "-n "
        f"-i {shlex.quote(str(config.ssh_key))} "
        "-o BatchMode=yes "
        "-o StrictHostKeyChecking=yes "
        "-o IdentitiesOnly=yes "
        f"{config.ssh_target} bash -lc <remote-script>",
        flush=True,
    )
    try:
        subprocess.run(
            _ssh_args(config, script),
            cwd=config.repo_root,
            check=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        if completion_check_script is None:
            raise DeployError(
                f"{timeout_description} timed out after {exc.timeout} seconds",
            ) from exc
        print(
            f"WARNING {timeout_description} ssh timed out after {exc.timeout} seconds; "
            "checking remote completion marker",
            flush=True,
        )
        subprocess.run(
            _ssh_args(config, completion_check_script),
            cwd=config.repo_root,
            check=True,
            text=True,
            timeout=REMOTE_COMPLETION_CHECK_TIMEOUT_SECONDS,
        )
        print(
            f"WARNING {timeout_description} completed remotely after ssh timeout; continuing",
            flush=True,
        )
        return
    if completion_check_script is not None:
        subprocess.run(
            _ssh_args(config, completion_check_script),
            cwd=config.repo_root,
            check=True,
            text=True,
            timeout=REMOTE_COMPLETION_CHECK_TIMEOUT_SECONDS,
        )


def _ssh_background_with_completion(
    config: DeployConfig,
    script: str,
    completion_check_script: str,
    *,
    timeout_seconds: int,
    timeout_description: str,
    job_name: str,
) -> None:
    safe_job_name = _safe_remote_job_name(job_name)
    remote_script = f"/tmp/{safe_job_name}.sh"
    remote_log = f"/tmp/{safe_job_name}.log"
    remote_pid = f"/tmp/{safe_job_name}.pid"
    starter_script = f"""
set -euo pipefail
job_script={shlex.quote(remote_script)}
job_log={shlex.quote(remote_log)}
job_pid={shlex.quote(remote_pid)}
cat > "$job_script" <<'MEDICAL_AUDIT_REMOTE_JOB_EOF'
{script}
MEDICAL_AUDIT_REMOTE_JOB_EOF
chmod 700 "$job_script"
rm -f "$job_log" "$job_pid"
nohup bash "$job_script" > "$job_log" 2>&1 &
printf '%s\\n' "$!" > "$job_pid"
"""
    print(
        f"+ ssh background {config.ssh_target} {timeout_description} "
        f"job={safe_job_name}",
        flush=True,
    )
    subprocess.run(
        _ssh_args(config, starter_script),
        cwd=config.repo_root,
        check=True,
        text=True,
        timeout=REMOTE_COMPLETION_CHECK_TIMEOUT_SECONDS,
    )
    deadline = time.monotonic() + timeout_seconds
    poll_script = f"""
set -euo pipefail
job_pid={shlex.quote(remote_pid)}
job_log={shlex.quote(remote_log)}
if bash -lc {shlex.quote(completion_check_script)}; then
  echo "MEDICAL_AUDIT_REMOTE_JOB_STATUS=complete"
  exit 0
fi
pid="$(cat "$job_pid" 2>/dev/null || true)"
if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
  echo "MEDICAL_AUDIT_REMOTE_JOB_STATUS=running"
  exit 0
fi
echo "MEDICAL_AUDIT_REMOTE_JOB_STATUS=failed"
echo "remote job exited before completion marker"
tail -n 80 "$job_log" || true
exit 0
"""
    while True:
        completed = subprocess.run(
            _ssh_args(config, poll_script),
            cwd=config.repo_root,
            check=False,
            text=True,
            capture_output=True,
            timeout=REMOTE_COMPLETION_CHECK_TIMEOUT_SECONDS,
        )
        detail = "\n".join(
            part.strip()
            for part in (completed.stdout, completed.stderr)
            if part.strip()
        )
        status = _extract_remote_job_status(completed.stdout)
        if status == "complete":
            print(f"{timeout_description} completed remotely", flush=True)
            return
        if status == "failed":
            raise DeployError(
                f"{timeout_description} failed before completion marker"
                + (f":\n{detail}" if detail else ""),
            )
        if status != "running":
            if completed.returncode != 0:
                raise DeployError(
                    f"{timeout_description} poll command failed"
                    + (f":\n{detail}" if detail else ""),
                )
            raise DeployError(
                f"{timeout_description} returned unknown poll status"
                + (f":\n{detail}" if detail else ""),
            )
        if time.monotonic() >= deadline:
            raise DeployError(
                f"{timeout_description} timed out after {timeout_seconds} seconds",
            )
        if completed.stdout.strip():
            print(completed.stdout.strip(), flush=True)
        time.sleep(REMOTE_COMPLETION_POLL_SECONDS)


def _extract_remote_job_status(stdout: str) -> str | None:
    prefix = "MEDICAL_AUDIT_REMOTE_JOB_STATUS="
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return None


def _safe_remote_job_name(job_name: str) -> str:
    safe = "".join(
        char if char.isalnum() or char in {"-", "_"} else "-" for char in job_name
    ).strip("-")
    return safe or "medical-audit-remote-job"


def _ssh_args(config: DeployConfig, script: str) -> list[str]:
    return [
        "ssh",
        "-n",
        "-i",
        str(config.ssh_key),
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "IdentitiesOnly=yes",
        config.ssh_target,
        "bash",
        "-lc",
        shlex.quote(script),
    ]


def _ssh_transport(config: DeployConfig) -> str:
    return (
        "ssh "
        f"-i {shlex.quote(str(config.ssh_key))} "
        "-o BatchMode=yes "
        "-o StrictHostKeyChecking=yes "
        "-o IdentitiesOnly=yes"
    )


def _run(args: Sequence[str], *, cwd: Path) -> None:
    print(_format_command(args), flush=True)
    subprocess.run(args, cwd=cwd, check=True, text=True)


def _run_capture(args: Sequence[str], *, cwd: Path) -> str:
    completed = subprocess.run(
        args,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout


def _format_command(args: Sequence[str]) -> str:
    return "+ " + " ".join(shlex.quote(str(arg)) for arg in args)


if __name__ == "__main__":
    raise SystemExit(main())
