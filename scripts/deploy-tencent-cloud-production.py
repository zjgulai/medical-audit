#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.parse
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath

DEFAULT_HOST = "101.34.52.232"
DEFAULT_USER = "ubuntu"
DEFAULT_DOMAIN = "audit.lute-tlz-dddd.top"
DEFAULT_REMOTE_APP_DIR = "/opt/medical-audit/app"
DEFAULT_REMOTE_WEB_DIR = "/var/www/audit"
DEFAULT_BASE_URL = f"https://{DEFAULT_DOMAIN}"
DEFAULT_PYTHON_INDEX = "https://pypi.org/simple"
REMOTE_NGINX_CONFIG = "/opt/ai-video/deploy/lighthouse/nginx.conf"
REMOTE_TRANSACTION_ROOT = "/opt/medical-audit/backups/transactions"
REMOTE_BACKUP_TIMEOUT_SECONDS = 45 * 60
REMOTE_COMPLETION_CHECK_TIMEOUT_SECONDS = 60
REMOTE_COMPLETION_POLL_SECONDS = 5
REMOTE_SSH_COMMAND_TIMEOUT_SECONDS = 30 * 60
REMOTE_RSYNC_TOTAL_TIMEOUT_SECONDS = 30 * 60
REMOTE_RSYNC_IO_TIMEOUT_SECONDS = 120
SSH_CONNECT_TIMEOUT_SECONDS = 15
SSH_SERVER_ALIVE_INTERVAL_SECONDS = 15
SSH_SERVER_ALIVE_COUNT_MAX = 4
RELEASE_MANIFEST_FORMAT = "medical-audit-web-release-manifest-v1"
RELEASE_MANIFEST_NAME = "release-manifest.json"
RELEASE_MANIFEST_FIELDS = {
    "files",
    "format",
    "lockfile_sha256",
    "node_version",
    "pnpm_version",
    "public_build_variables",
    "source_sha",
}
PUBLIC_BUILD_VARIABLES = (
    "NEXT_PUBLIC_AUDIT_ORG_LOGO",
    "NEXT_PUBLIC_AUDIT_ORG_NAME",
    "NEXT_PUBLIC_MEDICAL_AUDIT_AGENT_EXTENSION_PACK",
    "NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS",
)
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
FILE_HASH_CHUNK_SIZE = 1024 * 1024
MAX_RELEASE_MANIFEST_BYTES = 16 * 1024 * 1024
DIRECTORY_OPEN_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
FILE_OPEN_FLAGS = os.O_RDONLY | os.O_NOFOLLOW

APP_RSYNC_EXCLUDES = (
    ".DS_Store",
    ".deploy-sha",
    ".git",
    ".git/",
    ".gitnexus/",
    ".kiro/",
    ".playwright-mcp/",
    ".venv/",
    ".codegraph/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    "__pycache__/",
    "node_modules/",
    "web/.next/",
    "web/node_modules/",
    "web/test-results/",
    "web/playwright-report/",
    "drafts/",
    "tmp/",
    "data/",
    "archive/",
    "opendesign/",
    "output/",
    "ref/",
    "*.pyc",
    "*.pem",
    "*.key",
    "*.env",
    "*.uploading.cfg",
)


class DeployError(RuntimeError):
    pass


class RemoteOutcomeUnknownError(DeployError):
    pass


@dataclass(frozen=True)
class DeployConfig:
    repo_root: Path
    ssh_key: Path
    ssh_user: str
    ssh_host: str
    remote_app_dir: str
    remote_web_dir: str
    base_url: str
    stamp: str
    execute: bool
    rollback: bool
    allow_dirty: bool
    skip_web_build: bool
    skip_app_rebuild: bool
    apply_schema: bool
    skip_smoke: bool
    include_query_provider_smoke: bool
    include_review_write: bool
    confirm_production_write: str
    approved_sha: str
    expected_current_sha: str
    restore_sha: str
    allow_first_legacy_migration: bool
    report_path: Path

    @property
    def ssh_target(self) -> str:
        return f"{self.ssh_user}@{self.ssh_host}"


@dataclass(frozen=True)
class ReleaseEvidence:
    manifest_sha256: str
    manifest_file_count: int
    static_asset_path: str
    static_asset_sha256: str


@dataclass(frozen=True)
class _ReleaseFileEvidence:
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class _NginxToken:
    value: bytes
    start: int
    end: int


def _tokenize_nginx(content: bytes) -> list[_NginxToken]:
    tokens: list[_NginxToken] = []
    index = 0
    length = len(content)
    punctuation = b"{};"
    whitespace = b" \t\r\n"
    while index < length:
        byte = content[index]
        if byte in whitespace:
            index += 1
            continue
        if byte == ord("#"):
            newline = content.find(b"\n", index)
            index = length if newline < 0 else newline + 1
            continue
        if byte in punctuation:
            tokens.append(_NginxToken(content[index : index + 1], index, index + 1))
            index += 1
            continue
        start = index
        quote: int | None = None
        escaped = False
        while index < length:
            byte = content[index]
            if quote is not None:
                index += 1
                if escaped:
                    escaped = False
                elif byte == ord("\\"):
                    escaped = True
                elif byte == quote:
                    quote = None
                continue
            if byte in (ord("'"), ord('"')):
                quote = byte
                index += 1
                continue
            if byte in whitespace or byte in punctuation or byte == ord("#"):
                break
            index += 1
        if quote is not None:
            raise DeployError("nginx configuration contains an unterminated quote")
        if index == start:
            raise DeployError("nginx configuration tokenization failed")
        tokens.append(_NginxToken(content[start:index], start, index))
    return tokens


def _nginx_brace_pairs(tokens: Sequence[_NginxToken]) -> dict[int, int]:
    pairs: dict[int, int] = {}
    stack: list[int] = []
    for index, token in enumerate(tokens):
        if token.value == b"{":
            stack.append(index)
        elif token.value == b"}":
            if not stack:
                raise DeployError("nginx configuration braces are unbalanced")
            opening = stack.pop()
            pairs[opening] = index
    if stack:
        raise DeployError("nginx configuration braces are unbalanced")
    return pairs


def _audit_server_location_spans(content: bytes) -> dict[bytes, tuple[int, int]]:
    tokens = _tokenize_nginx(content)
    brace_pairs = _nginx_brace_pairs(tokens)
    domain = b"audit.lute-tlz-dddd.top"
    server_candidates: list[tuple[int, int]] = []
    for index, token in enumerate(tokens[:-1]):
        if token.value != b"server" or tokens[index + 1].value != b"{":
            continue
        opening = index + 1
        closing = brace_pairs.get(opening)
        if closing is None:
            raise DeployError("nginx configuration braces are unbalanced")
        cursor = opening + 1
        matching_directives = 0
        while cursor < closing:
            current = tokens[cursor]
            if current.value == b"{":
                nested_close = brace_pairs.get(cursor)
                if nested_close is None:
                    raise DeployError("nginx configuration braces are unbalanced")
                cursor = nested_close + 1
                continue
            if current.value != b"server_name":
                cursor += 1
                continue
            end = cursor + 1
            values: list[bytes] = []
            while end < closing and tokens[end].value != b";":
                if tokens[end].value in {b"{", b"}"}:
                    raise DeployError("nginx server_name structure drift")
                values.append(tokens[end].value)
                end += 1
            if end >= closing:
                raise DeployError("nginx server_name structure drift")
            if domain in values:
                matching_directives += 1
            cursor = end + 1
        if matching_directives == 1:
            server_candidates.append((opening, closing))
        elif matching_directives > 1:
            raise DeployError("nginx audit server cardinality mismatch")
    if len(server_candidates) != 1:
        raise DeployError("nginx audit server cardinality mismatch")

    opening, closing = server_candidates[0]
    wanted = {b"/_next/static/", b"/brand/", b"/"}
    found: dict[bytes, list[tuple[int, int]]] = {selector: [] for selector in wanted}
    cursor = opening + 1
    while cursor < closing:
        current = tokens[cursor]
        if current.value == b"{":
            nested_close = brace_pairs.get(cursor)
            if nested_close is None:
                raise DeployError("nginx configuration braces are unbalanced")
            cursor = nested_close + 1
            continue
        if current.value != b"location":
            cursor += 1
            continue
        block_open = cursor + 1
        selectors: list[bytes] = []
        while block_open < closing and tokens[block_open].value != b"{":
            if tokens[block_open].value in {b";", b"}"}:
                raise DeployError("nginx audit location structure drift")
            selectors.append(tokens[block_open].value)
            block_open += 1
        if block_open >= closing:
            raise DeployError("nginx audit location structure drift")
        block_close = brace_pairs.get(block_open)
        if block_close is None:
            raise DeployError("nginx configuration braces are unbalanced")
        if len(selectors) == 1 and selectors[0] in wanted:
            found[selectors[0]].append((current.start, tokens[block_close].end))
        cursor = block_close + 1
    if any(len(spans) != 1 for spans in found.values()):
        raise DeployError("nginx audit location cardinality mismatch")
    return {selector: spans[0] for selector, spans in found.items()}


def _patch_nginx_audit_locations(source: bytes, fragment: bytes) -> bytes:
    source_spans = _audit_server_location_spans(source)
    fragment_spans = _audit_server_location_spans(fragment)
    replacements: list[tuple[int, int, bytes]] = []
    for selector, (start, end) in source_spans.items():
        fragment_start, fragment_end = fragment_spans[selector]
        replacements.append((start, end, fragment[fragment_start:fragment_end]))
    result = source
    for start, end, replacement in sorted(replacements, reverse=True):
        result = result[:start] + replacement + result[end:]
    return result


def _overwrite_regular_file_in_place(destination: Path, source: Path) -> None:
    content, _evidence = _read_regular_file(
        source,
        label="nginx candidate",
        collect_content=True,
        max_bytes=MAX_RELEASE_MANIFEST_BYTES,
    )
    try:
        destination_stat = destination.lstat()
    except OSError as exc:
        raise DeployError("nginx host config is missing or unreadable") from exc
    if stat.S_ISLNK(destination_stat.st_mode) or not stat.S_ISREG(
        destination_stat.st_mode,
    ):
        raise DeployError("nginx host config must be a regular file and not a symlink")
    try:
        descriptor = os.open(
            destination,
            os.O_WRONLY | os.O_NOFOLLOW,
        )
    except OSError as exc:
        raise DeployError("nginx host config could not be opened safely") from exc
    try:
        opened = os.fstat(descriptor)
        if not _same_file(destination_stat, opened) or not stat.S_ISREG(opened.st_mode):
            raise DeployError("nginx host config changed before in-place update")
        os.ftruncate(descriptor, 0)
        offset = 0
        while offset < len(content):
            offset += os.write(descriptor, content[offset:])
        os.fsync(descriptor)
        final = os.fstat(descriptor)
    except OSError as exc:
        raise DeployError("nginx host config in-place update failed") from exc
    finally:
        os.close(descriptor)
    if not _same_file(opened, final) or final.st_size != len(content):
        raise DeployError("nginx host config inode changed during in-place update")
    try:
        final_path = destination.lstat()
    except OSError as exc:
        raise DeployError("nginx host config path changed during in-place update") from exc
    if not _same_file(final, final_path):
        raise DeployError("nginx host config path changed during in-place update")


def _remote_lock_dir(config: DeployConfig) -> str:
    return f"{config.remote_app_dir}.deploy.lock"


def _remote_lock_acquire_script(lock_dir: str, owner_token: str) -> str:
    return f"""
set -euo pipefail
umask 077
lock_dir={shlex.quote(lock_dir)}
owner_token={shlex.quote(owner_token)}
if ! mkdir -- "$lock_dir"; then
  echo "production deployment lock is already held" >&2
  exit 73
fi
cleanup_unowned_lock() {{
  if [ ! -s "$lock_dir/owner" ]; then
    rm -f -- "$lock_dir/owner.next"
    rmdir -- "$lock_dir" 2>/dev/null || true
  fi
}}
trap cleanup_unowned_lock ERR
printf '%s\n' "$owner_token" > "$lock_dir/owner.next"
mv -f -- "$lock_dir/owner.next" "$lock_dir/owner"
trap - ERR
"""


def _remote_lock_release_script(lock_dir: str, owner_token: str) -> str:
    return f"""
set -euo pipefail
lock_dir={shlex.quote(lock_dir)}
owner_token={shlex.quote(owner_token)}
test -d "$lock_dir"
if [ "$(cat "$lock_dir/owner" 2>/dev/null || true)" != "$owner_token" ]; then
  echo "production deployment lock owner mismatch" >&2
  exit 74
fi
worker_pid="$(cat "$lock_dir/worker.pid" 2>/dev/null || true)"
if [ -n "$worker_pid" ] && kill -0 "$worker_pid" 2>/dev/null; then
  echo "production deployment lock retained for active remote worker" >&2
  exit 75
fi
rm -f -- "$lock_dir/worker.pid" "$lock_dir/owner"
rmdir -- "$lock_dir"
"""


def _remote_lock_guard_script(config: DeployConfig, owner_token: str) -> str:
    return f"""
lock_dir={shlex.quote(_remote_lock_dir(config))}
owner_token={shlex.quote(owner_token)}
test -f "$lock_dir/owner"
test "$(cat "$lock_dir/owner")" = "$owner_token"
"""


def _remote_rsync_path(config: DeployConfig, owner_token: str) -> str:
    owner_path = f"{_remote_lock_dir(config)}/owner"
    return (
        f"test -f {shlex.quote(owner_path)} && "
        f"test \"$(cat {shlex.quote(owner_path)})\" = "
        f"{shlex.quote(owner_token)} && rsync"
    )


def _acquire_remote_deploy_lock(config: DeployConfig) -> str:
    owner_token = secrets.token_hex(32)
    _ssh(
        config,
        _remote_lock_acquire_script(_remote_lock_dir(config), owner_token),
    )
    return owner_token


def _release_remote_deploy_lock(config: DeployConfig, owner_token: str) -> None:
    _ssh(
        config,
        _remote_lock_release_script(_remote_lock_dir(config), owner_token),
    )


def _remote_release_verifier_code() -> str:
    return r'''
import hashlib
import json
import os
import stat
import sys
from pathlib import Path, PurePosixPath

FORMAT = "medical-audit-web-release-manifest-v1"
MANIFEST = "release-manifest.json"
FIELDS = {
    "files",
    "format",
    "lockfile_sha256",
    "node_version",
    "pnpm_version",
    "public_build_variables",
    "source_sha",
}


class VerificationError(RuntimeError):
    pass


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise VerificationError("duplicate JSON key")
        result[key] = value
    return result


def canonical_path(value):
    if type(value) is not str:
        raise VerificationError("invalid path")
    parts = value.split("/")
    normalized = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or "\x00" in value
        or normalized.is_absolute()
        or any(part in {"", ".", ".."} for part in parts)
        or normalized.as_posix() != value
        or value == MANIFEST
    ):
        raise VerificationError("invalid path")
    return value


def hash_regular(path):
    initial = path.lstat()
    if stat.S_ISLNK(initial.st_mode) or not stat.S_ISREG(initial.st_mode):
        raise VerificationError("non-regular file")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    digest = hashlib.sha256()
    size = 0
    try:
        opened = os.fstat(descriptor)
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
        final = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (
        initial.st_dev != opened.st_dev
        or initial.st_ino != opened.st_ino
        or opened.st_dev != final.st_dev
        or opened.st_ino != final.st_ino
        or opened.st_size != final.st_size
        or opened.st_mtime_ns != final.st_mtime_ns
        or size != final.st_size
    ):
        raise VerificationError("file changed")
    return size, digest.hexdigest()


def collect(root):
    result = {}

    def visit(directory, relative_directory):
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name.encode("utf-8"))
        except OSError as exc:
            raise VerificationError("directory unreadable") from exc
        for entry in entries:
            relative = (
                f"{relative_directory}/{entry.name}"
                if relative_directory
                else entry.name
            )
            mode = entry.stat(follow_symlinks=False).st_mode
            if stat.S_ISLNK(mode):
                raise VerificationError("symlink")
            if stat.S_ISDIR(mode):
                visit(Path(entry.path), relative)
                continue
            if not stat.S_ISREG(mode):
                raise VerificationError("special file")
            if relative != MANIFEST:
                result[relative] = hash_regular(Path(entry.path))

    visit(root, "")
    return result


def verify():
    if len(sys.argv) != 7:
        raise VerificationError("invalid arguments")
    root = Path(sys.argv[1])
    expected_source = sys.argv[2]
    expected_manifest_sha = sys.argv[3]
    expected_count = int(sys.argv[4])
    expected_static_path = sys.argv[5]
    expected_static_sha = sys.argv[6]
    root_stat = root.lstat()
    if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
        raise VerificationError("invalid root")
    manifest_path = root / MANIFEST
    manifest_size, manifest_sha = hash_regular(manifest_path)
    if manifest_size > 16 * 1024 * 1024 or (
        expected_manifest_sha != "-" and manifest_sha != expected_manifest_sha
    ):
        raise VerificationError("manifest mismatch")
    manifest_bytes = manifest_path.read_bytes()
    payload = json.loads(
        manifest_bytes.decode("utf-8"),
        object_pairs_hook=unique_object,
    )
    if not isinstance(payload, dict) or set(payload) != FIELDS:
        raise VerificationError("manifest fields")
    if payload.get("format") != FORMAT or payload.get("source_sha") != expected_source:
        raise VerificationError("manifest identity")
    raw_files = payload.get("files")
    if not isinstance(raw_files, list):
        raise VerificationError("manifest files")
    declared = {}
    ordered_paths = []
    for entry in raw_files:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "size_bytes"}:
            raise VerificationError("manifest entry")
        path = canonical_path(entry["path"])
        if path in declared:
            raise VerificationError("duplicate path")
        size = entry["size_bytes"]
        sha256 = entry["sha256"]
        if type(size) is not int or size < 0:
            raise VerificationError("invalid size")
        if (
            type(sha256) is not str
            or len(sha256) != 64
            or any(character not in "0123456789abcdef" for character in sha256)
        ):
            raise VerificationError("invalid hash")
        declared[path] = (size, sha256)
        ordered_paths.append(path)
    if ordered_paths != sorted(ordered_paths, key=lambda value: value.encode("utf-8")):
        raise VerificationError("path order")
    actual = collect(root)
    if declared != actual or (expected_count >= 0 and len(declared) != expected_count):
        raise VerificationError("release mismatch")
    if expected_static_path == "-":
        if not any(path.startswith("_next/static/") for path in declared):
            raise VerificationError("static mismatch")
    elif declared.get(expected_static_path) != (
        declared.get(expected_static_path, (-1, ""))[0],
        expected_static_sha,
    ):
        raise VerificationError("static mismatch")


try:
    verify()
except Exception:
    print("release verification failed", file=sys.stderr)
    raise SystemExit(2)
'''


def _public_release_verifier_code() -> str:
    return r'''
import hashlib
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path


def origin(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.username is not None or parsed.password is not None or not parsed.hostname:
        raise RuntimeError("invalid URL origin")
    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme.lower() == "https" else 80
    return parsed.scheme.lower(), parsed.hostname.lower(), port


class SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, expected_origin):
        super().__init__()
        self.expected_origin = expected_origin

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if origin(newurl) != self.expected_origin:
            raise RuntimeError("cross-origin redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def cache_directives(values):
    result = set()
    for value in values:
        for part in value.split(","):
            name = part.split("=", 1)[0].strip().lower()
            if name:
                result.add(name)
    return result


def fetch(url, expected_origin):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "medical-audit-deploy-verifier/1.0"},
    )
    opener = urllib.request.build_opener(SameOriginRedirectHandler(expected_origin))
    with opener.open(request, timeout=20) as response:
        body = response.read()
        values = response.headers.get_all("Cache-Control") or []
        final_url = response.geturl()
    if origin(final_url) != expected_origin:
        raise RuntimeError("final URL origin mismatch")
    return body, cache_directives(values)


def verify():
    if len(sys.argv) == 3:
        base_url = sys.argv[1].rstrip("/")
        release_root = Path(sys.argv[2])
        manifest = (release_root / "release-manifest.json").read_bytes()
        payload = json.loads(manifest.decode("utf-8"))
        candidates = [
            entry
            for entry in payload["files"]
            if entry["path"].startswith("_next/static/")
        ]
        if not candidates:
            raise RuntimeError("missing public static sample")
        selected = candidates[0]
        static_path = selected["path"]
        expected_manifest_sha = hashlib.sha256(manifest).hexdigest()
        expected_static_sha = selected["sha256"]
    elif len(sys.argv) == 5:
        base_url = sys.argv[1].rstrip("/")
        static_path = sys.argv[2]
        expected_manifest_sha = sys.argv[3]
        expected_static_sha = sys.argv[4]
    else:
        raise RuntimeError("invalid arguments")
    expected_origin = origin(base_url)
    manifest, _manifest_cache = fetch(
        base_url + "/release-manifest.json",
        expected_origin,
    )
    if hashlib.sha256(manifest).hexdigest() != expected_manifest_sha:
        raise RuntimeError("public manifest mismatch")
    _html, html_cache = fetch(base_url + "/", expected_origin)
    if html_cache.isdisjoint({"no-store", "no-cache"}):
        raise RuntimeError("html cache mismatch")
    quoted_static = urllib.parse.quote(static_path, safe="/-._~")
    static, static_cache = fetch(base_url + "/" + quoted_static, expected_origin)
    if hashlib.sha256(static).hexdigest() != expected_static_sha:
        raise RuntimeError("public static mismatch")
    if "immutable" not in static_cache:
        raise RuntimeError("static cache mismatch")


try:
    verify()
except Exception:
    print("public release verification failed", file=sys.stderr)
    raise SystemExit(2)
'''


@contextmanager
def _approved_release_snapshot(config: DeployConfig) -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="medical-audit-approved-release-") as temp_dir:
        temp_root = Path(temp_dir)
        archive_path = temp_root / "approved-source.tar"
        snapshot_root = temp_root / "source"
        snapshot_root.mkdir(mode=0o700)
        with archive_path.open("wb") as archive_output:
            subprocess.run(
                ["git", "archive", "--format=tar", config.approved_sha],
                cwd=config.repo_root,
                check=True,
                stdout=archive_output,
            )
        try:
            with tarfile.open(archive_path, mode="r:") as archive:
                archive.extractall(snapshot_root, filter="data")
        except (OSError, tarfile.TarError) as exc:
            raise DeployError("approved SHA archive could not be extracted safely") from exc
        finally:
            archive_path.unlink(missing_ok=True)
        if config.skip_web_build:
            source_web_out = config.repo_root / "web" / "out"
            snapshot_web_out = snapshot_root / "web" / "out"
            if snapshot_web_out.is_symlink() or (
                snapshot_web_out.exists() and not snapshot_web_out.is_dir()
            ):
                snapshot_web_out.unlink()
            elif snapshot_web_out.exists():
                shutil.rmtree(snapshot_web_out)
            snapshot_web_out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source_web_out, snapshot_web_out, symlinks=True)
        yield snapshot_root


def main() -> int:
    try:
        config = _config_from_args(_parse_args())
        _print_plan(config)
        _validate_local_state(config)
        if config.rollback:
            owner_token = _acquire_remote_deploy_lock(config)
            rollback_complete = False
            try:
                _run_remote_rollback(config, owner_token)
                rollback_complete = True
            finally:
                if rollback_complete:
                    _release_remote_deploy_lock(config, owner_token)
                else:
                    print(
                        "MANUAL_RECOVERY_REQUIRED: rollback failed; production lock "
                        "retained",
                        file=sys.stderr,
                    )
            return 0
        if config.execute and config.skip_web_build:
            _validate_web_release(config)
        if config.execute:
            with _approved_release_snapshot(config) as snapshot_root:
                return _run_nonrollback(replace(config, repo_root=snapshot_root))
        return _run_nonrollback(config)
    except DeployError as exc:
        print(f"deploy failed: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"command failed with exit code {exc.returncode}", file=sys.stderr)
        return exc.returncode or 1


def _run_nonrollback(config: DeployConfig) -> int:
    _validate_locked_python_dependencies(config)
    release_evidence: ReleaseEvidence | None = None
    if config.execute:
        _build_static_frontend(config)
        release_evidence = _validate_web_release(config)
    _run_remote_preflight(config)
    if not config.execute:
        print("Preflight passed. Add --execute --confirm-production to deploy.")
        return 0
    if release_evidence is None:
        raise DeployError("validated Web release evidence is missing")
    owner_token = _acquire_remote_deploy_lock(config)
    activation_reconcile_required = False
    release_lock = True
    schema_applied = False
    app_rebuild_attempted = False
    marker_commit_attempted = False
    try:
        _create_remote_backups(config, owner_token)
        _cleanup_remote_sync_artifacts(config, owner_token)
        _sync_application(config, owner_token)
        _prepare_remote_release_incoming(config, owner_token)
        _sync_static_frontend(config, owner_token)
        _verify_and_promote_remote_release(
            config,
            owner_token,
            release_evidence,
        )
        if config.apply_schema:
            _apply_schema(config, owner_token)
            schema_applied = True
        app_rebuild_attempted = not config.skip_app_rebuild
        _rebuild_application(config, owner_token)
        _activate_remote_release(config, owner_token)
        activation_reconcile_required = True
        _run_remote_post_checks(config)
        _verify_remote_release_commit_point(
            config,
            owner_token,
            release_evidence,
        )
        _run_production_smoke(config)
        marker_commit_attempted = True
        _write_remote_deploy_sha(config, owner_token)
    except BaseException as original_error:
        if not isinstance(original_error, Exception):
            release_lock = False
            raise
        if marker_commit_attempted:
            release_lock = False
            raise DeployError(
                "deploy marker commit outcome is unknown; production lock retained "
                "for manual reconciliation",
            ) from original_error
        if activation_reconcile_required and not isinstance(
            original_error,
            RemoteOutcomeUnknownError,
        ):
            try:
                _restore_remote_activation(config, owner_token)
            except BaseException as restore_error:
                release_lock = False
                raise DeployError(
                    "activation restore failed; production lock retained for "
                    "manual recovery",
                ) from restore_error
        if isinstance(original_error, RemoteOutcomeUnknownError):
            release_lock = False
            raise DeployError(
                "remote write outcome is unknown; production lock retained for "
                "manual reconciliation",
            ) from original_error
        if schema_applied or app_rebuild_attempted:
            print(
                "MANUAL_ROLLBACK_REQUIRED: app rebuild or schema may already be "
                "active; .deploy-sha was not committed",
                file=sys.stderr,
            )
        raise original_error
    finally:
        if release_lock:
            _release_remote_deploy_lock(config, owner_token)
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Deploy AuditScope to Tencent Cloud. The default mode is read-only "
            "preflight; production writes require --execute and confirmation."
        ),
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--execute",
        action="store_true",
        help="Run write operations against production after preflight succeeds.",
    )
    mode_group.add_argument(
        "--rollback",
        action="store_true",
        help="Restore app/web and deploy SHA from one verified pre-deploy backup stamp.",
    )
    parser.add_argument(
        "--confirm-production",
        default="",
        help=f"Required with --execute. Must equal {DEFAULT_DOMAIN}.",
    )
    parser.add_argument(
        "--approved-sha",
        default="",
        help=(
            "Required with --execute. The fresh local main HEAD and origin/main must both "
            "equal this full commit SHA."
        ),
    )
    parser.add_argument(
        "--expected-current-sha",
        default="",
        help="Required with --rollback. Rollback stops unless remote .deploy-sha equals it.",
    )
    parser.add_argument(
        "--restore-sha",
        default="",
        help="Required with --rollback. Must match .deploy-sha inside the app backup.",
    )
    parser.add_argument(
        "--allow-first-legacy-migration",
        action="store_true",
        help=(
            "Allow the one-time migration from the legacy flat Web root when no "
            "versioned current link or durable migration sentinel exists."
        ),
    )
    parser.add_argument(
        "--ssh-key",
        default=os.environ.get("MEDICAL_AUDIT_DEPLOY_SSH_KEY", "ai_video.pem"),
        help="Path to the SSH key. Defaults to ./ai_video.pem or env override.",
    )
    parser.add_argument("--ssh-user", default=DEFAULT_USER)
    parser.add_argument("--ssh-host", default=DEFAULT_HOST)
    parser.add_argument("--remote-app-dir", default=DEFAULT_REMOTE_APP_DIR)
    parser.add_argument("--remote-web-dir", default=DEFAULT_REMOTE_WEB_DIR)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--stamp",
        default=time.strftime("%Y%m%dT%H%M%S%z"),
        help="Deployment stamp used for remote backup and local report names.",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Allow deploying from a dirty git worktree.",
    )
    parser.add_argument(
        "--skip-web-build",
        action="store_true",
        help="Reuse the existing web/out directory instead of building it.",
    )
    parser.add_argument(
        "--skip-app-rebuild",
        action="store_true",
        help="Only sync files and static assets; do not rebuild/restart app.",
    )
    parser.add_argument(
        "--apply-schema",
        action="store_true",
        help="Apply sql/knowledge-query-schema.sql to production after sync.",
    )
    parser.add_argument(
        "--skip-smoke",
        action="store_true",
        help="Skip local production E2E smoke after deployment.",
    )
    parser.add_argument(
        "--include-query-provider-smoke",
        action="store_true",
        help=(
            "After deployment, opt in to query/provider smoke that may write query/audit "
            "history. Requires --confirm-production-write."
        ),
    )
    parser.add_argument(
        "--include-review-write",
        action="store_true",
        help="Include the write-path review task flow in production smoke.",
    )
    parser.add_argument(
        "--confirm-production-write",
        default="",
        help=(
            "Required with live query/provider or review smoke. Must equal the production "
            f"domain {DEFAULT_DOMAIN}."
        ),
    )
    parser.add_argument(
        "--report",
        default="",
        help=(
            "Local smoke report path. Defaults to "
            "tmp/outputs/production-e2e-smoke-after-deploy-<stamp>.json."
        ),
    )
    return parser.parse_args()


def _config_from_args(args: argparse.Namespace) -> DeployConfig:
    repo_root = Path(__file__).resolve().parents[1]
    ssh_key = Path(str(args.ssh_key)).expanduser()
    if not ssh_key.is_absolute():
        ssh_key = repo_root / ssh_key
    rollback = bool(args.rollback)
    execute = bool(args.execute)
    if (execute or rollback) and args.confirm_production != DEFAULT_DOMAIN:
        raise DeployError(
            f"live deployment actions require --confirm-production {DEFAULT_DOMAIN}",
        )
    if execute and bool(args.skip_smoke):
        raise DeployError("production execute forbids --skip-smoke")
    if execute and bool(args.skip_web_build):
        raise DeployError("production execute forbids --skip-web-build")
    allow_first_legacy_migration = bool(args.allow_first_legacy_migration)
    if allow_first_legacy_migration and not execute:
        raise DeployError("--allow-first-legacy-migration requires --execute")
    raw_base_url = str(args.base_url).strip()
    base_url = (
        _validated_live_base_url(raw_base_url)
        if execute or rollback
        else raw_base_url.rstrip("/")
    )
    approved_sha = _validated_sha(
        args.approved_sha,
        option="--approved-sha",
        required=execute,
    )
    expected_current_sha = _validated_sha(
        args.expected_current_sha,
        option="--expected-current-sha",
        required=rollback,
    )
    restore_sha = _validated_sha(
        args.restore_sha,
        option="--restore-sha",
        required=rollback,
    )
    include_query_provider_smoke = bool(args.include_query_provider_smoke)
    include_review_write = bool(args.include_review_write)
    if include_review_write and not include_query_provider_smoke:
        raise DeployError(
            "--include-review-write requires --include-query-provider-smoke",
        )
    confirm_production_write = str(args.confirm_production_write).strip()
    if include_query_provider_smoke and confirm_production_write != DEFAULT_DOMAIN:
        raise DeployError(
            f"live smoke requires --confirm-production-write {DEFAULT_DOMAIN}",
        )
    report_arg = str(args.report).strip()
    if not report_arg:
        report_path = repo_root / "tmp" / "outputs" / (
            f"production-e2e-smoke-after-deploy-{args.stamp}.json"
        )
    else:
        report_path = Path(report_arg).expanduser()
        if not report_path.is_absolute():
            report_path = repo_root / report_path
    return DeployConfig(
        repo_root=repo_root,
        ssh_key=ssh_key,
        ssh_user=str(args.ssh_user),
        ssh_host=str(args.ssh_host),
        remote_app_dir=str(args.remote_app_dir).rstrip("/"),
        remote_web_dir=str(args.remote_web_dir).rstrip("/"),
        base_url=base_url,
        stamp=str(args.stamp),
        execute=execute,
        rollback=rollback,
        allow_dirty=bool(args.allow_dirty),
        skip_web_build=bool(args.skip_web_build),
        skip_app_rebuild=bool(args.skip_app_rebuild),
        apply_schema=bool(args.apply_schema),
        skip_smoke=bool(args.skip_smoke),
        include_query_provider_smoke=include_query_provider_smoke,
        include_review_write=include_review_write,
        confirm_production_write=confirm_production_write,
        approved_sha=approved_sha,
        expected_current_sha=expected_current_sha,
        restore_sha=restore_sha,
        allow_first_legacy_migration=allow_first_legacy_migration,
        report_path=report_path,
    )


def _validated_sha(value: object, *, option: str, required: bool) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        if required:
            raise DeployError(f"{option} requires a full 40-character commit SHA")
        return ""
    if re.fullmatch(r"[0-9a-f]{40}", normalized) is None:
        raise DeployError(f"{option} requires a full 40-character commit SHA")
    return normalized


def _validated_live_base_url(value: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise DeployError("live --base-url is invalid") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname != DEFAULT_DOMAIN
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise DeployError(
            "live --base-url must be the exact HTTPS production origin",
        )
    return DEFAULT_BASE_URL


def _print_plan(config: DeployConfig) -> None:
    mode = "rollback" if config.rollback else "execute" if config.execute else "preflight"
    print(f"mode: {mode}", flush=True)
    print(f"target: {config.ssh_target}", flush=True)
    print(f"remote_app_dir: {config.remote_app_dir}", flush=True)
    print(f"remote_web_dir: {config.remote_web_dir}", flush=True)
    print(f"base_url: {config.base_url}", flush=True)


def _validate_local_state(config: DeployConfig) -> None:
    if not config.ssh_key.exists():
        raise DeployError(f"SSH key not found: {config.ssh_key}")
    if config.rollback:
        return
    if not (config.repo_root / "configs/deploy/tencent-cloud/docker-compose.prod.yaml").exists():
        raise DeployError("production compose file is missing")
    if not (config.repo_root / "scripts/run-production-e2e-smoke.py").exists():
        raise DeployError("production smoke script is missing")
    _run_capture(["git", "rev-parse", "--is-inside-work-tree"], cwd=config.repo_root)
    dirty = _run_capture(["git", "status", "--porcelain"], cwd=config.repo_root).strip()
    if config.execute and config.allow_dirty:
        raise DeployError("production execute forbids --allow-dirty")
    if dirty and not config.allow_dirty:
        raise DeployError("git worktree is dirty; commit changes or pass --allow-dirty")
    if config.execute:
        _validate_release_source(config)
    if config.execute and config.skip_web_build and not (config.repo_root / "web/out").is_dir():
        raise DeployError("web/out is missing; remove --skip-web-build or build first")


def _validate_release_source(config: DeployConfig) -> None:
    _run(
        [
            "git",
            "fetch",
            "--quiet",
            "origin",
            "+refs/heads/main:refs/remotes/origin/main",
        ],
        cwd=config.repo_root,
    )
    branch = _run_capture(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
        cwd=config.repo_root,
    ).strip()
    if branch != "main":
        raise DeployError(f"production execute requires main branch; current branch: {branch}")
    head_sha = _run_capture(["git", "rev-parse", "HEAD"], cwd=config.repo_root).strip()
    origin_main_sha = _run_capture(
        ["git", "rev-parse", "origin/main"],
        cwd=config.repo_root,
    ).strip()
    if head_sha != origin_main_sha:
        raise DeployError(
            f"production execute requires HEAD == origin/main; HEAD={head_sha} "
            f"origin/main={origin_main_sha}",
        )
    if head_sha != config.approved_sha:
        raise DeployError(
            f"production execute target does not match approved SHA: {config.approved_sha}",
        )


def _run_remote_preflight(config: DeployConfig) -> None:
    script = f"""
set -euo pipefail
test -d {shlex.quote(config.remote_app_dir)}
test -f {shlex.quote(config.remote_app_dir)}/configs/deploy/tencent-cloud/medical-audit.env
test -d {shlex.quote(config.remote_web_dir)}
docker inspect medical_audit_app >/dev/null
docker inspect medical_audit_pg >/dev/null
docker inspect ai_video_nginx >/dev/null
if ! docker exec ai_video_nginx nginx -t >/dev/null 2>&1; then
  echo "production nginx configuration test failed" >&2
  exit 80
fi
curl -fsS http://127.0.0.1:18080/health >/dev/null
auth_headers=(
  -H 'X-User-Id: deploy-smoke-admin'
  -H 'X-Role: it-admin'
  -H 'X-Project-Key: SELF-CHECK-FUND-20260607'
  -H 'X-Tenant-Id: hospital-demo'
)
curl -fsS "${{auth_headers[@]}}" \
  http://127.0.0.1:18080/knowledge-base/catalog >/dev/null
"""
    _ssh(config, script)


def _validate_locked_python_dependencies(config: DeployConfig) -> None:
    _run(
        [
            "uv",
            "lock",
            "--check",
            "--default-index",
            DEFAULT_PYTHON_INDEX,
        ],
        cwd=config.repo_root,
    )


def _build_static_frontend(config: DeployConfig) -> None:
    if config.skip_web_build:
        print("skip web build", flush=True)
        return
    _run(
        ["corepack", "pnpm", "install", "--frozen-lockfile"],
        cwd=config.repo_root,
    )
    child_environment = os.environ.copy()
    child_environment["MEDICAL_AUDIT_DEPLOY_SHA"] = config.approved_sha
    _run(
        ["corepack", "pnpm", "web:build:release"],
        cwd=config.repo_root,
        env=child_environment,
    )


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DeployError(f"web release manifest contains duplicate JSON key: {key}")
        result[key] = value
    return result


def _same_file(first: os.stat_result, second: os.stat_result) -> bool:
    return first.st_dev == second.st_dev and first.st_ino == second.st_ino


def _read_open_regular_file(
    file_descriptor: int,
    *,
    expected_stat: os.stat_result,
    label: str,
    collect_content: bool,
    max_bytes: int | None,
) -> tuple[bytes, _ReleaseFileEvidence]:
    digest = hashlib.sha256()
    chunks: list[bytes] = []
    size_bytes = 0
    try:
        initial_open_stat = os.fstat(file_descriptor)
        if not stat.S_ISREG(initial_open_stat.st_mode) or not _same_file(
            expected_stat,
            initial_open_stat,
        ):
            raise DeployError(f"{label} changed before it could be opened safely")
        while chunk := os.read(file_descriptor, FILE_HASH_CHUNK_SIZE):
            if collect_content:
                chunks.append(chunk)
            digest.update(chunk)
            size_bytes += len(chunk)
            if max_bytes is not None and size_bytes > max_bytes:
                raise DeployError(f"{label} exceeds the maximum allowed size")
        final_open_stat = os.fstat(file_descriptor)
    except OSError as exc:
        raise DeployError(f"{label} could not be read safely") from exc
    if (
        not _same_file(initial_open_stat, final_open_stat)
        or initial_open_stat.st_size != final_open_stat.st_size
        or initial_open_stat.st_mtime_ns != final_open_stat.st_mtime_ns
        or size_bytes != final_open_stat.st_size
    ):
        raise DeployError(f"{label} changed while it was being read")
    return (
        b"".join(chunks),
        _ReleaseFileEvidence(size_bytes=size_bytes, sha256=digest.hexdigest()),
    )


def _read_regular_file(
    path: Path,
    *,
    label: str,
    collect_content: bool = False,
    max_bytes: int | None = None,
) -> tuple[bytes, _ReleaseFileEvidence]:
    try:
        path_stat = path.lstat()
    except OSError as exc:
        raise DeployError(f"{label} is missing or unreadable") from exc
    if stat.S_ISLNK(path_stat.st_mode) or not stat.S_ISREG(path_stat.st_mode):
        raise DeployError(f"{label} must be a regular file and not a symlink")
    try:
        file_descriptor = os.open(path, FILE_OPEN_FLAGS)
    except OSError as exc:
        raise DeployError(f"{label} could not be opened safely") from exc
    try:
        return _read_open_regular_file(
            file_descriptor,
            expected_stat=path_stat,
            label=label,
            collect_content=collect_content,
            max_bytes=max_bytes,
        )
    finally:
        os.close(file_descriptor)


def _read_regular_file_at(
    *,
    directory_fd: int,
    name: str,
    label: str,
    collect_content: bool = False,
    max_bytes: int | None = None,
    expected_stat: os.stat_result | None = None,
) -> tuple[bytes, _ReleaseFileEvidence]:
    try:
        entry_stat = expected_stat or os.stat(
            name,
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
    except OSError as exc:
        raise DeployError(f"{label} is missing or unreadable") from exc
    if stat.S_ISLNK(entry_stat.st_mode) or not stat.S_ISREG(entry_stat.st_mode):
        raise DeployError(f"{label} must be a regular file and not a symlink")
    try:
        file_descriptor = os.open(
            name,
            FILE_OPEN_FLAGS,
            dir_fd=directory_fd,
        )
    except OSError as exc:
        raise DeployError(f"{label} could not be opened safely") from exc
    try:
        return _read_open_regular_file(
            file_descriptor,
            expected_stat=entry_stat,
            label=label,
            collect_content=collect_content,
            max_bytes=max_bytes,
        )
    finally:
        os.close(file_descriptor)


def _canonical_release_path(value: object) -> str:
    if type(value) is not str:
        raise DeployError("web release manifest file path must be a string")
    path = value
    raw_parts = path.split("/")
    normalized = PurePosixPath(path)
    if (
        not path
        or "\\" in path
        or "\x00" in path
        or normalized.is_absolute()
        or any(part in {"", ".", ".."} for part in raw_parts)
        or normalized.as_posix() != path
        or path == RELEASE_MANIFEST_NAME
    ):
        raise DeployError(
            "web release manifest path is not a canonical relative POSIX path",
        )
    return path


def _open_release_root(web_out: Path) -> tuple[int, os.stat_result]:
    try:
        root_stat = web_out.lstat()
    except OSError as exc:
        raise DeployError("web/out is missing or unreadable") from exc
    if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
        raise DeployError("web/out must be a directory and not a symlink")
    try:
        root_fd = os.open(web_out, DIRECTORY_OPEN_FLAGS)
    except OSError as exc:
        raise DeployError("web/out could not be opened safely") from exc
    try:
        opened_stat = os.fstat(root_fd)
        opened_root_is_valid = stat.S_ISDIR(opened_stat.st_mode) and _same_file(
            root_stat,
            opened_stat,
        )
    except (OSError, AttributeError, TypeError, ValueError) as exc:
        os.close(root_fd)
        raise DeployError("web/out could not be inspected after opening") from exc
    if not opened_root_is_valid:
        os.close(root_fd)
        raise DeployError("web/out changed before it could be opened safely")
    return root_fd, opened_stat


def _assert_release_root_unchanged(
    web_out: Path,
    *,
    opened_stat: os.stat_result,
) -> None:
    try:
        final_stat = web_out.lstat()
    except OSError as exc:
        raise DeployError("web/out changed during release validation") from exc
    if (
        stat.S_ISLNK(final_stat.st_mode)
        or not stat.S_ISDIR(final_stat.st_mode)
        or not _same_file(opened_stat, final_stat)
    ):
        raise DeployError("web/out changed during release validation")


def _collect_release_files(root_fd: int) -> dict[str, _ReleaseFileEvidence]:
    result: dict[str, _ReleaseFileEvidence] = {}

    def visit(directory_fd: int, relative_directory: str) -> None:
        try:
            with os.scandir(directory_fd) as iterator:
                entries = sorted(
                    iterator,
                    key=lambda item: item.name.encode("utf-8"),
                )
        except OSError as exc:
            raise DeployError("web/out could not be enumerated safely") from exc
        for entry in entries:
            relative_path = (
                f"{relative_directory}/{entry.name}"
                if relative_directory
                else entry.name
            )
            try:
                entry_stat = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise DeployError(
                    f"web/out entry could not be inspected: {relative_path}",
                ) from exc
            if stat.S_ISLNK(entry_stat.st_mode):
                raise DeployError(f"web/out contains a symlink: {relative_path}")
            if stat.S_ISDIR(entry_stat.st_mode):
                try:
                    child_fd = os.open(
                        entry.name,
                        DIRECTORY_OPEN_FLAGS,
                        dir_fd=directory_fd,
                    )
                except OSError as exc:
                    raise DeployError(
                        f"web/out directory could not be opened safely: {relative_path}",
                    ) from exc
                try:
                    child_stat = os.fstat(child_fd)
                    if not stat.S_ISDIR(child_stat.st_mode) or not _same_file(
                        entry_stat,
                        child_stat,
                    ):
                        raise DeployError(
                            f"web/out directory changed during validation: {relative_path}",
                        )
                    visit(child_fd, relative_path)
                finally:
                    os.close(child_fd)
                continue
            if not stat.S_ISREG(entry_stat.st_mode):
                raise DeployError(
                    f"web/out contains a non-regular file: {relative_path}",
                )
            if relative_path == RELEASE_MANIFEST_NAME:
                continue
            _content, evidence = _read_regular_file_at(
                directory_fd=directory_fd,
                name=entry.name,
                label=f"web/out file {relative_path}",
                expected_stat=entry_stat,
            )
            result[relative_path] = evidence

    visit(root_fd, "")
    return result


def _manifest_payload(manifest_bytes: bytes) -> dict[str, object]:
    try:
        decoded = manifest_bytes.decode("utf-8")
        payload = json.loads(decoded, object_pairs_hook=_unique_json_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeployError("web release manifest is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise DeployError("web release manifest root must be an object")
    if set(payload) != RELEASE_MANIFEST_FIELDS:
        raise DeployError("web release manifest fields do not match the required format")
    return payload


def _validate_manifest_metadata(
    *,
    payload: Mapping[str, object],
    config: DeployConfig,
) -> None:
    if payload["format"] != RELEASE_MANIFEST_FORMAT:
        raise DeployError("web release manifest format is invalid")
    source_sha = payload["source_sha"]
    if type(source_sha) is not str or re.fullmatch(r"[0-9a-f]{40}", source_sha) is None:
        raise DeployError("web release manifest source SHA is invalid")
    if source_sha != config.approved_sha:
        raise DeployError("web release manifest source SHA does not match approved SHA")
    for field in ("node_version", "pnpm_version"):
        value = payload[field]
        if type(value) is not str or not value:
            raise DeployError(f"web release manifest {field} is invalid")
    public_build_variables = payload["public_build_variables"]
    if (
        not isinstance(public_build_variables, dict)
        or set(public_build_variables) != set(PUBLIC_BUILD_VARIABLES)
        or any(
            type(key) is not str or (value is not None and type(value) is not str)
            for key, value in public_build_variables.items()
        )
    ):
        raise DeployError("web release manifest public_build_variables is invalid")


def _manifest_file_entries(payload: Mapping[str, object]) -> dict[str, _ReleaseFileEvidence]:
    raw_files = payload["files"]
    if not isinstance(raw_files, list):
        raise DeployError("web release manifest files must be a list")
    declared: dict[str, _ReleaseFileEvidence] = {}
    ordered_paths: list[str] = []
    for raw_entry in raw_files:
        if not isinstance(raw_entry, dict) or set(raw_entry) != {
            "path",
            "sha256",
            "size_bytes",
        }:
            raise DeployError("web release manifest files entry has invalid fields")
        path = _canonical_release_path(raw_entry["path"])
        if path in declared:
            raise DeployError(f"web release manifest contains duplicate path: {path}")
        size_bytes = raw_entry["size_bytes"]
        if type(size_bytes) is not int or size_bytes < 0:
            raise DeployError(
                "web release manifest file size_bytes must be a non-negative integer",
            )
        sha256 = raw_entry["sha256"]
        if type(sha256) is not str or SHA256_PATTERN.fullmatch(sha256) is None:
            raise DeployError(
                "web release manifest file sha256 must be lowercase hexadecimal",
            )
        declared[path] = _ReleaseFileEvidence(
            size_bytes=size_bytes,
            sha256=sha256,
        )
        ordered_paths.append(path)
    if ordered_paths != sorted(ordered_paths, key=lambda value: value.encode("utf-8")):
        raise DeployError("web release manifest files must be sorted by path")
    return declared


def _validate_web_release(config: DeployConfig) -> ReleaseEvidence:
    web_out = config.repo_root / "web" / "out"
    root_fd, root_stat = _open_release_root(web_out)
    try:
        manifest_bytes, manifest_evidence = _read_regular_file_at(
            directory_fd=root_fd,
            name=RELEASE_MANIFEST_NAME,
            label="web release manifest",
            collect_content=True,
            max_bytes=MAX_RELEASE_MANIFEST_BYTES,
        )
        payload = _manifest_payload(manifest_bytes)
        _validate_manifest_metadata(payload=payload, config=config)

        lockfile_sha256 = payload["lockfile_sha256"]
        if (
            type(lockfile_sha256) is not str
            or SHA256_PATTERN.fullmatch(lockfile_sha256) is None
        ):
            raise DeployError("web release manifest lockfile SHA-256 is invalid")
        _lockfile_bytes, lockfile_evidence = _read_regular_file(
            config.repo_root / "pnpm-lock.yaml",
            label="pnpm lockfile",
        )
        if lockfile_sha256 != lockfile_evidence.sha256:
            raise DeployError(
                "web release manifest lockfile hash does not match pnpm-lock.yaml",
            )

        declared = _manifest_file_entries(payload)
        actual = _collect_release_files(root_fd)
        if set(declared) != set(actual):
            raise DeployError("web release manifest file set does not match web/out")
        for path in sorted(declared, key=lambda value: value.encode("utf-8")):
            expected = declared[path]
            observed = actual[path]
            if observed.size_bytes != expected.size_bytes:
                raise DeployError(f"web release manifest size mismatch: {path}")
            if observed.sha256 != expected.sha256:
                raise DeployError(f"web release manifest SHA-256 mismatch: {path}")

        final_manifest_bytes, final_manifest_evidence = _read_regular_file_at(
            directory_fd=root_fd,
            name=RELEASE_MANIFEST_NAME,
            label="web release manifest",
            collect_content=True,
            max_bytes=MAX_RELEASE_MANIFEST_BYTES,
        )
        if (
            final_manifest_bytes != manifest_bytes
            or final_manifest_evidence != manifest_evidence
            or _collect_release_files(root_fd) != actual
        ):
            raise DeployError("web release files changed during release validation")
        _assert_release_root_unchanged(web_out, opened_stat=root_stat)

        static_assets = sorted(
            (path for path in declared if path.startswith("_next/static/")),
            key=lambda value: value.encode("utf-8"),
        )
        if not static_assets:
            raise DeployError("web release manifest must contain a _next/static asset")
        static_asset_path = static_assets[0]
        return ReleaseEvidence(
            manifest_sha256=manifest_evidence.sha256,
            manifest_file_count=len(declared),
            static_asset_path=static_asset_path,
            static_asset_sha256=declared[static_asset_path].sha256,
        )
    finally:
        os.close(root_fd)


def _create_remote_backups(config: DeployConfig, owner_token: str) -> None:
    backup_marker = f"/tmp/medical-audit-deploy-backups-{config.stamp}.complete"
    app_backup = f"/opt/medical-audit/backups/app/pre-deploy-{config.stamp}.tar.gz"
    env_backup = (
        f"/opt/medical-audit/backups/env/medical-audit.env.pre-deploy-{config.stamp}"
    )
    db_backup = f"/opt/medical-audit/backups/db/pre-deploy-{config.stamp}.sql.gz"
    nginx_backup = (
        f"/opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-{config.stamp}"
    )
    web_backup = (
        f"/opt/medical-audit/backups/web/audit-web-pre-deploy-{config.stamp}.tar.gz"
    )
    stale_backup_cleanup_script = f"""
set -euo pipefail
{_remote_lock_guard_script(config, owner_token)}
rm -f {shlex.quote(backup_marker)} \
  {shlex.quote(app_backup)} \
  {shlex.quote(env_backup)} \
  {shlex.quote(db_backup)} \
  {shlex.quote(nginx_backup)} \
  {shlex.quote(web_backup)}
"""
    script = f"""
set -euo pipefail
{_remote_lock_guard_script(config, owner_token)}
umask 077
worker_pid="$lock_dir/worker.pid"
worker_pid_next="$lock_dir/worker.pid.$BASHPID.next"
test ! -e "$worker_pid"
test ! -L "$worker_pid"
test ! -e "$worker_pid_next"
test ! -L "$worker_pid_next"
printf '%s\\n' "$BASHPID" > "$worker_pid_next"
mv -f -- "$worker_pid_next" "$worker_pid"
clear_worker_pid() {{
  if test "$(cat "$worker_pid" 2>/dev/null || true)" = "$BASHPID"; then
    rm -f -- "$worker_pid"
  fi
  rm -f -- "$worker_pid_next"
}}
trap clear_worker_pid EXIT
stamp={shlex.quote(config.stamp)}
backup_marker={shlex.quote(backup_marker)}
rm -f "$backup_marker"
mkdir -p /opt/medical-audit/backups/app \
  /opt/medical-audit/backups/env \
  /opt/medical-audit/backups/db \
  /opt/medical-audit/backups/nginx \
  /opt/medical-audit/backups/web \
  /opt/medical-audit/analytics-uploads \
  /opt/medical-audit/document-uploads
tar --exclude='.git' --exclude='.venv' --exclude='tmp' --exclude='data' \
  -czf /opt/medical-audit/backups/app/pre-deploy-${{stamp}}.tar.gz \
  -C /opt/medical-audit app
install -m 600 \
  {shlex.quote(config.remote_app_dir)}/configs/deploy/tencent-cloud/medical-audit.env \
  /opt/medical-audit/backups/env/medical-audit.env.pre-deploy-${{stamp}}
docker exec medical_audit_pg sh -lc 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | gzip > /opt/medical-audit/backups/db/pre-deploy-${{stamp}}.sql.gz
install -m 600 /opt/ai-video/deploy/lighthouse/nginx.conf \
  /opt/medical-audit/backups/nginx/nginx.conf.pre-deploy-${{stamp}}
tar --exclude='audit/releases' --exclude='audit/current' \
  -czf /opt/medical-audit/backups/web/audit-web-pre-deploy-${{stamp}}.tar.gz \
  -C /var/www audit
chmod 600 \
  /opt/medical-audit/backups/app/pre-deploy-${{stamp}}.tar.gz \
  /opt/medical-audit/backups/db/pre-deploy-${{stamp}}.sql.gz \
  /opt/medical-audit/backups/web/audit-web-pre-deploy-${{stamp}}.tar.gz
printf 'complete\\n' > "$backup_marker"
"""
    completion_check_script = f"""
set -euo pipefail
{_remote_lock_guard_script(config, owner_token)}
test ! -e "$lock_dir/worker.pid"
backup_marker={shlex.quote(backup_marker)}
verify_backup_file() {{
  path="$1"
  test -f "$path"
  test ! -L "$path"
  test -s "$path"
  test "$(stat -c '%a' "$path")" = 600
}}
verify_backup_file "$backup_marker"
verify_backup_file {shlex.quote(app_backup)}
verify_backup_file {shlex.quote(env_backup)}
verify_backup_file {shlex.quote(db_backup)}
verify_backup_file {shlex.quote(nginx_backup)}
verify_backup_file {shlex.quote(web_backup)}
"""
    _ssh(config, stale_backup_cleanup_script)
    _ssh_background_with_completion(
        config,
        script,
        timeout_seconds=REMOTE_BACKUP_TIMEOUT_SECONDS,
        completion_check_script=completion_check_script,
        timeout_description="remote backups",
        job_name=f"medical-audit-deploy-backups-{config.stamp}",
    )


def _sync_application(config: DeployConfig, owner_token: str) -> None:
    remote = f"{config.ssh_target}:{config.remote_app_dir}/"
    args = [
        "rsync",
        "-az",
        "--delete",
        "--itemize-changes",
        "--timeout",
        str(REMOTE_RSYNC_IO_TIMEOUT_SECONDS),
        "--rsync-path",
        _remote_rsync_path(config, owner_token),
        "-e",
        _ssh_transport(config),
    ]
    for pattern in APP_RSYNC_EXCLUDES:
        args.extend(["--exclude", pattern])
    args.extend([f"{config.repo_root}/", remote])
    _run(
        args,
        cwd=config.repo_root,
        timeout_seconds=REMOTE_RSYNC_TOTAL_TIMEOUT_SECONDS,
        remote_outcome_unknown=True,
    )


def _cleanup_remote_sync_artifacts(config: DeployConfig, owner_token: str) -> None:
    script = f"""
set -euo pipefail
{_remote_lock_guard_script(config, owner_token)}
git_file={shlex.quote(config.remote_app_dir)}/.git
if [ -f "$git_file" ]; then
  rm -f "$git_file"
fi
web_parent_dir={shlex.quote(config.remote_app_dir)}/web
web_out_dir={shlex.quote(config.remote_app_dir)}/web/out
test -d "$web_parent_dir"
if [ -e "$web_out_dir" ] || [ -L "$web_out_dir" ]; then
  if ! rm -rf "$web_out_dir"; then
    sudo -n rm -rf "$web_out_dir"
  fi
fi
if ! mkdir -p "$web_out_dir"; then
  sudo -n install -d -o "$(id -u)" -g "$(id -g)" "$web_out_dir"
fi
if [ ! -w "$web_out_dir" ]; then
  sudo -n chown -R "$(id -u):$(id -g)" "$web_out_dir"
fi
src_dir={shlex.quote(config.remote_app_dir)}/src
test -d "$src_dir"
find "$src_dir" -type f \\( \
  -name '*.pyc' -o \
  -name '*.pyo' -o \
  -name '*.uploading.cfg' \
\\) -print -delete
find "$src_dir" -type d -name __pycache__ -empty -print -delete
"""
    _ssh(config, script)


def _prepare_remote_release_incoming(
    config: DeployConfig,
    owner_token: str,
) -> None:
    release_root = f"{config.remote_web_dir}/releases"
    incoming = f"{release_root}/{config.approved_sha}.incoming"
    incoming_owner = f"{incoming}.owner"
    script = f"""
set -euo pipefail
{_remote_lock_guard_script(config, owner_token)}
release_root={shlex.quote(release_root)}
incoming={shlex.quote(incoming)}
incoming_owner={shlex.quote(incoming_owner)}
if [ -e "$release_root" ] || [ -L "$release_root" ]; then
  test -d "$release_root"
  test ! -L "$release_root"
else
  mkdir -- "$release_root"
fi
if [ -e "$incoming" ] || [ -L "$incoming" ] || \
   [ -e "$incoming_owner" ] || [ -L "$incoming_owner" ]; then
  echo "static release incoming path already exists" >&2
  exit 76
fi
mkdir -- "$incoming"
printf '%s\n' "$owner_token" > "$incoming_owner"
"""
    _ssh(config, script)


def _sync_static_frontend(config: DeployConfig, owner_token: str) -> None:
    web_out = config.repo_root / "web" / "out"
    if not web_out.is_dir():
        raise DeployError("web/out is missing after build")
    incoming = (
        f"{config.remote_web_dir}/releases/{config.approved_sha}.incoming/"
    )
    remote = f"{config.ssh_target}:{incoming}"
    _run(
        [
            "rsync",
            "-az",
            "--itemize-changes",
            "--timeout",
            str(REMOTE_RSYNC_IO_TIMEOUT_SECONDS),
            "--rsync-path",
            _remote_rsync_path(config, owner_token),
            "-e",
            _ssh_transport(config),
            f"{web_out}/",
            remote,
        ],
        cwd=config.repo_root,
        timeout_seconds=REMOTE_RSYNC_TOTAL_TIMEOUT_SECONDS,
        remote_outcome_unknown=True,
    )


def _verify_and_promote_remote_release(
    config: DeployConfig,
    owner_token: str,
    evidence: ReleaseEvidence,
) -> None:
    release_root = f"{config.remote_web_dir}/releases"
    incoming = f"{release_root}/{config.approved_sha}.incoming"
    incoming_owner = f"{incoming}.owner"
    release = f"{release_root}/{config.approved_sha}"
    verifier = _remote_release_verifier_code()
    verify_args = " ".join(
        shlex.quote(value)
        for value in (
            config.approved_sha,
            evidence.manifest_sha256,
            str(evidence.manifest_file_count),
            evidence.static_asset_path,
            evidence.static_asset_sha256,
        )
    )
    script = f"""
set -euo pipefail
{_remote_lock_guard_script(config, owner_token)}
incoming={shlex.quote(incoming)}
incoming_owner={shlex.quote(incoming_owner)}
release={shlex.quote(release)}
test -d "$incoming"
test ! -L "$incoming"
test "$(cat "$incoming_owner" 2>/dev/null || true)" = "$owner_token"
cleanup_owned_incoming() {{
  if [ "$(cat "$incoming_owner" 2>/dev/null || true)" = "$owner_token" ]; then
    rm -rf -- "$incoming"
    rm -f -- "$incoming_owner"
  fi
}}
trap cleanup_owned_incoming EXIT
python3 - "$incoming" {verify_args} <<'MEDICAL_AUDIT_RELEASE_VERIFY'
{verifier}
MEDICAL_AUDIT_RELEASE_VERIFY
if [ -e "$release" ] || [ -L "$release" ]; then
  test -d "$release"
  test ! -L "$release"
  python3 - "$release" {verify_args} <<'MEDICAL_AUDIT_RELEASE_VERIFY'
{verifier}
MEDICAL_AUDIT_RELEASE_VERIFY
  cmp -s "$incoming/{RELEASE_MANIFEST_NAME}" "$release/{RELEASE_MANIFEST_NAME}"
  cleanup_owned_incoming
else
  mv -T -- "$incoming" "$release"
  rm -f -- "$incoming_owner"
fi
trap - EXIT
"""
    _ssh(config, script)


def _activate_remote_release(config: DeployConfig, owner_token: str) -> None:
    safe_stamp = _safe_remote_job_name(config.stamp)
    release_root = f"{config.remote_web_dir}/releases"
    release = f"{release_root}/{config.approved_sha}"
    current = f"{config.remote_web_dir}/current"
    current_next = f"{config.remote_web_dir}/current.next"
    migration_sentinel = (
        f"{config.remote_web_dir}/.versioned-release-migration-complete"
    )
    next_migration_sentinel = f"{migration_sentinel}.next"
    transaction_dir = f"{REMOTE_TRANSACTION_ROOT}/{safe_stamp}"
    nginx_backup = f"{transaction_dir}/nginx.conf.before"
    candidate = f"/tmp/medical-audit-nginx-{safe_stamp}.candidate"
    container_candidate = f"/tmp/medical-audit-nginx-{safe_stamp}.candidate"
    fragment = (
        f"{config.remote_app_dir}/configs/deploy/tencent-cloud/"
        "nginx-audit-server.conf"
    )
    deploy_script = (
        f"{config.remote_app_dir}/scripts/deploy-tencent-cloud-production.py"
    )
    script = f"""
set -Eeuo pipefail
{_remote_lock_guard_script(config, owner_token)}
release_root={shlex.quote(release_root)}
release={shlex.quote(release)}
current={shlex.quote(current)}
current_next={shlex.quote(current_next)}
transaction_dir={shlex.quote(transaction_dir)}
nginx_config={shlex.quote(REMOTE_NGINX_CONFIG)}
nginx_backup={shlex.quote(nginx_backup)}
candidate={shlex.quote(candidate)}
container_candidate={shlex.quote(container_candidate)}
fragment={shlex.quote(fragment)}
deploy_script={shlex.quote(deploy_script)}
approved_sha={shlex.quote(config.approved_sha)}
allow_first_legacy_migration={1 if config.allow_first_legacy_migration else 0}
migration_sentinel={shlex.quote(migration_sentinel)}
next_migration_sentinel={shlex.quote(next_migration_sentinel)}
remote_web_dir={shlex.quote(config.remote_web_dir)}
legacy_marker={shlex.quote(config.remote_app_dir)}/.deploy-sha
test -d "$release"
test ! -L "$release"
test -f "$nginx_config"
test ! -L "$nginx_config"
previous_current=LEGACY_NONE
if [ -L "$current" ]; then
  previous_current="$(readlink "$current")"
  if [[ ! "$previous_current" =~ ^releases/[0-9a-f]{{40}}$ ]]; then
    echo "current release target is invalid" >&2
    exit 77
  fi
  previous_sha="${{previous_current#releases/}}"
  test -d "$release_root/$previous_sha"
  test ! -L "$release_root/$previous_sha"
  test -f "$migration_sentinel"
  test ! -L "$migration_sentinel"
  test ! -e "$next_migration_sentinel"
  test ! -L "$next_migration_sentinel"
  migration_sha="$(cat "$migration_sentinel")"
  [[ "$migration_sha" =~ ^[0-9a-f]{{40}}$ ]]
elif [ -e "$current" ]; then
  echo "current release path is not a symlink" >&2
  exit 77
else
  if [ "$allow_first_legacy_migration" -ne 1 ]; then
    echo "legacy migration authorization required" >&2
    exit 77
  fi
  test ! -e "$migration_sentinel"
  test ! -L "$migration_sentinel"
  test ! -e "$next_migration_sentinel"
  test ! -L "$next_migration_sentinel"
  test -f {shlex.quote(config.remote_web_dir)}/index.html
  test ! -L {shlex.quote(config.remote_web_dir)}/index.html
  test -f "$legacy_marker"
  test ! -L "$legacy_marker"
  legacy_sha="$(cat "$legacy_marker")"
  if [[ ! "$legacy_sha" =~ ^[0-9a-f]{{40}}$ ]]; then
    echo "legacy deploy marker is invalid" >&2
    exit 77
  fi
fi
test ! -e "$current_next"
test ! -L "$current_next"
test ! -e "$candidate"
test ! -L "$candidate"
if ! docker exec ai_video_nginx sh -c 'test ! -e "$1"' sh \
  "$container_candidate" >/dev/null 2>&1; then
  echo "candidate cleanup precondition failed" >&2
  exit 85
fi
host_candidate_owned=1
container_candidate_owned=0
cleanup_sensitive_candidates() {{
  cleanup_status=0
  if [ "$host_candidate_owned" -eq 1 ]; then
    if ! rm -f -- "$candidate"; then
      cleanup_status=1
    fi
  fi
  if [ "$container_candidate_owned" -eq 1 ]; then
    if ! docker exec ai_video_nginx rm -f "$container_candidate" \
      >/dev/null 2>&1; then
      cleanup_status=1
    fi
  fi
  return "$cleanup_status"
}}
cleanup_sensitive_candidates_on_exit() {{
  original_status="$?"
  trap - EXIT
  if ! cleanup_sensitive_candidates; then
    echo "sensitive candidate cleanup failed" >&2
    exit 85
  fi
  exit "$original_status"
}}
trap cleanup_sensitive_candidates_on_exit EXIT
umask 077
mkdir -p {shlex.quote(REMOTE_TRANSACTION_ROOT)}
mkdir -- "$transaction_dir"
cp -p -- "$nginx_config" "$nginx_backup"
chmod 600 "$nginx_backup"
python3 - "$nginx_config" "$fragment" "$candidate" "$deploy_script" <<'MEDICAL_AUDIT_NGINX_PATCH'
import os
import runpy
import stat
import sys
from pathlib import Path

source = Path(sys.argv[1])
fragment = Path(sys.argv[2])
candidate = Path(sys.argv[3])
namespace = runpy.run_path(sys.argv[4])
for path in (source, fragment):
    observed = path.lstat()
    if stat.S_ISLNK(observed.st_mode) or not stat.S_ISREG(observed.st_mode):
        raise SystemExit("nginx patch input must be regular")
content = namespace["_patch_nginx_audit_locations"](
    source.read_bytes(),
    fragment.read_bytes(),
)
descriptor = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
try:
    offset = 0
    while offset < len(content):
        offset += os.write(descriptor, content[offset:])
    os.fsync(descriptor)
finally:
    os.close(descriptor)
MEDICAL_AUDIT_NGINX_PATCH
container_candidate_owned=1
docker cp "$candidate" "ai_video_nginx:$container_candidate" >/dev/null 2>&1
if ! docker exec ai_video_nginx nginx -t -c "$container_candidate" \
  >/dev/null 2>&1; then
  echo "candidate nginx configuration test failed" >&2
  exit 78
fi
printf '%s\n' "$approved_sha" > "$transaction_dir/approved-sha"
printf '%s\n' "$previous_current" > "$transaction_dir/previous-current"
printf 'prepared\n' > "$transaction_dir/status"
activation_started=0
overwrite_nginx_in_place() {{
  destination="$1"
  source_file="$2"
  python3 - "$destination" "$source_file" "$deploy_script" <<'MEDICAL_AUDIT_NGINX_OVERWRITE'
import runpy
import sys
from pathlib import Path

namespace = runpy.run_path(sys.argv[3])
namespace["_overwrite_regular_file_in_place"](Path(sys.argv[1]), Path(sys.argv[2]))
MEDICAL_AUDIT_NGINX_OVERWRITE
}}
restore_activation() {{
  restore_status=0
  if [ -e "$current_next" ] || [ -L "$current_next" ]; then
    rm -f -- "$current_next" || restore_status=1
  fi
  if [ -e "$current_next" ] || [ -L "$current_next" ]; then
    restore_status=1
  fi
  if [ "$activation_started" -eq 1 ]; then
    if [ "$previous_current" = LEGACY_NONE ]; then
      rm -f -- "$current" || restore_status=1
      if [ -e "$current" ] || [ -L "$current" ]; then
        restore_status=1
      fi
      if [ -e "$migration_sentinel" ] || [ -L "$migration_sentinel" ]; then
        rm -f -- "$migration_sentinel" || restore_status=1
      fi
      if [ -e "$next_migration_sentinel" ] || \
         [ -L "$next_migration_sentinel" ]; then
        rm -f -- "$next_migration_sentinel" || restore_status=1
      fi
      if [ -e "$migration_sentinel" ] || [ -L "$migration_sentinel" ] || \
         [ -e "$next_migration_sentinel" ] || \
         [ -L "$next_migration_sentinel" ]; then
        restore_status=1
      fi
    else
      restore_link="$current.restore"
      rm -f -- "$restore_link"
      ln -s "$previous_current" "$restore_link" || restore_status=1
      mv -Tf -- "$restore_link" "$current" || restore_status=1
    fi
    overwrite_nginx_in_place "$nginx_config" "$nginx_backup" || restore_status=1
    docker exec ai_video_nginx nginx -t >/dev/null 2>&1 || restore_status=1
    docker exec ai_video_nginx nginx -s reload >/dev/null 2>&1 || restore_status=1
  fi
  if [ "$restore_status" -eq 0 ]; then
    printf 'restored\n' > "$transaction_dir/status"
    return 0
  fi
  printf 'restore-failed\n' > "$transaction_dir/status"
  return 1
}}
on_activation_error() {{
  original_status="$?"
  trap - ERR
  set +e
  if restore_activation; then
    exit "$original_status"
  fi
  echo "activation restore failed; production lock must be retained" >&2
  exit 79
}}
trap on_activation_error ERR
activation_started=1
ln -s "releases/$approved_sha" "$current_next"
mv -Tf -- "$current_next" "$current"
overwrite_nginx_in_place "$nginx_config" "$candidate"
if ! docker exec ai_video_nginx nginx -t >/dev/null 2>&1; then
  false
fi
if ! docker exec ai_video_nginx nginx -s reload >/dev/null 2>&1; then
  false
fi
if [ "$previous_current" = LEGACY_NONE ]; then
  printf '%s\n' "$approved_sha" > "$next_migration_sentinel"
  python3 - "$next_migration_sentinel" <<'MEDICAL_AUDIT_MIGRATION_FSYNC'
import os
import sys

descriptor = os.open(sys.argv[1], os.O_RDONLY | os.O_NOFOLLOW)
try:
    os.fsync(descriptor)
finally:
    os.close(descriptor)
MEDICAL_AUDIT_MIGRATION_FSYNC
  mv -Tf -- "$next_migration_sentinel" "$migration_sentinel"
  python3 - "$remote_web_dir" <<'MEDICAL_AUDIT_MIGRATION_DIR_FSYNC'
import os
import sys

descriptor = os.open(sys.argv[1], os.O_RDONLY | os.O_DIRECTORY)
try:
    os.fsync(descriptor)
finally:
    os.close(descriptor)
MEDICAL_AUDIT_MIGRATION_DIR_FSYNC
  test -f "$migration_sentinel"
  test ! -L "$migration_sentinel"
  test "$(cat "$migration_sentinel")" = "$approved_sha"
fi
printf 'active\n' > "$transaction_dir/status"
trap - ERR
"""
    try:
        _ssh(config, script)
    except subprocess.CalledProcessError as exc:
        if exc.returncode in {79, 85}:
            raise RemoteOutcomeUnknownError(
                "activation restore outcome is unknown",
            ) from exc
        raise


def _restore_remote_activation(config: DeployConfig, owner_token: str) -> None:
    safe_stamp = _safe_remote_job_name(config.stamp)
    transaction_dir = f"{REMOTE_TRANSACTION_ROOT}/{safe_stamp}"
    current = f"{config.remote_web_dir}/current"
    current_next = f"{config.remote_web_dir}/current.next"
    migration_sentinel = (
        f"{config.remote_web_dir}/.versioned-release-migration-complete"
    )
    next_migration_sentinel = f"{migration_sentinel}.next"
    nginx_backup = f"{transaction_dir}/nginx.conf.before"
    container_candidate = f"/tmp/medical-audit-nginx-restore-{safe_stamp}.candidate"
    deploy_script = (
        f"{config.remote_app_dir}/scripts/deploy-tencent-cloud-production.py"
    )
    script = f"""
set -Eeuo pipefail
{_remote_lock_guard_script(config, owner_token)}
transaction_dir={shlex.quote(transaction_dir)}
current={shlex.quote(current)}
current_next={shlex.quote(current_next)}
migration_sentinel={shlex.quote(migration_sentinel)}
next_migration_sentinel={shlex.quote(next_migration_sentinel)}
nginx_config={shlex.quote(REMOTE_NGINX_CONFIG)}
nginx_backup={shlex.quote(nginx_backup)}
container_candidate={shlex.quote(container_candidate)}
deploy_script={shlex.quote(deploy_script)}
approved_sha={shlex.quote(config.approved_sha)}
test -d "$transaction_dir"
test "$(cat "$transaction_dir/approved-sha")" = "$approved_sha"
status="$(cat "$transaction_dir/status")"
rm -f -- "$current_next"
test ! -e "$current_next"
test ! -L "$current_next"
case "$status" in
  prepared|active|restore-failed|restored) ;;
  *) echo "recorded activation status is invalid" >&2; exit 81 ;;
esac
previous_current="$(cat "$transaction_dir/previous-current")"
if [ "$previous_current" != LEGACY_NONE ] && \
   [[ ! "$previous_current" =~ ^releases/[0-9a-f]{{40}}$ ]]; then
  echo "recorded previous current target is invalid" >&2
  exit 81
fi
if [ "$status" = restored ]; then
  current_target="$(readlink "$current" 2>/dev/null || true)"
  if [ "$previous_current" = LEGACY_NONE ]; then
    test ! -e "$current"
    test ! -L "$current"
    test ! -e "$migration_sentinel"
    test ! -L "$migration_sentinel"
    test ! -e "$next_migration_sentinel"
    test ! -L "$next_migration_sentinel"
  else
    test -L "$current"
    test "$current_target" = "$previous_current"
    test -f "$migration_sentinel"
    test ! -L "$migration_sentinel"
    test ! -e "$next_migration_sentinel"
    test ! -L "$next_migration_sentinel"
    migration_sha="$(cat "$migration_sentinel")"
    [[ "$migration_sha" =~ ^[0-9a-f]{{40}}$ ]]
  fi
  exit 0
fi
test -f "$nginx_backup"
test ! -L "$nginx_backup"
test -f "$nginx_config"
test ! -L "$nginx_config"
mark_restore_failed() {{
  trap - ERR
  printf 'restore-failed\n' > "$transaction_dir/status"
}}
trap mark_restore_failed ERR
if ! docker exec ai_video_nginx sh -c 'test ! -e "$1"' sh \
  "$container_candidate" >/dev/null 2>&1; then
  echo "restore candidate cleanup precondition failed" >&2
  exit 85
fi
container_candidate_owned=1
cleanup_restore_candidate_on_exit() {{
  original_status="$?"
  trap - EXIT
  if [ "$container_candidate_owned" -eq 1 ] && \
     ! docker exec ai_video_nginx rm -f "$container_candidate" \
       >/dev/null 2>&1; then
    printf 'restore-failed\n' > "$transaction_dir/status"
    echo "sensitive restore candidate cleanup failed" >&2
    exit 85
  fi
  exit "$original_status"
}}
trap cleanup_restore_candidate_on_exit EXIT
docker cp "$nginx_backup" "ai_video_nginx:$container_candidate" >/dev/null 2>&1
if ! docker exec ai_video_nginx nginx -t -c "$container_candidate" \
  >/dev/null 2>&1; then
  echo "recorded nginx backup failed candidate validation" >&2
  exit 81
fi
current_target="$(readlink "$current" 2>/dev/null || true)"
if [ "$current_target" = "releases/$approved_sha" ]; then
  if [ "$previous_current" = LEGACY_NONE ]; then
    rm -f -- "$current"
  else
    restore_link="$current.restore"
    test ! -e "$restore_link"
    test ! -L "$restore_link"
    ln -s "$previous_current" "$restore_link"
    mv -Tf -- "$restore_link" "$current"
  fi
elif [ "$previous_current" = LEGACY_NONE ]; then
  test ! -e "$current"
  test ! -L "$current"
else
  test "$current_target" = "$previous_current"
fi
if [ "$previous_current" = LEGACY_NONE ]; then
  rm -f -- "$next_migration_sentinel"
  rm -f -- "$migration_sentinel"
  test ! -e "$current"
  test ! -L "$current"
  test ! -e "$migration_sentinel"
  test ! -L "$migration_sentinel"
  test ! -e "$next_migration_sentinel"
  test ! -L "$next_migration_sentinel"
else
  test -L "$current"
  test "$(readlink "$current")" = "$previous_current"
  test -f "$migration_sentinel"
  test ! -L "$migration_sentinel"
  test ! -e "$next_migration_sentinel"
  test ! -L "$next_migration_sentinel"
  migration_sha="$(cat "$migration_sentinel")"
  [[ "$migration_sha" =~ ^[0-9a-f]{{40}}$ ]]
fi
python3 - "$nginx_config" "$nginx_backup" "$deploy_script" <<'MEDICAL_AUDIT_NGINX_RESTORE'
import runpy
import sys
from pathlib import Path

namespace = runpy.run_path(sys.argv[3])
namespace["_overwrite_regular_file_in_place"](Path(sys.argv[1]), Path(sys.argv[2]))
MEDICAL_AUDIT_NGINX_RESTORE
if ! docker exec ai_video_nginx nginx -t >/dev/null 2>&1; then
  false
fi
if ! docker exec ai_video_nginx nginx -s reload >/dev/null 2>&1; then
  false
fi
printf 'restored\n' > "$transaction_dir/status"
trap - ERR
"""
    _ssh(config, script)


def _apply_schema(config: DeployConfig, owner_token: str) -> None:
    psql_command = 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1'
    script = f"""
set -euo pipefail
{_remote_lock_guard_script(config, owner_token)}
docker exec -i medical_audit_pg sh -lc {shlex.quote(psql_command)} \
  < {shlex.quote(config.remote_app_dir)}/sql/knowledge-query-schema.sql
"""
    _ssh(config, script)


def _write_remote_deploy_sha(config: DeployConfig, owner_token: str) -> None:
    sha = config.approved_sha
    marker = f"{config.remote_app_dir}/.deploy-sha"
    next_marker = f"{marker}.next"
    safe_stamp = _safe_remote_job_name(config.stamp)
    transaction_dir = f"{REMOTE_TRANSACTION_ROOT}/{safe_stamp}"
    migration_sentinel = (
        f"{config.remote_web_dir}/.versioned-release-migration-complete"
    )
    script = f"""
set -euo pipefail
{_remote_lock_guard_script(config, owner_token)}
marker={shlex.quote(marker)}
next_marker={shlex.quote(next_marker)}
approved_sha={shlex.quote(sha)}
transaction_dir={shlex.quote(transaction_dir)}
migration_sentinel={shlex.quote(migration_sentinel)}
test -d "$transaction_dir"
test "$(cat "$transaction_dir/approved-sha")" = "$approved_sha"
previous_current="$(cat "$transaction_dir/previous-current")"
if [ "$previous_current" != LEGACY_NONE ] && \
   [[ ! "$previous_current" =~ ^releases/[0-9a-f]{{40}}$ ]]; then
  echo "recorded previous current target is invalid" >&2
  exit 81
fi
test ! -e "$next_marker"
test ! -L "$next_marker"
test -f "$migration_sentinel"
test ! -L "$migration_sentinel"
migration_sha="$(cat "$migration_sentinel")"
if [ "$previous_current" = LEGACY_NONE ]; then
  test "$migration_sha" = "$approved_sha"
elif [[ ! "$migration_sha" =~ ^[0-9a-f]{{40}}$ ]]; then
  echo "migration sentinel is invalid" >&2
  exit 81
fi
printf '%s\\n' "$approved_sha" > "$next_marker"
python3 - "$next_marker" <<'MEDICAL_AUDIT_MARKER_FSYNC'
import os
import sys

descriptor = os.open(sys.argv[1], os.O_RDONLY | os.O_NOFOLLOW)
try:
    os.fsync(descriptor)
finally:
    os.close(descriptor)
MEDICAL_AUDIT_MARKER_FSYNC
mv -Tf -- "$next_marker" "$marker"
python3 - {shlex.quote(config.remote_app_dir)} <<'MEDICAL_AUDIT_MARKER_DIR_FSYNC'
import os
import sys

descriptor = os.open(sys.argv[1], os.O_RDONLY | os.O_DIRECTORY)
try:
    os.fsync(descriptor)
finally:
    os.close(descriptor)
MEDICAL_AUDIT_MARKER_DIR_FSYNC
test "$(cat "$marker")" = "$approved_sha"
"""
    _ssh(config, script)


def _rebuild_application(config: DeployConfig, owner_token: str) -> None:
    if config.skip_app_rebuild:
        print("skip app rebuild", flush=True)
        return
    sha = config.approved_sha
    container_id_format = "{{.Id}}"
    health_format = "{{.State.Health.Status}}"
    script = f"""
set -euo pipefail
{_remote_lock_guard_script(config, owner_token)}
export MEDICAL_AUDIT_DEPLOY_SHA={shlex.quote(sha)}
cd {shlex.quote(config.remote_app_dir)}
postgres_id_before="$(docker inspect medical_audit_pg \
  --format {shlex.quote(container_id_format)})"
test -n "$postgres_id_before"
clamav_service_present=0
clamav_id_before=""
if docker compose -f configs/deploy/tencent-cloud/docker-compose.prod.yaml \
  --env-file configs/deploy/tencent-cloud/medical-audit.env config --services \
  | grep -Fx clamav >/dev/null; then
  clamav_service_present=1
  clamav_id_before="$(docker inspect medical_audit_clamav \
    --format {shlex.quote(container_id_format)})"
  test -n "$clamav_id_before"
  test "$(docker inspect medical_audit_clamav \
    --format {shlex.quote(health_format)})" = "healthy"
fi
docker compose -f configs/deploy/tencent-cloud/docker-compose.prod.yaml \
  --env-file configs/deploy/tencent-cloud/medical-audit.env build app
docker compose -f configs/deploy/tencent-cloud/docker-compose.prod.yaml \
  --env-file configs/deploy/tencent-cloud/medical-audit.env up -d --no-deps app
test "$(docker inspect medical_audit_pg \
  --format {shlex.quote(container_id_format)})" = "$postgres_id_before"
if [ "$clamav_service_present" -eq 1 ]; then
  test "$(docker inspect medical_audit_clamav \
    --format {shlex.quote(container_id_format)})" = "$clamav_id_before"
fi
"""
    _ssh(config, script)
def _run_remote_post_checks(config: DeployConfig) -> None:
    health_format = "{{.State.Health.Status}}"
    script = f"""
set -euo pipefail
cd {shlex.quote(config.remote_app_dir)}
for attempt in $(seq 1 60); do
  app_health="$(docker inspect medical_audit_app \
    --format {shlex.quote(health_format)} 2>/dev/null || true)"
  if [ "$app_health" = "healthy" ]; then
    break
  fi
  sleep 2
done
test "$(docker inspect medical_audit_app \
  --format {shlex.quote(health_format)})" = "healthy"
if docker compose -f configs/deploy/tencent-cloud/docker-compose.prod.yaml \
  --env-file configs/deploy/tencent-cloud/medical-audit.env config --services \
  | grep -Fx clamav >/dev/null; then
  for attempt in $(seq 1 60); do
    clamav_health="$(docker inspect medical_audit_clamav \
      --format {shlex.quote(health_format)} 2>/dev/null || true)"
    if [ "$clamav_health" = "healthy" ]; then
      break
    fi
    sleep 2
  done
  test "$(docker inspect medical_audit_clamav \
    --format {shlex.quote(health_format)})" = "healthy"
fi
docker compose -f configs/deploy/tencent-cloud/docker-compose.prod.yaml \
  --env-file configs/deploy/tencent-cloud/medical-audit.env ps
if ! docker exec ai_video_nginx nginx -t >/dev/null 2>&1; then
  echo "production nginx configuration test failed" >&2
  exit 80
fi
curl -fsS http://127.0.0.1:18080/health >/dev/null
auth_headers=(
  -H 'X-User-Id: deploy-smoke-admin'
  -H 'X-Role: it-admin'
  -H 'X-Project-Key: SELF-CHECK-FUND-20260607'
  -H 'X-Tenant-Id: hospital-demo'
)
curl -fsS "${{auth_headers[@]}}" \
  http://127.0.0.1:18080/knowledge-base/catalog >/dev/null
curl -fsS "${{auth_headers[@]}}" \
  {shlex.quote(config.base_url)}/api/v1/knowledge-base/catalog >/dev/null
curl -fsS {shlex.quote(config.base_url)}/api/v1/health >/dev/null
curl -fsS "${{auth_headers[@]}}" {shlex.quote(config.base_url)}/documents >/dev/null
"""
    _ssh(config, script)


def _verify_remote_release_commit_point(
    config: DeployConfig,
    owner_token: str,
    evidence: ReleaseEvidence,
) -> None:
    release = f"{config.remote_web_dir}/releases/{config.approved_sha}"
    current = f"{config.remote_web_dir}/current"
    release_verifier = _remote_release_verifier_code()
    public_verifier = _public_release_verifier_code()
    health_format = "{{.State.Health.Status}}"
    script = f"""
set -euo pipefail
{_remote_lock_guard_script(config, owner_token)}
release={shlex.quote(release)}
current={shlex.quote(current)}
approved_sha={shlex.quote(config.approved_sha)}
test -L "$current"
test "$(readlink "$current")" = "releases/$approved_sha"
test -d "$release"
test ! -L "$release"
python3 - "$release" \
  {shlex.quote(config.approved_sha)} \
  {shlex.quote(evidence.manifest_sha256)} \
  {shlex.quote(str(evidence.manifest_file_count))} \
  {shlex.quote(evidence.static_asset_path)} \
  {shlex.quote(evidence.static_asset_sha256)} <<'MEDICAL_AUDIT_RELEASE_VERIFY'
{release_verifier}
MEDICAL_AUDIT_RELEASE_VERIFY
python3 - \
  {shlex.quote(config.base_url)} \
  {shlex.quote(evidence.static_asset_path)} \
  {shlex.quote(evidence.manifest_sha256)} \
  {shlex.quote(evidence.static_asset_sha256)} <<'MEDICAL_AUDIT_PUBLIC_VERIFY'
{public_verifier}
MEDICAL_AUDIT_PUBLIC_VERIFY
test "$(docker inspect medical_audit_app \
  --format {shlex.quote(health_format)})" = "healthy"
if ! docker exec ai_video_nginx nginx -t >/dev/null 2>&1; then
  echo "official nginx configuration test failed" >&2
  exit 80
fi
"""
    _ssh(config, script)


def _run_production_smoke(config: DeployConfig) -> None:
    if config.skip_smoke:
        raise DeployError("production execute forbids --skip-smoke")
    config.report_path.parent.mkdir(parents=True, exist_ok=True)
    args = [
        sys.executable,
        str(config.repo_root / "scripts/run-production-e2e-smoke.py"),
        "--base-url",
        config.base_url,
        "--report",
        str(config.report_path),
    ]
    if config.include_query_provider_smoke:
        args.extend(
            [
                "--include-query-provider-smoke",
                "--confirm-production-write",
                config.confirm_production_write,
            ],
        )
    if config.include_review_write:
        args.append("--include-review-write")
    _run(args, cwd=config.repo_root)


def _run_remote_rollback(config: DeployConfig, owner_token: str) -> None:
    app_backup = f"/opt/medical-audit/backups/app/pre-deploy-{config.stamp}.tar.gz"
    web_backup = f"/opt/medical-audit/backups/web/audit-web-pre-deploy-{config.stamp}.tar.gz"
    safe_stamp = _safe_remote_job_name(config.stamp)
    transaction_dir = f"{REMOTE_TRANSACTION_ROOT}/{safe_stamp}"
    rollback_transaction_dir = f"{REMOTE_TRANSACTION_ROOT}/rollback-{safe_stamp}"
    nginx_backup = f"{transaction_dir}/nginx.conf.before"
    container_candidate = f"/tmp/medical-audit-nginx-rollback-{safe_stamp}.candidate"
    release_verifier = _remote_release_verifier_code()
    public_verifier = _public_release_verifier_code()
    container_id_format = "{{.Id}}"
    health_format = "{{.State.Health.Status}}"
    script = f"""
set -Eeuo pipefail
{_remote_lock_guard_script(config, owner_token)}
remote_app_dir={shlex.quote(config.remote_app_dir)}
remote_web_dir={shlex.quote(config.remote_web_dir)}
app_backup={shlex.quote(app_backup)}
web_backup={shlex.quote(web_backup)}
transaction_dir={shlex.quote(transaction_dir)}
rollback_transaction_dir={shlex.quote(rollback_transaction_dir)}
nginx_config={shlex.quote(REMOTE_NGINX_CONFIG)}
nginx_backup={shlex.quote(nginx_backup)}
container_candidate={shlex.quote(container_candidate)}
base_url={shlex.quote(config.base_url)}
expected_current_sha={shlex.quote(config.expected_current_sha)}
restore_sha={shlex.quote(config.restore_sha)}
release="$remote_web_dir/releases/$restore_sha"
incoming="$remote_web_dir/releases/$restore_sha.incoming"
incoming_owner="$incoming.owner"
current="$remote_web_dir/current"
current_next="$remote_web_dir/current.next"
marker="$remote_app_dir/.deploy-sha"
next_marker="$remote_app_dir/.deploy-sha.next"
migration_sentinel="$remote_web_dir/.versioned-release-migration-complete"
next_migration_sentinel="$migration_sentinel.next"
test -s "$app_backup"
test -s "$web_backup"
test -s "$marker"
test "$(cat "$remote_app_dir/.deploy-sha")" = "$expected_current_sha"
test -d "$transaction_dir"
test "$(cat "$transaction_dir/approved-sha")" = "$expected_current_sha"
previous_current="$(cat "$transaction_dir/previous-current")"
if [ "$previous_current" != LEGACY_NONE ] && \
   [ "$previous_current" != "releases/$restore_sha" ]; then
  echo "rollback transaction does not identify requested release" >&2
  exit 82
fi
current_target="$(readlink "$current" 2>/dev/null || true)"
test "$current_target" = "releases/$expected_current_sha"
test -d "$remote_web_dir/releases/$expected_current_sha"
test ! -L "$remote_web_dir/releases/$expected_current_sha"
test ! -e "$current_next"
test ! -L "$current_next"
test ! -e "$next_marker"
test ! -L "$next_marker"
test ! -e "$next_migration_sentinel"
test ! -L "$next_migration_sentinel"
test -f "$migration_sentinel"
test ! -L "$migration_sentinel"
migration_sha="$(cat "$migration_sentinel")"
[[ "$migration_sha" =~ ^[0-9a-f]{{40}}$ ]]
test -f "$nginx_config"
test ! -L "$nginx_config"
test -f "$nginx_backup"
test ! -L "$nginx_backup"
tar -tzf "$app_backup" >/dev/null
tar -tzf "$web_backup" >/dev/null
restore_root="$(mktemp -d /opt/medical-audit/rollback-{safe_stamp}.XXXXXX)"
preserved_env="$(mktemp)"
if ! docker exec ai_video_nginx sh -c 'test ! -e "$1"' sh \
  "$container_candidate" >/dev/null 2>&1; then
  echo "rollback candidate cleanup precondition failed" >&2
  exit 85
fi
container_candidate_owned=1
cleanup_rollback() {{
  original_status="$?"
  trap - EXIT
  cleanup_status=0
  if [ "$container_candidate_owned" -eq 1 ] && \
     ! docker exec ai_video_nginx rm -f "$container_candidate" \
       >/dev/null 2>&1; then
    cleanup_status=1
  fi
  if [ "$(cat "$incoming_owner" 2>/dev/null || true)" = "$owner_token" ]; then
    rm -rf -- "$incoming" || cleanup_status=1
    rm -f -- "$incoming_owner" || cleanup_status=1
  fi
  rm -rf -- "$restore_root" || cleanup_status=1
  rm -f -- "$preserved_env" || cleanup_status=1
  if [ "$cleanup_status" -ne 0 ]; then
    echo "rollback cleanup failed" >&2
    exit 85
  fi
  exit "$original_status"
}}
trap cleanup_rollback EXIT
cp "$remote_app_dir/configs/deploy/tencent-cloud/medical-audit.env" "$preserved_env"
tar -xzf "$app_backup" -C "$restore_root"
tar -xzf "$web_backup" -C "$restore_root"
test -d "$restore_root/app"
test -d "$restore_root/audit"
test -s "$restore_root/app/.deploy-sha"
test "$(cat "$restore_root/app/.deploy-sha")" = "$restore_sha"
legacy_mode=0
if [ -f "$restore_root/app/web/out/release-manifest.json" ]; then
  python3 - "$restore_root/app/web/out" "$restore_sha" - -1 - - \
    <<'MEDICAL_AUDIT_RELEASE_VERIFY'
{release_verifier}
MEDICAL_AUDIT_RELEASE_VERIFY
  if [ -e "$release" ] || [ -L "$release" ]; then
    test -d "$release"
    test ! -L "$release"
  else
    test ! -e "$incoming"
    test ! -L "$incoming"
    test ! -e "$incoming_owner"
    test ! -L "$incoming_owner"
    mkdir -- "$incoming"
    printf '%s\n' "$owner_token" > "$incoming_owner"
    rsync -a -- "$restore_root/app/web/out/" "$incoming/"
    python3 - "$incoming" "$restore_sha" - -1 - - \
      <<'MEDICAL_AUDIT_RELEASE_VERIFY'
{release_verifier}
MEDICAL_AUDIT_RELEASE_VERIFY
    mv -T -- "$incoming" "$release"
    rm -f -- "$incoming_owner"
  fi
  python3 - "$release" "$restore_sha" - -1 - - \
    <<'MEDICAL_AUDIT_RELEASE_VERIFY'
{release_verifier}
MEDICAL_AUDIT_RELEASE_VERIFY
else
  test "$previous_current" = LEGACY_NONE
  test -f "$restore_root/audit/index.html"
  test -f "$remote_web_dir/index.html"
  legacy_mode=1
fi
docker cp "$nginx_backup" "ai_video_nginx:$container_candidate" >/dev/null 2>&1
if ! docker exec ai_video_nginx nginx -t -c "$container_candidate" \
  >/dev/null 2>&1; then
  echo "rollback nginx backup failed candidate validation" >&2
  exit 83
fi
if ! docker exec ai_video_nginx rm -f "$container_candidate" \
  >/dev/null 2>&1; then
  echo "sensitive rollback candidate cleanup failed" >&2
  exit 85
fi
container_candidate_owned=0
umask 077
test ! -e "$rollback_transaction_dir"
mkdir -- "$rollback_transaction_dir"
cp -p -- "$nginx_config" "$rollback_transaction_dir/nginx.conf.before"
chmod 600 "$rollback_transaction_dir/nginx.conf.before"
printf '%s\n' "$current_target" > "$rollback_transaction_dir/previous-current"
printf '%s\n' "$restore_sha" > "$rollback_transaction_dir/restore-sha"
printf 'prepared\n' > "$rollback_transaction_dir/status"
activation_started=0
marker_commit_started=0
sentinel_removed=0
overwrite_nginx_in_place() {{
  destination="$1"
  source_file="$2"
  python3 - "$destination" "$source_file" <<'MEDICAL_AUDIT_NGINX_OVERWRITE'
import os
import stat
import sys
from pathlib import Path

destination = Path(sys.argv[1])
source = Path(sys.argv[2])
destination_before = destination.lstat()
source_before = source.lstat()
for observed in (destination_before, source_before):
    if stat.S_ISLNK(observed.st_mode) or not stat.S_ISREG(observed.st_mode):
        raise SystemExit("nginx restore input must be regular")
content = source.read_bytes()
descriptor = os.open(
    destination,
    os.O_WRONLY | os.O_NOFOLLOW,
)
try:
    opened = os.fstat(descriptor)
    if (
        opened.st_dev != destination_before.st_dev
        or opened.st_ino != destination_before.st_ino
    ):
        raise SystemExit("nginx restore destination changed")
    os.ftruncate(descriptor, 0)
    offset = 0
    while offset < len(content):
        offset += os.write(descriptor, content[offset:])
    os.fsync(descriptor)
    final = os.fstat(descriptor)
finally:
    os.close(descriptor)
destination_after = destination.lstat()
if (
    final.st_dev != destination_after.st_dev
    or final.st_ino != destination_after.st_ino
):
    raise SystemExit("nginx restore destination changed")
MEDICAL_AUDIT_NGINX_OVERWRITE
}}
write_migration_sentinel() {{
  test ! -e "$next_migration_sentinel" || return 1
  test ! -L "$next_migration_sentinel" || return 1
  printf '%s\n' "$expected_current_sha" > "$next_migration_sentinel" || return 1
  python3 - "$next_migration_sentinel" <<'MEDICAL_AUDIT_MIGRATION_FSYNC'
import os
import sys

descriptor = os.open(sys.argv[1], os.O_RDONLY | os.O_NOFOLLOW)
try:
    os.fsync(descriptor)
finally:
    os.close(descriptor)
MEDICAL_AUDIT_MIGRATION_FSYNC
  if [ "$?" -ne 0 ]; then
    return 1
  fi
  mv -Tf -- "$next_migration_sentinel" "$migration_sentinel" || return 1
  python3 - "$remote_web_dir" <<'MEDICAL_AUDIT_MIGRATION_DIR_FSYNC'
import os
import sys

descriptor = os.open(sys.argv[1], os.O_RDONLY | os.O_DIRECTORY)
try:
    os.fsync(descriptor)
finally:
    os.close(descriptor)
MEDICAL_AUDIT_MIGRATION_DIR_FSYNC
  if [ "$?" -ne 0 ]; then
    return 1
  fi
  test -f "$migration_sentinel" || return 1
  test ! -L "$migration_sentinel" || return 1
  test "$(cat "$migration_sentinel")" = "$expected_current_sha" || return 1
}}
restore_ui_after_error() {{
  restore_status=0
  if [ "$activation_started" -eq 1 ]; then
    rm -f -- "$current_next"
    restore_link="$current.restore"
    rm -f -- "$restore_link"
    ln -s "releases/$expected_current_sha" "$restore_link" || restore_status=1
    mv -Tf -- "$restore_link" "$current" || restore_status=1
    overwrite_nginx_in_place \
      "$nginx_config" "$rollback_transaction_dir/nginx.conf.before" \
      || restore_status=1
    docker exec ai_video_nginx nginx -t >/dev/null 2>&1 || restore_status=1
    docker exec ai_video_nginx nginx -s reload >/dev/null 2>&1 \
      || restore_status=1
  fi
  if [ "$sentinel_removed" -eq 1 ]; then
    write_migration_sentinel || restore_status=1
  fi
  if [ "$restore_status" -eq 0 ]; then
    printf 'rollback-failed\n' > "$rollback_transaction_dir/status"
    return 0
  fi
  printf 'restore-failed\n' > "$rollback_transaction_dir/status"
  return 1
}}
on_rollback_error() {{
  original_status="$?"
  trap - ERR
  set +e
  if [ "$marker_commit_started" -eq 1 ]; then
    printf 'marker-commit-uncertain\n' > "$rollback_transaction_dir/status"
    echo "rollback marker commit outcome is unknown; production lock must be retained" >&2
    exit "$original_status"
  fi
  if ! restore_ui_after_error; then
    echo "rollback UI restore failed; production lock must be retained" >&2
    exit 84
  fi
  echo "rollback failed; production lock must be retained" >&2
  exit "$original_status"
}}
trap on_rollback_error ERR
rsync -a --delete \
  --exclude '.deploy-sha' \
  --exclude 'configs/deploy/tencent-cloud/medical-audit.env' \
  "$restore_root/app/" "$remote_app_dir/"
cp "$preserved_env" "$remote_app_dir/configs/deploy/tencent-cloud/medical-audit.env"
chmod 600 "$remote_app_dir/configs/deploy/tencent-cloud/medical-audit.env"
cd "$remote_app_dir"
postgres_id_before="$(docker inspect medical_audit_pg --format {shlex.quote(container_id_format)})"
clamav_id_before=""
if docker inspect medical_audit_clamav >/dev/null 2>&1; then
  clamav_id_before="$(docker inspect medical_audit_clamav \
    --format {shlex.quote(container_id_format)})"
fi
export MEDICAL_AUDIT_DEPLOY_SHA="$restore_sha"
docker compose -f configs/deploy/tencent-cloud/docker-compose.prod.yaml \
  --env-file configs/deploy/tencent-cloud/medical-audit.env build app
docker compose -f configs/deploy/tencent-cloud/docker-compose.prod.yaml \
  --env-file configs/deploy/tencent-cloud/medical-audit.env up -d --no-deps app
for attempt in $(seq 1 60); do
  app_health="$(docker inspect medical_audit_app \
    --format {shlex.quote(health_format)} 2>/dev/null || true)"
  if [ "$app_health" = "healthy" ]; then
    break
  fi
  sleep 2
done
test "$(docker inspect medical_audit_app --format {shlex.quote(health_format)})" = "healthy"
test "$(docker inspect medical_audit_pg \
  --format {shlex.quote(container_id_format)})" = "$postgres_id_before"
if [ -n "$clamav_id_before" ]; then
  test "$(docker inspect medical_audit_clamav \
    --format {shlex.quote(container_id_format)})" = "$clamav_id_before"
fi
activation_started=1
if [ "$legacy_mode" -eq 1 ]; then
  rm -f -- "$current"
else
  ln -s "releases/$restore_sha" "$current_next"
  mv -Tf -- "$current_next" "$current"
fi
overwrite_nginx_in_place "$nginx_config" "$nginx_backup"
if ! docker exec ai_video_nginx nginx -t >/dev/null 2>&1; then
  false
fi
if ! docker exec ai_video_nginx nginx -s reload >/dev/null 2>&1; then
  false
fi
curl -fsS http://127.0.0.1:18080/health >/dev/null
curl -fsS "$base_url/api/v1/health" >/dev/null
curl -fsS "$base_url/" >/dev/null
if [ "$legacy_mode" -eq 0 ]; then
  test "$(readlink "$current")" = "releases/$restore_sha"
  python3 - "$base_url" "$release" <<'MEDICAL_AUDIT_PUBLIC_VERIFY'
{public_verifier}
MEDICAL_AUDIT_PUBLIC_VERIFY
else
  test ! -e "$current"
  test ! -L "$current"
fi
if [ "$legacy_mode" -eq 1 ]; then
  rm -f -- "$next_migration_sentinel"
  rm -f -- "$migration_sentinel"
  sentinel_removed=1
  test ! -e "$migration_sentinel"
  test ! -L "$migration_sentinel"
  python3 - "$remote_web_dir" <<'MEDICAL_AUDIT_MIGRATION_DIR_FSYNC'
import os
import sys

descriptor = os.open(sys.argv[1], os.O_RDONLY | os.O_DIRECTORY)
try:
    os.fsync(descriptor)
finally:
    os.close(descriptor)
MEDICAL_AUDIT_MIGRATION_DIR_FSYNC
else
  test -f "$migration_sentinel"
  test ! -L "$migration_sentinel"
fi
printf 'ready-to-commit\n' > "$rollback_transaction_dir/status"
printf '%s\n' "$restore_sha" > "$next_marker"
python3 - "$next_marker" <<'MEDICAL_AUDIT_MARKER_FSYNC'
import os
import sys

descriptor = os.open(sys.argv[1], os.O_RDONLY | os.O_NOFOLLOW)
try:
    os.fsync(descriptor)
finally:
    os.close(descriptor)
MEDICAL_AUDIT_MARKER_FSYNC
marker_commit_started=1
mv -Tf -- "$next_marker" "$marker"
python3 - "$remote_app_dir" <<'MEDICAL_AUDIT_MARKER_DIR_FSYNC'
import os
import sys

descriptor = os.open(sys.argv[1], os.O_RDONLY | os.O_DIRECTORY)
try:
    os.fsync(descriptor)
finally:
    os.close(descriptor)
MEDICAL_AUDIT_MARKER_DIR_FSYNC
test "$(cat "$marker")" = "$restore_sha"
trap - ERR
"""
    _ssh(config, script)


def _ssh(
    config: DeployConfig,
    script: str,
    *,
    timeout_seconds: int | None = REMOTE_SSH_COMMAND_TIMEOUT_SECONDS,
    completion_check_script: str | None = None,
    timeout_description: str = "remote script",
) -> None:
    print(
        "+ ssh "
        "-n "
        f"-i {shlex.quote(str(config.ssh_key))} "
        "-o BatchMode=yes "
        "-o StrictHostKeyChecking=yes "
        "-o IdentitiesOnly=yes "
        f"{config.ssh_target} bash -lc <remote-script>",
        flush=True,
    )
    try:
        subprocess.run(
            _ssh_args(config, script),
            cwd=config.repo_root,
            check=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        if completion_check_script is None:
            raise RemoteOutcomeUnknownError(
                f"{timeout_description} timed out after {exc.timeout} seconds",
            ) from exc
        print(
            f"WARNING {timeout_description} ssh timed out after {exc.timeout} seconds; "
            "checking remote completion marker",
            flush=True,
        )
        try:
            subprocess.run(
                _ssh_args(config, completion_check_script),
                cwd=config.repo_root,
                check=True,
                text=True,
                timeout=REMOTE_COMPLETION_CHECK_TIMEOUT_SECONDS,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as check_error:
            raise RemoteOutcomeUnknownError(
                f"{timeout_description} completion outcome is unknown",
            ) from check_error
        print(
            f"WARNING {timeout_description} completed remotely after ssh timeout; continuing",
            flush=True,
        )
        return
    except subprocess.CalledProcessError as exc:
        if exc.returncode == 255 or exc.returncode < 0:
            raise RemoteOutcomeUnknownError(
                f"{timeout_description} SSH outcome is unknown",
            ) from exc
        raise
    if completion_check_script is not None:
        try:
            subprocess.run(
                _ssh_args(config, completion_check_script),
                cwd=config.repo_root,
                check=True,
                text=True,
                timeout=REMOTE_COMPLETION_CHECK_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise RemoteOutcomeUnknownError(
                f"{timeout_description} completion outcome is unknown",
            ) from exc
        except subprocess.CalledProcessError as exc:
            if exc.returncode == 255 or exc.returncode < 0:
                raise RemoteOutcomeUnknownError(
                    f"{timeout_description} completion outcome is unknown",
                ) from exc
            raise


def _ssh_background_with_completion(
    config: DeployConfig,
    script: str,
    completion_check_script: str,
    *,
    timeout_seconds: int,
    timeout_description: str,
    job_name: str,
) -> None:
    safe_job_name = _safe_remote_job_name(job_name)
    remote_script = f"/tmp/{safe_job_name}.sh"
    remote_log = f"/tmp/{safe_job_name}.log"
    remote_pid = f"/tmp/{safe_job_name}.pid"
    starter_script = f"""
set -euo pipefail
job_script={shlex.quote(remote_script)}
job_log={shlex.quote(remote_log)}
job_pid={shlex.quote(remote_pid)}
cat > "$job_script" <<'MEDICAL_AUDIT_REMOTE_JOB_EOF'
{script}
MEDICAL_AUDIT_REMOTE_JOB_EOF
chmod 700 "$job_script"
rm -f "$job_log" "$job_pid"
nohup bash "$job_script" > "$job_log" 2>&1 &
printf '%s\\n' "$!" > "$job_pid"
"""
    print(
        f"+ ssh background {config.ssh_target} {timeout_description} "
        f"job={safe_job_name}",
        flush=True,
    )
    try:
        subprocess.run(
            _ssh_args(config, starter_script),
            cwd=config.repo_root,
            check=True,
            text=True,
            timeout=REMOTE_COMPLETION_CHECK_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
        raise RemoteOutcomeUnknownError(
            f"{timeout_description} background starter outcome is unknown",
        ) from exc
    deadline = time.monotonic() + timeout_seconds
    poll_script = f"""
set -euo pipefail
job_pid={shlex.quote(remote_pid)}
job_log={shlex.quote(remote_log)}
if bash -lc {shlex.quote(completion_check_script)}; then
  echo "MEDICAL_AUDIT_REMOTE_JOB_STATUS=complete"
  exit 0
fi
pid="$(cat "$job_pid" 2>/dev/null || true)"
if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
  echo "MEDICAL_AUDIT_REMOTE_JOB_STATUS=running"
  exit 0
fi
echo "MEDICAL_AUDIT_REMOTE_JOB_STATUS=failed"
echo "remote job exited before completion marker"
tail -n 80 "$job_log" || true
exit 0
"""
    while True:
        try:
            completed = subprocess.run(
                _ssh_args(config, poll_script),
                cwd=config.repo_root,
                check=False,
                text=True,
                capture_output=True,
                timeout=REMOTE_COMPLETION_CHECK_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise RemoteOutcomeUnknownError(
                f"{timeout_description} background poll outcome is unknown",
            ) from exc
        if completed.returncode != 0:
            raise RemoteOutcomeUnknownError(
                f"{timeout_description} background poll outcome is unknown",
            )
        detail = "\n".join(
            part.strip()
            for part in (completed.stdout, completed.stderr)
            if part.strip()
        )
        status = _extract_remote_job_status(completed.stdout)
        if status == "complete":
            print(f"{timeout_description} completed remotely", flush=True)
            return
        if status == "failed":
            raise DeployError(
                f"{timeout_description} failed before completion marker"
                + (f":\n{detail}" if detail else ""),
            )
        if status != "running":
            raise RemoteOutcomeUnknownError(
                f"{timeout_description} background poll outcome is unknown"
                + (f":\n{detail}" if detail else ""),
            )
        if time.monotonic() >= deadline:
            raise RemoteOutcomeUnknownError(
                f"{timeout_description} timed out after {timeout_seconds} seconds",
            )
        if completed.stdout.strip():
            print(completed.stdout.strip(), flush=True)
        time.sleep(REMOTE_COMPLETION_POLL_SECONDS)


def _extract_remote_job_status(stdout: str) -> str | None:
    prefix = "MEDICAL_AUDIT_REMOTE_JOB_STATUS="
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return None


def _safe_remote_job_name(job_name: str) -> str:
    safe = "".join(
        char if char.isalnum() or char in {"-", "_"} else "-" for char in job_name
    ).strip("-")
    return safe or "medical-audit-remote-job"


def _ssh_args(config: DeployConfig, script: str) -> list[str]:
    return [
        "ssh",
        "-n",
        "-i",
        str(config.ssh_key),
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        f"ConnectTimeout={SSH_CONNECT_TIMEOUT_SECONDS}",
        "-o",
        f"ServerAliveInterval={SSH_SERVER_ALIVE_INTERVAL_SECONDS}",
        "-o",
        f"ServerAliveCountMax={SSH_SERVER_ALIVE_COUNT_MAX}",
        config.ssh_target,
        "bash",
        "-lc",
        shlex.quote(script),
    ]


def _ssh_transport(config: DeployConfig) -> str:
    return (
        "ssh "
        f"-i {shlex.quote(str(config.ssh_key))} "
        "-o BatchMode=yes "
        "-o StrictHostKeyChecking=yes "
        "-o IdentitiesOnly=yes "
        f"-o ConnectTimeout={SSH_CONNECT_TIMEOUT_SECONDS} "
        f"-o ServerAliveInterval={SSH_SERVER_ALIVE_INTERVAL_SECONDS} "
        f"-o ServerAliveCountMax={SSH_SERVER_ALIVE_COUNT_MAX}"
    )


def _run(
    args: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    timeout_seconds: int | None = None,
    remote_outcome_unknown: bool = False,
) -> None:
    print(_format_command(args), flush=True)
    try:
        if timeout_seconds is None:
            subprocess.run(
                args,
                cwd=cwd,
                check=True,
                text=True,
                env=env,
            )
        else:
            subprocess.run(
                args,
                cwd=cwd,
                check=True,
                text=True,
                env=env,
                timeout=timeout_seconds,
            )
    except subprocess.TimeoutExpired as exc:
        if remote_outcome_unknown:
            raise RemoteOutcomeUnknownError("remote command outcome is unknown") from exc
        raise
    except subprocess.CalledProcessError as exc:
        if remote_outcome_unknown:
            raise RemoteOutcomeUnknownError("remote command outcome is unknown") from exc
        raise


def _run_capture(args: Sequence[str], *, cwd: Path) -> str:
    completed = subprocess.run(
        args,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout


def _format_command(args: Sequence[str]) -> str:
    return "+ " + " ".join(shlex.quote(str(arg)) for arg in args)


if __name__ == "__main__":
    raise SystemExit(main())
