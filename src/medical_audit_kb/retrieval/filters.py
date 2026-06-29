from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from medical_audit_kb.domain.constants import SourceCollection


@dataclass(frozen=True, slots=True)
class RetrievalFilters:
    source_collections: tuple[SourceCollection, ...] = ()
    domains: tuple[str, ...] = ()
    domain_fallback_collections: tuple[SourceCollection, ...] = ()
    years: tuple[int, ...] = ()
    regions: tuple[str, ...] = ()
    document_types: tuple[str, ...] = ()
    business_topics: tuple[str, ...] = ()
    title_only: bool = False
    title_query: str = ""
    personal_material_created_by: str = ""
    personal_material_include_all: bool = False

    def matches(self, metadata: Mapping[str, object]) -> bool:
        checks = (
            _matches_any(
                metadata,
                "source_collection",
                _collection_values(self.source_collections),
            ),
            _matches_domain_scope(metadata, self.domains, self.domain_fallback_collections),
            _matches_any(metadata, "year", self.years),
            _matches_any(metadata, "region", self.regions),
            _matches_any(metadata, "document_type", self.document_types),
            _matches_any(metadata, "business_topic", self.business_topics),
            _matches_title(metadata, self.title_query) if self.title_only else True,
            _matches_personal_material_scope(
                metadata,
                created_by=self.personal_material_created_by,
                include_all=self.personal_material_include_all,
            ),
        )
        return all(checks)

    @property
    def is_empty(self) -> bool:
        return not any(
            (
                self.source_collections,
                self.domains,
                self.years,
                self.regions,
                self.document_types,
                self.business_topics,
                self.title_only,
                self.personal_material_created_by,
                self.personal_material_include_all,
            )
        )


def _matches_domain_scope(
    metadata: Mapping[str, object],
    domains: tuple[str, ...],
    fallback_collections: tuple[SourceCollection, ...],
) -> bool:
    """专题域过滤：命中 domain 即纳入；存量无 domain 的 chunk 按 source_collection 兜底。

    增量去重不会重切旧文档，故已入库的存量 chunk 没有 `domain` 标签——这类按其
    source_collection 是否属专题兜底集合判定，避免专题检索漏掉存量医保语料。
    """
    if not domains:
        return True
    domain_value = metadata.get("domain")
    if domain_value in domains:
        return True
    if not domain_value and fallback_collections:
        return metadata.get("source_collection") in _collection_values(fallback_collections)
    return False


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


def _matches_personal_material_scope(
    metadata: Mapping[str, object],
    *,
    created_by: str,
    include_all: bool,
) -> bool:
    if metadata.get("source_collection") != SourceCollection.PERSONAL_MATERIALS.value:
        return True
    if include_all:
        return True
    return bool(created_by) and metadata.get("created_by") == created_by


def _matches_title(metadata: Mapping[str, object], query: str) -> bool:
    terms = tuple(_query_terms(query))
    if not terms:
        return True
    haystack = _title_haystack(metadata).lower()
    return any(term in haystack for term in terms)


def _query_terms(query: str) -> Iterable[str]:
    normalized = query.strip().lower()
    if not normalized:
        return ()
    compact = "".join(normalized.split())
    terms = [compact] if compact else []
    terms.extend(part for part in normalized.split() if part)
    return tuple(dict.fromkeys(terms))


def _title_haystack(metadata: Mapping[str, object]) -> str:
    values: list[str] = []
    for key in ("title", "document_title", "file_name", "source_path"):
        value = metadata.get(key)
        if isinstance(value, str):
            values.append(value)
    _extend_string_values(values, metadata.get("title_path"))

    locator = metadata.get("locator")
    if isinstance(locator, Mapping):
        for key in ("title", "document_title", "file_name", "source_path"):
            value = locator.get(key)
            if isinstance(value, str):
                values.append(value)
                if key == "source_path":
                    values.append(Path(value).stem)
        _extend_string_values(values, locator.get("title_path"))
    return "\n".join(values)


def _extend_string_values(values: list[str], candidate: object) -> None:
    if isinstance(candidate, str):
        values.append(candidate)
        return
    if isinstance(candidate, list | tuple | set | frozenset):
        values.extend(item for item in candidate if isinstance(item, str))
