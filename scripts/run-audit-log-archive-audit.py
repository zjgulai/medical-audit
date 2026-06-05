#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import time
from pathlib import Path

from medical_audit_kb.cli import main as cli_main

DEFAULT_ARCHIVE_ROOT = "/app/audit-log-archive"
DEFAULT_REPORT_DIR = "/app/audit-reports"
DEFAULT_SIGNING_SECRET_ENV = "MEDICAL_AUDIT_AUDIT_LOG_SIGNING_SECRET"
DEFAULT_OUTPUT_PREFIX = "audit-log-archive-audit"
SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report_dir = Path(args.report_dir).expanduser().resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    run_id = args.run_id or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    markdown_report = report_dir / f"{args.output_prefix}-{run_id}.md"
    json_report = report_dir / f"{args.output_prefix}-{run_id}.json"

    exit_code = cli_main(
        [
            "audit-log-archive-audit",
            "--archive-root",
            str(Path(args.archive_root).expanduser().resolve()),
            "--signing-secret-env",
            str(args.signing_secret_env),
            "--min-manifest-count",
            str(args.min_manifest_count),
            "--output",
            str(markdown_report),
            "--json-output",
            str(json_report),
        ]
    )

    latest_markdown = report_dir / f"{args.output_prefix}-latest.md"
    latest_json = report_dir / f"{args.output_prefix}-latest.json"
    _copy_if_exists(markdown_report, latest_markdown)
    _copy_if_exists(json_report, latest_json)

    print(
        json.dumps(
            {
                "status": "pass" if exit_code == 0 else "fail",
                "exit_code": exit_code,
                "archive_root": str(Path(args.archive_root).expanduser().resolve()),
                "markdown_report": str(markdown_report),
                "json_report": str(json_report),
                "latest_markdown_report": str(latest_markdown),
                "latest_json_report": str(latest_json),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return exit_code


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
    parser.add_argument("--output-prefix", type=_safe_token, default=DEFAULT_OUTPUT_PREFIX)
    parser.add_argument("--run-id", type=_safe_token)
    return parser.parse_args(argv)


def _default_min_manifest_count() -> int:
    raw_value = os.environ.get("MEDICAL_AUDIT_AUDIT_LOG_MIN_MANIFEST_COUNT", "0")
    return _non_negative_int(raw_value)


def _non_negative_int(raw_value: str) -> int:
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("value must be an integer") from exc
    if value < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return value


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
