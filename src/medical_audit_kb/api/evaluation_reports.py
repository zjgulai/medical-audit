from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from medical_audit_kb.api.app import ApiState

EVALUATION_REPORT_EXPORT_PATH = "/index/evaluation/latest/export"
EVALUATION_HISTORY_PATH = "/index/evaluation/history"

_CREATE_EVALUATION_HISTORY_TABLE_SQL = """
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE IF NOT EXISTS index_evaluation_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL UNIQUE,
    status text NOT NULL,
    report_path text NOT NULL,
    retrieval_case_count integer NOT NULL DEFAULT 0,
    answer_case_count integer NOT NULL DEFAULT 0,
    ui_smoke_success boolean NOT NULL DEFAULT false,
    search_backend text NOT NULL,
    search_backend_details jsonb NOT NULL DEFAULT '{}'::jsonb,
    request jsonb NOT NULL DEFAULT '{}'::jsonb,
    report jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_index_evaluation_runs_retrieval_case_count_non_negative
        CHECK (retrieval_case_count >= 0),
    CONSTRAINT ck_index_evaluation_runs_answer_case_count_non_negative
        CHECK (answer_case_count >= 0)
);
CREATE INDEX IF NOT EXISTS idx_index_evaluation_runs_created_at
    ON index_evaluation_runs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_index_evaluation_runs_status
    ON index_evaluation_runs (status);
"""

_UPSERT_EVALUATION_HISTORY_SQL = """
INSERT INTO index_evaluation_runs (
    run_id,
    status,
    report_path,
    retrieval_case_count,
    answer_case_count,
    ui_smoke_success,
    search_backend,
    search_backend_details,
    request,
    report
) VALUES (
    %(run_id)s,
    %(status)s,
    %(report_path)s,
    %(retrieval_case_count)s,
    %(answer_case_count)s,
    %(ui_smoke_success)s,
    %(search_backend)s,
    %(search_backend_details)s,
    %(request)s,
    %(report)s
)
ON CONFLICT (run_id) DO UPDATE SET
    status = EXCLUDED.status,
    report_path = EXCLUDED.report_path,
    retrieval_case_count = EXCLUDED.retrieval_case_count,
    answer_case_count = EXCLUDED.answer_case_count,
    ui_smoke_success = EXCLUDED.ui_smoke_success,
    search_backend = EXCLUDED.search_backend,
    search_backend_details = EXCLUDED.search_backend_details,
    request = EXCLUDED.request,
    report = EXCLUDED.report;
"""

_LIST_EVALUATION_HISTORY_SQL = """
SELECT
    run_id::text,
    status,
    report_path,
    retrieval_case_count,
    answer_case_count,
    ui_smoke_success,
    search_backend,
    report ->> 'generated_at' AS generated_at,
    created_at
FROM index_evaluation_runs
ORDER BY created_at DESC
LIMIT %(limit)s;
"""


def persist_evaluation_report(
    state: ApiState,
    *,
    payload: BaseModel,
    result: dict[str, object],
    search_backend: dict[str, object],
) -> dict[str, object]:
    run_id = str(uuid4())
    now = datetime.now(UTC).replace(microsecond=0)
    generated_at = now.isoformat()
    report_dir = evaluation_report_dir(state)
    report_dir.mkdir(parents=True, exist_ok=True)
    filename_timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    report_path = report_dir / f"index-evaluation-run-{filename_timestamp}-{run_id}.json"
    metadata: dict[str, object] = {
        "run_id": run_id,
        "generated_at": generated_at,
        "path": str(report_path),
        "download_path": EVALUATION_REPORT_EXPORT_PATH,
        "history_path": EVALUATION_HISTORY_PATH,
    }
    report = {
        **result,
        "run_id": run_id,
        "generated_at": generated_at,
        "request": payload.model_dump(mode="json"),
        "search_backend": search_backend,
        "report": metadata,
    }
    _write_report_json(report_path, report)
    history = persist_evaluation_history(state, report)
    metadata["history"] = history
    report["history"] = history
    _write_report_json(report_path, report)
    return metadata


def persist_evaluation_history(
    state: ApiState,
    report: dict[str, object],
) -> dict[str, object]:
    if state.search_backend != "postgres":
        return {
            "backend": "postgres",
            "persisted": False,
            "reason": "search backend is not postgres",
        }

    try:
        with (
            psycopg.connect(
                _normalize_psycopg_database_url(state.settings.database_url),
                connect_timeout=2,
            ) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(_CREATE_EVALUATION_HISTORY_TABLE_SQL)
            cursor.execute(_UPSERT_EVALUATION_HISTORY_SQL, _history_row(report))
            connection.commit()
    except psycopg.Error as exc:
        return {
            "backend": "postgres",
            "persisted": False,
            "error": str(exc),
        }

    return {
        "backend": "postgres",
        "persisted": True,
        "table": "index_evaluation_runs",
        "run_id": str(report.get("run_id", "unknown")),
    }


def list_evaluation_history(state: ApiState, *, limit: int = 20) -> list[dict[str, object]]:
    try:
        with (
            psycopg.connect(
                _normalize_psycopg_database_url(state.settings.database_url),
                connect_timeout=2,
                row_factory=dict_row,
            ) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(_CREATE_EVALUATION_HISTORY_TABLE_SQL)
            cursor.execute(_LIST_EVALUATION_HISTORY_SQL, {"limit": limit})
            rows = cursor.fetchall()
    except psycopg.Error:
        return list_evaluation_report_files(state, limit=limit)

    return [_history_item(row, source="postgres") for row in rows]


def latest_evaluation_report(state: ApiState) -> dict[str, object] | None:
    report_dir = evaluation_report_dir(state)
    if not report_dir.exists():
        return None
    report_paths = sorted(report_dir.glob("index-evaluation-run-*.json"), reverse=True)
    if not report_paths:
        return None
    payload = json.loads(report_paths[0].read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"evaluation report root must be an object: {report_paths[0]}")
    return payload


def list_evaluation_report_files(state: ApiState, *, limit: int = 20) -> list[dict[str, object]]:
    report_dir = evaluation_report_dir(state)
    if not report_dir.exists():
        return []
    items: list[dict[str, object]] = []
    for report_path in sorted(report_dir.glob("index-evaluation-run-*.json"), reverse=True)[:limit]:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            items.append(_file_history_item(payload, report_path))
    return items


def evaluation_report_dir(state: ApiState) -> Path:
    return state.settings.index_root / "evaluation-runs"


def _write_report_json(report_path: Path, report: dict[str, object]) -> None:
    temp_path = report_path.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(report_path)


def _history_row(report: dict[str, object]) -> dict[str, object]:
    report_metadata = _object_value(report, "report")
    search_backend = _object_value(report, "search_backend")
    return {
        "run_id": str(report.get("run_id", "")),
        "status": str(report.get("status", "unknown")),
        "report_path": str(report_metadata.get("path", "")),
        "retrieval_case_count": _case_count(report, "retrieval"),
        "answer_case_count": _case_count(report, "answer"),
        "ui_smoke_success": _ui_smoke_success(report),
        "search_backend": str(search_backend.get("backend", "unknown")),
        "search_backend_details": Jsonb(_object_value(search_backend, "details")),
        "request": Jsonb(_object_value(report, "request")),
        "report": Jsonb(report),
    }


def _history_item(row: dict[str, object], *, source: str) -> dict[str, object]:
    created_at = row.get("created_at")
    return {
        "run_id": str(row.get("run_id", "")),
        "status": str(row.get("status", "unknown")),
        "generated_at": str(row.get("generated_at") or _isoformat(created_at)),
        "retrieval_case_count": _int_value(row.get("retrieval_case_count")),
        "answer_case_count": _int_value(row.get("answer_case_count")),
        "ui_smoke_success": bool(row.get("ui_smoke_success")),
        "report_path": str(row.get("report_path", "")),
        "download_path": EVALUATION_REPORT_EXPORT_PATH,
        "source": source,
    }


def _file_history_item(report: dict[str, object], report_path: Path) -> dict[str, object]:
    report_metadata = _object_value(report, "report")
    return {
        "run_id": str(report.get("run_id", report_metadata.get("run_id", ""))),
        "status": str(report.get("status", "unknown")),
        "generated_at": str(report.get("generated_at", report_metadata.get("generated_at", ""))),
        "retrieval_case_count": _case_count(report, "retrieval"),
        "answer_case_count": _case_count(report, "answer"),
        "ui_smoke_success": _ui_smoke_success(report),
        "report_path": str(report_metadata.get("path", report_path)),
        "download_path": EVALUATION_REPORT_EXPORT_PATH,
        "source": "json",
    }


def _case_count(report: dict[str, object], key: str) -> int:
    section = _object_value(report, key)
    value = section.get("case_count")
    return value if isinstance(value, int) else 0


def _int_value(value: object) -> int:
    return value if isinstance(value, int) else 0


def _ui_smoke_success(report: dict[str, object]) -> bool:
    return bool(_object_value(report, "ui_smoke").get("success"))


def _object_value(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _isoformat(value: object) -> str:
    return value.isoformat() if isinstance(value, datetime) else ""


def _normalize_psycopg_database_url(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)
