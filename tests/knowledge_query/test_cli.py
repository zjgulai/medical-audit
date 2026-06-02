import json
from pathlib import Path

from pytest import MonkeyPatch

from medical_audit_kb.cli import main
from medical_audit_kb.generation.citations import Citation


def test_acceptance_run_writes_markdown_and_json_outputs(tmp_path: Path) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(source_root / "医保目录" / "catalog.md", "# 医保目录\n医保目录内容")
    _write_binary(source_root / "风险负面清单" / "scan.png", b"png")
    report_path = tmp_path / "report.md"
    json_path = tmp_path / "report.json"

    exit_code = main(
        [
            "acceptance-run",
            "--source-root",
            str(source_root),
            "--output",
            str(report_path),
            "--json-output",
            str(json_path),
            "--package-version-key",
            "package-test",
        ]
    )

    assert exit_code == 0
    assert "知识库真实资料索引验收报告" in report_path.read_text(encoding="utf-8")
    assert '"source_package_version_key": "package-test"' in json_path.read_text(encoding="utf-8")


def test_acceptance_run_returns_nonzero_when_gate_fails(tmp_path: Path) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(source_root / "医保目录" / "broken.pdf", "not a pdf")
    report_path = tmp_path / "report.md"

    exit_code = main(
        [
            "acceptance-run",
            "--source-root",
            str(source_root),
            "--output",
            str(report_path),
        ]
    )

    assert exit_code == 2
    assert "总体状态：`FAIL`" in report_path.read_text(encoding="utf-8")


def test_index_build_and_evaluate_index_commands_write_outputs(tmp_path: Path) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(
        source_root / "全量法律" / "医保基金监管条例.md",
        "第一条 医疗机构应当保留医保基金审核依据。",
    )
    index_root = tmp_path / "index"
    build_summary = tmp_path / "index-summary.json"
    evaluation_report = tmp_path / "evaluation.md"
    evaluation_json = tmp_path / "evaluation.json"

    build_exit_code = main(
        [
            "index-build",
            "--source-root",
            str(source_root),
            "--index-root",
            str(index_root),
            "--json-output",
            str(build_summary),
            "--package-version-key",
            "package-test",
            "--max-chunks",
            "1",
        ]
    )
    evaluate_exit_code = main(
        [
            "evaluate-index",
            "--source-root",
            str(source_root),
            "--index-root",
            str(index_root),
            "--output",
            str(evaluation_report),
            "--json-output",
            str(evaluation_json),
            "--max-cases",
            "1",
            "--top-k",
            "3",
            "--query-terms",
            "医保",
        ]
    )

    assert build_exit_code == 0
    assert evaluate_exit_code == 0
    assert '"source_package_version_key": "package-test"' in build_summary.read_text(
        encoding="utf-8"
    )
    assert '"persistent_chunk_limit": 1' in build_summary.read_text(encoding="utf-8")
    assert "知识库真实资料检索评测报告" in evaluation_report.read_text(encoding="utf-8")
    assert '"case_count": 1' in evaluation_json.read_text(encoding="utf-8")


def test_evaluate_index_accepts_fixed_cases_file(tmp_path: Path) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(
        source_root / "全量法律" / "医保基金监管条例.md",
        "第一条 医疗机构应当保留医保基金审核依据。",
    )
    index_root = tmp_path / "index"
    cases_file = tmp_path / "cases.yaml"
    evaluation_report = tmp_path / "evaluation.md"
    evaluation_json = tmp_path / "evaluation.json"

    cases_file.write_text(
        """
cases:
  - case_id: fixed-case-001
    question: 医疗机构需要保留什么审核依据？
    expected_evidence:
      - source_collection: medical-insurance-laws
        source_path: 全量法律/医保基金监管条例.md
        article_or_rule: 第一条
""".strip(),
        encoding="utf-8",
    )

    main(
        [
            "index-build",
            "--source-root",
            str(source_root),
            "--index-root",
            str(index_root),
            "--package-version-key",
            "package-test",
        ]
    )
    evaluate_exit_code = main(
        [
            "evaluate-index",
            "--source-root",
            str(source_root),
            "--index-root",
            str(index_root),
            "--output",
            str(evaluation_report),
            "--json-output",
            str(evaluation_json),
            "--cases-file",
            str(cases_file),
            "--max-cases",
            "1",
        ]
    )

    assert evaluate_exit_code == 0
    assert "fixed-case-001" in evaluation_json.read_text(encoding="utf-8")
    assert '"case_count": 1' in evaluation_json.read_text(encoding="utf-8")


def test_evaluate_postgres_index_command_writes_outputs(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(
        source_root / "全量法律" / "医保基金监管条例.md",
        "第一条 医疗机构应当保留医保基金审核依据。",
    )
    cases_file = tmp_path / "cases.yaml"
    evaluation_report = tmp_path / "postgres-evaluation.md"
    evaluation_json = tmp_path / "postgres-evaluation.json"
    cases_file.write_text(
        """
cases:
  - case_id: postgres-fixed-case-001
    question: 医疗机构需要保留什么审核依据？
    expected_evidence:
      - source_collection: medical-insurance-laws
        source_path: 全量法律/医保基金监管条例.md
        article_or_rule: 第一条
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://user:pass@localhost/db")
    monkeypatch.setattr(
        "medical_audit_kb.cli.load_postgres_hybrid_search_engine",
        lambda **kwargs: EmptySearchEngine(),
    )

    exit_code = main(
        [
            "evaluate-postgres-index",
            "--source-root",
            str(source_root),
            "--database-url-env",
            "TEST_DATABASE_URL",
            "--output",
            str(evaluation_report),
            "--json-output",
            str(evaluation_json),
            "--cases-file",
            str(cases_file),
            "--max-cases",
            "1",
        ]
    )

    assert exit_code == 0
    assert "知识库真实资料检索评测报告" in evaluation_report.read_text(encoding="utf-8")
    assert '"case_count": 1' in evaluation_json.read_text(encoding="utf-8")


def test_evaluate_answers_command_writes_answer_quality_outputs(tmp_path: Path) -> None:
    source_root = tmp_path / "医保审核前期资料"
    _write_text(
        source_root / "全量法律" / "医保基金监管条例.md",
        "第一条 医疗机构应当保留医保基金审核依据。",
    )
    index_root = tmp_path / "index"
    cases_file = tmp_path / "answer-cases.yaml"
    report_path = tmp_path / "answer-evaluation.md"
    json_path = tmp_path / "answer-evaluation.json"

    cases_file.write_text(
        """
cases:
  - case_id: answer-case-001
    question: 医疗机构需要保留什么审核依据？
    expected_behavior: answer
    required_evidence_terms: [第一条]
    required_answer_terms: [审核依据]
    required_citation_terms: [医疗机构]
  - case_id: refusal-case-001
    question: 请给出资料中不存在的处罚金额。
    expected_behavior: refuse
    required_evidence_terms: [不存在的处罚金额]
""".strip(),
        encoding="utf-8",
    )

    main(
        [
            "index-build",
            "--source-root",
            str(source_root),
            "--index-root",
            str(index_root),
            "--package-version-key",
            "package-test",
        ]
    )
    exit_code = main(
        [
            "evaluate-answers",
            "--index-root",
            str(index_root),
            "--cases-file",
            str(cases_file),
            "--output",
            str(report_path),
            "--json-output",
            str(json_path),
            "--max-cases",
            "2",
        ]
    )

    assert exit_code == 0
    assert "知识库答案生成质量评测报告" in report_path.read_text(encoding="utf-8")
    assert '"case_count": 2' in json_path.read_text(encoding="utf-8")
    assert '"pass_rate": 1.0' in json_path.read_text(encoding="utf-8")


def test_answer_provider_smoke_command_writes_preflight_outputs(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    report_path = tmp_path / "answer-provider-smoke.md"
    json_path = tmp_path / "answer-provider-smoke.json"

    monkeypatch.setattr(
        "medical_audit_kb.cli.OpenAICompatibleAnswerGenerationProvider.from_env",
        lambda **kwargs: StaticAnswerSmokeProvider(),
    )

    exit_code = main(
        [
            "answer-provider-smoke",
            "--answer-provider",
            "openai",
            "--output",
            str(report_path),
            "--json-output",
            str(json_path),
        ]
    )

    assert exit_code == 0
    assert "答案生成 Provider 预检报告" in report_path.read_text(encoding="utf-8")
    assert '"success": true' in json_path.read_text(encoding="utf-8")


def test_answer_provider_smoke_command_accepts_anthropic_provider(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    report_path = tmp_path / "answer-provider-smoke.md"

    monkeypatch.setattr(
        "medical_audit_kb.cli.AnthropicAnswerGenerationProvider.from_env",
        lambda **kwargs: StaticAnswerSmokeProvider(),
    )

    exit_code = main(
        [
            "answer-provider-smoke",
            "--answer-provider",
            "anthropic",
            "--answer-model",
            "claude-test",
            "--answer-api-key-env",
            "ANTHROPIC_API_KEY",
            "--output",
            str(report_path),
        ]
    )

    assert exit_code == 0
    assert "总体状态：`PASS`" in report_path.read_text(encoding="utf-8")


def test_pgvector_import_plan_command_writes_outputs(tmp_path: Path) -> None:
    index_root = tmp_path / "index"
    report_path = tmp_path / "pgvector-import-plan.md"
    json_path = tmp_path / "pgvector-import-plan.json"
    _write_text(
        index_root / "summary.json",
        """
{
  "persistent_chunk_count": 1,
  "embedding_count": 1,
  "failed_file_count": 0,
  "pending_file_count": 0,
  "embedding_provider": "openai",
  "embedding_model": "kimi-for-coding",
  "embedding_provider_version": "v1",
  "embedding_dimension": 2
}
""".lstrip(),
    )
    _write_text(
        index_root / "chunks.jsonl",
        '{"chunk_id":"chunk-1","text":"医保审核依据"}\n',
    )
    _write_text(
        index_root / "embeddings.jsonl",
        (
            '{"chunk_id":"chunk-1","text":"医保审核依据","embedding":[1.0,0.0],'
            '"provider":"openai","model_name":"kimi-for-coding",'
            '"provider_version":"v1","dimension":2,"metadata":{}}\n'
        ),
    )
    _write_text(index_root / "failed_files.jsonl", "")
    _write_text(index_root / "pending_files.jsonl", "")

    exit_code = main(
        [
            "pgvector-import-plan",
            "--index-root",
            str(index_root),
            "--output",
            str(report_path),
            "--json-output",
            str(json_path),
            "--schema-dimension",
            "2",
        ]
    )

    assert exit_code == 0
    assert "知识库 pgvector 导入前校验报告" in report_path.read_text(encoding="utf-8")
    assert '"ready_for_import": true' in json_path.read_text(encoding="utf-8")


def test_pgvector_import_command_writes_dry_run_outputs(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    _write_text(source_root / "全量法律" / "医保政策.md", "第一条 医保审核依据。")
    index_root = tmp_path / "index"
    report_path = tmp_path / "pgvector-import.md"
    json_path = tmp_path / "pgvector-import.json"
    _write_text(
        index_root / "summary.json",
        """
{
  "job_type": "full-rebuild",
  "index_version_key": "full-rebuild-test",
  "source_package_version_key": "source-package-test",
  "persistent_chunk_count": 1,
  "embedding_count": 1,
  "failed_file_count": 0,
  "pending_file_count": 0,
  "embedding_provider": "openai",
  "embedding_model": "kimi-for-coding",
  "embedding_provider_version": "v1",
  "embedding_dimension": 2
}
""".lstrip(),
    )
    _write_text(
        index_root / "chunks.jsonl",
        (
            '{"chunk_id":"00000000-0000-0000-0000-000000000001",'
            '"text":"医保审核依据","metadata":{"source_collection":"medical-insurance-laws",'
            '"source_path":"全量法律/医保政策.md"},"locator":{"source_path":"全量法律/医保政策.md"},'
            '"source_path":"全量法律/医保政策.md"}\n'
        ),
    )
    _write_text(
        index_root / "embeddings.jsonl",
        (
            '{"chunk_id":"00000000-0000-0000-0000-000000000001",'
            '"text":"医保审核依据","embedding":[1.0,0.0],'
            '"provider":"openai","model_name":"kimi-for-coding",'
            '"provider_version":"v1","dimension":2,"metadata":{}}\n'
        ),
    )
    _write_text(index_root / "failed_files.jsonl", "")
    _write_text(index_root / "pending_files.jsonl", "")

    exit_code = main(
        [
            "pgvector-import",
            "--index-root",
            str(index_root),
            "--source-root",
            str(source_root),
            "--output",
            str(report_path),
            "--json-output",
            str(json_path),
            "--schema-dimension",
            "2",
        ]
    )

    assert exit_code == 0
    assert "知识库 pgvector 受控导入报告" in report_path.read_text(encoding="utf-8")
    assert '"mode": "dry-run"' in json_path.read_text(encoding="utf-8")
    assert '"ready_for_write": true' in json_path.read_text(encoding="utf-8")


def test_ui_smoke_command_writes_success_report(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    json_path = tmp_path / "ui-smoke.json"
    monkeypatch.setattr(
        "medical_audit_kb.cli._create_api_test_client",
        lambda: FakeUiSmokeClient(backend_status_code=200),
    )

    exit_code = main(["ui-smoke", "--json-output", str(json_path)])

    body = json.loads(json_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert body["success"] is True
    assert body["preview_path"] == "/pages/preview/11111111-1111-4111-8111-111111111111"


def test_ui_smoke_command_fails_when_backend_load_fails(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    json_path = tmp_path / "ui-smoke.json"
    monkeypatch.setattr(
        "medical_audit_kb.cli._create_api_test_client",
        lambda: FakeUiSmokeClient(backend_status_code=409),
    )

    exit_code = main(["ui-smoke", "--json-output", str(json_path)])

    body = json.loads(json_path.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert body["success"] is False
    assert body["backend_load_status_code"] == 409
    assert body["query_page_status_code"] is None


class StaticAnswerSmokeProvider:
    provider = "fake"
    model_name = "static-smoke"
    provider_version = "v1"

    def generate_answer(self, question: str, citations: tuple[Citation, ...]) -> str:
        return "医疗机构应当保留医保基金审核依据 [C1]。"


class EmptySearchEngine:
    def search(self, *args: object, **kwargs: object) -> tuple[object, ...]:
        return ()


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int,
        text: str = "",
        payload: object | None = None,
    ) -> None:
        self.status_code = status_code
        self.text = text
        self._payload = payload

    def json(self) -> object:
        return self._payload


class FakeUiSmokeClient:
    def __init__(self, *, backend_status_code: int) -> None:
        self._backend_status_code = backend_status_code

    def get(
        self,
        path: str,
        *,
        params: dict[str, object] | None = None,
    ) -> FakeResponse:
        if path == "/index/postgres-status":
            return FakeResponse(
                status_code=200,
                payload={
                    "row_counts": {"document_chunks": 1, "chunk_embeddings": 1},
                    "embedding_sets": [],
                },
            )
        if path == "/pages/query":
            return FakeResponse(
                status_code=200,
                text=(
                    '引用型回答 <a href="/pages/preview/'
                    '11111111-1111-4111-8111-111111111111">原文预览</a>'
                ),
            )
        if path == "/pages/preview/11111111-1111-4111-8111-111111111111":
            return FakeResponse(status_code=200, text="原文证据预览")
        return FakeResponse(status_code=404)

    def post(
        self,
        path: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
    ) -> FakeResponse:
        if path != "/index/search-backend/postgres":
            return FakeResponse(status_code=404)
        if self._backend_status_code != 200:
            return FakeResponse(
                status_code=self._backend_status_code,
                payload={"detail": "missing embedding api key env: KIMI_API_KEY"},
            )
        return FakeResponse(
            status_code=200,
            payload={
                "backend": "postgres",
                "ready": True,
                "details": {"matching_embedding_count": 1},
            },
        )


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_binary(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path
