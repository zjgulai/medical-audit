#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import uvicorn

from medical_audit_kb.api.analytics_upload_store import InMemoryAnalyticsUploadStore
from medical_audit_kb.api.app import ApiState, create_app
from medical_audit_kb.api.document_upload_store import InMemoryDocumentUploadStore
from medical_audit_kb.api.query_history_store import InMemoryQueryHistoryStore
from medical_audit_kb.core.config import (
    KnowledgeQuerySettings,
    ModelProviderSettings,
    load_settings,
)
from medical_audit_kb.domain.constants import SourceCollection
from medical_audit_kb.indexing.bm25_index import BM25Document, InMemoryBM25Index
from medical_audit_kb.indexing.embeddings import DeterministicFakeEmbeddingProvider
from medical_audit_kb.indexing.vector_index import (
    ChunkEmbeddingInput,
    InMemoryVectorIndex,
    build_chunk_embedding_records,
)
from medical_audit_kb.retrieval.hybrid_search import HybridSearchEngine
from medical_audit_kb.retrieval.rerank import FakeRerankProvider

JsonObject = dict[str, object]


def main() -> int:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[1]

    if args.backend_mode == "postgres-readonly":
        return _run_postgres_readonly_smoke(args)

    pnpm = shutil.which("pnpm")
    if pnpm is None:
        raise SystemExit("missing required command: pnpm")
    return _run_in_memory_e2e(args, repo_root=repo_root, pnpm=pnpm)


def _run_in_memory_e2e(args: argparse.Namespace, *, repo_root: Path, pnpm: str) -> int:
    with TemporaryDirectory(prefix="medical-audit-fullstack-e2e-") as temp_dir:
        temp_root = Path(temp_dir)
        context = multiprocessing.get_context("spawn")
        backend = context.Process(
            target=_serve_in_memory_backend,
            args=(temp_root, args.backend_host, args.backend_port),
            daemon=True,
        )
        backend.start()
        try:
            backend_url = f"http://{args.backend_host}:{args.backend_port}"
            _wait_for_health(backend_url, backend, timeout_seconds=args.timeout)
            _run_backend_smoke(backend_url)
            command = [pnpm, "--dir", "web", "e2e"]
            env = {
                **dict(os.environ),
                "MEDICAL_AUDIT_API_BASE_URL": backend_url,
            }
            result = subprocess.run(command, cwd=repo_root, env=env, check=False)
            return result.returncode
        finally:
            if backend.is_alive():
                backend.terminate()
                backend.join(timeout=5)
            if backend.is_alive():
                backend.kill()
                backend.join(timeout=5)


def _run_postgres_readonly_smoke(args: argparse.Namespace) -> int:
    config_path = Path(args.config) if args.config else None
    settings = load_settings(config_path)
    context = multiprocessing.get_context("spawn")
    backend = context.Process(
        target=_serve_configured_backend,
        args=(args.config, args.backend_host, args.backend_port),
        daemon=True,
    )
    backend.start()
    backend_url = f"http://{args.backend_host}:{args.backend_port}"
    report: JsonObject = {
        "mode": "postgres-readonly",
        "status": "blocked",
        "backend_url": backend_url,
        "config_path": str(config_path) if config_path else None,
        "database_endpoint": _database_endpoint(settings.database_url),
        "production_side_effect": "none",
        "provider_call_status": "not_called",
        "playwright_e2e_status": "not_run_in_readonly_mode",
    }
    try:
        _wait_for_health(backend_url, backend, timeout_seconds=args.timeout)
        report["health"] = _load_json(f"{backend_url}/health")
        postgres_status = _load_json(f"{backend_url}/index/postgres-status")
        report["postgres_status"] = postgres_status
        report["status"] = _postgres_readiness_status(postgres_status)
    except urllib.error.HTTPError as exc:
        report["http_status_code"] = exc.code
        report["error"] = _redact_error_text(exc.read().decode("utf-8", errors="replace"))
    except (OSError, urllib.error.URLError) as exc:
        report["error"] = _redact_error_text(str(exc))
    finally:
        if backend.is_alive():
            backend.terminate()
            backend.join(timeout=5)
        if backend.is_alive():
            backend.kill()
            backend.join(timeout=5)

    _write_report(report, Path(args.json_output) if args.json_output else None)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] == "ready":
        return 0
    return 0 if args.allow_unavailable else 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run local Next + FastAPI Playwright E2E with an in-memory backend and fake "
            "embedding provider. This command does not use production data or external providers."
        )
    )
    parser.add_argument(
        "--backend-mode",
        choices=("in-memory", "postgres-readonly"),
        default="in-memory",
        help=(
            "in-memory runs full Playwright E2E against a temporary fake-provider backend; "
            "postgres-readonly starts the configured FastAPI app and only probes read-only "
            "PostgreSQL index status."
        ),
    )
    parser.add_argument("--backend-host", default="127.0.0.1")
    parser.add_argument("--backend-port", type=int, default=8021)
    parser.add_argument("--config", default=None, help="Optional MEDICAL_AUDIT_KB_CONFIG path.")
    parser.add_argument("--json-output", default=None, help="Optional JSON report output path.")
    parser.add_argument(
        "--allow-unavailable",
        action="store_true",
        help="Return zero for postgres-readonly blocked/partial reports after writing evidence.",
    )
    parser.add_argument("--timeout", type=float, default=30)
    return parser.parse_args()


def _serve_in_memory_backend(temp_root: Path, host: str, port: int) -> None:
    app = create_app(_api_state(temp_root), enforce_controlled_api_auth=True)
    uvicorn.run(app, host=host, port=port, log_level="warning")


def _serve_configured_backend(config: str | None, host: str, port: int) -> None:
    app = create_app(ApiState.from_settings(load_settings(config)))
    uvicorn.run(app, host=host, port=port, log_level="warning")


def _api_state(temp_root: Path) -> ApiState:
    source_root = temp_root / "data"
    source_file = source_root / "全量法律" / "law.md"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text(
        "第一条 医疗机构应当保留医保基金审核依据。\n第二条 其他条款。\n",
        encoding="utf-8",
    )
    settings = KnowledgeQuerySettings(
        data_root=source_root,
        index_root=temp_root / "index",
        database_url="postgresql+psycopg://user:pass@localhost:5433/db",
        model_provider=ModelProviderSettings(
            provider="fake",
            api_key_env="OPENAI_API_KEY",
            embedding_model="fake",
            chat_model="fake",
        ),
        source_collection_weights={
            "medical-insurance-catalog": 1.25,
            "supervision-rules-knowledge": 1.35,
            "risk-negative-list": 1.1,
            "medical-insurance-laws": 1.0,
        },
    )
    state = ApiState.from_settings(settings)
    state.audit_finding_store = None
    state.audit_log_store = None
    state.agent_store = None
    state.project_member_store = None
    state.review_task_store = None
    state.analytics_upload_store = InMemoryAnalyticsUploadStore(
        upload_root=settings.index_root / "analytics-uploads"
    )
    state.document_upload_store = InMemoryDocumentUploadStore(
        upload_root=settings.index_root / "document-uploads"
    )
    state.query_history_store = InMemoryQueryHistoryStore()
    state.search_engine = _search_engine(source_file.relative_to(source_root).as_posix())
    return state


def _search_engine(source_path: str) -> HybridSearchEngine:
    provider = DeterministicFakeEmbeddingProvider(dimension=32)
    chunk = ChunkEmbeddingInput(
        chunk_id=uuid4(),
        text="第一条 医疗机构应当保留医保基金审核依据。",
        metadata={
            "source_collection": SourceCollection.MEDICAL_INSURANCE_LAWS.value,
            "locator": {
                "type": "law-article",
                "source_path": source_path,
                "line_start": 1,
                "line_end": 1,
                "article_number": "第一条",
            },
            "index_version_key": "index-v1",
            "source_package_version_key": "package-v1",
            "year": 2024,
            "region": "国家",
            "document_type": "law",
            "business_topic": "fund-supervision",
        },
    )
    vector_index = InMemoryVectorIndex(dimension=provider.dimension)
    vector_index.upsert(build_chunk_embedding_records([chunk], provider=provider))
    bm25_index = InMemoryBM25Index()
    bm25_index.upsert(
        [BM25Document(chunk_id=chunk.chunk_id, text=chunk.text, metadata=chunk.metadata)]
    )
    return HybridSearchEngine(
        embedding_provider=provider,
        vector_index=vector_index,
        bm25_index=bm25_index,
        rerank_provider=FakeRerankProvider(),
    )


def _wait_for_health(
    backend_url: str,
    backend: multiprocessing.Process,
    *,
    timeout_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not backend.is_alive():
            raise SystemExit("local test backend exited before /health became available")
        try:
            _load_json(f"{backend_url}/health")
            return
        except (OSError, urllib.error.URLError):
            time.sleep(0.25)
    raise SystemExit(f"local test backend did not become healthy within {timeout_seconds:g}s")


def _run_backend_smoke(backend_url: str) -> None:
    health = _load_json(f"{backend_url}/health")
    if health.get("status") != "ok":
        raise SystemExit(f"unexpected health response: {health!r}")
    query = _post_json(
        f"{backend_url}/query",
        {
            "question": "医保基金审核依据是什么",
            "top_k": 3,
            "source_collections": ["medical-insurance-laws"],
        },
        headers={
            "X-Role": "auditor",
            "X-User-Id": "local-fullstack-e2e",
            "X-Tenant-Id": "hospital-demo",
        },
    )
    if not query.get("citations"):
        raise SystemExit("local test backend query smoke returned no citations")
    agents = _load_json(
        f"{backend_url}/agents",
        headers={
            "X-Role": "auditor",
            "X-User-Id": "local-fullstack-e2e",
            "X-Tenant-Id": "hospital-demo",
        },
    )
    if agents.get("store", {}).get("ready") is not True:
        raise SystemExit(f"local test backend agents store is not ready: {agents!r}")


def _load_json(url: str, *, headers: dict[str, str] | None = None) -> dict[str, object]:
    request = urllib.request.Request(url, headers=dict(headers or {}), method="GET")
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"unexpected JSON payload from {url}: {payload!r}")
    return payload


def _post_json(
    url: str,
    payload: dict[str, object],
    *,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **dict(headers or {})},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"unexpected JSON payload from {url}: {value!r}")
    return value


def _postgres_readiness_status(payload: JsonObject) -> str:
    row_counts = payload.get("row_counts")
    index_versions = payload.get("index_versions")
    embedding_sets = payload.get("embedding_sets")
    if not isinstance(row_counts, dict):
        return "partial"
    document_chunks = row_counts.get("document_chunks")
    chunk_embeddings = row_counts.get("chunk_embeddings")
    has_rows = (
        isinstance(document_chunks, int)
        and isinstance(chunk_embeddings, int)
        and document_chunks > 0
        and chunk_embeddings > 0
    )
    has_embedding_set = isinstance(embedding_sets, list) and len(embedding_sets) > 0
    has_active_index = isinstance(index_versions, list) and any(
        isinstance(item, dict) and item.get("status") == "active" for item in index_versions
    )
    return "ready" if has_rows and has_embedding_set and has_active_index else "partial"


def _database_endpoint(database_url: str) -> str:
    normalized = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    parsed = urllib.parse.urlparse(normalized)
    host = parsed.hostname or "unknown-host"
    port = parsed.port or 5432
    return f"{host}:{port}"


def _redact_error_text(value: str) -> str:
    return value.replace("\n", " ")[:1200]


def _write_report(report: JsonObject, output_path: Path | None) -> None:
    if output_path is None:
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    sys.exit(main())
