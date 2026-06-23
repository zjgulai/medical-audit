#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

DEFAULT_BASE_URL = "http://127.0.0.1:8021"
DEFAULT_TENANT_ID = "hospital-demo"
DEFAULT_PROJECT_KEY = "SELF-CHECK-FUND-20260607"
DEFAULT_ADMIN_ROLE = "admin"
DEFAULT_ADMIN_USER_ID = "permission-smoke-admin"
DEFAULT_PROTECTED_PATHS = (
    "/auth/session",
    "/projects",
    "/agents",
    "/query/logs?limit=1",
    "/audit-findings",
    "/analytics/table-uploads",
    "/graph/workbench",
    "/rules/workbench",
    "/remediation/workbench",
    "/archive/workbench",
    "/reports/workbench",
)
PUBLIC_PATHS = ("/health", "/auth/roles")

JsonObject = dict[str, object]
Requester = Callable[["Probe", float], "HttpResponse"]


@dataclass(frozen=True, slots=True)
class SmokeConfig:
    base_url: str
    api_prefix: str
    mode: str
    protected_paths: tuple[str, ...]
    tenant_id: str
    project_key: str
    admin_role: str
    admin_user_id: str
    api_key: str | None
    api_key_env: str | None
    timeout_seconds: float
    json_output: Path | None


@dataclass(frozen=True, slots=True)
class Probe:
    name: str
    path: str
    url: str
    method: str
    headers: dict[str, str]
    expected_statuses: tuple[int, ...]
    kind: str


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    url: str
    text: str


class ProbeTransportError(RuntimeError):
    pass


def main() -> int:
    args = _parse_args()
    config = _config_from_args(args)
    report = run_readonly_permission_smoke(config)
    _write_report(report, config.json_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"pass", "observed"} else 2


def run_readonly_permission_smoke(
    config: SmokeConfig,
    *,
    requester: Requester = lambda probe, timeout_seconds: _request_probe(
        probe,
        timeout_seconds,
    ),
) -> JsonObject:
    probes = _build_probes(config)
    results: list[JsonObject] = []
    issues: list[str] = []
    observations: list[str] = []
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    for probe in probes:
        try:
            response = requester(probe, config.timeout_seconds)
            status = response.status
            matched = status in probe.expected_statuses
            result: JsonObject = {
                "name": probe.name,
                "kind": probe.kind,
                "method": probe.method,
                "path": probe.path,
                "status": status,
                "expected_statuses": list(probe.expected_statuses),
                "matched": matched,
                "body_preview": _body_preview(response.text),
            }
        except ProbeTransportError as exc:
            status = None
            matched = False
            result = {
                "name": probe.name,
                "kind": probe.kind,
                "method": probe.method,
                "path": probe.path,
                "status": None,
                "expected_statuses": list(probe.expected_statuses),
                "matched": False,
                "error": _redact(str(exc)),
            }
        results.append(result)

        if matched:
            continue
        message = (
            f"{probe.name}: expected {probe.expected_statuses}, "
            f"got {status if status is not None else 'transport-error'}"
        )
        if config.mode == "enforce" or probe.kind == "public":
            issues.append(message)
        else:
            observations.append(message)

    finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if issues:
        status_value = "fail"
    elif config.mode == "observe":
        status_value = "observed"
    else:
        status_value = "pass"
    return {
        "status": status_value,
        "mode": config.mode,
        "base_url": config.base_url,
        "api_prefix": config.api_prefix,
        "started_at": started_at,
        "finished_at": finished_at,
        "production_side_effect": "none",
        "provider_call_status": "not_called",
        "http_methods": ["GET"],
        "auth": {
            "api_key_env": config.api_key_env,
            "api_key_configured": config.api_key is not None,
            "tenant_id": config.tenant_id,
            "project_key": config.project_key,
            "admin_role": config.admin_role,
            "admin_user_id": config.admin_user_id,
        },
        "summary": {
            "probe_count": len(probes),
            "issue_count": len(issues),
            "observation_count": len(observations),
        },
        "issues": issues,
        "observations": observations,
        "probes": results,
    }


def _build_probes(config: SmokeConfig) -> list[Probe]:
    api_key_headers = _api_key_headers(config)
    probes: list[Probe] = []
    for path in PUBLIC_PATHS:
        probes.append(
            Probe(
                name=f"public:{path}",
                path=path,
                url=_build_url(config, path),
                method="GET",
                headers=dict(api_key_headers),
                expected_statuses=(200,),
                kind="public",
            )
        )

    for path in config.protected_paths:
        probes.extend(
            (
                Probe(
                    name=f"protected-anonymous:{path}",
                    path=path,
                    url=_build_url(config, path),
                    method="GET",
                    headers=dict(api_key_headers),
                    expected_statuses=(401, 403),
                    kind="protected-anonymous",
                ),
                Probe(
                    name=f"protected-missing-tenant:{path}",
                    path=path,
                    url=_build_url(config, path),
                    method="GET",
                    headers={
                        **api_key_headers,
                        "X-User-Id": config.admin_user_id,
                        "X-Role": config.admin_role,
                        "X-Project-Key": config.project_key,
                    },
                    expected_statuses=(401,),
                    kind="protected-missing-tenant",
                ),
                Probe(
                    name=f"protected-admin:{path}",
                    path=path,
                    url=_build_url(config, path),
                    method="GET",
                    headers={
                        **api_key_headers,
                        "X-User-Id": config.admin_user_id,
                        "X-Role": config.admin_role,
                        "X-Project-Key": config.project_key,
                        "X-Tenant-Id": config.tenant_id,
                    },
                    expected_statuses=(200,),
                    kind="protected-admin",
                ),
            )
        )
    return probes


def _request_probe(probe: Probe, timeout_seconds: float) -> HttpResponse:
    request = urllib.request.Request(
        probe.url,
        headers=probe.headers,
        method=probe.method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return HttpResponse(
                status=response.status,
                url=probe.url,
                text=response.read().decode("utf-8", errors="replace"),
            )
    except urllib.error.HTTPError as exc:
        return HttpResponse(
            status=exc.code,
            url=probe.url,
            text=exc.read().decode("utf-8", errors="replace"),
        )
    except (OSError, urllib.error.URLError) as exc:
        raise ProbeTransportError(str(exc)) from exc


def _config_from_args(args: argparse.Namespace) -> SmokeConfig:
    api_key = _optional_env_value(str(args.api_key_env) if args.api_key_env else None)
    return SmokeConfig(
        base_url=str(args.base_url).rstrip("/"),
        api_prefix=_normalize_prefix(str(args.api_prefix)),
        mode=str(args.mode),
        protected_paths=tuple(str(path) for path in args.protected_path),
        tenant_id=str(args.tenant_id),
        project_key=str(args.project_key),
        admin_role=str(args.admin_role),
        admin_user_id=str(args.admin_user_id),
        api_key=api_key,
        api_key_env=str(args.api_key_env) if args.api_key_env else None,
        timeout_seconds=float(args.timeout_seconds),
        json_output=Path(args.json_output) if args.json_output else None,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a read-only controlled API permission smoke. The script only issues GET "
            "requests and records whether controlled endpoints enforce role and tenant "
            "headers. Use --mode enforce for local gates and --mode observe for production "
            "read-only reconnaissance."
        )
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--api-prefix",
        default="",
        help="API prefix to prepend to all probes, for example /api/v1 behind Next rewrites.",
    )
    parser.add_argument("--mode", choices=("enforce", "observe"), default="enforce")
    parser.add_argument(
        "--protected-path",
        action="append",
        default=list(DEFAULT_PROTECTED_PATHS),
        help="Protected API path to probe. May be repeated.",
    )
    parser.add_argument("--tenant-id", default=DEFAULT_TENANT_ID)
    parser.add_argument("--project-key", default=DEFAULT_PROJECT_KEY)
    parser.add_argument("--admin-role", default=DEFAULT_ADMIN_ROLE)
    parser.add_argument("--admin-user-id", default=DEFAULT_ADMIN_USER_ID)
    parser.add_argument(
        "--api-key-env",
        default=None,
        help="Optional environment variable containing an API key for edge gateways.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=10)
    parser.add_argument("--json-output", default=None)
    return parser.parse_args()


def _build_url(config: SmokeConfig, path: str) -> str:
    normalized_path = path if path.startswith("/") else f"/{path}"
    combined = f"{config.api_prefix}{normalized_path}"
    parsed = urllib.parse.urlsplit(combined)
    quoted_path = urllib.parse.quote(parsed.path, safe="/")
    suffix = urllib.parse.urlunsplit(("", "", quoted_path, parsed.query, ""))
    return f"{config.base_url}{suffix}"


def _normalize_prefix(value: str) -> str:
    normalized = value.strip().strip("/")
    return f"/{normalized}" if normalized else ""


def _api_key_headers(config: SmokeConfig) -> dict[str, str]:
    if config.api_key is None:
        return {}
    return {"X-API-Key": config.api_key}


def _optional_env_value(name: str | None) -> str | None:
    if not name:
        return None
    value = os.getenv(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _body_preview(value: str) -> str:
    return _redact(value.replace("\n", " ")[:500])


def _redact(value: str) -> str:
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
