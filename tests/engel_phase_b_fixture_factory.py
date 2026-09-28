"""Full-window synthetic parents for Engel Phase-B tests."""
from __future__ import annotations

import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path

from basket_release.engel.artifact import build_reference_artifact
from basket_release.engel.phase_b_parents import month_sequence
from basket_release.engel.trajectory_contracts import DIVISION_IDS, REGIONS
from engel_fixture_factory import create_engho_parent


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields,lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def create_reference_parent(root: Path) -> Path:
    eng= create_engho_parent(root/"engho")
    return build_reference_artifact(eng, root/"reference_artifacts")


def create_ipc_parent(root: Path) -> Path:
    root.mkdir(parents=True,exist_ok=True)
    rows=[]
    for month_index,period in enumerate(month_sequence()):
        for region_index,region in enumerate(REGIONS):
            for division_index,division in enumerate(DIVISION_IDS,1):
                base=Decimal("125")+Decimal(region_index)*Decimal("1.5")+Decimal(division_index)*Decimal("0.7")
                slope=Decimal("1.1")+Decimal(division_index)*Decimal("0.08")+Decimal(region_index)*Decimal("0.03")
                value=base+Decimal(month_index)*slope
                rows.append({
                    "period":period,
                    "region_id":region,
                    "division_id":division,
                    "division_label":division,
                    "index_value":str(value),
                    "index_base":"2016-12=100",
                    "source_id":"indec_ipc_regional_divisions",
                    "source_snapshot_sha256":"a"*64,
                    "source_cell_identity":f"synthetic:{period}:{region}:{division}",
                    "value_status":"direct_official_observation",
                })
    table=root/"regional_division_indices.csv"
    fields=["period","region_id","division_id","division_label","index_value","index_base",
            "source_id","source_snapshot_sha256","source_cell_identity","value_status"]
    _write_csv(table,fields,rows)
    manifest={
        "schema":"research-artifact-manifest/v1",
        "artifact_type":"publicdata.indec-ipc-regional-divisions/v1",
        "release_id":"indec-ipc-regional-divisions-v1-synthetic-phase-b",
        "status":"direct_official_evidence",
        "source_id":"indec_ipc_regional_divisions",
        "source_snapshot_sha256":"a"*64,
        "files":[{"path":table.name,"sha256":_sha(table),"size":table.stat().st_size}],
    }
    (root/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return root


def create_official_basket_parent(root: Path) -> Path:
    root.mkdir(parents=True,exist_ok=True)
    rows=[]
    for month_index,period in enumerate(month_sequence()):
        for region_index,region in enumerate(REGIONS):
            cba=Decimal("9000")+Decimal(region_index)*Decimal("300")+Decimal(month_index)*Decimal("275")
            ice=Decimal("2.55")+Decimal(region_index)*Decimal("0.02")+Decimal(month_index)*Decimal("0.0015")
            cbt=cba*ice
            rows.append({
                "period":period,
                "region_id":region,
                "CBA_nominal":str(cba),
                "CBT_nominal":str(cbt),
                "unit":"ARS_per_equivalent_adult",
                "value_status":"observed_source",
                "CBA_source_identity":f"synthetic:cba:{period}:{region}",
                "CBT_source_identity":f"synthetic:cbt:{period}:{region}",
                "release_id":"regional-baskets-v2-synthetic-phase-b",
            })
    table=root/"observed_nominal_monthly.csv"
    fields=list(rows[0])
    _write_csv(table,fields,rows)
    manifest={
        "schema":"research-artifact-manifest/v1",
        "artifact_type":"research.argentina-regional-baskets/v1",
        "release_id":"regional-baskets-v2-synthetic-phase-b",
        "status":"candidate",
        "method_id":"research.argentina-regional-baskets/source-observed-plus-price-consensus-v2",
        "warnings":["synthetic_official_basket_parent"],
        "files":{table.name:{"bytes":table.stat().st_size,"sha256":_sha(table)}},
    }
    (root/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return root


def create_phase_b_parents(root: Path) -> tuple[Path,Path,Path]:
    return (
        create_reference_parent(root/"reference_source"),
        create_ipc_parent(root/"ipc"),
        create_official_basket_parent(root/"basket"),
    )


def rehash_ipc(root: Path) -> None:
    manifest_path=root/"manifest.json"; manifest=json.loads(manifest_path.read_text())
    table=root/"regional_division_indices.csv"
    manifest["files"]=[{"path":table.name,"sha256":_sha(table),"size":table.stat().st_size}]
    manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def rehash_reference(root: Path) -> None:
    manifest_path=root/"manifest.json"; manifest=json.loads(manifest_path.read_text())
    table=root/"reference_structure.csv"
    manifest["files"][table.name]={"bytes":table.stat().st_size,"sha256":_sha(table)}
    manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
