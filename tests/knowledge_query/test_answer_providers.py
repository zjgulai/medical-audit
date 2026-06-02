from collections.abc import Sequence
from uuid import uuid4

import httpx

from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.generation.answer_preflight import run_answer_provider_preflight
from medical_audit_kb.generation.answer_providers import (
    AnswerProviderError,
    AnthropicAnswerGenerationProvider,
    OpenAICompatibleAnswerGenerationProvider,
)
from medical_audit_kb.generation.citations import (
    Citation,
    EvidenceType,
)


def test_openai_compatible_answer_provider_posts_cited_chat_prompt() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "医疗机构应当保留医保基金审核依据 [C1]。"}}]},
        )

    provider = OpenAICompatibleAnswerGenerationProvider(
        api_key="test-key",
        model_name="custom-chat",
        base_url="https://example.test/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    answer = provider.generate_answer(
        "医疗机构需要保留什么？",
        (
            _citation(
                "C1",
                "第一条 医疗机构应当保留医保基金审核依据。",
            ),
        ),
    )

    request = requests[0]
    payload = request.read().decode("utf-8")
    assert answer == "医疗机构应当保留医保基金审核依据 [C1]。"
    assert request.url == "https://example.test/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer test-key"
    assert "医疗机构需要保留什么？" in payload
    assert "[C1] 第一条 医疗机构应当保留医保基金审核依据。" in payload


def test_openai_compatible_answer_provider_rejects_empty_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": ""}}]})

    provider = OpenAICompatibleAnswerGenerationProvider(
        api_key="test-key",
        model_name="custom-chat",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    try:
        provider.generate_answer("问题", (_citation("C1", "依据"),))
    except AnswerProviderError as exc:
        assert "content must be non-empty" in str(exc)
    else:
        raise AssertionError("expected AnswerProviderError")


def test_anthropic_answer_provider_posts_messages_request() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "content": [
                    {
                        "type": "text",
                        "text": "医疗机构应当保留医保基金审核依据 [C1]。",
                    }
                ]
            },
        )

    provider = AnthropicAnswerGenerationProvider(
        api_key="test-key",
        model_name="claude-test",
        base_url="https://anthropic.test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    answer = provider.generate_answer(
        "医疗机构需要保留什么？",
        (_citation("C1", "第一条 医疗机构应当保留医保基金审核依据。"),),
    )

    request = requests[0]
    payload = request.read().decode("utf-8")
    assert answer == "医疗机构应当保留医保基金审核依据 [C1]。"
    assert request.url == "https://anthropic.test/v1/messages"
    assert request.headers["x-api-key"] == "test-key"
    assert request.headers["anthropic-version"] == "2023-06-01"
    assert '"system"' in payload
    assert "[C1] 第一条 医疗机构应当保留医保基金审核依据。" in payload


def test_answer_provider_preflight_requires_citation_marker_and_term() -> None:
    result = run_answer_provider_preflight(StaticPreflightProvider())

    assert result.success
    assert result.citation_marker_present
    assert result.required_term_present
    assert result.answer == "医疗机构应当保留医保基金审核依据 [C1]。"


def test_answer_provider_preflight_captures_provider_errors() -> None:
    result = run_answer_provider_preflight(FailingPreflightProvider())

    assert result.success is False
    assert result.error == "provider unavailable"
    assert result.to_dict()["success"] is False


class StaticPreflightProvider:
    provider = "fake"
    model_name = "static-preflight"
    provider_version = "v1"

    def generate_answer(self, question: str, citations: Sequence[Citation]) -> str:
        return "医疗机构应当保留医保基金审核依据 [C1]。"


class FailingPreflightProvider:
    provider = "fake"
    model_name = "failing-preflight"
    provider_version = "v1"

    def generate_answer(self, question: str, citations: Sequence[Citation]) -> str:
        raise RuntimeError("provider unavailable")


def _citation(citation_id: str, snippet: str) -> Citation:
    return Citation(
        citation_id=citation_id,
        evidence_type=EvidenceType.LEGAL_BASIS,
        source_collection=SourceCollection.MEDICAL_INSURANCE_LAWS,
        chunk_id=uuid4(),
        snippet=snippet,
        locator={"type": "line", "source_path": "source.md", "line_start": 1},
        index_version_key="index-v1",
        source_package_version_key="package-v1",
        score=0.9,
        metadata={"source_collection": SourceCollection.MEDICAL_INSURANCE_LAWS.value},
    )
