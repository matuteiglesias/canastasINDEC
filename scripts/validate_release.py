#!/usr/bin/env python3
"""Standard-library compatibility validator for regional basket releases."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path, PurePosixPath

VOCABULARY = {"observed", "derived", "imputed", "interpolated", "projected", "synthetic", "unresolved"}


def fail(message: str) -> None:
    raise ValueError(message)


def validate(manifest_path: Path, approved: bool = False) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "research-artifact-manifest/v1": fail("unsupported manifest schema")
    if manifest.get("status") not in {"synthetic", "candidate", "reviewed", "approved"}: fail("invalid release status")
    if approved and manifest["status"] != "approved": fail("approved mode requires approved manifest")
    root = manifest_path.parent
    for name, identity in manifest.get("files", {}).items():
        pure = PurePosixPath(name)
        if pure.is_absolute() or ".." in pure.parts: fail(f"unsafe file path: {name}")
        path = root / name
        if not path.is_file(): fail(f"missing immutable file: {name}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != identity.get("sha256"): fail(f"hash mismatch: {name}")
    rd = manifest.get("region_dictionary", {})
    dictionary = json.loads((root / rd.get("path", "")).read_text(encoding="utf-8"))
    if dictionary.get("id") != rd.get("id"): fail("region dictionary identity mismatch")
    regions = set(manifest["coverage"]["regions"])
    if regions != {r["id"] for r in dictionary["regions"]}: fail("manifest/dictionary region mismatch")
    if manifest["unit"].get("basis") is None or manifest["unit"].get("currency") is None: fail("unit contract incomplete")
    monetary = manifest.get("monetary_reference", {})
    if not monetary.get("price_artifact_id") or not monetary.get("price_artifact_sha256"): fail("price artifact identity incomplete")
    counts: Counter[str] = Counter()
    allowed = set(manifest["cell_status_policy"]["approved_allowed"])
    for filename in ("monthly.csv", "quarterly.csv", "reference.csv"):
        with (root / filename).open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        required = {"period", "region_id", "measure", "value_ars", "status", "source_observation_id", "transformation_chain_id", "monetary_reference", "methodology_version", "warnings"}
        if not rows or not required.issubset(rows[0]): fail(f"cell contract incomplete: {filename}")
        keys = [(r["period"], r["region_id"], r["measure"]) for r in rows]
        if len(keys) != len(set(keys)): fail(f"duplicate cell keys: {filename}")
        for row in rows:
            if row["region_id"] not in regions or row["measure"] not in {"CBA", "CBT"}: fail(f"invalid region/measure: {filename}")
            if row["status"] not in VOCABULARY: fail(f"invalid cell status: {filename}")
            if approved and row["status"] not in allowed: fail(f"cell status forbidden in approved mode: {row['status']}")
            if row["status"] == "observed" and not row["source_observation_id"]: fail("observed cell lacks source ID")
            counts[row["status"]] += 1
        by_period = Counter((r["period"], r["measure"]) for r in rows)
        if any(n != len(regions) for n in by_period.values()): fail(f"incomplete region-period-measure coverage: {filename}")
        if any(float(r["value_ars"]) <= 0 for r in rows): fail(f"non-positive value: {filename}")
        paired = {(r["period"], r["region_id"]): {} for r in rows}
        for row in rows: paired[(row["period"], row["region_id"])][row["measure"]] = float(row["value_ars"])
        if any(set(v) != {"CBA", "CBT"} or v["CBA"] > v["CBT"] for v in paired.values()): fail(f"CBA/CBT ordering or pairing failure: {filename}")
    return {"release_id": manifest["release_id"], "status": manifest["status"], "cell_status_counts": dict(sorted(counts.items())), "result": "compatible"}


if __name__ == "__main__":
    try:
        result = validate(Path(sys.argv[1]), "--approved" in sys.argv[2:])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps(result, indent=2))
