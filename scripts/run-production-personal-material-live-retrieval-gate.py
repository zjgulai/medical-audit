#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_HOST = "101.34.52.232"
DEFAULT_USER = "ubuntu"
DEFAULT_REMOTE_APP_DIR = "/opt/medical-audit/app"
DEFAULT_REPORT = "tmp/outputs/production-personal-material-live-retrieval-gate-latest.json"
PRODUCTION_HOST = "audit.lute-tlz-dddd.top"


class LiveRetrievalGateError(RuntimeError):
    pass


def main() -> int:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    ssh_key = _resolve_ssh_key(repo_root, str(args.ssh_key))
    report_path = _resolve_output(repo_root, str(args.report))
    report_path.parent.mkdir(parents=True, exist_ok=True)
    execute = bool(args.execute)
    if execute:
        _require_production_write_confirmation(str(args.confirm_production_write))
    run_id = str(args.run_id) if args.run_id else _utc_stamp()
    actor = str(args.actor) if args.actor else f"personal-material-live-gate-{run_id}"
    before = _collect_remote_report(
        ssh_key=ssh_key,
        ssh_user=str(args.ssh_user),
        ssh_host=str(args.ssh_host),
        remote_app_dir=str(args.remote_app_dir),
        index_version_key=_optional_text(args.index_version_key),
    )
    report = _build_report(
        remote_report=before,
        expected_deploy_sha=_optional_text(args.expected_deploy_sha),
        execute=False,
        actor=actor,
        run_id=run_id,
    )
    if execute and report["status"] in {"ready_for_write", "already_marked"}:
        update_result = _mark_remote_live_ready(
            ssh_key=ssh_key,
            ssh_user=str(args.ssh_user),
            ssh_host=str(args.ssh_host),
            target_index_version_key=str(report["summary"]["target_index_version_key"]),
            actor=actor,
            run_id=run_id,
        )
        after = _collect_remote_report(
            ssh_key=ssh_key,
            ssh_user=str(args.ssh_user),
            ssh_host=str(args.ssh_host),
            remote_app_dir=str(args.remote_app_dir),
            index_version_key=str(report["summary"]["target_index_version_key"]),
        )
        report = _build_report(
            remote_report=after,
            expected_deploy_sha=_optional_text(args.expected_deploy_sha),
            execute=execute,
            actor=actor,
            run_id=run_id,
        )
        report["update_result"] = update_result
    _write_json(report_path, report)
    print(json.dumps(_stdout_summary(report), ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"pass", "ready_for_write", "already_marked"} else 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Mark the production personal-material candidate index as live-retrieval-gated. "
            "This updates candidate metadata only; it never runs index-activate or reloads "
            "the search backend."
        )
    )
    parser.add_argument(
        "--ssh-key",
        default=os.environ.get("MEDICAL_AUDIT_DEPLOY_SSH_KEY", "ai_video.pem"),
    )
    parser.add_argument("--ssh-user", default=DEFAULT_USER)
    parser.add_argument("--ssh-host", default=DEFAULT_HOST)
    parser.add_argument("--remote-app-dir", default=DEFAULT_REMOTE_APP_DIR)
    parser.add_argument("--index-version-key", default="")
    parser.add_argument("--expected-deploy-sha", default="")
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--actor", default="")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--confirm-production-write",
        default="",
        help=f"Required as {PRODUCTION_HOST} with --execute.",
    )
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
        raise LiveRetrievalGateError(f"SSH key not found: {ssh_key}")
    return _run_remote_json(
        ssh_key=ssh_key,
        ssh_user=ssh_user,
        ssh_host=ssh_host,
        label="personal-material-live-gate-readonly",
        remote_code=_remote_readonly_code(
            remote_app_dir=remote_app_dir,
            index_version_key=index_version_key,
        ),
    )


def _mark_remote_live_ready(
    *,
    ssh_key: Path,
    ssh_user: str,
    ssh_host: str,
    target_index_version_key: str,
    actor: str,
    run_id: str,
) -> dict[str, Any]:
    return _run_remote_json(
        ssh_key=ssh_key,
        ssh_user=ssh_user,
        ssh_host=ssh_host,
        label="personal-material-live-gate-write",
        remote_code=_remote_write_code(
            target_index_version_key=target_index_version_key,
            actor=actor,
            run_id=run_id,
        ),
    )


def _run_remote_json(
    *,
    ssh_key: Path,
    ssh_user: str,
    ssh_host: str,
    label: str,
    remote_code: str,
) -> dict[str, Any]:
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
        f"{ssh_user}@{ssh_host} python3 - <{label}>",
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
        raise LiveRetrievalGateError(completed.stderr.strip() or f"{label} failed")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise LiveRetrievalGateError(f"{label} returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise LiveRetrievalGateError(f"{label} returned non-object JSON")
    return payload


def _build_report(
    *,
    remote_report: dict[str, Any],
    expected_deploy_sha: str | None,
    execute: bool,
    actor: str,
    run_id: str,
) -> dict[str, Any]:
    containers = _dict(remote_report.get("containers"), "containers")
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
    if remote_report.get("runtime_ok") is False:
        issues.append("runtime-check-failed")
    if remote_report.get("db_ok") is False:
        issues.append("db-read-failed")

    target_key = _text(db_state.get("target_index_version_key"))
    if not target_key:
        issues.append("target-index-version-key-missing")
    if target_key and target_version is None:
        issues.append("target-index-version-not-found")

    target_status = ""
    source_collection = ""
    live_retrieval_activated = False
    if target_version is not None:
        metadata = _dict_or_empty(target_version.get("metadata"))
        target_status = _text(target_version.get("status"))
        source_collection = _text(metadata.get("source_collection"))
        live_retrieval_activated = metadata.get("live_retrieval_activated") is True
        if target_status != "candidate":
            issues.append("target-index-version-not-candidate")
        if source_collection != "personal-materials":
            issues.append("target-index-version-not-personal-materials")

    if runtime.get("activation_guard_blocks_inactive_live_retrieval") is not True:
        issues.append("runtime-activation-guard-not-enforced")
    if runtime.get("personal_material_default_query_excludes_personal_materials") is not True:
        issues.append("personal-material-default-query-not-isolated")
    explicit_roles = _str_list(runtime.get("personal_material_explicit_query_allowed_roles"))
    if explicit_roles:
        issues.append("personal-material-explicit-query-access-present")

    stats = _dict_or_empty(db_state.get("personal_material_stats"))
    candidate_chunks = _int(stats.get("chunks"))
    active_versions = _int(stats.get("active_versions"))
    active_chunks = _int(stats.get("active_chunks"))
    ready_not_indexed = _int(stats.get("ready_not_indexed_uploads"))
    if candidate_chunks <= 0:
        issues.append("personal-material-candidate-has-no-chunks")
    if active_versions > 0 or active_chunks > 0:
        issues.append("active-personal-material-index-already-present")
    if ready_not_indexed > 0:
        warnings.append("ready-not-indexed-uploads-present")

    if issues:
        status = "blocked"
    elif live_retrieval_activated:
        status = "pass" if execute else "already_marked"
    else:
        status = "pass" if execute else "ready_for_write"

    return {
        "status": status,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "issues": issues,
        "warnings": warnings,
        "expected_deploy_sha": expected_deploy_sha,
        "summary": {
            "deploy_sha": deploy_sha,
            "target_index_version_key": target_key,
            "target_status": target_status,
            "target_source_collection": source_collection,
            "target_live_retrieval_activated": live_retrieval_activated,
            "runtime_activation_guard_enforced": runtime.get(
                "activation_guard_blocks_inactive_live_retrieval"
            )
            is True,
            "personal_material_default_query_isolated": runtime.get(
                "personal_material_default_query_excludes_personal_materials"
            )
            is True,
            "personal_material_explicit_query_allowed_roles": explicit_roles,
            "personal_material_candidate_versions": _int(stats.get("candidate_versions")),
            "personal_material_active_versions": active_versions,
            "personal_material_documents": _int(stats.get("documents")),
            "personal_material_chunks": candidate_chunks,
            "personal_material_active_chunks": active_chunks,
            "ready_not_indexed_uploads": ready_not_indexed,
            "actor": actor,
            "run_id": run_id,
        },
        "boundaries": {
            "production_read_only": not execute,
            "production_write": execute,
            "api_write": False,
            "db_write": execute,
            "audit_log_write_expected": False,
            "external_provider_call": False,
            "index_activate_executed": False,
            "search_backend_reload_executed": False,
            "active_retrieval_activated": active_versions > 0 and active_chunks > 0,
        },
        "remote": remote_report,
    }


def _remote_readonly_code(*, remote_app_dir: str, index_version_key: str | None) -> str:
    return f"""
import json
import shlex
import subprocess
from pathlib import Path

APP_DIR = {json.dumps(remote_app_dir, ensure_ascii=False)}
REQUESTED_INDEX_VERSION_KEY = {json.dumps(index_version_key or "", ensure_ascii=False)}


def run(command, input_text=None):
    return subprocess.run(command, check=False, capture_output=True, text=True, input=input_text)


def docker_inspect_json(name, template):
    result = run(["docker", "inspect", name, "--format", template])
    if result.returncode != 0:
        return {{"available": False, "error": result.stderr.strip()}}
    try:
        value = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        value = result.stdout.strip()
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
        "MEDICAL_AUDIT_DOCUMENT_UPLOAD_INDEXING_INDEX_VERSION_KEY",
        "MEDICAL_AUDIT_DOCUMENT_UPLOAD_INDEXING_SOURCE_PACKAGE_KEY",
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
    from medical_audit_kb.api.document_permissions import allowed_source_collections
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
        if personal_value in allowed_source_collections(role):
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
        return {{"ok": True, "payload": json.loads(text)}}
    except json.JSONDecodeError as exc:
        return {{"ok": False, "error": f"invalid JSON from psql: {{exc}}", "stdout": text[:500]}}


def sql_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def db_state(target_key):
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
    ),
    'ready_not_indexed_uploads', (
      SELECT count(*)
      FROM document_upload_records
      WHERE COALESCE(extra_metadata->'index_readiness'->>'status', '') = 'ready'
        AND COALESCE(extra_metadata->>'index_status', 'not-indexed') = 'not-indexed'
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
env_values = env_result.get("values", {{}})
target_key = REQUESTED_INDEX_VERSION_KEY or env_values.get(
    "MEDICAL_AUDIT_DOCUMENT_UPLOAD_INDEXING_INDEX_VERSION_KEY", ""
)
runtime_result = runtime_checks()
db_result = (
    db_state(target_key)
    if target_key
    else {{"ok": True, "payload": {{"target_index_version_key": ""}}}}
)
deploy_sha_path = Path(APP_DIR) / ".deploy-sha"
deploy_sha = deploy_sha_path.read_text(encoding="utf-8").strip() if deploy_sha_path.exists() else ""
print(json.dumps({{
    "deploy_sha": deploy_sha,
    "remote_app_dir": APP_DIR,
    "containers": {{
        "medical_audit_app": container_state("medical_audit_app"),
        "medical_audit_pg": container_state("medical_audit_pg"),
    }},
    "env_ok": env_result.get("ok", False),
    "env_error": env_result.get("error"),
    "document_upload_indexing_env": env_values,
    "runtime_ok": runtime_result.get("ok", False),
    "runtime_error": runtime_result.get("error"),
    "runtime_checks": runtime_result.get("values", {{}}),
    "db_ok": db_result.get("ok", False),
    "db_error": db_result.get("error"),
    "db_state": db_result.get("payload", {{}}),
}}, ensure_ascii=False))
"""


def _remote_write_code(*, target_index_version_key: str, actor: str, run_id: str) -> str:
    return f"""
import json
import shlex
import subprocess

TARGET_KEY = {json.dumps(target_index_version_key, ensure_ascii=False)}
ACTOR = {json.dumps(actor, ensure_ascii=False)}
RUN_ID = {json.dumps(run_id, ensure_ascii=False)}


def run(command):
    return subprocess.run(command, check=False, capture_output=True, text=True)


def sql_literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def psql_json(sql):
    shell = 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -c ' + shlex.quote(sql)
    result = run(["docker", "exec", "medical_audit_pg", "sh", "-lc", shell])
    if result.returncode != 0:
        print(json.dumps({{"ok": False, "error": result.stderr.strip()}}, ensure_ascii=False))
        raise SystemExit(0)
    text = result.stdout.strip() or "{{}}"
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        payload = {{"invalid_json": str(exc), "stdout": text[:500]}}
    print(json.dumps({{"ok": True, "payload": payload}}, ensure_ascii=False))


sql = f'''
WITH target AS (
  SELECT iv.id, iv.source_package_version_id
  FROM index_versions iv
  WHERE iv.version_key = {{sql_literal(TARGET_KEY)}}
    AND iv.status = 'candidate'
    AND COALESCE(iv.metadata->>'source_collection', '') = 'personal-materials'
  FOR UPDATE
),
updated_index AS (
  UPDATE index_versions iv
  SET metadata = iv.metadata || jsonb_build_object(
    'live_retrieval_activated', true,
    'live_retrieval_activated_at', now()::text,
    'live_retrieval_activated_by', {{sql_literal(ACTOR)}},
    'live_retrieval_gate_run_id', {{sql_literal(RUN_ID)}},
    'live_retrieval_gate', jsonb_build_object(
      'default_query_isolated', true,
      'activation_guard_enforced', true,
      'index_activate_executed', false,
      'search_backend_reload_executed', false
    )
  )
  FROM target
  WHERE iv.id = target.id
  RETURNING iv.version_key, iv.status, iv.metadata
),
updated_package AS (
  UPDATE source_package_versions sp
  SET metadata = sp.metadata || jsonb_build_object(
    'live_retrieval_activated', true,
    'live_retrieval_activated_at', now()::text,
    'live_retrieval_activated_by', {{sql_literal(ACTOR)}},
    'live_retrieval_gate_run_id', {{sql_literal(RUN_ID)}}
  )
  FROM target
  WHERE sp.id = target.source_package_version_id
  RETURNING sp.version_key
),
updated_chunks AS (
  UPDATE document_chunks dc
  SET metadata = dc.metadata || jsonb_build_object(
    'live_retrieval_activated', true,
    'live_retrieval_gate_run_id', {{sql_literal(RUN_ID)}}
  )
  FROM source_documents sd, target
  WHERE dc.source_document_id = sd.id
    AND sd.source_package_version_id = target.source_package_version_id
    AND sd.source_collection = 'personal-materials'
  RETURNING dc.id
)
SELECT json_build_object(
  'updated_index_version', (SELECT row_to_json(updated_index) FROM updated_index),
  'updated_package_count', (SELECT count(*) FROM updated_package),
  'updated_chunk_count', (SELECT count(*) FROM updated_chunks)
)
'''
psql_json(sql)
"""


def _require_production_write_confirmation(confirm_production_write: str) -> None:
    if confirm_production_write != PRODUCTION_HOST:
        raise LiveRetrievalGateError(
            "production live retrieval gate requires "
            f"--confirm-production-write {PRODUCTION_HOST}"
        )


def _resolve_ssh_key(repo_root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return repo_root / path


def _resolve_output(repo_root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return repo_root / path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _stdout_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = _dict(report.get("summary"), "summary")
    boundaries = _dict(report.get("boundaries"), "boundaries")
    return {
        "status": report["status"],
        "issues": report["issues"],
        "warnings": report["warnings"],
        "target_index_version_key": summary["target_index_version_key"],
        "target_live_retrieval_activated": summary["target_live_retrieval_activated"],
        "personal_material_default_query_isolated": summary[
            "personal_material_default_query_isolated"
        ],
        "production_write": boundaries["production_write"],
        "db_write": boundaries["db_write"],
        "index_activate_executed": boundaries["index_activate_executed"],
        "search_backend_reload_executed": boundaries["search_backend_reload_executed"],
    }


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _optional_text(value: object) -> str | None:
    text = _text(value)
    return text or None


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _dict(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LiveRetrievalGateError(f"{label} is not an object")
    return value


def _dict_or_empty(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


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


def _container_health(containers: dict[str, Any], name: str) -> str:
    item = containers.get(name)
    if not isinstance(item, dict):
        return ""
    return _text(item.get("health") or item.get("status"))


if __name__ == "__main__":
    raise SystemExit(main())
