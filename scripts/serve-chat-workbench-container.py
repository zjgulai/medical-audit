#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any


def main() -> int:
    host = os.getenv("MEDICAL_AUDIT_KB_HOST", "0.0.0.0")
    port = int(os.getenv("MEDICAL_AUDIT_KB_PORT", "8000"))
    api_url = os.getenv("MEDICAL_AUDIT_KB_API_URL", f"http://127.0.0.1:{port}").rstrip("/")
    log_level = os.getenv("MEDICAL_AUDIT_KB_LOG_LEVEL", "warning")
    app_module = os.getenv("MEDICAL_AUDIT_KB_APP_MODULE", "medical_audit_kb.api.app:create_app")
    load_backend = os.getenv("MEDICAL_AUDIT_KB_LOAD_BACKEND", "1") == "1"

    process = subprocess.Popen(
        [
            "uvicorn",
            app_module,
            "--factory",
            "--host",
            host,
            "--port",
            str(port),
            "--log-level",
            log_level,
        ]
    )

    def terminate(signum: int, _frame: object) -> None:
        process.terminate()
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)

    try:
        _wait_for_health(api_url, process)
        if load_backend:
            _load_postgres_backend(api_url)
        print(f"Chat workbench ready: {api_url}/pages/chat", flush=True)
        return process.wait()
    finally:
        if process.poll() is None:
            process.terminate()


def _wait_for_health(api_url: str, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise SystemExit("uvicorn exited before /health became available")
        try:
            _load_json(f"{api_url}/health")
            return
        except (OSError, urllib.error.URLError):
            time.sleep(0.5)
    raise SystemExit("API did not become healthy within 60 seconds")


def _load_postgres_backend(api_url: str) -> None:
    provider = os.getenv("KIMI_EMBEDDING_PROVIDER", "openai")
    api_key_env = os.getenv("KIMI_API_KEY_ENV", "KIMI_API_KEY")
    if provider != "fake" and not os.getenv(api_key_env):
        raise SystemExit(f"missing {api_key_env}; set it before starting the container")

    payload = {
        "embedding_provider": provider,
        "embedding_model": os.getenv("KIMI_EMBEDDING_MODEL", "kimi-for-coding"),
        "embedding_dimension": int(os.getenv("KIMI_EMBEDDING_DIMENSION", "1024")),
        "api_key_env": api_key_env,
        "embedding_base_url": os.getenv(
            "KIMI_EMBEDDING_BASE_URL",
            "https://api.kimi.com/coding/v1",
        ),
        "embedding_batch_size": int(os.getenv("KIMI_EMBEDDING_BATCH_SIZE", "16")),
    }
    response = _post_json(
        f"{api_url}/index/search-backend/postgres",
        payload,
        headers={"X-Role": "it-admin"},
    )
    if response.get("ready") is not True:
        raise SystemExit("search backend response is not ready")
    matching_count = _nested(response, "details", "matching_embedding_count")
    if not isinstance(matching_count, int) or matching_count <= 0:
        raise SystemExit("matching_embedding_count must be greater than 0")
    print(f"PostgreSQL search backend ready: matching_embedding_count={matching_count}", flush=True)


def _load_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=10) as response:
        body = response.read().decode("utf-8")
    value = json.loads(body)
    if not isinstance(value, dict):
        raise RuntimeError(f"unexpected JSON response from {url}: {value!r}")
    return value


def _post_json(
    url: str,
    payload: Mapping[str, object],
    *,
    headers: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **dict(headers or {}),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"backend load failed with HTTP {exc.code}: {detail}") from exc
    value = json.loads(body)
    if not isinstance(value, dict):
        raise RuntimeError(f"unexpected JSON response from {url}: {value!r}")
    return value


def _nested(value: Mapping[str, object], first: str, second: str) -> object:
    child = value.get(first)
    if not isinstance(child, Mapping):
        return None
    return child.get(second)


if __name__ == "__main__":
    sys.exit(main())
