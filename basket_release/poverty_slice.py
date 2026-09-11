"""Build a period-parameterized poverty-input slice from a governed v2 basket release.

This is a bounded generalization of the historical 2024-Q1 integration helper.
It does not alter basket methodology or acquisition; it only selects one complete
quarter already present in ``reference_2016_01_quarterly.csv`` and packages the
six CBA/CBT regional cells for downstream poverty measurement.
"""
from __future__ import annotations

import csv
import json
import re
import shutil
from pathlib import Path

from .core import MEASURES, REGIONS, _write_csv, canonical_json, sha, write_checksums
from .v2_core import (
    INTEGRATION_ARTIFACT_TYPE,
    METHOD_ID,
    MONETARY_REFERENCE_ID,
    validate_v2_candidate,
)


class PovertySliceError(ValueError):
    pass


def _quarter_midpoint(period: str) -> tuple[str, str, list[str]]:
    match = re.fullmatch(r"(\d{4})-Q([1-4])", period)
    if not match:
        raise PovertySliceError("period must be YYYY-Q1..Q4")
    year = int(match.group(1))
    quarter = int(match.group(2))
    start = (quarter - 1) * 3 + 1
    months = [f"{year}-{m:02d}-01" for m in range(start, start + 3)]
    middle = start + 1
    return str(year), f"{year}-{middle:02d}-15", months


def build_poverty_slice(release: Path, output_parent: Path, *, period: str) -> Path:
    release = Path(release).resolve()
    output_parent = Path(output_parent).resolve()
    validate_v2_candidate(release)
    manifest = json.loads((release / "manifest.json").read_text())
    _, representative_date, monthly_periods = _quarter_midpoint(period)

    table_path = release / "reference_2016_01_quarterly.csv"
    with table_path.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row["period"] == period]
    values = {(row["region_id"], row["measure"]): row for row in rows}
    missing = [(region, measure) for region in REGIONS for measure in MEASURES if (region, measure) not in values]
    if missing:
        raise PovertySliceError(f"missing_required_region_or_measure_in_requested_slice: {period} {missing}")

    output_rows = []
    for region in REGIONS:
        cba = values[region, "CBA"]
        cbt = values[region, "CBT"]
        if cba["monetary_reference_id"] != MONETARY_REFERENCE_ID or cbt["monetary_reference_id"] != MONETARY_REFERENCE_ID:
            raise PovertySliceError("basket cell monetary reference mismatch")
        output_rows.append({
            "period": period,
            "representative_date": representative_date,
            "region_id": region,
            "CBA_2016_01": cba["value_2016_01"],
            "CBT_2016_01": cbt["value_2016_01"],
            "unit": cba["unit"],
            "monetary_reference_id": MONETARY_REFERENCE_ID,
            "status": "candidate",
        })

    bundle_id = f"poverty-baskets-v2-price-{period.lower()}-" + sha(canonical_json(output_rows))[:16]
    root = output_parent / bundle_id
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    _write_csv(root / "regional_baskets.csv", list(output_rows[0]), output_rows)
    for optional in ("compatibility.json", "limitations.md"):
        src = release / optional
        if src.exists():
            shutil.copy(src, root / optional)

    warnings = list(manifest.get("warnings", []))
    qa = {
        "result": "pass_with_warnings" if warnings else "pass",
        "warnings": warnings,
        "row_count": len(output_rows),
        "scientific_poverty_execution_performed": False,
        "period": period,
    }
    (root / "qa.json").write_bytes(canonical_json(qa))
    file_names = sorted(p.name for p in root.iterdir())
    files = {
        name: {"bytes": (root / name).stat().st_size, "sha256": sha((root / name).read_bytes())}
        for name in file_names
    }
    bundle_manifest = {
        "schema": "research-artifact-manifest/v1",
        "artifact_type": INTEGRATION_ARTIFACT_TYPE,
        "release_id": bundle_id,
        "status": "candidate",
        "method_id": METHOD_ID,
        "source_basket_release_id": manifest["release_id"],
        "source_snapshot_identities": manifest.get("source_snapshot_identities", []),
        "price_dependency": manifest.get("price_dependency"),
        "period": period,
        "monthly_periods": monthly_periods,
        "quarterly_method": "arithmetic mean of three complete monthly values",
        "representative_date": representative_date,
        "regions": list(REGIONS),
        "measures": list(MEASURES),
        "unit": "ARS_per_equivalent_adult",
        "monetary_reference_id": MONETARY_REFERENCE_ID,
        "warnings": warnings,
        "scientific_poverty_execution_performed": False,
        "files": files,
    }
    (root / "manifest.json").write_bytes(canonical_json(bundle_manifest))
    write_checksums(root)
    return root
