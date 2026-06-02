from __future__ import annotations

from typing import cast

import psycopg

from medical_audit_kb.indexing.embeddings import EmbeddingProvider

POSTGRES_STATUS_TABLES: tuple[str, ...] = (
    "source_package_versions",
    "source_documents",
    "document_chunks",
    "chunk_embeddings",
    "index_versions",
    "index_jobs",
    "failed_files",
    "pending_files",
)


def count_postgres_embeddings(
    database_url: str,
    embedding_provider: EmbeddingProvider,
) -> int:
    with (
        psycopg.connect(psycopg_database_url(database_url)) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(
            """
            SELECT count(*)
            FROM chunk_embeddings ce
            JOIN document_chunks dc ON dc.id = ce.chunk_id
            JOIN source_documents sd ON sd.id = dc.source_document_id
            JOIN index_versions iv ON iv.source_package_version_id = sd.source_package_version_id
            WHERE ce.provider = %s
              AND ce.model_name = %s
              AND ce.provider_version = %s
              AND ce.dimension = %s
              AND iv.status = 'active'
              AND sd.status = 'indexed'
            """,
            (
                embedding_provider.provider,
                embedding_provider.model_name,
                embedding_provider.provider_version,
                embedding_provider.dimension,
            ),
        )
        row = cursor.fetchone()

    count = _int_row_count(row)
    if count <= 0:
        raise ValueError(
            "no postgres embeddings match requested provider metadata: "
            f"{embedding_provider.provider}/"
            f"{embedding_provider.model_name}/"
            f"{embedding_provider.provider_version}/"
            f"{embedding_provider.dimension}"
        )
    return count


def load_postgres_index_status(database_url: str) -> dict[str, object]:
    with (
        psycopg.connect(psycopg_database_url(database_url)) as connection,
        connection.cursor() as cursor,
    ):
        row_counts = _postgres_row_counts(cursor)
        cursor.execute(
            """
            SELECT provider, model_name, provider_version, dimension, count(*) AS embedding_count
            FROM chunk_embeddings
            GROUP BY provider, model_name, provider_version, dimension
            ORDER BY embedding_count DESC, provider, model_name, provider_version, dimension
            """
        )
        embedding_rows = cursor.fetchall()
        embedding_sets = [
            {
                "provider": str(provider),
                "model_name": str(model_name),
                "provider_version": str(provider_version),
                "dimension": _int_from_db(dimension),
                "embedding_count": _int_from_db(embedding_count),
            }
            for provider, model_name, provider_version, dimension, embedding_count in embedding_rows
        ]
        cursor.execute(
            """
            SELECT version_key, status, vector_provider, vector_model, chunk_count, document_count
            FROM index_versions
            ORDER BY created_at DESC, version_key
            LIMIT 5
            """
        )
        index_versions = []
        for row in cursor.fetchall():
            (
                version_key,
                status,
                vector_provider,
                vector_model,
                chunk_count,
                document_count,
            ) = row
            index_versions.append(
                {
                    "version_key": str(version_key),
                    "status": str(status),
                    "vector_provider": (
                        str(vector_provider) if vector_provider is not None else None
                    ),
                    "vector_model": str(vector_model) if vector_model is not None else None,
                    "chunk_count": _int_from_db(chunk_count),
                    "document_count": _int_from_db(document_count),
                }
            )
        cursor.execute(
            """
            SELECT version_key, source_root_path
            FROM source_package_versions
            ORDER BY created_at DESC, version_key
            LIMIT 5
            """
        )
        source_packages = [
            {
                "version_key": str(version_key),
                "source_root_path": str(source_root_path),
            }
            for version_key, source_root_path in cursor.fetchall()
        ]

    return {
        "available": True,
        "row_counts": row_counts,
        "embedding_sets": embedding_sets,
        "index_versions": index_versions,
        "source_packages": source_packages,
    }


def row_count(response: dict[str, object], table_name: str) -> int:
    row_counts = response.get("row_counts")
    if not isinstance(row_counts, dict):
        return 0
    value = row_counts.get(table_name)
    return value if isinstance(value, int) else 0


def psycopg_database_url(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def _postgres_row_counts(cursor: psycopg.Cursor[object]) -> dict[str, int]:
    row_counts: dict[str, int] = {}
    for table_name in POSTGRES_STATUS_TABLES:
        cursor.execute(f"SELECT count(*) FROM {table_name}")
        row_counts[table_name] = _int_row_count(cursor.fetchone())
    return row_counts


def _int_row_count(row: object) -> int:
    if row is None:
        return 0
    row_values = cast(tuple[object, ...], row)
    return _int_from_db(row_values[0])


def _int_from_db(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise ValueError("database value must be an integer")
