#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from medical_audit_kb.api.document_upload_governance_preflight import (  # noqa: E402
    document_upload_governance_provider_preflight_from_settings,
)
from medical_audit_kb.core.config import load_settings  # noqa: E402


def main() -> int:
    args = _parse_args()
    settings = load_settings(args.config)
    report = document_upload_governance_provider_preflight_from_settings(
        settings.document_upload_governance,
        require_external_provider=args.require_external_provider,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a local document-governance provider preflight. "
            "The script reads configuration only; it does not call virus-scan, DLP, "
            "object-storage, or production APIs."
        ),
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to a knowledge-query-engine YAML config. Defaults to configured app behavior.",
    )
    parser.add_argument(
        "--require-external-provider",
        action="store_true",
        help="Block when no external virus-scan or DLP provider is configured.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
