from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from medical_audit_kb.indexing.embeddings import tokenize_text

BM25_K1 = 1.5
BM25_B = 0.75
CATALOG_CODE_EXACT_MATCH_BOOST = 10.0
CATALOG_CODE_TOKEN_PATTERN = re.compile(r"^[a-z]\d{2}\.\d+[a-z0-9+*]*$")


@dataclass(frozen=True, slots=True)
class BM25Document:
    chunk_id: UUID
    text: str
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class BM25SearchResult:
    document: BM25Document
    score: float


class InMemoryBM25Index:
    def __init__(self) -> None:
        self._documents: dict[UUID, BM25Document] = {}
        self._term_frequencies: dict[UUID, Counter[str]] = {}
        self._document_frequencies: Counter[str] = Counter()
        self._document_lengths: dict[UUID, int] = {}
        self._average_document_length = 0.0

    def upsert(self, documents: Sequence[BM25Document]) -> None:
        for document in documents:
            self._documents[document.chunk_id] = document
        self._rebuild_statistics()

    def search(
        self,
        query: str,
        *,
        top_k: int = 10,
        filters: Mapping[str, object] | None = None,
    ) -> tuple[BM25SearchResult, ...]:
        query_terms = tokenize_text(query)
        if not query_terms:
            return ()

        results: list[BM25SearchResult] = []
        for document in self._documents.values():
            if not _metadata_matches(document.metadata, filters):
                continue
            score = self._score_document(query_terms, document)
            if score > 0:
                results.append(BM25SearchResult(document=document, score=score))

        return tuple(sorted(results, key=lambda result: result.score, reverse=True)[:top_k])

    @property
    def size(self) -> int:
        return len(self._documents)

    def _rebuild_statistics(self) -> None:
        self._term_frequencies = {}
        self._document_frequencies = Counter()
        self._document_lengths = {}

        for document in self._documents.values():
            searchable_text = _searchable_text(document)
            terms = tokenize_text(searchable_text)
            frequencies = Counter(terms)
            self._term_frequencies[document.chunk_id] = frequencies
            self._document_lengths[document.chunk_id] = len(terms)
            self._document_frequencies.update(frequencies.keys())

        total_length = sum(self._document_lengths.values())
        self._average_document_length = (
            total_length / len(self._document_lengths) if self._document_lengths else 0.0
        )

    def _score_document(self, query_terms: tuple[str, ...], document: BM25Document) -> float:
        frequencies = self._term_frequencies[document.chunk_id]
        document_length = self._document_lengths[document.chunk_id]
        score = 0.0
        for term in query_terms:
            term_frequency = frequencies.get(term, 0)
            if term_frequency == 0:
                continue
            score += self._score_term(term, term_frequency, document_length)
            if CATALOG_CODE_TOKEN_PATTERN.match(term):
                score += CATALOG_CODE_EXACT_MATCH_BOOST

        normalized_query = query_terms_to_string(query_terms)
        searchable_text = _searchable_text(document).lower()
        if normalized_query and normalized_query in searchable_text:
            score += 2.0
        return score

    def _score_term(self, term: str, term_frequency: int, document_length: int) -> float:
        document_count = len(self._documents)
        document_frequency = self._document_frequencies.get(term, 0)
        idf = math.log(1 + (document_count - document_frequency + 0.5) / (document_frequency + 0.5))
        denominator = term_frequency + BM25_K1 * (
            1 - BM25_B + BM25_B * document_length / max(self._average_document_length, 1)
        )
        return idf * (term_frequency * (BM25_K1 + 1)) / denominator


def query_terms_to_string(query_terms: tuple[str, ...]) -> str:
    return "".join(query_terms)


def _searchable_text(document: BM25Document) -> str:
    metadata_text = " ".join(str(value) for value in document.metadata.values())
    return f"{document.text}\n{metadata_text}"


def _metadata_matches(
    metadata: Mapping[str, object],
    filters: Mapping[str, object] | None,
) -> bool:
    if not filters:
        return True
    return all(metadata.get(key) == value for key, value in filters.items())
