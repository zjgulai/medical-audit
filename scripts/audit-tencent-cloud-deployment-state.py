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
DEFAULT_BASE_URL = f"https://{DEFAULT_DOMAIN}"
DEFAULT_REMOTE_APP_DIR = "/opt/medical-audit/app"
DEFAULT_REMOTE_WEB_DIR = "/var/www/audit"
DEFAULT_REMOTE_BACKUP_ROOT = "/opt/medical-audit/backups"
DEFAULT_MIN_MATCHING_EMBEDDINGS = 1
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
            base_url=str(args.base_url),
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
            min_matching_embeddings=_min_matching_embeddings(args),
            require_clamav_sidecar=bool(args.require_clamav_sidecar),
            expected_dlp_review_provider=_optional_text(args.expected_dlp_review_provider),
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
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--remote-app-dir", default=DEFAULT_REMOTE_APP_DIR)
    parser.add_argument("--remote-web-dir", default=DEFAULT_REMOTE_WEB_DIR)
    parser.add_argument("--remote-backup-root", default=DEFAULT_REMOTE_BACKUP_ROOT)
    parser.add_argument("--expected-deploy-sha", default="")
    parser.add_argument("--required-backup-stamp", default="")
    parser.add_argument(
        "--min-matching-embeddings",
        type=int,
        default=None,
        help="Minimum acceptable active PostgreSQL embedding count. Defaults to 1.",
    )
    parser.add_argument(
        "--expected-matching-embeddings",
        type=int,
        default=None,
        help=(
            "Deprecated alias for --min-matching-embeddings. The value is treated "
            "as a lower bound, not an exact count."
        ),
    )
    parser.add_argument("--backup-limit", type=int, default=5)
    parser.add_argument("--local-smoke-limit", type=int, default=5)
    parser.add_argument(
        "--require-clamav-sidecar",
        action="store_true",
        help="Require the medical_audit_clamav sidecar to be present in compose and healthy.",
    )
    parser.add_argument(
        "--expected-dlp-review-provider",
        default="",
        help="Require MEDICAL_AUDIT_DOCUMENT_UPLOAD_DLP_REVIEWER_PROVIDER to match.",
    )
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


def _min_matching_embeddings(args: argparse.Namespace) -> int:
    explicit_min = getattr(args, "min_matching_embeddings", None)
    if explicit_min is not None:
        return int(explicit_min)
    legacy_expected = getattr(args, "expected_matching_embeddings", None)
    if legacy_expected is not None:
        return int(legacy_expected)
    return DEFAULT_MIN_MATCHING_EMBEDDINGS


def _collect_remote_report(
    *,
    ssh_key: Path,
    ssh_user: str,
    ssh_host: str,
    remote_app_dir: str,
    remote_web_dir: str,
    remote_backup_root: str,
    base_url: str,
    backup_limit: int,
) -> dict[str, Any]:
    if not ssh_key.exists():
        raise AuditError(f"SSH key not found: {ssh_key}")
    remote_code = _remote_audit_code(
        remote_app_dir=remote_app_dir,
        remote_web_dir=remote_web_dir,
        remote_backup_root=remote_backup_root,
        base_url=base_url.rstrip("/"),
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
    base_url: str,
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
BASE_URL = {json.dumps(base_url, ensure_ascii=False)}
BACKUP_LIMIT = {backup_limit}
BACKUP_CATEGORIES = {json.dumps(BACKUP_CATEGORIES)}
ENV_FILE_NAME = "medical" + "-audit" + ".env"
AUDIT_HEADERS = {{
    "User-Agent": "medical-audit-state-audit/1.0",
    "X-User-Id": "deployment-state-auditor",
    "X-Role": "it-admin",
    "X-Project-Key": "SELF-CHECK-FUND-20260607",
    "X-Tenant-Id": "hospital-demo",
}}


def run(command, cwd=None):
    return subprocess.run(command, check=False, capture_output=True, text=True, cwd=cwd)


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


def compose_services():
    compose_path = str(Path(APP_DIR) / "configs/deploy/tencent-cloud/docker-compose.prod.yaml")
    env_path = str(Path(APP_DIR) / "configs/deploy/tencent-cloud" / ENV_FILE_NAME)
    result = run(
        [
            "docker",
            "compose",
            "-f",
            compose_path,
            "--env-file",
            env_path,
            "config",
            "--services",
        ],
        cwd=APP_DIR,
    )
    if result.returncode != 0:
        return {{"ok": False, "services": [], "error": result.stderr.strip()}}
    services = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return {{"ok": True, "services": services}}


def governance_env():
    env_path = Path(APP_DIR) / "configs/deploy/tencent-cloud" / ENV_FILE_NAME
    keys = {{
        "MEDICAL_AUDIT_DOCUMENT_UPLOAD_VIRUS_SCANNER_PROVIDER",
        "MEDICAL_AUDIT_DOCUMENT_UPLOAD_DLP_REVIEWER_PROVIDER",
        "MEDICAL_AUDIT_DOCUMENT_UPLOAD_CLAMAV_HOST",
        "MEDICAL_AUDIT_DOCUMENT_UPLOAD_CLAMAV_PORT",
        "MEDICAL_AUDIT_DOCUMENT_UPLOAD_CLAMAV_TIMEOUT_SECONDS",
        "MEDICAL_AUDIT_DOCUMENT_UPLOAD_CLAMAV_CHUNK_SIZE_BYTES",
    }}
    values = {{}}
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", maxsplit=1)
            if key in keys:
                values[key] = value
    except OSError as exc:
        return {{"ok": False, "values": {{}}, "error": str(exc)}}
    return {{"ok": True, "values": values}}


def nginx_test():
    result = run(["docker", "exec", "ai_video_nginx", "nginx", "-t"])
    return {{
        "passed": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }}


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


def http_json(url, headers=None):
    try:
        request = urllib.request.Request(url, headers=headers or {{}})
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {{"raw": body[:500]}}
        return {{"ok": True, "payload": payload}}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {{"ok": False, "error": str(exc)}}


def http_status(url, expected_texts=None, headers=None):
    expected_texts = expected_texts or []
    try:
        request_headers = {{"User-Agent": "medical-audit-state-audit/1.0"}}
        if headers:
            request_headers.update(headers)
        request = urllib.request.Request(
            url,
            headers=request_headers,
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read()
            status_code = response.getcode()
            content_type = response.headers.get("content-type")
        expected_utf8_text = {{
            text: text.encode("utf-8") in body for text in expected_texts
        }}
        return {{
            "ok": status_code == 200 and all(expected_utf8_text.values()),
            "status_code": status_code,
            "content_type": content_type,
            "content_length": len(body),
            "expected_utf8_text": expected_utf8_text,
        }}
    except urllib.error.HTTPError as exc:
        return {{"ok": False, "status_code": exc.code, "error": str(exc)}}
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
        "medical_audit_clamav": container_state("medical_audit_clamav"),
        "ai_video_nginx": container_state("ai_video_nginx"),
    }},
    "compose": compose_services(),
    "document_upload_governance": governance_env(),
    "nginx": {{
        "config_test": nginx_test(),
        "mounts": nginx_mounts(),
    }},
    "local_backend": {{
        "health": http_json("http://127.0.0.1:18080/health"),
        "search_backend": http_json(
            "http://127.0.0.1:18080/index/search-backend",
            headers=AUDIT_HEADERS,
        ),
    }},
    "public_frontdoor": {{
        "health": http_status(BASE_URL + "/api/v1/health"),
        "documents": http_status(
            BASE_URL + "/documents",
            ["AI智能审计管理系统", "材料与知识库统一检索", "个人材料"],
            headers=AUDIT_HEADERS,
        ),
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
    min_matching_embeddings: int | None = None,
    require_clamav_sidecar: bool = False,
    expected_dlp_review_provider: str | None = None,
    expected_embeddings: int | None = None,
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    matching_embedding_floor = (
        min_matching_embeddings
        if min_matching_embeddings is not None
        else expected_embeddings
        if expected_embeddings is not None
        else DEFAULT_MIN_MATCHING_EMBEDDINGS
    )
    deploy_sha = _string_or_none(remote_report.get("deploy_sha"))
    if expected_deploy_sha and deploy_sha != expected_deploy_sha:
        issues.append("deploy-sha-mismatch")
    for name in ("medical_audit_app", "medical_audit_pg"):
        health = _container_health(remote_report, name)
        if health != "healthy":
            issues.append(f"{name}-not-healthy")
    nginx_config_test_passed = _nginx_test_passed(remote_report)
    audit_frontdoor_healthy = _audit_frontdoor_healthy(remote_report)
    if not nginx_config_test_passed and _shared_nginx_failure_is_non_blocking(
        remote_report,
        matching_embedding_floor,
    ):
        warnings.append("shared-nginx-config-test-failed-audit-route-healthy")
    elif not nginx_config_test_passed:
        issues.append("nginx-config-test-failed")
    if not _audit_mount_valid(remote_report) and not audit_frontdoor_healthy:
        issues.append("audit-static-bind-mount-missing")
    if not _search_backend_ready(remote_report, matching_embedding_floor):
        issues.append("search-backend-not-ready")
    if required_backup_stamp:
        missing = _missing_backup_categories(remote_report, required_backup_stamp)
        if missing:
            issues.append("missing-required-backup-stamp:" + ",".join(missing))
    if require_clamav_sidecar:
        if not _compose_service_present(remote_report, "clamav"):
            issues.append("clamav-compose-service-missing")
        if not _clamav_sidecar_healthy(remote_report):
            issues.append("medical_audit_clamav-not-healthy")
    dlp_review_provider = _governance_env_value(
        remote_report,
        "MEDICAL_AUDIT_DOCUMENT_UPLOAD_DLP_REVIEWER_PROVIDER",
    )
    if expected_dlp_review_provider and dlp_review_provider != expected_dlp_review_provider:
        issues.append("dlp-review-provider-mismatch")
    latest_smoke = local_smoke_reports[0] if local_smoke_reports else None
    if latest_smoke and latest_smoke.get("status") != "pass":
        issues.append("latest-local-smoke-not-pass")
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "warnings": warnings,
        "expected_deploy_sha": expected_deploy_sha,
        "required_backup_stamp": required_backup_stamp,
        "expected_dlp_review_provider": expected_dlp_review_provider,
        "minimum_matching_embeddings": matching_embedding_floor,
        "expected_matching_embeddings": matching_embedding_floor,
        "summary": {
            "deploy_sha": deploy_sha,
            "app_health": _container_health(remote_report, "medical_audit_app"),
            "postgres_health": _container_health(remote_report, "medical_audit_pg"),
            "clamav_health": _container_health(remote_report, "medical_audit_clamav"),
            "clamav_compose_service_present": _compose_service_present(remote_report, "clamav"),
            "virus_scan_provider": _governance_env_value(
                remote_report,
                "MEDICAL_AUDIT_DOCUMENT_UPLOAD_VIRUS_SCANNER_PROVIDER",
            ),
            "dlp_review_provider": dlp_review_provider,
            "nginx_config_test": _nginx_test_passed(remote_report),
            "audit_frontdoor_healthy": audit_frontdoor_healthy,
            "audit_mount_present": _audit_mount_valid(remote_report),
            "search_backend_ready": _search_backend_ready(
                remote_report,
                matching_embedding_floor,
            ),
            "matching_embedding_count": _matching_embedding_count(remote_report),
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


def _compose_service_present(remote_report: dict[str, Any], service_name: str) -> bool:
    compose = _nested_dict(remote_report, "compose")
    services = compose.get("services")
    return isinstance(services, list) and service_name in services


def _clamav_sidecar_healthy(remote_report: dict[str, Any]) -> bool:
    return _container_health(remote_report, "medical_audit_clamav") == "healthy"


def _governance_env_value(remote_report: dict[str, Any], key: str) -> str | None:
    governance = _nested_dict(remote_report, "document_upload_governance")
    values = governance.get("values")
    if not isinstance(values, dict):
        return None
    value = values.get(key)
    return value if isinstance(value, str) else None


def _nginx_test_passed(remote_report: dict[str, Any]) -> bool:
    config_test = _nested_dict(remote_report, "nginx", "config_test")
    return config_test.get("passed") is True


def _shared_nginx_failure_is_non_blocking(
    remote_report: dict[str, Any],
    min_matching_embeddings: int,
) -> bool:
    return (
        _container_health(remote_report, "medical_audit_app") == "healthy"
        and _container_health(remote_report, "medical_audit_pg") == "healthy"
        and (_audit_mount_valid(remote_report) or _audit_frontdoor_healthy(remote_report))
        and _search_backend_ready(remote_report, min_matching_embeddings)
        and _audit_frontdoor_healthy(remote_report)
    )


def _audit_frontdoor_healthy(remote_report: dict[str, Any]) -> bool:
    frontdoor = _nested_dict(remote_report, "public_frontdoor")
    health = _nested_dict(frontdoor, "health")
    documents = _nested_dict(frontdoor, "documents")
    return (
        health.get("ok") is True
        and health.get("status_code") == 200
        and documents.get("ok") is True
        and documents.get("status_code") == 200
    )


def _audit_mount_valid(remote_report: dict[str, Any]) -> bool:
    mounts = _nested_dict(remote_report, "nginx", "mounts")
    audit_mount = mounts.get("audit_mount")
    if not isinstance(audit_mount, dict):
        return False
    return audit_mount.get("destination") == "/var/www/audit" and audit_mount.get("rw") is False


def _search_backend_ready(remote_report: dict[str, Any], min_matching_embeddings: int) -> bool:
    search_backend = _nested_dict(remote_report, "local_backend", "search_backend")
    if search_backend.get("ok") is not True:
        return False
    payload = search_backend.get("payload")
    if not isinstance(payload, dict):
        return False
    matching_embedding_count = _matching_embedding_count(remote_report)
    if matching_embedding_count is None:
        return False
    return (
        payload.get("backend") == "postgres"
        and payload.get("ready") is True
        and matching_embedding_count >= min_matching_embeddings
    )


def _matching_embedding_count(remote_report: dict[str, Any]) -> int | None:
    search_backend = _nested_dict(remote_report, "local_backend", "search_backend")
    payload = search_backend.get("payload")
    if not isinstance(payload, dict):
        return None
    details = payload.get("details")
    if not isinstance(details, dict):
        return None
    value = details.get("matching_embedding_count")
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


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
    clamav_service_present = summary.get("clamav_compose_service_present")
    issues = report.get("issues")
    warnings = report.get("warnings")
    issue_lines = (
        [f"- `{issue}`" for issue in issues]
        if isinstance(issues, list) and issues
        else ["- 无"]
    )
    warning_lines = (
        [f"- `{warning}`" for warning in warnings]
        if isinstance(warnings, list) and warnings
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
            f"- `clamav_health`: `{summary.get('clamav_health')}`",
            f"- `clamav_compose_service_present`: `{clamav_service_present}`",
            f"- `virus_scan_provider`: `{summary.get('virus_scan_provider')}`",
            f"- `dlp_review_provider`: `{summary.get('dlp_review_provider')}`",
            f"- `nginx_config_test`: `{summary.get('nginx_config_test')}`",
            f"- `audit_frontdoor_healthy`: `{summary.get('audit_frontdoor_healthy')}`",
            f"- `audit_mount_present`: `{summary.get('audit_mount_present')}`",
            f"- `search_backend_ready`: `{summary.get('search_backend_ready')}`",
            f"- `latest_local_smoke_status`: `{summary.get('latest_local_smoke_status')}`",
            "",
            "## 阻断项",
            "",
            *issue_lines,
            "",
            "## 警告项",
            "",
            *warning_lines,
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
