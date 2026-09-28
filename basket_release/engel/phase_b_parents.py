"""Immutable parent loaders for Engel Phase B."""
from __future__ import annotations

import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path, PurePosixPath

from basket_release.core import BuildError
from basket_release.v2_core import (
    ARTIFACT_TYPE as BASKET_ARTIFACT_TYPE,
    METHOD_ID as BASKET_METHOD_ID,
)
from .artifact import validate_reference_artifact
from .contracts import ARTIFACT_TYPE as REFERENCE_ARTIFACT_TYPE, METHOD_ID as REFERENCE_METHOD_ID
from .trajectory_contracts import (
    BASE_PERIOD,
    DIVISION_IDS,
    IPC_ARTIFACT_TYPE,
    IPC_INDEX_BASE,
    IPC_VALUE_STATUS,
    REGIONS,
    WINDOW_END,
    WINDOW_START,
)


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def month_sequence(start: str=WINDOW_START, end: str=WINDOW_END) -> list[str]:
    y,m=map(int,start[:7].split("-")); ey,em=map(int,end[:7].split("-"))
    out=[]
    while (y,m)<=(ey,em):
        out.append(f"{y:04d}-{m:02d}-01")
        m+=1
        if m==13: y+=1; m=1
    return out


def _safe(root: Path, relative: str) -> Path:
    pure=PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or relative in {"","."}:
        raise BuildError(f"engel_phase_b_unsafe_parent_path:{relative}")
    path=(root/relative).resolve()
    if root.resolve() not in path.parents:
        raise BuildError(f"engel_phase_b_unsafe_parent_path:{relative}")
    return path


def load_reference_parent(root: Path) -> dict:
    root=Path(root).expanduser().resolve()
    validation=validate_reference_artifact(root)
    manifest_bytes=(root/"manifest.json").read_bytes()
    manifest=json.loads(manifest_bytes)
    if manifest.get("artifact_type")!=REFERENCE_ARTIFACT_TYPE or manifest.get("method_id")!=REFERENCE_METHOD_ID:
        raise BuildError("engel_phase_b_reference_parent_identity_mismatch")
    if manifest.get("base_period")!="2018-05":
        raise BuildError("engel_phase_b_reference_parent_base_mismatch")
    with (root/"reference_structure.csv").open(newline="",encoding="utf-8") as h:
        rows=list(csv.DictReader(h))
    regional=[r for r in rows if r["region_id"]!="national"]
    if {r["region_id"] for r in regional}!=set(REGIONS) or len(regional)!=len(REGIONS):
        raise BuildError("engel_phase_b_reference_region_inventory_mismatch")
    return {
        "root":root,
        "manifest":manifest,
        "manifest_sha256":hashlib.sha256(manifest_bytes).hexdigest(),
        "release_id":manifest["release_id"],
        "rows":{r["region_id"]:r for r in regional},
        "warnings":list(manifest.get("warnings") or []),
        "validation":validation,
    }


def load_ipc_parent(root: Path) -> dict:
    root=Path(root).expanduser().resolve()
    manifest_path=root/"manifest.json"
    if not manifest_path.is_file():
        raise BuildError("engel_phase_b_ipc_manifest_missing")
    manifest_bytes=manifest_path.read_bytes(); manifest=json.loads(manifest_bytes)
    if manifest.get("artifact_type")!=IPC_ARTIFACT_TYPE:
        raise BuildError("engel_phase_b_ipc_wrong_artifact")
    files=manifest.get("files")
    if not isinstance(files,list):
        raise BuildError("engel_phase_b_ipc_invalid_file_envelope")
    for item in files:
        path=_safe(root,item.get("path",""))
        if not path.is_file() or path.stat().st_size!=item.get("size") or sha256(path)!=item.get("sha256"):
            raise BuildError(f"engel_phase_b_ipc_file_mismatch:{item.get('path')}")
    table=root/"regional_division_indices.csv"
    if not table.is_file():
        raise BuildError("engel_phase_b_ipc_table_missing")
    with table.open(newline="",encoding="utf-8") as h:
        rows=list(csv.DictReader(h))
    expected_periods=set(month_sequence())
    seen={}
    for row in rows:
        period=row.get("period"); region=row.get("region_id"); division=row.get("division_id")
        if period not in expected_periods:
            continue
        if region not in REGIONS:
            raise BuildError(f"engel_phase_b_ipc_unknown_region:{region}")
        if division not in DIVISION_IDS:
            raise BuildError(f"engel_phase_b_ipc_unknown_division:{division}")
        if row.get("index_base")!=IPC_INDEX_BASE or row.get("value_status")!=IPC_VALUE_STATUS:
            raise BuildError("engel_phase_b_ipc_nonofficial_or_wrong_base")
        key=(period,region,division)
        if key in seen:
            raise BuildError(f"engel_phase_b_ipc_duplicate_cell:{key}")
        try: value=Decimal(row["index_value"])
        except Exception as exc: raise BuildError("engel_phase_b_ipc_invalid_value") from exc
        if not value.is_finite() or value<=0:
            raise BuildError("engel_phase_b_ipc_invalid_value")
        seen[key]={**row,"index_decimal":value}
    expected={(p,r,d) for p in expected_periods for r in REGIONS for d in DIVISION_IDS}
    missing=expected-set(seen)
    if missing:
        sample=sorted(missing)[:10]
        raise BuildError(f"engel_phase_b_ipc_required_window_missing:{sample}:count={len(missing)}")
    return {
        "root":root,
        "manifest":manifest,
        "manifest_sha256":hashlib.sha256(manifest_bytes).hexdigest(),
        "release_id":manifest["release_id"],
        "rows":seen,
        "periods":month_sequence(),
    }


def load_official_basket_parent(root: Path) -> dict:
    root=Path(root).expanduser().resolve()
    manifest_path=root/"manifest.json"
    if not manifest_path.is_file():
        raise BuildError("engel_phase_b_basket_manifest_missing")
    manifest_bytes=manifest_path.read_bytes(); manifest=json.loads(manifest_bytes)
    if manifest.get("artifact_type")!=BASKET_ARTIFACT_TYPE or manifest.get("method_id")!=BASKET_METHOD_ID:
        raise BuildError("engel_phase_b_basket_identity_mismatch")
    files=manifest.get("files")
    if not isinstance(files,dict):
        raise BuildError("engel_phase_b_basket_invalid_file_envelope")
    for name,item in files.items():
        path=_safe(root,name)
        if not path.is_file() or path.stat().st_size!=item.get("bytes") or sha256(path)!=item.get("sha256"):
            raise BuildError(f"engel_phase_b_basket_file_mismatch:{name}")
    table=root/"observed_nominal_monthly.csv"
    if not table.is_file():
        raise BuildError("engel_phase_b_basket_nominal_table_missing")
    expected_periods=set(month_sequence())
    seen={}
    with table.open(newline="",encoding="utf-8") as h:
        for row in csv.DictReader(h):
            period=row.get("period"); region=row.get("region_id")
            if period not in expected_periods:
                continue
            if region not in REGIONS:
                raise BuildError(f"engel_phase_b_basket_unknown_region:{region}")
            key=(period,region)
            if key in seen:
                raise BuildError(f"engel_phase_b_basket_duplicate_cell:{key}")
            try:
                cba=Decimal(row["CBA_nominal"]); cbt=Decimal(row["CBT_nominal"])
            except Exception as exc:
                raise BuildError("engel_phase_b_basket_invalid_nominal_value") from exc
            if not cba.is_finite() or not cbt.is_finite() or cba<=0 or cbt<=0 or cba>cbt:
                raise BuildError("engel_phase_b_basket_invalid_nominal_value")
            seen[key]={**row,"cba_decimal":cba,"cbt_decimal":cbt}
    expected={(p,r) for p in expected_periods for r in REGIONS}
    missing=expected-set(seen)
    if missing:
        raise BuildError(f"engel_phase_b_basket_required_window_missing:{sorted(missing)[:10]}:count={len(missing)}")
    return {
        "root":root,
        "manifest":manifest,
        "manifest_sha256":hashlib.sha256(manifest_bytes).hexdigest(),
        "release_id":manifest["release_id"],
        "rows":seen,
        "warnings":list(manifest.get("warnings") or []),
        "periods":month_sequence(),
    }
