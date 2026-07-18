#!/usr/bin/env python3
"""Fetch or strictly verify pinned, redistributable subtitle font inputs.

Large font binaries stay outside Git in ``reproducibility/local_inputs``.
Every network response is written to a sibling temporary file, checked against
the manifest byte count and SHA-256, and only then atomically installed.  The
``--offline`` mode never opens a URL and is suitable for an archived cache.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Callable


MANIFEST_SCHEMA = "magireco-font-dependencies-v1"
SHA256_RE = re.compile(r"^[0-9A-Fa-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9A-Fa-f]{40}$")
SCRIPT_DIR = Path(__file__).resolve().parent
REPRODUCIBILITY_ROOT = SCRIPT_DIR.parent
DEFAULT_MANIFEST = REPRODUCIBILITY_ROOT / "fonts" / "dependencies.json"
DEFAULT_CACHE_DIR = REPRODUCIBILITY_ROOT / "local_inputs" / "fonts"
Download = Callable[[str], bytes]


class FontDependencyError(RuntimeError):
    """A pinned dependency is malformed, missing, or does not match its lock."""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _default_download(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "magireco-slot-font-dependency/1"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def _safe_target(cache_dir: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or not relative.parts:
        raise FontDependencyError(
            f"dependency path must be a non-empty relative path: {relative_path!r}"
        )
    root = cache_dir.resolve()
    target = (root / relative).resolve()
    try:
        target.relative_to(root)
    except ValueError as error:
        raise FontDependencyError(
            f"dependency path escapes cache root: {relative_path!r}"
        ) from error
    return target


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FontDependencyError(f"unable to read font manifest {path}: {error}") from error
    if payload.get("schema") != MANIFEST_SCHEMA:
        raise FontDependencyError(
            f"font manifest schema must be {MANIFEST_SCHEMA!r}: {path}"
        )
    dependencies = payload.get("dependencies")
    if not isinstance(dependencies, dict) or not dependencies:
        raise FontDependencyError("font manifest requires a non-empty dependencies object")

    for dependency_id, dependency in dependencies.items():
        label = f"dependency {dependency_id!r}"
        if not isinstance(dependency, dict):
            raise FontDependencyError(f"{label} must be an object")
        upstream = dependency.get("upstream")
        commit = str(upstream.get("commit", "")) if isinstance(upstream, dict) else ""
        if not COMMIT_RE.fullmatch(commit):
            raise FontDependencyError(f"{label} requires an immutable 40-hex commit")
        license_spec = dependency.get("license")
        if (
            not isinstance(license_spec, dict)
            or not str(license_spec.get("spdx", "")).strip()
            or not str(license_spec.get("file", "")).strip()
        ):
            raise FontDependencyError(f"{label} requires license.spdx and license.file")
        files = dependency.get("files")
        if not isinstance(files, list) or not files:
            raise FontDependencyError(f"{label} requires a non-empty files list")
        roles: set[str] = set()
        paths: set[str] = set()
        for index, spec in enumerate(files):
            file_label = f"{label} file {index}"
            if not isinstance(spec, dict):
                raise FontDependencyError(f"{file_label} must be an object")
            role = str(spec.get("role", "")).strip()
            relative_path = str(spec.get("path", "")).strip()
            url = str(spec.get("url", "")).strip()
            sha256 = str(spec.get("sha256", "")).strip().upper()
            try:
                byte_count = int(spec["bytes"])
            except (KeyError, TypeError, ValueError) as error:
                raise FontDependencyError(
                    f"{file_label} requires a positive integer byte count"
                ) from error
            if not role or role in roles:
                raise FontDependencyError(f"{file_label} has blank or duplicate role")
            if not relative_path or relative_path in paths:
                raise FontDependencyError(f"{file_label} has blank or duplicate path")
            if not url.startswith("https://") or commit.lower() not in url.lower():
                raise FontDependencyError(
                    f"{file_label} URL must be HTTPS and pinned to upstream commit"
                )
            if not SHA256_RE.fullmatch(sha256) or byte_count <= 0:
                raise FontDependencyError(
                    f"{file_label} requires full SHA-256 and positive byte count"
                )
            roles.add(role)
            paths.add(relative_path)
        if "font" not in roles or "license" not in roles:
            raise FontDependencyError(f"{label} must lock both font and license files")
        if str(license_spec["file"]) not in paths:
            raise FontDependencyError(
                f"{label} license.file is not present in the locked files list"
            )
    return payload


def verify_file(path: Path, spec: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        raise FontDependencyError(f"cached dependency is missing: {path}")
    expected_bytes = int(spec["bytes"])
    actual_bytes = path.stat().st_size
    if actual_bytes != expected_bytes:
        raise FontDependencyError(
            f"cached dependency size mismatch for {path}: "
            f"expected={expected_bytes}, actual={actual_bytes}"
        )
    expected_sha256 = str(spec["sha256"]).upper()
    actual_sha256 = file_sha256(path)
    if actual_sha256 != expected_sha256:
        raise FontDependencyError(
            f"cached dependency SHA-256 mismatch for {path}: "
            f"expected={expected_sha256}, actual={actual_sha256}"
        )
    return {
        "path": str(path),
        "bytes": actual_bytes,
        "sha256": actual_sha256,
        "verified": True,
    }


def _install_download(
    *,
    target: Path,
    spec: dict[str, Any],
    download: Download,
) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = download(str(spec["url"]))
    if not isinstance(payload, bytes):
        raise FontDependencyError(
            f"download callback returned {type(payload).__name__}, expected bytes"
        )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".download", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        audit = verify_file(temporary, spec)
        os.replace(temporary, target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    audit["path"] = str(target)
    audit["source_url"] = str(spec["url"])
    return audit


def materialize_dependencies(
    manifest: dict[str, Any],
    *,
    cache_dir: Path,
    selected: list[str] | None = None,
    offline: bool = False,
    repair: bool = False,
    download: Download = _default_download,
) -> dict[str, Any]:
    dependencies = manifest["dependencies"]
    dependency_ids = selected or list(dependencies)
    unknown = [value for value in dependency_ids if value not in dependencies]
    if unknown:
        raise FontDependencyError(f"unknown font dependencies: {unknown}")

    result: dict[str, Any] = {
        "schema": "magireco-font-dependency-audit-v1",
        "mode": "offline_verify" if offline else "fetch_or_verify",
        "cache_dir": str(cache_dir.resolve()),
        "dependencies": {},
    }
    for dependency_id in dependency_ids:
        dependency = dependencies[dependency_id]
        rows: list[dict[str, Any]] = []
        for spec in dependency["files"]:
            target = _safe_target(cache_dir, str(spec["path"]))
            existed_before = target.exists()
            status = "cached"
            try:
                audit = verify_file(target, spec)
            except FontDependencyError:
                if offline:
                    raise
                if target.exists() and not repair:
                    raise FontDependencyError(
                        f"refusing to overwrite invalid cache without --repair: {target}"
                    )
                audit = _install_download(target=target, spec=spec, download=download)
                status = "repaired" if existed_before else "downloaded"
            rows.append({"role": spec["role"], "status": status, **audit})
        result["dependencies"][dependency_id] = {
            "version": dependency["version"],
            "license": dependency["license"],
            "files": rows,
            "verified": True,
        }
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument(
        "--dependency",
        action="append",
        dest="dependencies",
        help="repeat to select dependency IDs; default is every locked dependency",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="strictly verify the cache and perform no network access",
    )
    parser.add_argument(
        "--repair",
        action="store_true",
        help="replace a corrupt cached file after a verified re-download",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.offline and args.repair:
        raise FontDependencyError("--repair cannot be combined with --offline")
    manifest = load_manifest(args.manifest.resolve())
    audit = materialize_dependencies(
        manifest,
        cache_dir=args.cache_dir,
        selected=args.dependencies,
        offline=args.offline,
        repair=args.repair,
    )
    json.dump(audit, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FontDependencyError as error:
        print(f"font dependency error: {error}", file=sys.stderr)
        raise SystemExit(2)
