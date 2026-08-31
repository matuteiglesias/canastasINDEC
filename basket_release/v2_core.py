"""Opt-in regional-basket builder consuming IPC-Argentina curated v2 conversions.

Legacy basket construction remains untouched in ``core.py``. This module proves
an independent immutable handoff from ``research.argentina-monetary-conversion/v1``
without silently changing existing basket candidates.
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path, PurePosixPath

from .core import (
    BuildError,
    MEASURES,
    REGIONS,
    _write_csv,
    canonical_json,
    complete_core,
    sha,
    write_checksums,
)
from .portable_sources import load_portable_locked_sources

ARTIFACT_TYPE = "research.argentina-regional-baskets/v1"
INTEGRATION_ARTIFACT_TYPE = "research.argentina-regional-baskets-poverty-input/v1"
METHOD_ID = "research.argentina-regional-baskets/source-observed-plus-price-consensus-v2"
PRICE_ARTIFACT = "research.argentina-monetary-conversion/v1"
PRICE_METHOD = "research.argentina-price-consensus/curated-official-panel-v2"
MONETARY_REFERENCE_ID = "research.argentina-price-consensus/curated-official-panel-v2@2016-01=100"
WARNINGS = [
    "source_unit_metadata_wording_incomplete",
    "legacy_backcast_excluded",
    "synthetic_tail_excluded",
    "province_mapping_out_of_scope",
]


def _safe_file(root: Path, name: str) -> Path:
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts or name in {"", "."}:
        raise BuildError(f"corrupted_or_incompatible_price_release: unsafe path {name}")
    path = (root / name).resolve(); base = root.resolve()
    if base not in path.parents:
        raise BuildError(f"corrupted_or_incompatible_price_release: unsafe path {name}")
    return path


def _verify_v2_files(root: Path, manifest: dict) -> None:
    files = manifest.get("files", [])
    if not isinstance(files, list):
        raise BuildError("corrupted_or_incompatible_price_release: v2 file envelope")
    for identity in files:
        name = identity.get("path", "")
        path = _safe_file(root, name)
        if not path.is_file():
            raise BuildError(f"corrupted_or_incompatible_price_release: {name}")
        raw = path.read_bytes()
        if len(raw) != identity.get("size") or hashlib.sha256(raw).hexdigest() != identity.get("sha256"):
            raise BuildError(f"corrupted_or_incompatible_price_release: {name}")


def load_v2_price_release(
    root: Path,
    required: set[str],
    *,
    allow_thin_coverage: bool = False,
) -> tuple[dict, dict[str, tuple[str, str]], str, list[str]]:
    root = Path(root).resolve(); manifest_path = root / "manifest.json"
    manifest_bytes = manifest_path.read_bytes(); manifest = json.loads(manifest_bytes)
    if manifest.get("schema") != "research-artifact-manifest/v1":
        raise BuildError("corrupted_or_incompatible_price_release: manifest envelope")
    if manifest.get("artifact_type") != PRICE_ARTIFACT or manifest.get("method_id") != PRICE_METHOD:
        raise BuildError("corrupted_or_incompatible_price_release: artifact or method identity")
    if manifest.get("monetary_reference_id") != MONETARY_REFERENCE_ID:
        raise BuildError("corrupted_or_incompatible_price_release: incompatible monetary identity")
    _verify_v2_files(root, manifest)
    table = root / "monthly_conversion_factors.csv"
    if not table.is_file():
        raise BuildError("corrupted_or_incompatible_price_release: conversion table missing")
    with table.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    prices = {}
    for row in rows:
        period = row.get("period")
        value = row.get("consensus_index")
        coverage = row.get("coverage_class") or "unknown_coverage"
        approved = (row.get("approved_mode_eligible") or "").lower() == "true"
        if not period or value in (None, ""):
            continue
        d = Decimal(value)
        if not d.is_finite() or d <= 0:
            raise BuildError("corrupted_or_incompatible_price_release: invalid consensus index")
        if period in prices:
            raise BuildError("corrupted_or_incompatible_price_release: duplicate price period")
        prices[period] = (value, coverage, approved)
    missing = required - prices.keys()
    if missing:
        raise BuildError(f"missing_required_price_period: {sorted(missing)}")
    ineligible = sorted(p for p in required if not prices[p][2])
    accepted_thin = [p for p in ineligible if prices[p][1] == "thin_coverage"]
    rejected = [p for p in ineligible if p not in accepted_thin or not allow_thin_coverage]
    if rejected:
        raise BuildError(f"price_period_not_approved_mode_eligible: {rejected}")
    return (
        manifest,
        {p: (v[0], v[1]) for p, v in prices.items()},
        sha(manifest_bytes),
        accepted_thin,
    )


def build_v2(
    lock_path: Path,
    price_root: Path,
    output_parent: Path,
    integration_parent: Path | None = None,
    *,
    allow_thin_price_coverage: bool = False,
) -> tuple[Path, Path | None]:
    lock, source_rows = load_portable_locked_sources(lock_path); core, coverage = complete_core(source_rows)
    periods = {r["period"] for r in core}
    price_manifest, prices, price_hash, thin_periods = load_v2_price_release(
        price_root,
        periods | {"2016-01-01"},
        allow_thin_coverage=allow_thin_price_coverage,
    )
    inherited = list(price_manifest.get("warnings", []))
    warnings = WARNINGS + (["incomplete_period_omitted_outside_requested_slice"] if coverage["incomplete_periods"] else []) + (["price_candidate_has_provenance_warnings"] if inherited else []) + (["thin_price_coverage_accepted_for_candidate"] if thin_periods else [])
    provenance_time = max(s["retrieved_at_utc"] for s in lock["snapshots"])
    identity_seed = {"sources": [s["sha256"] for s in lock["snapshots"]], "price_manifest_sha256": price_hash, "method_id": METHOD_ID}
    release_id = "regional-baskets-v2-price-" + sha(canonical_json(identity_seed))[:16]
    root = Path(output_parent) / release_id
    if root.exists(): shutil.rmtree(root)
    root.mkdir(parents=True)
    nominal, referenced, lineage = [], [], []
    release_price, _ = prices["2016-01-01"]
    for r in core:
        base = (r["period"], r["region_id"])
        nominal.append({"period": base[0], "region_id": base[1], f"{r['measure']}_nominal": r["nominal_value"], "unit": r["unit"], "value_status": r["value_status"], f"{r['measure']}_source_identity": f"sha256:{r['source_snapshot_sha256']}#{r['source_cell_identity']}", "release_id": release_id})
        price, price_status = prices[r["period"]]
        value = Decimal(r["nominal_value"]) / Decimal(price) * Decimal(release_price)
        referenced.append({"period": base[0], "region_id": base[1], "measure": r["measure"], "value_2016_01": str(value), "unit": r["unit"], "monetary_reference_id": MONETARY_REFERENCE_ID, "value_status": "derived_monetary_conversion", "price_row_status": price_status, "release_id": release_id})
        lineage.append({"period": base[0], "region_id": base[1], "measure": r["measure"], "source_id": r["source_id"], "source_snapshot_sha256": r["source_snapshot_sha256"], "source_cell_identity": r["source_cell_identity"], "price_release_id": price_manifest["release_id"], "price_manifest_sha256": price_hash, "price_period": r["period"], "price_row_status": price_status, "formula": "nominal_value / consensus_index_at_period * consensus_index_2016_01"})
    pivot = {}
    for r in nominal:
        key=(r["period"],r["region_id"]); pivot.setdefault(key,{"period":key[0],"region_id":key[1],"unit":r["unit"],"value_status":"observed_source","release_id":release_id}); pivot[key].update({x:y for x,y in r.items() if x.startswith("CBA_") or x.startswith("CBT_")})
    nominal_rows=[pivot[k] for k in sorted(pivot)]
    quarterly=[]; groups=defaultdict(list)
    for r in referenced:
        d=datetime.strptime(r["period"],"%Y-%m-%d"); groups[(d.year,(d.month-1)//3+1,r["region_id"],r["measure"])].append(r)
    for (year,q,region,measure), rs in sorted(groups.items()):
        if len(rs)!=3: continue
        middle=(q-1)*3+2
        quarterly.append({"period":f"{year}-Q{q}","representative_date":f"{year}-{middle:02d}-15","region_id":region,"measure":measure,"value_2016_01":str(sum(Decimal(x["value_2016_01"]) for x in rs)/3),"unit":rs[0]["unit"],"monetary_reference_id":MONETARY_REFERENCE_ID,"value_status":"derived_quarterly_mean","monthly_input_periods":"|".join(x["period"] for x in rs),"price_release_id":price_manifest["release_id"],"release_id":release_id})
    _write_csv(root/"observed_nominal_monthly.csv",["period","region_id","CBA_nominal","CBT_nominal","unit","value_status","CBA_source_identity","CBT_source_identity","release_id"],nominal_rows)
    _write_csv(root/"reference_2016_01_monthly.csv",["period","region_id","measure","value_2016_01","unit","monetary_reference_id","value_status","price_row_status","release_id"],referenced)
    _write_csv(root/"reference_2016_01_quarterly.csv",["period","representative_date","region_id","measure","value_2016_01","unit","monetary_reference_id","value_status","monthly_input_periods","price_release_id","release_id"],quarterly)
    _write_csv(root/"cell_lineage.csv",["period","region_id","measure","source_id","source_snapshot_sha256","source_cell_identity","price_release_id","price_manifest_sha256","price_period","price_row_status","formula"],lineage)
    (root/"coverage.json").write_bytes(canonical_json(coverage)); (root/"source_lock.json").write_bytes(canonical_json(lock))
    dependency={"release_id":price_manifest["release_id"],"manifest_sha256":price_hash,"artifact_type":PRICE_ARTIFACT,"method_id":PRICE_METHOD,"monetary_reference_id":MONETARY_REFERENCE_ID,"warnings":inherited,"thin_coverage_periods_used":thin_periods,"eligibility_mode":"candidate_allow_thin" if thin_periods else "approved_only"}
    (root/"price_dependency_lock.json").write_bytes(canonical_json(dependency))
    qa={"result":"pass_with_warnings" if warnings else "pass","warnings":warnings,"hard_failures":[],"scientific_poverty_execution_performed":False}
    thin_note = ""
    if thin_periods:
        thin_note = " The candidate accepts explicitly labeled thin-coverage IPC rows for these required periods: " + ", ".join(thin_periods) + ". Those rows remain ineligible for approved-mode use."
    (root/"qa.json").write_bytes(canonical_json(qa)); (root/"limitations.md").write_text("# Limitations\n\nCandidate research artifact using the curated official-panel v2 monetary reference. It is not an official basket publication or poverty result. Six basket regions are not provincial indexes; Buenos Aires requires subprovincial classification between Gran Buenos Aires and Pampeana." + thin_note + "\n",encoding="utf-8")
    compatibility={"artifact_type":ARTIFACT_TYPE,"method_id":METHOD_ID,"monetary_reference_id":MONETARY_REFERENCE_ID,"geography_contract":"geography entity -> exactly one basket region_id","buenos_aires_requires_subprovincial_classification":True}
    (root/"compatibility.json").write_bytes(canonical_json(compatibility))
    payload_names=[p.name for p in root.iterdir()]
    files={n:{"bytes":(root/n).stat().st_size,"sha256":sha((root/n).read_bytes())} for n in sorted(payload_names)}
    manifest={"schema":"research-artifact-manifest/v1","artifact_type":ARTIFACT_TYPE,"release_id":release_id,"status":"candidate","method_id":METHOD_ID,"created_at_utc":provenance_time,"monetary_reference_id":MONETARY_REFERENCE_ID,"unit":"ARS_per_equivalent_adult","regions":list(REGIONS),"complete_core":{"start":coverage["complete_core_period_start"],"end":coverage["complete_core_period_end"]},"source_snapshot_identities":[s["sha256"] for s in lock["snapshots"]],"price_dependency":dependency,"warnings":warnings,"files":files}
    (root/"manifest.json").write_bytes(canonical_json(manifest)); write_checksums(root)
    validate_v2_candidate(root)
    bundle = build_v2_integration(root, integration_parent) if integration_parent else None
    return root, bundle


def _verify_candidate_files(root: Path, manifest: dict) -> None:
    for name, identity in manifest.get("files", {}).items():
        path=_safe_file(root,name)
        if not path.is_file() or path.stat().st_size!=identity.get("bytes") or sha(path.read_bytes())!=identity.get("sha256"):
            raise BuildError(f"corrupted candidate file: {name}")


def validate_v2_candidate(root: Path) -> dict:
    root=Path(root); manifest=json.loads((root/"manifest.json").read_text())
    if manifest.get("artifact_type")==INTEGRATION_ARTIFACT_TYPE:
        _verify_candidate_files(root,manifest)
        with (root/"regional_baskets.csv").open(newline="",encoding="utf-8") as handle: rows=list(csv.DictReader(handle))
        if len(rows)!=6 or {r["region_id"] for r in rows}!=set(REGIONS): raise BuildError("missing_required_region_or_measure_in_requested_slice")
        if any(r["period"]!="2024-Q1" or r["representative_date"]!="2024-02-15" or Decimal(r["CBA_2016_01"])>Decimal(r["CBT_2016_01"]) for r in rows): raise BuildError("invalid 2024-Q1 slice")
        if manifest.get("monetary_reference_id")!=MONETARY_REFERENCE_ID or manifest.get("scientific_poverty_execution_performed") is not False: raise BuildError("incompatible integration identity")
        return {"release_id":manifest["release_id"],"result":"compatible_with_warnings","warnings":manifest.get("warnings",[]),"rows":6}
    if manifest.get("artifact_type")!=ARTIFACT_TYPE or manifest.get("method_id")!=METHOD_ID or manifest.get("monetary_reference_id")!=MONETARY_REFERENCE_ID: raise BuildError("incompatible candidate identity")
    _verify_candidate_files(root,manifest)
    with (root/"observed_nominal_monthly.csv").open(newline="",encoding="utf-8") as handle: nominal=list(csv.DictReader(handle))
    with (root/"reference_2016_01_quarterly.csv").open(newline="",encoding="utf-8") as handle: quarterly=list(csv.DictReader(handle))
    if len({(r["period"],r["region_id"]) for r in nominal})!=len(nominal): raise BuildError("conflicting_duplicate")
    if any(set(x["region_id"] for x in nominal if x["period"]==p)!=set(REGIONS) for p in {x["period"] for x in nominal}): raise BuildError("missing_required_region_or_measure_in_requested_slice")
    if any(Decimal(r["CBA_nominal"])>Decimal(r["CBT_nominal"]) for r in nominal): raise BuildError("cba_exceeds_cbt")
    return {"release_id":manifest["release_id"],"result":"compatible_with_warnings" if manifest.get("warnings") else "compatible","warnings":manifest.get("warnings",[]),"monthly_rows":len(nominal),"quarterly_cells":len(quarterly)}


def build_v2_integration(release: Path, parent: Path) -> Path:
    validate_v2_candidate(release); manifest=json.loads((Path(release)/"manifest.json").read_text())
    with (Path(release)/"reference_2016_01_quarterly.csv").open(newline="",encoding="utf-8") as handle: rows=[r for r in csv.DictReader(handle) if r["period"]=="2024-Q1"]
    values={(r["region_id"],r["measure"]):r for r in rows}; missing=[(r,m) for r in REGIONS for m in MEASURES if (r,m) not in values]
    if missing: raise BuildError(f"missing_required_region_or_measure_in_requested_slice: 2024-Q1 {missing}")
    table=[{"period":"2024-Q1","representative_date":"2024-02-15","region_id":r,"CBA_2016_01":values[r,"CBA"]["value_2016_01"],"CBT_2016_01":values[r,"CBT"]["value_2016_01"],"unit":values[r,"CBA"]["unit"],"monetary_reference_id":MONETARY_REFERENCE_ID,"status":"candidate"} for r in REGIONS]
    bundle_id="poverty-baskets-v2-price-2024q1-"+sha(canonical_json(table))[:16]; root=Path(parent)/bundle_id
    if root.exists(): shutil.rmtree(root)
    root.mkdir(parents=True); _write_csv(root/"regional_baskets.csv",list(table[0]),table)
    shutil.copy(Path(release)/"compatibility.json",root/"compatibility.json"); shutil.copy(Path(release)/"limitations.md",root/"limitations.md")
    qa={"result":"pass_with_warnings","warnings":manifest["warnings"],"row_count":6,"scientific_poverty_execution_performed":False}; (root/"qa.json").write_bytes(canonical_json(qa))
    files={n:{"bytes":(root/n).stat().st_size,"sha256":sha((root/n).read_bytes())} for n in sorted(p.name for p in root.iterdir())}
    bundle_manifest={"schema":"research-artifact-manifest/v1","artifact_type":INTEGRATION_ARTIFACT_TYPE,"release_id":bundle_id,"status":"candidate","method_id":METHOD_ID,"source_basket_release_id":manifest["release_id"],"source_snapshot_identities":manifest["source_snapshot_identities"],"price_dependency":manifest["price_dependency"],"period":"2024-Q1","monthly_periods":["2024-01-01","2024-02-01","2024-03-01"],"quarterly_method":"arithmetic mean of three complete monthly values","representative_date":"2024-02-15","regions":list(REGIONS),"measures":list(MEASURES),"unit":"ARS_per_equivalent_adult","monetary_reference_id":MONETARY_REFERENCE_ID,"warnings":manifest["warnings"],"scientific_poverty_execution_performed":False,"files":files}
    (root/"manifest.json").write_bytes(canonical_json(bundle_manifest)); write_checksums(root); validate_v2_candidate(root); return root
