#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

JsonObject = dict[str, object]

DEFAULT_API_TYPES_PATH = REPO_ROOT / "web/src/lib/api-types.ts"
DEFAULT_JSON_OUTPUT = REPO_ROOT / "tmp/outputs/frontend-backend-api-contract-schema-latest.json"
DEFAULT_MARKDOWN_OUTPUT = REPO_ROOT / "tmp/outputs/frontend-backend-api-contract-schema-latest.md"


@dataclass(frozen=True, slots=True)
class FrontendContract:
    surface: str
    function_name: str
    method: str
    path: str
    response_type: str
    request_type: str | None = None


FRONTEND_CONTRACTS: tuple[FrontendContract, ...] = (
    FrontendContract(
        "dashboard-status",
        "fetchBackendHealth",
        "get",
        "/api/backend/health",
        "BackendHealthResponse",
    ),
    FrontendContract(
        "search-status",
        "fetchSearchBackendStatus",
        "get",
        "/api/backend/index/search-backend",
        "SearchBackendStatusResponse",
    ),
    FrontendContract(
        "user-session-shell",
        "fetchAuthSession",
        "get",
        "/api/v1/auth/session",
        "AuthSessionResponse",
    ),
    FrontendContract(
        "knowledge-query",
        "runKnowledgeQuery",
        "post",
        "/api/v1/query",
        "QueryResponse",
        "QueryRequest",
    ),
    FrontendContract(
        "query-history",
        "fetchQueryHistory",
        "get",
        "/api/v1/query/logs",
        "QueryHistoryResponse",
    ),
    FrontendContract(
        "audit-findings",
        "fetchAuditFindings",
        "get",
        "/api/v1/audit-findings",
        "AuditFindingsResponse",
    ),
    FrontendContract(
        "reports",
        "fetchReportWorkbench",
        "get",
        "/api/v1/reports/workbench",
        "ReportWorkbenchResponse",
    ),
    FrontendContract(
        "graph",
        "fetchGraphWorkbench",
        "get",
        "/api/v1/graph/workbench",
        "GraphWorkbenchResponse",
    ),
    FrontendContract(
        "rules",
        "fetchRulesWorkbench",
        "get",
        "/api/v1/rules/workbench",
        "RulesWorkbenchResponse",
    ),
    FrontendContract(
        "remediation",
        "fetchRemediationWorkbench",
        "get",
        "/api/v1/remediation/workbench",
        "RemediationWorkbenchResponse",
    ),
    FrontendContract(
        "archive",
        "fetchArchiveWorkbench",
        "get",
        "/api/v1/archive/workbench",
        "ArchiveWorkbenchResponse",
    ),
    FrontendContract(
        "analytics-upload",
        "uploadAnalysisTable",
        "post",
        "/api/v1/analytics/table-upload",
        "TableAnalysisUploadResponse",
    ),
    FrontendContract(
        "analytics-history",
        "fetchAnalysisUploadHistory",
        "get",
        "/api/v1/analytics/table-uploads",
        "TableAnalysisUploadHistoryResponse",
    ),
    FrontendContract(
        "document-permissions",
        "fetchDocumentPermissions",
        "get",
        "/api/v1/documents/permissions",
        "DocumentPermissionsResponse",
    ),
    FrontendContract(
        "document-uploads",
        "fetchDocumentUploads",
        "get",
        "/api/v1/documents/uploads",
        "DocumentUploadListResponse",
    ),
    FrontendContract(
        "document-upload",
        "uploadPersonalDocument",
        "post",
        "/api/v1/documents/uploads",
        "DocumentUploadResponse",
    ),
    FrontendContract(
        "document-governance",
        "updateDocumentUploadGovernance",
        "post",
        "/api/v1/documents/uploads/{upload_id}/governance",
        "DocumentUploadResponse",
        "DocumentUploadGovernanceRequest",
    ),
    FrontendContract(
        "document-indexing",
        "indexPersonalDocument",
        "post",
        "/api/v1/documents/uploads/{upload_id}/index",
        "DocumentUploadResponse",
    ),
    FrontendContract(
        "ocr-capabilities",
        "fetchOcrCapabilities",
        "get",
        "/api/v1/ocr/capabilities",
        "OcrCapabilityResponse",
    ),
    FrontendContract(
        "ocr-extraction",
        "extractOcrText",
        "post",
        "/api/v1/ocr/extract",
        "OcrExtractionResponse",
    ),
    FrontendContract("agents-list", "fetchAgents", "get", "/api/v1/agents", "AgentsResponse"),
    FrontendContract(
        "agent-detail",
        "fetchAuditAgent",
        "get",
        "/api/v1/agents/{agent_key}",
        "AgentDetailResponse",
    ),
    FrontendContract(
        "agent-create",
        "createAuditAgent",
        "post",
        "/api/v1/agents",
        "AgentCreateResponse",
        "AgentCreateRequest",
    ),
    FrontendContract(
        "agent-prompt-versions",
        "fetchAuditAgentPromptVersions",
        "get",
        "/api/v1/agents/{agent_key}/prompt-versions",
        "AgentPromptVersionsResponse",
    ),
    FrontendContract(
        "agent-prompt-create",
        "createAuditAgentPromptVersion",
        "post",
        "/api/v1/agents/{agent_key}/prompt-versions",
        "AgentCreateResponse",
        "AgentPromptVersionCreateRequest",
    ),
    FrontendContract(
        "agent-prompt-rollback",
        "rollbackAuditAgentPromptVersion",
        "post",
        "/api/v1/agents/{agent_key}/prompt-versions/rollback",
        "AgentCreateResponse",
        "AgentPromptVersionRollbackRequest",
    ),
    FrontendContract(
        "agent-prompt-review",
        "reviewAuditAgentPromptVersion",
        "post",
        "/api/v1/agents/{agent_key}/prompt-versions/review",
        "AgentCreateResponse",
        "AgentPromptVersionReviewRequest",
    ),
    FrontendContract(
        "agent-lifecycle",
        "updateAuditAgentLifecycle",
        "post",
        "/api/v1/agents/{agent_key}/lifecycle",
        "AgentCreateResponse",
        "AgentLifecycleRequest",
    ),
    FrontendContract(
        "agent-invocations",
        "fetchAuditAgentInvocations",
        "get",
        "/api/v1/agents/{agent_key}/invocations",
        "AgentInvocationsResponse",
    ),
    FrontendContract(
        "agent-invocation-create",
        "recordAuditAgentInvocation",
        "post",
        "/api/v1/agents/{agent_key}/invocations",
        "AgentInvocationResponse",
        "AgentInvocationCreateRequest",
    ),
    FrontendContract(
        "agent-feedback",
        "fetchAuditAgentFeedback",
        "get",
        "/api/v1/agents/{agent_key}/feedback",
        "AgentFeedbackListResponse",
    ),
    FrontendContract(
        "agent-feedback-create",
        "submitAuditAgentFeedback",
        "post",
        "/api/v1/agents/{agent_key}/feedback",
        "AgentFeedbackResponse",
        "AgentFeedbackCreateRequest",
    ),
    FrontendContract("projects", "fetchProjects", "get", "/api/v1/projects", "ProjectsResponse"),
    FrontendContract(
        "project-members",
        "fetchProjectMembers",
        "get",
        "/api/v1/projects/{project_key}/members",
        "ProjectMembersResponse",
    ),
    FrontendContract(
        "project-member-create",
        "createProjectMember",
        "post",
        "/api/v1/projects/{project_key}/members",
        "ProjectMemberCreateResponse",
        "ProjectMemberCreateRequest",
    ),
)


def main() -> int:
    args = _parse_args()
    report = build_contract_report(
        schema=_load_openapi_schema(),
        api_types_text=Path(args.api_types).read_text(encoding="utf-8"),
    )
    _write_json(report, Path(args.json_output) if args.json_output else None)
    _write_markdown(report, Path(args.markdown_output) if args.markdown_output else None)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.fail_on_mismatch and report["summary"]["hardening_issue_count"]:
        return 2
    return 0


def build_contract_report(*, schema: JsonObject, api_types_text: str) -> JsonObject:
    ts_types = _parse_exported_type_fields(api_types_text)
    items = [_contract_item(schema, ts_types, contract) for contract in FRONTEND_CONTRACTS]
    summary = {
        "contract_count": len(items),
        "openapi_path_count": len(_dict(schema.get("paths"))),
        "aligned_count": sum(1 for item in items if item["status"] == "aligned"),
        "field_mismatch_count": sum(1 for item in items if item["status"] == "field_mismatch"),
        "schema_gap_count": sum(1 for item in items if item["status"] == "schema_gap"),
        "missing_response_schema_count": sum(
            1 for item in items if item["response"]["status"] == "missing_response_schema"
        ),
        "missing_request_schema_count": sum(
            1 for item in items if item["request"]["status"] == "missing_request_schema"
        ),
        "missing_path_or_method_count": sum(
            1 for item in items if item["status"] in {"missing_path", "missing_method"}
        ),
    }
    summary["hardening_issue_count"] = (
        summary["field_mismatch_count"]
        + summary["schema_gap_count"]
        + summary["missing_path_or_method_count"]
    )
    return {
        "task": "frontend-backend-api-contract-schema",
        "status": (
            "needs_contract_hardening"
            if summary["hardening_issue_count"]
            else "schema_fields_aligned"
        ),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "evidence_grade": "L2-fixture-or-dry-run",
        "summary": summary,
        "items": items,
        "boundaries": {
            "production_side_effect": "none",
            "production_env_write": False,
            "provider_call_status": "not_called",
            "network_call_status": "not_called",
            "secret_values_reported": False,
        },
    }


def _contract_item(
    schema: JsonObject,
    ts_types: dict[str, JsonObject],
    contract: FrontendContract,
) -> JsonObject:
    paths = _dict(schema.get("paths"))
    path_item = _dict(paths.get(contract.path))
    if not path_item:
        return _missing_contract_item(contract, "missing_path")
    operation = _dict(path_item.get(contract.method.lower()))
    if not operation:
        return _missing_contract_item(contract, "missing_method")

    request = _compare_body_schema(
        schema=schema,
        operation=operation,
        ts_types=ts_types,
        ts_type_name=contract.request_type,
        body_kind="request",
    )
    response = _compare_body_schema(
        schema=schema,
        operation=operation,
        ts_types=ts_types,
        ts_type_name=contract.response_type,
        body_kind="response",
    )
    return {
        "surface": contract.surface,
        "function": contract.function_name,
        "method": contract.method.upper(),
        "path": contract.path,
        "request_type": contract.request_type,
        "response_type": contract.response_type,
        "status": _item_status(request, response),
        "request": request,
        "response": response,
    }


def _missing_contract_item(contract: FrontendContract, status: str) -> JsonObject:
    return {
        "surface": contract.surface,
        "function": contract.function_name,
        "method": contract.method.upper(),
        "path": contract.path,
        "request_type": contract.request_type,
        "response_type": contract.response_type,
        "status": status,
        "request": {"status": "not_checked"},
        "response": {"status": "not_checked"},
    }


def _compare_body_schema(
    *,
    schema: JsonObject,
    operation: JsonObject,
    ts_types: dict[str, JsonObject],
    ts_type_name: str | None,
    body_kind: str,
) -> JsonObject:
    if ts_type_name is None:
        return {"status": "not_applicable"}
    openapi_body_schema = (
        _request_schema(operation) if body_kind == "request" else _response_schema(operation)
    )
    if not openapi_body_schema:
        return {"status": f"missing_{body_kind}_schema"}
    schema_fields = _schema_fields(schema, openapi_body_schema)
    if schema_fields is None:
        return {"status": f"missing_{body_kind}_schema"}
    ts_fields = _resolve_ts_fields(ts_types, ts_type_name)
    if ts_fields is None:
        return {"status": "missing_ts_type", "ts_type": ts_type_name}

    openapi_names = set(schema_fields)
    ts_names = set(ts_fields)
    missing_ts_fields = sorted(openapi_names - ts_names)
    extra_ts_fields = sorted(ts_names - openapi_names)
    required_in_openapi_optional_in_ts = sorted(
        name
        for name in openapi_names & ts_names
        if schema_fields[name]["required"] and not ts_fields[name]["required"]
    )
    optional_in_openapi_required_in_ts = sorted(
        name
        for name in openapi_names & ts_names
        if not schema_fields[name]["required"] and ts_fields[name]["required"]
    )
    status = (
        "field_mismatch"
        if missing_ts_fields
        or extra_ts_fields
        or required_in_openapi_optional_in_ts
        or optional_in_openapi_required_in_ts
        else "aligned"
    )
    return {
        "status": status,
        "ts_type": ts_type_name,
        "openapi_fields": sorted(openapi_names),
        "ts_fields": sorted(ts_names),
        "missing_ts_fields": missing_ts_fields,
        "extra_ts_fields": extra_ts_fields,
        "required_in_openapi_optional_in_ts": required_in_openapi_optional_in_ts,
        "optional_in_openapi_required_in_ts": optional_in_openapi_required_in_ts,
    }


def _item_status(request: JsonObject, response: JsonObject) -> str:
    statuses = {str(request["status"]), str(response["status"])}
    if statuses & {"field_mismatch", "missing_ts_type"}:
        return "field_mismatch"
    if statuses & {"missing_request_schema", "missing_response_schema"}:
        return "schema_gap"
    return "aligned"


def _request_schema(operation: JsonObject) -> JsonObject | None:
    request_body = _dict(operation.get("requestBody"))
    content = _dict(request_body.get("content"))
    return _dict(_dict(content.get("application/json")).get("schema")) or None


def _response_schema(operation: JsonObject) -> JsonObject | None:
    responses = _dict(operation.get("responses"))
    response = _dict(responses.get("200"))
    content = _dict(response.get("content"))
    return _dict(_dict(content.get("application/json")).get("schema")) or None


def _schema_fields(schema: JsonObject, body_schema: JsonObject) -> dict[str, JsonObject] | None:
    resolved = _resolve_schema(schema, body_schema)
    properties = _dict(resolved.get("properties"))
    if not properties:
        return None
    required = set(_list_of_strings(resolved.get("required")))
    return {name: {"required": name in required} for name in properties}


def _resolve_schema(schema: JsonObject, value: JsonObject) -> JsonObject:
    if "$ref" in value:
        ref = str(value["$ref"])
        if not ref.startswith("#/components/schemas/"):
            return value
        name = ref.rsplit("/", 1)[-1]
        return _dict(_dict(_dict(schema.get("components")).get("schemas")).get(name))
    if "allOf" in value:
        properties: JsonObject = {}
        required: list[str] = []
        for item in _list_of_dicts(value.get("allOf")):
            resolved = _resolve_schema(schema, item)
            properties.update(_dict(resolved.get("properties")))
            required.extend(_list_of_strings(resolved.get("required")))
        return {"properties": properties, "required": required}
    return value


def _parse_exported_type_fields(source: str) -> dict[str, JsonObject]:
    results: dict[str, JsonObject] = {}
    pattern = re.compile(r"export\s+type\s+([A-Za-z][A-Za-z0-9_]*)\s*=")
    for match in pattern.finditer(source):
        name = match.group(1)
        cursor = match.end()
        while cursor < len(source) and source[cursor].isspace():
            cursor += 1
        if cursor >= len(source):
            continue
        if source[cursor] == "{":
            block, _ = _read_balanced_block(source, cursor)
            results[name] = {"kind": "object", "fields": _parse_top_level_fields(block)}
            continue
        alias_end = source.find(";", cursor)
        if alias_end == -1:
            continue
        alias = source[cursor:alias_end].strip()
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", alias):
            results[name] = {"kind": "alias", "target": alias}
    return results


def _read_balanced_block(source: str, start: int) -> tuple[str, int]:
    depth = 0
    for index in range(start, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1], index + 1
    raise ValueError("unterminated TypeScript object type")


def _parse_top_level_fields(block: str) -> dict[str, JsonObject]:
    fields: dict[str, JsonObject] = {}
    depth = 0
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if depth == 1:
            match = re.match(r"readonly\s+([A-Za-z_][A-Za-z0-9_]*)(\?)?\s*:", line)
            if match:
                fields[match.group(1)] = {"required": match.group(2) != "?"}
        depth += line.count("{")
        depth -= line.count("}")
    return fields


def _resolve_ts_fields(
    ts_types: dict[str, JsonObject],
    type_name: str,
) -> dict[str, JsonObject] | None:
    current = type_name
    seen: set[str] = set()
    while current not in seen:
        seen.add(current)
        entry = ts_types.get(current)
        if entry is None:
            return None
        if entry["kind"] == "object":
            return _dict(entry["fields"])
        current = str(entry["target"])
    return None


def _load_openapi_schema() -> JsonObject:
    # Reuse the repository's test fixture state to avoid loading real settings,
    # DBs, production services, or provider clients while generating schema.
    from medical_audit_kb.api.app import create_app
    from tests.knowledge_query.test_api import _api_state

    with tempfile.TemporaryDirectory(prefix="medical-audit-openapi-") as temp_root:
        return create_app(_api_state(Path(temp_root))).openapi()


def _write_json(payload: JsonObject, path: Path | None) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_markdown(payload: JsonObject, path: Path | None) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Frontend Backend API Contract Schema",
        "",
        f"- status: `{payload['status']}`",
        f"- evidence_grade: `{payload['evidence_grade']}`",
        f"- contract_count: `{payload['summary']['contract_count']}`",
        f"- hardening_issue_count: `{payload['summary']['hardening_issue_count']}`",
        f"- field_mismatch_count: `{payload['summary']['field_mismatch_count']}`",
        f"- schema_gap_count: `{payload['summary']['schema_gap_count']}`",
        "",
        "| Surface | Function | Method | Path | Status | Request | Response |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in payload["items"]:
        lines.append(
            "| {surface} | `{function}` | {method} | `{path}` | `{status}` | "
            "`{request}` | `{response}` |".format(
                surface=item["surface"],
                function=item["function"],
                method=item["method"],
                path=item["path"],
                status=item["status"],
                request=item["request"]["status"],
                response=item["response"]["status"],
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _dict(value: object) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _list_of_dicts(value: object) -> list[JsonObject]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _list_of_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare frontend TypeScript API types against the local FastAPI OpenAPI schema. "
            "This is a local dry-run contract audit and does not call production or providers."
        )
    )
    parser.add_argument("--api-types", default=str(DEFAULT_API_TYPES_PATH))
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN_OUTPUT))
    parser.add_argument("--fail-on-mismatch", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
