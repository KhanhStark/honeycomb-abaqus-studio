"""Restore public release volumes with per-part and whole-file verification.

Re-running in the same target verifies and reuses completed parts in partial
files. Existing different files are never overwritten. No solver is launched.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import httpx

from .cloud_github import REPOSITORY

MAX_PART = 1024**3
SHA = re.compile(r"^[0-9a-f]{64}$")


def public_asset(url: str) -> str:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or not parsed.path.startswith(f"/{REPOSITORY}/releases/download/")
        or parsed.query
        or parsed.fragment
        or any(p in (".", "..") for p in parsed.path.split("/"))
    ):
        raise ValueError("Only public release assets in this repository are accepted")
    return url


def destination(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if (
        not relative
        or path.is_absolute()
        or "\\" in relative
        or any(
            p in (".", "..")
            or ":" in p
            or p != p.rstrip(" .")
            or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?", p)
            for p in path.parts
        )
    ):
        raise ValueError("Unsafe archive path")
    target = root.joinpath(*path.parts)
    if not target.resolve().is_relative_to(root) or any(p.is_symlink() for p in [target, *target.parents]):
        raise ValueError("Archive target escapes the restore directory or follows a symlink")
    return target


def validate_manifest(manifest: dict, *, allow_incomplete=False):
    if manifest.get("kind") != "honeycomb-release-archive" or manifest.get("schema_version") != "1":
        raise ValueError("Unsupported archive manifest")
    if manifest.get("complete") is not True and not allow_incomplete:
        raise ValueError(
            "Incomplete checkpoint: pass --allow-incomplete to recover retained files explicitly"
        )
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) > 100000:
        raise ValueError("Invalid file inventory")
    seen = set()
    for file in files:
        # Case-folding also prevents aliases on a Windows restore destination.
        key = file["path"].casefold()
        if key in seen:
            raise ValueError("Duplicate archive path")
        seen.add(key)
        if not SHA.fullmatch(file["sha256"]) or type(file["bytes"]) is not int or file["bytes"] < 0:
            raise ValueError("Invalid file digest or size")
        offset = 0
        if not isinstance(file["parts"], list) or len(file["parts"]) > 10000:
            raise ValueError("Invalid part inventory")
        for index, part in enumerate(file["parts"]):
            if (
                part["index"] != index
                or part["offset"] != offset
                or type(part["bytes"]) is not int
                or not 0 < part["bytes"] <= MAX_PART
                or not SHA.fullmatch(part["sha256"])
                or part.get("digest") != "sha256:" + part["sha256"]
            ):
                raise ValueError("Non-contiguous parts or inconsistent digest")
            public_asset(part["url"])
            offset += part["bytes"]
        if offset != file["bytes"]:
            raise ValueError("Part sizes do not match the original file")


def restore(manifest: dict, root: Path, *, client=None, allow_incomplete=False, paths=None):
    if client is None:
        with httpx.Client(timeout=120, follow_redirects=True) as transport:
            return restore(manifest, root, client=transport, allow_incomplete=allow_incomplete, paths=paths)
    validate_manifest(manifest, allow_incomplete=allow_incomplete)
    from .actions_log import get_actions_log

    logger = get_actions_log()
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    # Validate all destinations before the first transfer.
    targets = [(file, destination(root, file["path"])) for file in manifest["files"]]
    if paths is not None:
        paths = set(paths)
        if paths - {file["path"] for file in manifest["files"]}:
            raise ValueError("Requested files are absent from the archive")
        targets = [(file, target) for file, target in targets if file["path"] in paths]
    result = []
    for file, target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        destination(root, file["path"])
        if target.exists():
            with target.open("rb") as stream:
                matches = (
                    target.stat().st_size == file["bytes"]
                    and hashlib.file_digest(stream, "sha256").hexdigest() == file["sha256"]
                )
            if not matches:
                raise ValueError("Existing file differs; choose another destination: " + file["path"])
            result.append({"path": file["path"], "verified": True, "reused": True})
            continue
        partial = target.with_name("." + target.name + "." + file["sha256"][:12] + ".partial")
        if partial.is_symlink():
            raise ValueError("Partial file is a symlink")
        with partial.open("r+b" if partial.exists() else "w+b") as stream:
            for part in file["parts"]:
                stream.seek(part["offset"])
                digest, count = hashlib.sha256(), 0
                while count < part["bytes"]:
                    block = stream.read(min(4 * 1024**2, part["bytes"] - count))
                    if not block:
                        break
                    digest.update(block)
                    count += len(block)
                if count == part["bytes"] and digest.hexdigest() == part["sha256"]:
                    continue
                stream.seek(part["offset"])
                stream.truncate()
                digest, count = hashlib.sha256(), 0
                transfer = logger.transfer("Tải xuống " + file["path"] + f" · phần {part['index'] + 1}", part["bytes"]) if logger else None
                with client.stream("GET", part["url"]) as response:
                    response.raise_for_status()
                    for block in response.iter_bytes(65536):
                        count += len(block)
                        if count > part["bytes"]:
                            raise ValueError("Downloaded part exceeds its declared size")
                        stream.write(block)
                        digest.update(block)
                        if transfer:
                            transfer.advance(len(block))
                stream.flush()
                if count != part["bytes"] or digest.hexdigest() != part["sha256"]:
                    raise ValueError("Downloaded part failed SHA-256/size verification")
                if transfer:
                    transfer.verified()
            stream.truncate(file["bytes"])
            stream.seek(0)
            if hashlib.file_digest(stream, "sha256").hexdigest() != file["sha256"]:
                raise ValueError("Reassembled file failed SHA-256 verification")
        # An exclusive hard link avoids replacing a file created during download.
        os.link(partial, target)
        partial.unlink()
        result.append({"path": file["path"], "verified": True, "reused": False})
    return {"files": result, "complete_dataset": manifest["complete"] is True and paths is None}
