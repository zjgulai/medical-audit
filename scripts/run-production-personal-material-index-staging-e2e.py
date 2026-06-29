#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

DEFAULT_BASE_URL = "https://audit.lute-tlz-dddd.top"
DEFAULT_API_PREFIX = "/api/v1"
DEFAULT_REPORT = "tmp/outputs/production-personal-material-index-staging-e2e-latest.json"
DEFAULT_READINESS_REPORT = "tmp/outputs/production-personal-material-indexing-readiness-latest.json"
DEFAULT_TENANT_ID = "hospital-demo"
DEFAULT_PROJECT_KEY = "SELF-CHECK-FUND-20260607"
PRODUCTION_HOST = "audit.lute-tlz-dddd.top"


class StagingE2EError(RuntimeError):
    pass


def main() -> int:
    args = _parse_args()
    base_url = str(args.base_url).rstrip("/")
    _require_production_write_confirmation(
        base_url=base_url,
        confirm_production_write=str(args.confirm_production_write),
    )
    api_prefix = "/" + str(args.api_prefix).strip("/")
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    run_id = str(args.run_id) if args.run_id else _utc_stamp()
    timeout_seconds = float(args.timeout_seconds)
    upload_ids = _selected_upload_ids(
        readiness_report=Path(args.readiness_report),
        explicit_upload_ids=tuple(str(item) for item in args.upload_id),
        max_uploads=int(args.max_uploads),
    )
    actor_headers = _actor_headers(
        user_id=str(args.user_id) or f"personal-index-head-{run_id}",
        role=str(args.role),
        tenant_id=str(args.tenant_id),
        project_key=str(args.project_key),
    )
    session = requests.Session()
    steps: list[dict[str, object]] = []
    started_at = _now_iso()

    def run_step(name: str, callback: Callable[[], dict[str, object]]) -> dict[str, object]:
        step_started = time.time()
        try:
            details = callback()
            entry = {
                "name": name,
                "passed": True,
                "duration_ms": round((time.time() - step_started) * 1000),
                "details": details,
            }
            steps.append(entry)
            return details
        except Exception as exc:
            entry = {
                "name": name,
                "passed": False,
                "duration_ms": round((time.time() - step_started) * 1000),
                "error": str(exc),
            }
            steps.append(entry)
            raise

    def api_url(path: str) -> str:
        return f"{base_url}{api_prefix}{path}"

    def request_json(method: str, path: str) -> tuple[requests.Response, dict[str, object]]:
        response = session.request(
            method,
            api_url(path),
            headers=actor_headers,
            timeout=timeout_seconds,
        )
        try:
            payload: object = response.json()
        except ValueError:
            payload = {
                "content_type": response.headers.get("content-type", ""),
                "raw_text_prefix": response.text[:500],
            }
        if not isinstance(payload, dict):
            payload = {"payload": payload}
        return response, payload

    def ingest_upload(upload_id: str) -> dict[str, object]:
        response, payload = request_json(
            "POST",
            f"/documents/uploads/{upload_id}/index-ingestion",
        )
        _require(
            response.status_code == 200,
            f"index ingestion returned {response.status_code}: {payload}",
        )
        item = _dict(payload.get("item"), "item")
        ingestion = _dict(payload.get("ingestion"), "ingestion")
        _require(item.get("id") == upload_id, f"unexpected upload id: {item.get('id')}")
        _require(
            item.get("index_status") == "staged-for-index",
            f"upload is not staged-for-index: {item.get('index_status')}",
        )
        _require(
            ingestion.get("status") in {"staged-for-index", "already-staged"},
            f"unexpected ingestion status: {ingestion.get('status')}",
        )
        _require(
            ingestion.get("source_collection") == "personal-materials",
            f"unexpected source_collection: {ingestion.get('source_collection')}",
        )
        _require(
            ingestion.get("index_version_status") == "candidate",
            f"unexpected index_version_status: {ingestion.get('index_version_status')}",
        )
        _require(
            _int(ingestion.get("chunk_count")) > 0,
            f"chunk_count is not positive: {ingestion.get('chunk_count')}",
        )
        _require(
            _int(ingestion.get("embedding_count")) == _int(ingestion.get("chunk_count")),
            "embedding_count must equal chunk_count",
        )
        _require(
            ingestion.get("external_provider_call_performed") is False,
            "index ingestion must not call an external embedding provider",
        )
        _require(
            ingestion.get("live_retrieval_activated") is False,
            "candidate staging must not activate live retrieval",
        )
        return {
            "status_code": response.status_code,
            "upload_id": upload_id,
            "index_status": item.get("index_status"),
            "ingestion": ingestion,
            "store_backend": _dict(payload.get("store"), "store").get("backend"),
        }

    status = "pass"
    error: str | None = None
    try:
        _require(upload_ids, "no upload ids selected for staging")
        for upload_id in upload_ids:
            run_step(
                f"index-ingestion:{upload_id}",
                lambda upload_id=upload_id: ingest_upload(upload_id),
            )
    except Exception as exc:
        status = "fail"
        error = str(exc)

    report = {
        "status": status,
        "base_url": base_url,
        "api_prefix": api_prefix,
        "started_at": started_at,
        "finished_at": _now_iso(),
        "run_id": run_id,
        "upload_ids": upload_ids,
        "auth_context": {
            "tenant_id": str(args.tenant_id),
            "project_key": str(args.project_key),
            "role": str(args.role),
        },
        "boundaries": {
            "production_write": True,
            "api_write": True,
            "db_write": True,
            "index_ingestion_triggered": True,
            "external_provider_call": False,
            "index_activate_executed": False,
            "search_backend_reload_executed": False,
            "active_retrieval_activated": False,
        },
        "steps": steps,
    }
    if error is not None:
        report["error"] = error
    _write_report(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status == "pass" else 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run production personal-material candidate index staging E2E for already "
            "approved ready uploads. This writes candidate staging metadata and embeddings, "
            "but does not activate retrieval."
        )
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-prefix", default=DEFAULT_API_PREFIX)
    parser.add_argument("--readiness-report", default=DEFAULT_READINESS_REPORT)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--upload-id", action="append", default=[])
    parser.add_argument("--max-uploads", type=int, default=10)
    parser.add_argument(
        "--confirm-production-write",
        default="",
        help=f"Required as {PRODUCTION_HOST} when --base-url targets production.",
    )
    parser.add_argument("--tenant-id", default=DEFAULT_TENANT_ID)
    parser.add_argument("--project-key", default=DEFAULT_PROJECT_KEY)
    parser.add_argument("--user-id", default="")
    parser.add_argument("--role", default="department-head")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    return parser.parse_args()


def _selected_upload_ids(
    *,
    readiness_report: Path,
    explicit_upload_ids: tuple[str, ...],
    max_uploads: int,
) -> list[str]:
    explicit = [item.strip() for item in explicit_upload_ids if item.strip()]
    if explicit:
        return explicit[:max(1, max_uploads)]
    payload = json.loads(readiness_report.read_text(encoding="utf-8"))
    remote = _dict(payload.get("remote"), "remote")
    indexing = _dict(remote.get("document_upload_indexing"), "indexing")
    db_state = _dict(indexing.get("db"), "db")
    samples = db_state.get("ready_not_indexed_samples") or []
    if not isinstance(samples, list):
        raise StagingE2EError("ready_not_indexed_samples is not a list")
    upload_ids = [
        str(_dict(sample, "ready sample").get("upload_key") or "").strip()
        for sample in samples
    ]
    return [item for item in upload_ids if item][:max(1, max_uploads)]


def _actor_headers(
    *,
    user_id: str,
    role: str,
    tenant_id: str,
    project_key: str,
) -> dict[str, str]:
    return {
        "X-User-Id": user_id,
        "X-Role": role,
        "X-Project-Key": project_key,
        "X-Tenant-Id": tenant_id,
    }


def _require_production_write_confirmation(
    *,
    base_url: str,
    confirm_production_write: str,
) -> None:
    if _is_production_base_url(base_url) and confirm_production_write != PRODUCTION_HOST:
        raise StagingE2EError(
            "production personal-material index staging requires "
            f"--confirm-production-write {PRODUCTION_HOST}"
        )


def _is_production_base_url(base_url: str) -> bool:
    return (urlparse(base_url).hostname or "").lower() == PRODUCTION_HOST


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _write_report(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _require(condition: object, message: str) -> None:
    if not condition:
        raise StagingE2EError(message)


def _dict(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise StagingE2EError(f"{label} is not an object")
    return value


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


if __name__ == "__main__":
    raise SystemExit(main())
