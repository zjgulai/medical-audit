#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_HOST = "101.34.52.232"
DEFAULT_USER = "ubuntu"
DEFAULT_DOMAIN = "audit.lute-tlz-dddd.top"
DEFAULT_REMOTE_APP_DIR = "/opt/medical-audit/app"
DEFAULT_REMOTE_WEB_DIR = "/var/www/audit"
DEFAULT_REMOTE_BACKUP_ROOT = "/opt/medical-audit/backups"
DEFAULT_EXPECTED_EMBEDDINGS = 48985
DEFAULT_JSON_OUTPUT = "tmp/outputs/tencent-cloud-deployment-state-latest.json"
DEFAULT_MARKDOWN_OUTPUT = "tmp/outputs/tencent-cloud-deployment-state-latest.md"
BACKUP_CATEGORIES = (
    "app",
    "env",
    "db",
    "nginx",
    "web",
    "web-container",
    "ai-video-nginx-bind-mount",
)


class AuditError(RuntimeError):
    pass


def main() -> int:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    json_output = _resolve_output(repo_root, str(args.json_output))
    markdown_output = _resolve_output(repo_root, str(args.markdown_output))
    ssh_key = _resolve_ssh_key(repo_root, str(args.ssh_key))

    try:
        remote_report = _collect_remote_report(
            ssh_key=ssh_key,
            ssh_user=str(args.ssh_user),
            ssh_host=str(args.ssh_host),
            remote_app_dir=str(args.remote_app_dir),
            remote_web_dir=str(args.remote_web_dir),
            remote_backup_root=str(args.remote_backup_root),
            backup_limit=int(args.backup_limit),
        )
        local_smoke_reports = _summarize_local_smoke_reports(
            repo_root / "tmp" / "outputs",
            limit=int(args.local_smoke_limit),
        )
        report = _build_report(
            remote_report=remote_report,
            local_smoke_reports=local_smoke_reports,
            expected_deploy_sha=_optional_text(args.expected_deploy_sha),
            required_backup_stamp=_optional_text(args.required_backup_stamp),
            expected_embeddings=int(args.expected_matching_embeddings),
        )
    except AuditError as exc:
        print(f"audit failed: {exc}", file=sys.stderr)
        return 2

    _write_json(json_output, report)
    _write_markdown(markdown_output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a read-only deployment state audit for the Tencent Cloud production host.",
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
    parser.add_argument("--remote-backup-root", default=DEFAULT_REMOTE_BACKUP_ROOT)
    parser.add_argument("--expected-deploy-sha", default="")
    parser.add_argument("--required-backup-stamp", default="")
    parser.add_argument(
        "--expected-matching-embeddings",
        type=int,
        default=DEFAULT_EXPECTED_EMBEDDINGS,
    )
    parser.add_argument("--backup-limit", type=int, default=5)
    parser.add_argument("--local-smoke-limit", type=int, default=5)
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def _resolve_output(repo_root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return repo_root / path


def _resolve_ssh_key(repo_root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return repo_root / path


def _optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _collect_remote_report(
    *,
    ssh_key: Path,
    ssh_user: str,
    ssh_host: str,
    remote_app_dir: str,
    remote_web_dir: str,
    remote_backup_root: str,
    backup_limit: int,
) -> dict[str, Any]:
    if not ssh_key.exists():
        raise AuditError(f"SSH key not found: {ssh_key}")
    remote_code = _remote_audit_code(
        remote_app_dir=remote_app_dir,
        remote_web_dir=remote_web_dir,
        remote_backup_root=remote_backup_root,
        backup_limit=max(1, backup_limit),
    )
    command = [
        "ssh",
        "-i",
        str(ssh_key),
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "IdentitiesOnly=yes",
        f"{ssh_user}@{ssh_host}",
        "python3",
        "-",
    ]
    print(
        "+ ssh "
        f"-i {shlex.quote(str(ssh_key))} "
        "-o StrictHostKeyChecking=no "
        "-o IdentitiesOnly=yes "
        f"{ssh_user}@{ssh_host} python3 - <remote-audit>",
        flush=True,
    )
    completed = subprocess.run(
        command,
        input=remote_code,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise AuditError(completed.stderr.strip() or "remote audit command failed")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AuditError("remote audit returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise AuditError("remote audit returned non-object JSON")
    return payload


def _remote_audit_code(
    *,
    remote_app_dir: str,
    remote_web_dir: str,
    remote_backup_root: str,
    backup_limit: int,
) -> str:
    return f"""
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

APP_DIR = {json.dumps(remote_app_dir, ensure_ascii=False)}
WEB_DIR = {json.dumps(remote_web_dir, ensure_ascii=False)}
BACKUP_ROOT = {json.dumps(remote_backup_root, ensure_ascii=False)}
BACKUP_LIMIT = {backup_limit}
BACKUP_CATEGORIES = {json.dumps(BACKUP_CATEGORIES)}


def run(command):
    return subprocess.run(command, check=False, capture_output=True, text=True)


def docker_inspect_json(name, template):
    result = run(["docker", "inspect", name, "--format", template])
    if result.returncode != 0:
        return {{"available": False, "error": result.stderr.strip()}}
    text = result.stdout.strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = text
    return {{"available": True, "value": value}}


def container_state(name):
    inspected = docker_inspect_json(name, "{{{{json .State}}}}")
    state = inspected.get("value") if inspected.get("available") else {{}}
    labels = docker_inspect_json(name, "{{{{json .Config.Labels}}}}")
    label_value = labels.get("value") if labels.get("available") else {{}}
    if not isinstance(label_value, dict):
        label_value = {{}}
    health = state.get("Health") if isinstance(state, dict) else None
    health_status = health.get("Status") if isinstance(health, dict) else None
    return {{
        "available": bool(inspected.get("available")),
        "status": state.get("Status") if isinstance(state, dict) else None,
        "running": state.get("Running") if isinstance(state, dict) else None,
        "health": health_status,
        "started_at": state.get("StartedAt") if isinstance(state, dict) else None,
        "compose_project": label_value.get("com.docker.compose.project"),
        "compose_service": label_value.get("com.docker.compose.service"),
    }}


def nginx_test():
    result = run(["docker", "exec", "ai_video_nginx", "nginx", "-t"])
    return {{"passed": result.returncode == 0}}


def nginx_mounts():
    inspected = docker_inspect_json("ai_video_nginx", "{{{{json .Mounts}}}}")
    mounts = inspected.get("value") if inspected.get("available") else []
    if not isinstance(mounts, list):
        mounts = []
    audit_mount = None
    for mount in mounts:
        if not isinstance(mount, dict):
            continue
        if mount.get("Destination") == "/var/www/audit":
            audit_mount = {{
                "source": mount.get("Source"),
                "destination": mount.get("Destination"),
                "mode": mount.get("Mode"),
                "rw": mount.get("RW"),
            }}
            break
    return {{"audit_mount": audit_mount, "mount_count": len(mounts)}}


def read_file(path):
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def http_json(url):
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            body = response.read().decode("utf-8")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {{"raw": body[:500]}}
        return {{"ok": True, "payload": payload}}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {{"ok": False, "error": str(exc)}}


def backup_entries(category):
    root = Path(BACKUP_ROOT) / category
    if not root.exists():
        return []
    entries = []
    for path in root.rglob("*"):
        try:
            stat = path.stat()
        except OSError:
            continue
        if not path.is_file():
            continue
        entries.append(
            {{
                "path": str(path),
                "size_bytes": stat.st_size,
                "mtime": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(stat.st_mtime)),
            }}
        )
    entries.sort(key=lambda item: item["mtime"], reverse=True)
    return entries[:BACKUP_LIMIT]


def backup_index():
    return {{category: backup_entries(category) for category in BACKUP_CATEGORIES}}


report = {{
    "collected_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "remote_app_dir": APP_DIR,
    "remote_web_dir": WEB_DIR,
    "remote_backup_root": BACKUP_ROOT,
    "deploy_sha": read_file(str(Path(APP_DIR) / ".deploy-sha")),
    "containers": {{
        "medical_audit_app": container_state("medical_audit_app"),
        "medical_audit_pg": container_state("medical_audit_pg"),
        "ai_video_nginx": container_state("ai_video_nginx"),
    }},
    "nginx": {{
        "config_test": nginx_test(),
        "mounts": nginx_mounts(),
    }},
    "local_backend": {{
        "health": http_json("http://127.0.0.1:18080/health"),
        "search_backend": http_json("http://127.0.0.1:18080/index/search-backend"),
    }},
    "backups": backup_index(),
}}
print(json.dumps(report, ensure_ascii=False))
"""


def _summarize_local_smoke_reports(output_dir: Path, *, limit: int) -> list[dict[str, Any]]:
    if not output_dir.exists():
        return []
    candidates = sorted(
        output_dir.glob("production-e2e-smoke*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    reports: list[dict[str, Any]] = []
    for path in candidates[: max(1, limit)]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        reports.append(
            {
                "path": str(path),
                "status": payload.get("status"),
                "base_url": payload.get("base_url"),
                "started_at": payload.get("started_at"),
                "finished_at": payload.get("finished_at"),
                "step_count": len(payload.get("steps", []))
                if isinstance(payload.get("steps"), list)
                else 0,
            }
        )
    return reports


def _build_report(
    *,
    remote_report: dict[str, Any],
    local_smoke_reports: list[dict[str, Any]],
    expected_deploy_sha: str | None,
    required_backup_stamp: str | None,
    expected_embeddings: int,
) -> dict[str, Any]:
    issues: list[str] = []
    deploy_sha = _string_or_none(remote_report.get("deploy_sha"))
    if expected_deploy_sha and deploy_sha != expected_deploy_sha:
        issues.append("deploy-sha-mismatch")
    for name in ("medical_audit_app", "medical_audit_pg"):
        health = _container_health(remote_report, name)
        if health != "healthy":
            issues.append(f"{name}-not-healthy")
    if not _nginx_test_passed(remote_report):
        issues.append("nginx-config-test-failed")
    if not _audit_mount_valid(remote_report):
        issues.append("audit-static-bind-mount-missing")
    if not _search_backend_ready(remote_report, expected_embeddings):
        issues.append("search-backend-not-ready")
    if required_backup_stamp:
        missing = _missing_backup_categories(remote_report, required_backup_stamp)
        if missing:
            issues.append("missing-required-backup-stamp:" + ",".join(missing))
    latest_smoke = local_smoke_reports[0] if local_smoke_reports else None
    if latest_smoke and latest_smoke.get("status") != "pass":
        issues.append("latest-local-smoke-not-pass")
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "expected_deploy_sha": expected_deploy_sha,
        "required_backup_stamp": required_backup_stamp,
        "expected_matching_embeddings": expected_embeddings,
        "summary": {
            "deploy_sha": deploy_sha,
            "app_health": _container_health(remote_report, "medical_audit_app"),
            "postgres_health": _container_health(remote_report, "medical_audit_pg"),
            "nginx_config_test": _nginx_test_passed(remote_report),
            "audit_mount_present": _audit_mount_valid(remote_report),
            "search_backend_ready": _search_backend_ready(remote_report, expected_embeddings),
            "latest_local_smoke_status": latest_smoke.get("status") if latest_smoke else None,
        },
        "remote": remote_report,
        "local_smoke_reports": local_smoke_reports,
    }


def _container_health(remote_report: dict[str, Any], name: str) -> str | None:
    container = _nested_dict(remote_report, "containers", name)
    direct_health = _string_or_none(container.get("health"))
    if direct_health:
        return direct_health
    state = container.get("state")
    if not isinstance(state, dict):
        return None
    health = state.get("Health")
    if isinstance(health, dict):
        return _string_or_none(health.get("Status"))
    return _string_or_none(state.get("Status"))


def _nginx_test_passed(remote_report: dict[str, Any]) -> bool:
    config_test = _nested_dict(remote_report, "nginx", "config_test")
    return config_test.get("passed") is True


def _audit_mount_valid(remote_report: dict[str, Any]) -> bool:
    mounts = _nested_dict(remote_report, "nginx", "mounts")
    audit_mount = mounts.get("audit_mount")
    if not isinstance(audit_mount, dict):
        return False
    return audit_mount.get("destination") == "/var/www/audit" and audit_mount.get("rw") is False


def _search_backend_ready(remote_report: dict[str, Any], expected_embeddings: int) -> bool:
    search_backend = _nested_dict(remote_report, "local_backend", "search_backend")
    if search_backend.get("ok") is not True:
        return False
    payload = search_backend.get("payload")
    if not isinstance(payload, dict):
        return False
    details = payload.get("details")
    if not isinstance(details, dict):
        return False
    return (
        payload.get("backend") == "postgres"
        and payload.get("ready") is True
        and details.get("matching_embedding_count") == expected_embeddings
    )


def _missing_backup_categories(remote_report: dict[str, Any], stamp: str) -> list[str]:
    backups = remote_report.get("backups")
    if not isinstance(backups, dict):
        return list(BACKUP_CATEGORIES)
    missing: list[str] = []
    for category in ("app", "env", "db", "nginx", "web"):
        entries = backups.get(category)
        if not isinstance(entries, list):
            missing.append(category)
            continue
        if not any(stamp in str(_dict_or_empty(item).get("path", "")) for item in entries):
            missing.append(category)
    return missing


def _nested_dict(payload: dict[str, Any], *keys: str) -> dict[str, Any]:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return {}
        current = current.get(key)
    return current if isinstance(current, dict) else {}


def _dict_or_empty(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _write_json(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = _dict_or_empty(report.get("summary"))
    issues = report.get("issues")
    issue_lines = (
        [f"- `{issue}`" for issue in issues]
        if isinstance(issues, list) and issues
        else ["- 无"]
    )
    smoke_reports = report.get("local_smoke_reports")
    smoke_lines: list[str] = []
    if isinstance(smoke_reports, list):
        for item in smoke_reports:
            smoke = _dict_or_empty(item)
            smoke_lines.append(
                f"- `{smoke.get('status')}` `{smoke.get('finished_at')}` `{smoke.get('path')}`"
            )
    if not smoke_lines:
        smoke_lines = ["- 无"]
    body = "\n".join(
        [
            "# 腾讯云生产部署状态巡检报告",
            "",
            f"- `status`: `{report.get('status')}`",
            f"- `deploy_sha`: `{summary.get('deploy_sha')}`",
            f"- `app_health`: `{summary.get('app_health')}`",
            f"- `postgres_health`: `{summary.get('postgres_health')}`",
            f"- `nginx_config_test`: `{summary.get('nginx_config_test')}`",
            f"- `audit_mount_present`: `{summary.get('audit_mount_present')}`",
            f"- `search_backend_ready`: `{summary.get('search_backend_ready')}`",
            f"- `latest_local_smoke_status`: `{summary.get('latest_local_smoke_status')}`",
            "",
            "## 阻断项",
            "",
            *issue_lines,
            "",
            "## 本地 Smoke 报告",
            "",
            *smoke_lines,
            "",
        ]
    )
    path.write_text(body, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
