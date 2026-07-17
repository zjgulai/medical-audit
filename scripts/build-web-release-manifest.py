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
class ManifestFile:
    relative_path: str
    size_bytes: int
    sha256: str


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


def _directory_open_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def _file_open_flags() -> int:
    return os.O_RDONLY | os.O_NOFOLLOW


def _hash_file_descriptor(file_descriptor: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    size_bytes = 0
    try:
        initial = os.fstat(file_descriptor)
        if not stat.S_ISREG(initial.st_mode):
            raise ManifestError("manifest input changed into a non-regular file")
        while chunk := os.read(file_descriptor, HASH_CHUNK_SIZE):
            digest.update(chunk)
            size_bytes += len(chunk)
        final = os.fstat(file_descriptor)
    except OSError as exc:
        raise ManifestError("failed to hash a manifest input file") from exc
    if (
        initial.st_dev != final.st_dev
        or initial.st_ino != final.st_ino
        or initial.st_size != final.st_size
        or initial.st_mtime_ns != final.st_mtime_ns
        or size_bytes != final.st_size
    ):
        raise ManifestError("manifest input changed while it was being hashed")
    return digest.hexdigest(), size_bytes


def _hash_regular_file(path: Path) -> tuple[str, int]:
    try:
        file_descriptor = os.open(path, _file_open_flags())
    except OSError as exc:
        raise ManifestError("failed to open a manifest input file") from exc
    try:
        return _hash_file_descriptor(file_descriptor)
    finally:
        os.close(file_descriptor)


def _hash_public_file_at(
    *,
    directory_fd: int,
    name: str,
    relative_path: str,
) -> ManifestFile:
    try:
        file_descriptor = os.open(
            name,
            _file_open_flags(),
            dir_fd=directory_fd,
        )
    except OSError as exc:
        raise ManifestError(
            f"failed to open a static Web output file: {relative_path}"
        ) from exc
    try:
        sha256, size_bytes = _hash_file_descriptor(file_descriptor)
    finally:
        os.close(file_descriptor)
    return ManifestFile(
        relative_path=relative_path,
        size_bytes=size_bytes,
        sha256=sha256,
    )


def _collect_from_directory(
    *,
    directory_fd: int,
    relative_directory: str,
    output_relative_path: str,
    public_files: list[ManifestFile],
) -> None:
    try:
        with os.scandir(directory_fd) as iterator:
            entries = list(iterator)
    except OSError as exc:
        raise ManifestError("failed to enumerate static Web output") from exc
    for entry in entries:
        relative_path = (
            f"{relative_directory}/{entry.name}"
            if relative_directory
            else entry.name
        )
        try:
            mode = entry.stat(follow_symlinks=False).st_mode
        except OSError as exc:
            raise ManifestError("failed to inspect a static Web output entry") from exc
        if stat.S_ISLNK(mode):
            raise ManifestError(f"static Web output contains a symlink: {relative_path}")
        if stat.S_ISDIR(mode):
            try:
                child_fd = os.open(
                    entry.name,
                    _directory_open_flags(),
                    dir_fd=directory_fd,
                )
            except OSError as exc:
                raise ManifestError(
                    f"failed to open a static Web output directory: {relative_path}"
                ) from exc
            try:
                if not stat.S_ISDIR(os.fstat(child_fd).st_mode):
                    raise ManifestError(
                        f"static Web output directory changed type: {relative_path}"
                    )
                _collect_from_directory(
                    directory_fd=child_fd,
                    relative_directory=relative_path,
                    output_relative_path=output_relative_path,
                    public_files=public_files,
                )
            finally:
                os.close(child_fd)
            continue
        if not stat.S_ISREG(mode):
            raise ManifestError(
                f"static Web output contains a non-regular file: {relative_path}"
            )
        if relative_path == output_relative_path:
            continue
        public_files.append(
            _hash_public_file_at(
                directory_fd=directory_fd,
                name=entry.name,
                relative_path=relative_path,
            )
        )


def _collect_public_files(web_out: Path, output: Path) -> list[ManifestFile]:
    output_relative_path = output.relative_to(web_out).as_posix()
    try:
        root_fd = os.open(web_out, _directory_open_flags())
    except OSError as exc:
        raise ManifestError("failed to open --web-out without following symlinks") from exc
    try:
        if not stat.S_ISDIR(os.fstat(root_fd).st_mode):
            raise ManifestError("--web-out changed into a non-directory")
        public_files: list[ManifestFile] = []
        _collect_from_directory(
            directory_fd=root_fd,
            relative_directory="",
            output_relative_path=output_relative_path,
            public_files=public_files,
        )
    finally:
        os.close(root_fd)
    return sorted(public_files, key=lambda item: item.relative_path.encode("utf-8"))


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
    files = [
        {
            "path": public_file.relative_path,
            "size_bytes": public_file.size_bytes,
            "sha256": public_file.sha256,
        }
        for public_file in _collect_public_files(web_out, output)
    ]
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
            os.fchmod(handle.fileno(), 0o644)
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
