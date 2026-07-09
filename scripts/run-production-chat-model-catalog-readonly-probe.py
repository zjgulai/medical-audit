#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "https://audit.lute-tlz-dddd.top"
DEFAULT_REPORT = "tmp/outputs/production-chat-model-catalog-readonly-latest.json"
DEFAULT_USER_ID = "production-chat-model-catalog-probe"
DEFAULT_TENANT_ID = "hospital-demo"
DEFAULT_PROJECT_KEY = "SELF-CHECK-FUND-20260607"
DEPLOYMENT_METADATA_ENDPOINT = "/api/v1/deployment/metadata"
QUERY_MODELS_ENDPOINT = "/api/v1/query/models"
EXPECTED_MODEL_ALIASES = ("kimi-2.7", "deepseek-v4-pro")
SECRET_FIELD_FRAGMENTS = ("api_key", "apikey", "secret", "token", "password", "private_key")
ALLOWED_BOUNDARY_SECRET_FIELDS = frozenset({"secret_values_reported"})


class ReadOnlyProbeError(RuntimeError):
    pass


@dataclass(frozen=True)
class HttpResponse:
    status: int
    url: str
    content: bytes
    headers: dict[str, str]


def main() -> int:
    args = _parse_args()
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = _run_probe(
        base_url=str(args.base_url),
        timeout_seconds=float(args.timeout_seconds),
        user_id=str(args.user_id),
        role=str(args.role),
        tenant_id=str(args.tenant_id),
        project_key=str(args.project_key),
        api_key_env=_optional_env_name(args.api_key_env),
        expected_deploy_sha=_optional_env_name(args.expected_deploy_sha),
        require_ready_model=bool(args.require_ready_model),
    )
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a production /api/v1/query/models read-only probe. The probe uses GET "
            "only and verifies the public model catalog contract without provider calls."
        )
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--role", default="auditor")
    parser.add_argument("--tenant-id", default=DEFAULT_TENANT_ID)
    parser.add_argument("--project-key", default=DEFAULT_PROJECT_KEY)
    parser.add_argument(
        "--api-key-env",
        default=None,
        help=(
            "Optional environment variable containing the production API secret. "
            "The secret value is never written to the report."
        ),
    )
    parser.add_argument(
        "--expected-deploy-sha",
        default="",
        help=(
            "Optional expected production deploy SHA. When set, the GET-only deployment "
            "metadata check must match this SHA."
        ),
    )
    parser.add_argument(
        "--require-ready-model",
        action="store_true",
        help="Fail unless at least one chat model alias is available.",
    )
    parser.add_argument("--report", default=DEFAULT_REPORT)
    return parser.parse_args()


def _run_probe(
    *,
    base_url: str,
    timeout_seconds: float,
    user_id: str,
    role: str,
    tenant_id: str,
    project_key: str,
    api_key_env: str | None = None,
    expected_deploy_sha: str | None = None,
    require_ready_model: bool = False,
    http_get: Callable[[str, dict[str, str], float], HttpResponse] | None = None,
) -> dict[str, Any]:
    selected_http_get = http_get or _http_get
    normalized_base_url = base_url.rstrip("/")
    api_key = _secret_from_env(api_key_env)
    auth_headers = _auth_headers(
        user_id=user_id,
        role=role,
        tenant_id=tenant_id,
        project_key=project_key,
        api_key=api_key,
    )
    started_at = _now_iso()
    steps: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "auth_context": {
            "user_id": user_id,
            "role": role,
            "tenant_id": tenant_id,
            "project_key": project_key,
            "api_key_env": api_key_env,
            "api_key_configured": api_key is not None,
            "expected_deploy_sha": expected_deploy_sha,
        },
        "require_ready_model": require_ready_model,
    }

    deployment_details = _run_step(
        steps,
        "deployment-metadata",
        lambda: _check_deployment_metadata(
            normalized_base_url,
            timeout_seconds=timeout_seconds,
            auth_headers=auth_headers,
            expected_deploy_sha=expected_deploy_sha,
            http_get=selected_http_get,
        ),
    )
    if "error" not in deployment_details:
        summary["deploy_sha"] = deployment_details["deploy_sha"]
        summary["deploy_sha_status"] = deployment_details["deploy_sha_status"]
        summary["deploy_sha_matches_expected"] = deployment_details[
            "deploy_sha_matches_expected"
        ]

    catalog_details = _run_step(
        steps,
        "query-models-catalog",
        lambda: _check_query_models_catalog(
            normalized_base_url,
            timeout_seconds=timeout_seconds,
            auth_headers=auth_headers,
            require_ready_model=require_ready_model,
            http_get=selected_http_get,
        ),
    )
    if "error" not in catalog_details:
        summary["contract_version"] = catalog_details["contract_version"]
        summary["default_model"] = catalog_details["default_model"]
        summary["model_aliases"] = catalog_details["model_aliases"]
        summary["available_model_aliases"] = catalog_details["available_model_aliases"]
        summary["unavailable_models"] = catalog_details["unavailable_models"]
        summary["ready_model_count"] = len(catalog_details["available_model_aliases"])

    return {
        "status": "pass" if all(step["passed"] for step in steps) else "fail",
        "base_url": normalized_base_url,
        "started_at": started_at,
        "finished_at": _now_iso(),
        "boundaries": {
            "production_write": False,
            "production_env_write": False,
            "provider_call": False,
            "browser_js_executed": False,
            "query_models_api_called": True,
            "deployment_metadata_api_called": True,
            "secret_values_reported": False,
            "allowed_http_methods": ["GET"],
            "non_get_http_methods_allowed": False,
            "api_key_env": api_key_env,
            "api_key_configured": api_key is not None,
            "evidence_grade": "L3-production-read-only",
        },
        "summary": summary,
        "steps": steps,
    }


def _run_step(
    steps: list[dict[str, Any]],
    name: str,
    callback: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    started = time.time()
    try:
        details = callback()
    except Exception as exc:
        details = {"error": str(exc)}
        steps.append(
            {
                "name": name,
                "passed": False,
                "duration_ms": round((time.time() - started) * 1000),
                "details": details,
            }
        )
        return details
    steps.append(
        {
            "name": name,
            "passed": True,
            "duration_ms": round((time.time() - started) * 1000),
            "details": details,
        }
    )
    return details


def _check_deployment_metadata(
    base_url: str,
    *,
    timeout_seconds: float,
    auth_headers: dict[str, str],
    expected_deploy_sha: str | None,
    http_get: Callable[[str, dict[str, str], float], HttpResponse],
) -> dict[str, Any]:
    payload = _request_json(
        f"{base_url}{DEPLOYMENT_METADATA_ENDPOINT}",
        {"Accept": "application/json", **auth_headers},
        timeout_seconds,
        http_get=http_get,
    )
    boundaries = _dict(payload.get("boundaries"), "deployment metadata boundaries")
    deploy_sha = payload.get("deploy_sha")
    _require(
        payload.get("status") == "deployment_metadata_available",
        "deployment metadata unavailable",
    )
    _require(payload.get("deploy_sha_status") == "set", "deploy_sha_status should be set")
    _require(isinstance(deploy_sha, str) and bool(deploy_sha), "deploy_sha should be present")
    _require(boundaries.get("production_write") is False, "deployment metadata writes production")
    _require(
        boundaries.get("production_env_write") is False,
        "deployment metadata writes production env",
    )
    _require(boundaries.get("provider_call") is False, "deployment metadata calls provider")
    _require(
        boundaries.get("secret_values_reported") is False,
        "deployment metadata reports secrets",
    )
    _require(
        boundaries.get("non_get_http_methods_allowed") is False,
        "deployment metadata allows non-GET methods",
    )
    normalized_expected = expected_deploy_sha.strip().lower() if expected_deploy_sha else None
    deploy_sha_matches_expected = (
        None if normalized_expected is None else deploy_sha == normalized_expected
    )
    if normalized_expected is not None:
        _require(
            deploy_sha_matches_expected is True,
            f"deploy_sha mismatch: {deploy_sha} != {normalized_expected}",
        )
    return {
        "status": payload.get("status"),
        "evidence_grade": payload.get("evidence_grade"),
        "deploy_sha": deploy_sha,
        "deploy_sha_status": payload.get("deploy_sha_status"),
        "deploy_sha_source": payload.get("deploy_sha_source"),
        "deploy_sha_matches_expected": deploy_sha_matches_expected,
    }


def _check_query_models_catalog(
    base_url: str,
    *,
    timeout_seconds: float,
    auth_headers: dict[str, str],
    require_ready_model: bool,
    http_get: Callable[[str, dict[str, str], float], HttpResponse],
) -> dict[str, Any]:
    payload = _request_json(
        f"{base_url}{QUERY_MODELS_ENDPOINT}",
        {"Accept": "application/json", **auth_headers},
        timeout_seconds,
        http_get=http_get,
    )
    _assert_no_secret_fields(payload)
    boundaries = _dict(payload.get("boundaries"), "query models boundaries")
    items = _list(payload.get("items"), "query models items")
    model_aliases = [
        _str(_dict(item, "query model item").get("alias"), "query model alias")
        for item in items
    ]
    available_model_aliases: list[str] = []
    unavailable_models: dict[str, str | None] = {}
    for item_value in items:
        item = _dict(item_value, "query model item")
        alias = _str(item.get("alias"), "query model alias")
        available = _bool(item.get("available"), f"{alias}.available")
        if available:
            available_model_aliases.append(alias)
        else:
            reason = item.get("unavailable_reason")
            unavailable_models[alias] = reason if isinstance(reason, str) else None

    missing_aliases = [alias for alias in EXPECTED_MODEL_ALIASES if alias not in model_aliases]
    _require(payload.get("contract_version") == "chat-model-catalog-v1", "contract mismatch")
    _require(payload.get("default_model") in model_aliases, "default_model missing from items")
    _require(not missing_aliases, f"missing model aliases: {missing_aliases}")
    _require(boundaries.get("production_write") is False, "query models writes production")
    _require(boundaries.get("provider_call") is False, "query models calls provider")
    _require(
        boundaries.get("secret_values_reported") is False,
        "query models reports secrets",
    )
    _require(
        boundaries.get("source") == "environment_capability_probe_only",
        "query models source boundary drifted",
    )
    if require_ready_model:
        _require(bool(available_model_aliases), "no chat model alias is available")

    return {
        "contract_version": payload.get("contract_version"),
        "default_model": payload.get("default_model"),
        "model_aliases": model_aliases,
        "available_model_aliases": available_model_aliases,
        "unavailable_models": unavailable_models,
        "boundaries": boundaries,
    }


def _request_json(
    url: str,
    headers: dict[str, str],
    timeout_seconds: float,
    *,
    http_get: Callable[[str, dict[str, str], float], HttpResponse],
) -> dict[str, Any]:
    response = http_get(url, headers, timeout_seconds)
    _require(response.status == 200, f"{url} returned {response.status}")
    try:
        payload = json.loads(response.content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReadOnlyProbeError(f"{url} did not return valid JSON: {exc}") from exc
    return _dict(payload, "JSON response")


def _auth_headers(
    *,
    user_id: str,
    role: str,
    tenant_id: str,
    project_key: str,
    api_key: str | None,
) -> dict[str, str]:
    headers = {
        "X-User-Id": user_id,
        "X-Role": role,
        "X-Project-Key": project_key,
        "X-Tenant-Id": tenant_id,
    }
    if api_key is not None:
        headers["X-API-Key"] = api_key
    return headers


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
        raise ReadOnlyProbeError(f"environment variable {env_name} is empty or unset")
    return value


def _http_get(url: str, headers: dict[str, str], timeout_seconds: float) -> HttpResponse:
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return HttpResponse(
                status=response.status,
                url=response.geturl(),
                content=response.read(),
                headers={key.lower(): value for key, value in response.headers.items()},
            )
    except urllib.error.HTTPError as exc:
        return HttpResponse(
            status=exc.code,
            url=url,
            content=exc.read(),
            headers={key.lower(): value for key, value in exc.headers.items()},
        )
    except urllib.error.URLError as exc:
        raise ReadOnlyProbeError(f"GET {url} failed: {exc}") from exc


def _dict(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReadOnlyProbeError(f"{label} must be an object")
    return value


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ReadOnlyProbeError(f"{label} must be a list")
    return value


def _str(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReadOnlyProbeError(f"{label} must be a non-empty string")
    return value


def _bool(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ReadOnlyProbeError(f"{label} must be a boolean")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReadOnlyProbeError(message)


def _assert_no_secret_fields(value: object, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lower_key = str(key).lower()
            if lower_key not in ALLOWED_BOUNDARY_SECRET_FIELDS and any(
                fragment in lower_key for fragment in SECRET_FIELD_FRAGMENTS
            ):
                raise ReadOnlyProbeError(f"secret-shaped field exposed at {path}.{key}")
            _assert_no_secret_fields(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_secret_fields(child, f"{path}[{index}]")


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


if __name__ == "__main__":
    raise SystemExit(main())
