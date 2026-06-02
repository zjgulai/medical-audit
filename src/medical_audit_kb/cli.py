from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import NoReturn

from medical_audit_kb.core.config import DATABASE_URL_ENV
from medical_audit_kb.indexing.incremental_plan import (
    build_incremental_plan_from_database,
    incremental_plan_json,
    render_incremental_plan_markdown,
)
from medical_audit_kb.indexing.index_activation import (
    activate_index_version,
    index_activation_json,
    index_rollback_json,
    render_index_activation_markdown,
    render_index_rollback_markdown,
    rollback_index_version,
)
from medical_audit_kb.indexing.pgvector_import import (
    build_pgvector_import_plan,
    render_pgvector_import_plan_markdown,
)
from medical_audit_kb.indexing.pgvector_writer import (
    render_pgvector_import_execution_markdown,
    run_pgvector_import,
)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "index-incremental-plan":
        return _index_incremental_plan(args)
    if args.command == "pgvector-import-plan":
        return _pgvector_import_plan(args)
    if args.command == "pgvector-import":
        return _pgvector_import(args)
    if args.command == "index-activate":
        return _index_activate(args)
    if args.command == "index-rollback":
        return _index_rollback(args)
    _die(f"unsupported command: {args.command}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="medical-audit-kb")
    subparsers = parser.add_subparsers(dest="command", required=True)

    incremental_plan = subparsers.add_parser(
        "index-incremental-plan",
        help="Build a read-only incremental update plan from the active PostgreSQL index.",
    )
    incremental_plan.add_argument("--source-root", required=True, type=Path)
    incremental_plan.add_argument("--package-version-key")
    incremental_plan.add_argument("--output", required=True, type=Path)
    incremental_plan.add_argument("--json-output", type=Path)
    incremental_plan.add_argument("--database-url-env", default=DATABASE_URL_ENV)

    pgvector_import_plan = subparsers.add_parser(
        "pgvector-import-plan",
        help="Validate local persistent index artifacts before PostgreSQL + pgvector import.",
    )
    pgvector_import_plan.add_argument("--index-root", required=True, type=Path)
    pgvector_import_plan.add_argument("--output", required=True, type=Path)
    pgvector_import_plan.add_argument("--json-output", type=Path)
    pgvector_import_plan.add_argument("--schema-dimension", type=int, default=1024)

    pgvector_import = subparsers.add_parser(
        "pgvector-import",
        help="Dry-run or execute PostgreSQL + pgvector import from persistent JSONL artifacts.",
    )
    pgvector_import.add_argument("--index-root", required=True, type=Path)
    pgvector_import.add_argument("--source-root", required=True, type=Path)
    pgvector_import.add_argument("--output", required=True, type=Path)
    pgvector_import.add_argument("--json-output", type=Path)
    pgvector_import.add_argument("--schema-dimension", type=int, default=1024)
    pgvector_import.add_argument("--batch-size", type=int, default=500)
    pgvector_import.add_argument("--database-url-env", default=DATABASE_URL_ENV)
    pgvector_import.add_argument(
        "--index-version-status",
        choices=("candidate", "active"),
        default="candidate",
        help="Status written to index_versions when executing the import.",
    )
    pgvector_import.add_argument(
        "--execute",
        action="store_true",
        help="Actually write to PostgreSQL. Omit this flag to run dry-run only.",
    )

    index_activate = subparsers.add_parser(
        "index-activate",
        help="Atomically activate a candidate index version and deactivate matching active ones.",
    )
    index_activate.add_argument("--index-version-key", required=True)
    index_activate.add_argument("--database-url-env", default=DATABASE_URL_ENV)
    index_activate.add_argument("--output", required=True, type=Path)
    index_activate.add_argument("--json-output", type=Path)

    index_rollback = subparsers.add_parser(
        "index-rollback",
        help="Rollback to an inactive or active index version and deactivate matching active ones.",
    )
    index_rollback.add_argument("--index-version-key", required=True)
    index_rollback.add_argument("--database-url-env", default=DATABASE_URL_ENV)
    index_rollback.add_argument("--output", required=True, type=Path)
    index_rollback.add_argument("--json-output", type=Path)
    return parser


def _index_incremental_plan(args: argparse.Namespace) -> int:
    plan = build_incremental_plan_from_database(
        source_root=args.source_root,
        database_url=_database_url_from_env(args.database_url_env),
        package_version_key=args.package_version_key,
    )
    _write_text(args.output, render_incremental_plan_markdown(plan))
    if args.json_output is not None:
        _write_text(args.json_output, incremental_plan_json(plan))
    return 0 if plan.ready_for_incremental_build else 2


def _pgvector_import_plan(args: argparse.Namespace) -> int:
    plan = build_pgvector_import_plan(
        args.index_root,
        schema_dimension=args.schema_dimension,
    )
    _write_text(args.output, render_pgvector_import_plan_markdown(plan))
    if args.json_output is not None:
        _write_text(
            args.json_output,
            json.dumps(plan.to_dict(), ensure_ascii=False, indent=2) + "\n",
        )
    return 0 if plan.ready_for_import else 2


def _pgvector_import(args: argparse.Namespace) -> int:
    try:
        result = run_pgvector_import(
            args.index_root,
            args.source_root,
            execute=args.execute,
            database_url_env=args.database_url_env,
            schema_dimension=args.schema_dimension,
            batch_size=args.batch_size,
            index_version_status=args.index_version_status,
        )
    except ValueError as exc:
        _die(str(exc))
    _write_text(args.output, render_pgvector_import_execution_markdown(result))
    if args.json_output is not None:
        _write_text(
            args.json_output,
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n",
        )
    return 0 if result.success else 2


def _index_activate(args: argparse.Namespace) -> int:
    result = activate_index_version(
        database_url=_database_url_from_env(args.database_url_env),
        index_version_key=args.index_version_key,
    )
    _write_text(args.output, render_index_activation_markdown(result))
    if args.json_output is not None:
        _write_text(args.json_output, index_activation_json(result))
    return 0 if result.success else 2


def _index_rollback(args: argparse.Namespace) -> int:
    result = rollback_index_version(
        database_url=_database_url_from_env(args.database_url_env),
        index_version_key=args.index_version_key,
    )
    _write_text(args.output, render_index_rollback_markdown(result))
    if args.json_output is not None:
        _write_text(args.json_output, index_rollback_json(result))
    return 0 if result.success else 2


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _database_url_from_env(env_name: str) -> str:
    import os

    database_url = os.getenv(env_name)
    if not database_url:
        _die(f"missing database url env: {env_name}")
    return database_url


def _die(message: str) -> NoReturn:
    raise SystemExit(message)


if __name__ == "__main__":
    raise SystemExit(main())
