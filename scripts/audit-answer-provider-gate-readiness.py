#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_HOST = "101.34.52.232"
DEFAULT_USER = "ubuntu"
DEFAULT_REMOTE_CONTAINER = "medical_audit_app"
DEFAULT_JSON_OUTPUT = "tmp/outputs/answer-provider-gate-readiness-latest.json"
DEFAULT_MARKDOWN_OUTPUT = "tmp/outputs/answer-provider-gate-readiness-latest.md"

ANSWER_CONFIG_KEYS = (
    "MEDICAL_AUDIT_KB_ANSWER_PROVIDER",
    "MEDICAL_AUDIT_KB_ANSWER_API_KEY_ENV",
    "MEDICAL_AUDIT_KB_ANSWER_MODEL",
    "MEDICAL_AUDIT_KB_ANSWER_BASE_URL",
    "MEDICAL_AUDIT_KB_ANSWER_MAX_OUTPUT_TOKENS",
    "MEDICAL_AUDIT_KB_ANSWER_TEMPERATURE",
)
EMBEDDING_CONFIG_KEYS = (
    "KIMI_API_KEY_ENV",
    "KIMI_EMBEDDING_PROVIDER",
    "KIMI_EMBEDDING_MODEL",
    "KIMI_EMBEDDING_DIMENSION",
    "KIMI_EMBEDDING_BASE_URL",
    "KIMI_EMBEDDING_BATCH_SIZE",
)
CHAT_MODEL_ALIASES = (
    {
        "alias": "kimi-2.7",
        "env_slug": "KIMI_2_7",
        "default_provider": "kimi",
        "default_model": "kimi-k2.7-code",
        "default_api_key_env": "MOONSHOT_API_KEY",
        "default_base_url": "https://api.moonshot.ai/v1",
        "default_max_output_tokens": "4096",
        "minimum_output_tokens": 4096,
        "default_temperature": "1.0",
        "default_thinking_mode": "enabled",
        "required_thinking_mode": "enabled",
    },
    {
        "alias": "deepseek-v4-pro",
        "env_slug": "DEEPSEEK_V4_PRO",
        "default_provider": "deepseek",
        "default_model": "deepseek-v4-pro",
        "default_api_key_env": "DEEPSEEK_API_KEY",
        "default_base_url": "https://api.deepseek.com",
        "default_max_output_tokens": "900",
        "minimum_output_tokens": None,
        "default_temperature": "0.0",
        "default_thinking_mode": "disabled",
        "required_thinking_mode": "disabled",
    },
)
CHAT_MODEL_CONFIG_KEYS = tuple(
    f"MEDICAL_AUDIT_KB_CHAT_MODEL_{alias['env_slug']}_{suffix}"
    for alias in CHAT_MODEL_ALIASES
    for suffix in (
        "API_KEY_ENV",
        "PROVIDER",
        "MODEL",
        "BASE_URL",
        "MAX_OUTPUT_TOKENS",
        "TEMPERATURE",
        "THINKING_MODE",
    )
)
KNOWN_API_KEY_ENVS = (
    "DEEPSEEK_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "MOONSHOT_API_KEY",
    "KIMI_API_KEY",
)
PROVIDER_CANDIDATES = (
    {
        "candidate": "deepseek",
        "answer_provider": "openai",
        "answer_model": "deepseek-v4-pro",
        "answer_api_key_env": "DEEPSEEK_API_KEY",
        "answer_base_url": "https://api.deepseek.com",
    },
    {
        "candidate": "openai",
        "answer_provider": "openai",
        "answer_model": "gpt-4.1-mini",
        "answer_api_key_env": "OPENAI_API_KEY",
        "answer_base_url": "https://api.openai.com/v1",
    },
    {
        "candidate": "anthropic",
        "answer_provider": "anthropic",
        "answer_model": "claude-haiku-4-5",
        "answer_api_key_env": "ANTHROPIC_API_KEY",
        "answer_base_url": "https://api.anthropic.com",
    },
    {
        "candidate": "moonshot-chat",
        "answer_provider": "openai",
        "answer_model": "kimi-k2.7-code",
        "answer_api_key_env": "MOONSHOT_API_KEY",
        "answer_base_url": "https://api.moonshot.ai/v1",
    },
)


class ReadinessError(RuntimeError):
    pass


def main() -> int:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    json_output = _resolve_output(repo_root, str(args.json_output))
    markdown_output = _resolve_output(repo_root, str(args.markdown_output))

    scopes: list[dict[str, Any]] = []
    if not args.skip_local:
        scopes.append(_build_scope_report("local-shell", _sanitize_env_mapping(os.environ)))
    if args.ssh_key:
        ssh_key = _resolve_ssh_key(repo_root, str(args.ssh_key))
        remote_snapshot = _collect_remote_snapshot(
            ssh_key=ssh_key,
            ssh_user=str(args.ssh_user),
            ssh_host=str(args.ssh_host),
            container=str(args.remote_container),
        )
        scopes.append(_build_scope_report("production-container", remote_snapshot))

    report = _build_report(scopes)
    _write_json(json_output, report)
    _write_markdown(markdown_output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.fail_when_not_ready and report["status"] != "ready_for_smoke":
        return 2
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only answer-provider gate readiness audit. The report only contains "
            "environment variable names, SET/UNSET states, and non-secret config values. "
            "ready_for_smoke is only a precondition, not provider validation."
        )
    )
    parser.add_argument("--skip-local", action="store_true")
    parser.add_argument(
        "--ssh-key",
        default="",
        help="Optional SSH key for production container observation. Omit for local only.",
    )
    parser.add_argument("--ssh-user", default=DEFAULT_USER)
    parser.add_argument("--ssh-host", default=DEFAULT_HOST)
    parser.add_argument("--remote-container", default=DEFAULT_REMOTE_CONTAINER)
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument(
        "--fail-when-not-ready",
        action="store_true",
        help="Exit 2 when no scope has a candidate provider key ready for smoke.",
    )
    return parser.parse_args()


def _resolve_output(repo_root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return repo_root / path


def _resolve_ssh_key(repo_root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return repo_root / path


def _sanitize_env_mapping(mapping: os._Environ[str] | dict[str, str]) -> dict[str, Any]:
    safe_values: dict[str, str] = {}
    for key in (*ANSWER_CONFIG_KEYS, *EMBEDDING_CONFIG_KEYS, *CHAT_MODEL_CONFIG_KEYS):
        value = str(mapping.get(key, "")).strip()
        if value:
            safe_values[key] = value

    status_names = set(KNOWN_API_KEY_ENVS)
    answer_key_env = safe_values.get("MEDICAL_AUDIT_KB_ANSWER_API_KEY_ENV", "").strip()
    if answer_key_env:
        status_names.add(answer_key_env)
    kimi_key_env = safe_values.get("KIMI_API_KEY_ENV", "").strip()
    if kimi_key_env:
        status_names.add(kimi_key_env)
    for alias in CHAT_MODEL_ALIASES:
        api_key_env = safe_values.get(
            f"MEDICAL_AUDIT_KB_CHAT_MODEL_{alias['env_slug']}_API_KEY_ENV",
            "",
        ).strip()
        if api_key_env:
            status_names.add(api_key_env)

    key_status = {
        name: "SET" if str(mapping.get(name, "")).strip() else "UNSET"
        for name in sorted(status_names)
    }
    return {"safe_values": safe_values, "key_status": key_status}


def _build_scope_report(scope: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    safe_values = _dict(snapshot.get("safe_values"))
    key_status = _dict(snapshot.get("key_status"))
    answer_config = _answer_config_readiness(safe_values=safe_values, key_status=key_status)
    candidates = [
        _candidate_readiness(candidate, key_status=key_status)
        for candidate in PROVIDER_CANDIDATES
    ]
    chat_models = _chat_model_readiness(safe_values=safe_values, key_status=key_status)
    ready_candidates = [
        candidate["candidate"]
        for candidate in candidates
        if candidate["precondition_status"] == "ready_for_smoke"
    ]
    ready_chat_model_aliases = [
        model["alias"] for model in chat_models if model["status"] == "configured_with_key"
    ]
    return {
        "scope": scope,
        "answer_runtime": answer_config,
        "embedding_runtime": _embedding_runtime(safe_values=safe_values, key_status=key_status),
        "chat_model_runtime": chat_models,
        "provider_candidates": candidates,
        "ready_for_provider_smoke": bool(ready_candidates or ready_chat_model_aliases),
        "ready_provider_candidates": ready_candidates,
        "ready_chat_model_aliases": ready_chat_model_aliases,
    }


def _answer_config_readiness(
    *, safe_values: dict[str, Any], key_status: dict[str, Any]
) -> dict[str, Any]:
    provider = str(safe_values.get("MEDICAL_AUDIT_KB_ANSWER_PROVIDER", "fallback")).strip()
    provider = provider or "fallback"
    api_key_env = str(safe_values.get("MEDICAL_AUDIT_KB_ANSWER_API_KEY_ENV", "")).strip()
    api_key_state = str(key_status.get(api_key_env, "UNSET")) if api_key_env else "UNSET"
    enabled = provider.lower() not in {"", "fallback", "none"}
    complete = enabled and bool(api_key_env) and api_key_state == "SET"
    if complete:
        status = "configured_with_key"
    elif enabled:
        status = "configured_missing_key"
    else:
        status = "fallback_or_unset"
    return {
        "status": status,
        "provider": provider,
        "model": str(safe_values.get("MEDICAL_AUDIT_KB_ANSWER_MODEL", "")).strip() or None,
        "api_key_env": api_key_env or None,
        "api_key_status": api_key_state,
        "base_url": str(safe_values.get("MEDICAL_AUDIT_KB_ANSWER_BASE_URL", "")).strip()
        or None,
        "max_output_tokens": str(
            safe_values.get("MEDICAL_AUDIT_KB_ANSWER_MAX_OUTPUT_TOKENS", "")
        ).strip()
        or None,
        "temperature": str(
            safe_values.get("MEDICAL_AUDIT_KB_ANSWER_TEMPERATURE", "")
        ).strip()
        or None,
    }


def _embedding_runtime(
    *, safe_values: dict[str, Any], key_status: dict[str, Any]
) -> dict[str, Any]:
    api_key_env = str(safe_values.get("KIMI_API_KEY_ENV", "KIMI_API_KEY")).strip()
    return {
        "provider": str(safe_values.get("KIMI_EMBEDDING_PROVIDER", "")).strip() or None,
        "model": str(safe_values.get("KIMI_EMBEDDING_MODEL", "")).strip() or None,
        "dimension": str(safe_values.get("KIMI_EMBEDDING_DIMENSION", "")).strip() or None,
        "api_key_env": api_key_env,
        "api_key_status": str(key_status.get(api_key_env, "UNSET")),
        "base_url": str(safe_values.get("KIMI_EMBEDDING_BASE_URL", "")).strip() or None,
    }


def _chat_model_readiness(
    *, safe_values: dict[str, Any], key_status: dict[str, Any]
) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    for alias in CHAT_MODEL_ALIASES:
        prefix = f"MEDICAL_AUDIT_KB_CHAT_MODEL_{alias['env_slug']}"
        api_key_env = str(safe_values.get(f"{prefix}_API_KEY_ENV", "")).strip()
        api_key_state = str(key_status.get(api_key_env, "UNSET")) if api_key_env else "UNSET"
        max_output_tokens = str(
            safe_values.get(
                f"{prefix}_MAX_OUTPUT_TOKENS",
                alias["default_max_output_tokens"],
            )
        ).strip() or str(alias["default_max_output_tokens"])
        thinking_mode = str(
            safe_values.get(
                f"{prefix}_THINKING_MODE",
                alias["default_thinking_mode"],
            )
        ).strip().lower() or str(alias["default_thinking_mode"])
        if not api_key_env:
            status = "missing_api_key_env"
        elif api_key_state != "SET":
            status = "configured_missing_key"
        elif thinking_mode != alias["required_thinking_mode"]:
            status = "unsupported_thinking_mode"
        else:
            status = _output_budget_status(
                max_output_tokens,
                minimum=alias["minimum_output_tokens"],
            )
        models.append(
            {
                "alias": alias["alias"],
                "status": status,
                "provider": str(
                    safe_values.get(f"{prefix}_PROVIDER", alias["default_provider"])
                ).strip()
                or alias["default_provider"],
                "model": str(safe_values.get(f"{prefix}_MODEL", alias["default_model"])).strip()
                or alias["default_model"],
                "api_key_env": api_key_env or None,
                "expected_api_key_env": alias["default_api_key_env"],
                "api_key_status": api_key_state,
                "base_url": str(
                    safe_values.get(f"{prefix}_BASE_URL", alias["default_base_url"])
                ).strip()
                or alias["default_base_url"],
                "max_output_tokens": max_output_tokens,
                "temperature": str(
                    safe_values.get(
                        f"{prefix}_TEMPERATURE",
                        alias["default_temperature"],
                    )
                ).strip()
                or alias["default_temperature"],
                "thinking_mode": thinking_mode,
            }
        )
    return models


def _output_budget_status(value: str, *, minimum: object) -> str:
    try:
        parsed = int(value)
    except ValueError:
        return "invalid_output_budget"
    if parsed <= 0:
        return "invalid_output_budget"
    if isinstance(minimum, int) and parsed < minimum:
        return "insufficient_output_budget"
    return "configured_with_key"


def _candidate_readiness(
    candidate: dict[str, str], *, key_status: dict[str, Any]
) -> dict[str, Any]:
    api_key_env = candidate["answer_api_key_env"]
    api_key_state = str(key_status.get(api_key_env, "UNSET"))
    precondition_status = "ready_for_smoke" if api_key_state == "SET" else "missing_key_env"
    return {
        **candidate,
        "api_key_status": api_key_state,
        "precondition_status": precondition_status,
        "provider_call_status": "not_called",
    }


def _build_report(scopes: list[dict[str, Any]]) -> dict[str, Any]:
    ready_scopes = [scope for scope in scopes if scope["ready_for_provider_smoke"]]
    status = "ready_for_smoke" if ready_scopes else "blocked"
    blockers = [] if ready_scopes else ["no-provider-or-chat-model-api-key-env-set"]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017 - py3.9 compat
        "status": status,
        "task": "answer-provider-production-gate-readiness",
        "summary": {
            "scope_count": len(scopes),
            "ready_scope_count": len(ready_scopes),
            "ready_scopes": [scope["scope"] for scope in ready_scopes],
        },
        "blockers": blockers,
        "boundaries": {
            "provider_call_status": "not_called",
            "production_side_effect": "none",
            "production_env_write": False,
            "secret_values_reported": False,
            "evidence_grade": "L3-production-read-only"
            if any(scope["scope"] == "production-container" for scope in scopes)
            else "L1-local-runtime",
        },
        "scopes": scopes,
    }


def _collect_remote_snapshot(
    *, ssh_key: Path, ssh_user: str, ssh_host: str, container: str
) -> dict[str, Any]:
    if not ssh_key.exists():
        raise ReadinessError(f"SSH key not found: {ssh_key}")
    remote_code = _remote_audit_code(container=container)
    command = [
        "ssh",
        "-i",
        str(ssh_key),
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "IdentitiesOnly=yes",
        f"{ssh_user}@{ssh_host}",
        "python3",
        "-",
    ]
    print(
        "+ ssh "
        f"-i {shlex.quote(str(ssh_key))} "
        "-o StrictHostKeyChecking=no "
        "-o IdentitiesOnly=yes "
        f"{ssh_user}@{ssh_host} python3 - <answer-provider-readiness>",
        flush=True,
    )
    completed = subprocess.run(
        command,
        input=remote_code,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ReadinessError(completed.stderr.strip() or "remote readiness audit failed")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ReadinessError("remote readiness audit returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ReadinessError("remote readiness audit returned non-object JSON")
    return payload


def _remote_audit_code(*, container: str) -> str:
    config_keys = tuple((*ANSWER_CONFIG_KEYS, *EMBEDDING_CONFIG_KEYS, *CHAT_MODEL_CONFIG_KEYS))
    known_key_envs = tuple(KNOWN_API_KEY_ENVS)
    return f"""
import json
import subprocess

container = {container!r}
config_keys = {config_keys!r}
known_key_envs = {known_key_envs!r}

python_code = '''
import json
import os

config_keys = {config_keys!r}
known_key_envs = set({known_key_envs!r})

safe_values = {{}}
for key in config_keys:
    value = os.environ.get(key, '').strip()
    if value:
        safe_values[key] = value

answer_key_env = safe_values.get('MEDICAL_AUDIT_KB_ANSWER_API_KEY_ENV', '').strip()
if answer_key_env:
    known_key_envs.add(answer_key_env)
kimi_key_env = safe_values.get('KIMI_API_KEY_ENV', '').strip()
if kimi_key_env:
    known_key_envs.add(kimi_key_env)
for key, value in safe_values.items():
    if key.startswith('MEDICAL_AUDIT_KB_CHAT_MODEL_') and key.endswith('_API_KEY_ENV'):
        known_key_envs.add(value)

key_status = {{
    name: 'SET' if os.environ.get(name, '').strip() else 'UNSET'
    for name in sorted(known_key_envs)
}}
print(json.dumps({{'safe_values': safe_values, 'key_status': key_status}}, ensure_ascii=False))
'''

completed = subprocess.run(
    ['docker', 'exec', container, 'python', '-c', python_code],
    check=False,
    capture_output=True,
    text=True,
)
if completed.returncode != 0:
    raise SystemExit(completed.stderr.strip() or 'docker exec readiness probe failed')
print(completed.stdout.strip())
"""


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Answer Provider Gate Readiness",
        "",
        f"- status: `{report['status']}`",
        f"- evidence_grade: `{report['boundaries']['evidence_grade']}`",
        f"- provider_call_status: `{report['boundaries']['provider_call_status']}`",
        f"- production_side_effect: `{report['boundaries']['production_side_effect']}`",
        f"- secret_values_reported: `{report['boundaries']['secret_values_reported']}`",
        "",
        "## Scopes",
        "",
    ]
    for scope in report["scopes"]:
        lines.append(f"### {scope['scope']}")
        lines.append("")
        lines.append(f"- answer_runtime: `{scope['answer_runtime']['status']}`")
        lines.append(
            "- ready_chat_model_aliases: "
            f"`{', '.join(scope['ready_chat_model_aliases']) or 'none'}`"
        )
        lines.append(
            "- ready_provider_candidates: "
            f"`{', '.join(scope['ready_provider_candidates']) or 'none'}`"
        )
        lines.append("")
    if report["blockers"]:
        lines.extend(["## Blockers", ""])
        lines.extend(f"- `{blocker}`" for blocker in report["blockers"])
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReadinessError as exc:
        print(f"readiness audit failed: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
