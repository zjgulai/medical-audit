#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from http.client import HTTPMessage
from pathlib import Path
from typing import IO

DEFAULT_BASE_URL = "https://audit.lute-tlz-dddd.top"
DEFAULT_QUESTION = "医保基金审核发现异常收费时应优先核验证据链的哪些要点？"
DEFAULT_REGRESSION_URLS: tuple[str, ...] = ()
SHARED_EDGE_REGRESSION_URLS = (
    "https://kg.lute-tlz-dddd.top/",
    "https://video.lute-tlz-dddd.top/",
    "https://voc.lute-tlz-dddd.top/",
    "https://lute-tlz-dddd.top/",
)
DEFAULT_TENANT_ID = "hospital-demo"
DEFAULT_PROJECT_KEY = "SELF-CHECK-FUND-20260607"
DEFAULT_USER_ID = "production-smoke-auditor"
DEFAULT_ADMIN_USER_ID = "production-smoke-admin"
DEFAULT_USER_ROLE = "auditor"
PUBLIC_SHELL_ACCESS_MODE = "public-shell-readonly"
HEADER_TRANSITION_ACCESS_MODE = "header-transition-test"
REQUIRED_PAGE_TEXTS = {
    PUBLIC_SHELL_ACCESS_MODE: ("AI审计一体化协作平台", "登录暂未开放"),
    HEADER_TRANSITION_ACCESS_MODE: ("AI审计一体化协作平台", "登录工作台"),
}
REQUIRED_PAGE_PATHS = ("/", "/login")


class SmokeError(RuntimeError):
    pass


def _url_origin(url: str) -> tuple[str, str, int]:
    parsed = urllib.parse.urlsplit(url)
    scheme = parsed.scheme.lower()
    if (
        scheme not in {"http", "https"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.hostname is None
    ):
        raise SmokeError("request URL has an invalid origin")
    try:
        port = parsed.port
    except ValueError as exc:
        raise SmokeError("request URL has an invalid origin") from exc
    if port is None:
        port = 443 if scheme == "https" else 80
    return scheme, parsed.hostname.lower(), port


class _SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, expected_origin: tuple[str, str, int]) -> None:
        super().__init__()
        self.expected_origin = expected_origin

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        redirect_url = urllib.parse.urljoin(req.full_url, newurl)
        if _url_origin(redirect_url) != self.expected_origin:
            raise SmokeError("cross-origin redirect rejected")
        return super().redirect_request(req, fp, code, msg, headers, redirect_url)


@dataclass(frozen=True)
class HttpResponse:
    status: int
    url: str
    text: str
    headers: dict[str, str]


@dataclass(frozen=True)
class SmokeAuth:
    api_key: str | None
    admin_api_key: str | None
    api_key_env: str | None
    admin_api_key_env: str | None
    tenant_id: str = DEFAULT_TENANT_ID
    project_key: str = DEFAULT_PROJECT_KEY
    user_id: str = DEFAULT_USER_ID
    user_role: str = DEFAULT_USER_ROLE
    admin_user_id: str = DEFAULT_ADMIN_USER_ID
    admin_role: str = "it-admin"
    include_context_headers: bool = False

    def headers(self, *, admin: bool = False) -> dict[str, str]:
        token = self.admin_api_key if admin else self.api_key
        if token is None:
            token = self.api_key if admin else self.admin_api_key
        headers: dict[str, str] = {}
        if token is not None:
            headers["X-API-Key"] = token
        if self.include_context_headers:
            headers.update(
                {
                    "X-User-Id": self.admin_user_id if admin else self.user_id,
                    "X-Role": self.admin_role if admin else self.user_role,
                    "X-Project-Key": self.project_key,
                    "X-Tenant-Id": self.tenant_id,
                }
            )
        elif admin:
            headers["X-Role"] = self.admin_role
        return headers

    def to_report_dict(self) -> dict[str, object]:
        return {
            "api_key_env": self.api_key_env,
            "admin_api_key_env": self.admin_api_key_env,
            "admin_role": self.admin_role,
            "api_key_configured": self.api_key is not None,
            "admin_api_key_configured": self.admin_api_key is not None,
            "tenant_id": self.tenant_id,
            "project_key": self.project_key,
            "user_role": self.user_role,
        }


def main() -> int:
    args = _parse_args()
    base_url = str(args.base_url).rstrip("/")
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    steps: list[dict[str, object]] = []
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    try:
        _validate_side_effect_authorization(args)
        auth = _auth_from_args(args)
        _run_step(
            steps,
            "tls-certificate-san",
            lambda: _check_certificate_san(
                host=str(args.expected_cert_host),
                timeout_seconds=float(args.timeout_seconds),
            ),
        )
        _run_step(
            steps,
            "health",
            lambda: _check_health(base_url, timeout_seconds=float(args.timeout_seconds)),
        )
        if args.access_mode == PUBLIC_SHELL_ACCESS_MODE:
            _run_step(
                steps,
                "runtime-access",
                lambda: _check_deployment_metadata(
                    base_url,
                    timeout_seconds=float(args.timeout_seconds),
                ),
            )
            _run_step(
                steps,
                "protected-catalog",
                lambda: _check_protected_catalog(
                    base_url,
                    timeout_seconds=float(args.timeout_seconds),
                ),
            )
            steps.append(
                {
                    "name": "search-backend",
                    "passed": True,
                    "details": {
                        "status": "not_run",
                        "reason": "blocked-by-public-shell-access-mode",
                    },
                }
            )
        else:
            _run_step(
                steps,
                "search-backend",
                lambda: _check_search_backend(
                    base_url,
                    auth=auth,
                    expected_matching_embeddings=int(args.expected_matching_embeddings),
                    timeout_seconds=float(args.timeout_seconds),
                ),
            )
        _run_step(
            steps,
            "page-rendering",
            lambda: _check_pages(
                base_url,
                auth=auth if args.access_mode == HEADER_TRANSITION_ACCESS_MODE else None,
                access_mode=str(args.access_mode),
                timeout_seconds=float(args.timeout_seconds),
            ),
        )
        steps.append(
            {
                "name": "audit-logs-permission",
                "passed": True,
                "details": {
                    "status": "not_run",
                    "reason": "legacy-audit-logs-page-retired",
                },
            }
        )
        if args.include_query_provider_smoke:
            query_details = _run_step(
                steps,
                "query-api-with-citations",
                lambda: _check_query_api(
                    base_url,
                    auth=auth,
                    question=str(args.question),
                    require_generated_answer=bool(args.require_generated_answer),
                    timeout_seconds=float(args.timeout_seconds),
                ),
            )
            first_chunk_id = str(query_details["first_chunk_id"])
            _run_step(
                steps,
                "citation-preview",
                lambda: _check_preview(
                    base_url,
                    auth=auth,
                    chunk_id=first_chunk_id,
                    timeout_seconds=float(args.timeout_seconds),
                ),
            )
            _run_step(
                steps,
                "chat-dossier-export",
                lambda: _check_chat_export(
                    base_url,
                    auth=auth,
                    question=str(args.question),
                    timeout_seconds=float(args.timeout_seconds),
                ),
            )
        else:
            for step_name in (
                "query-api-with-citations",
                "citation-preview",
                "chat-dossier-export",
            ):
                steps.append(
                    {
                        "name": step_name,
                        "passed": True,
                        "details": {
                            "status": "not_run",
                            "reason": "requires-explicit-production-write-authorization",
                        },
                    }
                )
        if args.include_review_write:
            _run_step(
                steps,
                "review-flow-create-update-export",
                lambda: _check_review_task_flow(
                    base_url,
                    auth=auth,
                    question=str(args.question),
                    timeout_seconds=float(args.timeout_seconds),
                ),
            )
        regression_urls = _selected_regression_urls(args)
        if regression_urls:
            _run_step(
                steps,
                "edge-regression",
                lambda: _check_regression_urls(
                    regression_urls,
                    timeout_seconds=float(args.timeout_seconds),
                ),
            )
        else:
            steps.append(
                {
                    "name": "edge-regression",
                    "passed": True,
                    "details": {
                        "status": "not_run",
                        "reason": "shared-edge-regression-is-opt-in",
                        "urls": {},
                    },
                }
            )
    except SmokeError:
        report = _report(
            status="fail",
            base_url=base_url,
            question=str(args.question),
            started_at=started_at,
            steps=steps,
            auth=auth if "auth" in locals() else None,
            args=args,
        )
        _write_report(report_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    report = _report(
        status="pass",
        base_url=base_url,
        question=str(args.question),
        started_at=started_at,
        steps=steps,
        auth=auth,
        args=args,
    )
    _write_report(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run production E2E smoke against the deployed AuditScope website.",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--expected-cert-host", default="audit.lute-tlz-dddd.top")
    parser.add_argument("--expected-matching-embeddings", type=int, default=48985)
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    parser.add_argument(
        "--access-mode",
        choices=(PUBLIC_SHELL_ACCESS_MODE, HEADER_TRANSITION_ACCESS_MODE),
        default=PUBLIC_SHELL_ACCESS_MODE,
        help="Production runtime access contract to validate.",
    )
    parser.add_argument(
        "--report",
        default="tmp/outputs/production-e2e-smoke-latest.json",
    )
    parser.add_argument(
        "--api-key-env",
        default=None,
        help=(
            "Environment variable containing the auditor API secret. "
            "The secret value is never written to the report."
        ),
    )
    parser.add_argument(
        "--admin-api-key-env",
        default=None,
        help=(
            "Environment variable containing the it-admin API secret. "
            "The secret value is never written to the report."
        ),
    )
    parser.add_argument(
        "--admin-role",
        default="it-admin",
        help="Role used for backend admin checks.",
    )
    parser.add_argument("--tenant-id", default=DEFAULT_TENANT_ID)
    parser.add_argument("--project-key", default=DEFAULT_PROJECT_KEY)
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--user-role", default=DEFAULT_USER_ROLE)
    parser.add_argument("--admin-user-id", default=DEFAULT_ADMIN_USER_ID)
    parser.add_argument(
        "--regression-url",
        action="append",
        default=None,
        help=(
            "Optional extra public URL to regression-check. No URLs are checked by default; "
            "can be supplied multiple times."
        ),
    )
    parser.add_argument(
        "--include-shared-edge-regression",
        action="store_true",
        help=(
            "Opt in to legacy shared-domain checks for kg/video/voc/root. "
            "These are outside the default medical_audit release smoke."
        ),
    )
    parser.add_argument(
        "--include-query-provider-smoke",
        action="store_true",
        help=(
            "Opt in to POST /query and chat export. These paths can write query/audit "
            "history and call the configured answer provider, so --confirm-production-write "
            "is also required."
        ),
    )
    parser.add_argument(
        "--include-review-write",
        dest="include_review_write",
        action="store_true",
        help=(
            "Opt in to the persistent review flow create/update/export check. Requires "
            "--include-query-provider-smoke and --confirm-production-write."
        ),
    )
    parser.add_argument(
        "--skip-review-write",
        dest="include_review_write",
        action="store_false",
        help="Deprecated compatibility flag. Production smoke is read-only by default.",
    )
    parser.add_argument(
        "--confirm-production-write",
        default="",
        help=(
            "Required for query/provider or review write smoke. Must equal the expected "
            "production certificate host."
        ),
    )
    parser.add_argument(
        "--require-generated-answer",
        action="store_true",
        help="Fail when /query returns fallback_used=true.",
    )
    parser.set_defaults(include_review_write=False)
    return parser.parse_args()


def _validate_side_effect_authorization(args: argparse.Namespace) -> None:
    include_query_provider_smoke = bool(args.include_query_provider_smoke)
    include_review_write = bool(args.include_review_write)
    if include_review_write and not include_query_provider_smoke:
        raise SmokeError(
            "--include-review-write requires --include-query-provider-smoke",
        )
    if bool(args.require_generated_answer) and not include_query_provider_smoke:
        raise SmokeError(
            "--require-generated-answer requires --include-query-provider-smoke",
        )
    if not (include_query_provider_smoke or include_review_write):
        return
    expected_host = str(args.expected_cert_host).strip()
    if str(args.confirm_production_write).strip() != expected_host:
        raise SmokeError(
            f"live smoke requires --confirm-production-write {expected_host}",
        )


def _selected_regression_urls(args: argparse.Namespace) -> tuple[str, ...]:
    urls: list[str] = []
    if bool(args.include_shared_edge_regression):
        urls.extend(SHARED_EDGE_REGRESSION_URLS)
    explicit_urls = args.regression_url or []
    urls.extend(str(url) for url in explicit_urls)
    return tuple(dict.fromkeys(urls))


def _auth_from_args(args: argparse.Namespace) -> SmokeAuth:
    api_key_env = _optional_env_name(args.api_key_env)
    admin_api_key_env = _optional_env_name(args.admin_api_key_env)
    api_key = _secret_from_env(api_key_env)
    admin_api_key = _secret_from_env(admin_api_key_env)
    admin_role = _optional_env_name(args.admin_role) or "it-admin"
    return SmokeAuth(
        api_key=api_key,
        admin_api_key=admin_api_key,
        admin_role=admin_role,
        tenant_id=str(args.tenant_id),
        project_key=str(args.project_key),
        user_id=str(args.user_id),
        user_role=str(args.user_role),
        admin_user_id=str(args.admin_user_id),
        include_context_headers=True,
        api_key_env=api_key_env,
        admin_api_key_env=admin_api_key_env,
    )


def _optional_env_name(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _secret_from_env(env_name: str | None) -> str | None:
    if env_name is None:
        return None
    value = os.getenv(env_name, "").strip()
    if not value:
        raise SmokeError(f"environment variable {env_name} is empty or unset")
    return value


def _run_step(
    steps: list[dict[str, object]],
    name: str,
    callback: Callable[[], object],
) -> dict[str, object]:
    try:
        details = callback()
    except Exception as exc:
        steps.append(
            {
                "name": name,
                "passed": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        raise SmokeError(name) from exc
    steps.append({"name": name, "passed": True, "details": details})
    return _ensure_dict(details)


def _check_certificate_san(*, host: str, timeout_seconds: float) -> dict[str, object]:
    context = ssl.create_default_context()
    with (
        socket.create_connection((host, 443), timeout=timeout_seconds) as raw_socket,
        context.wrap_socket(raw_socket, server_hostname=host) as tls_socket,
    ):
        cert = tls_socket.getpeercert()
    if not isinstance(cert, dict):
        raise SmokeError("certificate payload is empty")
    raw_subject_alt_names = cert.get("subjectAltName", ())
    subject_alt_names: list[str] = []
    if isinstance(raw_subject_alt_names, tuple):
        for entry in raw_subject_alt_names:
            if not isinstance(entry, tuple) or len(entry) != 2:
                continue
            key, value = entry
            if key == "DNS" and isinstance(value, str):
                subject_alt_names.append(value)
    _require(host in subject_alt_names, f"certificate SAN does not include {host}")
    return {"host": host, "san_count": len(subject_alt_names)}


def _check_health(base_url: str, *, timeout_seconds: float) -> dict[str, object]:
    payload = _get_json(f"{base_url}/health", timeout_seconds=timeout_seconds)
    _require(payload.get("status") == "ok", "health status is not ok")
    return {
        "status": payload.get("status"),
        "version": payload.get("version"),
        "data_root": payload.get("data_root"),
    }


def _check_search_backend(
    base_url: str,
    *,
    auth: SmokeAuth,
    expected_matching_embeddings: int,
    timeout_seconds: float,
) -> dict[str, object]:
    payload = _get_json(
        f"{base_url}/api/v1/knowledge-base/catalog",
        auth=auth,
        admin=True,
        timeout_seconds=timeout_seconds,
    )
    search_backend = _ensure_dict(payload.get("search_backend"))
    details = _ensure_dict(search_backend.get("details"))
    summary = _ensure_dict(payload.get("summary"))
    boundaries = _ensure_dict(payload.get("boundaries"))
    matching = _int_value(summary.get("current_search_embedding_count"))
    _require(search_backend.get("backend") == "postgres", "search backend is not postgres")
    _require(search_backend.get("ready") is True, "search backend is not ready")
    _require(
        matching >= expected_matching_embeddings,
        f"matching embeddings {matching} < expected {expected_matching_embeddings}",
    )
    _require(boundaries.get("database_write") is False, "catalog permits database writes")
    _require(boundaries.get("provider_call") is False, "catalog permits provider calls")
    _require(
        boundaries.get("query_history_write") is False,
        "catalog permits query history writes",
    )
    return {
        "backend": search_backend.get("backend"),
        "ready": search_backend.get("ready"),
        "matching_embedding_count": matching,
        "embedding_model": details.get("embedding_model"),
    }


def _check_deployment_metadata(
    base_url: str,
    *,
    timeout_seconds: float,
) -> dict[str, object]:
    payload = _get_json(
        f"{base_url}/api/v1/deployment/metadata",
        timeout_seconds=timeout_seconds,
    )
    runtime_access = _ensure_dict(payload.get("runtime_access"))
    expected: dict[str, object] = {
        "mode": PUBLIC_SHELL_ACCESS_MODE,
        "trusted_identity_ready": False,
        "protected_reads_allowed": False,
        "writes_allowed": False,
    }
    _require(runtime_access == expected, "deployment metadata runtime_access mismatch")
    return expected


def _check_protected_catalog(
    base_url: str,
    *,
    timeout_seconds: float,
) -> dict[str, object]:
    response = _get_text(
        f"{base_url}/api/v1/knowledge-base/catalog",
        timeout_seconds=timeout_seconds,
    )
    _require(response.status == 503, f"protected catalog returned {response.status}")
    try:
        payload = _ensure_dict(json.loads(response.text))
    except json.JSONDecodeError as exc:
        raise SmokeError("protected catalog response is not valid JSON") from exc
    detail = _ensure_dict(payload.get("detail"))
    _require(
        detail.get("code") == "trusted_identity_required",
        "protected catalog error code mismatch",
    )
    _require(
        detail.get("access_mode") == PUBLIC_SHELL_ACCESS_MODE,
        "protected catalog access mode mismatch",
    )
    cache_control = response.headers.get("cache-control", "")
    _require("no-store" in cache_control.lower(), "protected catalog permits caching")
    return {
        "status": response.status,
        "code": detail.get("code"),
        "access_mode": detail.get("access_mode"),
        "cache_control": cache_control,
    }


def _check_pages(
    base_url: str,
    *,
    auth: SmokeAuth | None,
    access_mode: str,
    timeout_seconds: float,
) -> dict[str, object]:
    pages: dict[str, object] = {}
    required_texts = REQUIRED_PAGE_TEXTS[access_mode]
    for path in REQUIRED_PAGE_PATHS:
        response = _get_text(
            f"{base_url}{path}",
            auth=auth,
            admin=path in {"/pages/index-admin", "/pages/audit-logs"},
            timeout_seconds=timeout_seconds,
        )
        _require(response.status == 200, f"{path} returned {response.status}")
        missing = [text for text in required_texts if text not in response.text]
        _require(not missing, f"{path} missing texts: {missing}")
        pages[path] = {"status": response.status, "bytes": len(response.text.encode())}
    return {"pages": pages}


def _check_audit_log_permissions(
    base_url: str,
    *,
    auth: SmokeAuth,
    timeout_seconds: float,
) -> dict[str, object]:
    denied_response = _get_text(
        f"{base_url}/pages/audit-logs",
        timeout_seconds=timeout_seconds,
    )
    _require(
        "需要审计日志权限后才能查看事件" in denied_response.text,
        "audit logs page should show permission-denied state without role",
    )

    allowed_response = _get_text(
        f"{base_url}/pages/audit-logs",
        auth=auth,
        admin=True,
        timeout_seconds=timeout_seconds,
    )
    _require(
        "需要审计日志权限后才能查看事件" not in allowed_response.text,
        "audit logs page still shows permission-denied under admin role",
    )
    _require(
        "审计日志台" in allowed_response.text and "audit-log-shell" in allowed_response.text,
        "audit logs page missing expected admin shell",
    )

    unauthorized_api = _request(
        f"{base_url}/audit/logs",
        method="GET",
        timeout_seconds=timeout_seconds,
    )
    _require(
        unauthorized_api.status in {401, 403},
        "audit logs API should return 401/403 without role",
    )

    authorized_api = _get_json(
        f"{base_url}/audit/logs",
        auth=auth,
        admin=True,
        timeout_seconds=timeout_seconds,
    )
    items = _ensure_list(authorized_api.get("items"))
    store = _ensure_dict(authorized_api.get("store"))
    filters = _ensure_dict(authorized_api.get("filters"))

    return {
        "audit_logs_page_denied_bytes": len(denied_response.text.encode()),
        "audit_logs_page_allowed_bytes": len(allowed_response.text.encode()),
        "audit_logs_api_item_count": len(items),
        "audit_log_store_ready": bool(store.get("ready")),
        "audit_log_filter_fields": list(filters.keys()),
    }


def _check_query_api(
    base_url: str,
    *,
    auth: SmokeAuth,
    question: str,
    require_generated_answer: bool,
    timeout_seconds: float,
) -> dict[str, object]:
    payload = {
        "question": question,
        "top_k": 5,
    }
    headers = {"Content-Type": "application/json"}
    headers.update(auth.headers())
    response = _request_json(
        f"{base_url}/api/v1/query",
        method="POST",
        body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        timeout_seconds=timeout_seconds,
    )
    citations = _ensure_list(response.get("citations"))
    basis_groups = _ensure_list(response.get("basis_groups"))
    _require(response.get("confidence") in {"medium", "high"}, "query confidence is too low")
    if require_generated_answer:
        _require(
            response.get("fallback_used") is False,
            "query response used fallback answer instead of generated answer",
        )
    _require(bool(citations), "query response has no citations")
    _require(bool(basis_groups), "query response has no basis groups")
    first_citation = _ensure_dict(citations[0])
    first_chunk_id = str(first_citation.get("chunk_id") or "")
    _require(bool(first_chunk_id), "first citation has no chunk id")
    return {
        "confidence": response.get("confidence"),
        "fallback_used": response.get("fallback_used"),
        "citation_count": len(citations),
        "basis_group_count": len(basis_groups),
        "first_chunk_id": first_chunk_id,
    }


def _check_preview(
    base_url: str,
    *,
    auth: SmokeAuth,
    chunk_id: str,
    timeout_seconds: float,
) -> dict[str, object]:
    response = _get_text(
        f"{base_url}/pages/preview/{chunk_id}",
        auth=auth,
        timeout_seconds=timeout_seconds,
    )
    _require(response.status == 200, f"preview returned {response.status}")
    _require(
        "原文证据预览" in response.text or "source" in response.text.lower(),
        "preview body invalid",
    )
    return {"status": response.status, "chunk_id": chunk_id, "bytes": len(response.text.encode())}


def _check_chat_export(
    base_url: str,
    *,
    auth: SmokeAuth,
    question: str,
    timeout_seconds: float,
) -> dict[str, object]:
    query = urllib.parse.urlencode({"question": question, "format": "markdown"})
    response = _get_text(
        f"{base_url}/pages/chat/export?{query}",
        auth=auth,
        timeout_seconds=timeout_seconds,
    )
    _require(response.status == 200, f"chat export returned {response.status}")
    _require(
        "引用" in response.text or "citation" in response.text.lower(),
        "export has no citations",
    )
    return {
        "status": response.status,
        "content_type": response.headers.get("content-type"),
        "bytes": len(response.text.encode()),
    }


def _check_review_task_flow(
    base_url: str,
    *,
    auth: SmokeAuth,
    question: str,
    timeout_seconds: float,
) -> dict[str, object]:
    create_response = _post_form(
        f"{base_url}/pages/review-tasks/create",
        {"question": question},
        auth=auth,
        admin=True,
        timeout_seconds=timeout_seconds,
    )
    _require(create_response.status == 200, f"review task create returned {create_response.status}")
    task_id = _first_review_task_id(create_response.text)
    update_response = _post_form(
        f"{base_url}/pages/review-tasks/{task_id}/status",
        {
            "status": "closed",
            "reviewer_note": "production e2e smoke",
            "conclusion": "deployment e2e passed",
        },
        auth=auth,
        admin=True,
        timeout_seconds=timeout_seconds,
    )
    _require(update_response.status == 200, f"review task update returned {update_response.status}")
    export_response = _get_json(
        f"{base_url}/review-tasks/{task_id}/export?format=json",
        auth=auth,
        admin=True,
        timeout_seconds=timeout_seconds,
    )
    _require(str(export_response.get("task_id")) == task_id, "review export task id mismatch")
    return {
        "task_id": task_id,
        "create_status": create_response.status,
        "update_status": update_response.status,
    }


def _check_regression_urls(
    urls: tuple[str, ...],
    *,
    timeout_seconds: float,
) -> dict[str, object]:
    results: dict[str, object] = {}
    for url in urls:
        response = _get_text(url, timeout_seconds=timeout_seconds)
        _require(200 <= response.status < 400, f"{url} returned {response.status}")
        results[url] = {"status": response.status, "effective_url": response.url}
    return {"urls": results}


def _first_review_task_id(html: str) -> str:
    task_ids: list[str] = re.findall(r"/review-tasks/([^/]+)/export\?format=json", html)
    if not task_ids:
        raise SmokeError("no review task export link found")
    return str(max(task_ids, key=_review_task_sort_key))


def _review_task_sort_key(task_id: str) -> tuple[int, str]:
    prefix = "review" + "-" + "task" + "-"
    suffix = task_id.removeprefix(prefix)
    if task_id.startswith(prefix) and suffix.isdigit():
        return (int(suffix), task_id)
    return (-1, task_id)


def _get_json(
    url: str,
    *,
    auth: SmokeAuth | None = None,
    admin: bool = False,
    timeout_seconds: float,
) -> dict[str, object]:
    return _request_json(
        url,
        method="GET",
        headers=_auth_headers(auth, admin=admin),
        timeout_seconds=timeout_seconds,
    )


def _request_json(
    url: str,
    *,
    method: str,
    timeout_seconds: float,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    response = _request(
        url,
        method=method,
        body=body,
        headers=headers,
        timeout_seconds=timeout_seconds,
    )
    _require(200 <= response.status < 300, f"{url} returned {response.status}")
    payload = json.loads(response.text)
    return _ensure_dict(payload)


def _get_text(
    url: str,
    *,
    auth: SmokeAuth | None = None,
    admin: bool = False,
    timeout_seconds: float,
) -> HttpResponse:
    return _request(
        url,
        method="GET",
        headers=_auth_headers(auth, admin=admin),
        timeout_seconds=timeout_seconds,
    )


def _post_form(
    url: str,
    data: dict[str, str],
    *,
    auth: SmokeAuth | None = None,
    admin: bool = False,
    timeout_seconds: float,
) -> HttpResponse:
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    headers.update(_auth_headers(auth, admin=admin))
    return _request(
        url,
        method="POST",
        body=encoded,
        headers=headers,
        timeout_seconds=timeout_seconds,
    )


def _auth_headers(auth: SmokeAuth | None, *, admin: bool = False) -> dict[str, str]:
    if auth is None:
        return {}
    return auth.headers(admin=admin)


def _request(
    url: str,
    *,
    method: str,
    timeout_seconds: float,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> HttpResponse:
    expected_origin = _url_origin(url)
    request_headers = {"User-Agent": "medical-audit-production-e2e/1.0"}
    request_headers.update(headers or {})
    request = urllib.request.Request(
        url,
        data=body,
        headers=request_headers,
        method=method,
    )
    opener = urllib.request.build_opener(
        # Match the certificate probe's direct path instead of inheriting macOS system proxies.
        urllib.request.ProxyHandler({}),
        _SameOriginRedirectHandler(expected_origin),
    )
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            raw = response.read()
            response_url = response.geturl()
            if _url_origin(response_url) != expected_origin:
                raise SmokeError("cross-origin final response rejected")
            return HttpResponse(
                status=response.status,
                url=response_url,
                text=raw.decode("utf-8", errors="replace"),
                headers={key.lower(): value for key, value in response.headers.items()},
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        response_url = exc.geturl()
        if _url_origin(response_url) != expected_origin:
            raise SmokeError("cross-origin final response rejected") from exc
        return HttpResponse(
            status=exc.code,
            url=response_url,
            text=raw.decode("utf-8", errors="replace"),
            headers={key.lower(): value for key, value in exc.headers.items()},
        )


def _report(
    *,
    status: str,
    base_url: str,
    question: str,
    started_at: str,
    steps: list[dict[str, object]],
    auth: SmokeAuth | None,
    args: argparse.Namespace,
) -> dict[str, object]:
    live_side_effects = bool(args.include_query_provider_smoke or args.include_review_write)
    return {
        "status": status,
        "evidence_grade": (
            "L4-authorized-live" if live_side_effects else "L3-production-read-only"
        ),
        "production_side_effect": (
            "query/audit/review-write-authorized" if live_side_effects else "none"
        ),
        "database_write": live_side_effects,
        "provider_call": (
            "authorized_possible" if args.include_query_provider_smoke else "not_called"
        ),
        "http_methods": ["GET", "POST"] if live_side_effects else ["GET"],
        "transport": {
            "proxy_mode": "direct",
            "automatic_retry": False,
        },
        "access_mode": str(args.access_mode),
        "base_url": base_url,
        "question": question,
        "auth": auth.to_report_dict() if auth else {},
        "started_at": started_at,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "steps": steps,
    }


def _write_report(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _ensure_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise SmokeError(f"expected dict, got {type(value).__name__}")
    return value


def _ensure_list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise SmokeError(f"expected list, got {type(value).__name__}")
    return value


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    return 0


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeError(message)


if __name__ == "__main__":
    raise SystemExit(main())
