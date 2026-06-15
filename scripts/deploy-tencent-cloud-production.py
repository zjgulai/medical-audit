#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
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

APP_RSYNC_EXCLUDES = (
    ".DS_Store",
    ".deploy-sha",
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
    "web/out/",
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
    allow_dirty: bool
    skip_web_build: bool
    skip_app_rebuild: bool
    apply_schema: bool
    skip_smoke: bool
    include_review_write: bool
    report_path: Path

    @property
    def ssh_target(self) -> str:
        return f"{self.ssh_user}@{self.ssh_host}"


def main() -> int:
    try:
        config = _config_from_args(_parse_args())
        _print_plan(config)
        _validate_local_state(config)
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
        _write_remote_deploy_sha(config)
        _rebuild_application(config)
        _run_remote_post_checks(config)
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
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run write operations against production after preflight succeeds.",
    )
    parser.add_argument(
        "--confirm-production",
        default="",
        help=f"Required with --execute. Must equal {DEFAULT_DOMAIN}.",
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
        "--include-review-write",
        action="store_true",
        help="Include the write-path review task flow in production smoke.",
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
    if args.execute and args.confirm_production != DEFAULT_DOMAIN:
        raise DeployError(
            f"--execute requires --confirm-production {DEFAULT_DOMAIN}",
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
        execute=bool(args.execute),
        allow_dirty=bool(args.allow_dirty),
        skip_web_build=bool(args.skip_web_build),
        skip_app_rebuild=bool(args.skip_app_rebuild),
        apply_schema=bool(args.apply_schema),
        skip_smoke=bool(args.skip_smoke),
        include_review_write=bool(args.include_review_write),
        report_path=report_path,
    )


def _print_plan(config: DeployConfig) -> None:
    mode = "execute" if config.execute else "preflight"
    print(f"mode: {mode}", flush=True)
    print(f"target: {config.ssh_target}", flush=True)
    print(f"remote_app_dir: {config.remote_app_dir}", flush=True)
    print(f"remote_web_dir: {config.remote_web_dir}", flush=True)
    print(f"base_url: {config.base_url}", flush=True)


def _validate_local_state(config: DeployConfig) -> None:
    if not config.ssh_key.exists():
        raise DeployError(f"SSH key not found: {config.ssh_key}")
    if not (config.repo_root / "configs/deploy/tencent-cloud/docker-compose.prod.yaml").exists():
        raise DeployError("production compose file is missing")
    if not (config.repo_root / "scripts/run-production-e2e-smoke.py").exists():
        raise DeployError("production smoke script is missing")
    _run_capture(["git", "rev-parse", "--is-inside-work-tree"], cwd=config.repo_root)
    dirty = _run_capture(["git", "status", "--porcelain"], cwd=config.repo_root).strip()
    if dirty and not config.allow_dirty:
        raise DeployError("git worktree is dirty; commit changes or pass --allow-dirty")
    if config.execute and config.skip_web_build and not (config.repo_root / "web/out").is_dir():
        raise DeployError("web/out is missing; remove --skip-web-build or build first")


def _run_remote_preflight(config: DeployConfig) -> None:
    mount_format = '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
    script = f"""
set -euo pipefail
test -d {shlex.quote(config.remote_app_dir)}
test -f {shlex.quote(config.remote_app_dir)}/configs/deploy/tencent-cloud/medical-audit.env
test -d {shlex.quote(config.remote_web_dir)}
docker inspect medical_audit_app >/dev/null
docker inspect medical_audit_pg >/dev/null
docker inspect ai_video_nginx >/dev/null
docker inspect ai_video_nginx --format {shlex.quote(mount_format)} \
  | grep -F '{config.remote_web_dir} -> /var/www/audit' >/dev/null
if ! docker exec ai_video_nginx nginx -t >/tmp/medical-audit-nginx-test.log 2>&1; then
  echo "WARNING shared-nginx-test-failed"
  sed -n '1,20p' /tmp/medical-audit-nginx-test.log
fi
curl -fsS http://127.0.0.1:18080/health >/dev/null
curl -fsS http://127.0.0.1:18080/index/search-backend >/dev/null
"""
    _ssh(config, script)


def _build_static_frontend(config: DeployConfig) -> None:
    if config.skip_web_build:
        print("skip web build", flush=True)
        return
    _run(["pnpm", "web:build:static"], cwd=config.repo_root)


def _create_remote_backups(config: DeployConfig) -> None:
    script = f"""
set -euo pipefail
stamp={shlex.quote(config.stamp)}
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
docker exec -i medical_audit_pg sh -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | gzip > /opt/medical-audit/backups/db/pre-deploy-${{stamp}}.sql.gz
cp /opt/ai-video/deploy/lighthouse/nginx.conf \
  /opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-${{stamp}}
tar -czf /opt/medical-audit/backups/web/audit-web-pre-deploy-${{stamp}}.tar.gz \
  -C /var/www audit
"""
    _ssh(config, script)


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
    sha = _run_capture(["git", "rev-parse", "HEAD"], cwd=config.repo_root).strip()
    script = f"""
set -euo pipefail
printf '%s\\n' {shlex.quote(sha)} > {shlex.quote(config.remote_app_dir)}/.deploy-sha
"""
    _ssh(config, script)


def _rebuild_application(config: DeployConfig) -> None:
    if config.skip_app_rebuild:
        print("skip app rebuild", flush=True)
        return
    script = f"""
set -euo pipefail
cd {shlex.quote(config.remote_app_dir)}
docker compose -f configs/deploy/tencent-cloud/docker-compose.prod.yaml \
  --env-file configs/deploy/tencent-cloud/medical-audit.env build app
docker compose -f configs/deploy/tencent-cloud/docker-compose.prod.yaml \
  --env-file configs/deploy/tencent-cloud/medical-audit.env up -d app
"""
    _ssh(config, script)


def _run_remote_post_checks(config: DeployConfig) -> None:
    sha = _run_capture(["git", "rev-parse", "HEAD"], cwd=config.repo_root).strip()
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
test "$(cat .deploy-sha)" = {shlex.quote(sha)}
docker compose -f configs/deploy/tencent-cloud/docker-compose.prod.yaml \
  --env-file configs/deploy/tencent-cloud/medical-audit.env ps
if ! docker exec ai_video_nginx nginx -t >/tmp/medical-audit-nginx-test.log 2>&1; then
  echo "WARNING shared-nginx-test-failed"
  sed -n '1,20p' /tmp/medical-audit-nginx-test.log
fi
curl -fsS http://127.0.0.1:18080/health >/dev/null
curl -fsS http://127.0.0.1:18080/index/search-backend >/dev/null
curl -fsS {shlex.quote(config.base_url)}/api/v1/index/search-backend >/dev/null
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
    if config.include_review_write:
        args.append("--include-review-write")
    _run(args, cwd=config.repo_root)


def _ssh(config: DeployConfig, script: str) -> None:
    print(
        "+ ssh "
        f"-i {shlex.quote(str(config.ssh_key))} "
        "-o StrictHostKeyChecking=no "
        "-o IdentitiesOnly=yes "
        f"{config.ssh_target} bash -lc <remote-script>",
        flush=True,
    )
    subprocess.run(_ssh_args(config, script), cwd=config.repo_root, check=True, text=True)


def _ssh_args(config: DeployConfig, script: str) -> list[str]:
    return [
        "ssh",
        "-i",
        str(config.ssh_key),
        "-o",
        "StrictHostKeyChecking=no",
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
        "-o StrictHostKeyChecking=no "
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
