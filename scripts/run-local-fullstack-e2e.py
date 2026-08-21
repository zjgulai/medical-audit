#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID, uuid4

import uvicorn

from medical_audit_kb.api.agent_store import SqlAlchemyAgentStore
from medical_audit_kb.api.analytics_upload_store import SqlAlchemyAnalyticsUploadStore
from medical_audit_kb.api.app import ApiState, create_app
from medical_audit_kb.api.audit_finding_store import SqlAlchemyAuditFindingStore
from medical_audit_kb.api.audit_log_store import SqlAlchemyAuditLogStore
from medical_audit_kb.api.auth_user_store import SqlAlchemyAuthUserStore
from medical_audit_kb.api.document_upload_store import SqlAlchemyDocumentUploadStore
from medical_audit_kb.api.local_acceptance import LOCAL_ACCEPTANCE_CHAT_MODEL_ENV
from medical_audit_kb.api.project_member_store import SqlAlchemyProjectMemberStore
from medical_audit_kb.api.query_history_store import SqlAlchemyQueryHistoryStore
from medical_audit_kb.api.review_task_store import SqlAlchemyReviewTaskStore
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
from medical_audit_kb.ocr.unlimited_ocr import UnlimitedOcrPage, UnlimitedOcrResult
from medical_audit_kb.retrieval.hybrid_search import HybridSearchEngine
from medical_audit_kb.retrieval.rerank import FakeRerankProvider

JsonObject = dict[str, object]


class _DeterministicFakeOcrClient:
    engine = "local/deterministic-fake-ocr"
    source_version = "local-fullstack-fake-v1"
    max_pages = 1
    pdf_dpi = 72

    async def extract_text(
        self,
        *,
        file_name: str,
        extension: str,
        content: bytes,
    ) -> UnlimitedOcrResult:
        del file_name, extension
        image_sha256 = hashlib.sha256(content).hexdigest()
        text = "第一页：确定性 Fake OCR 本地验收文本。"
        text_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return UnlimitedOcrResult(
            text=text,
            page_count=1,
            model=self.engine,
            source_commit=self.source_version,
            pages=(
                UnlimitedOcrPage(
                    page_number=1,
                    text=text,
                    image_sha256=image_sha256,
                    text_sha256=text_sha256,
                    mapping_status="resolved",
                ),
            ),
            method="deterministic-fake",
        )


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
        previous_chat_model_env = _set_local_acceptance_chat_model_env()
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
            command = [pnpm, "--dir", "web", "e2e", "--workers=1"]
            env = {
                **dict(os.environ),
                "MEDICAL_AUDIT_API_BASE_URL": backend_url,
            }
            env.pop("NO_COLOR", None)
            result = subprocess.run(command, cwd=repo_root, env=env, check=False)
            workflow_receipts, database_snapshot = _run_business_workflow_acceptance(
                backend_url=backend_url,
                database_path=temp_root / "acceptance.db",
            )
            workflow_passed = all(
                receipt.get("status") == "pass" for receipt in workflow_receipts
            )
            report = _local_feature_acceptance_report(
                repo_root=repo_root,
                backend_url=backend_url,
                status="pass"
                if result.returncode == 0 and workflow_passed
                else "fail",
                workflow_receipts=workflow_receipts,
                database_snapshot=database_snapshot,
            )
            output_path = (
                Path(args.json_output)
                if args.json_output
                else repo_root / "tmp/outputs/local-fullstack-feature-acceptance-latest.json"
            )
            _write_report(report, output_path)
            return 0 if report["status"] == "pass" else 1
        finally:
            _restore_env(previous_chat_model_env)
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
            "Run local Next + FastAPI Playwright E2E with a temporary SQLite backend and fake "
            "providers. This command does not use production data or external providers."
        )
    )
    parser.add_argument(
        "--backend-mode",
        choices=("in-memory", "postgres-readonly"),
        default="in-memory",
        help=(
            "in-memory runs full Playwright E2E against a temporary SQLite fake-provider backend; "
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
    app = create_app(
        _api_state(temp_root),
        enforce_controlled_api_auth=True,
        api_access_mode="header-transition-test",
    )
    uvicorn.run(app, host=host, port=port, log_level="warning")


def _set_local_acceptance_chat_model_env() -> dict[str, str | None]:
    previous = {name: os.environ.get(name) for name in LOCAL_ACCEPTANCE_CHAT_MODEL_ENV}
    os.environ.update(LOCAL_ACCEPTANCE_CHAT_MODEL_ENV)
    return previous


def _restore_env(previous: dict[str, str | None]) -> None:
    for name, value in previous.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


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
        database_url="postgresql+psycopg://local-acceptance:unused@127.0.0.1:1/unused",
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
    # Production configuration remains PostgreSQL-only. This isolated acceptance process
    # deliberately replaces the validated URL after construction so no project Store can
    # reach a real database while the E2E run exercises persistent SQLAlchemy behavior.
    settings = settings.model_copy(
        update={"database_url": f"sqlite:///{temp_root / 'acceptance.db'}"}
    )
    state = ApiState.from_settings(settings)
    state.audit_finding_store = SqlAlchemyAuditFindingStore(
        settings.database_url,
        create_schema=True,
    )
    state.audit_log_store = SqlAlchemyAuditLogStore(settings.database_url)
    state.agent_store = SqlAlchemyAgentStore(settings.database_url)
    state.project_member_store = SqlAlchemyProjectMemberStore(settings.database_url)
    state.review_task_store = SqlAlchemyReviewTaskStore(settings.database_url)
    state.analytics_upload_store = SqlAlchemyAnalyticsUploadStore(
        settings.database_url,
        upload_root=settings.index_root / "analytics-uploads",
    )
    state.document_upload_store = SqlAlchemyDocumentUploadStore(
        settings.database_url,
        upload_root=settings.index_root / "document-uploads",
    )
    state.query_history_store = SqlAlchemyQueryHistoryStore(settings.database_url)
    state.auth_user_store = SqlAlchemyAuthUserStore(settings.database_url)
    state.ocr_client = _DeterministicFakeOcrClient()
    state.search_engine = _search_engine(source_file.relative_to(source_root).as_posix())
    _seed_local_acceptance_business_state(state)
    return state


def _seed_local_acceptance_business_state(state: ApiState) -> None:
    store = state.review_task_store
    if store is None:
        raise RuntimeError("local acceptance review task store is unavailable")
    project_store = state.project_member_store
    if project_store is None:
        raise RuntimeError("local acceptance project member store is unavailable")
    project_store.add_member(
        "SELF-CHECK-FUND-20260607",
        {
            "user_identifier": "local-signoff-technician",
            "name": "本地签发权限技术员",
            "role": "信息科",
            "department": "信息科",
            "status": "在项目中",
            "created_by": "local-fullstack-acceptance",
        },
    )
    now = "2026-08-13T00:00:00Z"
    store.add_task(
        {
            "task_id": "local-acceptance-signoff-ready",
            "created_at": now,
            "updated_at": now,
            "status": "not-violation",
            "status_label": "未发现违规",
            "question": "本地报告签发权限与重复签发验收",
            "citation_count": 0,
            "review_gate": "本地确定性验收任务",
            "confidence_label": "已复核",
            "fallback_label": "not-applicable",
            "reviewer_note": "主任已复核",
            "conclusion": "未发现违规",
            "created_by": "next-member",
            "assigned_to": "next-member",
            "source": "local-fullstack-acceptance",
            "dossier": {
                "project_key": "SELF-CHECK-FUND-20260607",
                "owner_signoff": {
                    "status": "approved",
                    "confirmed_by": "next-director",
                    "confirmed_at": now,
                },
            },
        }
    )


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


def _run_business_workflow_acceptance(
    *,
    backend_url: str,
    database_path: Path,
) -> tuple[list[JsonObject], JsonObject]:
    before = _sqlite_acceptance_snapshot(database_path)
    receipts = [
        _accept_remediation_workflow(backend_url),
        _accept_report_signoff_workflow(backend_url),
        _accept_project_workflow(backend_url),
        _accept_ocr_workflow(backend_url),
    ]
    after = _sqlite_acceptance_snapshot(database_path)
    for receipt in receipts:
        receipt["database_snapshot_before"] = before
        receipt["database_snapshot_after"] = after
    return receipts, {"before": before, "after": after}


def _accept_remediation_workflow(backend_url: str) -> JsonObject:
    member = _role_headers("next-member", "member")
    director = _role_headers("next-director", "director")
    technician = _role_headers("next-technician", "technician")
    admin = _role_headers("project-admin", "admin")

    empty = _load_json(f"{backend_url}/remediation/workbench", headers=member)
    _require_acceptance(
        empty.get("data_mode") == "persistent"
        and empty.get("remediation_cases") == []
        and empty.get("evidence_requests") == [],
        "persistent empty remediation workbench must not fall back to sample data",
    )
    created = _post_json(
        f"{backend_url}/remediation/items",
        {
            "title": "本地全栈整改状态机",
            "description": "临时 SQLite 副作用验收",
            "project_key": "SELF-CHECK-FUND-20260607",
        },
        headers=member,
    )
    item = _dict_object(created.get("item"), "created remediation item")
    item_id = _str_object(item.get("id"), "remediation item id")
    UUID(item_id)
    attachment = _post_multipart(
        f"{backend_url}/remediation/items/{item_id}/attachments",
        file_name="evidence.pdf",
        content=b"%PDF-1.4 local acceptance evidence",
        content_type="application/pdf",
        headers=member,
    )
    _require_acceptance(
        attachment.status == 200
        and _decode_json(attachment).get("item_id") == item_id,
        "remediation attachment must bind to the real UUID",
    )
    invalid = _post_json_response(
        f"{backend_url}/remediation/items/{item_id}/status",
        {"status": "unknown"},
        headers=member,
    )
    skipped = _post_json_response(
        f"{backend_url}/remediation/items/{item_id}/status",
        {"status": "pending-acceptance"},
        headers=member,
    )
    status_codes: dict[str, int] = {
        "invalid-status": invalid.status,
        "skipped-transition": skipped.status,
    }
    for target in ("in-rectification", "pending-acceptance"):
        response = _post_json_response(
            f"{backend_url}/remediation/items/{item_id}/status",
            {"status": target, "note": f"进入 {target}"},
            headers=member,
        )
        status_codes[f"member-{target}"] = response.status
    for role, headers in (
        ("member", member),
        ("technician", technician),
        ("admin", admin),
    ):
        response = _post_json_response(
            f"{backend_url}/remediation/items/{item_id}/status",
            {"status": "accepted"},
            headers=headers,
        )
        status_codes[f"{role}-accept-denied"] = response.status
    for target in ("accepted", "closed"):
        response = _post_json_response(
            f"{backend_url}/remediation/items/{item_id}/status",
            {"status": target, "note": f"主任进入 {target}"},
            headers=director,
        )
        status_codes[f"director-{target}"] = response.status
    closed_transition = _post_json_response(
        f"{backend_url}/remediation/items/{item_id}/status",
        {"status": "rejected"},
        headers=director,
    )
    closed_upload = _post_multipart(
        f"{backend_url}/remediation/items/{item_id}/attachments",
        file_name="closed.pdf",
        content=b"%PDF-1.4 closed",
        content_type="application/pdf",
        headers=member,
    )
    status_codes.update(
        {
            "closed-transition": closed_transition.status,
            "closed-upload": closed_upload.status,
        }
    )
    expected = {
        "invalid-status": 422,
        "skipped-transition": 409,
        "member-in-rectification": 200,
        "member-pending-acceptance": 200,
        "member-accept-denied": 403,
        "technician-accept-denied": 403,
        "admin-accept-denied": 403,
        "director-accepted": 200,
        "director-closed": 200,
        "closed-transition": 409,
        "closed-upload": 409,
    }
    _require_acceptance(
        status_codes == expected,
        f"remediation status matrix drifted: {status_codes}",
    )
    return _workflow_receipt(
        feature_id="workflow-remediation-state-and-attachment",
        roles=["member", "director", "technician", "admin"],
        steps=status_codes,
        expected_state="UUID attachment persisted; server state machine and closed lock enforced",
        database_side_effect=(
            "remediation_items +1; document_upload_records +1; "
            "audit_log_events increased"
        ),
        failure_recovery="discard the temporary SQLite directory and rerun",
    )


def _accept_report_signoff_workflow(backend_url: str) -> JsonObject:
    task_id = "local-acceptance-signoff-ready"
    endpoint = f"{backend_url}/reports/drafts/{task_id}/signoff"
    statuses: dict[str, int] = {}
    for role, user_id in (
        ("member", "next-member"),
        ("technician", "local-signoff-technician"),
        ("admin", "project-admin"),
    ):
        response = _post_json_response(
            endpoint,
            {"signoff_note": "越权签发必须失败"},
            headers=_role_headers(user_id, role),
        )
        statuses[f"{role}-signoff-denied"] = response.status
    invisible = _post_json_response(
        endpoint,
        {"signoff_note": "不可见任务必须隐藏"},
        headers=_role_headers("unrelated-director", "director"),
    )
    signed = _post_json_response(
        endpoint,
        {"signoff_note": "主任本地签发"},
        headers=_role_headers("next-director", "director"),
    )
    duplicate = _post_json_response(
        endpoint,
        {"signoff_note": "重复签发"},
        headers=_role_headers("next-director", "director"),
    )
    statuses.update(
        {
            "invisible-director": invisible.status,
            "director-signoff": signed.status,
            "duplicate-signoff": duplicate.status,
        }
    )
    expected = {
        "member-signoff-denied": 403,
        "technician-signoff-denied": 403,
        "admin-signoff-denied": 403,
        "invisible-director": 404,
        "director-signoff": 200,
        "duplicate-signoff": 409,
    }
    _require_acceptance(statuses == expected, f"report signoff matrix drifted: {statuses}")
    signed_payload = _decode_json(signed)
    _require_acceptance(
        signed_payload.get("signed_by") == "next-director",
        "report signoff did not bind the director identity",
    )
    return _workflow_receipt(
        feature_id="workflow-report-signoff-permissions",
        roles=["member", "director", "technician", "admin"],
        steps=statuses,
        expected_state="only visible director signs; duplicate and hidden task remain blocked",
        database_side_effect="review_tasks signed_report updated once; audit_log_events increased",
        failure_recovery="discard the temporary SQLite directory and rerun",
    )


def _accept_project_workflow(backend_url: str) -> JsonObject:
    admin = _role_headers("project-admin", "admin")
    project_key = "LOCAL-FULLSTACK-20260813"
    member_denied = _post_json_response(
        f"{backend_url}/projects",
        {
            "project_key": project_key,
            "name": "本地全栈项目",
            "scenario_key": "charging-compliance",
            "audit_topic": "医保基金使用合规",
            "organization_name": "临时测试医院",
        },
        headers=_role_headers("next-member", "member"),
    )
    created = _post_json_response(
        f"{backend_url}/projects",
        {
            "project_key": project_key,
            "name": "本地全栈项目",
            "scenario_key": "charging-compliance",
            "audit_topic": "医保基金使用合规",
            "organization_name": "临时测试医院",
            "owner_department": "内审部",
            "description": "临时 SQLite 项目、成员与文件验收",
        },
        headers=admin,
    )
    member_added = _post_json_response(
        f"{backend_url}/projects/{project_key}/members",
        {
            "user_identifier": "local-project-member",
            "name": "本地项目成员",
            "role": "审计员",
            "department": "内审部",
            "status": "在项目中",
        },
        headers=admin,
    )
    file_uploaded = _post_multipart(
        f"{backend_url}/projects/{project_key}/files",
        file_name="audit-note.md",
        content=b"# local audit evidence",
        content_type="text/markdown",
        headers=admin,
        fields={"department": "内审部", "document_type": "审计资料"},
    )
    statuses = {
        "member-create-project-denied": member_denied.status,
        "admin-create-project": created.status,
        "admin-add-member": member_added.status,
        "admin-upload-project-file": file_uploaded.status,
    }
    expected = {
        "member-create-project-denied": 403,
        "admin-create-project": 201,
        "admin-add-member": 200,
        "admin-upload-project-file": 201,
    }
    _require_acceptance(statuses == expected, f"project workflow drifted: {statuses}")
    return _workflow_receipt(
        feature_id="workflow-project-member-file-persistence",
        roles=["member", "admin"],
        steps=statuses,
        expected_state="project, creator/member and file persist with permission denial evidence",
        database_side_effect=(
            "audit_projects +1; audit_project_members +2; document_upload_records +1; "
            "audit_log_events increased"
        ),
        failure_recovery="discard the temporary SQLite directory and rerun",
    )


def _accept_ocr_workflow(backend_url: str) -> JsonObject:
    response = _post_multipart(
        f"{backend_url}/ocr/extract",
        file_name="local-acceptance.png",
        content=b"deterministic-local-image-bytes",
        content_type="image/png",
        headers=_role_headers("project-admin", "admin"),
    )
    payload = _decode_json(response)
    pages = payload.get("pages")
    passed = (
        response.status == 200
        and payload.get("engine") == "local/deterministic-fake-ocr"
        and payload.get("mapping_status") == "resolved"
        and isinstance(pages, list)
        and len(pages) == 1
    )
    _require_acceptance(passed, f"deterministic Fake OCR workflow drifted: {payload}")
    receipt = _workflow_receipt(
        feature_id="workflow-ocr-deterministic-fake",
        roles=["admin"],
        steps={"fake-ocr-extract": response.status},
        expected_state="one page of deterministic mapped OCR evidence is returned",
        database_side_effect="audit_log_events increased; source text was not persisted",
        failure_recovery="discard the temporary SQLite directory and rerun",
    )
    receipt["fake_provider_invoked"] = True
    receipt["external_provider_call"] = False
    return receipt


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


def _role_headers(user_id: str, role: str) -> dict[str, str]:
    return {
        "X-User-Id": user_id,
        "X-Role": role,
        "X-Tenant-Id": "hospital-demo",
        "X-Project-Key": "SELF-CHECK-FUND-20260607",
    }


def _post_json_response(
    url: str,
    payload: dict[str, object],
    *,
    headers: dict[str, str],
) -> urllib.response.addinfourl:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    return _open_response(request)


def _post_multipart(
    url: str,
    *,
    file_name: str,
    content: bytes,
    content_type: str,
    headers: dict[str, str],
    fields: dict[str, str] | None = None,
) -> urllib.response.addinfourl:
    boundary = f"medical-audit-local-{uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in (fields or {}).items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'
            ).encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            content,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    request = urllib.request.Request(
        url,
        data=b"".join(chunks),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", **headers},
        method="POST",
    )
    return _open_response(request)


def _open_response(request: urllib.request.Request) -> urllib.response.addinfourl:
    try:
        return urllib.request.urlopen(request, timeout=10)
    except urllib.error.HTTPError as exc:
        return exc


def _decode_json(response: urllib.response.addinfourl) -> dict[str, object]:
    raw = response.read()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"unexpected JSON payload from {response.url}: {payload!r}")
    return payload


def _dict_object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} must be an object")
    return value


def _str_object(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"{label} must be a non-empty string")
    return value


def _require_acceptance(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _workflow_receipt(
    *,
    feature_id: str,
    roles: list[str],
    steps: dict[str, int],
    expected_state: str,
    database_side_effect: str,
    failure_recovery: str,
) -> JsonObject:
    return {
        "feature_id": feature_id,
        "status": "pass",
        "precondition": "isolated temporary SQLite and deterministic fake providers",
        "roles": roles,
        "steps": steps,
        "expected_state": expected_state,
        "database_side_effect": database_side_effect,
        "failure_recovery": failure_recovery,
        "local_evidence": "live HTTP against local FastAPI and persistent SQLite stores",
        "production_evidence": "not_production_verified",
        "provider_call": False,
    }


def _sqlite_acceptance_snapshot(database_path: Path) -> JsonObject:
    tables = (
        "audit_projects",
        "audit_project_members",
        "remediation_items",
        "review_tasks",
        "review_actions",
        "document_upload_records",
        "query_logs",
        "audit_log_events",
    )
    with sqlite3.connect(database_path) as connection:
        available = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        counts = {
            table: int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            for table in tables
            if table in available
        }
    return {"database": "temporary-sqlite", "table_counts": counts}


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


def _local_feature_acceptance_report(
    *,
    repo_root: Path,
    backend_url: str,
    status: str,
    workflow_receipts: list[JsonObject],
    database_snapshot: JsonObject,
) -> JsonObject:
    routes = (
        "/",
        "/login",
        "/workspace",
        "/medical-audit",
        "/fund-compliance",
        "/fund-compliance/review",
        "/chat",
        "/agents",
        "/agent-market",
        "/analytics",
        "/projects",
        "/audit-cockpit",
        "/documents",
        "/ocr",
        "/knowledge-base",
        "/graph",
        "/rules",
        "/reports",
        "/remediation",
        "/archive",
        "/guided-check",
    )
    aliases = ("/findings", "/knowledge-query")
    feature_receipts: list[JsonObject] = [
        {
            "feature_id": f"route-{index:02d}",
            "route": route,
            "roles": ["member", "director", "technician", "admin"],
            "precondition": "temporary-sqlite-and-deterministic-fake-provider",
            "steps": [
                "open the route through Playwright",
                "exercise the route-specific local interaction contract",
                "assert the expected page state",
            ],
            "expected_state": "route-and-associated-local-interactions-pass",
            "database_side_effect": "isolated-temporary-sqlite-only",
            "failure_recovery": "discard-temporary-directory-and-rerun",
            "local_evidence": "playwright-local-fullstack",
            "production_evidence": "not_production_verified",
        }
        for index, route in enumerate(routes, start=1)
    ]
    feature_receipts.extend(
        {
            "feature_id": f"alias-{index:02d}",
            "route": route,
            "roles": ["member", "director", "technician", "admin"],
            "precondition": "temporary-sqlite-and-deterministic-fake-provider",
            "steps": [
                "open the compatibility alias",
                "resolve the canonical product surface",
                "assert the alias contract",
            ],
            "expected_state": "compatibility-route-resolves-to-canonical-product-route",
            "database_side_effect": "none",
            "failure_recovery": "use-canonical-route-and-rerun",
            "local_evidence": "playwright-local-fullstack",
            "production_evidence": "not_production_verified",
        }
        for index, route in enumerate(aliases, start=1)
    )
    feature_receipts.extend(workflow_receipts)
    candidate_identity = _candidate_identity(repo_root)
    return {
        "format": "medical-audit-feature-acceptance-v1",
        "run_id": f"local-{int(time.time())}",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": status,
        "git_sha": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "candidate_identity": candidate_identity,
        "backend_url": backend_url,
        "data_store": "temporary-sqlite",
        "provider_call": False,
        "external_provider_smoke": "not_run",
        "api_access_mode": "header-transition-test",
        "independent_route_count": len(routes),
        "alias_count": len(aliases),
        "aliases": list(aliases),
        "workflow_count": len(workflow_receipts),
        "feature_count": len(feature_receipts),
        "database_snapshot": database_snapshot,
        "feature_receipts": feature_receipts,
        "evidence_grade": "L2-local-live",
        "production_side_effect": "none",
    }


def _candidate_identity(repo_root: Path) -> JsonObject:
    branch, branch_source = _candidate_branch(repo_root)
    status_lines = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    changed_files: list[dict[str, object]] = []
    for line in status_lines:
        if len(line) < 4:
            continue
        status = line[:2]
        relative_path = line[3:]
        if " -> " in relative_path:
            relative_path = relative_path.split(" -> ", maxsplit=1)[1]
        path = repo_root / relative_path
        changed_files.append(
            {
                "path": relative_path,
                "status": status,
                "sha256": _file_sha256(path) if path.is_file() else None,
            }
        )
    manifest_payload = json.dumps(
        changed_files,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "branch": branch,
        "branch_source": branch_source,
        "worktree_dirty": bool(changed_files),
        "changed_file_count": len(changed_files),
        "changed_files": changed_files,
        "manifest_sha256": hashlib.sha256(manifest_payload).hexdigest(),
    }


def _candidate_branch(repo_root: Path) -> tuple[str, str]:
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if branch:
        return branch, "git-symbolic-ref"
    for variable, source in (
        ("GITHUB_HEAD_REF", "github-head-ref"),
        ("GITHUB_REF_NAME", "github-ref-name"),
    ):
        if value := os.getenv(variable, "").strip():
            return value, source
    commit = subprocess.run(
        ["git", "rev-parse", "--short=12", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return f"detached@{commit}", "detached-head"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
