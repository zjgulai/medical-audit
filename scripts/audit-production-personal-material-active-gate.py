#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_HOST = "101.34.52.232"
DEFAULT_USER = "ubuntu"
DEFAULT_REMOTE_APP_DIR = "/opt/medical-audit/app"
DEFAULT_JSON_OUTPUT = "tmp/outputs/production-personal-material-active-gate-latest.json"
DEFAULT_MARKDOWN_OUTPUT = "tmp/outputs/production-personal-material-active-gate-latest.md"


class ActiveGateAuditError(RuntimeError):
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
            index_version_key=_optional_text(args.index_version_key),
        )
        report = _build_report(
            remote_report=remote_report,
            expected_deploy_sha=_optional_text(args.expected_deploy_sha),
            require_live_retrieval_activated=bool(args.require_live_retrieval_activated),
            require_runtime_activation_guard=bool(args.require_runtime_activation_guard),
        )
    except ActiveGateAuditError as exc:
        print(f"active gate audit failed: {exc}", file=sys.stderr)
        return 2
    _write_json(json_output, report)
    _write_markdown(markdown_output, report)
    print(json.dumps(_stdout_summary(report), ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a read-only production gate for activating personal-material index versions. "
            "The audit reads env/runtime/SQL state only; it never calls index-activate."
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
    parser.add_argument(
        "--index-version-key",
        default="",
        help=(
            "Target index_version_key. If omitted, the production "
            "MEDICAL_AUDIT_DOCUMENT_UPLOAD_INDEXING_INDEX_VERSION_KEY env is used."
        ),
    )
    parser.add_argument("--expected-deploy-sha", default="")
    parser.add_argument("--require-live-retrieval-activated", action="store_true", default=True)
    parser.add_argument(
        "--allow-live-retrieval-inactive",
        dest="require_live_retrieval_activated",
        action="store_false",
    )
    parser.add_argument("--require-runtime-activation-guard", action="store_true", default=True)
    parser.add_argument(
        "--allow-missing-runtime-activation-guard",
        dest="require_runtime_activation_guard",
        action="store_false",
    )
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args()


def _collect_remote_report(
    *,
    ssh_key: Path,
    ssh_user: str,
    ssh_host: str,
    remote_app_dir: str,
    index_version_key: str | None,
) -> dict[str, Any]:
    if not ssh_key.exists():
        raise ActiveGateAuditError(f"SSH key not found: {ssh_key}")
    remote_code = _remote_audit_code(
        remote_app_dir=remote_app_dir,
        index_version_key=index_version_key,
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
        f"{ssh_user}@{ssh_host} python3 - <personal-material-active-gate>",
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
        raise ActiveGateAuditError(completed.stderr.strip() or "remote active gate command failed")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ActiveGateAuditError("remote active gate command returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ActiveGateAuditError("remote active gate command returned non-object JSON")
    return payload


def _build_report(
    *,
    remote_report: dict[str, Any],
    expected_deploy_sha: str | None,
    require_live_retrieval_activated: bool,
    require_runtime_activation_guard: bool,
) -> dict[str, Any]:
    containers = _dict(remote_report.get("containers"), "containers")
    env = _dict(remote_report.get("document_upload_indexing_env"), "document_upload_indexing_env")
    runtime = _dict(remote_report.get("runtime_checks"), "runtime_checks")
    db_state = _dict(remote_report.get("db_state"), "db_state")
    target = db_state.get("target_version")
    target_version = target if isinstance(target, dict) else None
    issues: list[str] = []
    warnings: list[str] = []

    deploy_sha = _text(remote_report.get("deploy_sha"))
    if expected_deploy_sha and deploy_sha != expected_deploy_sha:
        issues.append("deploy-sha-mismatch")
    if _container_health(containers, "medical_audit_app") != "healthy":
        issues.append("app-container-unhealthy")
    if _container_health(containers, "medical_audit_pg") != "healthy":
        issues.append("postgres-container-unhealthy")
    if remote_report.get("env_ok") is False:
        issues.append("env-read-failed")
    if remote_report.get("runtime_ok") is False:
        issues.append("runtime-check-failed")
    if remote_report.get("db_ok") is False:
        issues.append("db-read-failed")

    target_key = _text(db_state.get("target_index_version_key"))
    if not target_key:
        issues.append("target-index-version-key-missing")
    if target_key and target_version is None:
        issues.append("target-index-version-not-found")

    live_retrieval_activated = False
    source_collection = ""
    target_status = ""
    if target_version is not None:
        metadata = _dict_or_empty(target_version.get("metadata"))
        source_collection = _text(metadata.get("source_collection"))
        live_retrieval_activated = metadata.get("live_retrieval_activated") is True
        target_status = _text(target_version.get("status"))
        if target_status != "candidate":
            issues.append("target-index-version-not-candidate")
        if source_collection != "personal-materials":
            issues.append("target-index-version-not-personal-materials")
        if require_live_retrieval_activated and not live_retrieval_activated:
            issues.append("live-retrieval-not-activated")

    guard_blocks = runtime.get("activation_guard_blocks_inactive_live_retrieval") is True
    if require_runtime_activation_guard and not guard_blocks:
        issues.append("runtime-activation-guard-not-enforced")
    explicit_query_allowed_roles = _str_list(
        runtime.get("personal_material_explicit_query_allowed_roles")
    )
    if explicit_query_allowed_roles:
        warnings.append("personal-material-explicit-query-access-present")
    default_query_allowed_roles = _str_list(
        runtime.get("personal_material_default_query_allowed_roles")
    )
    if runtime.get("personal_material_default_query_excludes_personal_materials") is not True:
        issues.append("personal-material-default-query-not-isolated")

    stats = _dict_or_empty(db_state.get("personal_material_stats"))
    active_versions = _int(stats.get("active_versions"))
    active_chunks = _int(stats.get("active_chunks"))
    if active_versions > 0 or active_chunks > 0:
        warnings.append("active-personal-material-index-already-present")

    status = "pass" if not issues else "blocked"
    safe_to_activate = (
        status == "pass"
        and target_version is not None
        and target_status == "candidate"
        and source_collection == "personal-materials"
        and live_retrieval_activated
    )
    return {
        "status": status,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),  # noqa: UP017
        "issues": issues,
        "warnings": warnings,
        "expected_deploy_sha": expected_deploy_sha,
        "summary": {
            "deploy_sha": deploy_sha,
            "target_index_version_key": target_key,
            "env_index_version_key": _text(
                env.get("MEDICAL_AUDIT_DOCUMENT_UPLOAD_INDEXING_INDEX_VERSION_KEY")
            ),
            "env_source_package_version_key": _text(
                env.get("MEDICAL_AUDIT_DOCUMENT_UPLOAD_INDEXING_SOURCE_PACKAGE_KEY")
            ),
            "target_status": target_status,
            "target_source_collection": source_collection,
            "target_live_retrieval_activated": live_retrieval_activated,
            "runtime_activation_guard_enforced": guard_blocks,
            "personal_material_default_query_isolated": runtime.get(
                "personal_material_default_query_excludes_personal_materials"
            )
            is True,
            "personal_material_default_query_allowed_roles": default_query_allowed_roles,
            "personal_material_candidate_versions": _int(stats.get("candidate_versions")),
            "personal_material_active_versions": active_versions,
            "personal_material_documents": _int(stats.get("documents")),
            "personal_material_chunks": _int(stats.get("chunks")),
            "personal_material_active_chunks": active_chunks,
            "safe_to_execute_index_activate": safe_to_activate,
        },
        "recommended_next_step": _recommended_next_step(
            status=status,
            safe_to_activate=safe_to_activate,
            issues=issues,
        ),
        "boundaries": {
            "production_read_only": True,
            "production_write": False,
            "api_write": False,
            "db_write": False,
            "audit_log_write_expected": False,
            "external_provider_call": False,
            "index_activate_executed": False,
            "search_backend_reload_executed": False,
            "active_retrieval_activated": active_versions > 0 and active_chunks > 0,
            "evidence_grade": "L3-production-read-only",
        },
        "remote": remote_report,
    }


def _remote_audit_code(*, remote_app_dir: str, index_version_key: str | None) -> str:
    return f"""
import json
import shlex
import subprocess
from pathlib import Path

APP_DIR = {json.dumps(remote_app_dir, ensure_ascii=False)}
REQUESTED_INDEX_VERSION_KEY = {json.dumps(index_version_key or "", ensure_ascii=False)}


def run(command, cwd=None, input_text=None):
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        cwd=cwd,
        input=input_text,
    )


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


def runtime_checks():
    code = r'''
import json

payload = {{
    "activation_guard_blocks_inactive_live_retrieval": False,
    "personal_material_explicit_query_allowed_roles": [],
    "personal_material_default_query_allowed_roles": [],
    "personal_material_default_query_excludes_personal_materials": False,
    "error": "",
}}
try:
    from medical_audit_kb.api.document_permissions import allowed_explicit_source_collections
    from medical_audit_kb.api.routes_query import _effective_source_collections
    from medical_audit_kb.domain.constants import SourceCollection
    from medical_audit_kb.indexing.index_activation import (
        IndexActivationError,
        _validate_activation_allowed,
    )

    try:
        _validate_activation_allowed(
            version_key="personal-materials-candidate",
            metadata={{
                "source_collection": SourceCollection.PERSONAL_MATERIALS.value,
                "live_retrieval_activated": False,
            }},
        )
    except IndexActivationError:
        payload["activation_guard_blocks_inactive_live_retrieval"] = True

    personal_value = SourceCollection.PERSONAL_MATERIALS
    for role in ("auditor", "department-head", "it-admin", "technician"):
        if personal_value in allowed_explicit_source_collections(role):
            payload["personal_material_explicit_query_allowed_roles"].append(role)
        if personal_value in _effective_source_collections(
            role=role,
            requested_source_collections=(),
        ):
            payload["personal_material_default_query_allowed_roles"].append(role)
    payload["personal_material_default_query_excludes_personal_materials"] = (
        not payload["personal_material_default_query_allowed_roles"]
    )
except Exception as exc:
    payload["error"] = str(exc)

print(json.dumps(payload, ensure_ascii=False))
'''
    result = run(["docker", "exec", "-i", "medical_audit_app", "python", "-"], input_text=code)
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


def sql_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def db_active_gate_state(target_key):
    if not target_key:
        return {{"ok": True, "payload": {{"target_index_version_key": ""}}}}
    sql = f'''
WITH target AS (
  SELECT
    iv.version_key,
    iv.status,
    sp.version_key AS source_package_version_key,
    iv.vector_provider,
    iv.vector_model,
    iv.document_count,
    iv.chunk_count,
    iv.metadata,
    iv.created_at::text AS created_at,
    iv.activated_at::text AS activated_at
  FROM index_versions iv
  JOIN source_package_versions sp ON sp.id = iv.source_package_version_id
  WHERE iv.version_key = {{sql_literal(target_key)}}
),
personal_stats AS (
  SELECT json_build_object(
    'candidate_versions', (
      SELECT count(*) FROM index_versions
      WHERE status = 'candidate'
        AND COALESCE(metadata->>'source_collection', '') = 'personal-materials'
    ),
    'active_versions', (
      SELECT count(*) FROM index_versions
      WHERE status = 'active'
        AND COALESCE(metadata->>'source_collection', '') = 'personal-materials'
    ),
    'documents', (
      SELECT count(*) FROM source_documents
      WHERE source_collection = 'personal-materials'
    ),
    'chunks', (
      SELECT count(*)
      FROM document_chunks c
      JOIN source_documents d ON d.id = c.source_document_id
      WHERE d.source_collection = 'personal-materials'
    ),
    'active_chunks', (
      SELECT count(*)
      FROM document_chunks c
      JOIN source_documents d ON d.id = c.source_document_id
      JOIN source_package_versions spv ON spv.id = d.source_package_version_id
      JOIN index_versions iv ON iv.source_package_version_id = spv.id
      WHERE d.source_collection = 'personal-materials'
        AND iv.status = 'active'
    )
  ) AS payload
)
SELECT json_build_object(
  'target_index_version_key', {{sql_literal(target_key)}},
  'target_version', (SELECT row_to_json(target) FROM target),
  'personal_material_stats', (SELECT payload FROM personal_stats)
)
'''
    return psql_json(sql)


env_result = app_env()
runtime_result = runtime_checks()
env_values = env_result.get("values", {{}})
target_key = REQUESTED_INDEX_VERSION_KEY or env_values.get(
    "MEDICAL_AUDIT_DOCUMENT_UPLOAD_INDEXING_INDEX_VERSION_KEY", ""
)
db_result = db_active_gate_state(target_key)
deploy_sha_path = Path(APP_DIR) / ".deploy-sha"
deploy_sha = deploy_sha_path.read_text(encoding="utf-8").strip() if deploy_sha_path.exists() else ""
report = {{
    "deploy_sha": deploy_sha,
    "remote_app_dir": APP_DIR,
    "containers": {{
        "medical_audit_app": container_state("medical_audit_app"),
        "medical_audit_pg": container_state("medical_audit_pg"),
    }},
    "document_upload_indexing_env": env_values,
    "env_ok": env_result.get("ok", False),
    "env_error": env_result.get("error"),
    "runtime_checks": runtime_result.get("values", {{}}),
    "runtime_ok": runtime_result.get("ok", False),
    "runtime_error": runtime_result.get("error"),
    "db_state": db_result.get("payload", {{}}),
    "db_ok": db_result.get("ok", False),
    "db_error": db_result.get("error"),
}}
print(json.dumps(report, ensure_ascii=False))
"""


def _recommended_next_step(*, status: str, safe_to_activate: bool, issues: list[str]) -> str:
    if status != "pass":
        return (
            "保持 production unchanged；不得执行 index-activate 或 search backend reload，"
            f"先处理 blockers: {', '.join(issues)}"
        )
    if safe_to_activate:
        return (
            "只读门禁通过；若要改变生产检索行为，需单独授权执行 index-activate，"
            "并随后重载 PostgreSQL 检索后端与运行发布后验收。"
        )
    return "只读门禁通过但未形成激活条件；继续人工复核。"


def _stdout_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = _dict(report.get("summary"), "summary")
    boundaries = _dict(report.get("boundaries"), "boundaries")
    return {
        "status": report["status"],
        "issues": report["issues"],
        "warnings": report["warnings"],
        "target_index_version_key": summary["target_index_version_key"],
        "target_status": summary["target_status"],
        "target_live_retrieval_activated": summary["target_live_retrieval_activated"],
        "safe_to_execute_index_activate": summary["safe_to_execute_index_activate"],
        "evidence_grade": boundaries["evidence_grade"],
    }


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


def _dict(value: object, label: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    raise ActiveGateAuditError(f"{label} is missing or not an object")


def _dict_or_empty(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


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


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


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
    boundaries = _dict(payload.get("boundaries"), "boundaries")
    default_query_allowed_roles = (
        ", ".join(summary.get("personal_material_default_query_allowed_roles") or [])
        or "none"
    )
    lines = [
        "# Production Personal Material Active Gate",
        "",
        f"- generated_at: `{payload.get('generated_at')}`",
        f"- status: `{payload.get('status')}`",
        f"- issues: `{', '.join(payload.get('issues') or []) or 'none'}`",
        f"- warnings: `{', '.join(payload.get('warnings') or []) or 'none'}`",
        f"- deploy_sha: `{summary.get('deploy_sha')}`",
        f"- target_index_version_key: `{summary.get('target_index_version_key')}`",
        f"- target_status: `{summary.get('target_status')}`",
        f"- target_source_collection: `{summary.get('target_source_collection')}`",
        "- target_live_retrieval_activated: "
        f"`{summary.get('target_live_retrieval_activated')}`",
        "- runtime_activation_guard_enforced: "
        f"`{summary.get('runtime_activation_guard_enforced')}`",
        "- personal_material_default_query_isolated: "
        f"`{summary.get('personal_material_default_query_isolated')}`",
        "- personal_material_default_query_allowed_roles: "
        f"`{default_query_allowed_roles}`",
        "- safe_to_execute_index_activate: "
        f"`{summary.get('safe_to_execute_index_activate')}`",
        "",
        "## Personal Material Counts",
        "",
        "- personal_material_candidate_versions: "
        f"`{summary.get('personal_material_candidate_versions')}`",
        "- personal_material_active_versions: "
        f"`{summary.get('personal_material_active_versions')}`",
        f"- personal_material_documents: `{summary.get('personal_material_documents')}`",
        f"- personal_material_chunks: `{summary.get('personal_material_chunks')}`",
        f"- personal_material_active_chunks: `{summary.get('personal_material_active_chunks')}`",
        "",
        "## Boundary",
        "",
        f"- production_write: `{str(boundaries.get('production_write')).lower()}`",
        f"- api_write: `{str(boundaries.get('api_write')).lower()}`",
        f"- db_write: `{str(boundaries.get('db_write')).lower()}`",
        "- audit_log_write_expected: "
        f"`{str(boundaries.get('audit_log_write_expected')).lower()}`",
        f"- external_provider_call: `{str(boundaries.get('external_provider_call')).lower()}`",
        f"- index_activate_executed: `{str(boundaries.get('index_activate_executed')).lower()}`",
        "- search_backend_reload_executed: "
        f"`{str(boundaries.get('search_backend_reload_executed')).lower()}`",
        f"- evidence_grade: `{boundaries.get('evidence_grade')}`",
        "",
        "## Recommended Next Step",
        "",
        str(payload.get("recommended_next_step") or ""),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
