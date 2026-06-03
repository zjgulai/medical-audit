#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_OUTPUT = "tmp/outputs/knowledge-query-index-candidate-release-readiness-latest.md"
DEFAULT_JSON_OUTPUT = "tmp/outputs/knowledge-query-index-candidate-release-readiness-latest.json"


@dataclass(frozen=True, slots=True)
class IndexVersion:
    version_key: str
    status: str
    source_package_version_key: str | None
    vector_provider: str | None
    vector_model: str | None
    document_count: int
    chunk_count: int
    created_at: str | None = None
    activated_at: str | None = None

    @property
    def provider_model_key(self) -> str:
        return f"{self.vector_provider or 'unknown'}::{self.vector_model or 'unknown'}"

    def to_dict(self) -> dict[str, object]:
        return {
            "version_key": self.version_key,
            "status": self.status,
            "source_package_version_key": self.source_package_version_key,
            "vector_provider": self.vector_provider,
            "vector_model": self.vector_model,
            "document_count": self.document_count,
            "chunk_count": self.chunk_count,
            "created_at": self.created_at,
            "activated_at": self.activated_at,
        }


def main() -> int:
    args = _parse_args()
    import_result = _load_mapping(Path(args.import_result_json))
    incremental_plan = (
        _load_mapping(Path(args.incremental_plan_json)) if args.incremental_plan_json else None
    )
    versions = (
        _load_versions_file(Path(args.versions_file))
        if args.versions_file
        else _load_versions_from_database(database_url_env=str(args.database_url_env))
    )
    candidate_chunk_ids = _load_candidate_chunk_ids(
        import_result,
        chunks_file=args.candidate_chunks_file,
    )
    active_chunk_ids = (
        _load_chunk_ids_file(Path(args.active_chunks_file))
        if args.active_chunks_file
        else (
            _load_active_chunk_ids_from_database(database_url_env=str(args.database_url_env))
            if not args.versions_file
            else None
        )
    )
    report = _build_report(
        import_result=import_result,
        versions=versions,
        incremental_plan=incremental_plan,
        candidate_chunk_ids=candidate_chunk_ids,
        active_chunk_ids=active_chunk_ids,
        expected_active_key=args.expected_active_key,
        allow_provider_model_change=bool(args.allow_provider_model_change),
        versions_source="file" if args.versions_file else "database",
    )
    output = Path(args.output)
    json_output = Path(args.json_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_render_markdown(report), encoding="utf-8")
    json_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(_stdout_summary(report), ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit whether a pgvector dry-run result is safe to write as candidate.",
    )
    parser.add_argument("--import-result-json", required=True)
    parser.add_argument("--incremental-plan-json")
    parser.add_argument("--candidate-chunks-file")
    parser.add_argument("--active-chunks-file")
    parser.add_argument("--database-url-env", default="MEDICAL_AUDIT_KB_DATABASE_URL")
    parser.add_argument("--versions-file")
    parser.add_argument("--expected-active-key")
    parser.add_argument(
        "--allow-provider-model-change",
        action="store_true",
        help="Allow candidate provider/model to differ from current active.",
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT)
    return parser.parse_args()


def _load_mapping(path: Path) -> Mapping[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON file must contain an object: {path}")
    return payload


def _load_versions_file(path: Path) -> tuple[IndexVersion, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("versions file must contain a JSON array")
    return tuple(_version_from_mapping(item) for item in payload)


def _load_versions_from_database(*, database_url_env: str) -> tuple[IndexVersion, ...]:
    database_url = os.environ.get(database_url_env)
    if not database_url:
        raise RuntimeError(f"missing database URL env: {database_url_env}")

    import psycopg

    query = """
        SELECT
            iv.version_key,
            iv.status,
            sp.version_key AS source_package_version_key,
            iv.vector_provider,
            iv.vector_model,
            iv.document_count,
            iv.chunk_count,
            iv.created_at::text,
            iv.activated_at::text
        FROM index_versions iv
        JOIN source_package_versions sp ON sp.id = iv.source_package_version_id
        ORDER BY iv.created_at ASC
    """
    with (
        psycopg.connect(_normalize_database_url(database_url)) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(query)
        rows = cursor.fetchall()
    return tuple(_version_from_row(row) for row in rows)


def _build_report(
    *,
    import_result: Mapping[str, object],
    versions: tuple[IndexVersion, ...],
    incremental_plan: Mapping[str, object] | None,
    candidate_chunk_ids: set[str] | None,
    active_chunk_ids: set[str] | None,
    expected_active_key: str | None,
    allow_provider_model_change: bool,
    versions_source: str,
) -> dict[str, object]:
    import_summary = _extract_import_summary(import_result)
    active_versions = tuple(version for version in versions if version.status == "active")
    candidate_versions = tuple(version for version in versions if version.status == "candidate")
    inactive_versions = tuple(version for version in versions if version.status == "inactive")
    blocking_reasons: list[str] = []

    blocking_reasons.extend(_import_blockers(import_result, import_summary))

    active = active_versions[0] if len(active_versions) == 1 else None
    if not active_versions:
        blocking_reasons.append("no-active-index-version")
    if len(active_versions) > 1:
        blocking_reasons.append("multiple-active-index-versions")
    if expected_active_key and (
        len(active_versions) != 1 or active_versions[0].version_key != expected_active_key
    ):
        blocking_reasons.append("expected-active-version-mismatch")

    candidate_key = _optional_str(import_summary.get("candidate_index_version_key"))
    existing_version = _version_by_key(versions, candidate_key)
    if candidate_key is not None and existing_version is not None:
        blocking_reasons.append("candidate-index-version-key-already-exists")
    if active is not None and candidate_key == active.version_key:
        blocking_reasons.append("candidate-index-version-key-matches-active")
    if (
        active is not None
        and not allow_provider_model_change
        and import_summary["provider_model_key"] != active.provider_model_key
    ):
        blocking_reasons.append("candidate-provider-model-differs-from-active")

    chunk_collision_summary = _chunk_collision_summary(
        candidate_source_package_key=_optional_str(
            import_summary.get("source_package_version_key")
        ),
        active=active,
        candidate_chunk_ids=candidate_chunk_ids,
        active_chunk_ids=active_chunk_ids,
        versions_source=versions_source,
    )
    if chunk_collision_summary["required"] is True:
        if chunk_collision_summary["evidence_available"] is not True:
            blocking_reasons.append("candidate-active-chunk-collision-check-missing")
        elif chunk_collision_summary["collision_count"] != 0:
            blocking_reasons.append("candidate-chunk-id-collides-with-active-package")

    incremental_summary = (
        _extract_incremental_summary(incremental_plan) if incremental_plan is not None else None
    )
    if incremental_summary is not None:
        if incremental_summary["ready_for_incremental_build"] is not True:
            blocking_reasons.append("incremental-plan-not-ready")
        if (
            active is not None
            and incremental_summary["active_index_version_key"] is not None
            and incremental_summary["active_index_version_key"] != active.version_key
        ):
            blocking_reasons.append("incremental-plan-active-version-mismatch")

    status = "pass" if not blocking_reasons else "blocked"
    return {
        "status": status,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "evidence_grade": _evidence_grade(versions_source),
        "safe_to_execute_candidate_write": status == "pass",
        "blocking_reasons": blocking_reasons,
        "recommended_next_step": _recommended_next_step(status, versions_source),
        "allow_provider_model_change": allow_provider_model_change,
        "summary": {
            "versions_source": versions_source,
            "index_version_count": len(versions),
            "active_count": len(active_versions),
            "candidate_count": len(candidate_versions),
            "inactive_count": len(inactive_versions),
            "statuses": dict(sorted(Counter(version.status for version in versions).items())),
        },
        "candidate": import_summary,
        "active_version": active.to_dict() if active is not None else None,
        "chunk_collision_check": chunk_collision_summary,
        "existing_candidate_version": (
            existing_version.to_dict() if existing_version is not None else None
        ),
        "incremental_plan": incremental_summary,
        "versions": [version.to_dict() for version in versions],
    }


def _extract_import_summary(import_result: Mapping[str, object]) -> dict[str, object]:
    manifest = _ensure_mapping(import_result.get("manifest"))
    plan = _ensure_mapping(manifest.get("plan"))
    summary = _ensure_mapping(plan.get("summary"))
    provider = _optional_str(
        plan.get("expected_embedding_provider") or summary.get("embedding_provider")
    )
    model = _optional_str(plan.get("expected_embedding_model") or summary.get("embedding_model"))
    return {
        "mode": _optional_str(import_result.get("mode")),
        "executed": import_result.get("executed"),
        "success": import_result.get("success"),
        "index_version_status": _optional_str(import_result.get("index_version_status")),
        "manifest_ready_for_write": manifest.get("ready_for_write"),
        "candidate_index_version_key": _optional_str(summary.get("index_version_key")),
        "source_package_version_key": _optional_str(summary.get("source_package_version_key")),
        "vector_provider": provider,
        "vector_model": model,
        "provider_model_key": f"{provider or 'unknown'}::{model or 'unknown'}",
        "source_document_count": _optional_int(manifest.get("source_document_count")),
        "document_chunk_count": _optional_int(manifest.get("document_chunk_count")),
        "chunk_embedding_count": _optional_int(manifest.get("chunk_embedding_count")),
        "failed_file_count": _optional_int(manifest.get("failed_file_count")),
        "pending_file_count": _optional_int(manifest.get("pending_file_count")),
        "source_file_missing_count": _optional_int(manifest.get("source_file_missing_count")),
        "invalid_source_metadata_count": _optional_int(
            manifest.get("invalid_source_metadata_count")
        ),
    }


def _import_blockers(
    import_result: Mapping[str, object],
    import_summary: Mapping[str, object],
) -> list[str]:
    blockers: list[str] = []
    if import_summary["mode"] != "dry-run":
        blockers.append("import-result-not-dry-run")
    if import_summary["executed"] is not False:
        blockers.append("import-result-was-executed")
    if import_summary["success"] is not True:
        blockers.append("import-result-not-successful")
    if import_summary["index_version_status"] != "candidate":
        blockers.append("import-result-not-candidate-status")
    if import_summary["manifest_ready_for_write"] is not True:
        blockers.append("import-manifest-not-ready-for-write")
    if import_summary["candidate_index_version_key"] is None:
        blockers.append("missing-candidate-index-version-key")
    if import_summary["source_package_version_key"] is None:
        blockers.append("missing-source-package-version-key")
    if import_summary["source_file_missing_count"] != 0:
        blockers.append("source-files-missing-for-candidate")
    if import_summary["invalid_source_metadata_count"] != 0:
        blockers.append("invalid-source-metadata-for-candidate")
    if _positive_count(import_summary["source_document_count"]) is False:
        blockers.append("candidate-source-document-count-not-positive")
    if _positive_count(import_summary["document_chunk_count"]) is False:
        blockers.append("candidate-document-chunk-count-not-positive")
    if _positive_count(import_summary["chunk_embedding_count"]) is False:
        blockers.append("candidate-chunk-embedding-count-not-positive")
    if "manifest" not in import_result:
        blockers.append("import-result-missing-manifest")
    return blockers


def _extract_incremental_summary(plan: Mapping[str, object]) -> dict[str, object]:
    return {
        "ready_for_incremental_build": plan.get("ready_for_incremental_build"),
        "active_index_version_key": _optional_str(plan.get("active_index_version_key")),
        "active_source_package_version_key": _optional_str(
            plan.get("active_source_package_version_key")
        ),
        "added_file_count": _optional_int(plan.get("added_file_count")),
        "modified_file_count": _optional_int(plan.get("modified_file_count")),
        "deleted_file_count": _optional_int(plan.get("deleted_file_count")),
        "unchanged_file_count": _optional_int(plan.get("unchanged_file_count")),
        "estimated_new_embeddings": _optional_int(plan.get("estimated_new_embeddings")),
        "db_rows_to_deactivate": _optional_int(plan.get("db_rows_to_deactivate")),
        "db_rows_to_activate": _optional_int(plan.get("db_rows_to_activate")),
    }


def _render_markdown(report: Mapping[str, object]) -> str:
    summary = _ensure_mapping(report["summary"])
    candidate = _ensure_mapping(report["candidate"])
    active_version = report.get("active_version")
    chunk_collision_check = _ensure_mapping(report["chunk_collision_check"])
    incremental_plan = report.get("incremental_plan")
    lines = [
        "# 知识库 candidate 发布就绪审计报告",
        "",
        f"- `generated_at`: `{report['generated_at']}`",
        f"- `status`: `{report['status']}`",
        f"- `evidence_grade`: `{report['evidence_grade']}`",
        f"- `safe_to_execute_candidate_write`: `{report['safe_to_execute_candidate_write']}`",
        f"- `blocking_reasons`: `{', '.join(_str_list(report['blocking_reasons'])) or 'none'}`",
        f"- `recommended_next_step`: {report['recommended_next_step']}",
        "",
        "## 版本计数",
        "",
        f"- `versions_source`: `{summary['versions_source']}`",
        f"- `index_version_count`: `{summary['index_version_count']}`",
        f"- `active_count`: `{summary['active_count']}`",
        f"- `candidate_count`: `{summary['candidate_count']}`",
        f"- `inactive_count`: `{summary['inactive_count']}`",
        "",
        "## candidate dry-run 摘要",
        "",
        f"- `candidate_index_version_key`: `{candidate['candidate_index_version_key']}`",
        f"- `source_package_version_key`: `{candidate['source_package_version_key']}`",
        f"- `vector_provider`: `{candidate['vector_provider'] or 'unknown'}`",
        f"- `vector_model`: `{candidate['vector_model'] or 'unknown'}`",
        f"- `source_document_count`: `{candidate['source_document_count']}`",
        f"- `document_chunk_count`: `{candidate['document_chunk_count']}`",
        f"- `chunk_embedding_count`: `{candidate['chunk_embedding_count']}`",
        f"- `pending_file_count`: `{candidate['pending_file_count']}`",
        "",
        "## chunk id 碰撞检查",
        "",
        f"- `required`: `{chunk_collision_check['required']}`",
        f"- `evidence_available`: `{chunk_collision_check['evidence_available']}`",
        f"- `collision_count`: `{chunk_collision_check['collision_count']}`",
        f"- `reason`: `{chunk_collision_check['reason']}`",
        "",
        "## 当前 active 版本",
        "",
        _version_line(_ensure_mapping(active_version)) if active_version else "- 无 active 版本",
        "",
        "## 增量计划",
        "",
        _incremental_line(_ensure_mapping(incremental_plan))
        if incremental_plan
        else "- 未提供增量计划 JSON",
        "",
    ]
    return "\n".join(lines)


def _stdout_summary(report: Mapping[str, object]) -> dict[str, object]:
    summary = _ensure_mapping(report["summary"])
    return {
        "status": report["status"],
        "evidence_grade": report["evidence_grade"],
        "safe_to_execute_candidate_write": report["safe_to_execute_candidate_write"],
        "blocking_reasons": report["blocking_reasons"],
        "active_count": summary["active_count"],
        "candidate_count": summary["candidate_count"],
    }


def _recommended_next_step(status: str, versions_source: str) -> str:
    if status != "pass":
        return "先修复 blocking_reasons；不得执行 candidate 写入或 active 激活。"
    if versions_source != "database":
        return "fixture 门禁通过；生产执行前必须用数据库只读版本状态重新审计。"
    return (
        "可以执行 `pgvector-import --execute --index-version-status candidate`；"
        "写入后必须先评测 candidate，不得直接激活。"
    )


def _evidence_grade(versions_source: str) -> str:
    if versions_source == "database":
        return "L3-production-read-only + L2-dry-run"
    return "L2-fixture-or-dry-run"


def _load_candidate_chunk_ids(
    import_result: Mapping[str, object],
    *,
    chunks_file: str | None,
) -> set[str] | None:
    if chunks_file:
        return _load_chunk_ids_file(Path(chunks_file))
    manifest = _ensure_mapping(import_result.get("manifest"))
    index_root = _optional_str(manifest.get("index_root"))
    if index_root is None:
        return None
    path = Path(index_root) / "chunks.jsonl"
    return _load_chunk_ids_file(path) if path.exists() else None


def _load_chunk_ids_file(path: Path) -> set[str]:
    chunk_ids: set[str] = set()
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"chunk row must be an object: {path}:{line_number}")
            chunk_id = _optional_str(payload.get("chunk_id"))
            if chunk_id is None:
                raise ValueError(f"chunk row missing chunk_id: {path}:{line_number}")
            chunk_ids.add(chunk_id)
    return chunk_ids


def _load_active_chunk_ids_from_database(*, database_url_env: str) -> set[str]:
    database_url = os.environ.get(database_url_env)
    if not database_url:
        raise RuntimeError(f"missing database URL env: {database_url_env}")

    import psycopg

    query = """
        SELECT dc.id::text
        FROM document_chunks dc
        JOIN source_documents sd ON sd.id = dc.source_document_id
        JOIN index_versions iv ON iv.source_package_version_id = sd.source_package_version_id
        WHERE iv.status = 'active'
          AND sd.status = 'indexed'
    """
    with (
        psycopg.connect(_normalize_database_url(database_url)) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(query)
        return {str(row[0]) for row in cursor.fetchall()}


def _chunk_collision_summary(
    *,
    candidate_source_package_key: str | None,
    active: IndexVersion | None,
    candidate_chunk_ids: set[str] | None,
    active_chunk_ids: set[str] | None,
    versions_source: str,
) -> dict[str, object]:
    if active is None:
        return _chunk_collision_result(
            required=False,
            evidence_available=False,
            collision_ids=(),
            reason="no-active-version",
        )
    active_source_package_key = active.source_package_version_key
    if candidate_source_package_key is None or active_source_package_key is None:
        return _chunk_collision_result(
            required=versions_source == "database",
            evidence_available=False,
            collision_ids=(),
            reason="missing-source-package-version-key",
        )
    if candidate_source_package_key == active_source_package_key:
        return _chunk_collision_result(
            required=False,
            evidence_available=True,
            collision_ids=(),
            reason="same-source-package-version",
        )

    required = True
    evidence_available = candidate_chunk_ids is not None and active_chunk_ids is not None
    if not evidence_available:
        return _chunk_collision_result(
            required=required,
            evidence_available=False,
            collision_ids=(),
            reason="chunk-id-evidence-missing",
        )
    assert candidate_chunk_ids is not None
    assert active_chunk_ids is not None
    collision_ids = candidate_chunk_ids.intersection(active_chunk_ids)
    collisions = tuple(sorted(collision_ids)[:20])
    return _chunk_collision_result(
        required=required,
        evidence_available=True,
        collision_ids=collisions,
        reason="different-source-package-version",
        collision_count=len(collision_ids),
    )


def _chunk_collision_result(
    *,
    required: bool,
    evidence_available: bool,
    collision_ids: tuple[str, ...],
    reason: str,
    collision_count: int | None = None,
) -> dict[str, object]:
    return {
        "required": required,
        "evidence_available": evidence_available,
        "collision_count": len(collision_ids) if collision_count is None else collision_count,
        "collision_samples": list(collision_ids),
        "reason": reason,
    }


def _version_by_key(
    versions: tuple[IndexVersion, ...],
    version_key: str | None,
) -> IndexVersion | None:
    if version_key is None:
        return None
    for version in versions:
        if version.version_key == version_key:
            return version
    return None


def _version_from_mapping(payload: object) -> IndexVersion:
    item = _ensure_mapping(payload)
    return IndexVersion(
        version_key=_required_str(item, "version_key"),
        status=_required_str(item, "status"),
        vector_provider=_optional_str(item.get("vector_provider")),
        vector_model=_optional_str(item.get("vector_model")),
        source_package_version_key=_optional_str(item.get("source_package_version_key")),
        document_count=_required_int(item, "document_count"),
        chunk_count=_required_int(item, "chunk_count"),
        created_at=_optional_str(item.get("created_at")),
        activated_at=_optional_str(item.get("activated_at")),
    )


def _version_from_row(row: tuple[object, ...]) -> IndexVersion:
    return IndexVersion(
        version_key=str(row[0]),
        status=str(row[1]),
        source_package_version_key=_optional_str(row[2]),
        vector_provider=_optional_str(row[3]),
        vector_model=_optional_str(row[4]),
        document_count=_coerce_int(row[5], "document_count"),
        chunk_count=_coerce_int(row[6], "chunk_count"),
        created_at=_optional_str(row[7]),
        activated_at=_optional_str(row[8]),
    )


def _version_line(version: Mapping[str, object]) -> str:
    return (
        f"- `{version['version_key']}` | status=`{version['status']}` | "
        f"provider=`{version['vector_provider'] or 'unknown'}` | "
        f"model=`{version['vector_model'] or 'unknown'}` | "
        f"documents=`{version['document_count']}` | chunks=`{version['chunk_count']}`"
    )


def _incremental_line(plan: Mapping[str, object]) -> str:
    return (
        f"- `ready_for_incremental_build`: `{plan['ready_for_incremental_build']}` | "
        f"`active_index_version_key`: `{plan['active_index_version_key']}` | "
        f"`added`: `{plan['added_file_count']}` | "
        f"`modified`: `{plan['modified_file_count']}` | "
        f"`deleted`: `{plan['deleted_file_count']}` | "
        f"`estimated_new_embeddings`: `{plan['estimated_new_embeddings']}`"
    )


def _positive_count(value: object) -> bool:
    return isinstance(value, int) and value > 0


def _ensure_mapping(payload: object) -> Mapping[str, object]:
    if isinstance(payload, Mapping):
        return payload
    raise ValueError("expected mapping")


def _required_str(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing string field: {key}")
    return value


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _required_int(payload: Mapping[str, object], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"missing integer field: {key}")
    return value


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def _coerce_int(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"invalid integer field: {field_name}")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise ValueError(f"invalid integer field: {field_name}")


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+psycopg://"):
        return "postgresql://" + database_url.removeprefix("postgresql+psycopg://")
    return database_url


if __name__ == "__main__":
    raise SystemExit(main())
