#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASE_URL = "https://audit.lute-tlz-dddd.top"
DEFAULT_QUESTION = "医保基金审核发现异常收费时应优先核验证据链的哪些要点？"
DEFAULT_REGRESSION_URLS = (
    "https://kg.lute-tlz-dddd.top/",
    "https://video.lute-tlz-dddd.top/",
    "https://voc.lute-tlz-dddd.top/",
    "https://lute-tlz-dddd.top/",
)
REQUIRED_PAGES = {
    "/pages/chat": ("医保审核对话审证台", "对话审证", "检索后端"),
    "/pages/query": ("医保审核知识库查询", "查询工作台"),
    "/pages/review-tasks": ("复核任务台", "人工复核台"),
    "/pages/index-admin": ("索引管理", "检索后端"),
}


class SmokeError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    url: str
    text: str
    headers: dict[str, str]


def main() -> int:
    args = _parse_args()
    base_url = str(args.base_url).rstrip("/")
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    steps: list[dict[str, object]] = []
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    try:
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
        _run_step(
            steps,
            "search-backend",
            lambda: _check_search_backend(
                base_url,
                expected_matching_embeddings=int(args.expected_matching_embeddings),
                timeout_seconds=float(args.timeout_seconds),
            ),
        )
        _run_step(
            steps,
            "page-rendering",
            lambda: _check_pages(base_url, timeout_seconds=float(args.timeout_seconds)),
        )
        query_details = _run_step(
            steps,
            "query-api-with-citations",
            lambda: _check_query_api(
                base_url,
                question=str(args.question),
                timeout_seconds=float(args.timeout_seconds),
            ),
        )
        first_chunk_id = str(query_details["first_chunk_id"])
        _run_step(
            steps,
            "citation-preview",
            lambda: _check_preview(
                base_url,
                chunk_id=first_chunk_id,
                timeout_seconds=float(args.timeout_seconds),
            ),
        )
        _run_step(
            steps,
            "chat-dossier-export",
            lambda: _check_chat_export(
                base_url,
                question=str(args.question),
                timeout_seconds=float(args.timeout_seconds),
            ),
        )
        if not args.skip_review_write:
            _run_step(
                steps,
                "review-flow-create-update-export",
                lambda: _check_review_task_flow(
                    base_url,
                    question=str(args.question),
                    timeout_seconds=float(args.timeout_seconds),
                ),
            )
        _run_step(
            steps,
            "edge-regression",
            lambda: _check_regression_urls(
                tuple(str(url) for url in args.regression_url),
                timeout_seconds=float(args.timeout_seconds),
            ),
        )
    except SmokeError:
        report = _report(
            status="fail",
            base_url=base_url,
            question=str(args.question),
            started_at=started_at,
            steps=steps,
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
        "--report",
        default="tmp/outputs/production-e2e-smoke-latest.json",
    )
    parser.add_argument(
        "--regression-url",
        action="append",
        default=list(DEFAULT_REGRESSION_URLS),
        help="Existing public URL to regression-check. Can be supplied multiple times.",
    )
    parser.add_argument(
        "--skip-review-write",
        action="store_true",
        help="Skip the in-memory review flow create/update/export check.",
    )
    return parser.parse_args()


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
    expected_matching_embeddings: int,
    timeout_seconds: float,
) -> dict[str, object]:
    payload = _get_json(f"{base_url}/index/search-backend", timeout_seconds=timeout_seconds)
    details = _ensure_dict(payload.get("details"))
    matching = _int_value(details.get("matching_embedding_count"))
    _require(payload.get("backend") == "postgres", "search backend is not postgres")
    _require(payload.get("ready") is True, "search backend is not ready")
    _require(
        matching >= expected_matching_embeddings,
        f"matching embeddings {matching} < expected {expected_matching_embeddings}",
    )
    return {
        "backend": payload.get("backend"),
        "ready": payload.get("ready"),
        "matching_embedding_count": matching,
        "embedding_model": details.get("embedding_model"),
    }


def _check_pages(base_url: str, *, timeout_seconds: float) -> dict[str, object]:
    pages: dict[str, object] = {}
    for path, required_texts in REQUIRED_PAGES.items():
        response = _get_text(f"{base_url}{path}", timeout_seconds=timeout_seconds)
        _require(response.status == 200, f"{path} returned {response.status}")
        missing = [text for text in required_texts if text not in response.text]
        _require(not missing, f"{path} missing texts: {missing}")
        pages[path] = {"status": response.status, "bytes": len(response.text.encode())}
    return {"pages": pages}


def _check_query_api(
    base_url: str,
    *,
    question: str,
    timeout_seconds: float,
) -> dict[str, object]:
    payload = {
        "question": question,
        "top_k": 5,
    }
    response = _request_json(
        f"{base_url}/query",
        method="POST",
        body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Role": "auditor"},
        timeout_seconds=timeout_seconds,
    )
    citations = _ensure_list(response.get("citations"))
    basis_groups = _ensure_list(response.get("basis_groups"))
    _require(response.get("confidence") in {"medium", "high"}, "query confidence is too low")
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
    chunk_id: str,
    timeout_seconds: float,
) -> dict[str, object]:
    response = _get_text(f"{base_url}/pages/preview/{chunk_id}", timeout_seconds=timeout_seconds)
    _require(response.status == 200, f"preview returned {response.status}")
    _require(
        "原文证据预览" in response.text or "source" in response.text.lower(),
        "preview body invalid",
    )
    return {"status": response.status, "chunk_id": chunk_id, "bytes": len(response.text.encode())}


def _check_chat_export(
    base_url: str,
    *,
    question: str,
    timeout_seconds: float,
) -> dict[str, object]:
    query = urllib.parse.urlencode({"question": question, "format": "markdown"})
    response = _get_text(f"{base_url}/pages/chat/export?{query}", timeout_seconds=timeout_seconds)
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
    question: str,
    timeout_seconds: float,
) -> dict[str, object]:
    create_response = _post_form(
        f"{base_url}/pages/review-tasks/create",
        {"question": question},
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
        timeout_seconds=timeout_seconds,
    )
    _require(update_response.status == 200, f"review task update returned {update_response.status}")
    export_response = _get_json(
        f"{base_url}/review-tasks/{task_id}/export?format=json",
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
    match = re.search(r"/review-tasks/([^/]+)/export\?format=json", html)
    if match is None:
        raise SmokeError("no review task export link found")
    return match.group(1)


def _get_json(url: str, *, timeout_seconds: float) -> dict[str, object]:
    return _request_json(url, method="GET", timeout_seconds=timeout_seconds)


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


def _get_text(url: str, *, timeout_seconds: float) -> HttpResponse:
    return _request(url, method="GET", timeout_seconds=timeout_seconds)


def _post_form(
    url: str,
    data: dict[str, str],
    *,
    timeout_seconds: float,
) -> HttpResponse:
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    return _request(
        url,
        method="POST",
        body=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout_seconds=timeout_seconds,
    )


def _request(
    url: str,
    *,
    method: str,
    timeout_seconds: float,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> HttpResponse:
    request_headers = {"User-Agent": "medical-audit-production-e2e/1.0"}
    request_headers.update(headers or {})
    request = urllib.request.Request(
        url,
        data=body,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
            return HttpResponse(
                status=response.status,
                url=response.geturl(),
                text=raw.decode("utf-8", errors="replace"),
                headers={key.lower(): value for key, value in response.headers.items()},
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return HttpResponse(
            status=exc.code,
            url=exc.geturl(),
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
) -> dict[str, object]:
    return {
        "status": status,
        "base_url": base_url,
        "question": question,
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
