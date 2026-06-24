#!/usr/bin/env python3
"""F2 调优测试台：进程内复刻生产 pgvector + 真实生成 provider 路径，逐问题判读。

承接 docs/workflows/workflow-answer-provider-production-gate-stable.md §6。
不污染生产 DB、不经服务进程、不写 env；只读检索 + 调一次生成，输出可判读 JSON，
用于量化召回/提示词调优（reranker、来源加权、拒答阈值）对端到端真实生成率的影响。

判读要点：
- ``fallback_used=true`` + ``generation_error`` 含「依据不足…」=模型按设计拒答（弱召回）。
  应从检索召回（A1 reranker / A2 来源加权）与提示词（B1 拒答阈值）两端改进，
  不要通过放宽引用校验来制造「成功」。
- ``weak_recall_*`` 与 ``strong_recall_*`` 分组指标对齐 generate-or-safe-fallback 姿态：
  强召回集追求高生成率，弱召回集追求安全回退（拒答+零幻觉）。

容器内运行示例（注入 DEEPSEEK_API_KEY 后；只读，不写生产）：

    docker exec \
      -e MEDICAL_AUDIT_KB_DATABASE_URL="$MEDICAL_AUDIT_KB_DATABASE_URL" \
      -e DEEPSEEK_API_KEY="$DEEPSEEK_API_KEY" \
      medical_audit_app python scripts/run-answer-provider-tuning-bench.py \
        --questions-file tmp/tuning-questions.txt \
        --embedding-provider openai --embedding-model kimi-for-coding \
        --api-key-env KIMI_API_KEY --embedding-dimension 1024 \
        --embedding-base-url https://api.kimi.com/coding/v1 \
        --answer-provider openai --answer-model deepseek-chat \
        --answer-api-key-env DEEPSEEK_API_KEY \
        --answer-base-url https://api.deepseek.com/v1 \
        --answer-max-output-tokens 900 --answer-temperature 0 \
        --top-k 10 \
        --json-output tmp/outputs/answer-tuning-bench-$(date +%Y%m%dT%H%M%S).json

questions-file：每行一个问题；``#`` 开头或空行忽略；行内可用 ``\t<tag>`` 追加标签
（如 ``weak-recall``）以参与强/弱召回分组统计。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from medical_audit_kb.core.config import DATABASE_URL_ENV
from medical_audit_kb.generation.answer_builder import (
    AnswerGenerationProvider,
    build_citation_backed_answer,
)
from medical_audit_kb.generation.answer_providers import (
    AnthropicAnswerGenerationProvider,
    OpenAICompatibleAnswerGenerationProvider,
)
from medical_audit_kb.indexing.embeddings import (
    DeterministicFakeEmbeddingProvider,
    EmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
)
from medical_audit_kb.retrieval.postgres_search import load_postgres_hybrid_search_engine
from medical_audit_kb.retrieval.rerank import rerank_provider_from_name

_REFUSAL_GENERATION_ERROR = "generated answer does not contain citation markers"


@dataclass(frozen=True, slots=True)
class BenchQuestion:
    question: str
    tags: tuple[str, ...]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="F2 调优测试台：pgvector + 真实生成 provider 逐问题判读（只读）",
    )
    parser.add_argument("--questions-file", required=True)
    parser.add_argument("--database-url-env", default=DATABASE_URL_ENV)
    parser.add_argument("--index-version-status", default="active")
    parser.add_argument("--index-version-key", default=None)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument(
        "--rerank",
        choices=("fake", "domain"),
        default="fake",
        help="fake=生产现默认 token-overlap；domain=A1 域码感知候选（A/B 用）。",
    )
    parser.add_argument(
        "--source-weights-file",
        default=None,
        help="可选 JSON（来源集合→权重）做 A2 来源加权 A/B；缺省用 DEFAULT_SOURCE_WEIGHTS。",
    )
    parser.add_argument("--json-output", required=True)
    # 与 cli.py 的构造保持一致，确保与生产/评测同源
    parser.add_argument("--embedding-provider", choices=("fake", "openai"), default="openai")
    parser.add_argument("--embedding-model", default="text-embedding-3-small")
    parser.add_argument("--embedding-dimension", type=int)
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--embedding-base-url", default="https://api.openai.com/v1")
    parser.add_argument("--embedding-batch-size", type=int, default=128)
    parser.add_argument(
        "--answer-provider", choices=("fallback", "openai", "anthropic"), default="fallback"
    )
    parser.add_argument("--answer-model", default="gpt-4.1-mini")
    parser.add_argument("--answer-api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--answer-base-url")
    parser.add_argument("--answer-max-output-tokens", type=int, default=600)
    parser.add_argument("--answer-temperature", type=float, default=0.0)
    return parser


def _embedding_provider(args: argparse.Namespace) -> EmbeddingProvider:
    if args.embedding_provider == "fake":
        return DeterministicFakeEmbeddingProvider(dimension=args.embedding_dimension or 32)
    return OpenAICompatibleEmbeddingProvider.from_env(
        api_key_env=args.api_key_env,
        model_name=args.embedding_model,
        dimension=args.embedding_dimension,
        base_url=args.embedding_base_url,
        batch_size=args.embedding_batch_size,
    )


def _answer_provider(args: argparse.Namespace) -> AnswerGenerationProvider | None:
    if args.answer_provider == "fallback":
        return None
    if args.answer_provider == "anthropic":
        return AnthropicAnswerGenerationProvider.from_env(
            api_key_env=args.answer_api_key_env,
            model_name=args.answer_model,
            base_url=args.answer_base_url or "https://api.anthropic.com",
            max_output_tokens=args.answer_max_output_tokens,
            temperature=args.answer_temperature,
        )
    return OpenAICompatibleAnswerGenerationProvider.from_env(
        api_key_env=args.answer_api_key_env,
        model_name=args.answer_model,
        base_url=args.answer_base_url or "https://api.openai.com/v1",
        max_output_tokens=args.answer_max_output_tokens,
        temperature=args.answer_temperature,
    )


def _load_source_weights(path: str | None) -> dict[str, float] | None:
    if not path:
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("source weights file must be a JSON object of collection -> factor")
    return {str(key): float(value) for key, value in payload.items()}


def _load_questions(path: Path) -> tuple[BenchQuestion, ...]:
    questions: list[BenchQuestion] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        question, _, tag_blob = line.partition("\t")
        tags = tuple(tag.strip() for tag in tag_blob.split(",") if tag.strip())
        questions.append(BenchQuestion(question=question.strip(), tags=tags))
    return tuple(questions)


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    database_url = os.getenv(args.database_url_env)
    if not database_url:
        print(f"FATAL: 缺少数据库 URL env: {args.database_url_env}", file=sys.stderr)
        return 2

    generation_provider = _answer_provider(args)
    if generation_provider is None:
        print(
            "WARN: --answer-provider=fallback，仅测召回与回退基线，不调真实生成。",
            file=sys.stderr,
        )

    engine = load_postgres_hybrid_search_engine(
        database_url=database_url,
        embedding_provider=_embedding_provider(args),
        rerank_provider=rerank_provider_from_name(args.rerank),
        source_collection_weights=_load_source_weights(args.source_weights_file),
        index_version_status=args.index_version_status,
        index_version_key=args.index_version_key,
    )

    questions = _load_questions(Path(args.questions_file))
    records: list[dict[str, object]] = []
    for item in questions:
        results = engine.search(item.question, top_k=args.top_k)
        answer = build_citation_backed_answer(
            item.question, results, generation_provider=generation_provider
        )
        is_refusal = (
            answer.fallback_used and answer.generation_error == _REFUSAL_GENERATION_ERROR
        )
        records.append(
            {
                "question": item.question,
                "tags": list(item.tags),
                "fallback_used": answer.fallback_used,
                "model_refused": is_refusal,
                "generation_error": answer.generation_error,
                "citation_count": len(answer.citations),
                "confidence": str(answer.confidence),
                "answer_head": answer.answer[:200],
                "recall": [
                    {
                        "chunk_id": str(result.chunk.chunk_id),
                        "source_collection": str(
                            result.chunk.metadata.get("source_collection", "")
                        ),
                        "score": _round(result.score),
                        "vector_score": _round(result.vector_score),
                        "bm25_score": _round(result.bm25_score),
                        "rerank_score": _round(result.rerank_score),
                    }
                    for result in results
                ],
            }
        )

    total = len(records)
    generated = sum(1 for record in records if not record["fallback_used"])

    def _rate(subset: list[dict[str, object]]) -> dict[str, object]:
        count = len(subset)
        gen = sum(1 for record in subset if not record["fallback_used"])
        refused = sum(1 for record in subset if record["model_refused"])
        return {
            "count": count,
            "generation_rate": round(gen / count, 4) if count else 0.0,
            "fallback_rate": round((count - gen) / count, 4) if count else 0.0,
            "model_refusal_count": refused,
        }

    weak = [rec for item, rec in zip(questions, records, strict=True) if "weak-recall" in item.tags]
    strong = [
        rec for item, rec in zip(questions, records, strict=True) if "weak-recall" not in item.tags
    ]
    report: dict[str, object] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "answer_provider": args.answer_provider,
        "answer_model": args.answer_model,
        "embedding_provider": args.embedding_provider,
        "embedding_model": args.embedding_model,
        "rerank": args.rerank,
        "source_weights_file": args.source_weights_file,
        "top_k": args.top_k,
        "index_version_status": args.index_version_status,
        "index_version_key": args.index_version_key,
        "question_count": total,
        "generation_rate": round(generated / total, 4) if total else 0.0,
        "fallback_rate": round((total - generated) / total, 4) if total else 0.0,
        "strong_recall": _rate(strong),
        "weak_recall": _rate(weak),
        "production_side_effect": "none",
        "records": records,
    }

    output_path = Path(args.json_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"questions={total} generation_rate={report['generation_rate']} "
        f"weak_recall={report['weak_recall']} -> {output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
