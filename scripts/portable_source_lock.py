#!/usr/bin/env python3
"""Make basket source locks relocatable while the legacy core still uses file paths.

New scheduled source evidence stores snapshot paths relative to the lock directory.
Validation resolves those paths in a temporary runtime copy and then delegates to
`basket_release.core.load_locked_sources`, preserving the existing schema/hash QA.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from copy import deepcopy
from pathlib import Path

from basket_release.core import BuildError, canonical_json, load_locked_sources


def _inside(base: Path, path: Path) -> bool:
    base = base.resolve(); path = path.resolve()
    return path == base or base in path.parents


def export_portable(runtime_lock: Path, output_lock: Path) -> dict:
    runtime_lock = runtime_lock.resolve(); output_lock = output_lock.resolve()
    lock = json.loads(runtime_lock.read_text(encoding="utf-8"))
    base = output_lock.parent.resolve()
    snapshots = lock.get("snapshots", [])
    if {s.get("distribution_id") for s in snapshots} != {"445.1", "446.1"}:
        raise BuildError("unparseable_pinned_source: lock must contain 445.1 and 446.1")
    for snap in snapshots:
        source = Path(snap["cache_file"]).resolve()
        if not source.is_file():
            raise BuildError(f"source_checksum_mismatch: {snap['source_id']}")
        if not _inside(base, source):
            raise BuildError(f"nonportable_source_snapshot: {snap['source_id']}")
        snap["cache_file"] = source.relative_to(base).as_posix()
    output_lock.parent.mkdir(parents=True, exist_ok=True)
    output_lock.write_bytes(canonical_json(lock))
    return lock


def _runtime_copy(portable_lock: Path) -> dict:
    portable_lock = portable_lock.resolve()
    lock = deepcopy(json.loads(portable_lock.read_text(encoding="utf-8")))
    base = portable_lock.parent.resolve()
    for snap in lock.get("snapshots", []):
        declared = Path(snap["cache_file"])
        if declared.is_absolute():
            # Backward compatibility for existing fixture/source locks.
            resolved = declared.resolve()
        else:
            resolved = (base / declared).resolve()
            if not _inside(base, resolved):
                raise BuildError(f"unsafe_source_snapshot_path: {snap.get('source_id', 'unknown')}")
        snap["cache_file"] = str(resolved)
    return lock


def validate_portable(portable_lock: Path) -> dict:
    runtime = _runtime_copy(portable_lock)
    with tempfile.TemporaryDirectory() as tmp:
        runtime_path = Path(tmp) / "source_lock.runtime.json"
        runtime_path.write_bytes(canonical_json(runtime))
        lock, rows = load_locked_sources(runtime_path)
    return {"result": "valid", "snapshots": len(lock["snapshots"]), "normalized_cells": len(rows)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Export/check relocatable regional basket source locks")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("export"); p.add_argument("--runtime", type=Path, required=True); p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("check"); p.add_argument("--lock", type=Path, required=True)
    args = parser.parse_args()
    result = export_portable(args.runtime, args.output) if args.command == "export" else validate_portable(args.lock)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BuildError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
