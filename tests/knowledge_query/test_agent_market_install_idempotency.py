from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from medical_audit_kb.api.agent_store import SqlAlchemyAgentStore
from medical_audit_kb.api.app import ApiState, create_app
from medical_audit_kb.core.config import KnowledgeQuerySettings, ModelProviderSettings

PROJECT_NAME_HEADER = (
    "%E5%8C%BB%E4%BF%9D%E5%9F%BA%E9%87%91"
    "%E4%BD%BF%E7%94%A8%E5%90%88%E8%A7%84"
    "%E4%B8%93%E9%A1%B9%E8%87%AA%E6%9F%A5"
)
PROJECT_NAME = "医保基金使用合规专项自查"


def _market_payload(
    *,
    project_name: str = PROJECT_NAME,
    template_id: str = "template-medical-fund",
) -> dict[str, object]:
    return {
        "name": "医保核验",
        "category": "业务类",
        "topic": "医保基金使用合规",
        "prompt": "仅基于项目材料和引用依据输出核验意见。",
        "knowledge_base": "医保基金合规知识库",
        "project_name": project_name,
        "visibility_scope": "project",
        "allowed_roles": ["admin", "technician", "director", "member"],
        "metadata": {
            "source": "agent-market",
            "template_id": template_id,
        },
    }


def _agent_api_state(tmp_path: Path) -> ApiState:
    settings = KnowledgeQuerySettings(
        data_root=tmp_path / "data",
        index_root=tmp_path / "index",
        database_url="postgresql+psycopg://user:pass@localhost:5433/db",
        model_provider=ModelProviderSettings(
            provider="fake",
            api_key_env="OPENAI_API_KEY",
            embedding_model="fake",
            chat_model="fake",
        ),
        source_collection_weights={
            "medical-insurance-catalog": 1.25,
            "supervision-rules-knowledge": 1.35,
            "risk-negative-list": 1.1,
            "medical-insurance-laws": 1.0,
        },
    )
    state = ApiState.from_settings(settings)
    state.audit_log_store = None
    return state


def test_agents_api_reuses_market_install_for_same_actor_project_and_template(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'agents-market-install.db'}"
    state = _agent_api_state(tmp_path)
    store = SqlAlchemyAgentStore(database_url, create_schema=True)
    state.agent_store = store
    client = TestClient(create_app(state))
    headers = {
        "X-User-Id": "director-1",
        "X-Role": "director",
        "X-Project-Name": PROJECT_NAME_HEADER,
    }
    payload = _market_payload(project_name=f" {PROJECT_NAME} ")

    second_payload = {
        **payload,
        "name": "不应覆盖既有安装",
        "prompt": "不应覆盖既有提示词。",
    }
    first_response = client.post("/agents", headers=headers, json=payload)
    second_response = client.post("/agents", headers=headers, json=second_payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["created"] is True
    assert first_response.json()["reactivated"] is False
    assert second_response.json()["created"] is False
    assert second_response.json()["reactivated"] is False
    assert second_response.json()["item"]["id"] == first_response.json()["item"]["id"]
    assert second_response.json()["item"]["project_name"] == PROJECT_NAME
    assert len(first_response.json()["item"]["prompt_versions"]) == 1
    assert len(second_response.json()["item"]["prompt_versions"]) == 1
    assert second_response.json()["item"]["name"] == payload["name"]
    assert second_response.json()["item"]["prompt"] == payload["prompt"]

    list_response = client.get("/agents", headers=headers)
    assert list_response.status_code == 200
    custom_installs = [
        item
        for item in list_response.json()["items"]
        if item["metadata"].get("source") == "agent-market"
        and item["metadata"].get("template_id") == "template-medical-fund"
        and item["created_by"] == "director-1"
    ]
    assert [item["id"] for item in custom_installs] == [first_response.json()["item"]["id"]]
    assert list_response.json()["market_installations"] == [
        {
            "template_id": "template-medical-fund",
            "agent_id": first_response.json()["item"]["id"],
        }
    ]
    reuse_logs = [
        item for item in state.operation_logs if item["action"] == "agent-install-reused"
    ]
    assert len(reuse_logs) == 1
    reuse_payload = reuse_logs[0]["payload"]
    assert isinstance(reuse_payload, dict)
    assert reuse_payload["created"] is False

    other_headers = {**headers, "X-User-Id": "director-2"}
    other_response = client.post("/agents", headers=other_headers, json=payload)
    assert other_response.status_code == 200
    assert other_response.json()["created"] is True
    assert other_response.json()["item"]["id"] != first_response.json()["item"]["id"]

    other_list_response = client.get("/agents", headers=other_headers)
    assert other_list_response.status_code == 200
    assert other_list_response.json()["market_installations"] == [
        {
            "template_id": "template-medical-fund",
            "agent_id": other_response.json()["item"]["id"],
        }
    ]

    other_project = store.install_market_agent(
        {**_market_payload(project_name="另一专项"), "created_by": "director-1"}
    )
    assert other_project.created is True
    assert other_project.item["id"] != first_response.json()["item"]["id"]


def test_agents_api_reactivates_an_archived_market_install(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'agents-market-reactivate.db'}"
    state = _agent_api_state(tmp_path)
    state.agent_store = SqlAlchemyAgentStore(database_url, create_schema=True)
    client = TestClient(create_app(state))
    headers = {
        "X-User-Id": "director-1",
        "X-Role": "director",
        "X-Project-Name": PROJECT_NAME_HEADER,
    }
    payload = _market_payload()

    first_response = client.post("/agents", headers=headers, json=payload)
    agent_id = first_response.json()["item"]["id"]
    archive_response = client.post(
        f"/agents/{agent_id}/lifecycle",
        headers=headers,
        json={"status": "archived", "reason": "user archived template"},
    )
    archived_list = client.get("/agents", headers=headers)
    reinstall_response = client.post("/agents", headers=headers, json=payload)
    restored_list = client.get("/agents", headers=headers)

    assert first_response.status_code == 200
    assert archive_response.status_code == 200
    assert archived_list.json()["market_installations"] == []
    assert reinstall_response.status_code == 200
    assert reinstall_response.json()["created"] is False
    assert reinstall_response.json()["reactivated"] is True
    assert reinstall_response.json()["item"]["id"] == agent_id
    assert reinstall_response.json()["item"]["status"] == "active"
    assert restored_list.json()["market_installations"] == [
        {"template_id": "template-medical-fund", "agent_id": agent_id}
    ]
    assert any(
        item["action"] == "agent-install-reactivated"
        for item in state.operation_logs
    )


def test_store_reuses_a_single_legacy_random_market_install(tmp_path: Path) -> None:
    store = SqlAlchemyAgentStore(
        f"sqlite:///{tmp_path / 'agents-market-legacy.db'}",
        create_schema=True,
    )
    values = {**_market_payload(), "created_by": "director-1"}
    legacy = store.add_agent(values)

    result = store.install_market_agent(values)

    assert result.created is False
    assert result.reactivated is False
    assert result.item["id"] == legacy["id"]


def test_store_concurrent_market_install_returns_one_agent(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'agents-market-concurrent.db'}"
    first_store = SqlAlchemyAgentStore(database_url, create_schema=True)
    second_store = SqlAlchemyAgentStore(database_url)
    values = {**_market_payload(), "created_by": "director-1"}

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda store: store.install_market_agent(values),
                (first_store, second_store),
            )
        )

    assert {str(result.item["id"]) for result in results} == {
        str(results[0].item["id"])
    }
    assert sorted(result.created for result in results) == [False, True]
    assert len(first_store.list_agents()) == 1


def test_agents_api_fails_closed_for_ambiguous_legacy_market_installs(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'agents-market-duplicates.db'}"
    state = _agent_api_state(tmp_path)
    store = SqlAlchemyAgentStore(database_url, create_schema=True)
    state.agent_store = store
    client = TestClient(create_app(state))
    headers = {
        "X-User-Id": "director-1",
        "X-Role": "director",
        "X-Project-Name": PROJECT_NAME_HEADER,
    }
    payload = _market_payload()
    legacy_values = {**payload, "created_by": "director-1"}
    first_legacy = store.add_agent(legacy_values)
    second_legacy = store.add_agent(legacy_values)

    list_response = client.get("/agents", headers=headers)
    response = client.post("/agents", headers=headers, json=payload)

    assert list_response.status_code == 200
    assert list_response.json()["market_installations"] == []
    assert list_response.json()["market_installation_issues"] == [
        {
            "code": "ambiguous-market-installations",
            "template_id": "template-medical-fund",
            "agent_ids": sorted([first_legacy["id"], second_legacy["id"]]),
        }
    ]
    assert response.status_code == 409
    assert response.json()["detail"] == (
        "multiple market agent installations already exist"
    )
