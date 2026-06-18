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
from urllib.parse import urlencode

import requests

DEFAULT_BASE_URL = "https://audit.lute-tlz-dddd.top"
DEFAULT_API_PREFIX = "/api/v1"
DEFAULT_REPORT = "tmp/outputs/production-documents-governance-result-e2e-latest.json"


class E2EError(RuntimeError):
    pass


def main() -> int:
    args = _parse_args()
    base_url = str(args.base_url).rstrip("/")
    api_prefix = "/" + str(args.api_prefix).strip("/")
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    run_id = str(args.run_id) if args.run_id else _utc_stamp()
    timeout_seconds = float(args.timeout_seconds)
    session = requests.Session()
    steps: list[dict[str, object]] = []
    upload_id: str | None = None
    started_at = _now_iso()

    fixture_name = f"production-documents-governance-ready-e2e-{run_id}.txt"
    fixture_bytes = (
        b"Production governance-result E2E fixture.\n"
        b"This validates controlled result writeback and readiness state only.\n"
    )
    fixture_sha256 = hashlib.sha256(fixture_bytes).hexdigest()
    actor_suffix = run_id.replace(":", "").replace("+", "").replace(".", "")
    auditor_headers = {
        "X-User-Id": f"documents-governance-owner-{actor_suffix}",
        "X-Role": "auditor",
    }
    head_headers = {
        "X-User-Id": f"documents-governance-head-{actor_suffix}",
        "X-Role": "department-head",
    }
    admin_headers = {
        "X-User-Id": f"documents-governance-admin-{actor_suffix}",
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
        blockers = _list(readiness.get("blockers"), "initial blockers")
        _require(readiness.get("status") == "blocked", "new upload should be blocked")
        _require("virus-scan-required" in blockers, "missing virus-scan blocker")
        _require("dlp-review-required" in blockers, "missing dlp-review blocker")
        _require(
            "manual-index-approval-required" in blockers,
            "missing manual approval blocker",
        )
        return {
            "status_code": response.status_code,
            "upload_id": upload_id,
            "file_name": item.get("name"),
            "file_sha256": fixture_sha256,
            "created_by": item.get("created_by"),
            "index_status": item.get("index_status"),
            "readiness_status": readiness.get("status"),
            "blockers": blockers,
            "check_statuses": _check_statuses(readiness),
            "store_backend": _dict(payload.get("store"), "store").get("backend"),
        }

    def auditor_result_update_denied() -> dict[str, object]:
        uid = _upload_id(upload_id)
        response, payload = request_json(
            "POST",
            f"/documents/uploads/{uid}/index-readiness/governance-result",
            headers={**auditor_headers, "Content-Type": "application/json"},
            data=json.dumps(
                {
                    "check_type": "dlp-review",
                    "provider": "external-dlp",
                    "status": "passed",
                    "detail": "Auditor role should not write governance results.",
                    "result_code": "no-sensitive-marker",
                },
                ensure_ascii=False,
            ).encode("utf-8"),
        )
        expected = (
            "document upload governance result update requires department-head "
            "or system-admin role"
        )
        _require(response.status_code == 403, f"auditor update expected 403: {payload}")
        _require(payload.get("detail") == expected, f"unexpected denial detail: {payload}")
        return {
            "status_code": response.status_code,
            "detail": payload.get("detail"),
            "upload_id": uid,
        }

    def write_governance_result(
        check_type: str,
        provider: str,
        result_code: str,
    ) -> dict[str, object]:
        uid = _upload_id(upload_id)
        result_payload = {
            "check_type": check_type,
            "provider": provider,
            "status": "passed",
            "detail": (
                f"Production E2E controlled {check_type} result writeback; "
                "no external governance provider was called."
            ),
            "result_code": result_code,
            "external_job_id": f"{run_id}-{check_type}-job",
            "finished_at": _now_iso(),
        }
        response, payload = request_json(
            "POST",
            f"/documents/uploads/{uid}/index-readiness/governance-result",
            headers={**head_headers, "Content-Type": "application/json"},
            data=json.dumps(result_payload, ensure_ascii=False).encode("utf-8"),
        )
        _require(
            response.status_code == 200,
            f"{check_type} writeback returned {response.status_code}: {payload}",
        )
        item = _dict(payload.get("item"), "upload item")
        readiness = _dict(item.get("index_readiness"), "index_readiness")
        check = _check(readiness, check_type)
        _require(check.get("status") == "passed", f"{check_type} was not passed")
        _require(check.get("blocker") is None, f"{check_type} blocker still present")
        _require(
            check.get("external_job_id") == result_payload["external_job_id"],
            f"{check_type} external_job_id did not persist",
        )
        blockers = _list(readiness.get("blockers"), "blockers")
        expected_removed = f"{check_type}-required"
        _require(expected_removed not in blockers, f"{expected_removed} still present")
        return {
            "status_code": response.status_code,
            "upload_id": uid,
            "readiness_status": readiness.get("status"),
            "blockers": blockers,
            "check": check,
            "store_backend": _dict(payload.get("store"), "store").get("backend"),
        }

    def approve_manual_index() -> dict[str, object]:
        uid = _upload_id(upload_id)
        response, payload = request_json(
            "POST",
            f"/documents/uploads/{uid}/index-readiness/manual-approval",
            headers={**head_headers, "Content-Type": "application/json"},
            data=json.dumps(
                {
                    "decision": "approved",
                    "note": "Production E2E approved after controlled governance checks.",
                },
                ensure_ascii=False,
            ).encode("utf-8"),
        )
        _require(
            response.status_code == 200,
            f"manual approval returned {response.status_code}: {payload}",
        )
        item = _dict(payload.get("item"), "upload item")
        readiness = _dict(item.get("index_readiness"), "index_readiness")
        blockers = _list(readiness.get("blockers"), "blockers")
        _require(readiness.get("status") == "ready", f"readiness is not ready: {readiness}")
        _require(blockers == [], f"ready state still has blockers: {blockers}")
        _require(
            readiness.get("next_action") == "ingest-personal-upload",
            f"unexpected next_action: {readiness}",
        )
        _require(item.get("index_status") == "not-indexed", "E2E should not trigger indexing")
        checks = _list(readiness.get("checks"), "checks")
        _require(
            all(_dict(check, "check").get("status") == "passed" for check in checks),
            "not all checks passed",
        )
        return {
            "status_code": response.status_code,
            "upload_id": uid,
            "index_status": item.get("index_status"),
            "readiness_status": readiness.get("status"),
            "next_action": readiness.get("next_action"),
            "blockers": blockers,
            "check_statuses": _check_statuses(readiness),
            "store_backend": _dict(payload.get("store"), "store").get("backend"),
        }

    def verify_persisted_ready() -> dict[str, object]:
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
            _require(readiness.get("status") == "ready", f"{label} list did not persist ready")
            _require(
                _list(readiness.get("blockers"), f"{label} blockers") == [],
                f"{label} blockers not empty",
            )
        owner_readiness = _dict(owner_item.get("index_readiness"), "owner readiness")
        head_readiness = _dict(head_item.get("index_readiness"), "department-head readiness")
        return {
            "upload_id": uid,
            "owner_visible": True,
            "department_head_visible": True,
            "owner_readiness_status": owner_readiness.get("status"),
            "department_head_readiness_status": head_readiness.get("status"),
        }

    def verify_audit_logs() -> dict[str, object]:
        uid = _upload_id(upload_id)
        expected_actions = {
            "document-upload": 1,
            "document-upload-governance-result-access-denied": 1,
            "document-upload-governance-result-update": 2,
            "document-upload-index-readiness-update": 1,
        }
        action_results: dict[str, object] = {}
        for action, minimum_count in expected_actions.items():
            query = urlencode({"action": action, "limit": 100})
            response, payload = request_json("GET", f"/audit/logs?{query}", headers=admin_headers)
            _require(
                response.status_code == 200,
                f"audit logs {action} returned {response.status_code}: {payload}",
            )
            items = _list(payload.get("items"), f"audit log items for {action}")
            matched = [item for item in items if uid in json.dumps(item, ensure_ascii=False)]
            _require(
                len(matched) >= minimum_count,
                f"audit logs missing {action} for {uid}: matched {len(matched)}",
            )
            action_results[action] = {
                "matched_count": len(matched),
                "store_ready": _dict(payload.get("store"), "store").get("ready"),
                "backend": _dict(payload.get("store"), "store").get("backend"),
            }
        return {"upload_id": uid, "actions": action_results}

    status = "pass"
    error: str | None = None
    try:
        run_step("upload-test-document", upload_fixture)
        run_step("auditor-governance-result-update-denied", auditor_result_update_denied)
        run_step(
            "department-head-virus-scan-result-passed",
            lambda: write_governance_result("virus-scan", "tencent-ci-virus", "normal"),
        )
        run_step(
            "department-head-dlp-review-result-passed",
            lambda: write_governance_result("dlp-review", "external-dlp", "no-sensitive-marker"),
        )
        run_step("department-head-manual-approval-approved", approve_manual_index)
        run_step("persisted-list-shows-ready", verify_persisted_ready)
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
            "production_write": True,
            "object_storage_write": True,
            "external_governance_provider_call": False,
            "real_virus_scan_or_dlp": False,
            "indexing_triggered": False,
        },
        "actors": {
            "upload_actor_role": "auditor",
            "writeback_actor_role": "department-head",
            "approval_actor_role": "department-head",
            "denied_actor_role": "auditor",
            "audit_reader_role": "system-admin",
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
            "Run production /documents governance-result E2E. "
            "This writes a controlled upload, governance results, manual approval, "
            "and audit log entries."
        ),
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-prefix", default=DEFAULT_API_PREFIX)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    parser.add_argument(
        "--skip-audit-log-check",
        action="store_true",
        help="Skip persisted audit-log verification.",
    )
    return parser.parse_args()


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _write_report(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise E2EError(message)


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


def _upload_id(value: str | None) -> str:
    if value is None:
        raise E2EError("upload id is not available")
    return value


def _check(readiness: dict[str, object], check_type: str) -> dict[str, object]:
    for item in _list(readiness.get("checks"), "checks"):
        check = _dict(item, "check")
        if check.get("check_type") == check_type:
            return check
    raise E2EError(f"missing check {check_type}")


def _check_statuses(readiness: dict[str, object]) -> dict[str, object]:
    statuses: dict[str, object] = {}
    for item in _list(readiness.get("checks"), "checks"):
        check = _dict(item, "check")
        check_type = _text(check.get("check_type"), "check_type")
        statuses[check_type] = {
            "provider": check.get("provider"),
            "status": check.get("status"),
            "blocker": check.get("blocker"),
        }
    return statuses


def _list_contains_upload(
    response_payload: tuple[requests.Response, dict[str, object]],
    upload_id: str,
    label: str,
) -> dict[str, object]:
    response, payload = response_payload
    _require(
        response.status_code == 200,
        f"{label} returned {response.status_code}: {payload}",
    )
    items = _list(payload.get("items"), f"{label} items")
    for item in items:
        upload = _dict(item, f"{label} item")
        if upload.get("id") == upload_id:
            return upload
    raise E2EError(f"{label} did not include upload {upload_id}")


if __name__ == "__main__":
    sys.exit(main())
