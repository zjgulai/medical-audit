#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

JsonObject = dict[str, object]

DEFAULT_JSON_OUTPUT = "tmp/outputs/auth-sso-contract-readiness-latest.json"
DEFAULT_MARKDOWN_OUTPUT = "tmp/outputs/auth-sso-contract-readiness-latest.md"

ENV_NAMES = (
    "MEDICAL_AUDIT_AUTH_MODE",
    "MEDICAL_AUDIT_TRUSTED_PROXY_ENABLED",
    "MEDICAL_AUDIT_TRUSTED_PROXY_SIGNATURE_KEY_ENV",
    "MEDICAL_AUDIT_TRUSTED_PROXY_ALLOWED_SOURCE_CIDRS",
    "MEDICAL_AUDIT_SESSION_COOKIE_NAME",
    "MEDICAL_AUDIT_SESSION_COOKIE_SECURE",
    "MEDICAL_AUDIT_SESSION_COOKIE_SAMESITE",
    "MEDICAL_AUDIT_SESSION_STORE",
    "MEDICAL_AUDIT_DISABLE_LEGACY_HEADER_AUTH",
)

TRUSTED_PROXY_REQUIRED_CLAIMS: tuple[JsonObject, ...] = (
    {
        "claim": "user_id",
        "trusted_header": "X-Medical-Audit-User-Id",
        "legacy_header": "X-User-Id",
        "required": True,
    },
    {
        "claim": "role_keys",
        "trusted_header": "X-Medical-Audit-Role-Keys",
        "legacy_header": "X-Role",
        "required": True,
    },
    {
        "claim": "tenant_id",
        "trusted_header": "X-Medical-Audit-Tenant-Id",
        "legacy_header": "X-Tenant-Id",
        "required": True,
    },
    {
        "claim": "project_keys",
        "trusted_header": "X-Medical-Audit-Project-Keys",
        "legacy_header": "X-Project-Key",
        "required": True,
    },
    {
        "claim": "external_subject",
        "trusted_header": "X-Medical-Audit-External-Subject",
        "legacy_header": None,
        "required": True,
    },
    {
        "claim": "department_key",
        "trusted_header": "X-Medical-Audit-Department-Key",
        "legacy_header": None,
        "required": True,
    },
    {
        "claim": "claims_issued_at",
        "trusted_header": "X-Medical-Audit-Claims-Issued-At",
        "legacy_header": None,
        "required": True,
    },
    {
        "claim": "claims_signature",
        "trusted_header": "X-Medical-Audit-Claims-Signature",
        "legacy_header": None,
        "required": True,
    },
)


@dataclass(frozen=True, slots=True)
class ReadinessConfig:
    target_mode: str
    json_output: Path | None
    markdown_output: Path | None
    fail_when_blocked: bool


def main() -> int:
    args = _parse_args()
    config = ReadinessConfig(
        target_mode=str(args.target_mode),
        json_output=Path(args.json_output) if args.json_output else None,
        markdown_output=Path(args.markdown_output) if args.markdown_output else None,
        fail_when_blocked=bool(args.fail_when_blocked),
    )
    report = build_readiness_report(config, os.environ)
    _write_json(report, config.json_output)
    _write_markdown(report, config.markdown_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if config.fail_when_blocked and report["status"] == "blocked":
        return 2
    return 0


def build_readiness_report(
    config: ReadinessConfig,
    env: os._Environ[str] | dict[str, str],
) -> JsonObject:
    safe_env = _sanitize_env(env)
    if config.target_mode == "trusted-sso-proxy":
        mode_report = _trusted_proxy_readiness(safe_env)
    else:
        mode_report = _server_session_readiness(safe_env)
    blockers = list(mode_report["blockers"])
    status = "ready_for_readonly_gateway_probe" if not blockers else "blocked"
    return {
        "task": "auth-sso-contract-readiness",
        "status": status,
        "target_mode": config.target_mode,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "evidence_grade": "L2-fixture-or-dry-run",
        "safe_env": safe_env,
        "contract": {
            "trusted_proxy_required_claims": list(TRUSTED_PROXY_REQUIRED_CLAIMS),
            "server_session_requirements": [
                "HttpOnly Secure SameSite cookie",
                "server-side session store",
                "revocation on logout or disabled account",
                "CSRF or trusted same-origin protection for write APIs",
            ],
            "legacy_transition_headers": [
                "X-User-Id",
                "X-Role",
                "X-Project-Key",
                "X-Tenant-Id",
            ],
        },
        "mode_readiness": mode_report,
        "blockers": blockers,
        "boundaries": {
            "production_side_effect": "none",
            "production_env_write": False,
            "provider_call_status": "not_called",
            "secret_values_reported": False,
            "network_call_status": "not_called",
            "authorized_write_e2e": "not_run",
        },
        "supported_claims": [
            "The SSO/session contract is machine-readable and fail-closed.",
            "The report only inspects local environment names and SET/UNSET state.",
        ],
        "forbidden_claims": [
            "real hospital SSO is complete",
            "production session signing is enabled",
            "browser-supplied legacy headers are safe for production authorization",
        ],
    }


def _trusted_proxy_readiness(safe_env: JsonObject) -> JsonObject:
    blockers: list[str] = []
    mode = str(safe_env["MEDICAL_AUDIT_AUTH_MODE"]["value"] or "header-transition")
    if mode != "trusted-sso-proxy":
        blockers.append("auth-mode-not-trusted-sso-proxy")
    if not _truthy(safe_env["MEDICAL_AUDIT_TRUSTED_PROXY_ENABLED"]["value"]):
        blockers.append("trusted-proxy-not-enabled")
    signature_key_env = str(
        safe_env["MEDICAL_AUDIT_TRUSTED_PROXY_SIGNATURE_KEY_ENV"]["value"] or ""
    ).strip()
    if not signature_key_env:
        blockers.append("trusted-proxy-signature-key-env-missing")
    elif safe_env["referenced_secret_status"].get(signature_key_env) != "SET":
        blockers.append("trusted-proxy-signature-key-not-set")
    if not str(
        safe_env["MEDICAL_AUDIT_TRUSTED_PROXY_ALLOWED_SOURCE_CIDRS"]["value"] or ""
    ).strip():
        blockers.append("trusted-proxy-allowed-source-cidrs-missing")
    if not _truthy(safe_env["MEDICAL_AUDIT_DISABLE_LEGACY_HEADER_AUTH"]["value"]):
        blockers.append("legacy-header-auth-still-enabled")
    return {
        "mode": "trusted-sso-proxy",
        "status": "ready" if not blockers else "blocked",
        "blockers": blockers,
        "next_evidence": [
            "Configure a trusted gateway to inject signed X-Medical-Audit-* claims.",
            "Run production:permission-readonly after the gateway is enabled.",
            "Only then request explicit approval for write-type permission E2E.",
        ],
    }


def _server_session_readiness(safe_env: JsonObject) -> JsonObject:
    blockers: list[str] = []
    mode = str(safe_env["MEDICAL_AUDIT_AUTH_MODE"]["value"] or "header-transition")
    if mode != "server-session":
        blockers.append("auth-mode-not-server-session")
    if not str(safe_env["MEDICAL_AUDIT_SESSION_COOKIE_NAME"]["value"] or "").strip():
        blockers.append("session-cookie-name-missing")
    if not _truthy(safe_env["MEDICAL_AUDIT_SESSION_COOKIE_SECURE"]["value"]):
        blockers.append("session-cookie-secure-not-enabled")
    samesite = str(
        safe_env["MEDICAL_AUDIT_SESSION_COOKIE_SAMESITE"]["value"] or ""
    ).strip().lower()
    if samesite not in {"lax", "strict"}:
        blockers.append("session-cookie-samesite-invalid")
    if str(safe_env["MEDICAL_AUDIT_SESSION_STORE"]["value"] or "").strip() != "postgres":
        blockers.append("session-store-not-postgres")
    if not _truthy(safe_env["MEDICAL_AUDIT_DISABLE_LEGACY_HEADER_AUTH"]["value"]):
        blockers.append("legacy-header-auth-still-enabled")
    return {
        "mode": "server-session",
        "status": "ready" if not blockers else "blocked",
        "blockers": blockers,
        "next_evidence": [
            "Add login/logout/current-user endpoints backed by the session store.",
            "Verify disabled users and revoked sessions fail immediately.",
            "Only then request explicit approval for write-type permission E2E.",
        ],
    }


def _sanitize_env(env: os._Environ[str] | dict[str, str]) -> JsonObject:
    safe: JsonObject = {}
    for name in ENV_NAMES:
        value = str(env.get(name, "")).strip()
        safe[name] = {
            "status": "SET" if value else "UNSET",
            "value": value if _is_safe_to_report_value(name) else None,
        }
    signature_key_env = str(
        safe["MEDICAL_AUDIT_TRUSTED_PROXY_SIGNATURE_KEY_ENV"]["value"] or ""
    ).strip()
    referenced: dict[str, str] = {}
    if signature_key_env:
        referenced[signature_key_env] = (
            "SET" if str(env.get(signature_key_env, "")).strip() else "UNSET"
        )
    safe["referenced_secret_status"] = referenced
    return safe


def _is_safe_to_report_value(name: str) -> bool:
    return name in {
        "MEDICAL_AUDIT_AUTH_MODE",
        "MEDICAL_AUDIT_TRUSTED_PROXY_ENABLED",
        "MEDICAL_AUDIT_TRUSTED_PROXY_SIGNATURE_KEY_ENV",
        "MEDICAL_AUDIT_TRUSTED_PROXY_ALLOWED_SOURCE_CIDRS",
        "MEDICAL_AUDIT_SESSION_COOKIE_NAME",
        "MEDICAL_AUDIT_SESSION_COOKIE_SECURE",
        "MEDICAL_AUDIT_SESSION_COOKIE_SAMESITE",
        "MEDICAL_AUDIT_SESSION_STORE",
        "MEDICAL_AUDIT_DISABLE_LEGACY_HEADER_AUTH",
    }


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _write_json(report: JsonObject, path: Path | None) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_markdown(report: JsonObject, path: Path | None) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    blockers = "\n".join(f"- `{item}`" for item in report["blockers"]) or "- none"
    path.write_text(
        "\n".join(
            [
                "# Auth SSO Contract Readiness",
                "",
                f"- status: `{report['status']}`",
                f"- target_mode: `{report['target_mode']}`",
                f"- evidence_grade: `{report['evidence_grade']}`",
                "- production_side_effect: `none`",
                "- provider_call_status: `not_called`",
                "- secret_values_reported: `false`",
                "",
                "## Blockers",
                "",
                blockers,
                "",
            ]
        ),
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fail-closed readiness audit for the P0-04 real SSO/session contract. "
            "The script only inspects local environment names and SET/UNSET state; "
            "it performs no network call, provider call, production write, or env write."
        )
    )
    parser.add_argument(
        "--target-mode",
        choices=("trusted-sso-proxy", "server-session"),
        default="trusted-sso-proxy",
    )
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument(
        "--fail-when-blocked",
        action="store_true",
        help="Exit 2 when the selected target mode still has blockers.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(main())
