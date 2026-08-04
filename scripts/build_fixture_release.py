#!/usr/bin/env python3
"""Build a deterministic, mechanics-only regional basket fixture release."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOOD = ROOT / "fixtures/releases/synthetic-baskets"
BAD = ROOT / "fixtures/releases/tampered-baskets"
REGIONS = ("fixture_north", "fixture_south")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


monthly = []
for month, north, south in (("2020-01", (100, 220), (120, 252)), ("2020-02", (110, 242), (130, 273)), ("2020-03", (120, 264), (140, 294))):
    for region, values in zip(REGIONS, (north, south)):
        for measure, value in zip(("CBA", "CBT"), values):
            status = "observed"
            source_id = f"fixture-source:{month}:{region}:{measure}"
            warning = "synthetic demonstration; not a real threshold"
            if month == "2020-02" and region == "fixture_south" and measure == "CBA":
                value, status, source_id = 130, "imputed", ""
                warning += "; declared fixture imputation from adjacent months"
            monthly.append({"period": month, "region_id": region, "measure": measure, "value_ars": value, "status": status, "source_observation_id": source_id, "transformation_chain_id": "fixture-monthly/v1", "monetary_reference": "nominal-fixture-ARS", "methodology_version": "fixture/v1", "warnings": warning})

quarterly = []
for region in REGIONS:
    for measure in ("CBA", "CBT"):
        cells = [r for r in monthly if r["region_id"] == region and r["measure"] == measure]
        quarterly.append({"period": "2020-Q1", "region_id": region, "measure": measure, "value_ars": sum(int(r["value_ars"]) for r in cells) / 3, "status": "derived", "source_observation_id": "", "transformation_chain_id": "fixture-quarter-mean/v1", "monetary_reference": "nominal-fixture-ARS", "methodology_version": "fixture/v1", "warnings": "synthetic demonstration; input includes imputation" if any(r["status"] == "imputed" for r in cells) else "synthetic demonstration"})

referenced = []
for row in monthly:
    out = dict(row)
    out["value_ars"] = int(row["value_ars"]) * 2
    out["status"] = "derived"
    out["source_observation_id"] = ""
    out["transformation_chain_id"] = "fixture-reference-x2/v1"
    out["monetary_reference"] = "fixture-price-level-200"
    out["warnings"] += "; mechanics-only factor 2; input_status=" + str(row["status"])
    referenced.append(out)

fields = ["period", "region_id", "measure", "value_ars", "status", "source_observation_id", "transformation_chain_id", "monetary_reference", "methodology_version", "warnings"]
GOOD.mkdir(parents=True, exist_ok=True)
write_csv(GOOD / "monthly.csv", fields, monthly)
write_csv(GOOD / "quarterly.csv", fields, quarterly)
write_csv(GOOD / "reference.csv", fields, referenced)
region_dictionary = {"schema": "regional-basket-region-dictionary/v1", "id": "fixture-regions/v1", "regions": [{"id": r, "label": r.replace("_", " ").title()} for r in REGIONS], "coverage": {"required_each_period": list(REGIONS)}}
(GOOD / "regions.json").write_text(json.dumps(region_dictionary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

files = {name: {"sha256": digest(GOOD / name)} for name in ("monthly.csv", "quarterly.csv", "reference.csv", "regions.json")}
manifest = {
    "schema": "research-artifact-manifest/v1", "artifact_id": "fixture.regional-baskets-derived/v1", "release_id": "synthetic-baskets-2020q1-v1", "status": "synthetic",
    "files": files, "region_dictionary": {"path": "regions.json", "id": "fixture-regions/v1"},
    "coverage": {"period_start": "2020-01", "period_end": "2020-03", "frequency": "monthly_with_quarterly_derivative", "regions": list(REGIONS), "measures": ["CBA", "CBT"]},
    "unit": {"currency": "FIXTURE_ARS", "basis": "one fictional reference adult"},
    "monetary_reference": {"nominal": "nominal-fixture-ARS", "transformed": "fixture-price-level-200", "price_artifact_id": "fixture.price-index/v1", "price_artifact_sha256": hashlib.sha256(b"fixture-price-index:100,200\n").hexdigest(), "formula": "value * 200 / 100", "rounding": "exact integers"},
    "cell_status_policy": {"vocabulary": ["observed", "derived", "imputed", "interpolated", "projected", "synthetic", "unresolved"], "approved_allowed": ["observed", "derived"]},
    "warning": "Entire release is invented and demonstrates mechanics only; it is not an approved or real poverty threshold."
}
(GOOD / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

BAD.mkdir(parents=True, exist_ok=True)
(BAD / "monthly.csv").write_bytes((GOOD / "monthly.csv").read_bytes() + b"tampered\n")
bad = dict(manifest)
bad["release_id"] = "intentionally-invalid-tampered-v1"
(BAD / "manifest.json").write_text(json.dumps(bad, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"built {manifest['release_id']} ({len(monthly)} monthly cells, {len(quarterly)} quarterly cells, {len(referenced)} reference cells)")
