#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "https://audit.lute-tlz-dddd.top"
DEFAULT_REPORT = "tmp/outputs/production-documents-readonly-latest.json"
DEFAULT_USER_ID = "production-documents-readonly-probe"
EXPECTED_DOCUMENTS_TEXT = (
    "AI智能审计管理系统",
    "材料与知识库统一检索",
    "个人材料",
)
SKIPPED_AUDIT_LOG_WRITING_ENDPOINTS = (
    "/api/v1/documents/uploads",
    "/api/v1/documents/uploads/{upload_id}/download",
)


class ReadOnlyProbeError(RuntimeError):
    pass


@dataclass(frozen=True)
class HttpResponse:
    status: int
    url: str
    content: bytes
    headers: dict[str, str]


def main() -> int:
    args = _parse_args()
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = _run_probe(
        base_url=str(args.base_url),
        timeout_seconds=float(args.timeout_seconds),
        user_id=str(args.user_id),
        role=str(args.role),
        min_matching_embeddings=int(args.min_matching_embeddings),
    )
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a production /documents read-only probe. The probe intentionally avoids "
            "document upload list and download-metadata endpoints because they write audit logs."
        )
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--role", default="auditor")
    parser.add_argument(
        "--min-matching-embeddings",
        type=int,
        default=1,
        help="Minimum acceptable active PostgreSQL embedding count.",
    )
    parser.add_argument("--report", default=DEFAULT_REPORT)
    return parser.parse_args()


def _run_probe(
    *,
    base_url: str,
    timeout_seconds: float,
    user_id: str,
    role: str,
    min_matching_embeddings: int,
    http_get: Callable[[str, dict[str, str], float], HttpResponse] | None = None,
) -> dict[str, Any]:
    selected_http_get = http_get or _http_get
    normalized_base_url = base_url.rstrip("/")
    started_at = _now_iso()
    steps: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}

    _run_step(
        steps,
        "documents-page-html",
        lambda: _check_documents_page(
            normalized_base_url,
            timeout_seconds=timeout_seconds,
            http_get=selected_http_get,
        ),
    )
    permissions_details = _run_step(
        steps,
        "documents-permissions",
        lambda: _check_documents_permissions(
            normalized_base_url,
            timeout_seconds=timeout_seconds,
            user_id=user_id,
            role=role,
            http_get=selected_http_get,
        ),
    )
    summary["documents_role"] = permissions_details["role"]
    summary["source_collection_count"] = permissions_details["source_collection_count"]
    summary["can_upload_personal"] = permissions_details["can_upload_personal"]
    summary["can_read_all_personal_uploads"] = permissions_details[
        "can_read_all_personal_uploads"
    ]

    health_details = _run_step(
        steps,
        "backend-health",
        lambda: _check_backend_health(
            normalized_base_url,
            timeout_seconds=timeout_seconds,
            http_get=selected_http_get,
        ),
    )
    summary["backend_health"] = health_details["status"]
    search_details = _run_step(
        steps,
        "backend-search-backend",
        lambda: _check_search_backend(
            normalized_base_url,
            timeout_seconds=timeout_seconds,
            min_matching_embeddings=min_matching_embeddings,
            http_get=selected_http_get,
        ),
    )
    summary["search_backend_ready"] = search_details["ready"]
    summary["matching_embedding_count"] = search_details["matching_embedding_count"]

    return {
        "status": "pass" if all(step["passed"] for step in steps) else "fail",
        "base_url": normalized_base_url,
        "started_at": started_at,
        "finished_at": _now_iso(),
        "boundaries": {
            "production_write": False,
            "document_upload_write": False,
            "document_upload_list_api_called": False,
            "download_metadata_api_called": False,
            "audit_log_write_expected": False,
            "provider_call": False,
            "browser_js_executed": False,
            "skipped_audit_log_writing_endpoints": list(SKIPPED_AUDIT_LOG_WRITING_ENDPOINTS),
        },
        "summary": summary,
        "steps": steps,
    }


def _run_step(
    steps: list[dict[str, Any]],
    name: str,
    callback: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    started = time.time()
    try:
        details = callback()
    except Exception as exc:
        details = {"error": str(exc)}
        steps.append(
            {
                "name": name,
                "passed": False,
                "duration_ms": round((time.time() - started) * 1000),
                "details": details,
            }
        )
        return details
    steps.append(
        {
            "name": name,
            "passed": True,
            "duration_ms": round((time.time() - started) * 1000),
            "details": details,
        }
    )
    return details


def _check_documents_page(
    base_url: str,
    *,
    timeout_seconds: float,
    http_get: Callable[[str, dict[str, str], float], HttpResponse],
) -> dict[str, Any]:
    response = http_get(
        f"{base_url}/documents",
        {"Accept": "text/html"},
        timeout_seconds,
    )
    _require(response.status == 200, f"/documents returned {response.status}")
    expected_text = {
        text: text.encode("utf-8") in response.content for text in EXPECTED_DOCUMENTS_TEXT
    }
    _require(all(expected_text.values()), f"/documents missing expected text: {expected_text}")
    return {
        "url": response.url,
        "status_code": response.status,
        "content_type": _header(response, "content-type"),
        "content_length": len(response.content),
        "expected_utf8_text": expected_text,
        "assertion_mode": "utf8-bytes-because-response-may-not-declare-charset",
    }


def _check_documents_permissions(
    base_url: str,
    *,
    timeout_seconds: float,
    user_id: str,
    role: str,
    http_get: Callable[[str, dict[str, str], float], HttpResponse],
) -> dict[str, Any]:
    payload = _request_json(
        f"{base_url}/api/v1/documents/permissions",
        {
            "Accept": "application/json",
            "X-Role": role,
            "X-User-Id": user_id,
        },
        timeout_seconds,
        http_get=http_get,
    )
    upload_permissions = _dict(payload.get("upload_permissions"), "upload_permissions")
    source_collections = _list(payload.get("source_collections"), "source_collections")
    _require(payload.get("role") == role, f"role mismatch: {payload.get('role')}")
    _require(bool(source_collections), "source_collections should not be empty")
    _require(
        upload_permissions.get("can_upload_personal") is True,
        "auditor should be able to upload personal documents",
    )
    _require(
        upload_permissions.get("can_read_all_personal_uploads") is False,
        "auditor should not have read-all personal upload access",
    )
    return {
        "role": payload.get("role"),
        "source_collection_count": len(source_collections),
        "can_upload_personal": upload_permissions.get("can_upload_personal"),
        "can_read_all_personal_uploads": upload_permissions.get(
            "can_read_all_personal_uploads"
        ),
    }


def _check_backend_health(
    base_url: str,
    *,
    timeout_seconds: float,
    http_get: Callable[[str, dict[str, str], float], HttpResponse],
) -> dict[str, Any]:
    payload = _request_json(
        f"{base_url}/api/backend/health",
        {"Accept": "application/json"},
        timeout_seconds,
        http_get=http_get,
    )
    _require(payload.get("status") == "ok", f"backend health is {payload.get('status')}")
    return {"status": payload.get("status"), "version": payload.get("version")}


def _check_search_backend(
    base_url: str,
    *,
    timeout_seconds: float,
    min_matching_embeddings: int,
    http_get: Callable[[str, dict[str, str], float], HttpResponse],
) -> dict[str, Any]:
    payload = _request_json(
        f"{base_url}/api/backend/index/search-backend",
        {"Accept": "application/json"},
        timeout_seconds,
        http_get=http_get,
    )
    details = _dict(payload.get("details"), "search backend details")
    matching_embedding_count = _int(
        details.get("matching_embedding_count"),
        "matching_embedding_count",
    )
    _require(payload.get("ready") is True, "search backend should be ready")
    _require(
        matching_embedding_count >= min_matching_embeddings,
        (
            "matching_embedding_count below minimum: "
            f"{matching_embedding_count} < {min_matching_embeddings}"
        ),
    )
    return {
        "backend": payload.get("backend"),
        "ready": payload.get("ready"),
        "matching_embedding_count": matching_embedding_count,
        "embedding_provider": details.get("embedding_provider"),
    }


def _request_json(
    url: str,
    headers: dict[str, str],
    timeout_seconds: float,
    *,
    http_get: Callable[[str, dict[str, str], float], HttpResponse],
) -> dict[str, Any]:
    response = http_get(url, headers, timeout_seconds)
    _require(response.status == 200, f"{url} returned {response.status}")
    try:
        payload = json.loads(response.content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReadOnlyProbeError(f"{url} did not return valid JSON: {exc}") from exc
    return _dict(payload, "JSON response")


def _http_get(url: str, headers: dict[str, str], timeout_seconds: float) -> HttpResponse:
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return HttpResponse(
                status=response.status,
                url=response.geturl(),
                content=response.read(),
                headers={key.lower(): value for key, value in response.headers.items()},
            )
    except urllib.error.HTTPError as exc:
        return HttpResponse(
            status=exc.code,
            url=url,
            content=exc.read(),
            headers={key.lower(): value for key, value in exc.headers.items()},
        )
    except urllib.error.URLError as exc:
        raise ReadOnlyProbeError(f"GET {url} failed: {exc}") from exc


def _header(response: HttpResponse, name: str) -> str:
    return response.headers.get(name.lower(), "")


def _dict(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReadOnlyProbeError(f"{label} must be an object")
    return value


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ReadOnlyProbeError(f"{label} must be a list")
    return value


def _int(value: object, label: str) -> int:
    if not isinstance(value, int):
        raise ReadOnlyProbeError(f"{label} must be an integer")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReadOnlyProbeError(message)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


if __name__ == "__main__":
    raise SystemExit(main())
