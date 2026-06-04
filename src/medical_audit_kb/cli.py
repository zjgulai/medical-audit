from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path
from typing import NoReturn, Protocol, cast
from uuid import UUID

from medical_audit_kb.acceptance.reports import (
    build_acceptance_report,
    render_acceptance_report_markdown,
)
from medical_audit_kb.core.config import DATABASE_URL_ENV
from medical_audit_kb.evaluation.answer_datasets import load_answer_evaluation_cases
from medical_audit_kb.evaluation.answer_reports import (
    render_answer_evaluation_summary_markdown,
)
from medical_audit_kb.evaluation.answer_runner import evaluate_answers
from medical_audit_kb.evaluation.datasets import (
    generate_candidate_cases_from_materials,
    load_evaluation_cases,
)
from medical_audit_kb.evaluation.reports import render_evaluation_summary_markdown
from medical_audit_kb.evaluation.runner import evaluate_retrieval
from medical_audit_kb.generation.answer_builder import AnswerGenerationProvider
from medical_audit_kb.generation.answer_preflight import (
    render_answer_provider_preflight_markdown,
    run_answer_provider_preflight,
)
from medical_audit_kb.generation.answer_providers import (
    AnthropicAnswerGenerationProvider,
    OpenAICompatibleAnswerGenerationProvider,
)
from medical_audit_kb.his.ddl_parser import (
    his_ddl_parse_report_json,
    parse_his_ddl,
    render_his_ddl_parse_report_markdown,
)
from medical_audit_kb.his.sample_quality import (
    build_his_sample_quality_report,
    his_sample_quality_report_json,
    load_his_ddl_parse_report_json,
    render_his_sample_quality_report_markdown,
)
from medical_audit_kb.his.snapshot_apply import (
    apply_his_snapshot_plan_to_database,
    his_snapshot_apply_result_json,
    load_his_snapshot_plan_json,
    render_his_snapshot_apply_markdown,
)
from medical_audit_kb.his.snapshot_plan import (
    build_his_snapshot_plan,
    his_snapshot_plan_json,
    load_his_sample_quality_report_json,
    render_his_snapshot_plan_markdown,
)
from medical_audit_kb.his.staging_import import (
    his_staging_import_result_json,
    import_his_sample_quality_to_staging_database,
    load_his_staging_sample_quality_report_json,
    render_his_staging_import_markdown,
)
from medical_audit_kb.indexing.embeddings import (
    DeterministicFakeEmbeddingProvider,
    EmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
)
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
from medical_audit_kb.indexing.persistent_index import (
    build_persistent_index,
    load_material_question_seeds,
    load_persistent_search_engine,
)
from medical_audit_kb.indexing.pgvector_import import (
    build_pgvector_import_plan,
    render_pgvector_import_plan_markdown,
)
from medical_audit_kb.indexing.pgvector_writer import (
    render_pgvector_import_execution_markdown,
    run_pgvector_import,
)
from medical_audit_kb.ingestion.pipeline import KnowledgeIndexPipeline
from medical_audit_kb.preview.resolver import PreviewResolver
from medical_audit_kb.retrieval.postgres_search import load_postgres_hybrid_search_engine

PREVIEW_LINK_PATTERN = re.compile(r'href="(?P<path>/pages/preview/[0-9a-fA-F-]+)"')


class ClientResponse(Protocol):
    status_code: int
    text: str

    def json(self) -> object: ...


class ApiTestClient(Protocol):
    def get(
        self,
        path: str,
        *,
        params: dict[str, object] | None = None,
    ) -> ClientResponse: ...

    def post(
        self,
        path: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
    ) -> ClientResponse: ...


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "acceptance-run":
        return _acceptance_run(args)
    if args.command == "index-build":
        return _index_build(args)
    if args.command == "index-incremental-plan":
        return _index_incremental_plan(args)
    if args.command == "evaluate-index":
        return _evaluate_index(args)
    if args.command == "evaluate-postgres-index":
        return _evaluate_postgres_index(args)
    if args.command == "evaluate-answers":
        return _evaluate_answers(args)
    if args.command == "answer-provider-smoke":
        return _answer_provider_smoke(args)
    if args.command == "pgvector-import-plan":
        return _pgvector_import_plan(args)
    if args.command == "pgvector-import":
        return _pgvector_import(args)
    if args.command == "index-activate":
        return _index_activate(args)
    if args.command == "index-rollback":
        return _index_rollback(args)
    if args.command == "his-ddl-parse":
        return _his_ddl_parse(args)
    if args.command == "his-sample-quality":
        return _his_sample_quality(args)
    if args.command == "his-snapshot-plan":
        return _his_snapshot_plan(args)
    if args.command == "his-snapshot-apply":
        return _his_snapshot_apply(args)
    if args.command == "his-staging-import":
        return _his_staging_import(args)
    if args.command == "ui-smoke":
        return _ui_smoke(args)
    _die(f"unsupported command: {args.command}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="medical-audit-kb")
    subparsers = parser.add_subparsers(dest="command", required=True)
    acceptance = subparsers.add_parser(
        "acceptance-run",
        help="Run read-only source package indexing acceptance and write a report.",
    )
    acceptance.add_argument("--source-root", required=True, type=Path)
    acceptance.add_argument("--output", required=True, type=Path)
    acceptance.add_argument("--json-output", type=Path)
    acceptance.add_argument("--package-version-key")

    index_build = subparsers.add_parser(
        "index-build",
        help="Build durable local vector and BM25 artifacts from source materials.",
    )
    index_build.add_argument("--source-root", required=True, type=Path)
    index_build.add_argument("--index-root", required=True, type=Path)
    index_build.add_argument("--json-output", type=Path)
    index_build.add_argument("--package-version-key")
    _add_embedding_provider_args(index_build)
    index_build.add_argument("--max-chunks", type=int)
    index_build.add_argument(
        "--resume",
        action="store_true",
        help="Reuse existing matching embeddings.jsonl rows and append missing rows.",
    )

    incremental_plan = subparsers.add_parser(
        "index-incremental-plan",
        help="Build a read-only incremental update plan from the active PostgreSQL index.",
    )
    incremental_plan.add_argument("--source-root", required=True, type=Path)
    incremental_plan.add_argument("--package-version-key")
    incremental_plan.add_argument("--output", required=True, type=Path)
    incremental_plan.add_argument("--json-output", type=Path)
    incremental_plan.add_argument("--database-url-env", default=DATABASE_URL_ENV)

    evaluate = subparsers.add_parser(
        "evaluate-index",
        help="Evaluate a durable local index with auto-generated material questions.",
    )
    evaluate.add_argument("--source-root", required=True, type=Path)
    evaluate.add_argument("--index-root", required=True, type=Path)
    evaluate.add_argument("--output", required=True, type=Path)
    evaluate.add_argument("--json-output", type=Path)
    evaluate.add_argument("--cases-file", type=Path)
    evaluate.add_argument("--max-cases", type=int, default=25)
    evaluate.add_argument("--top-k", type=int, default=5)
    evaluate.add_argument("--query-terms", nargs="*")
    _add_embedding_provider_args(evaluate)

    evaluate_postgres = subparsers.add_parser(
        "evaluate-postgres-index",
        help="Evaluate PostgreSQL + pgvector retrieval path with fixed material cases.",
    )
    evaluate_postgres.add_argument("--source-root", required=True, type=Path)
    evaluate_postgres.add_argument("--output", required=True, type=Path)
    evaluate_postgres.add_argument("--json-output", type=Path)
    evaluate_postgres.add_argument("--cases-file", required=True, type=Path)
    evaluate_postgres.add_argument("--max-cases", type=int, default=25)
    evaluate_postgres.add_argument("--top-k", type=int, default=5)
    evaluate_postgres.add_argument("--database-url-env", default=DATABASE_URL_ENV)
    evaluate_postgres.add_argument(
        "--index-version-status",
        choices=("active", "candidate", "inactive"),
        default="active",
        help="PostgreSQL index version status to evaluate. Defaults to active.",
    )
    evaluate_postgres.add_argument(
        "--index-version-key",
        help="Optional exact index_versions.version_key to evaluate within the selected status.",
    )
    _add_embedding_provider_args(evaluate_postgres)

    answer_evaluate = subparsers.add_parser(
        "evaluate-answers",
        help="Evaluate citation-backed answer quality on a durable local index.",
    )
    answer_evaluate.add_argument("--index-root", required=True, type=Path)
    answer_evaluate.add_argument("--cases-file", required=True, type=Path)
    answer_evaluate.add_argument("--output", required=True, type=Path)
    answer_evaluate.add_argument("--json-output", type=Path)
    answer_evaluate.add_argument("--max-cases", type=int, default=25)
    answer_evaluate.add_argument("--top-k", type=int, default=5)
    _add_embedding_provider_args(answer_evaluate)
    _add_answer_generation_provider_args(answer_evaluate)

    answer_provider_smoke = subparsers.add_parser(
        "answer-provider-smoke",
        help="Preflight an OpenAI-compatible answer provider before full evaluation.",
    )
    answer_provider_smoke.add_argument("--output", required=True, type=Path)
    answer_provider_smoke.add_argument("--json-output", type=Path)
    _add_answer_generation_provider_args(answer_provider_smoke)

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

    his_ddl_parse = subparsers.add_parser(
        "his-ddl-parse",
        help="Parse HIS DDL into table schema and field dictionary report artifacts.",
    )
    his_ddl_parse.add_argument("--ddl-file", required=True, type=Path)
    his_ddl_parse.add_argument("--output", required=True, type=Path)
    his_ddl_parse.add_argument("--json-output", type=Path)

    his_sample_quality = subparsers.add_parser(
        "his-sample-quality",
        help="Validate deidentified HIS sample files against a parsed DDL report.",
    )
    his_sample_quality.add_argument("--sample-root", required=True, type=Path)
    his_sample_quality.add_argument("--ddl-report-json", type=Path)
    his_sample_quality.add_argument("--output", required=True, type=Path)
    his_sample_quality.add_argument("--json-output", type=Path)

    his_snapshot_plan = subparsers.add_parser(
        "his-snapshot-plan",
        help="Build a validated HIS audit_data_snapshots payload from a sample quality report.",
    )
    his_snapshot_plan.add_argument("--quality-report-json", required=True, type=Path)
    his_snapshot_plan.add_argument("--project-id", required=True)
    his_snapshot_plan.add_argument("--snapshot-key", required=True)
    his_snapshot_plan.add_argument("--source-batch-key", required=True)
    his_snapshot_plan.add_argument("--time-range-json", default="{}")
    his_snapshot_plan.add_argument("--status", default="validated")
    his_snapshot_plan.add_argument("--output", required=True, type=Path)
    his_snapshot_plan.add_argument("--json-output", type=Path)

    his_snapshot_apply = subparsers.add_parser(
        "his-snapshot-apply",
        help="Dry-run or write a validated HIS snapshot plan into audit_data_snapshots.",
    )
    his_snapshot_apply.add_argument("--snapshot-plan-json", required=True, type=Path)
    his_snapshot_apply.add_argument("--database-url-env", default=DATABASE_URL_ENV)
    his_snapshot_apply.add_argument("--output", required=True, type=Path)
    his_snapshot_apply.add_argument("--json-output", type=Path)
    his_snapshot_apply.add_argument(
        "--execute",
        action="store_true",
        help="Actually insert audit_data_snapshots. Omit this flag to run dry-run only.",
    )
    his_snapshot_apply.add_argument(
        "--create-schema",
        action="store_true",
        help="Create SQLAlchemy schema before running. Intended for local fixtures only.",
    )

    his_staging_import = subparsers.add_parser(
        "his-staging-import",
        help="Dry-run or write validated HIS sample rows into his_staging_rows.",
    )
    his_staging_import.add_argument("--quality-report-json", required=True, type=Path)
    his_staging_import.add_argument("--source-batch-key", required=True)
    his_staging_import.add_argument("--database-url-env", default=DATABASE_URL_ENV)
    his_staging_import.add_argument("--output", required=True, type=Path)
    his_staging_import.add_argument("--json-output", type=Path)
    his_staging_import.add_argument(
        "--execute",
        action="store_true",
        help="Actually insert his_staging_rows. Omit this flag to run dry-run only.",
    )
    his_staging_import.add_argument(
        "--create-schema",
        action="store_true",
        help="Create SQLAlchemy schema before running. Intended for local fixtures only.",
    )

    ui_smoke = subparsers.add_parser(
        "ui-smoke",
        help="Run API UI smoke through PostgreSQL backend load, query page, and preview page.",
    )
    ui_smoke.add_argument("--question", default="医保基金审核依据")
    ui_smoke.add_argument("--json-output", required=True, type=Path)
    ui_smoke.add_argument("--embedding-provider", choices=("fake", "openai"), default="openai")
    ui_smoke.add_argument("--embedding-model", default="kimi-for-coding")
    ui_smoke.add_argument("--embedding-dimension", type=int, default=1024)
    ui_smoke.add_argument("--api-key-env", default="KIMI_API_KEY")
    ui_smoke.add_argument("--embedding-base-url", default="https://api.kimi.com/coding/v1")
    ui_smoke.add_argument("--embedding-batch-size", type=int, default=16)
    return parser


def _acceptance_run(args: argparse.Namespace) -> int:
    run_result = KnowledgeIndexPipeline().run_full_rebuild(
        args.source_root,
        package_version_key=args.package_version_key,
    )
    report = build_acceptance_report(run_result)
    _write_text(args.output, render_acceptance_report_markdown(report))
    if args.json_output is not None:
        _write_text(
            args.json_output,
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        )
    return 0 if report.passed else 2


def _index_build(args: argparse.Namespace) -> int:
    embedding_provider = _embedding_provider_from_args(args)
    result = build_persistent_index(
        args.source_root,
        args.index_root,
        package_version_key=args.package_version_key,
        embedding_provider=embedding_provider,
        max_chunks=args.max_chunks,
        resume=args.resume,
    )
    if args.json_output is not None:
        _write_text(
            args.json_output,
            json.dumps(result.summary, ensure_ascii=False, indent=2) + "\n",
        )
    return 0


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


def _evaluate_index(args: argparse.Namespace) -> int:
    embedding_provider = _embedding_provider_from_args(args)
    search_engine = load_persistent_search_engine(
        args.index_root,
        embedding_provider=embedding_provider,
    )
    if args.cases_file is not None:
        cases = load_evaluation_cases(args.cases_file)[: args.max_cases]
    else:
        seeds = load_material_question_seeds(
            args.index_root,
            max_cases=args.max_cases,
            query_terms=tuple(args.query_terms or ()),
        )
        cases = generate_candidate_cases_from_materials(
            seeds,
            case_id_prefix="real-data-auto",
            max_cases=args.max_cases,
        )
    summary = evaluate_retrieval(
        cases,
        search_engine,
        top_k=args.top_k,
        preview_resolver=PreviewResolver(source_root=args.source_root),
    )
    _write_text(
        args.output,
        render_evaluation_summary_markdown(
            summary,
            embedding_provider=embedding_provider.provider,
            embedding_model=embedding_provider.model_name,
            embedding_dimension=embedding_provider.dimension,
            index_root=str(args.index_root),
        ),
    )
    if args.json_output is not None:
        _write_text(
            args.json_output,
            json.dumps(summary.to_dict(), ensure_ascii=False, indent=2) + "\n",
        )
    return 0


def _evaluate_postgres_index(args: argparse.Namespace) -> int:
    database_url = _database_url_from_env(args.database_url_env)
    embedding_provider = _embedding_provider_from_args(args)
    search_engine = load_postgres_hybrid_search_engine(
        database_url=database_url,
        embedding_provider=embedding_provider,
        index_version_status=args.index_version_status,
        index_version_key=args.index_version_key,
    )
    cases = load_evaluation_cases(args.cases_file)[: args.max_cases]
    summary = evaluate_retrieval(
        cases,
        search_engine,
        top_k=args.top_k,
        preview_resolver=PreviewResolver(source_root=args.source_root),
    )
    _write_text(
        args.output,
        render_evaluation_summary_markdown(
            summary,
            embedding_provider=embedding_provider.provider,
            embedding_model=embedding_provider.model_name,
            embedding_dimension=embedding_provider.dimension,
            index_root=(
                f"postgres:{args.database_url_env}:"
                f"{args.index_version_status}:{args.index_version_key or '*'}"
            ),
        ),
    )
    if args.json_output is not None:
        _write_text(
            args.json_output,
            json.dumps(summary.to_dict(), ensure_ascii=False, indent=2) + "\n",
        )
    return 0


def _evaluate_answers(args: argparse.Namespace) -> int:
    embedding_provider = _embedding_provider_from_args(args)
    generation_provider = _answer_generation_provider_from_args(args)
    search_engine = load_persistent_search_engine(
        args.index_root,
        embedding_provider=embedding_provider,
    )
    cases = load_answer_evaluation_cases(args.cases_file)[: args.max_cases]
    summary = evaluate_answers(
        cases,
        search_engine,
        top_k=args.top_k,
        generation_provider=generation_provider,
        require_generation_success=(
            generation_provider is not None and not args.allow_answer_fallback
        ),
    )
    _write_text(
        args.output,
        render_answer_evaluation_summary_markdown(
            summary,
            embedding_provider=embedding_provider.provider,
            embedding_model=embedding_provider.model_name,
            embedding_dimension=embedding_provider.dimension,
            answer_provider=(
                generation_provider.provider if generation_provider is not None else "fallback"
            ),
            answer_model=(
                generation_provider.model_name
                if generation_provider is not None
                else "citation-backed-fallback"
            ),
            index_root=str(args.index_root),
        ),
    )
    if args.json_output is not None:
        _write_text(
            args.json_output,
            json.dumps(summary.to_dict(), ensure_ascii=False, indent=2) + "\n",
        )
    return 0


def _answer_provider_smoke(args: argparse.Namespace) -> int:
    generation_provider = _answer_generation_provider_from_args(args)
    if generation_provider is None:
        _die("answer-provider-smoke requires --answer-provider openai")
    result = run_answer_provider_preflight(generation_provider)
    _write_text(args.output, render_answer_provider_preflight_markdown(result))
    if args.json_output is not None:
        _write_text(
            args.json_output,
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n",
        )
    return 0 if result.success else 2


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


def _his_ddl_parse(args: argparse.Namespace) -> int:
    report = parse_his_ddl(args.ddl_file.read_text(encoding="utf-8"))
    _write_text(
        args.output,
        render_his_ddl_parse_report_markdown(report, source_path=str(args.ddl_file)),
    )
    if args.json_output is not None:
        _write_text(args.json_output, his_ddl_parse_report_json(report))
    return 0 if report.status == "pass" else 2


def _his_sample_quality(args: argparse.Namespace) -> int:
    ddl_report = (
        load_his_ddl_parse_report_json(args.ddl_report_json)
        if args.ddl_report_json is not None
        else None
    )
    report = build_his_sample_quality_report(args.sample_root, ddl_report=ddl_report)
    _write_text(args.output, render_his_sample_quality_report_markdown(report))
    if args.json_output is not None:
        _write_text(args.json_output, his_sample_quality_report_json(report))
    return 0 if report.status == "pass" else 2


def _his_snapshot_plan(args: argparse.Namespace) -> int:
    quality_report = load_his_sample_quality_report_json(args.quality_report_json)
    plan = build_his_snapshot_plan(
        quality_report,
        project_id=UUID(args.project_id),
        snapshot_key=args.snapshot_key,
        source_batch_key=args.source_batch_key,
        time_range=_json_object_arg(args.time_range_json, name="time-range-json"),
        status=args.status,
    )
    _write_text(args.output, render_his_snapshot_plan_markdown(plan))
    if args.json_output is not None:
        _write_text(args.json_output, his_snapshot_plan_json(plan))
    return 0 if plan.status == "pass" else 2


def _his_snapshot_apply(args: argparse.Namespace) -> int:
    plan = load_his_snapshot_plan_json(args.snapshot_plan_json)
    result = asyncio.run(
        apply_his_snapshot_plan_to_database(
            plan,
            database_url=_database_url_from_env(args.database_url_env),
            execute=args.execute,
            create_schema_if_missing=args.create_schema,
        )
    )
    _write_text(args.output, render_his_snapshot_apply_markdown(result))
    if args.json_output is not None:
        _write_text(args.json_output, his_snapshot_apply_result_json(result))
    return 0 if result.status == "pass" else 2


def _his_staging_import(args: argparse.Namespace) -> int:
    quality_report = load_his_staging_sample_quality_report_json(args.quality_report_json)
    result = asyncio.run(
        import_his_sample_quality_to_staging_database(
            quality_report,
            source_batch_key=args.source_batch_key,
            database_url=_database_url_from_env(args.database_url_env),
            execute=args.execute,
            create_schema_if_missing=args.create_schema,
        )
    )
    _write_text(args.output, render_his_staging_import_markdown(result))
    if args.json_output is not None:
        _write_text(args.json_output, his_staging_import_result_json(result))
    return 0 if result.status == "pass" else 2


def _ui_smoke(args: argparse.Namespace) -> int:
    client = _create_api_test_client()
    postgres_response = client.get("/index/postgres-status")
    backend_response = client.post(
        "/index/search-backend/postgres",
        headers={"X-Role": "it-admin"},
        json={
            "embedding_provider": args.embedding_provider,
            "embedding_model": args.embedding_model,
            "embedding_dimension": args.embedding_dimension,
            "api_key_env": args.api_key_env,
            "embedding_base_url": args.embedding_base_url,
            "embedding_batch_size": args.embedding_batch_size,
        },
    )

    query_response: ClientResponse | None = None
    preview_response: ClientResponse | None = None
    preview_path: str | None = None
    if backend_response.status_code == 200:
        query_response = client.get("/pages/query", params={"question": args.question})
        if query_response.status_code == 200:
            preview_path = _first_preview_path(query_response.text)
            if preview_path is not None:
                preview_response = client.get(preview_path)

    result = {
        "success": (
            postgres_response.status_code == 200
            and backend_response.status_code == 200
            and _response_status_code(query_response) == 200
            and _response_status_code(preview_response) == 200
            and preview_path is not None
            and _response_text_contains(query_response, "引用型回答")
            and _response_text_contains(preview_response, "原文证据预览")
        ),
        "question": args.question,
        "postgres_status_code": postgres_response.status_code,
        "backend_load_status_code": backend_response.status_code,
        "query_page_status_code": _response_status_code(query_response),
        "preview_page_status_code": _response_status_code(preview_response),
        "preview_path": preview_path,
        "postgres_status": _response_json(postgres_response),
        "backend_load": _response_json(backend_response),
    }
    _write_text(args.json_output, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 0 if result["success"] else 2


def _answer_generation_provider_from_args(
    args: argparse.Namespace,
) -> AnswerGenerationProvider | None:
    if args.answer_provider == "fallback":
        return None
    if args.answer_provider == "anthropic":
        return AnthropicAnswerGenerationProvider.from_env(
            api_key_env=args.answer_api_key_env,
            model_name=args.answer_model,
            base_url=args.answer_base_url or "https://api.anthropic.com",
            max_output_tokens=args.answer_max_output_tokens,
            temperature=args.answer_temperature,
        )
    return OpenAICompatibleAnswerGenerationProvider.from_env(
        api_key_env=args.answer_api_key_env,
        model_name=args.answer_model,
        base_url=args.answer_base_url or "https://api.openai.com/v1",
        max_output_tokens=args.answer_max_output_tokens,
        temperature=args.answer_temperature,
    )


def _embedding_provider_from_args(args: argparse.Namespace) -> EmbeddingProvider:
    if args.embedding_provider == "fake":
        return cast(
            EmbeddingProvider,
            DeterministicFakeEmbeddingProvider(dimension=args.embedding_dimension or 32),
        )
    return OpenAICompatibleEmbeddingProvider.from_env(
        api_key_env=args.api_key_env,
        model_name=args.embedding_model,
        dimension=args.embedding_dimension,
        base_url=args.embedding_base_url,
        batch_size=args.embedding_batch_size,
    )


def _add_embedding_provider_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--embedding-provider", choices=("fake", "openai"), default="fake")
    parser.add_argument("--embedding-model", default="text-embedding-3-small")
    parser.add_argument("--embedding-dimension", type=int)
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--embedding-base-url", default="https://api.openai.com/v1")
    parser.add_argument("--embedding-batch-size", type=int, default=128)


def _add_answer_generation_provider_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--answer-provider",
        choices=("fallback", "openai", "anthropic"),
        default="fallback",
    )
    parser.add_argument("--answer-model", default="gpt-4.1-mini")
    parser.add_argument("--answer-api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--answer-base-url")
    parser.add_argument("--answer-max-output-tokens", type=int, default=600)
    parser.add_argument("--answer-temperature", type=float, default=0.0)
    parser.add_argument(
        "--allow-answer-fallback",
        action="store_true",
        help=(
            "Do not fail answer cases when the configured answer provider falls back "
            "to citation-backed fallback output."
        ),
    )


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _create_api_test_client() -> ApiTestClient:
    from fastapi.testclient import TestClient

    from medical_audit_kb.api.app import create_app

    return cast(ApiTestClient, TestClient(create_app()))


def _first_preview_path(html: str) -> str | None:
    match = PREVIEW_LINK_PATTERN.search(html)
    return match.group("path") if match is not None else None


def _response_status_code(response: ClientResponse | None) -> int | None:
    return None if response is None else int(response.status_code)


def _response_text_contains(response: ClientResponse | None, needle: str) -> bool:
    return response is not None and needle in str(response.text)


def _response_json(response: ClientResponse | None) -> object:
    if response is None:
        return None
    try:
        return response.json()
    except ValueError:
        return None


def _database_url_from_env(env_name: str) -> str:
    import os

    database_url = os.getenv(env_name)
    if not database_url:
        _die(f"missing database url env: {env_name}")
    return database_url


def _json_object_arg(value: str, *, name: str) -> dict[str, object]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        _die(f"{name} must be a JSON object")
    return cast(dict[str, object], parsed)


def _die(message: str) -> NoReturn:
    raise SystemExit(message)


if __name__ == "__main__":
    raise SystemExit(main())
