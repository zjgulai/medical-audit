#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from medical_audit_kb.api.document_upload_store import (  # noqa: E402
    tencent_cos_bootstrap_preflight_from_settings,
)
from medical_audit_kb.core.config import load_settings  # noqa: E402


def main() -> int:
    args = _parse_args()
    settings = load_settings(args.config)
    report = tencent_cos_bootstrap_preflight_from_settings(
        settings.document_storage,
        qcloud_cos_available=_sdk_availability_override(args.qcloud_cos_availability),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a local Tencent COS document-storage bootstrap preflight. "
            "The script reads configuration and environment only; it does not upload objects."
        ),
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to a knowledge-query-engine YAML config. Defaults to configured app behavior.",
    )
    parser.add_argument(
        "--qcloud-cos-availability",
        choices=("auto", "available", "missing"),
        default="auto",
        help="Override SDK availability detection for offline validation.",
    )
    return parser.parse_args()


def _sdk_availability_override(value: str) -> bool | None:
    if value == "available":
        return True
    if value == "missing":
        return False
    return None


if __name__ == "__main__":
    raise SystemExit(main())
