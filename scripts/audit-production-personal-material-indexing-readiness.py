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
DEFAULT_REMOTE_APP_DIR = "/opt/medical-audit/app"
DEFAULT_REMOTE_UPLOAD_ROOT = "/opt/medical-audit/document-uploads"
DEFAULT_JSON_OUTPUT = "tmp/outputs/production-personal-material-indexing-readiness-latest.json"
DEFAULT_MARKDOWN_OUTPUT = "tmp/outputs/production-personal-material-indexing-readiness-latest.md"


class ReadinessAuditError(RuntimeError):
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
            remote_upload_root=str(args.remote_upload_root),
            sample_limit=max(1, int(args.sample_limit)),
        )
        report = _build_report(
            remote_report=remote_report,
            expected_deploy_sha=_optional_text(args.expected_deploy_sha),
            require_indexing_enabled=bool(args.require_indexing_enabled),
            require_ready_upload=bool(args.require_ready_upload),
            require_local_file_available=bool(args.require_local_file_available),
            require_no_active_personal_materials=bool(args.require_no_active_personal_materials),
        )
    except ReadinessAuditError as exc:
        print(f"readiness audit failed: {exc}", file=sys.stderr)
        return 2
    _write_json(json_output, report)
    _write_markdown(markdown_output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a read-only production readiness audit for personal-material indexing. "
            "The audit uses SSH and read-only SQL only; it does not call mutating API endpoints."
        )
    )
    parser.add_argument(
        "--ssh-key",
        default=os.environ.get("MEDICAL_AUDIT_DEPLOY_SSH_KEY", "ai_video.pem"),
        help="Path to the SSH key. Defaults to ./ai_video.pem or env override.",
    )
    parser.add_argument("--ssh-user", default=DEFAULT_USER)
    parser.add_argument("--ssh-host", default=DEFAULT_HOST)
    parser.add_argument("--remote-app-dir", default=DEFAULT_REMOTE_APP_DIR)
    parser.add_argument("--remote-upload-root", default=DEFAULT_REMOTE_UPLOAD_ROOT)
    parser.add_argument("--expected-deploy-sha", default="")
    parser.add_argument("--sample-limit", type=int, default=5)
    parser.add_argument("--require-indexing-enabled", action="store_true", default=True)
    parser.add_argument(
        "--allow-indexing-disabled",
        dest="require_indexing_enabled",
        action="store_false",
    )
    parser.add_argument("--require-ready-upload", action="store_true", default=True)
    parser.add_argument(
        "--allow-no-ready-upload",
        dest="require_ready_upload",
        action="store_false",
    )
    parser.add_argument("--require-local-file-available", action="store_true", default=True)
    parser.add_argument(
        "--allow-cos-only-ready-upload",
        dest="require_local_file_available",
        action="store_false",
    )
    parser.add_argument("--require-no-active-personal-materials", action="store_true", default=True)
    parser.add_argument(
        "--allow-active-personal-materials",
        dest="require_no_active_personal_materials",
        action="store_false",
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


def _collect_remote_report(
    *,
    ssh_key: Path,
    ssh_user: str,
    ssh_host: str,
    remote_app_dir: str,
    remote_upload_root: str,
    sample_limit: int,
) -> dict[str, Any]:
    if not ssh_key.exists():
        raise ReadinessAuditError(f"SSH key not found: {ssh_key}")
    remote_code = _remote_audit_code(
        remote_app_dir=remote_app_dir,
        remote_upload_root=remote_upload_root,
        sample_limit=sample_limit,
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
        f"{ssh_user}@{ssh_host} python3 - <personal-material-indexing-readiness>",
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
        raise ReadinessAuditError(completed.stderr.strip() or "remote readiness command failed")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ReadinessAuditError("remote readiness command returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ReadinessAuditError("remote readiness command returned non-object JSON")
    return payload


def _build_report(
    *,
    remote_report: dict[str, Any],
    expected_deploy_sha: str | None,
    require_indexing_enabled: bool,
    require_ready_upload: bool,
    require_local_file_available: bool,
    require_no_active_personal_materials: bool,
) -> dict[str, Any]:
    indexing = _dict(remote_report.get("document_upload_indexing"), "document_upload_indexing")
    env = _dict(indexing.get("env"), "document_upload_indexing.env")
    db = _dict(indexing.get("db"), "document_upload_indexing.db")
    containers = _dict(remote_report.get("containers"), "containers")
    issues: list[str] = []
    warnings: list[str] = []

    deploy_sha = _text(remote_report.get("deploy_sha"))
    if expected_deploy_sha and deploy_sha != expected_deploy_sha:
        issues.append("deploy-sha-mismatch")
    if _container_health(containers, "medical_audit_app") != "healthy":
        issues.append("app-container-unhealthy")
    if _container_health(containers, "medical_audit_pg") != "healthy":
        issues.append("postgres-container-unhealthy")
    if indexing.get("env_ok") is False:
        issues.append("env-read-failed")
    if indexing.get("db_ok") is False:
        issues.append("db-read-failed")

    indexing_enabled = _truthy(
        _text(env.get("MEDICAL_AUDIT_DOCUMENT_UPLOAD_INDEXING_ENABLED"))
    )
    ready_not_indexed_uploads = _int(db.get("ready_not_indexed_uploads"))
    staged_uploads = _int(db.get("staged_uploads"))
    active_versions = _int(db.get("personal_material_active_versions"))
    active_chunks = _int(db.get("personal_material_active_chunks"))
    ready_local_available = _int(db.get("ready_not_indexed_local_file_available_count"))
    if require_indexing_enabled and not indexing_enabled:
        issues.append("document-upload-indexing-disabled")
    if require_ready_upload and ready_not_indexed_uploads < 1:
        issues.append("no-ready-upload-for-indexing")
    if (
        require_local_file_available
        and ready_not_indexed_uploads > 0
        and ready_local_available < 1
    ):
        issues.append("ready-upload-local-file-unavailable")
    if require_no_active_personal_materials and (active_versions > 0 or active_chunks > 0):
        warnings.append("active-personal-material-index-already-present")

    active_retrieval_activated = active_versions > 0 and active_chunks > 0
    summary = {
        "deploy_sha": deploy_sha,
        "indexing_enabled": indexing_enabled,
        "index_version_key": _text(
            env.get("MEDICAL_AUDIT_DOCUMENT_UPLOAD_INDEXING_INDEX_VERSION_KEY")
        ),
        "source_package_version_key": _text(
            env.get("MEDICAL_AUDIT_DOCUMENT_UPLOAD_INDEXING_SOURCE_PACKAGE_KEY")
        ),
        "total_uploads": _int(db.get("total_uploads")),
        "ready_not_indexed_uploads": ready_not_indexed_uploads,
        "ready_not_indexed_local_file_available_count": ready_local_available,
        "staged_uploads": staged_uploads,
        "personal_material_candidate_versions": _int(
            db.get("personal_material_candidate_versions")
        ),
        "personal_material_active_versions": active_versions,
        "personal_material_chunks": _int(db.get("personal_material_chunks")),
        "personal_material_active_chunks": active_chunks,
        "active_retrieval_activated": active_retrieval_activated,
    }
    status = "pass" if not issues else "blocked"
    return {
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "expected_deploy_sha": expected_deploy_sha,
        "summary": summary,
        "boundaries": {
            "production_read_only": True,
            "production_write": False,
            "api_write": False,
            "db_write": False,
            "audit_log_write_expected": False,
            "external_provider_call": False,
            "index_ingestion_triggered": False,
            "active_retrieval_activated": active_retrieval_activated,
            "evidence_grade": "L3-production-read-only",
        },
        "remote": remote_report,
    }


def _remote_audit_code(
    *,
    remote_app_dir: str,
    remote_upload_root: str,
    sample_limit: int,
) -> str:
    return f"""
import json
import shlex
import subprocess
from pathlib import Path

APP_DIR = {json.dumps(remote_app_dir, ensure_ascii=False)}
UPLOAD_ROOT = {json.dumps(remote_upload_root, ensure_ascii=False)}
SAMPLE_LIMIT = {sample_limit}


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
    return {{
        "available": bool(inspected.get("available")),
        "status": state.get("Status"),
        "running": bool(state.get("Running")),
        "health": (state.get("Health") or {{}}).get("Status"),
        "started_at": state.get("StartedAt"),
    }}


def app_env():
    keys = [
        "MEDICAL_AUDIT_DOCUMENT_UPLOAD_INDEXING_ENABLED",
        "MEDICAL_AUDIT_DOCUMENT_UPLOAD_INDEXING_INDEX_VERSION_KEY",
        "MEDICAL_AUDIT_DOCUMENT_UPLOAD_INDEXING_SOURCE_PACKAGE_KEY",
        "MEDICAL_AUDIT_DOCUMENT_UPLOAD_INDEXING_EMBEDDING_DIMENSION",
        "MEDICAL_AUDIT_DOCUMENT_STORAGE_PROVIDER",
        "MEDICAL_AUDIT_DOCUMENT_UPLOAD_VIRUS_SCANNER_PROVIDER",
        "MEDICAL_AUDIT_DOCUMENT_UPLOAD_DLP_REVIEWER_PROVIDER",
    ]
    code = (
        "import json, os; "
        "keys = " + repr(keys) + "; "
        "print(json.dumps({{key: os.environ.get(key, '') for key in keys}}, ensure_ascii=False))"
    )
    result = run(["docker", "exec", "medical_audit_app", "python", "-c", code])
    if result.returncode != 0:
        return {{"ok": False, "error": result.stderr.strip(), "values": {{}}}}
    return {{"ok": True, "values": json.loads(result.stdout)}}


def psql_json(sql):
    shell = 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -c ' + shlex.quote(sql)
    result = run(["docker", "exec", "medical_audit_pg", "sh", "-lc", shell])
    if result.returncode != 0:
        return {{"ok": False, "error": result.stderr.strip()}}
    text = result.stdout.strip() or "{{}}"
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return {{"ok": False, "error": f"invalid JSON from psql: {{exc}}", "stdout": text[:500]}}
    return {{"ok": True, "payload": payload}}


def indexing_db_state():
    sql = \"\"\"
WITH upload_base AS (
  SELECT
    r.upload_key,
    r.file_name,
    r.storage_path,
    r.created_by,
    COALESCE(r.metadata->>'index_status', 'not-indexed') AS index_status,
    COALESCE(r.metadata->'index_readiness'->>'status', '') AS readiness_status,
    so.provider AS storage_provider,
    so.object_key AS object_key,
    r.created_at
  FROM document_upload_records r
  LEFT JOIN LATERAL (
    SELECT provider, object_key
    FROM document_storage_objects so
    WHERE so.upload_key = r.upload_key
    ORDER BY so.created_at DESC
    LIMIT 1
  ) so ON true
),
ready_samples AS (
  SELECT *
  FROM upload_base
  WHERE readiness_status = 'ready' AND index_status = 'not-indexed'
  ORDER BY created_at DESC
  LIMIT %d
)
SELECT json_build_object(
  'total_uploads', (SELECT count(*) FROM document_upload_records),
  'ready_not_indexed_uploads', (
    SELECT count(*) FROM upload_base
    WHERE readiness_status = 'ready' AND index_status = 'not-indexed'
  ),
  'staged_uploads', (
    SELECT count(*) FROM upload_base
    WHERE index_status = 'staged-for-index'
  ),
  'personal_material_candidate_versions', (
    SELECT count(*) FROM index_versions
    WHERE status = 'candidate'
      AND COALESCE(metadata->>'source_collection', '') = 'personal-materials'
  ),
  'personal_material_active_versions', (
    SELECT count(*) FROM index_versions
    WHERE status = 'active'
      AND COALESCE(metadata->>'source_collection', '') = 'personal-materials'
  ),
  'personal_material_chunks', (
    SELECT count(*)
    FROM document_chunks c
    JOIN source_documents d ON d.id = c.source_document_id
    WHERE d.source_collection = 'personal-materials'
  ),
  'personal_material_active_chunks', (
    SELECT count(*)
    FROM document_chunks c
    JOIN source_documents d ON d.id = c.source_document_id
    JOIN source_package_versions spv ON spv.id = d.source_package_version_id
    JOIN index_versions iv ON iv.source_package_version_id = spv.id
    WHERE d.source_collection = 'personal-materials'
      AND iv.status = 'active'
  ),
  'ready_not_indexed_samples', COALESCE((
    SELECT json_agg(json_build_object(
      'upload_key', upload_key,
      'file_name', file_name,
      'storage_path', storage_path,
      'created_by', created_by,
      'storage_provider', storage_provider,
      'object_key', object_key
    ))
    FROM ready_samples
  ), '[]'::json)
)
\"\"\" % SAMPLE_LIMIT
    result = psql_json(sql)
    if not result.get("ok"):
        return result
    payload = result.get("payload") or {{}}
    samples = payload.get("ready_not_indexed_samples") or []
    local_available = 0
    enriched = []
    for sample in samples:
        sample = dict(sample)
        storage_path = str(sample.get("storage_path") or "")
        local_path = Path(UPLOAD_ROOT) / storage_path
        exists = bool(storage_path) and local_path.is_file()
        if exists:
            local_available += 1
        sample["local_file_exists"] = exists
        sample["local_path"] = str(local_path) if storage_path else ""
        enriched.append(sample)
    payload["ready_not_indexed_samples"] = enriched
    payload["ready_not_indexed_local_file_available_count"] = local_available
    return {{"ok": True, "payload": payload}}


env_result = app_env()
db_result = indexing_db_state()
deploy_sha_path = Path(APP_DIR) / ".deploy-sha"
deploy_sha = deploy_sha_path.read_text(encoding="utf-8").strip() if deploy_sha_path.exists() else ""
report = {{
    "deploy_sha": deploy_sha,
    "remote_app_dir": APP_DIR,
    "remote_upload_root": UPLOAD_ROOT,
    "containers": {{
        "medical_audit_app": container_state("medical_audit_app"),
        "medical_audit_pg": container_state("medical_audit_pg"),
    }},
    "document_upload_indexing": {{
        "env": env_result.get("values", {{}}),
        "env_ok": env_result.get("ok", False),
        "db": db_result.get("payload", {{}}),
        "db_ok": db_result.get("ok", False),
        "db_error": db_result.get("error"),
    }},
}}
print(json.dumps(report, ensure_ascii=False))
"""


def _dict(value: object, label: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    raise ReadinessAuditError(f"{label} is missing or not an object")


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip():
        return int(value)
    return 0


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _container_health(containers: dict[str, Any], name: str) -> str:
    item = containers.get(name)
    if not isinstance(item, dict):
        return ""
    return _text(item.get("health") or item.get("status"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = _dict(payload.get("summary"), "summary")
    lines = [
        "# Production Personal Material Indexing Readiness",
        "",
        f"- status: `{payload.get('status')}`",
        f"- issues: `{', '.join(payload.get('issues') or []) or 'none'}`",
        f"- warnings: `{', '.join(payload.get('warnings') or []) or 'none'}`",
        f"- deploy_sha: `{summary.get('deploy_sha')}`",
        f"- indexing_enabled: `{summary.get('indexing_enabled')}`",
        f"- ready_not_indexed_uploads: `{summary.get('ready_not_indexed_uploads')}`",
        "- ready_not_indexed_local_file_available_count: "
        f"`{summary.get('ready_not_indexed_local_file_available_count')}`",
        f"- staged_uploads: `{summary.get('staged_uploads')}`",
        "- personal_material_active_versions: "
        f"`{summary.get('personal_material_active_versions')}`",
        f"- personal_material_active_chunks: `{summary.get('personal_material_active_chunks')}`",
        "",
        "## Boundary",
        "",
        "- production_write: `false`",
        "- api_write: `false`",
        "- db_write: `false`",
        "- audit_log_write_expected: `false`",
        "- index_ingestion_triggered: `false`",
        "- active_retrieval_activated: `false` unless existing active rows are observed",
        "- evidence_grade: `L3-production-read-only`",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
