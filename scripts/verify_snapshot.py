#!/usr/bin/env python3
"""Verify structural and semantic boundaries of CB_Reg_defl_m.csv."""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
status = json.loads((ROOT / "DATA_STATUS.json").read_text(encoding="utf-8"))
artifact = ROOT / status["artifact"]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


if not artifact.is_file():
    fail(f"missing declared artifact: {artifact.relative_to(ROOT)}")

with artifact.open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))

required = {"Q", "Region", "CBA", "CBT"}
if not rows or not required.issubset(rows[0]):
    fail(f"expected columns {sorted(required)}")

periods = [date.fromisoformat(row["Q"]) for row in rows]
actual_max = max(periods).isoformat()
if actual_max != status["artifact_max_period"]:
    fail(
        "declared artifact_max_period does not match CSV: "
        f"declared={status['artifact_max_period']} actual={actual_max}"
    )

counts = Counter(row["Q"] for row in rows)
bad_counts = {period: count for period, count in counts.items() if count != 6}
if bad_counts:
    fail(f"expected six regional rows per period; mismatches={bad_counts}")

synthetic_from = date.fromisoformat(status["synthetic_tail_from"])
tail = defaultdict(list)
for row in rows:
    if date.fromisoformat(row["Q"]) >= synthetic_from:
        tail[row["Region"]].append((row["CBA"], row["CBT"]))

nonconstant_regions = [
    region for region, values in tail.items() if len(set(values)) != 1
]
if nonconstant_regions:
    fail(
        "declared synthetic tail no longer repeats one value per region; "
        f"review boundary for {nonconstant_regions}"
    )

print(
    json.dumps(
        {
            "artifact": status["artifact"],
            "rows": len(rows),
            "regions": sorted({row["Region"] for row in rows}),
            "artifact_begin": min(periods).isoformat(),
            "artifact_max_period": actual_max,
            "official_regional_source_begin_declared": status["source_nominal_regional_series_begin"],
            "synthetic_tail_from": status["synthetic_tail_from"],
            "semantic_warning": status["classification"],
            "result": "declared structure and synthetic-tail boundary match artifact",
        },
        indent=2,
    )
)
