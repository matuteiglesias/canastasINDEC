"""Source locking, normalization, immutable price consumption and release building.

Only the standard library is used so the integrity preflight always runs before a
dataframe library could load untrusted artifact content.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import shutil
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path, PurePosixPath

from . import ARTIFACT_TYPE, METHOD_ID, MONETARY_REFERENCE_ID

REGIONS = ("gran_buenos_aires", "cuyo", "noreste", "noroeste", "pampeana", "patagonia")
MEASURES = ("CBA", "CBT")
PRICE_ARTIFACT = "research.argentina-price-composite/v1"
PRICE_METHOD = "research.argentina-price-composite/legacy-compatible-v1"
WARNINGS = ["source_unit_metadata_wording_incomplete", "legacy_backcast_excluded", "synthetic_tail_excluded", "province_mapping_out_of_scope"]


class BuildError(ValueError):
    """A named hard failure from the candidate contract."""


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_name(name: str) -> None:
    p = PurePosixPath(name)
    if p.is_absolute() or ".." in p.parts or name in {"", "."}:
        raise BuildError(f"unsafe_path: {name}")


def registry_sources(registry: Path) -> list[dict]:
    doc = json.loads(registry.read_text(encoding="utf-8"))
    return [s for s in doc["sources"] if s.get("distribution_id") in {"445.1", "446.1"}]


def _period(value: str) -> str:
    value = value.strip()[:10]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%Y-%m"):
        try:
            d = datetime.strptime(value, fmt)
            return f"{d.year:04d}-{d.month:02d}-01"
        except ValueError:
            pass
    raise BuildError(f"unparseable_pinned_source: invalid period {value!r}")


def parse_source(data: bytes, spec: dict, snapshot_hash: str) -> tuple[list[dict], dict]:
    try:
        text = data.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        fields = reader.fieldnames or []
    except (UnicodeError, csv.Error) as exc:
        raise BuildError(f"unparseable_pinned_source: {exc}") from exc
    expected = [spec["expected_period_column"], *spec["expected_region_columns"]]
    if not set(expected).issubset(fields):
        raise BuildError(f"unparseable_pinned_source: expected {expected}, actual {fields}")
    measure = "CBA" if spec["artifact_role"].endswith("cba") else "CBT"
    rows, seen = [], {}
    for row_number, source_row in enumerate(reader, 2):
        period = _period(source_row[spec["expected_period_column"]])
        for column in spec["expected_region_columns"]:
            raw = source_row.get(column, "").strip()
            if not raw:
                continue
            try:
                value = Decimal(raw.replace(",", "."))
            except Exception as exc:
                raise BuildError(f"unparseable_pinned_source: row {row_number} column {column}") from exc
            if not value.is_finite() or value <= 0:
                raise BuildError(f"nonfinite_or_nonpositive_value: row {row_number} column {column}")
            key = (period, column, measure)
            if key in seen and seen[key] != raw:
                raise BuildError(f"conflicting_duplicate: {key}")
            if key in seen:
                continue
            seen[key] = raw
            rows.append({"period": period, "region_id": column, "measure": measure,
                         "nominal_value": raw, "unit": spec["candidate_unit"],
                         "value_status": "observed_source", "source_id": spec["source_id"],
                         "source_snapshot_sha256": snapshot_hash,
                         "source_cell_identity": f"row:{row_number};column:{column}",
                         "parser_id": "datos-gob-ar-regional-wide-csv/v1"})
    rows.sort(key=lambda r: (r["period"], r["region_id"], r["measure"]))
    coverage = sorted({r["period"] for r in rows})
    return rows, {"actual_schema": fields, "period_start": coverage[0] if coverage else None,
                  "period_end": coverage[-1] if coverage else None, "row_count": len(rows)}


def acquire(registry: Path, cache: Path, write_lock: Path | None = None) -> dict:
    cache.mkdir(parents=True, exist_ok=True)
    snapshots = []
    for spec in registry_sources(registry):
        url = spec["retrieval"]["url"]
        request = urllib.request.Request(url, headers={"User-Agent": "canastasINDEC-source-lock/1"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data, resolved = response.read(), response.geturl()
                headers = {k.lower(): v for k, v in response.headers.items() if k.lower() in {"content-type", "etag", "last-modified"}}
        except Exception as exc:
            raise BuildError(f"source_unavailable: {spec['distribution_id']}: {exc}") from exc
        digest = sha(data)
        path = cache / f"{spec['distribution_id']}-{digest}.csv"
        path.write_bytes(data)
        _, facts = parse_source(data, spec, digest)
        snapshots.append({"source_id": spec["source_id"], "dataset_id": spec["dataset_id"],
            "distribution_id": spec["distribution_id"], "dataset_page": spec["dataset_page"],
            "requested_url": url, "resolved_url": resolved,
            "retrieved_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "byte_size": len(data), "sha256": digest, "http_headers": headers,
            "parser_id": "datos-gob-ar-regional-wide-csv/v1", **facts,
            "publisher": spec["authority"], "publisher_catalog": spec["publisher_catalog"],
            "license": spec["license"], "unit_metadata": spec.get("unit_verification_policy"),
            "cache_file": str(path.resolve())})
    lock = {"schema": "regional-basket-source-lock/v1", "snapshots": snapshots}
    if write_lock:
        write_lock.parent.mkdir(parents=True, exist_ok=True)
        write_lock.write_bytes(canonical_json(lock))
    return lock


def load_locked_sources(lock_path: Path) -> tuple[dict, list[dict]]:
    lock = json.loads(lock_path.read_text(encoding="utf-8")); all_rows = []
    if {s.get("distribution_id") for s in lock.get("snapshots", [])} != {"445.1", "446.1"}:
        raise BuildError("unparseable_pinned_source: lock must contain 445.1 and 446.1")
    specs = {s["source_id"]: s for s in registry_sources(Path(__file__).parents[1] / "contracts/source_registry.json")}
    for snap in lock["snapshots"]:
        path = Path(snap["cache_file"])
        data = path.read_bytes()
        if len(data) != snap["byte_size"] or sha(data) != snap["sha256"]:
            raise BuildError(f"source_checksum_mismatch: {snap['source_id']}")
        rows, facts = parse_source(data, specs[snap["source_id"]], snap["sha256"])
        if facts["actual_schema"] != snap["actual_schema"] or facts["period_start"] != snap["period_start"] or facts["period_end"] != snap["period_end"]:
            raise BuildError(f"source_checksum_mismatch: declared facts changed for {snap['source_id']}")
        all_rows.extend(rows)
    paired = defaultdict(dict)
    for row in all_rows: paired[(row["period"], row["region_id"])][row["measure"]] = Decimal(row["nominal_value"])
    if any(v.get("CBA", Decimal(0)) > v.get("CBT", Decimal("Infinity")) for v in paired.values()):
        raise BuildError("cba_exceeds_cbt")
    return lock, sorted(all_rows, key=lambda r: (r["period"], r["region_id"], r["measure"]))


def verify_files(root: Path, manifest: dict) -> None:
    for name, identity in manifest.get("files", {}).items():
        safe_name(name); path = root / name
        if not path.is_file() or path.stat().st_size != identity.get("bytes") or sha(path.read_bytes()) != identity.get("sha256"):
            raise BuildError(f"corrupted_or_incompatible_price_release: {name}")


def load_price_release(root: Path, required: set[str]) -> tuple[dict, dict[str, tuple[str, str]], str]:
    manifest_path = root / "manifest.json"
    manifest_bytes = manifest_path.read_bytes(); manifest = json.loads(manifest_bytes)
    if manifest.get("schema") not in {"research-artifact-manifest/v1", "research-artifact-manifest/v1.0"}:
        raise BuildError("corrupted_or_incompatible_price_release: manifest envelope")
    verify_files(root, manifest)
    if manifest.get("artifact_type", manifest.get("artifact_id")) != PRICE_ARTIFACT or manifest.get("method_id") != PRICE_METHOD:
        raise BuildError("corrupted_or_incompatible_price_release: artifact or method identity")
    ref = manifest.get("monetary_reference_id") or manifest.get("monetary_reference", {}).get("id")
    if ref != MONETARY_REFERENCE_ID:
        raise BuildError("corrupted_or_incompatible_price_release: incompatible monetary identity")
    candidates = [n for n in manifest["files"] if n.endswith(".csv") and ("month" in n.lower() or "price" in n.lower() or "indice" in n.lower())]
    if not candidates: raise BuildError("corrupted_or_incompatible_price_release: no monthly price table")
    with (root / candidates[0]).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    prices = {}
    for r in rows:
        period_raw = r.get("period") or r.get("date") or r.get("indice_tiempo")
        value = r.get("price_index") or r.get("value") or r.get("indice_precios")
        status = r.get("value_status") or r.get("status") or "observed"
        if not period_raw or value is None: continue
        period = _period(period_raw)
        d = Decimal(value)
        if not d.is_finite() or d <= 0: raise BuildError("corrupted_or_incompatible_price_release: invalid price")
        if period in prices: raise BuildError("corrupted_or_incompatible_price_release: duplicate price period")
        prices[period] = (value, status)
    missing = required - prices.keys()
    if missing: raise BuildError(f"missing_required_price_period: {sorted(missing)}")
    forbidden = {p for p in required if prices[p][1].lower() in {"projected", "projection", "forecast", "synthetic"}}
    if forbidden: raise BuildError(f"projected_price_used_for_core_conversion: {sorted(forbidden)}")
    return manifest, prices, sha(manifest_bytes)


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fields, lineterminator="\n"); w.writeheader(); w.writerows(rows)


def complete_core(rows: list[dict]) -> tuple[list[dict], dict]:
    cells = {(r["period"], r["region_id"], r["measure"]): r for r in rows}
    periods = sorted({r["period"] for r in rows}); complete, incomplete = [], []
    required_cells = [(region, measure) for region in REGIONS for measure in MEASURES]
    for p in periods:
        missing = [{"region_id": r, "measure": m} for r, m in required_cells if (p, r, m) not in cells]
        if missing: incomplete.append({"period": p, "missing_cells": missing})
        else: complete.extend(cells[p, r, m] for r, m in required_cells)
    complete_periods = sorted({r["period"] for r in complete})
    counts = Counter((r["source_id"], r["measure"], r["region_id"], r["value_status"]) for r in rows)
    coverage = {"actual_raw_period_start": periods[0], "actual_raw_period_end": periods[-1],
        "complete_core_period_start": complete_periods[0] if complete_periods else None,
        "complete_core_period_end": complete_periods[-1] if complete_periods else None,
        "complete_core_month_count": len(complete_periods), "incomplete_periods": incomplete,
        "counts": [{"source_id": k[0], "measure": k[1], "region_id": k[2], "status": k[3], "count": v} for k, v in sorted(counts.items())]}
    return complete, coverage


def build(lock_path: Path, price_root: Path, output_parent: Path, integration_parent: Path | None = None) -> tuple[Path, Path | None]:
    lock, source_rows = load_locked_sources(lock_path); core, coverage = complete_core(source_rows)
    periods = {r["period"] for r in core}
    price_manifest, prices, price_hash = load_price_release(price_root, periods | {"2016-01-01"})
    inherited = list(price_manifest.get("warnings", []))
    warnings = WARNINGS + (["incomplete_period_omitted_outside_requested_slice"] if coverage["incomplete_periods"] else []) + (["price_candidate_has_provenance_warnings"] if inherited else [])
    provenance_time = max(s["retrieved_at_utc"] for s in lock["snapshots"])
    identity_seed = {"sources": [s["sha256"] for s in lock["snapshots"]], "price_manifest_sha256": price_hash, "method_id": METHOD_ID}
    release_id = "regional-baskets-" + sha(canonical_json(identity_seed))[:16]
    root = output_parent / release_id
    if root.exists(): shutil.rmtree(root)
    root.mkdir(parents=True)
    nominal, referenced, lineage = [], [], []
    release_price, _ = prices["2016-01-01"]
    for r in core:
        base = (r["period"], r["region_id"]); nominal.append({"period": base[0], "region_id": base[1],
            f"{r['measure']}_nominal": r["nominal_value"], "unit": r["unit"], "value_status": r["value_status"],
            f"{r['measure']}_source_identity": f"sha256:{r['source_snapshot_sha256']}#{r['source_cell_identity']}", "release_id": release_id})
        price, price_status = prices[r["period"]]
        value = Decimal(r["nominal_value"]) / Decimal(price) * Decimal(release_price)
        referenced.append({"period": base[0], "region_id": base[1], "measure": r["measure"], "value_2016_01": str(value),
            "unit": r["unit"], "monetary_reference_id": MONETARY_REFERENCE_ID, "value_status": "derived_monetary_conversion",
            "price_row_status": price_status, "release_id": release_id})
        lineage.append({"period": base[0], "region_id": base[1], "measure": r["measure"], "source_id": r["source_id"],
            "source_snapshot_sha256": r["source_snapshot_sha256"], "source_cell_identity": r["source_cell_identity"],
            "price_release_id": price_manifest["release_id"], "price_manifest_sha256": price_hash,
            "price_period": r["period"], "price_row_status": price_status,
            "formula": "nominal_value / price_index_at_period * price_index_2016_01"})
    # Pivot nominal without changing the source strings.
    pivot = {}
    for r in nominal:
        k=(r["period"],r["region_id"]); pivot.setdefault(k,{"period":k[0],"region_id":k[1],"unit":r["unit"],"value_status":"observed_source","release_id":release_id}); pivot[k].update({x:y for x,y in r.items() if x.startswith("CBA_") or x.startswith("CBT_")})
    nominal_rows=[pivot[k] for k in sorted(pivot)]
    quarterly=[]; groups=defaultdict(list)
    for r in referenced:
        d=datetime.strptime(r["period"],"%Y-%m-%d"); groups[(d.year,(d.month-1)//3+1,r["region_id"],r["measure"])].append(r)
    for (year,q,region,measure), rs in sorted(groups.items()):
        if len(rs)!=3: continue
        middle=(q-1)*3+2
        quarterly.append({"period":f"{year}-Q{q}","representative_date":f"{year}-{middle:02d}-15","region_id":region,"measure":measure,
            "value_2016_01":str(sum(Decimal(x["value_2016_01"]) for x in rs)/3),"unit":rs[0]["unit"],"monetary_reference_id":MONETARY_REFERENCE_ID,
            "value_status":"derived_quarterly_mean","monthly_input_periods":"|".join(x["period"] for x in rs),"price_release_id":price_manifest["release_id"],"release_id":release_id})
    _write_csv(root/"observed_nominal_monthly.csv",["period","region_id","CBA_nominal","CBT_nominal","unit","value_status","CBA_source_identity","CBT_source_identity","release_id"],nominal_rows)
    _write_csv(root/"reference_2016_01_monthly.csv",["period","region_id","measure","value_2016_01","unit","monetary_reference_id","value_status","price_row_status","release_id"],referenced)
    _write_csv(root/"reference_2016_01_quarterly.csv",["period","representative_date","region_id","measure","value_2016_01","unit","monetary_reference_id","value_status","monthly_input_periods","price_release_id","release_id"],quarterly)
    _write_csv(root/"cell_lineage.csv",["period","region_id","measure","source_id","source_snapshot_sha256","source_cell_identity","price_release_id","price_manifest_sha256","price_period","price_row_status","formula"],lineage)
    (root/"coverage.json").write_bytes(canonical_json(coverage)); (root/"source_lock.json").write_bytes(canonical_json(lock))
    dependency={"release_id":price_manifest["release_id"],"manifest_sha256":price_hash,"artifact_type":PRICE_ARTIFACT,"method_id":PRICE_METHOD,"monetary_reference_id":MONETARY_REFERENCE_ID,"warnings":inherited}
    (root/"price_dependency_lock.json").write_bytes(canonical_json(dependency))
    qa={"result":"pass_with_warnings" if warnings else "pass","warnings":warnings,"hard_failures":[],"scientific_poverty_execution_performed":False}
    (root/"qa.json").write_bytes(canonical_json(qa)); (root/"limitations.md").write_text("# Limitations\n\nCandidate research artifact, not an official basket publication or poverty result. Legacy imputation and synthetic tails are excluded. Six basket regions are not provincial indexes; Buenos Aires requires subprovincial classification between Gran Buenos Aires and Pampeana.\n",encoding="utf-8")
    compatibility={"artifact_type":ARTIFACT_TYPE,"method_id":METHOD_ID,"monetary_reference_id":MONETARY_REFERENCE_ID,"geography_contract":"geography entity -> exactly one basket region_id","buenos_aires_requires_subprovincial_classification":True}
    (root/"compatibility.json").write_bytes(canonical_json(compatibility))
    payload_names=[p.name for p in root.iterdir()]
    files={n:{"bytes":(root/n).stat().st_size,"sha256":sha((root/n).read_bytes())} for n in sorted(payload_names)}
    manifest={"schema":"research-artifact-manifest/v1","artifact_type":ARTIFACT_TYPE,"release_id":release_id,"status":"candidate","method_id":METHOD_ID,"created_at_utc":provenance_time,"monetary_reference_id":MONETARY_REFERENCE_ID,"unit":"ARS_per_equivalent_adult","regions":list(REGIONS),"complete_core":{"start":coverage["complete_core_period_start"],"end":coverage["complete_core_period_end"]},"source_snapshot_identities":[s["sha256"] for s in lock["snapshots"]],"price_dependency":dependency,"warnings":warnings,"files":files}
    (root/"manifest.json").write_bytes(canonical_json(manifest)); write_checksums(root)
    validate_candidate(root)
    bundle = build_integration(root, integration_parent) if integration_parent else None
    return root, bundle


def write_checksums(root: Path) -> None:
    names=sorted(p.name for p in root.iterdir() if p.is_file() and p.name!="checksums.sha256")
    (root/"checksums.sha256").write_text("".join(f"{sha((root/n).read_bytes())}  {n}\n" for n in names),encoding="utf-8")


def validate_candidate(root: Path) -> dict:
    manifest=json.loads((root/"manifest.json").read_text());
    if manifest.get("artifact_type")=="research.argentina-regional-baskets-poverty-input/v1":
        verify_files(root,manifest)
        with (root/"regional_baskets.csv").open(newline="",encoding="utf-8") as h: rows=list(csv.DictReader(h))
        if len(rows)!=6 or {r["region_id"] for r in rows}!=set(REGIONS): raise BuildError("missing_required_region_or_measure_in_requested_slice")
        if any(r["period"]!="2024-Q1" or r["representative_date"]!="2024-02-15" or Decimal(r["CBA_2016_01"])>Decimal(r["CBT_2016_01"]) for r in rows): raise BuildError("invalid 2024-Q1 slice")
        if manifest.get("monetary_reference_id")!=MONETARY_REFERENCE_ID or manifest.get("scientific_poverty_execution_performed") is not False: raise BuildError("incompatible integration identity")
        return {"release_id":manifest["release_id"],"result":"compatible_with_warnings","warnings":manifest.get("warnings",[]),"rows":6}
    if manifest.get("artifact_type")!=ARTIFACT_TYPE or manifest.get("method_id")!=METHOD_ID or manifest.get("monetary_reference_id")!=MONETARY_REFERENCE_ID: raise BuildError("incompatible candidate identity")
    verify_files(root,manifest)
    with (root/"observed_nominal_monthly.csv").open(newline="",encoding="utf-8") as h: nominal=list(csv.DictReader(h))
    with (root/"reference_2016_01_quarterly.csv").open(newline="",encoding="utf-8") as h: quarterly=list(csv.DictReader(h))
    for rows, a,b in ((nominal,"CBA_nominal","CBT_nominal"),):
        if len({(r["period"],r["region_id"]) for r in rows})!=len(rows): raise BuildError("conflicting_duplicate")
        if any(set(x["region_id"] for x in rows if x["period"]==p)!=set(REGIONS) for p in {x["period"] for x in rows}): raise BuildError("missing_required_region_or_measure_in_requested_slice")
        if any(Decimal(r[a])>Decimal(r[b]) for r in rows): raise BuildError("cba_exceeds_cbt")
    return {"release_id":manifest["release_id"],"result":"compatible_with_warnings" if manifest.get("warnings") else "compatible","warnings":manifest.get("warnings",[]),"monthly_rows":len(nominal),"quarterly_cells":len(quarterly)}


def build_integration(release: Path, parent: Path) -> Path:
    validate_candidate(release); manifest=json.loads((release/"manifest.json").read_text())
    with (release/"reference_2016_01_quarterly.csv").open(newline="",encoding="utf-8") as h: rows=[r for r in csv.DictReader(h) if r["period"]=="2024-Q1"]
    values={(r["region_id"],r["measure"]):r for r in rows}
    missing=[(r,m) for r in REGIONS for m in MEASURES if (r,m) not in values]
    if missing: raise BuildError(f"missing_required_region_or_measure_in_requested_slice: 2024-Q1 {missing}")
    table=[{"period":"2024-Q1","representative_date":"2024-02-15","region_id":r,"CBA_2016_01":values[r,"CBA"]["value_2016_01"],"CBT_2016_01":values[r,"CBT"]["value_2016_01"],"unit":values[r,"CBA"]["unit"],"monetary_reference_id":MONETARY_REFERENCE_ID,"status":"candidate"} for r in REGIONS]
    bundle_id="poverty-baskets-2024q1-"+sha(canonical_json(table))[:16]; root=parent/bundle_id
    if root.exists(): shutil.rmtree(root)
    root.mkdir(parents=True); _write_csv(root/"regional_baskets.csv",list(table[0]),table)
    shutil.copy(release/"compatibility.json",root/"compatibility.json")
    shutil.copy(release/"limitations.md",root/"limitations.md")
    qa={"result":"pass_with_warnings","warnings":manifest["warnings"],"row_count":6,"scientific_poverty_execution_performed":False}; (root/"qa.json").write_bytes(canonical_json(qa))
    files={n:{"bytes":(root/n).stat().st_size,"sha256":sha((root/n).read_bytes())} for n in sorted(p.name for p in root.iterdir())}
    bm={"schema":"research-artifact-manifest/v1","artifact_type":"research.argentina-regional-baskets-poverty-input/v1","release_id":bundle_id,"status":"candidate","source_basket_release_id":manifest["release_id"],"source_snapshot_identities":manifest["source_snapshot_identities"],"price_dependency":manifest["price_dependency"],"period":"2024-Q1","monthly_periods":["2024-01-01","2024-02-01","2024-03-01"],"quarterly_method":"arithmetic mean of three complete monthly values","representative_date":"2024-02-15","regions":list(REGIONS),"measures":list(MEASURES),"unit":"ARS_per_equivalent_adult","monetary_reference_id":MONETARY_REFERENCE_ID,"warnings":manifest["warnings"],"scientific_poverty_execution_performed":False,"files":files}
    (root/"manifest.json").write_bytes(canonical_json(bm)); write_checksums(root); return root
