from __future__ import annotations

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

_INVALID_URL_SENTINEL = "<redacted-invalid-url>"
_UNSUPPORTED_VALUE_SENTINEL = "<unsupported-diagnostic-value>"


def safe_search_backend_details(details: Mapping[str, object]) -> dict[str, object]:
    return {
        key: safe_search_backend_value(value)
        for key, value in details.items()
        if isinstance(key, str) and not _is_sensitive_key(key)
    }


def safe_search_backend_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float)):
        return value
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

    if not parsed.scheme or not parsed.netloc:
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
    if _contains_sensitive_fragment(unquote(fragment)):
        fragment = ""
    return urlunsplit((parsed.scheme, netloc, parsed.path, safe_query, fragment))


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS)


def _contains_sensitive_fragment(value: str) -> bool:
    lowered = value.lower()
    return any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS)
