from __future__ import annotations

from uuid import UUID

from pytest import MonkeyPatch

from medical_audit_kb.retrieval.postgres_search import (
    PostgresVectorIndex,
    load_postgres_bm25_index,
)


def test_postgres_vector_index_queries_pgvector_and_maps_results(
    monkeypatch: MonkeyPatch,
) -> None:
    chunk_id = UUID("00000000-0000-0000-0000-000000000001")
    cursor = FakeCursor(
        rows=[
            (
                chunk_id,
                "医保审核依据",
                {"source_collection": "medical-insurance-laws"},
                "openai",
                "kimi-for-coding",
                "v1",
                1024,
                0.87,
            )
        ]
    )
    monkeypatch.setattr(
        "medical_audit_kb.retrieval.postgres_search.psycopg.connect",
        lambda database_url: FakeConnection(cursor),
    )
    index = PostgresVectorIndex(
        database_url="postgresql+psycopg://user:pass@localhost/db",
        provider="openai",
        model_name="kimi-for-coding",
        provider_version="v1",
        dimension=3,
    )

    results = index.search((1.0, 0.0, 0.0), top_k=1)

    assert results[0].record.chunk_id == chunk_id
    assert results[0].record.text == "医保审核依据"
    assert results[0].record.metadata["source_collection"] == "medical-insurance-laws"
    assert results[0].score == 0.87
    assert cursor.params is not None
    assert cursor.params[0] == "[1,0,0]"
    assert cursor.params[1:5] == ("openai", "kimi-for-coding", "v1", 3)
    assert cursor.params[5] == "active"
    assert cursor.query is not None
    assert "JOIN source_documents sd ON sd.id = dc.source_document_id" in cursor.query
    assert "JOIN index_versions iv ON iv.source_package_version_id" in cursor.query
    assert "iv.status = %s" in cursor.query


def test_postgres_vector_index_validates_query_dimension() -> None:
    index = PostgresVectorIndex(
        database_url="postgresql://user:pass@localhost/db",
        provider="openai",
        model_name="kimi-for-coding",
        provider_version="v1",
        dimension=3,
    )

    try:
        index.search((1.0, 0.0), top_k=1)
    except ValueError as exc:
        assert "embedding dimension mismatch" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_load_postgres_bm25_index_reads_document_chunks(
    monkeypatch: MonkeyPatch,
) -> None:
    cursor = FakeCursor(
        rows=[
            (
                UUID("00000000-0000-0000-0000-000000000001"),
                "规则名称: 超量开药",
                {"source_collection": "supervision-rules-knowledge"},
            )
        ]
    )
    monkeypatch.setattr(
        "medical_audit_kb.retrieval.postgres_search.psycopg.connect",
        lambda database_url: FakeConnection(cursor),
    )

    index = load_postgres_bm25_index("postgresql://user:pass@localhost/db")
    results = index.search("超量开药", top_k=1)

    assert results[0].document.text == "规则名称: 超量开药"
    assert cursor.query is not None
    assert "JOIN source_documents sd ON sd.id = dc.source_document_id" in cursor.query
    assert "JOIN index_versions iv ON iv.source_package_version_id" in cursor.query
    assert "iv.status = %s" in cursor.query
    assert cursor.params == ("active",)


def test_postgres_indexes_can_target_candidate_version(
    monkeypatch: MonkeyPatch,
) -> None:
    cursor = FakeCursor(rows=[])
    monkeypatch.setattr(
        "medical_audit_kb.retrieval.postgres_search.psycopg.connect",
        lambda database_url: FakeConnection(cursor),
    )
    index = PostgresVectorIndex(
        database_url="postgresql://user:pass@localhost/db",
        provider="openai",
        model_name="kimi-for-coding",
        provider_version="v1",
        dimension=3,
        index_version_status="candidate",
        index_version_key="full-rebuild-next",
    )

    index.search((1.0, 0.0, 0.0), top_k=1)

    assert cursor.query is not None
    assert "iv.status = %s" in cursor.query
    assert "iv.version_key = %s" in cursor.query
    assert cursor.params is not None
    assert cursor.params[5:7] == ("candidate", "full-rebuild-next")


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return self._cursor


class FakeCursor:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self._rows = rows
        self.query: str | None = None
        self.params: tuple[object, ...] | None = None

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def execute(
        self,
        query: str,
        params: tuple[object, ...] | None = None,
    ) -> None:
        self.query = query
        self.params = params

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._rows
