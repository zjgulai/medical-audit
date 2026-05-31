from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from medical_audit_kb.domain.constants import SourceCollection


@dataclass(frozen=True, slots=True)
class RetrievalFilters:
    source_collections: tuple[SourceCollection, ...] = ()
    years: tuple[int, ...] = ()
    regions: tuple[str, ...] = ()
    document_types: tuple[str, ...] = ()
    business_topics: tuple[str, ...] = ()

    def matches(self, metadata: Mapping[str, object]) -> bool:
        checks = (
            _matches_any(
                metadata,
                "source_collection",
                _collection_values(self.source_collections),
            ),
            _matches_any(metadata, "year", self.years),
            _matches_any(metadata, "region", self.regions),
            _matches_any(metadata, "document_type", self.document_types),
            _matches_any(metadata, "business_topic", self.business_topics),
        )
        return all(checks)

    @property
    def is_empty(self) -> bool:
        return not any(
            (
                self.source_collections,
                self.years,
                self.regions,
                self.document_types,
                self.business_topics,
            )
        )


def _collection_values(collections: tuple[SourceCollection, ...]) -> tuple[str, ...]:
    return tuple(collection.value for collection in collections)


def _matches_any(
    metadata: Mapping[str, object],
    key: str,
    accepted_values: Iterable[object],
) -> bool:
    accepted = tuple(accepted_values)
    if not accepted:
        return True

    value = metadata.get(key)
    if isinstance(value, list | tuple | set | frozenset):
        return bool(set(value).intersection(accepted))
    return value in accepted
