#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
READY_PROFILE_CONFIG = "configs/knowledge-query-engine-document-governance-ready-profile.yaml"
READY_PROFILE_JSON_OUTPUT = (
    "tmp/outputs/document-governance-contract-readiness-ready-profile-latest.json"
)
READY_PROFILE_MARKDOWN_OUTPUT = (
    "tmp/outputs/document-governance-contract-readiness-ready-profile-latest.md"
)
READY_PROFILE_ENV = {
    "MEDICAL_AUDIT_DOCUMENT_READY_PROFILE_COS_SECRET_ID": "ready-profile-cos-id-sentinel",
    "MEDICAL_AUDIT_DOCUMENT_READY_PROFILE_COS_SECRET_KEY": "ready-profile-cos-key-sentinel",
}


def main() -> int:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts/audit-document-governance-contract-readiness.py"),
        "--config",
        READY_PROFILE_CONFIG,
        "--qcloud-cos-availability",
        "available",
        "--json-output",
        READY_PROFILE_JSON_OUTPUT,
        "--markdown-output",
        READY_PROFILE_MARKDOWN_OUTPUT,
    ]
    env = {**os.environ, **READY_PROFILE_ENV}
    completed = subprocess.run(command, cwd=REPO_ROOT, env=env, check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
