#!/usr/bin/env python3
"""Build a deterministic integrity manifest for a static Web release."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

FORMAT = "medical-audit-web-release-manifest-v1"
SOURCE_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
PUBLIC_BUILD_VARIABLES = (
    "NEXT_PUBLIC_AUDIT_ORG_LOGO",
    "NEXT_PUBLIC_AUDIT_ORG_NAME",
    "NEXT_PUBLIC_MEDICAL_AUDIT_AGENT_EXTENSION_PACK",
    "NEXT_PUBLIC_MEDICAL_AUDIT_REPLICA_API_READS",
)
HASH_CHUNK_SIZE = 1024 * 1024
TOOL_VERSION_TIMEOUT_SECONDS = 10


class ManifestError(RuntimeError):
    """Raised when a release manifest cannot be built safely."""


@dataclass(frozen=True)
class Config:
    web_out: Path
    output: Path
    source_sha: str | None
    source_sha_env: str | None


@dataclass(frozen=True)
class PublicFile:
    relative_path: str
    absolute_path: Path


def _parse_args(argv: Sequence[str] | None = None) -> Config:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--web-out", required=True, help="Static Web output directory")
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--source-sha", help="Exact Git SHA represented by the build")
    source_group.add_argument(
        "--source-sha-env",
        help="Environment variable containing the exact Git SHA represented by the build",
    )
    parser.add_argument("--output", required=True, help="Manifest output path inside --web-out")
    args = parser.parse_args(argv)
    return Config(
        web_out=Path(cast(str, args.web_out)),
        output=Path(cast(str, args.output)),
        source_sha=cast(str | None, args.source_sha),
        source_sha_env=cast(str | None, args.source_sha_env),
    )


def _validated_source_sha(config: Config) -> str:
    source_sha = config.source_sha
    if config.source_sha_env is not None:
        source_sha = os.environ.get(config.source_sha_env)
        if source_sha is None or source_sha == "":
            raise ManifestError(
                f"source SHA environment variable {config.source_sha_env} is not set"
            )
    if source_sha is None or SOURCE_SHA_PATTERN.fullmatch(source_sha) is None:
        raise ManifestError("source SHA must be exactly 40 lowercase hexadecimal characters")
    return source_sha


def _validated_paths(config: Config) -> tuple[Path, Path]:
    web_out = config.web_out.absolute()
    if web_out.is_symlink():
        raise ManifestError("--web-out must not be a symlink")
    if not web_out.exists() or not web_out.is_dir():
        raise ManifestError("--web-out must be an existing directory")
    web_out = web_out.resolve(strict=True)

    output = config.output.absolute()
    if output.is_symlink():
        raise ManifestError("--output must not be a symlink")
    if output.exists() and not output.is_file():
        raise ManifestError("--output must be a regular file when it already exists")
    try:
        output_parent = output.parent.resolve(strict=True)
    except OSError as exc:
        raise ManifestError("--output parent must be an existing directory") from exc
    output = output_parent / output.name
    try:
        output.relative_to(web_out)
    except ValueError as exc:
        raise ManifestError("--output must be inside --web-out") from exc
    return web_out, output


def _collect_public_files(web_out: Path, output: Path) -> list[PublicFile]:
    pending = [web_out]
    public_files: list[PublicFile] = []
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as iterator:
                entries = list(iterator)
        except OSError as exc:
            raise ManifestError("failed to enumerate static Web output") from exc
        for entry in entries:
            path = directory / entry.name
            try:
                mode = entry.stat(follow_symlinks=False).st_mode
            except OSError as exc:
                raise ManifestError("failed to inspect a static Web output entry") from exc
            relative_path = path.relative_to(web_out).as_posix()
            if stat.S_ISLNK(mode):
                raise ManifestError(f"static Web output contains a symlink: {relative_path}")
            if stat.S_ISDIR(mode):
                pending.append(path)
                continue
            if not stat.S_ISREG(mode):
                raise ManifestError(
                    f"static Web output contains a non-regular file: {relative_path}"
                )
            if path == output:
                continue
            public_files.append(
                PublicFile(relative_path=relative_path, absolute_path=path)
            )
    return sorted(public_files, key=lambda item: item.relative_path.encode("utf-8"))


def _hash_regular_file(path: Path) -> tuple[str, int]:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        file_descriptor = os.open(path, flags)
    except OSError as exc:
        raise ManifestError("failed to open a manifest input file") from exc
    digest = hashlib.sha256()
    size_bytes = 0
    try:
        initial = os.fstat(file_descriptor)
        if not stat.S_ISREG(initial.st_mode):
            raise ManifestError("manifest input changed into a non-regular file")
        with os.fdopen(file_descriptor, "rb") as handle:
            file_descriptor = -1
            while chunk := handle.read(HASH_CHUNK_SIZE):
                digest.update(chunk)
                size_bytes += len(chunk)
            final = os.fstat(handle.fileno())
        if (
            initial.st_dev != final.st_dev
            or initial.st_ino != final.st_ino
            or initial.st_size != final.st_size
            or initial.st_mtime_ns != final.st_mtime_ns
            or size_bytes != final.st_size
        ):
            raise ManifestError("manifest input changed while it was being hashed")
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)
    return digest.hexdigest(), size_bytes


def _tool_version(command: str) -> str:
    try:
        result = subprocess.run(
            [command, "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=TOOL_VERSION_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ManifestError(f"failed to read {command} version") from exc
    version = result.stdout.strip()
    if not version or "\n" in version or "\r" in version:
        raise ManifestError(f"{command} version output must contain exactly one line")
    return version


def _public_build_variables() -> dict[str, str | None]:
    allowlist = set(PUBLIC_BUILD_VARIABLES)
    unknown = sorted(
        key
        for key in os.environ
        if key.startswith("NEXT_PUBLIC_") and key not in allowlist
    )
    if unknown:
        raise ManifestError(
            "unreviewed public build variable(s): " + ", ".join(unknown)
        )
    return {key: os.environ.get(key) for key in PUBLIC_BUILD_VARIABLES}


def _manifest_bytes(*, web_out: Path, output: Path, source_sha: str) -> bytes:
    repo_root = Path(__file__).resolve().parent.parent
    lockfile_sha256, _ = _hash_regular_file(repo_root / "pnpm-lock.yaml")
    files = []
    for public_file in _collect_public_files(web_out, output):
        sha256, size_bytes = _hash_regular_file(public_file.absolute_path)
        files.append(
            {
                "path": public_file.relative_path,
                "size_bytes": size_bytes,
                "sha256": sha256,
            }
        )
    payload: dict[str, object] = {
        "format": FORMAT,
        "source_sha": source_sha,
        "lockfile_sha256": lockfile_sha256,
        "node_version": _tool_version("node"),
        "pnpm_version": _tool_version("pnpm"),
        "public_build_variables": _public_build_variables(),
        "files": files,
    }
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _write_atomic(output: Path, content: bytes) -> None:
    temp_path: Path | None = None
    write_error: OSError | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, output)
        temp_path = None
    except OSError as exc:
        write_error = exc
    if temp_path is not None:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError as exc:
            raise ManifestError(
                "failed to write release manifest atomically and clean its temporary file"
            ) from exc
    if write_error is not None:
        raise ManifestError("failed to write release manifest atomically") from write_error


def main(argv: Sequence[str] | None = None) -> int:
    config = _parse_args(argv)
    try:
        source_sha = _validated_source_sha(config)
        web_out, output = _validated_paths(config)
        content = _manifest_bytes(web_out=web_out, output=output, source_sha=source_sha)
        _write_atomic(output, content)
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
