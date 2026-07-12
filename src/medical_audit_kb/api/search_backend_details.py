from __future__ import annotations

import math
from collections.abc import Mapping
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

SENSITIVE_KEY_FRAGMENTS = (
    "secret",
    "token",
    "password",
    "private_key",
    "api_key",
    "credential",
)
SENSITIVE_MATCH_UNQUOTE_MAX_ROUNDS = 4

_INVALID_URL_SENTINEL = "<redacted-invalid-url>"
_UNSUPPORTED_VALUE_SENTINEL = "<unsupported-diagnostic-value>"


def safe_search_backend_details(details: Mapping[str, object]) -> dict[str, object]:
    return {
        key: safe_search_backend_value(value)
        for key, value in details.items()
        if isinstance(key, str) and not _is_sensitive_key(key)
    }


def safe_search_backend_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else _UNSUPPORTED_VALUE_SENTINEL
    if isinstance(value, str):
        return redact_url_credentials_and_sensitive_query(value)
    if isinstance(value, Mapping):
        return {
            key: safe_search_backend_value(nested_value)
            for key, nested_value in value.items()
            if isinstance(key, str) and not _is_sensitive_key(key)
        }
    if isinstance(value, (list, tuple)):
        return [safe_search_backend_value(item) for item in value]
    return _UNSUPPORTED_VALUE_SENTINEL


def redact_url_credentials_and_sensitive_query(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return _INVALID_URL_SENTINEL

    explicit_authority = value.startswith("//") or (
        bool(parsed.scheme) and value.lower().startswith(f"{parsed.scheme.lower()}://")
    )
    if not parsed.netloc:
        if explicit_authority:
            return _INVALID_URL_SENTINEL
        return value

    try:
        hostname = parsed.hostname
        port = parsed.port
        query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    except ValueError:
        return _INVALID_URL_SENTINEL

    if hostname is None:
        return _INVALID_URL_SENTINEL

    host = f"[{hostname}]" if ":" in hostname else hostname
    netloc = f"{host}:{port}" if port is not None else host
    safe_query = urlencode(
        [(key, query_value) for key, query_value in query_pairs if not _is_sensitive_key(key)],
        doseq=True,
    )
    fragment = parsed.fragment
    if _contains_sensitive_fragment(fragment):
        fragment = ""
    return urlunsplit((parsed.scheme, netloc, parsed.path, safe_query, fragment))


def _is_sensitive_key(key: str) -> bool:
    lowered = _canonicalize_for_sensitive_matching(key).lower()
    return any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS)


def _contains_sensitive_fragment(value: str) -> bool:
    lowered = _canonicalize_for_sensitive_matching(value).lower()
    return any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS)


def _canonicalize_for_sensitive_matching(value: str) -> str:
    current = value
    for _ in range(SENSITIVE_MATCH_UNQUOTE_MAX_ROUNDS):
        decoded = unquote(current)
        if decoded == current:
            break
        current = decoded
    return current
