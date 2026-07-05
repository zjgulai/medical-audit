from __future__ import annotations

import json
from pathlib import Path

from medical_audit_kb.api.routes_query import QueryRequest
from medical_audit_kb.domain.constants import SourceCollection

CONTRACT_PATH = (
    Path(__file__).resolve().parents[2] / "docs/api/knowledge-query-contract-v1.json"
)
CONTRACT_V2_PATH = (
    Path(__file__).resolve().parents[2] / "docs/api/knowledge-query-contract-v2.json"
)


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _contract_v2() -> dict[str, object]:
    return json.loads(CONTRACT_V2_PATH.read_text(encoding="utf-8"))


def test_query_contract_v1_source_collections_remain_frontend_subset() -> None:
    contract = _contract()
    source_collections = contract["source_collections"]
    assert isinstance(source_collections, dict)

    allowed = source_collections["allowed"]
    assert isinstance(allowed, list)
    assert set(allowed).issubset(item.value for item in SourceCollection)

    default_member_effective = source_collections["default_member_effective"]
    assert default_member_effective == [
        SourceCollection.MEDICAL_INSURANCE_CATALOG.value,
        SourceCollection.MEDICAL_INSURANCE_LAWS.value,
        SourceCollection.RISK_NEGATIVE_LIST.value,
        SourceCollection.SUPERVISION_RULES_KNOWLEDGE.value,
    ]
    assert SourceCollection.PERSONAL_MATERIALS.value not in default_member_effective


def test_query_contract_v2_source_collections_match_backend_enum() -> None:
    contract = _contract_v2()
    source_collections = contract["source_collections"]
    assert isinstance(source_collections, dict)

    allowed = source_collections["allowed"]
    assert isinstance(allowed, list)
    assert allowed == sorted(item.value for item in SourceCollection)
    assert SourceCollection.POLICY_GENERAL_POLICY.value in allowed
    assert SourceCollection.MANAGEMENT_GENERAL_ADMIN.value in allowed
    assert SourceCollection.OTHER_EDUCATION_RESEARCH.value in allowed


def test_query_contract_request_fields_match_backend_model() -> None:
    contract = _contract()
    endpoints = contract["endpoints"]
    assert isinstance(endpoints, dict)
    post_query = endpoints["post_query"]
    assert isinstance(post_query, dict)
    request = post_query["request"]
    assert isinstance(request, dict)
    request_fields = request["fields"]
    assert isinstance(request_fields, dict)

    schema = QueryRequest.model_json_schema()
    assert set(request_fields) == set(schema["properties"])
    assert request["required"] == ["question"]
    assert schema["required"] == ["question"]
    assert schema["properties"]["top_k"]["default"] == 5
    assert schema["properties"]["top_k"]["minimum"] == 1
    assert schema["properties"]["top_k"]["maximum"] == 20
    assert schema["properties"]["title_only"]["default"] is False


def test_query_contract_response_and_error_states_are_frozen() -> None:
    contract = _contract()
    endpoints = contract["endpoints"]
    assert isinstance(endpoints, dict)
    post_query = endpoints["post_query"]
    assert isinstance(post_query, dict)

    response = post_query["response"]
    assert isinstance(response, dict)
    assert response["required"] == [
        "question",
        "answer",
        "confidence",
        "fallback_used",
        "effective_source_collections",
        "basis_groups",
        "citations",
        "personal_upload_matches",
        "query_log_index",
        "query_log_id",
        "agent_invocation_id",
    ]

    errors = post_query["error_contract"]
    assert isinstance(errors, list)
    assert {(item["status"], item["frontend_code"]) for item in errors} == {
        (400, "unknown-topic"),
        (403, "source-collection-denied"),
        (404, "no-cited-evidence"),
        (409, "search-engine-not-initialized"),
    }
