from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from medical_audit_kb.db.engine import create_schema, create_session_factory
from medical_audit_kb.db.models import HisSourceBatch, HisStagingRow, HisTableSchema
from medical_audit_kb.db.repositories import HisIngestionRepository
from medical_audit_kb.domain.schemas import HisStagingRowCreate
from medical_audit_kb.his.sample_quality import HisSampleQualityReport, load_his_sample_rows


class HisStagingImportTableResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    table_name: str
    file_path: str
    planned_row_count: int
    existing_row_count: int
    inserted_row_count: int
    table_schema_id: UUID | None


class HisStagingImportResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["pass", "fail"]
    execute_requested: bool
    executed: bool
    dry_run: bool
    source_batch_key: str
    source_batch_id: UUID | None
    planned_row_count: int
    inserted_row_count: int
    table_results: tuple[HisStagingImportTableResult, ...]
    issues: tuple[str, ...]


async def import_his_sample_quality_to_staging_database(
    quality_report: HisSampleQualityReport,
    *,
    source_batch_key: str,
    database_url: str,
    execute: bool = False,
    create_schema_if_missing: bool = False,
) -> HisStagingImportResult:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        return await import_his_sample_quality_to_staging_with_engine(
            quality_report,
            source_batch_key=source_batch_key,
            engine=engine,
            execute=execute,
            create_schema_if_missing=create_schema_if_missing,
        )
    finally:
        await engine.dispose()


async def import_his_sample_quality_to_staging_with_engine(
    quality_report: HisSampleQualityReport,
    *,
    source_batch_key: str,
    engine: AsyncEngine,
    execute: bool = False,
    create_schema_if_missing: bool = False,
) -> HisStagingImportResult:
    if create_schema_if_missing:
        await create_schema(engine)

    session_factory = create_session_factory(engine)
    async with session_factory() as session, session.begin():
        source_batch = (
            await session.execute(
                select(HisSourceBatch).where(HisSourceBatch.batch_key == source_batch_key)
            )
        ).scalar_one_or_none()
        table_schemas = (
            []
            if source_batch is None
            else list(
                (
                    await session.execute(
                        select(HisTableSchema).where(
                            HisTableSchema.source_batch_id == source_batch.id
                        )
                    )
                )
                .scalars()
                .all()
            )
        )
        schema_by_table = {schema.table_name: schema for schema in table_schemas}

        issues = list(_quality_report_issues(quality_report, source_batch_key, source_batch))
        table_results: list[HisStagingImportTableResult] = []
        payloads: list[HisStagingRowCreate] = []

        for table in quality_report.tables:
            table_schema = schema_by_table.get(table.table_name)
            existing_count = 0
            if source_batch is not None:
                existing_rows = (
                    await session.execute(
                        select(HisStagingRow).where(
                            HisStagingRow.source_batch_id == source_batch.id,
                            HisStagingRow.table_name == table.table_name,
                        )
                    )
                ).scalars()
                existing_count = len(existing_rows.all())
            if table_schema is None:
                issues.append(
                    f"table schema not found for batch {source_batch_key}: {table.table_name}"
                )
            if existing_count:
                issues.append(
                    f"staging rows already exist for {source_batch_key}/{table.table_name}: "
                    f"{existing_count}"
                )

            rows = _load_rows_for_table(table.file_path, table.table_name, issues)
            if len(rows) != table.row_count:
                issues.append(
                    f"sample row count changed for {table.table_name}: "
                    f"quality={table.row_count}, file={len(rows)}"
                )

            table_results.append(
                HisStagingImportTableResult(
                    table_name=table.table_name,
                    file_path=table.file_path,
                    planned_row_count=len(rows),
                    existing_row_count=existing_count,
                    inserted_row_count=0,
                    table_schema_id=table_schema.id if table_schema is not None else None,
                )
            )
            if source_batch is None or table_schema is None:
                continue
            payloads.extend(
                _staging_payloads(
                    source_batch_id=source_batch.id,
                    table_schema_id=table_schema.id,
                    table_name=table.table_name,
                    file_path=table.file_path,
                    file_sha256=table.file_sha256,
                    rows=rows,
                )
            )

        if issues or not execute:
            return _result(
                status="fail" if issues else "pass",
                execute_requested=execute,
                source_batch_key=source_batch_key,
                source_batch_id=source_batch.id if source_batch is not None else None,
                table_results=tuple(table_results),
                issues=tuple(dict.fromkeys(issues)),
            )

        inserted_rows = await HisIngestionRepository(session).add_staging_rows(payloads)
        inserted_by_table = _inserted_by_table(inserted_rows)
        return _result(
            status="pass",
            execute_requested=execute,
            source_batch_key=source_batch_key,
            source_batch_id=source_batch.id if source_batch is not None else None,
            table_results=tuple(
                table_result.model_copy(
                    update={
                        "inserted_row_count": inserted_by_table.get(table_result.table_name, 0),
                    }
                )
                for table_result in table_results
            ),
            issues=(),
        )


def load_his_staging_sample_quality_report_json(path: Path) -> HisSampleQualityReport:
    return HisSampleQualityReport.model_validate_json(path.read_text(encoding="utf-8"))


def render_his_staging_import_markdown(result: HisStagingImportResult) -> str:
    lines = [
        "# HIS 脱敏样本 staging 导入报告",
        "",
        f"- 总体状态：`{result.status.upper()}`",
        f"- 请求写入：`{str(result.execute_requested).lower()}`",
        f"- 执行写入：`{str(result.executed).lower()}`",
        f"- dry_run：`{str(result.dry_run).lower()}`",
        f"- source_batch_key：`{result.source_batch_key}`",
        f"- source_batch_id：`{result.source_batch_id or '-'}`",
        f"- 计划行数：`{result.planned_row_count}`",
        f"- 写入行数：`{result.inserted_row_count}`",
    ]
    if result.issues:
        lines.extend(["", "## 阻断问题"])
        lines.extend(f"- {issue}" for issue in result.issues)
    lines.extend(
        [
            "",
            "## 表级导入计划",
            "",
            "| 表 | 计划行数 | 已存在行数 | 写入行数 | table_schema_id |",
            "| --- | ---: | ---: | ---: | --- |",
        ]
    )
    for table_result in result.table_results:
        lines.append(
            f"| `{table_result.table_name}` | {table_result.planned_row_count} | "
            f"{table_result.existing_row_count} | {table_result.inserted_row_count} | "
            f"`{table_result.table_schema_id or '-'}` |"
        )
    return "\n".join(lines) + "\n"


def his_staging_import_result_json(result: HisStagingImportResult) -> str:
    return json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"


def _quality_report_issues(
    quality_report: HisSampleQualityReport,
    source_batch_key: str,
    source_batch: HisSourceBatch | None,
) -> tuple[str, ...]:
    issues = list(quality_report.issues)
    if quality_report.status != "pass":
        issues.append("sample quality report is not PASS")
    if not quality_report.tables:
        issues.append("sample quality report has no tables")
    if source_batch is None:
        issues.append(f"his source batch not found: {source_batch_key}")
    for table in quality_report.tables:
        if table.status != "pass":
            issues.append(f"table quality is not PASS: {table.table_name}")
    return tuple(issues)


def _load_rows_for_table(
    file_path: str,
    table_name: str,
    issues: list[str],
) -> tuple[dict[str, str], ...]:
    path = Path(file_path)
    try:
        return tuple(load_his_sample_rows(path))
    except (OSError, ValueError) as exc:
        issues.append(f"failed to read sample rows for {table_name}: {exc}")
        return ()


def _staging_payloads(
    *,
    source_batch_id: UUID,
    table_schema_id: UUID,
    table_name: str,
    file_path: str,
    file_sha256: str,
    rows: tuple[dict[str, str], ...],
) -> list[HisStagingRowCreate]:
    return [
        HisStagingRowCreate(
            source_batch_id=source_batch_id,
            table_schema_id=table_schema_id,
            table_name=table_name,
            row_number=index,
            row_data=dict(row),
            row_hash=_row_hash(row),
            status="staged",
            metadata={
                "source": "his-staging-import",
                "file_path": file_path,
                "file_sha256": file_sha256,
            },
        )
        for index, row in enumerate(rows, start=1)
    ]


def _row_hash(row: dict[str, Any]) -> str:
    canonical = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _inserted_by_table(rows: list[HisStagingRow]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.table_name] = counts.get(row.table_name, 0) + 1
    return counts


def _result(
    *,
    status: Literal["pass", "fail"],
    execute_requested: bool,
    source_batch_key: str,
    source_batch_id: UUID | None,
    table_results: tuple[HisStagingImportTableResult, ...],
    issues: tuple[str, ...],
) -> HisStagingImportResult:
    inserted_row_count = sum(table.inserted_row_count for table in table_results)
    return HisStagingImportResult(
        status=status,
        execute_requested=execute_requested,
        executed=execute_requested and status == "pass",
        dry_run=not execute_requested,
        source_batch_key=source_batch_key,
        source_batch_id=source_batch_id,
        planned_row_count=sum(table.planned_row_count for table in table_results),
        inserted_row_count=inserted_row_count,
        table_results=table_results,
        issues=issues,
    )
