#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path

from medical_audit_kb.cli import main as cli_main

DEFAULT_ARCHIVE_ROOT = "/app/audit-log-archive"
DEFAULT_REPORT_DIR = "/app/audit-reports"
DEFAULT_SIGNING_SECRET_ENV = "MEDICAL_AUDIT_AUDIT_LOG_SIGNING_SECRET"
DEFAULT_OUTPUT_PREFIX = "audit-log-archive-audit"
DEFAULT_ALERT_WEBHOOK_URL_ENV = "MEDICAL_AUDIT_AUDIT_LOG_ALERT_WEBHOOK_URL"
DEFAULT_ALERT_SERVICE = "medical-audit"
DEFAULT_ALERT_TIMEOUT_SECONDS = 10.0
SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
TRUE_VALUES = frozenset(("1", "true", "yes", "on"))


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report_dir = Path(args.report_dir).expanduser().resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    run_id = args.run_id or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    markdown_report = report_dir / f"{args.output_prefix}-{run_id}.md"
    json_report = report_dir / f"{args.output_prefix}-{run_id}.json"

    archive_root = Path(args.archive_root).expanduser().resolve()
    try:
        exit_code = _run_archive_audit(
            archive_root=archive_root,
            signing_secret_env=str(args.signing_secret_env),
            min_manifest_count=int(args.min_manifest_count),
            markdown_report=markdown_report,
            json_report=json_report,
        )
        result_payload = _read_json_report(json_report)
    except SystemExit as exc:
        exit_code = _system_exit_code(exc)
        result_payload = _write_script_error_reports(
            markdown_report=markdown_report,
            json_report=json_report,
            archive_root=archive_root,
            run_id=run_id,
            error_type="SystemExit",
            error_message=_system_exit_message(exc),
            exit_code=exit_code,
        )
    except Exception as exc:
        exit_code = 2
        result_payload = _write_script_error_reports(
            markdown_report=markdown_report,
            json_report=json_report,
            archive_root=archive_root,
            run_id=run_id,
            error_type=type(exc).__name__,
            error_message=str(exc),
            exit_code=exit_code,
        )

    latest_markdown = report_dir / f"{args.output_prefix}-latest.md"
    latest_json = report_dir / f"{args.output_prefix}-latest.json"
    _copy_if_exists(markdown_report, latest_markdown)
    _copy_if_exists(json_report, latest_json)
    alert_result = _maybe_send_alert(
        args=args,
        exit_code=exit_code,
        run_id=run_id,
        archive_root=archive_root,
        markdown_report=markdown_report,
        json_report=json_report,
        latest_markdown=latest_markdown,
        latest_json=latest_json,
        result_payload=result_payload,
    )
    final_exit_code = exit_code
    alert_requested = exit_code != 0 or bool(args.send_success_alert)
    if (
        exit_code == 0
        and args.fail_on_alert_error
        and alert_requested
        and alert_result.get("sent") is not True
    ):
        final_exit_code = 2

    print(
        json.dumps(
            {
                "status": "pass" if final_exit_code == 0 else "fail",
                "exit_code": final_exit_code,
                "audit_exit_code": exit_code,
                "archive_root": str(archive_root),
                "markdown_report": str(markdown_report),
                "json_report": str(json_report),
                "latest_markdown_report": str(latest_markdown),
                "latest_json_report": str(latest_json),
                "alert": alert_result,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return final_exit_code


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Run a read-only audit-log archive root audit and maintain latest reports.")
    )
    parser.add_argument(
        "--archive-root",
        default=os.environ.get(
            "MEDICAL_AUDIT_AUDIT_LOG_ARCHIVE_ROOT",
            DEFAULT_ARCHIVE_ROOT,
        ),
    )
    parser.add_argument(
        "--report-dir",
        default=os.environ.get(
            "MEDICAL_AUDIT_AUDIT_LOG_ARCHIVE_REPORT_DIR",
            DEFAULT_REPORT_DIR,
        ),
    )
    parser.add_argument(
        "--signing-secret-env",
        default=os.environ.get(
            "MEDICAL_AUDIT_AUDIT_LOG_SIGNING_SECRET_ENV",
            DEFAULT_SIGNING_SECRET_ENV,
        ),
        help="Name of the environment variable containing the HMAC signing secret.",
    )
    parser.add_argument(
        "--min-manifest-count",
        type=_non_negative_int,
        default=_default_min_manifest_count(),
    )
    parser.add_argument(
        "--alert-webhook-url-env",
        default=os.environ.get(
            "MEDICAL_AUDIT_AUDIT_LOG_ALERT_WEBHOOK_URL_ENV",
            DEFAULT_ALERT_WEBHOOK_URL_ENV,
        ),
        help="Name of the environment variable containing the alert webhook URL.",
    )
    parser.add_argument(
        "--alert-service",
        default=os.environ.get(
            "MEDICAL_AUDIT_AUDIT_LOG_ALERT_SERVICE",
            DEFAULT_ALERT_SERVICE,
        ),
    )
    parser.add_argument(
        "--alert-timeout-seconds",
        type=_positive_float,
        default=_default_alert_timeout_seconds(),
    )
    parser.add_argument(
        "--send-success-alert",
        action="store_true",
        default=_env_bool("MEDICAL_AUDIT_AUDIT_LOG_SEND_SUCCESS_ALERT"),
        help="Send an alert even when the archive root audit passes.",
    )
    parser.add_argument(
        "--fail-on-alert-error",
        action="store_true",
        default=_env_bool("MEDICAL_AUDIT_AUDIT_LOG_ALERT_FAIL_ON_ERROR"),
        help="Return non-zero when a requested alert cannot be delivered.",
    )
    parser.add_argument("--output-prefix", type=_safe_token, default=DEFAULT_OUTPUT_PREFIX)
    parser.add_argument("--run-id", type=_safe_token)
    return parser.parse_args(argv)


def _default_min_manifest_count() -> int:
    raw_value = os.environ.get("MEDICAL_AUDIT_AUDIT_LOG_MIN_MANIFEST_COUNT", "0")
    return _non_negative_int(raw_value)


def _default_alert_timeout_seconds() -> float:
    raw_value = os.environ.get(
        "MEDICAL_AUDIT_AUDIT_LOG_ALERT_TIMEOUT_SECONDS",
        str(DEFAULT_ALERT_TIMEOUT_SECONDS),
    )
    return _positive_float(raw_value)


def _run_archive_audit(
    *,
    archive_root: Path,
    signing_secret_env: str,
    min_manifest_count: int,
    markdown_report: Path,
    json_report: Path,
) -> int:
    return cli_main(
        [
            "audit-log-archive-audit",
            "--archive-root",
            str(archive_root),
            "--signing-secret-env",
            signing_secret_env,
            "--min-manifest-count",
            str(min_manifest_count),
            "--output",
            str(markdown_report),
            "--json-output",
            str(json_report),
        ]
    )


def _read_json_report(json_report: Path) -> dict[str, object]:
    try:
        payload = json.loads(json_report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "status": "unknown",
            "issues": ["json report could not be read"],
        }
    if not isinstance(payload, dict):
        return {
            "status": "unknown",
            "issues": ["json report payload is not an object"],
        }
    return payload


def _write_script_error_reports(
    *,
    markdown_report: Path,
    json_report: Path,
    archive_root: Path,
    run_id: str,
    error_type: str,
    error_message: str,
    exit_code: int,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": "error",
        "run_id": run_id,
        "archive_root": str(archive_root),
        "error_type": error_type,
        "error_message": error_message,
        "exit_code": exit_code,
        "issues": [f"{error_type}: {error_message}"],
    }
    json_report.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_report.write_text(
        "\n".join(
            (
                "# 审计日志归档根目录巡检脚本错误",
                "",
                "- 总体状态：`ERROR`",
                f"- 归档根目录：`{archive_root}`",
                f"- 错误类型：`{error_type}`",
                f"- 错误信息：`{error_message}`",
                f"- 退出码：`{exit_code}`",
                "",
            )
        ),
        encoding="utf-8",
    )
    return payload


def _maybe_send_alert(
    *,
    args: argparse.Namespace,
    exit_code: int,
    run_id: str,
    archive_root: Path,
    markdown_report: Path,
    json_report: Path,
    latest_markdown: Path,
    latest_json: Path,
    result_payload: dict[str, object],
) -> dict[str, object]:
    should_send = exit_code != 0 or bool(args.send_success_alert)
    if not should_send:
        return {
            "configured": False,
            "sent": False,
            "status": "not-requested",
            "reason": "audit-passed",
        }
    webhook_url = os.environ.get(str(args.alert_webhook_url_env), "").strip()
    if not webhook_url:
        return {
            "configured": False,
            "sent": False,
            "status": "not-configured",
            "reason": "webhook-not-configured",
        }
    alert_payload = _build_alert_payload(
        args=args,
        exit_code=exit_code,
        run_id=run_id,
        archive_root=archive_root,
        markdown_report=markdown_report,
        json_report=json_report,
        latest_markdown=latest_markdown,
        latest_json=latest_json,
        result_payload=result_payload,
    )
    request = urllib.request.Request(
        webhook_url,
        data=json.dumps(alert_payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=float(args.alert_timeout_seconds),
        ) as response:
            status_code = int(response.status)
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        return {
            "configured": True,
            "sent": False,
            "status": "failed",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }
    if status_code >= 400:
        return {
            "configured": True,
            "sent": False,
            "status": "failed",
            "status_code": status_code,
        }
    return {
        "configured": True,
        "sent": True,
        "status": "sent",
        "status_code": status_code,
    }


def _build_alert_payload(
    *,
    args: argparse.Namespace,
    exit_code: int,
    run_id: str,
    archive_root: Path,
    markdown_report: Path,
    json_report: Path,
    latest_markdown: Path,
    latest_json: Path,
    result_payload: dict[str, object],
) -> dict[str, object]:
    status = str(result_payload.get("status") or ("pass" if exit_code == 0 else "fail"))
    return {
        "event_type": "medical_audit.audit_log_archive_audit",
        "service": str(args.alert_service),
        "severity": "critical" if exit_code != 0 else "info",
        "status": status,
        "exit_code": exit_code,
        "run_id": run_id,
        "host": socket.gethostname(),
        "archive_root": str(archive_root),
        "reports": {
            "markdown": str(markdown_report),
            "json": str(json_report),
            "latest_markdown": str(latest_markdown),
            "latest_json": str(latest_json),
        },
        "summary": _alert_summary(result_payload),
    }


def _alert_summary(result_payload: dict[str, object]) -> dict[str, object]:
    keys = (
        "manifest_count",
        "verified_count",
        "failed_count",
        "missing_archive_count",
        "path_escape_count",
        "issues",
        "error_type",
        "error_message",
    )
    return {key: result_payload.get(key) for key in keys if key in result_payload}


def _system_exit_code(exc: SystemExit) -> int:
    return exc.code if isinstance(exc.code, int) else 2


def _system_exit_message(exc: SystemExit) -> str:
    if exc.code is None or isinstance(exc.code, int):
        return ""
    return str(exc.code)


def _non_negative_int(raw_value: str) -> int:
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be an integer") from exc
    if value < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return value


def _positive_float(raw_value: str) -> float:
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be a number") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError("value must be greater than 0")
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in TRUE_VALUES


def _safe_token(raw_value: str) -> str:
    if not SAFE_TOKEN_PATTERN.fullmatch(raw_value):
        raise argparse.ArgumentTypeError(
            "value must contain only letters, numbers, dots, underscores or hyphens"
        )
    return raw_value


def _copy_if_exists(source: Path, target: Path) -> None:
    if source.exists():
        shutil.copyfile(source, target)


if __name__ == "__main__":
    raise SystemExit(main())
