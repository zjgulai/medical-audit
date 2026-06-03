#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_OUTPUT = "tmp/outputs/knowledge-query-index-rollback-readiness-latest.md"
DEFAULT_JSON_OUTPUT = "tmp/outputs/knowledge-query-index-rollback-readiness-latest.json"


@dataclass(frozen=True, slots=True)
class IndexVersion:
    version_key: str
    status: str
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
            "vector_provider": self.vector_provider,
            "vector_model": self.vector_model,
            "document_count": self.document_count,
            "chunk_count": self.chunk_count,
            "created_at": self.created_at,
            "activated_at": self.activated_at,
        }


def main() -> int:
    args = _parse_args()
    versions = (
        _load_versions_file(Path(args.versions_file))
        if args.versions_file
        else _load_versions_from_database(database_url_env=str(args.database_url_env))
    )
    report = _build_report(versions, expected_active_key=args.expected_active_key)
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
        description="Audit whether a production index rollback rehearsal can safely run.",
    )
    parser.add_argument("--database-url-env", default="MEDICAL_AUDIT_KB_DATABASE_URL")
    parser.add_argument(
        "--versions-file",
        help="Read index versions from a JSON file instead of DB.",
    )
    parser.add_argument("--expected-active-key")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT)
    return parser.parse_args()


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
            version_key,
            status,
            vector_provider,
            vector_model,
            document_count,
            chunk_count,
            created_at::text,
            activated_at::text
        FROM index_versions
        ORDER BY created_at ASC
    """
    with (
        psycopg.connect(_normalize_database_url(database_url)) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(query)
        rows = cursor.fetchall()
    return tuple(_version_from_row(row) for row in rows)


def _build_report(
    versions: tuple[IndexVersion, ...],
    *,
    expected_active_key: str | None,
) -> dict[str, object]:
    active_versions = tuple(version for version in versions if version.status == "active")
    inactive_versions = tuple(version for version in versions if version.status == "inactive")
    candidate_versions = tuple(version for version in versions if version.status == "candidate")
    blocking_reasons: list[str] = []

    if not active_versions:
        blocking_reasons.append("no-active-index-version")
    if len(active_versions) > 1:
        blocking_reasons.append("multiple-active-index-versions")
    if expected_active_key and (
        len(active_versions) != 1 or active_versions[0].version_key != expected_active_key
    ):
        blocking_reasons.append("expected-active-version-mismatch")

    active = active_versions[0] if len(active_versions) == 1 else None
    rollback_targets: tuple[IndexVersion, ...] = ()
    if active is not None:
        rollback_targets = tuple(
            version
            for version in inactive_versions
            if version.provider_model_key == active.provider_model_key
        )
        if not rollback_targets:
            blocking_reasons.append("no-inactive-rollback-target-for-active-provider-model")

    status = "pass" if not blocking_reasons else "blocked"
    recommended_next_step = (
        "可以选择一个 inactive 版本执行受控 rollback，然后 reload PostgreSQL 后端并运行生产 E2E。"
        if status == "pass"
        else (
            "先发布下一版 candidate 并激活，使当前 active 变为 inactive；"
            "随后再做真实 rollback 演练。"
        )
    )
    return {
        "status": status,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "safe_to_execute_rollback_rehearsal": status == "pass",
        "blocking_reasons": blocking_reasons,
        "recommended_next_step": recommended_next_step,
        "summary": {
            "index_version_count": len(versions),
            "active_count": len(active_versions),
            "inactive_count": len(inactive_versions),
            "candidate_count": len(candidate_versions),
            "rollback_target_count": len(rollback_targets),
            "statuses": dict(sorted(Counter(version.status for version in versions).items())),
        },
        "active_version": active.to_dict() if active is not None else None,
        "rollback_targets": [version.to_dict() for version in rollback_targets],
        "versions": [version.to_dict() for version in versions],
    }


def _render_markdown(report: dict[str, object]) -> str:
    summary = _ensure_dict(report["summary"])
    active_version = report.get("active_version")
    rollback_targets = _ensure_list(report["rollback_targets"])
    versions = _ensure_list(report["versions"])
    lines = [
        "# 知识库索引回滚就绪审计报告",
        "",
        f"- `generated_at`: `{report['generated_at']}`",
        f"- `status`: `{report['status']}`",
        (
            "- `safe_to_execute_rollback_rehearsal`: "
            f"`{report['safe_to_execute_rollback_rehearsal']}`"
        ),
        f"- `blocking_reasons`: `{', '.join(_str_list(report['blocking_reasons'])) or 'none'}`",
        f"- `recommended_next_step`: {report['recommended_next_step']}",
        "",
        "## 版本计数",
        "",
        f"- `index_version_count`: `{summary['index_version_count']}`",
        f"- `active_count`: `{summary['active_count']}`",
        f"- `inactive_count`: `{summary['inactive_count']}`",
        f"- `candidate_count`: `{summary['candidate_count']}`",
        f"- `rollback_target_count`: `{summary['rollback_target_count']}`",
        "",
        "## 当前 active 版本",
        "",
        _version_line(_ensure_dict(active_version)) if active_version else "- 无 active 版本",
        "",
        "## 可回滚目标",
        "",
        *(_version_line(_ensure_dict(item)) for item in rollback_targets),
        *(["- 无"] if not rollback_targets else []),
        "",
        "## 全部版本",
        "",
        *(_version_line(_ensure_dict(item)) for item in versions),
        *(["- 无"] if not versions else []),
        "",
    ]
    return "\n".join(lines)


def _stdout_summary(report: dict[str, object]) -> dict[str, object]:
    summary = _ensure_dict(report["summary"])
    return {
        "status": report["status"],
        "safe_to_execute_rollback_rehearsal": report["safe_to_execute_rollback_rehearsal"],
        "blocking_reasons": report["blocking_reasons"],
        "active_count": summary["active_count"],
        "inactive_count": summary["inactive_count"],
        "rollback_target_count": summary["rollback_target_count"],
    }


def _version_from_mapping(value: object) -> IndexVersion:
    if not isinstance(value, dict):
        raise ValueError("version row must be an object")
    return IndexVersion(
        version_key=_required_str(value, "version_key"),
        status=_required_str(value, "status"),
        vector_provider=_optional_str(value.get("vector_provider")),
        vector_model=_optional_str(value.get("vector_model")),
        document_count=_int_value(value.get("document_count")),
        chunk_count=_int_value(value.get("chunk_count")),
        created_at=_optional_str(value.get("created_at")),
        activated_at=_optional_str(value.get("activated_at")),
    )


def _version_from_row(row: tuple[object, ...]) -> IndexVersion:
    return IndexVersion(
        version_key=str(row[0]),
        status=str(row[1]),
        vector_provider=_optional_str(row[2]),
        vector_model=_optional_str(row[3]),
        document_count=_int_value(row[4]),
        chunk_count=_int_value(row[5]),
        created_at=_optional_str(row[6]),
        activated_at=_optional_str(row[7]),
    )


def _version_line(version: dict[str, object]) -> str:
    return (
        f"- `{version['version_key']}` "
        f"status=`{version['status']}` "
        f"provider=`{version['vector_provider']}` "
        f"model=`{version['vector_model']}` "
        f"documents=`{version['document_count']}` "
        f"chunks=`{version['chunk_count']}`"
    )


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+psycopg://"):
        return database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    return database_url


def _required_str(row: dict[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing required string: {key}")
    return value


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    return 0


def _ensure_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"expected dict, got {type(value).__name__}")
    return value


def _ensure_list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise TypeError(f"expected list, got {type(value).__name__}")
    return value


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


if __name__ == "__main__":
    raise SystemExit(main())
