from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from medical_audit_kb.domain.schemas import HisTableSchemaCreate


class HisDdlColumn(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    data_type: str
    nullable: bool
    primary_key: bool
    raw_definition: str
    comment: str | None = None


class HisDdlTable(BaseModel):
    model_config = ConfigDict(frozen=True)

    table_name: str
    business_domain: str
    ddl_hash: str
    columns: tuple[HisDdlColumn, ...]
    primary_key_fields: tuple[str, ...]
    time_fields: tuple[str, ...]
    raw_statement: str
    table_comment: str | None = None


class HisDdlParseIssue(BaseModel):
    model_config = ConfigDict(frozen=True)

    severity: Literal["error", "warning"]
    message: str
    statement_preview: str | None = None


class HisDdlParseReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["pass", "fail"]
    table_count: int
    tables: tuple[HisDdlTable, ...]
    issues: tuple[HisDdlParseIssue, ...]


_CONSTRAINT_PREFIXES = (
    "CONSTRAINT",
    "PRIMARY",
    "UNIQUE",
    "FOREIGN",
    "CHECK",
    "KEY",
    "INDEX",
)
_COLUMN_CONSTRAINT_KEYWORDS = {
    "NOT",
    "NULL",
    "PRIMARY",
    "REFERENCES",
    "DEFAULT",
    "COMMENT",
    "COLLATE",
    "CONSTRAINT",
    "UNIQUE",
    "CHECK",
    "GENERATED",
    "IDENTITY",
    "ENABLE",
    "DISABLE",
}
_COMMENT_ON_COLUMN_RE = re.compile(
    r"COMMENT\s+ON\s+COLUMN\s+(?P<table>[^\s.]+(?:\.[^\s.]+)?)\.(?P<column>[^\s]+)"
    r"\s+IS\s+(?P<quote>['\"])(?P<comment>.*?)(?P=quote)",
    re.IGNORECASE | re.DOTALL,
)
_COMMENT_ON_TABLE_RE = re.compile(
    r"COMMENT\s+ON\s+TABLE\s+(?P<table>[^\s;]+)\s+IS\s+"
    r"(?P<quote>['\"])(?P<comment>.*?)(?P=quote)",
    re.IGNORECASE | re.DOTALL,
)


def parse_his_ddl(ddl_text: str) -> HisDdlParseReport:
    statements = tuple(_split_sql_statements(_strip_sql_comments(ddl_text)))
    column_comments = _column_comments(ddl_text)
    table_comments = _table_comments(ddl_text)
    tables: list[HisDdlTable] = []
    issues: list[HisDdlParseIssue] = []

    for statement in statements:
        if not statement.strip():
            continue
        if not _is_create_table_statement(statement):
            continue
        try:
            tables.append(_parse_create_table(statement, column_comments, table_comments))
        except ValueError as exc:
            issues.append(
                HisDdlParseIssue(
                    severity="error",
                    message=str(exc),
                    statement_preview=statement.strip()[:160],
                )
            )

    if not tables:
        issues.append(
            HisDdlParseIssue(
                severity="error",
                message="no CREATE TABLE statements were parsed",
            )
        )
    status: Literal["pass", "fail"] = (
        "fail" if any(issue.severity == "error" for issue in issues) else "pass"
    )
    return HisDdlParseReport(
        status=status,
        table_count=len(tables),
        tables=tuple(tables),
        issues=tuple(issues),
    )


def build_his_table_schema_payloads(
    report: HisDdlParseReport,
    *,
    source_batch_id: UUID,
    batch_key: str,
    status: str = "parsed",
) -> tuple[HisTableSchemaCreate, ...]:
    if report.status != "pass":
        raise ValueError("cannot build table schema payloads from failed DDL parse report")
    return tuple(
        HisTableSchemaCreate(
            schema_key=_schema_key(batch_key, table),
            source_batch_id=source_batch_id,
            table_name=table.table_name,
            business_domain=table.business_domain,
            ddl_text=table.raw_statement,
            ddl_hash=table.ddl_hash,
            field_dictionary=_field_dictionary(table),
            primary_key_fields=list(table.primary_key_fields),
            time_fields=list(table.time_fields),
            status=status,
            metadata={"parser": "simple-his-ddl-v1"},
        )
        for table in report.tables
    )


def render_his_ddl_parse_report_markdown(
    report: HisDdlParseReport,
    *,
    source_path: str | None = None,
) -> str:
    lines = [
        "# HIS DDL 解析报告",
        "",
        f"- 总体状态：`{report.status.upper()}`",
        f"- 表数量：`{report.table_count}`",
    ]
    if source_path is not None:
        lines.append(f"- DDL 文件：`{source_path}`")
    if report.issues:
        lines.extend(["", "## 解析问题"])
        for issue in report.issues:
            lines.append(f"- `{issue.severity}`：{issue.message}")
    for table in report.tables:
        lines.extend(
            [
                "",
                f"## {table.table_name}",
                "",
                f"- 业务域推断：`{table.business_domain}`",
                f"- DDL hash：`{table.ddl_hash}`",
                f"- 主键字段：`{', '.join(table.primary_key_fields) or '-'}`",
                f"- 时间字段：`{', '.join(table.time_fields) or '-'}`",
                "",
                "| 字段 | 类型 | 可空 | 主键 | 注释 |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for column in table.columns:
            lines.append(
                "| "
                f"`{column.name}` | `{column.data_type}` | "
                f"{'是' if column.nullable else '否'} | "
                f"{'是' if column.primary_key else '否'} | "
                f"{column.comment or ''} |"
            )
    return "\n".join(lines) + "\n"


def his_ddl_parse_report_json(report: HisDdlParseReport) -> str:
    return json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"


def _parse_create_table(
    statement: str,
    column_comments: dict[tuple[str, str], str],
    table_comments: dict[str, str],
) -> HisDdlTable:
    open_index = statement.find("(")
    if open_index < 0:
        raise ValueError("CREATE TABLE statement has no column body")
    close_index = _matching_closing_paren(statement, open_index)
    if close_index is None:
        raise ValueError("CREATE TABLE statement has unbalanced parentheses")

    table_name = _table_name_from_header(statement[:open_index])
    body = statement[open_index + 1 : close_index]
    definitions = tuple(_split_top_level_csv(body))
    primary_key_fields: list[str] = []
    columns: list[HisDdlColumn] = []

    for definition in definitions:
        normalized_definition = definition.strip()
        if not normalized_definition:
            continue
        if _is_table_constraint(normalized_definition):
            primary_key_fields.extend(_primary_key_fields_from_constraint(normalized_definition))
            continue
        column, inline_primary_key = _parse_column_definition(
            normalized_definition,
            table_name=table_name,
            column_comments=column_comments,
        )
        columns.append(column)
        if inline_primary_key:
            primary_key_fields.append(column.name)

    primary_key_fields = _unique_preserve_order(primary_key_fields)
    if not columns:
        raise ValueError(f"CREATE TABLE {table_name} has no parsed columns")

    columns_by_name = {column.name: column for column in columns}
    normalized_columns = tuple(
        column.model_copy(update={"primary_key": column.name in primary_key_fields})
        for column in columns
    )
    time_fields = tuple(
        column.name
        for column in normalized_columns
        if _is_time_field(column.name, column.data_type)
    )
    unknown_primary_keys = [field for field in primary_key_fields if field not in columns_by_name]
    if unknown_primary_keys:
        raise ValueError(
            f"CREATE TABLE {table_name} references unknown primary key fields: "
            f"{', '.join(unknown_primary_keys)}"
        )

    return HisDdlTable(
        table_name=table_name,
        business_domain=_infer_business_domain(table_name),
        ddl_hash=_ddl_hash(statement),
        columns=normalized_columns,
        primary_key_fields=tuple(primary_key_fields),
        time_fields=time_fields,
        raw_statement=statement.strip(),
        table_comment=table_comments.get(_identifier_key(table_name)),
    )


def _parse_column_definition(
    definition: str,
    *,
    table_name: str,
    column_comments: dict[tuple[str, str], str],
) -> tuple[HisDdlColumn, bool]:
    tokens = _definition_tokens(definition)
    if len(tokens) < 2:
        raise ValueError(f"column definition is incomplete: {definition}")
    column_name = _normalize_identifier(tokens[0])
    data_type_parts: list[str] = []
    for token in tokens[1:]:
        if token.upper() in _COLUMN_CONSTRAINT_KEYWORDS:
            break
        data_type_parts.append(token)
    if not data_type_parts:
        raise ValueError(f"column data type is missing: {definition}")
    normalized_definition = definition.upper()
    inline_primary_key = "PRIMARY KEY" in normalized_definition
    nullable = "NOT NULL" not in normalized_definition and not inline_primary_key
    comment = _inline_column_comment(definition) or column_comments.get(
        (_identifier_key(table_name), _identifier_key(column_name))
    )
    return (
        HisDdlColumn(
            name=column_name,
            data_type=" ".join(data_type_parts),
            nullable=nullable,
            primary_key=inline_primary_key,
            raw_definition=definition,
            comment=comment,
        ),
        inline_primary_key,
    )


def _split_sql_statements(sql: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escaped = False
    for char in sql:
        current.append(char)
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
        elif char == ";":
            statement = "".join(current).strip().rstrip(";").strip()
            if statement:
                statements.append(statement)
            current = []
    trailing = "".join(current).strip()
    if trailing:
        statements.append(trailing)
    return statements


def _split_top_level_csv(text: str) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    depth = 0
    quote: str | None = None
    escaped = False
    for char in text:
        if quote is not None:
            current.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            current.append(char)
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            item = "".join(current).strip()
            if item:
                items.append(item)
            current = []
        else:
            current.append(char)
    item = "".join(current).strip()
    if item:
        items.append(item)
    return items


def _matching_closing_paren(text: str, open_index: int) -> int | None:
    depth = 0
    quote: str | None = None
    escaped = False
    for index, char in enumerate(text[open_index:], start=open_index):
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return None


def _definition_tokens(definition: str) -> list[str]:
    return re.findall(r'"[^"]+"|`[^`]+`|\[[^\]]+\]|[^\s]+', definition)


def _primary_key_fields_from_constraint(definition: str) -> list[str]:
    match = re.search(r"PRIMARY\s+KEY\s*\((?P<fields>.*?)\)", definition, re.IGNORECASE)
    if match is None:
        return []
    return [
        _normalize_identifier(item.strip()) for item in _split_top_level_csv(match.group("fields"))
    ]


def _table_name_from_header(header: str) -> str:
    normalized_header = re.sub(
        r"^\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?",
        "",
        header,
        flags=re.IGNORECASE,
    ).strip()
    if not normalized_header:
        raise ValueError("CREATE TABLE statement has no table name")
    return ".".join(
        _normalize_identifier(part) for part in _split_identifier_path(normalized_header)
    )


def _split_identifier_path(identifier: str) -> list[str]:
    return [part.strip() for part in identifier.split(".") if part.strip()]


def _normalize_identifier(identifier: str) -> str:
    value = identifier.strip().rstrip(",")
    if value.startswith(('"', "`", "[")) and value.endswith(('"', "`", "]")):
        value = value[1:-1]
    return value


def _identifier_key(identifier: str) -> str:
    return _normalize_identifier(identifier).replace('"', "").replace("`", "").upper()


def _is_create_table_statement(statement: str) -> bool:
    return bool(re.match(r"^\s*CREATE\s+TABLE\b", statement, flags=re.IGNORECASE))


def _is_table_constraint(definition: str) -> bool:
    first_token = _definition_tokens(definition)[0].upper()
    return first_token in _CONSTRAINT_PREFIXES


def _strip_sql_comments(sql: str) -> str:
    without_block_comments = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return re.sub(r"--.*?$", "", without_block_comments, flags=re.MULTILINE)


def _column_comments(sql: str) -> dict[tuple[str, str], str]:
    comments: dict[tuple[str, str], str] = {}
    for match in _COMMENT_ON_COLUMN_RE.finditer(sql):
        comments[
            (_identifier_key(match.group("table")), _identifier_key(match.group("column")))
        ] = _unescape_sql_string(match.group("comment"))
    return comments


def _table_comments(sql: str) -> dict[str, str]:
    return {
        _identifier_key(match.group("table")): _unescape_sql_string(match.group("comment"))
        for match in _COMMENT_ON_TABLE_RE.finditer(sql)
    }


def _inline_column_comment(definition: str) -> str | None:
    match = re.search(
        r"\bCOMMENT\s+(?P<quote>['\"])(?P<comment>.*?)(?P=quote)",
        definition,
        re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        return None
    return _unescape_sql_string(match.group("comment"))


def _unescape_sql_string(value: str) -> str:
    return value.replace("''", "'").strip()


def _is_time_field(column_name: str, data_type: str) -> bool:
    name = column_name.lower()
    data_type_lower = data_type.lower()
    return (
        "date" in name
        or "time" in name
        or name.endswith("_at")
        or "date" in data_type_lower
        or "time" in data_type_lower
        or "timestamp" in data_type_lower
    )


def _infer_business_domain(table_name: str) -> str:
    name = table_name.lower()
    if any(token in name for token in ("charge", "fee", "cost", "bill")):
        return "charge_detail"
    if any(token in name for token in ("diagnosis", "diag")):
        return "diagnosis"
    if any(token in name for token in ("order", "prescription", "recipe")):
        return "order_item"
    if any(token in name for token in ("catalog", "item", "price")):
        return "item_catalog"
    if any(token in name for token in ("dept", "department", "doctor", "staff")):
        return "department_staff"
    if any(token in name for token in ("visit", "encounter", "admission", "patient")):
        return "visit"
    return "unknown"


def _ddl_hash(statement: str) -> str:
    return hashlib.sha256(_normalize_sql_for_hash(statement).encode("utf-8")).hexdigest()


def _normalize_sql_for_hash(statement: str) -> str:
    return re.sub(r"\s+", " ", statement).strip()


def _schema_key(batch_key: str, table: HisDdlTable) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", table.table_name).strip("-").lower()
    return f"{batch_key}-{slug}-{table.ddl_hash[:12]}"


def _field_dictionary(table: HisDdlTable) -> dict[str, Any]:
    return {
        "table_comment": table.table_comment,
        "columns": [
            {
                "name": column.name,
                "data_type": column.data_type,
                "nullable": column.nullable,
                "primary_key": column.primary_key,
                "comment": column.comment,
                "raw_definition": column.raw_definition,
            }
            for column in table.columns
        ],
    }


def _unique_preserve_order(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
