#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode, urlparse

import requests

DEFAULT_BASE_URL = "https://audit.lute-tlz-dddd.top"
DEFAULT_API_PREFIX = "/api/v1"
DEFAULT_REPORT = "tmp/outputs/production-documents-clamav-sidecar-write-e2e-latest.json"
PRODUCTION_HOST = "audit.lute-tlz-dddd.top"


class E2EError(RuntimeError):
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
    session = requests.Session()
    steps: list[dict[str, object]] = []
    upload_id: str | None = None
    started_at = _now_iso()

    fixture_name = f"production-documents-clamav-sidecar-e2e-{run_id}.txt"
    fixture_bytes = (
        b"Production ClamAV sidecar clean upload E2E fixture.\n"
        b"This file contains no malware markers and must remain blocked only by DLP/manual gates.\n"
    )
    fixture_sha256 = hashlib.sha256(fixture_bytes).hexdigest()
    actor_suffix = run_id.replace(":", "").replace("+", "").replace(".", "").replace("-", "")
    auditor_headers = {
        "X-User-Id": f"clamav-sidecar-owner-{actor_suffix}",
        "X-Role": "auditor",
    }
    head_headers = {
        "X-User-Id": f"clamav-sidecar-head-{actor_suffix}",
        "X-Role": "department-head",
    }
    admin_headers = {
        "X-User-Id": f"clamav-sidecar-admin-{actor_suffix}",
        "X-Role": "system-admin",
    }

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

    def request_json(
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        **kwargs: object,
    ) -> tuple[requests.Response, dict[str, object]]:
        response = session.request(
            method,
            api_url(path),
            headers=headers or {},
            timeout=timeout_seconds,
            **kwargs,
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

    def upload_fixture() -> dict[str, object]:
        response, payload = request_json(
            "POST",
            "/documents/uploads",
            headers=auditor_headers,
            files={"file": (fixture_name, fixture_bytes, "text/plain")},
        )
        _require(response.status_code == 200, f"upload returned {response.status_code}: {payload}")
        item = _dict(payload.get("item"), "upload item")
        nonlocal upload_id
        upload_id = _text(item.get("id"), "upload id")
        readiness = _dict(item.get("index_readiness"), "index_readiness")
        blockers = _list(readiness.get("blockers"), "blockers")
        checks = _checks_by_type(readiness)
        virus_check = _dict(checks.get("virus-scan"), "virus-scan check")
        dlp_check = _dict(checks.get("dlp-review"), "dlp-review check")
        manual_check = _dict(checks.get("manual-index-approval"), "manual-index-approval check")

        _require(readiness.get("status") == "blocked", "new upload should remain blocked")
        _require("virus-scan-required" not in blockers, "virus-scan blocker should be cleared")
        _require("dlp-review-required" in blockers, "missing DLP blocker")
        _require(
            "manual-index-approval-required" in blockers,
            "missing manual approval blocker",
        )
        _require(virus_check.get("provider") == "clamav-sidecar", "virus provider mismatch")
        _require(virus_check.get("status") == "passed", "virus check should pass")
        _require(virus_check.get("blocker") is None, "virus check should not block")
        _require(
            virus_check.get("detail") == "clamav-sidecar found no malware",
            "virus detail mismatch",
        )
        _require(virus_check.get("result_code") == "clean", "virus result_code mismatch")
        _require(dlp_check.get("provider") == "unconfigured", "DLP provider mismatch")
        _require(dlp_check.get("status") == "blocked", "DLP should remain blocked")
        _require(dlp_check.get("blocker") == "dlp-review-required", "DLP blocker mismatch")
        _require(manual_check.get("status") == "blocked", "manual approval should remain blocked")
        _require(
            manual_check.get("blocker") == "manual-index-approval-required",
            "manual approval blocker mismatch",
        )
        return {
            "status_code": response.status_code,
            "upload_id": upload_id,
            "file_name": item.get("name"),
            "file_sha256": fixture_sha256,
            "created_by": item.get("created_by"),
            "index_status": item.get("index_status"),
            "readiness_status": readiness.get("status"),
            "next_action": readiness.get("next_action"),
            "blockers": blockers,
            "check_statuses": _check_statuses(readiness),
            "store_backend": _dict(payload.get("store"), "store").get("backend"),
            "governance_job_count": _dict(payload.get("store"), "store").get(
                "governance_job_count"
            ),
        }

    def verify_download_metadata() -> dict[str, object]:
        uid = _upload_id(upload_id)
        response, payload = request_json(
            "GET",
            f"/documents/uploads/{uid}/download",
            headers=auditor_headers,
        )
        _require(
            response.status_code == 200,
            f"download metadata returned {response.status_code}: {payload}",
        )
        download = _dict(payload.get("download"), "download")
        storage_objects = _list(download.get("storage_objects"), "storage_objects")
        _require(storage_objects, "download metadata should include storage objects")
        object_summaries = []
        for item in storage_objects:
            storage_object = _dict(item, "storage object")
            _require(storage_object.get("sha256") == fixture_sha256, "storage object sha mismatch")
            _require(
                storage_object.get("storage_status") in {"object-stored", "local-quarantine"},
                "unexpected storage status",
            )
            object_summaries.append(
                {
                    "provider": storage_object.get("provider"),
                    "bucket": storage_object.get("bucket"),
                    "region": storage_object.get("region"),
                    "storage_status": storage_object.get("storage_status"),
                    "size_bytes": storage_object.get("size_bytes"),
                    "sha256": storage_object.get("sha256"),
                    "object_key_present": bool(storage_object.get("object_key")),
                    "object_version_present": bool(storage_object.get("object_version")),
                    "etag_present": bool(storage_object.get("etag")),
                    "encryption_mode": storage_object.get("encryption_mode"),
                }
            )
        return {
            "upload_id": uid,
            "status_code": response.status_code,
            "download_status": download.get("status"),
            "delivery": download.get("delivery"),
            "reason": download.get("reason"),
            "signed_url_issued": bool(download.get("signed_url")),
            "storage_object_count": len(storage_objects),
            "storage_objects": object_summaries,
        }

    def verify_visibility_and_persistence() -> dict[str, object]:
        uid = _upload_id(upload_id)
        owner_item = _list_contains_upload(
            request_json("GET", "/documents/uploads?limit=100", headers=auditor_headers),
            uid,
            "owner list",
        )
        head_item = _list_contains_upload(
            request_json("GET", "/documents/uploads?limit=100", headers=head_headers),
            uid,
            "department-head list",
        )
        for label, item in {"owner": owner_item, "department_head": head_item}.items():
            readiness = _dict(item.get("index_readiness"), f"{label} readiness")
            blockers = _list(readiness.get("blockers"), f"{label} blockers")
            _require(readiness.get("status") == "blocked", f"{label} list did not persist blocked")
            _require("virus-scan-required" not in blockers, f"{label} virus blocker persisted")
            _require("dlp-review-required" in blockers, f"{label} missing DLP blocker")
            _require(
                "manual-index-approval-required" in blockers,
                f"{label} missing manual blocker",
            )
        return {
            "upload_id": uid,
            "owner_visible": True,
            "department_head_visible": True,
            "owner_check_statuses": _check_statuses(
                _dict(owner_item.get("index_readiness"), "owner readiness")
            ),
            "department_head_check_statuses": _check_statuses(
                _dict(head_item.get("index_readiness"), "department-head readiness")
            ),
        }

    def verify_audit_logs() -> dict[str, object]:
        uid = _upload_id(upload_id)
        expected_actions = {
            "document-upload": {"minimum_count": 1, "must_reference_upload": True},
            "document-upload-download-metadata": {
                "minimum_count": 1,
                "must_reference_upload": True,
            },
            "document-upload-list": {"minimum_count": 2, "must_reference_upload": False},
        }
        action_results: dict[str, object] = {}
        for action, expectation in expected_actions.items():
            query = urlencode({"action": action, "limit": 100})
            response, payload = request_json("GET", f"/audit/logs?{query}", headers=admin_headers)
            _require(
                response.status_code == 200,
                f"audit logs {action} returned {response.status_code}: {payload}",
            )
            items = _list(payload.get("items"), f"audit log items for {action}")
            minimum_count = int(expectation["minimum_count"])
            must_reference_upload = bool(expectation["must_reference_upload"])
            matched = (
                [item for item in items if uid in json.dumps(item, ensure_ascii=False)]
                if must_reference_upload
                else items
            )
            _require(
                len(matched) >= minimum_count,
                f"audit logs missing {action} for {uid}: matched {len(matched)}",
            )
            action_results[action] = {
                "matched_count": len(matched),
                "must_reference_upload": must_reference_upload,
                "store_ready": _dict(payload.get("store"), "store").get("ready"),
                "backend": _dict(payload.get("store"), "store").get("backend"),
            }
        return {"upload_id": uid, "actions": action_results}

    status = "pass"
    error: str | None = None
    try:
        run_step("upload-clean-document-and-run-clamav-sidecar", upload_fixture)
        run_step("download-metadata-storage-object-recorded", verify_download_metadata)
        run_step(
            "list-persistence-keeps-only-dlp-and-manual-blockers",
            verify_visibility_and_persistence,
        )
        if not args.skip_audit_log_check:
            run_step("audit-log-events-recorded", verify_audit_logs)
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
        "upload_id": upload_id,
        "fixture": {"file_name": fixture_name, "sha256": fixture_sha256},
        "boundaries": {
            "production_write": _is_production_base_url(base_url),
            "document_upload_write": True,
            "object_storage_write": True,
            "real_clamav_sidecar_scan": True,
            "external_governance_provider_call": False,
            "external_dlp_provider_call": False,
            "manual_index_approval_writeback": False,
            "indexing_triggered": False,
        },
        "actors": {
            "upload_actor_role": "auditor",
            "read_all_actor_role": "department-head",
            "audit_log_actor_role": "system-admin",
        },
        "steps": steps,
        "error": error,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status == "pass" else 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a /documents write E2E that proves clamav-sidecar clears virus-scan "
            "while DLP/manual blockers still prevent indexing."
        )
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-prefix", default=DEFAULT_API_PREFIX)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--skip-audit-log-check", action="store_true")
    parser.add_argument(
        "--confirm-production-write",
        default="",
        help=(
            "Required when --base-url targets audit.lute-tlz-dddd.top. "
            "Pass audit.lute-tlz-dddd.top to acknowledge a production upload/object write."
        ),
    )
    return parser.parse_args()


def _require_production_write_confirmation(
    *,
    base_url: str,
    confirm_production_write: str,
) -> None:
    if _is_production_base_url(base_url) and confirm_production_write != PRODUCTION_HOST:
        raise E2EError(
            "production /documents write requires "
            f"--confirm-production-write {PRODUCTION_HOST}"
        )


def _is_production_base_url(base_url: str) -> bool:
    return (urlparse(base_url).hostname or "").lower() == PRODUCTION_HOST


def _check_statuses(readiness: dict[str, object]) -> dict[str, dict[str, object]]:
    checks = _checks_by_type(readiness)
    result: dict[str, dict[str, object]] = {}
    for check_type, check in checks.items():
        payload = _dict(check, f"{check_type} check")
        result[check_type] = {
            "provider": payload.get("provider"),
            "status": payload.get("status"),
            "blocker": payload.get("blocker"),
            "detail": payload.get("detail"),
            "result_code": payload.get("result_code"),
            "risk_level": payload.get("risk_level"),
        }
    return result


def _checks_by_type(readiness: dict[str, object]) -> dict[str, object]:
    checks = _list(readiness.get("checks"), "checks")
    result: dict[str, object] = {}
    for check in checks:
        check_payload = _dict(check, "check")
        check_type = _text(check_payload.get("check_type"), "check_type")
        result[check_type] = check_payload
    return result


def _list_contains_upload(
    response_payload: tuple[requests.Response, dict[str, object]],
    upload_id: str,
    label: str,
) -> dict[str, object]:
    response, payload = response_payload
    _require(response.status_code == 200, f"{label} returned {response.status_code}: {payload}")
    items = _list(payload.get("items"), f"{label} items")
    for item in items:
        candidate = _dict(item, f"{label} item")
        if candidate.get("id") == upload_id:
            return candidate
    raise E2EError(f"{label} does not contain upload {upload_id}")


def _upload_id(value: str | None) -> str:
    if not value:
        raise E2EError("upload id is not set")
    return value


def _dict(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise E2EError(f"{label} is not an object: {value!r}")
    return value


def _list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise E2EError(f"{label} is not a list: {value!r}")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise E2EError(f"{label} is not text: {value!r}")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise E2EError(message)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    sys.exit(main())
