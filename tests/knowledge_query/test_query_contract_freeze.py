import json
from pathlib import Path

from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.domain.source_collection_registry import (
    KNOWLEDGE_QUERY_CONTRACT_VERSION,
    SOURCE_COLLECTION_DEFINITIONS,
)

CONTRACT_PATH = Path("docs/api/knowledge-query-contract-v2.json")


def test_query_contract_v2_json_matches_runtime_source_collection_registry() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    contract_values = tuple(item["value"] for item in contract["source_collections"])
    registry_values = tuple(
        definition.collection.value for definition in SOURCE_COLLECTION_DEFINITIONS
    )

    assert contract["contract_version"] == KNOWLEDGE_QUERY_CONTRACT_VERSION
    assert contract["boundaries"] == {
        "provider_call": False,
        "database_write": False,
        "index_activation": False,
        "production_probe": False,
        "frontend_business_change": False,
    }
    assert contract_values == registry_values
    assert set(contract_values) == {item.value for item in SourceCollection}
    assert "other-unclassified" not in contract_values
    assert [item["value"] for item in contract["excluded_collections"]] == ["other-unclassified"]
    assert "contract_version" in contract["query_response_required_fields"]
    assert "effective_source_collections" in contract["query_response_required_fields"]


def test_query_contract_v2_keeps_phase_counts_explicit() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    phase_counts: dict[str, int] = {}
    for item in contract["source_collections"]:
        phase_counts[item["phase"]] = phase_counts.get(item["phase"], 0) + 1

    assert phase_counts == {
        "P6A-medical-current-library-completion": 4,
        "P6B-policy-library-buildout": 6,
        "P6C-management-library-buildout": 8,
        "P6E-other-library-buildout": 6,
        "personal-materials": 1,
    }
