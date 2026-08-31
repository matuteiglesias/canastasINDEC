"""Load exact basket source locks with paths relative to the lock directory."""
from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from .core import BuildError, parse_source, registry_sources, sha


def _inside(base: Path, path: Path) -> bool:
    base=base.resolve(); path=path.resolve()
    return path==base or base in path.parents


def load_portable_locked_sources(lock_path: Path) -> tuple[dict,list[dict]]:
    lock_path=Path(lock_path).resolve(); base=lock_path.parent
    lock=json.loads(lock_path.read_text(encoding="utf-8")); all_rows=[]
    if {s.get("distribution_id") for s in lock.get("snapshots",[])} != {"445.1","446.1"}:
        raise BuildError("unparseable_pinned_source: lock must contain 445.1 and 446.1")
    specs={s["source_id"]:s for s in registry_sources(Path(__file__).parents[1]/"contracts/source_registry.json")}
    for snap in lock["snapshots"]:
        declared=Path(snap["cache_file"])
        if declared.is_absolute():
            path=declared.resolve()
        else:
            path=(base/declared).resolve()
            if not _inside(base,path):
                raise BuildError(f"unsafe_source_snapshot_path: {snap['source_id']}")
        if not path.is_file():
            raise BuildError(f"source_checksum_mismatch: {snap['source_id']}")
        data=path.read_bytes()
        if len(data)!=snap["byte_size"] or sha(data)!=snap["sha256"]:
            raise BuildError(f"source_checksum_mismatch: {snap['source_id']}")
        rows,facts=parse_source(data,specs[snap["source_id"]],snap["sha256"])
        if facts["actual_schema"]!=snap["actual_schema"] or facts["period_start"]!=snap["period_start"] or facts["period_end"]!=snap["period_end"]:
            raise BuildError(f"source_checksum_mismatch: declared facts changed for {snap['source_id']}")
        all_rows.extend(rows)
    paired=defaultdict(dict)
    for row in all_rows:
        paired[(row["period"],row["region_id"])][row["measure"]]=Decimal(row["nominal_value"])
    if any(v.get("CBA",Decimal(0))>v.get("CBT",Decimal("Infinity")) for v in paired.values()):
        raise BuildError("cba_exceeds_cbt")
    return lock,sorted(all_rows,key=lambda r:(r["period"],r["region_id"],r["measure"]))
