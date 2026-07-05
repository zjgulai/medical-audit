#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from medical_audit_kb.ingestion.canonical_source_root import (
    build_canonical_source_root,
    write_canonical_manifest_csv,
    write_canonical_manifest_json,
    write_canonical_report,
)

DEFAULT_SOURCE_ROOT = "tmp/knowledge-base-batches/medical-legal-regulations-normalized-20260703"
DEFAULT_OUTPUT_ROOT = "tmp/knowledge-base-batches/medical-legal-regulations-canonical-20260703"
DEFAULT_MANIFEST_JSON = (
    "tmp/outputs/knowledge-base-medical-legal-regulations-canonical-manifest-20260703.json"
)
DEFAULT_MANIFEST_CSV = (
    "tmp/outputs/knowledge-base-medical-legal-regulations-canonical-manifest-20260703.csv"
)
DEFAULT_REPORT = (
    "drafts/analysis/knowledge-base-medical-legal-regulations-canonical-root-draft-20260703.md"
)


def main() -> int:
    args = _parse_args()
    result = build_canonical_source_root(
        Path(args.source_root),
        Path(args.output_root),
        execute=args.execute,
    )
    write_canonical_manifest_json(Path(args.manifest_json), result)
    write_canonical_manifest_csv(Path(args.manifest_csv), result)
    write_canonical_report(Path(args.report), result)
    payload = {
        "status": "materialized" if args.execute else "planned",
        **result.summary(),
        "manifest_json": args.manifest_json,
        "manifest_csv": args.manifest_csv,
        "report": args.report,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a canonical symlink source root by deduplicating legal documents.",
    )
    parser.add_argument("--source-root", default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--manifest-json", default=DEFAULT_MANIFEST_JSON)
    parser.add_argument("--manifest-csv", default=DEFAULT_MANIFEST_CSV)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
