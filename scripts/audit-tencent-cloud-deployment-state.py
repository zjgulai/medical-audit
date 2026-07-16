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
        description=(
            "Audit Tencent Cloud production deployment state and classify the run as L3 "
            "only when the measured audit snapshot is unchanged, the unique auditor identity "
            "has no events, and endpoint boundaries forbid write and provider side effects."
        ),
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
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "IdentitiesOnly=yes",
        f"{ssh_user}@{ssh_host}",
        "python3",
        "-",
    ]
    print(
        "+ ssh "
        f"-i {shlex.quote(str(ssh_key))} "
        "-o BatchMode=yes "
        "-o StrictHostKeyChecking=yes "
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
import hashlib
import json
import os
import re
import stat
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path, PurePosixPath

APP_DIR = {json.dumps(remote_app_dir, ensure_ascii=False)}
WEB_DIR = {json.dumps(remote_web_dir, ensure_ascii=False)}
BACKUP_ROOT = {json.dumps(remote_backup_root, ensure_ascii=False)}
BASE_URL = {json.dumps(base_url, ensure_ascii=False)}
BACKUP_LIMIT = {backup_limit}
BACKUP_CATEGORIES = {json.dumps(BACKUP_CATEGORIES)}
RELEASE_MANIFEST_FORMAT = "medical-audit-web-release-manifest-v1"
RELEASE_TARGET_PATTERN = re.compile(r"releases/([0-9a-f]{{40}})")
SHA256_PATTERN = re.compile(r"[0-9a-f]{{64}}")
GOVERNANCE_ENV_KEYS = (
    "MEDICAL_AUDIT_DOCUMENT_UPLOAD_VIRUS_SCANNER_PROVIDER",
    "MEDICAL_AUDIT_DOCUMENT_UPLOAD_DLP_REVIEWER_PROVIDER",
    "MEDICAL_AUDIT_DOCUMENT_UPLOAD_CLAMAV_HOST",
    "MEDICAL_AUDIT_DOCUMENT_UPLOAD_CLAMAV_PORT",
    "MEDICAL_AUDIT_DOCUMENT_UPLOAD_CLAMAV_TIMEOUT_SECONDS",
    "MEDICAL_AUDIT_DOCUMENT_UPLOAD_CLAMAV_CHUNK_SIZE_BYTES",
)
AUDIT_HEADERS = {{
    "User-Agent": "medical-audit-state-audit/1.0",
    "X-User-Id": "deployment-state-auditor-" + uuid.uuid4().hex,
    "X-Role": "it-admin",
    "X-Project-Key": "SELF-CHECK-FUND-20260607",
    "X-Tenant-Id": "hospital-demo",
}}


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


HTTP_OPENER = urllib.request.build_opener(NoRedirectHandler())


def run(command, cwd=None):
    return subprocess.run(command, check=False, capture_output=True, text=True, cwd=cwd)


def audit_log_event_snapshot():
    auditor_user_identifier = AUDIT_HEADERS["X-User-Id"]
    auditor_sql = auditor_user_identifier.replace("'", "''")
    sql = (
        "SELECT current_setting('transaction_read_only'), "
        "count(*), "
        "COALESCE(max(created_at)::text, 'none'), "
        "md5(COALESCE(string_agg(id::text, ',' ORDER BY id::text), '')), "
        f"count(*) FILTER (WHERE user_identifier = '{{auditor_sql}}') "
        "FROM audit_log_events;"
    )
    result = run(
        [
            "docker",
            "exec",
            "medical_audit_pg",
            "sh",
            "-c",
            'PGOPTIONS="-c default_transaction_read_only=on" '
            'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" "$POSTGRES_DB" '
            '-At -F "|" -c "$1"',
            "medical-audit-audit-log-snapshot",
            sql,
        ]
    )
    if result.returncode != 0:
        return {{"ok": False, "error": result.stderr.strip() or "audit-log-snapshot-failed"}}
    fields = [field.strip() for field in result.stdout.strip().split("|")]
    fingerprint = fields[3] if len(fields) == 5 else ""
    fingerprint_valid = len(fingerprint) == 32 and all(
        character in "0123456789abcdef" for character in fingerprint
    )
    if (
        len(fields) != 5
        or fields[0] != "on"
        or not fields[1].isdigit()
        or not fields[2]
        or not fingerprint_valid
        or not fields[4].isdigit()
    ):
        return {{"ok": False, "error": "audit-log-snapshot-invalid-output"}}
    return {{
        "ok": True,
        "transaction_read_only": fields[0],
        "count": int(fields[1]),
        "latest_created_at": fields[2],
        "event_id_fingerprint": fields[3],
        "auditor_user_identifier": auditor_user_identifier,
        "auditor_event_count": int(fields[4]),
    }}


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
    result = run(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            "label=com.docker.compose.project=medical-audit",
            "--format",
            "{{{{.Names}}}}",
        ]
    )
    if result.returncode != 0:
        return {{"ok": False, "services": [], "error": result.stderr.strip()}}
    container_names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    services = []
    inspect_errors = []
    for container_name in container_names:
        labels = docker_inspect_json(container_name, "{{{{json .Config.Labels}}}}")
        label_value = labels.get("value") if labels.get("available") else None
        if not isinstance(label_value, dict):
            inspect_errors.append(container_name)
            continue
        if label_value.get("com.docker.compose.project") != "medical-audit":
            continue
        service = label_value.get("com.docker.compose.service")
        if isinstance(service, str) and service:
            services.append(service)
    return {{
        "ok": not inspect_errors,
        "services": sorted(set(services)),
        "error": ",".join(inspect_errors) if inspect_errors else None,
    }}


def governance_env():
    result = run(
        [
            "docker",
            "exec",
            "medical_audit_app",
            "python3",
            "-c",
            (
                "import json, os, sys; "
                "print(json.dumps({{key: os.environ.get(key) for key in sys.argv[1:] "
                "if os.environ.get(key) is not None}}))"
            ),
            *GOVERNANCE_ENV_KEYS,
        ]
    )
    if result.returncode != 0:
        return {{"ok": False, "values": {{}}, "error": result.stderr.strip()}}
    try:
        values = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {{"ok": False, "values": {{}}, "error": "governance-env-invalid-json"}}
    if not isinstance(values, dict) or any(
        key not in GOVERNANCE_ENV_KEYS or not isinstance(value, str)
        for key, value in values.items()
    ):
        return {{"ok": False, "values": {{}}, "error": "governance-env-invalid-values"}}
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


def empty_release_state(error):
    return {{
        "ok": False,
        "error": error,
        "current_release_target": None,
        "release_sha": None,
        "manifest_source_sha": None,
        "remote_manifest_sha256": None,
        "manifest_file_count": 0,
        "manifest_mismatch_count": 1,
        "selected_html_path": None,
        "selected_html_sha256": None,
        "selected_static_path": None,
        "selected_static_sha256": None,
    }}


def hash_regular_file(path):
    try:
        before = path.lstat()
    except OSError as exc:
        raise RuntimeError("release-file-stat-failed") from exc
    if not stat.S_ISREG(before.st_mode):
        raise RuntimeError("release-entry-not-regular")
    digest = hashlib.sha256()
    size_bytes = 0
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
                size_bytes += len(chunk)
        after = path.lstat()
    except OSError as exc:
        raise RuntimeError("release-file-read-failed") from exc
    if (
        before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or size_bytes != after.st_size
    ):
        raise RuntimeError("release-file-changed-during-audit")
    return digest.hexdigest(), size_bytes


def valid_manifest_path(value):
    if not isinstance(value, str) or not value or "\\\\" in value:
        return False
    candidate = PurePosixPath(value)
    return (
        not candidate.is_absolute()
        and candidate.as_posix() == value
        and value != "release-manifest.json"
        and all(part not in ("", ".", "..") for part in candidate.parts)
    )


def collect_release_files(release_root):
    collected = {{}}
    invalid_count = 0

    def visit(directory, relative_directory):
        nonlocal invalid_count
        try:
            entries = list(os.scandir(directory))
        except OSError as exc:
            raise RuntimeError("release-directory-scan-failed") from exc
        for entry in entries:
            relative_path = (
                f"{{relative_directory}}/{{entry.name}}"
                if relative_directory
                else entry.name
            )
            try:
                entry_stat = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise RuntimeError("release-entry-stat-failed") from exc
            if stat.S_ISDIR(entry_stat.st_mode):
                visit(Path(entry.path), relative_path)
                continue
            if not stat.S_ISREG(entry_stat.st_mode):
                invalid_count += 1
                continue
            if relative_path == "release-manifest.json":
                continue
            file_sha256, size_bytes = hash_regular_file(Path(entry.path))
            collected[relative_path] = {{
                "sha256": file_sha256,
                "size_bytes": size_bytes,
            }}

    visit(release_root, "")
    return collected, invalid_count


def release_state():
    state = empty_release_state("current-release-invalid")
    web_root = Path(WEB_DIR)
    current = web_root / "current"
    try:
        current_stat = current.lstat()
    except OSError:
        return state
    if not stat.S_ISLNK(current_stat.st_mode):
        return state
    try:
        current_target = os.readlink(current)
    except OSError:
        return state
    state["current_release_target"] = current_target
    matched_target = RELEASE_TARGET_PATTERN.fullmatch(current_target)
    if matched_target is None:
        return state
    release_sha = matched_target.group(1)
    state["release_sha"] = release_sha
    releases_root = web_root / "releases"
    release_root = releases_root / release_sha
    try:
        releases_stat = releases_root.lstat()
        release_stat = release_root.lstat()
        resolved_current = current.resolve(strict=True)
        resolved_release = release_root.resolve(strict=True)
    except OSError:
        state["error"] = "current-release-target-missing"
        return state
    if (
        not stat.S_ISDIR(releases_stat.st_mode)
        or not stat.S_ISDIR(release_stat.st_mode)
        or resolved_current != resolved_release
    ):
        state["error"] = "current-release-target-invalid"
        return state
    manifest_path = release_root / "release-manifest.json"
    try:
        before_manifest_sha256, before_manifest_size = hash_regular_file(manifest_path)
        manifest_bytes = manifest_path.read_bytes()
        after_manifest_sha256, after_manifest_size = hash_regular_file(manifest_path)
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, RuntimeError):
        state["error"] = "release-manifest-invalid"
        return state
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    state["remote_manifest_sha256"] = manifest_sha256
    if (
        before_manifest_sha256 != manifest_sha256
        or after_manifest_sha256 != manifest_sha256
        or before_manifest_size != len(manifest_bytes)
        or after_manifest_size != len(manifest_bytes)
    ):
        state["error"] = "release-manifest-changed-during-audit"
        return state
    if not isinstance(manifest, dict) or manifest.get("format") != RELEASE_MANIFEST_FORMAT:
        state["error"] = "release-manifest-format-invalid"
        return state
    source_sha = manifest.get("source_sha")
    state["manifest_source_sha"] = source_sha if isinstance(source_sha, str) else None
    raw_files = manifest.get("files")
    if not isinstance(raw_files, list):
        state["error"] = "release-manifest-files-invalid"
        return state
    expected_files = {{}}
    ordered_paths = []
    for item in raw_files:
        if not isinstance(item, dict) or set(item) != {{"path", "size_bytes", "sha256"}}:
            state["error"] = "release-manifest-entry-invalid"
            return state
        relative_path = item.get("path")
        size_bytes = item.get("size_bytes")
        file_sha256 = item.get("sha256")
        if (
            not valid_manifest_path(relative_path)
            or isinstance(size_bytes, bool)
            or not isinstance(size_bytes, int)
            or size_bytes < 0
            or not isinstance(file_sha256, str)
            or SHA256_PATTERN.fullmatch(file_sha256) is None
            or relative_path in expected_files
        ):
            state["error"] = "release-manifest-entry-invalid"
            return state
        ordered_paths.append(relative_path)
        expected_files[relative_path] = {{
            "size_bytes": size_bytes,
            "sha256": file_sha256,
        }}
    state["manifest_file_count"] = len(expected_files)
    if ordered_paths != sorted(ordered_paths, key=lambda path: path.encode("utf-8")):
        state["error"] = "release-manifest-order-invalid"
        return state
    static_paths = [
        path for path in ordered_paths if path.startswith("_next/static/")
    ]
    selected_html_path = "documents.html"
    if selected_html_path not in expected_files:
        state["error"] = "release-manifest-html-missing"
        return state
    if not static_paths:
        state["error"] = "release-manifest-static-missing"
        return state
    selected_static_path = static_paths[0]
    state["selected_html_path"] = selected_html_path
    state["selected_html_sha256"] = expected_files[selected_html_path]["sha256"]
    state["selected_static_path"] = selected_static_path
    state["selected_static_sha256"] = expected_files[selected_static_path]["sha256"]
    if source_sha != release_sha:
        state["error"] = "release-manifest-source-sha-mismatch"
        return state
    try:
        actual_files, invalid_count = collect_release_files(release_root)
    except RuntimeError as exc:
        state["error"] = str(exc)
        return state
    mismatch_count = invalid_count + len(set(expected_files) ^ set(actual_files))
    for relative_path in set(expected_files) & set(actual_files):
        if expected_files[relative_path] != actual_files[relative_path]:
            mismatch_count += 1
    state["manifest_mismatch_count"] = mismatch_count
    if mismatch_count:
        state["error"] = "release-file-mismatch"
        return state
    state["ok"] = True
    state["error"] = None
    return state


def url_origin(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.username is not None or parsed.password is not None or not parsed.hostname:
        return None
    try:
        port = parsed.port
    except ValueError:
        return None
    if port is None:
        port = 443 if parsed.scheme.lower() == "https" else 80
    return parsed.scheme.lower(), parsed.hostname.lower(), port


def normalized_cache_control(headers):
    values = headers.get_all("Cache-Control") or []
    directives = []
    for value in values:
        for part in value.split(","):
            normalized = part.strip().lower()
            if normalized:
                directives.append(normalized)
    return ", ".join(directives)


def http_json(url, headers=None):
    try:
        request = urllib.request.Request(url, headers=headers or {{}})
        with HTTP_OPENER.open(request, timeout=20) as response:
            body = response.read().decode("utf-8")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {{"raw": body[:500]}}
        return {{"ok": True, "payload": payload}}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {{"ok": False, "error": str(exc)}}


def knowledge_base_catalog_status():
    response = http_json(
        "http://127.0.0.1:18080/knowledge-base/catalog",
        headers=AUDIT_HEADERS,
    )
    if response.get("ok") is not True:
        return response
    payload = response.get("payload")
    if not isinstance(payload, dict):
        return {{"ok": False, "error": "knowledge-base-catalog-non-object"}}
    search_backend = payload.get("search_backend")
    summary = payload.get("summary")
    boundaries = payload.get("boundaries")
    if not isinstance(search_backend, dict):
        return {{"ok": False, "error": "knowledge-base-catalog-search-backend-missing"}}
    if not isinstance(summary, dict):
        return {{"ok": False, "error": "knowledge-base-catalog-summary-missing"}}
    if not isinstance(boundaries, dict):
        return {{"ok": False, "error": "knowledge-base-catalog-boundaries-missing"}}
    if payload.get("contract_version") != "knowledge-base-catalog-v1":
        return {{"ok": False, "error": "knowledge-base-catalog-contract-version-mismatch"}}
    expected_false = (
        "production_write",
        "provider_call",
        "database_write",
        "object_storage_write",
        "query_history_write",
    )
    if any(boundaries.get(key) is not False for key in expected_false):
        return {{"ok": False, "error": "knowledge-base-catalog-boundaries-unsafe"}}
    matching = summary.get("current_search_embedding_count")
    if isinstance(matching, bool) or not isinstance(matching, int):
        return {{"ok": False, "error": "knowledge-base-catalog-matching-count-invalid"}}
    raw_details = search_backend.get("details")
    details = raw_details if isinstance(raw_details, dict) else {{}}
    safe_details = {{
        key: details.get(key)
        for key in (
            "embedding_provider",
            "embedding_model",
            "provider_version",
            "embedding_dimension",
        )
        if key in details
    }}
    safe_details["matching_embedding_count"] = matching
    return {{
        "ok": True,
        "payload": {{
            "contract_version": payload.get("contract_version"),
            "backend": search_backend.get("backend"),
            "ready": search_backend.get("ready"),
            "details": safe_details,
            "boundaries": {{key: boundaries.get(key) for key in expected_false}},
        }},
    }}


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
        with HTTP_OPENER.open(request, timeout=20) as response:
            body = response.read()
            status_code = response.getcode()
            content_type = response.headers.get("content-type")
            cache_control = normalized_cache_control(response.headers)
            final_url = response.geturl()
        same_origin = url_origin(url) == url_origin(final_url)
        expected_utf8_text = {{
            text: text.encode("utf-8") in body for text in expected_texts
        }}
        return {{
            "ok": (
                status_code == 200
                and same_origin
                and all(expected_utf8_text.values())
            ),
            "status_code": status_code,
            "content_type": content_type,
            "content_length": len(body),
            "body_sha256": hashlib.sha256(body).hexdigest(),
            "cache_control": cache_control,
            "final_url": final_url,
            "same_origin": same_origin,
            "expected_utf8_text": expected_utf8_text,
        }}
    except urllib.error.HTTPError as exc:
        location = exc.headers.get("Location") if exc.headers is not None else None
        final_url = urllib.parse.urljoin(url, location) if location else exc.geturl()
        return {{
            "ok": False,
            "status_code": exc.code,
            "error": str(exc),
            "final_url": final_url,
            "same_origin": url_origin(url) == url_origin(final_url),
        }}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {{
            "ok": False,
            "error": str(exc),
            "final_url": None,
            "same_origin": False,
        }}


def next_static_asset_status(active_release):
    if active_release.get("ok") is not True:
        return {{"ok": False, "error": "active-release-invalid"}}
    relative = active_release.get("selected_static_path")
    expected_sha256 = active_release.get("selected_static_sha256")
    if (
        not isinstance(relative, str)
        or not relative.startswith("_next/static/")
        or not isinstance(expected_sha256, str)
    ):
        return {{"ok": False, "error": "next-static-manifest-entry-missing"}}
    url_path = "/" + urllib.parse.quote(relative, safe="/-._~")
    status = http_status(BASE_URL + url_path)
    status["path"] = url_path
    status["expected_sha256"] = expected_sha256
    return status


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


active_release = release_state()
audit_log_before = audit_log_event_snapshot()
local_backend = {{
    "health": http_json("http://127.0.0.1:18080/health"),
    "search_backend": knowledge_base_catalog_status(),
}}
public_frontdoor = {{
    "health": http_status(BASE_URL + "/api/v1/health"),
    "documents": http_status(
        BASE_URL + "/documents",
        ["登录工作台", "AI审计一体化协作平台"],
        headers=AUDIT_HEADERS,
    ),
    "manifest": http_status(BASE_URL + "/release-manifest.json"),
    "next_static": next_static_asset_status(active_release),
}}
audit_log_after = audit_log_event_snapshot()

report = {{
    "collected_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "remote_app_dir": APP_DIR,
    "remote_web_dir": WEB_DIR,
    "remote_backup_root": BACKUP_ROOT,
    "deploy_sha": read_file(str(Path(APP_DIR) / ".deploy-sha")),
    "release_state": active_release,
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
    "local_backend": local_backend,
    "public_frontdoor": public_frontdoor,
    "side_effect_observation": {{
        "audit_log_before": audit_log_before,
        "audit_log_after": audit_log_after,
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
    expected_sha_valid = _valid_hex_digest(expected_deploy_sha, length=40)
    if expected_deploy_sha is None:
        issues.append("expected-deploy-sha-required")
    elif not expected_sha_valid:
        issues.append("expected-deploy-sha-invalid")
    elif deploy_sha != expected_deploy_sha:
        issues.append("deploy-sha-mismatch")
    release = _nested_dict(remote_report, "release_state")
    current_release_target = _string_or_none(release.get("current_release_target"))
    release_sha = _string_or_none(release.get("release_sha"))
    manifest_source_sha = _string_or_none(release.get("manifest_source_sha"))
    remote_manifest_sha256 = _valid_digest_or_none(
        release.get("remote_manifest_sha256"),
        length=64,
    )
    manifest_file_count = _nonnegative_int_or_none(release.get("manifest_file_count"))
    manifest_mismatch_count = _nonnegative_int_or_none(
        release.get("manifest_mismatch_count")
    )
    selected_html_path = _string_or_none(release.get("selected_html_path"))
    selected_html_sha256 = _valid_digest_or_none(
        release.get("selected_html_sha256"),
        length=64,
    )
    selected_static_path = _string_or_none(release.get("selected_static_path"))
    selected_static_sha256 = _valid_digest_or_none(
        release.get("selected_static_sha256"),
        length=64,
    )
    release_integrity_valid = (
        release.get("ok") is True
        and manifest_file_count is not None
        and manifest_file_count > 0
        and manifest_mismatch_count == 0
        and remote_manifest_sha256 is not None
        and selected_html_path == "documents.html"
        and selected_html_sha256 is not None
        and selected_static_path is not None
        and selected_static_path.startswith("_next/static/")
        and selected_static_sha256 is not None
    )
    if not release_integrity_valid:
        issues.append("remote-release-integrity-failed")
    expected_release_target = (
        f"releases/{expected_deploy_sha}" if expected_sha_valid else None
    )
    if (
        expected_release_target is None
        or current_release_target != expected_release_target
        or release_sha != expected_deploy_sha
    ):
        issues.append("current-release-target-mismatch")
    if not expected_sha_valid or manifest_source_sha != expected_deploy_sha:
        issues.append("remote-manifest-source-sha-mismatch")
    frontdoor = _nested_dict(remote_report, "public_frontdoor")
    public_manifest = _nested_dict(frontdoor, "manifest")
    public_static = _nested_dict(frontdoor, "next_static")
    documents_frontdoor = _nested_dict(frontdoor, "documents")
    public_manifest_sha256 = _valid_digest_or_none(
        public_manifest.get("body_sha256"),
        length=64,
    )
    public_static_sha256 = _valid_digest_or_none(
        public_static.get("body_sha256"),
        length=64,
    )
    public_html_sha256 = _valid_digest_or_none(
        documents_frontdoor.get("body_sha256"),
        length=64,
    )
    manifest_frontdoor_ready = (
        public_manifest.get("ok") is True
        and public_manifest.get("status_code") == 200
        and public_manifest.get("same_origin") is True
    )
    if not manifest_frontdoor_ready:
        issues.append("public-manifest-not-ready")
    elif (
        remote_manifest_sha256 is None
        or public_manifest_sha256 != remote_manifest_sha256
    ):
        issues.append("public-manifest-sha-mismatch")
    if (
        _audit_frontdoor_healthy(remote_report)
        and selected_html_sha256 is not None
        and public_html_sha256 != selected_html_sha256
    ):
        issues.append("public-html-sha-mismatch")
    if (
        _audit_next_static_healthy(remote_report)
        and selected_static_sha256 is not None
        and public_static_sha256 != selected_static_sha256
    ):
        issues.append("public-static-sha-mismatch")
    html_cache_control = _string_or_none(documents_frontdoor.get("cache_control"))
    static_cache_control = _string_or_none(public_static.get("cache_control"))
    html_cache_valid = _html_cache_control_valid(html_cache_control)
    static_cache_valid = _static_cache_control_valid(static_cache_control)
    if not html_cache_valid:
        issues.append("html-cache-control-invalid")
    if not static_cache_valid:
        issues.append("static-cache-control-invalid")
    for name in ("medical_audit_app", "medical_audit_pg"):
        health = _container_health(remote_report, name)
        if health != "healthy":
            issues.append(f"{name}-not-healthy")
    nginx_config_test_passed = _nginx_test_passed(remote_report)
    audit_frontdoor_healthy = _audit_frontdoor_healthy(remote_report)
    if not audit_frontdoor_healthy:
        issues.append("audit-frontdoor-not-ready")
    if not nginx_config_test_passed:
        issues.append("nginx-config-test-failed")
    if not _audit_mount_valid(remote_report):
        issues.append("audit-static-bind-mount-missing")
    if not _audit_next_static_healthy(remote_report):
        issues.append("audit-next-static-not-ready")
    if not _search_backend_ready(remote_report, matching_embedding_floor):
        issues.append("search-backend-not-ready")
    audit_log_event_delta = _audit_log_event_delta(remote_report)
    audit_log_snapshot_unchanged = _audit_log_snapshot_unchanged(remote_report)
    audit_log_auditor_event_delta = _audit_log_auditor_event_delta(remote_report)
    audit_log_auditor_events_absent = _audit_log_auditor_events_absent(remote_report)
    audit_log_auditor_write_attributed = _audit_log_auditor_write_attributed(remote_report)
    search_backend_boundaries_safe = _search_backend_boundaries_safe(remote_report)
    if audit_log_event_delta is None:
        issues.append("audit-log-delta-unavailable")
    elif audit_log_event_delta != 0:
        issues.append("audit-log-delta-nonzero")
    if audit_log_snapshot_unchanged is None:
        issues.append("audit-log-snapshot-unavailable")
    elif not audit_log_snapshot_unchanged:
        issues.append("audit-log-snapshot-mutated")
    if audit_log_auditor_events_absent is None:
        issues.append("audit-log-auditor-delta-unavailable")
    elif not audit_log_auditor_events_absent:
        issues.append("audit-log-auditor-events-detected")
    if not search_backend_boundaries_safe:
        issues.append("search-backend-side-effect-boundary-unsafe")
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
    provider_call_status = (
        "not_called" if _search_backend_provider_call_disabled(remote_report) else "unknown"
    )
    audit_log_observation_safe = (
        audit_log_event_delta == 0
        and audit_log_snapshot_unchanged is True
        and audit_log_auditor_events_absent is True
    )
    if audit_log_observation_safe and search_backend_boundaries_safe:
        database_write: bool | str = False
        production_side_effect = "none"
    elif audit_log_auditor_write_attributed is True and search_backend_boundaries_safe:
        database_write = "audit-log-only"
        production_side_effect = "audit-log-only"
    else:
        database_write = "unknown"
        production_side_effect = "unknown"
    evidence_grade = (
        "L3-production-read-only"
        if audit_log_observation_safe and search_backend_boundaries_safe
        else "L1-public-or-runtime"
    )
    release_commit_state = (
        "committed_by_marker"
        if (
            expected_sha_valid
            and deploy_sha == expected_deploy_sha
            and current_release_target == expected_release_target
            and release_sha == expected_deploy_sha
            and manifest_source_sha == expected_deploy_sha
        )
        else "unproven"
    )
    nginx_release_route_ready = (
        nginx_config_test_passed
        and _audit_mount_valid(remote_report)
        and release_integrity_valid
        and manifest_frontdoor_ready
        and public_manifest_sha256 == remote_manifest_sha256
        and _audit_next_static_healthy(remote_report)
        and public_static_sha256 == selected_static_sha256
        and _audit_frontdoor_healthy(remote_report)
        and public_html_sha256 == selected_html_sha256
        and html_cache_valid
        and static_cache_valid
    )
    return {
        "status": "pass" if not issues else "fail",
        "evidence_grade": evidence_grade,
        "production_side_effect": production_side_effect,
        "database_write": database_write,
        "provider_call_status": provider_call_status,
        "http_methods": ["GET"],
        "issues": issues,
        "warnings": warnings,
        "expected_deploy_sha": expected_deploy_sha,
        "required_backup_stamp": required_backup_stamp,
        "expected_dlp_review_provider": expected_dlp_review_provider,
        "minimum_matching_embeddings": matching_embedding_floor,
        "expected_matching_embeddings": matching_embedding_floor,
        "summary": {
            "deploy_sha": deploy_sha,
            "current_release_target": current_release_target,
            "manifest_source_sha": manifest_source_sha,
            "remote_manifest_sha256": remote_manifest_sha256,
            "public_manifest_sha256": public_manifest_sha256,
            "manifest_file_count": manifest_file_count,
            "manifest_mismatch_count": manifest_mismatch_count,
            "manifest_html_sha256": selected_html_sha256,
            "public_html_sha256": public_html_sha256,
            "manifest_static_sha256": selected_static_sha256,
            "public_static_sha256": public_static_sha256,
            "html_cache_control": html_cache_control,
            "static_cache_control": static_cache_control,
            "release_commit_state": release_commit_state,
            "nginx_release_route_ready": nginx_release_route_ready,
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
            "audit_next_static_healthy": _audit_next_static_healthy(remote_report),
            "audit_mount_present": _audit_mount_valid(remote_report),
            "search_backend_ready": _search_backend_ready(
                remote_report,
                matching_embedding_floor,
            ),
            "matching_embedding_count": _matching_embedding_count(remote_report),
            "audit_log_event_delta": audit_log_event_delta,
            "audit_log_snapshot_unchanged": audit_log_snapshot_unchanged,
            "audit_log_auditor_event_delta": audit_log_auditor_event_delta,
            "audit_log_auditor_events_absent": audit_log_auditor_events_absent,
            "audit_log_auditor_write_attributed": audit_log_auditor_write_attributed,
            "audit_log_count_transaction_read_only": _audit_log_count_transaction_read_only(
                remote_report
            ),
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


def _valid_hex_digest(value: object, *, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _valid_digest_or_none(value: object, *, length: int) -> str | None:
    if not isinstance(value, str) or not _valid_hex_digest(value, length=length):
        return None
    return value


def _nonnegative_int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _cache_control_directives(value: str | None) -> dict[str, set[str | None]]:
    directives: dict[str, set[str | None]] = {}
    if value is None:
        return directives
    for part in value.split(","):
        name, separator, raw_value = part.strip().lower().partition("=")
        if not name:
            continue
        directive_value = raw_value.strip() if separator else None
        directives.setdefault(name, set()).add(directive_value)
    return directives


def _html_cache_control_valid(value: str | None) -> bool:
    directives = _cache_control_directives(value)
    return not {"no-store", "no-cache"}.isdisjoint(directives)


def _static_cache_control_valid(value: str | None) -> bool:
    directives = _cache_control_directives(value)
    return (
        "immutable" in directives
        and directives.get("max-age") == {"31536000"}
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
        and documents.get("same_origin") is True
    )


def _audit_next_static_healthy(remote_report: dict[str, Any]) -> bool:
    frontdoor = _nested_dict(remote_report, "public_frontdoor")
    next_static = _nested_dict(frontdoor, "next_static")
    return (
        next_static.get("ok") is True
        and next_static.get("status_code") == 200
        and next_static.get("same_origin") is True
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


def _search_backend_boundaries(remote_report: dict[str, Any]) -> dict[str, Any]:
    search_backend = _nested_dict(remote_report, "local_backend", "search_backend")
    payload = search_backend.get("payload")
    if not isinstance(payload, dict):
        return {}
    boundaries = payload.get("boundaries")
    return boundaries if isinstance(boundaries, dict) else {}


def _search_backend_boundaries_safe(remote_report: dict[str, Any]) -> bool:
    search_backend = _nested_dict(remote_report, "local_backend", "search_backend")
    payload = search_backend.get("payload")
    if not isinstance(payload, dict):
        return False
    if payload.get("contract_version") != "knowledge-base-catalog-v1":
        return False
    boundaries = _search_backend_boundaries(remote_report)
    return all(
        boundaries.get(key) is False
        for key in (
            "production_write",
            "provider_call",
            "database_write",
            "object_storage_write",
            "query_history_write",
        )
    )


def _search_backend_provider_call_disabled(remote_report: dict[str, Any]) -> bool:
    return _search_backend_boundaries(remote_report).get("provider_call") is False


def _audit_log_event_delta(remote_report: dict[str, Any]) -> int | None:
    observation = _nested_dict(remote_report, "side_effect_observation")
    before = _dict_or_empty(observation.get("audit_log_before"))
    after = _dict_or_empty(observation.get("audit_log_after"))
    if before.get("ok") is not True or after.get("ok") is not True:
        return None
    if before.get("transaction_read_only") != "on":
        return None
    if after.get("transaction_read_only") != "on":
        return None
    before_count = before.get("count")
    after_count = after.get("count")
    if isinstance(before_count, bool) or not isinstance(before_count, int):
        return None
    if isinstance(after_count, bool) or not isinstance(after_count, int):
        return None
    return after_count - before_count


def _audit_log_snapshot_unchanged(remote_report: dict[str, Any]) -> bool | None:
    observation = _nested_dict(remote_report, "side_effect_observation")
    before = _dict_or_empty(observation.get("audit_log_before"))
    after = _dict_or_empty(observation.get("audit_log_after"))
    before_latest = before.get("latest_created_at")
    after_latest = after.get("latest_created_at")
    before_fingerprint = before.get("event_id_fingerprint")
    after_fingerprint = after.get("event_id_fingerprint")
    if not all(
        isinstance(value, str) and bool(value)
        for value in (
            before_latest,
            after_latest,
            before_fingerprint,
            after_fingerprint,
        )
    ):
        return None
    return before_latest == after_latest and before_fingerprint == after_fingerprint


def _audit_log_auditor_event_delta(remote_report: dict[str, Any]) -> int | None:
    observation = _nested_dict(remote_report, "side_effect_observation")
    before = _dict_or_empty(observation.get("audit_log_before"))
    after = _dict_or_empty(observation.get("audit_log_after"))
    before_identifier = before.get("auditor_user_identifier")
    after_identifier = after.get("auditor_user_identifier")
    if (
        not isinstance(before_identifier, str)
        or not before_identifier
        or before_identifier != after_identifier
    ):
        return None
    before_count = before.get("auditor_event_count")
    after_count = after.get("auditor_event_count")
    if isinstance(before_count, bool) or not isinstance(before_count, int):
        return None
    if isinstance(after_count, bool) or not isinstance(after_count, int):
        return None
    return after_count - before_count


def _audit_log_auditor_events_absent(remote_report: dict[str, Any]) -> bool | None:
    observation = _nested_dict(remote_report, "side_effect_observation")
    before = _dict_or_empty(observation.get("audit_log_before"))
    after = _dict_or_empty(observation.get("audit_log_after"))
    if _audit_log_auditor_event_delta(remote_report) is None:
        return None
    before_count = before.get("auditor_event_count")
    after_count = after.get("auditor_event_count")
    if isinstance(before_count, bool) or not isinstance(before_count, int):
        return None
    if isinstance(after_count, bool) or not isinstance(after_count, int):
        return None
    return before_count == 0 and after_count == 0


def _audit_log_auditor_write_attributed(remote_report: dict[str, Any]) -> bool | None:
    observation = _nested_dict(remote_report, "side_effect_observation")
    before = _dict_or_empty(observation.get("audit_log_before"))
    after = _dict_or_empty(observation.get("audit_log_after"))
    if _audit_log_auditor_event_delta(remote_report) is None:
        return None
    before_count = before.get("auditor_event_count")
    after_count = after.get("auditor_event_count")
    if isinstance(before_count, bool) or not isinstance(before_count, int):
        return None
    if isinstance(after_count, bool) or not isinstance(after_count, int):
        return None
    return before_count == 0 and after_count > 0


def _audit_log_count_transaction_read_only(remote_report: dict[str, Any]) -> bool:
    observation = _nested_dict(remote_report, "side_effect_observation")
    before = _dict_or_empty(observation.get("audit_log_before"))
    after = _dict_or_empty(observation.get("audit_log_after"))
    return (
        before.get("ok") is True
        and after.get("ok") is True
        and before.get("transaction_read_only") == "on"
        and after.get("transaction_read_only") == "on"
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
            f"- `evidence_grade`: `{report.get('evidence_grade')}`",
            f"- `production_side_effect`: `{report.get('production_side_effect')}`",
            f"- `database_write`: `{report.get('database_write')}`",
            f"- `provider_call_status`: `{report.get('provider_call_status')}`",
            f"- `http_methods`: `{report.get('http_methods')}`",
            f"- `deploy_sha`: `{summary.get('deploy_sha')}`",
            f"- `current_release_target`: `{summary.get('current_release_target')}`",
            f"- `manifest_source_sha`: `{summary.get('manifest_source_sha')}`",
            f"- `remote_manifest_sha256`: `{summary.get('remote_manifest_sha256')}`",
            f"- `public_manifest_sha256`: `{summary.get('public_manifest_sha256')}`",
            f"- `manifest_file_count`: `{summary.get('manifest_file_count')}`",
            f"- `manifest_mismatch_count`: `{summary.get('manifest_mismatch_count')}`",
            f"- `manifest_html_sha256`: `{summary.get('manifest_html_sha256')}`",
            f"- `public_html_sha256`: `{summary.get('public_html_sha256')}`",
            f"- `manifest_static_sha256`: `{summary.get('manifest_static_sha256')}`",
            f"- `public_static_sha256`: `{summary.get('public_static_sha256')}`",
            f"- `html_cache_control`: `{summary.get('html_cache_control')}`",
            f"- `static_cache_control`: `{summary.get('static_cache_control')}`",
            f"- `release_commit_state`: `{summary.get('release_commit_state')}`",
            f"- `nginx_release_route_ready`: `{summary.get('nginx_release_route_ready')}`",
            f"- `app_health`: `{summary.get('app_health')}`",
            f"- `postgres_health`: `{summary.get('postgres_health')}`",
            f"- `clamav_health`: `{summary.get('clamav_health')}`",
            f"- `clamav_compose_service_present`: `{clamav_service_present}`",
            f"- `virus_scan_provider`: `{summary.get('virus_scan_provider')}`",
            f"- `dlp_review_provider`: `{summary.get('dlp_review_provider')}`",
            f"- `nginx_config_test`: `{summary.get('nginx_config_test')}`",
            f"- `audit_frontdoor_healthy`: `{summary.get('audit_frontdoor_healthy')}`",
            f"- `audit_next_static_healthy`: `{summary.get('audit_next_static_healthy')}`",
            f"- `audit_mount_present`: `{summary.get('audit_mount_present')}`",
            f"- `search_backend_ready`: `{summary.get('search_backend_ready')}`",
            f"- `matching_embedding_count`: `{summary.get('matching_embedding_count')}`",
            f"- `audit_log_event_delta`: `{summary.get('audit_log_event_delta')}`",
            f"- `audit_log_snapshot_unchanged`: "
            f"`{summary.get('audit_log_snapshot_unchanged')}`",
            f"- `audit_log_auditor_event_delta`: "
            f"`{summary.get('audit_log_auditor_event_delta')}`",
            f"- `audit_log_auditor_events_absent`: "
            f"`{summary.get('audit_log_auditor_events_absent')}`",
            f"- `audit_log_auditor_write_attributed`: "
            f"`{summary.get('audit_log_auditor_write_attributed')}`",
            f"- `audit_log_count_transaction_read_only`: "
            f"`{summary.get('audit_log_count_transaction_read_only')}`",
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
