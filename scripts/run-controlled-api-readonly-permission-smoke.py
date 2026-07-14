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
PRODUCTION_HOST = "audit.lute-tlz-dddd.top"
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
# Protected requests cross controlled-auth middleware. Even a code-audited GET
# handler can persist authorization-denied when the supplied profile is disabled
# or otherwise rejected, so no protected probe is universally read-only.
READONLY_PROTECTED_PATHS: frozenset[str] = frozenset()

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
    allow_audit_log_writes: bool = False
    confirm_production_write: str | None = None


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


class PermissionSmokeConfigError(ValueError):
    pass


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> urllib.request.Request | None:
        del req, fp, code, msg, headers, newurl
        return None


_NO_REDIRECT_OPENER = urllib.request.build_opener(_NoRedirectHandler())


def main() -> int:
    args = _parse_args()
    try:
        config = _config_from_args(args)
    except PermissionSmokeConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
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
    _validate_write_authorization(config)
    probes = _build_probes(config)
    skipped_probes = _build_skipped_probes(config)
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
                "body_length": len(response.text),
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
    audit_log_write_expected = config.allow_audit_log_writes
    return {
        "status": status_value,
        "mode": config.mode,
        "side_effect_mode": (
            "audit-log-write-enabled" if audit_log_write_expected else "readonly"
        ),
        "base_url": config.base_url,
        "api_prefix": config.api_prefix,
        "started_at": started_at,
        "finished_at": finished_at,
        "production_side_effect": (
            "audit-log-only" if audit_log_write_expected else "none"
        ),
        "database_write": (
            "audit-log-only" if audit_log_write_expected else False
        ),
        "audit_log_write_expected": audit_log_write_expected,
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
            "executed_probe_count": len(probes),
            "skipped_probe_count": len(skipped_probes),
            "total_probe_count": len(probes) + len(skipped_probes),
            "issue_count": len(issues),
            "observation_count": len(observations),
        },
        "issues": issues,
        "observations": observations,
        "executed_probes": [str(result["name"]) for result in results],
        "skipped_probes": skipped_probes,
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
        if config.allow_audit_log_writes:
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
                )
            )
        if config.allow_audit_log_writes or _is_readonly_protected_path(path):
            probes.append(
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
                )
            )
    return probes


def _build_skipped_probes(config: SmokeConfig) -> list[JsonObject]:
    if config.allow_audit_log_writes:
        return []

    skipped: list[JsonObject] = []
    for path in config.protected_paths:
        skipped.extend(
            (
                {
                    "name": f"protected-anonymous:{path}",
                    "kind": "protected-anonymous",
                    "method": "GET",
                    "path": path,
                    "expected_statuses": [401, 403],
                    "status": "skipped",
                    "reason": "audit-log-writes-not-authorized",
                },
                {
                    "name": f"protected-missing-tenant:{path}",
                    "kind": "protected-missing-tenant",
                    "method": "GET",
                    "path": path,
                    "expected_statuses": [401],
                    "status": "skipped",
                    "reason": "audit-log-writes-not-authorized",
                },
            )
        )
        if not _is_readonly_protected_path(path):
            skipped.append(
                {
                    "name": f"protected-admin:{path}",
                    "kind": "protected-admin",
                    "method": "GET",
                    "path": path,
                    "expected_statuses": [200],
                    "status": "skipped",
                    "reason": "endpoint-may-write-audit-log",
                }
            )
    return skipped


def _validate_write_authorization(config: SmokeConfig) -> None:
    confirmation = config.confirm_production_write
    if confirmation is not None and not config.allow_audit_log_writes:
        raise PermissionSmokeConfigError(
            "--confirm-production-write requires --allow-audit-log-writes"
        )
    if not config.allow_audit_log_writes:
        return
    if confirmation != PRODUCTION_HOST:
        raise PermissionSmokeConfigError(
            "audit-log writes require "
            f"--confirm-production-write {PRODUCTION_HOST}"
        )


def _is_readonly_protected_path(path: str) -> bool:
    normalized_path = path if path.startswith("/") else f"/{path}"
    return urllib.parse.urlsplit(normalized_path).path in READONLY_PROTECTED_PATHS


def _request_probe(probe: Probe, timeout_seconds: float) -> HttpResponse:
    request = urllib.request.Request(
        probe.url,
        headers=probe.headers,
        method=probe.method,
    )
    try:
        with _NO_REDIRECT_OPENER.open(request, timeout=timeout_seconds) as response:
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
    confirmation_value = getattr(args, "confirm_production_write", None)
    config = SmokeConfig(
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
        allow_audit_log_writes=bool(getattr(args, "allow_audit_log_writes", False)),
        confirm_production_write=(
            str(confirmation_value) if confirmation_value is not None else None
        ),
    )
    _validate_write_authorization(config)
    return config


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a controlled API permission smoke. By default, only code-audited GET "
            "probes without known audit-log writes execute; other probes are reported as "
            "skipped. Use --allow-audit-log-writes for the complete permission matrix."
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
    parser.add_argument(
        "--allow-audit-log-writes",
        action="store_true",
        help=(
            "Run negative and write-capable positive probes that may persist audit-log "
            "events."
        ),
    )
    parser.add_argument(
        "--confirm-production-write",
        default=None,
        metavar="HOST",
        help=(
            "Required with --allow-audit-log-writes for every target so aliases and "
            f"redirects cannot bypass production confirmation; must equal {PRODUCTION_HOST}."
        ),
    )
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
