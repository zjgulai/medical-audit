from pytest import MonkeyPatch

from medical_audit_kb.api.postgres_status import count_postgres_embeddings
from medical_audit_kb.indexing.embeddings import DeterministicFakeEmbeddingProvider


def test_count_postgres_embeddings_counts_only_active_index_embeddings(
    monkeypatch: MonkeyPatch,
) -> None:
    cursor = FakeCursor(row=(7,))
    monkeypatch.setattr(
        "medical_audit_kb.api.postgres_status.psycopg.connect",
        lambda database_url: FakeConnection(cursor),
    )

    count = count_postgres_embeddings(
        "postgresql+psycopg://user:pass@localhost/db",
        DeterministicFakeEmbeddingProvider(dimension=32),
    )

    assert count == 7
    assert cursor.query is not None
    assert "JOIN source_documents sd ON sd.id = dc.source_document_id" in cursor.query
    assert "JOIN index_versions iv ON iv.source_package_version_id" in cursor.query
    assert "iv.status = 'active'" in cursor.query


class FakeConnection:
    def __init__(self, cursor: "FakeCursor") -> None:
        self._cursor = cursor

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def cursor(self) -> "FakeCursor":
        return self._cursor


class FakeCursor:
    def __init__(self, *, row: tuple[object, ...]) -> None:
        self._row = row
        self.query: str | None = None
        self.params: tuple[object, ...] | None = None

    def __enter__(self) -> "FakeCursor":
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

    def fetchone(self) -> tuple[object, ...]:
        return self._row
