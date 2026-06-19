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
    personal_upload_user_key: str | None = None
    personal_upload_read_all: bool = False

    def matches(self, metadata: Mapping[str, object]) -> bool:
        checks = (
            _matches_personal_upload_access(
                metadata,
                user_key=self.personal_upload_user_key,
                read_all=self.personal_upload_read_all,
            ),
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
                self.personal_upload_user_key,
                self.personal_upload_read_all,
            )
        )


def _collection_values(collections: tuple[SourceCollection, ...]) -> tuple[str, ...]:
    return tuple(collection.value for collection in collections)


def _matches_personal_upload_access(
    metadata: Mapping[str, object],
    *,
    user_key: str | None,
    read_all: bool,
) -> bool:
    if metadata.get("source_collection") != SourceCollection.PERSONAL_MATERIALS.value:
        return True
    if read_all:
        return True
    if user_key is None:
        return False
    return metadata.get("visibility") == "private" and metadata.get("created_by") == user_key


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
