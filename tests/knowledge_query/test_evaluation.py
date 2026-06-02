import json
from pathlib import Path
from uuid import UUID

from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.evaluation.datasets import (
    MaterialQuestionSeed,
    answer_meets_acceptance,
    generate_candidate_cases_from_materials,
    load_evaluation_cases,
    prd_seed_cases,
)
from medical_audit_kb.evaluation.runner import evaluate_retrieval
from medical_audit_kb.indexing.bm25_index import BM25Document, InMemoryBM25Index
from medical_audit_kb.indexing.embeddings import DeterministicFakeEmbeddingProvider
from medical_audit_kb.indexing.vector_index import (
    ChunkEmbeddingInput,
    InMemoryVectorIndex,
    build_chunk_embedding_records,
)
from medical_audit_kb.preview.resolver import PreviewResolver
from medical_audit_kb.retrieval.hybrid_search import HybridSearchEngine
from medical_audit_kb.retrieval.rerank import FakeRerankProvider


def test_load_evaluation_cases_keeps_expected_sources_and_auditor_import(
    tmp_path: Path,
) -> None:
    dataset_path = tmp_path / "evaluation.json"
    dataset_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case-001",
                        "question": "超量开药规则依据是什么？",
                        "expected_evidence": [
                            {
                                "source_collection": "supervision-rules-knowledge",
                                "source_path": "rules/rule.md",
                                "article_or_rule": "超量开药",
                                "required_terms": ["超量"],
                            }
                        ],
                        "acceptance_criteria": {
                            "required_terms": ["超量开药"],
                            "min_citations": 1,
                            "require_preview": True,
                        },
                        "tags": ["prescription-audit"],
                        "filters": {
                            "source_collections": ["supervision-rules-knowledge"],
                            "business_topics": ["prescription-audit"],
                        },
                        "auditor_import": {
                            "raw_question": "这个处方是不是超量？",
                            "source_channel": "interview",
                            "auditor_question_id": "auditor-q-1",
                            "auditor_role": "auditor",
                            "asked_at": "2026-05-31",
                            "reviewer_notes": "首批访谈问题",
                        },
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    cases = load_evaluation_cases(dataset_path)

    assert len(cases) == 1
    assert cases[0].expected_evidence[0].source_collection == (
        SourceCollection.SUPERVISION_RULES_KNOWLEDGE
    )
    assert cases[0].expected_evidence[0].article_or_rule == "超量开药"
    assert cases[0].filters.source_collections == (SourceCollection.SUPERVISION_RULES_KNOWLEDGE,)
    assert cases[0].auditor_import.auditor_question_id == "auditor-q-1"


def test_prd_seed_cases_cover_prescription_and_rule_trace_topics() -> None:
    cases = prd_seed_cases()
    case_ids = {case.case_id for case in cases}

    assert "prd-prescription-over-quantity-001" in case_ids
    assert "prd-prescription-over-course-001" in case_ids
    assert "prd-rule-version-trace-001" in case_ids


def test_generate_candidate_cases_from_articles_and_rules() -> None:
    cases = generate_candidate_cases_from_materials(
        (
            MaterialQuestionSeed(
                source_collection=SourceCollection.MEDICAL_INSURANCE_LAWS,
                source_path="laws/fund.md",
                title="医保基金监管条例",
                text="第一条 医疗机构应当保留审核依据。",
            ),
            MaterialQuestionSeed(
                source_collection=SourceCollection.SUPERVISION_RULES_KNOWLEDGE,
                source_path="rules/rules.md",
                title="处方规则",
                text="规则编码: R001\n规则名称: 超量开药\n说明: 超过限定数量。",
            ),
        )
    )

    assert cases[0].question == "医保基金监管条例中第一条的审核要求是什么？"
    assert cases[0].expected_evidence[0].article_or_rule == "第一条"
    assert cases[1].question == "超量开药规则的判定依据是什么？"
    assert cases[1].filters.source_collections == (SourceCollection.SUPERVISION_RULES_KNOWLEDGE,)


def test_evaluate_retrieval_outputs_recall_citation_and_preview_metrics(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "data"
    _write_text(source_root / "laws" / "fund.md", "第一条 医疗机构应当保留审核依据。")
    chunks = (
        _chunk(
            chunk_id=LAW_CHUNK_ID,
            text="第一条 医疗机构应当保留审核依据。",
            source_collection=SourceCollection.MEDICAL_INSURANCE_LAWS,
            source_path="laws/fund.md",
            article_or_rule="第一条",
        ),
    )
    engine = _engine_from_chunks(chunks)
    cases = load_evaluation_cases(
        _write_dataset(
            tmp_path / "evaluation.json",
            [
                {
                    "case_id": "hit-case",
                    "question": "医疗机构需要保留什么审核依据？",
                    "expected_evidence": [
                        {
                            "source_collection": "medical-insurance-laws",
                            "source_path": "laws/fund.md",
                            "article_or_rule": "第一条",
                        }
                    ],
                },
                {
                    "case_id": "miss-case",
                    "question": "超量开药规则是什么？",
                    "expected_evidence": [
                        {
                            "source_collection": "supervision-rules-knowledge",
                            "source_path": "rules/rules.md",
                            "article_or_rule": "超量开药",
                        }
                    ],
                },
            ],
        )
    )

    summary = evaluate_retrieval(
        cases,
        engine,
        top_k=3,
        preview_resolver=PreviewResolver(source_root=source_root),
    )

    assert summary.case_count == 2
    assert summary.recall_at_k == 0.5
    assert summary.citation_hit_rate == 0.5
    assert summary.preview_location_success_rate == 1.0
    assert summary.results[0].preview_success
    assert summary.results[1].missing_expected_sources == ("rules/rules.md",)
    assert summary.to_dict()["case_count"] == 2


def test_answer_meets_acceptance_checks_terms_citations_and_preview() -> None:
    criteria = prd_seed_cases()[0].acceptance_criteria

    assert answer_meets_acceptance(
        "超量开药需要引用规则来源",
        citation_count=1,
        preview_success=True,
        criteria=criteria,
    )
    assert not answer_meets_acceptance(
        "超量开药需要引用规则来源",
        citation_count=0,
        preview_success=True,
        criteria=criteria,
    )
    assert not answer_meets_acceptance(
        "超量开药需要引用规则来源",
        citation_count=1,
        preview_success=False,
        criteria=criteria,
    )


LAW_CHUNK_ID = UUID("33333333-3333-4333-8333-333333333333")


def _engine_from_chunks(chunks: tuple[ChunkEmbeddingInput, ...]) -> HybridSearchEngine:
    provider = DeterministicFakeEmbeddingProvider(dimension=32)
    vector_index = InMemoryVectorIndex(dimension=provider.dimension)
    vector_index.upsert(build_chunk_embedding_records(chunks, provider=provider))
    bm25_index = InMemoryBM25Index()
    bm25_index.upsert(
        [
            BM25Document(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                metadata=chunk.metadata,
            )
            for chunk in chunks
        ]
    )
    return HybridSearchEngine(
        embedding_provider=provider,
        vector_index=vector_index,
        bm25_index=bm25_index,
        rerank_provider=FakeRerankProvider(),
    )


def _chunk(
    *,
    chunk_id: UUID,
    text: str,
    source_collection: SourceCollection,
    source_path: str,
    article_or_rule: str,
) -> ChunkEmbeddingInput:
    return ChunkEmbeddingInput(
        chunk_id=chunk_id,
        text=text,
        metadata={
            "source_collection": source_collection.value,
            "locator": {
                "type": "markdown-section",
                "source_path": source_path,
                "line_start": 1,
                "line_end": 1,
            },
            "index_version_key": "index-v1",
            "source_package_version_key": "package-v1",
            "article_number": article_or_rule,
            "year": 2024,
            "region": "国家",
            "document_type": "law",
            "business_topic": "fund-supervision",
        },
    )


def _write_dataset(path: Path, cases: list[dict[str, object]]) -> Path:
    path.write_text(json.dumps({"cases": cases}, ensure_ascii=False), encoding="utf-8")
    return path


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
