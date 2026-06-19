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
DEFAULT_REPORT = "tmp/outputs/production-documents-ruleset-dlp-write-e2e-latest.json"
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
    uploads: dict[str, dict[str, object]] = {}
    started_at = _now_iso()

    actor_suffix = run_id.replace(":", "").replace("+", "").replace(".", "").replace("-", "")
    auditor_headers = {
        "X-User-Id": f"ruleset-dlp-owner-{actor_suffix}",
        "X-Role": "auditor",
    }
    head_headers = {
        "X-User-Id": f"ruleset-dlp-head-{actor_suffix}",
        "X-Role": "department-head",
    }
    admin_headers = {
        "X-User-Id": f"ruleset-dlp-admin-{actor_suffix}",
        "X-Role": "system-admin",
    }
    clean_fixture = _fixture(
        label="clean",
        run_id=run_id,
        content=(
            b"Production ruleset-v1 DLP clean upload E2E fixture.\n"
            b"No configured sensitive markers should be present in this file.\n"
        ),
    )
    sensitive_fixture = _fixture(
        label="sensitive",
        run_id=run_id,
        content=(
            "Production ruleset-v1 DLP sensitive upload E2E fixture.\n"
            "患者姓名：测试患者\n"
            "身份证：110105199001011234\n"
            "手机号：13800138000\n"
            "诊断：高血压\n"
        ).encode(),
    )

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

    def upload_and_assert_clean() -> dict[str, object]:
        return _upload_and_assert(
            request_json=request_json,
            headers=auditor_headers,
            fixture=clean_fixture,
            expected_dlp_status="passed",
            expected_dlp_result_code="no-sensitive-marker",
            expected_blockers=["manual-index-approval-required"],
            uploads=uploads,
        )

    def upload_and_assert_sensitive() -> dict[str, object]:
        return _upload_and_assert(
            request_json=request_json,
            headers=auditor_headers,
            fixture=sensitive_fixture,
            expected_dlp_status="blocked",
            expected_dlp_result_code="sensitive-marker-detected",
            expected_blockers=["dlp-review-required", "manual-index-approval-required"],
            uploads=uploads,
        )

    def verify_download_metadata() -> dict[str, object]:
        results: dict[str, object] = {}
        for label, upload in uploads.items():
            uid = _text(upload.get("upload_id"), f"{label} upload id")
            response, payload = request_json(
                "GET",
                f"/documents/uploads/{uid}/download",
                headers=auditor_headers,
            )
            _require(
                response.status_code == 200,
                f"{label} download metadata returned {response.status_code}: {payload}",
            )
            download = _dict(payload.get("download"), f"{label} download")
            storage_objects = _list(download.get("storage_objects"), f"{label} storage_objects")
            _require(storage_objects, f"{label} download metadata should include storage objects")
            object_summaries = []
            for item in storage_objects:
                storage_object = _dict(item, f"{label} storage object")
                _require(
                    storage_object.get("sha256") == upload.get("sha256"),
                    f"{label} storage object sha mismatch",
                )
                _require(
                    storage_object.get("storage_status") in {"object-stored", "local-quarantine"},
                    f"{label} unexpected storage status",
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
                        "etag_present": bool(storage_object.get("etag")),
                        "encryption_mode": storage_object.get("encryption_mode"),
                    }
                )
            results[label] = {
                "upload_id": uid,
                "status_code": response.status_code,
                "download_status": download.get("status"),
                "delivery": download.get("delivery"),
                "reason": download.get("reason"),
                "signed_url_issued": bool(download.get("signed_url")),
                "storage_object_count": len(storage_objects),
                "storage_objects": object_summaries,
            }
        return results

    def verify_visibility_and_persistence() -> dict[str, object]:
        results: dict[str, object] = {}
        for label, upload in uploads.items():
            uid = _text(upload.get("upload_id"), f"{label} upload id")
            owner_item = _list_contains_upload(
                request_json("GET", "/documents/uploads?limit=100", headers=auditor_headers),
                uid,
                f"{label} owner list",
            )
            head_item = _list_contains_upload(
                request_json("GET", "/documents/uploads?limit=100", headers=head_headers),
                uid,
                f"{label} department-head list",
            )
            for actor_label, item in {"owner": owner_item, "department_head": head_item}.items():
                readiness = _dict(item.get("index_readiness"), f"{label} {actor_label} readiness")
                blockers = _list(readiness.get("blockers"), f"{label} {actor_label} blockers")
                _require(
                    blockers == upload.get("expected_blockers"),
                    f"{label} {actor_label} blockers mismatch: {blockers}",
                )
            results[label] = {
                "upload_id": uid,
                "owner_visible": True,
                "department_head_visible": True,
                "expected_blockers": upload.get("expected_blockers"),
            }
        return results

    def verify_audit_logs() -> dict[str, object]:
        expected_actions = {
            "document-upload": {"minimum_count": 2, "must_reference_upload": True},
            "document-upload-download-metadata": {
                "minimum_count": 2,
                "must_reference_upload": True,
            },
            "document-upload-list": {"minimum_count": 4, "must_reference_upload": False},
        }
        action_results: dict[str, object] = {}
        upload_ids = [
            _text(upload.get("upload_id"), f"{label} upload id")
            for label, upload in uploads.items()
        ]
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
            if must_reference_upload:
                serialized_items = [json.dumps(item, ensure_ascii=False) for item in items]
                matched = [
                    item
                    for item in serialized_items
                    if any(upload_id in item for upload_id in upload_ids)
                ]
            else:
                matched = items
            _require(
                len(matched) >= minimum_count,
                f"audit logs missing {action}: matched {len(matched)}",
            )
            action_results[action] = {
                "matched_count": len(matched),
                "must_reference_upload": must_reference_upload,
                "store_ready": _dict(payload.get("store"), "store").get("ready"),
                "backend": _dict(payload.get("store"), "store").get("backend"),
            }
        return {"upload_ids": upload_ids, "actions": action_results}

    status = "pass"
    error: str | None = None
    try:
        run_step("upload-clean-document-and-run-ruleset-dlp", upload_and_assert_clean)
        run_step("upload-sensitive-document-and-run-ruleset-dlp", upload_and_assert_sensitive)
        run_step("download-metadata-storage-objects-recorded", verify_download_metadata)
        run_step("list-persistence-keeps-ruleset-dlp-results", verify_visibility_and_persistence)
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
        "uploads": uploads,
        "boundaries": {
            "production_write": _is_production_base_url(base_url),
            "document_upload_write": True,
            "object_storage_write": True,
            "real_clamav_sidecar_scan": True,
            "real_ruleset_dlp_review": True,
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
            "and ruleset-v1 DLP passes clean content while blocking sensitive content."
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
            "Pass audit.lute-tlz-dddd.top to acknowledge production upload/object writes."
        ),
    )
    return parser.parse_args()


def _upload_and_assert(
    *,
    request_json: Callable[..., tuple[requests.Response, dict[str, object]]],
    headers: dict[str, str],
    fixture: dict[str, object],
    expected_dlp_status: str,
    expected_dlp_result_code: str,
    expected_blockers: list[str],
    uploads: dict[str, dict[str, object]],
) -> dict[str, object]:
    label = _text(fixture.get("label"), "fixture label")
    content = _bytes(fixture.get("content"), f"{label} fixture content")
    file_name = _text(fixture.get("file_name"), f"{label} fixture file name")
    response, payload = request_json(
        "POST",
        "/documents/uploads",
        headers=headers,
        files={"file": (file_name, content, "text/plain")},
    )
    _require(
        response.status_code == 200,
        f"{label} upload returned {response.status_code}: {payload}",
    )
    item = _dict(payload.get("item"), f"{label} upload item")
    upload_id = _text(item.get("id"), f"{label} upload id")
    readiness = _dict(item.get("index_readiness"), f"{label} index_readiness")
    blockers = _list(readiness.get("blockers"), f"{label} blockers")
    checks = _checks_by_type(readiness)
    virus_check = _dict(checks.get("virus-scan"), f"{label} virus-scan check")
    dlp_check = _dict(checks.get("dlp-review"), f"{label} dlp-review check")
    manual_check = _dict(
        checks.get("manual-index-approval"),
        f"{label} manual-index-approval check",
    )

    _require(readiness.get("status") == "blocked", f"{label} upload should remain blocked")
    _require(blockers == expected_blockers, f"{label} blockers mismatch: {blockers}")
    _require(virus_check.get("provider") == "clamav-sidecar", f"{label} virus provider mismatch")
    _require(virus_check.get("status") == "passed", f"{label} virus check should pass")
    _require(virus_check.get("blocker") is None, f"{label} virus check should not block")
    _require(virus_check.get("result_code") == "clean", f"{label} virus result_code mismatch")
    _require(dlp_check.get("provider") == "ruleset-v1", f"{label} DLP provider mismatch")
    _require(dlp_check.get("status") == expected_dlp_status, f"{label} DLP status mismatch")
    _require(
        dlp_check.get("result_code") == expected_dlp_result_code,
        f"{label} DLP result_code mismatch",
    )
    _require(
        manual_check.get("blocker") == "manual-index-approval-required",
        f"{label} manual approval blocker mismatch",
    )
    serialized_dlp_check = json.dumps(dlp_check, ensure_ascii=False)
    for raw_marker in ("测试患者", "110105199001011234", "13800138000"):
        _require(raw_marker not in serialized_dlp_check, f"{label} DLP check leaked raw marker")

    upload_summary = {
        "upload_id": upload_id,
        "file_name": item.get("name"),
        "sha256": fixture.get("sha256"),
        "expected_blockers": expected_blockers,
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
    uploads[label] = upload_summary
    return upload_summary


def _fixture(*, label: str, run_id: str, content: bytes) -> dict[str, object]:
    return {
        "label": label,
        "file_name": f"production-documents-ruleset-dlp-{label}-e2e-{run_id}.txt",
        "content": content,
        "sha256": hashlib.sha256(content).hexdigest(),
    }


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
        result[check_type] = {
            "provider": check.get("provider"),
            "status": check.get("status"),
            "blocker": check.get("blocker"),
            "risk_level": check.get("risk_level"),
            "result_code": check.get("result_code"),
        }
    return result


def _checks_by_type(readiness: dict[str, object]) -> dict[str, dict[str, object]]:
    checks = _list(readiness.get("checks"), "readiness checks")
    result: dict[str, dict[str, object]] = {}
    for item in checks:
        check = _dict(item, "readiness check")
        check_type = _text(check.get("check_type"), "check_type")
        result[check_type] = check
    return result


def _list_contains_upload(
    response_payload: tuple[requests.Response, dict[str, object]],
    upload_id: str,
    label: str,
) -> dict[str, object]:
    response, payload = response_payload
    _require(response.status_code == 200, f"{label} returned {response.status_code}: {payload}")
    items = _list(payload.get("items"), f"{label} items")
    matches = [
        _dict(item, f"{label} item")
        for item in items
        if _dict(item, f"{label} item").get("id") == upload_id
    ]
    _require(matches, f"{label} does not include {upload_id}")
    return matches[0]


def _dict(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise E2EError(f"{label} is not an object")
    return value


def _list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise E2EError(f"{label} is not a list")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise E2EError(f"{label} is not text")
    return value


def _bytes(value: object, label: str) -> bytes:
    if not isinstance(value, bytes):
        raise E2EError(f"{label} is not bytes")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise E2EError(message)


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    sys.exit(main())
