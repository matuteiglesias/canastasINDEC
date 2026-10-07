#!/usr/bin/env python3
"""Package one validated regional-basket v2 candidate for immutable transport."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from basket_release.v2_core import validate_v2_candidate

EXPECTED_TYPE = "research.argentina-regional-baskets/v1"
EXPECTED_METHOD = "research.argentina-regional-baskets/source-observed-plus-price-consensus-v2"
SCHEMA = "ecosystem-release-discovery/v1"
PRODUCER = "matuteiglesias/canastasINDEC"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def package(release_dir: Path, output_dir: Path) -> dict:
    release_dir = release_dir.resolve()
    output_dir = output_dir.resolve()
    validate_v2_candidate(release_dir)
    manifest_path = release_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("missing_manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("artifact_type") != EXPECTED_TYPE:
        raise ValueError("unexpected_artifact_type")
    if manifest.get("method_id") != EXPECTED_METHOD:
        raise ValueError("unexpected_method_id")
    if manifest.get("status") != "candidate":
        raise ValueError("only_candidate_publication_supported")
    release_id = manifest.get("release_id")
    if not release_id or release_dir.name != release_id:
        raise ValueError("release_id_directory_mismatch")
    dependency = manifest.get("price_dependency")
    if not isinstance(dependency, dict):
        raise ValueError("missing_price_dependency")

    output_dir.mkdir(parents=True, exist_ok=True)
    asset_name = f"{release_id}.zip"
    asset_path = output_dir / asset_name
    with zipfile.ZipFile(asset_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(p for p in release_dir.iterdir() if p.is_file()):
            info = zipfile.ZipInfo(
                f"{release_id}/{path.name}",
                date_time=(1980, 1, 1, 0, 0, 0),
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, path.read_bytes())

    tag = f"candidate-{release_id}"
    discovery = {
        "schema": SCHEMA,
        "producer": PRODUCER,
        "artifact_type": EXPECTED_TYPE,
        "release_id": release_id,
        "status": "candidate",
        "method_id": manifest["method_id"],
        "monetary_reference_id": manifest.get("monetary_reference_id"),
        "created_at": manifest.get("created_at_utc"),
        "price_dependency": dependency,
        "github_release": {
            "tag": tag,
            "asset_name": asset_name,
            "asset_sha256": sha256(asset_path),
            "manifest_sha256": sha256(manifest_path),
        },
    }
    discovery_path = output_dir / "discovery.json"
    discovery_path.write_bytes(canonical_json(discovery))
    return {
        "tag": tag,
        "asset": str(asset_path),
        "discovery": str(discovery_path),
        **discovery,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("release_dir", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/basket-publication"),
    )
    args = parser.parse_args()
    result = package(args.release_dir, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
