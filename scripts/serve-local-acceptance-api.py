#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import uvicorn

from medical_audit_kb.api.local_acceptance import (
    DEFAULT_LOCAL_ACCEPTANCE_ROOT,
    create_local_acceptance_app,
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    app = create_local_acceptance_app(args.state_root)
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
    )
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve the local-only acceptance API for frontend smoke checks.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8021)
    parser.add_argument(
        "--state-root",
        type=Path,
        default=DEFAULT_LOCAL_ACCEPTANCE_ROOT,
        help="Local directory for deterministic source and upload fixtures.",
    )
    parser.add_argument("--log-level", default="info")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
