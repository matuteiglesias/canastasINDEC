"""Discover and materialize immutable IPC v2 conversion releases.

This is deliberately a boring HTTP/artifact boundary. It does not import the
IPC producer, does not follow mutable branch files, and does not upgrade
candidate scientific status.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from .v2_core import MONETARY_REFERENCE_ID, PRICE_ARTIFACT, PRICE_METHOD

DISCOVERY_SCHEMA = "ecosystem-release-discovery/v1"
LOCK_SCHEMA = "ecosystem-consumer-lock/v1"
PRODUCER = "matuteiglesias/IPC-Argentina"
RELEASES_API = f"https://api.github.com/repos/{PRODUCER}/releases?per_page=30"
USER_AGENT = "canastasINDEC-ipc-release-consumer/1.0"


def _request(url: str, *, token: str | None = None) -> bytes:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
        return response.read()


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _asset(release: dict, name: str) -> dict:
    matches = [a for a in release.get("assets", []) if a.get("name") == name]
    if len(matches) != 1:
        raise ValueError(f"release_asset_count:{name}:{len(matches)}")
    return matches[0]


def validate_discovery(discovery: dict, release: dict) -> dict:
    if discovery.get("schema") != DISCOVERY_SCHEMA:
        raise ValueError("incompatible_discovery_schema")
    if discovery.get("producer") != PRODUCER:
        raise ValueError("incompatible_discovery_producer")
    if discovery.get("artifact_type") != PRICE_ARTIFACT:
        raise ValueError("incompatible_discovery_artifact")
    if discovery.get("method_id") != PRICE_METHOD:
        raise ValueError("incompatible_discovery_method")
    if discovery.get("monetary_reference_id") != MONETARY_REFERENCE_ID:
        raise ValueError("incompatible_discovery_monetary_reference")
    if discovery.get("status") != "candidate":
        raise ValueError("unsupported_discovery_status")

    release_id = discovery.get("release_id")
    transport = discovery.get("github_release") or {}
    tag = transport.get("tag")
    asset_name = transport.get("asset_name")
    if not release_id or tag != f"candidate-{release_id}":
        raise ValueError("release_tag_identity_mismatch")
    if release.get("tag_name") != tag or not release.get("prerelease") or release.get("draft"):
        raise ValueError("incompatible_github_release_state")
    if asset_name != f"{release_id}.zip":
        raise ValueError("release_asset_identity_mismatch")
    _asset(release, "discovery.json")
    _asset(release, asset_name)
    for field in ("asset_sha256", "manifest_sha256"):
        value = transport.get(field)
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError(f"missing_{field}")
    return discovery


def select_release(releases: list[dict], fetch_bytes=_request, token: str | None = None) -> tuple[dict, dict]:
    """Select newest compatible producer publication; malformed candidate releases fail closed."""
    for release in releases:
        if release.get("draft"):
            continue
        assets = {a.get("name") for a in release.get("assets", [])}
        if "discovery.json" not in assets:
            continue
        discovery_asset = _asset(release, "discovery.json")
        raw = fetch_bytes(discovery_asset["browser_download_url"], token=token)
        discovery = json.loads(raw.decode("utf-8"))
        return release, validate_discovery(discovery, release)
    raise ValueError("no_compatible_ipc_release_discovered")


def _safe_extract(raw_zip: bytes, release_id: str, destination: Path) -> Path:
    destination = destination.resolve()
    release_root = destination / release_id
    if release_root.exists():
        shutil.rmtree(release_root)
    release_root.mkdir(parents=True)
    from io import BytesIO

    with zipfile.ZipFile(BytesIO(raw_zip)) as archive:
        names = archive.namelist()
        if not names:
            raise ValueError("empty_release_archive")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts or not pure.parts or pure.parts[0] != release_id:
                raise ValueError("unsafe_or_mismatched_release_archive_path")
            if info.is_dir():
                continue
            relative = Path(*pure.parts[1:])
            if not relative.parts:
                raise ValueError("invalid_release_archive_member")
            target = (release_root / relative).resolve()
            if release_root not in target.parents:
                raise ValueError("unsafe_release_archive_path")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
    return release_root


def materialize(output_root: Path, lock_path: Path, *, token: str | None = None, releases: list[dict] | None = None, fetch_bytes=_request) -> dict:
    output_root = Path(output_root).resolve()
    lock_path = Path(lock_path).resolve()
    token = token or os.environ.get("GITHUB_TOKEN")
    if releases is None:
        releases = json.loads(fetch_bytes(RELEASES_API, token=token).decode("utf-8"))
    release, discovery = select_release(releases, fetch_bytes=fetch_bytes, token=token)
    transport = discovery["github_release"]
    asset = _asset(release, transport["asset_name"])
    raw_zip = fetch_bytes(asset["browser_download_url"], token=token)
    if _sha(raw_zip) != transport["asset_sha256"]:
        raise ValueError("ipc_release_asset_checksum_mismatch")

    release_root = _safe_extract(raw_zip, discovery["release_id"], output_root)
    manifest_path = release_root / "manifest.json"
    if not manifest_path.is_file() or _sha(manifest_path.read_bytes()) != transport["manifest_sha256"]:
        raise ValueError("ipc_release_manifest_checksum_mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for field in ("release_id", "artifact_type", "method_id", "monetary_reference_id", "status"):
        if manifest.get(field) != discovery.get(field):
            raise ValueError(f"ipc_release_manifest_discovery_mismatch:{field}")

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        portable_path = release_root.relative_to(lock_path.parent).as_posix()
    except ValueError:
        portable_path = str(release_root)
    lock = {
        "schema": LOCK_SCHEMA,
        "producer": PRODUCER,
        "artifact_type": discovery["artifact_type"],
        "release_id": discovery["release_id"],
        "status": discovery["status"],
        "method_id": discovery["method_id"],
        "monetary_reference_id": discovery["monetary_reference_id"],
        "release_tag": release["tag_name"],
        "release_api_url": release.get("url"),
        "published_at": release.get("published_at"),
        "asset_name": transport["asset_name"],
        "asset_sha256": transport["asset_sha256"],
        "manifest_sha256": transport["manifest_sha256"],
        "materialized_release_path": portable_path,
    }
    lock_path.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return lock


def resolve_locked_release(lock_path: Path) -> Path:
    lock_path = Path(lock_path).resolve()
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("schema") != LOCK_SCHEMA:
        raise ValueError("invalid_ipc_release_lock")
    path = Path(lock["materialized_release_path"])
    if not path.is_absolute():
        path = (lock_path.parent / path).resolve()
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("run/ipc_release"))
    parser.add_argument("--lock", type=Path, default=Path("run/ipc_release_lock.json"))
    args = parser.parse_args()
    lock = materialize(args.output, args.lock)
    print(json.dumps(lock, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
