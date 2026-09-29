"""CEDLAS DT370 old-method IPC reconstruction control (Anexo-style diagnostic)."""
from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path

from basket_release.core import BuildError
from .artifact import canonical_json, _write_csv
from .phase_b_parents import load_ipc_parent, load_official_basket_parent
from .trajectory_contracts import BASE_PERIOD, DIVISION_IDS, REGIONS
from .cedlas_dt370 import TABLE2_CBA_MAY2018, TABLE2_CBT_MAY2018

OLD_2005_PCT = (
    Decimal("33.0"), Decimal("4.0"), Decimal("10.0"), Decimal("11.0"),
    Decimal("5.0"), Decimal("6.0"), Decimal("9.0"), Decimal("3.0"),
    Decimal("6.0"), Decimal("2.0"), Decimal("7.0"), Decimal("4.0"),
)

def _structure(region: str) -> dict:
    base={d:p/Decimal(100) for d,p in zip(DIVISION_IDS,OLD_2005_PCT)}
    ice=TABLE2_CBT_MAY2018[region]/TABLE2_CBA_MAY2018[region]
    food_share=Decimal(1)/ice
    food_raw=base["coicop01"]+base["coicop02"]
    nonfood_raw=sum((base[d] for d in DIVISION_IDS[2:]),Decimal(0))
    total={d:Decimal(0) for d in DIVISION_IDS}
    food={d:Decimal(0) for d in DIVISION_IDS}
    for d in ("coicop01","coicop02"):
        x=base[d]/food_raw*food_share
        total[d]=x; food[d]=x
    for d in DIVISION_IDS[2:]:
        total[d]=base[d]/nonfood_raw*(Decimal(1)-food_share)
    return {"ice_base":ice,"food_share":food_share,"total":total,"food":food}

def reconstruct_old_method(ipc_root: Path, basket_root: Path, output: Path) -> Path:
    ipc=load_ipc_parent(ipc_root); basket=load_official_basket_parent(basket_root)
    if ipc["periods"]!=basket["periods"]:
        raise BuildError("cedlas_old_reconstruction_period_mismatch")
    rows=[]
    for region in REGIONS:
        s=_structure(region)
        base_idx={d:ipc["rows"][(BASE_PERIOD,region,d)]["index_decimal"] for d in DIVISION_IDS}
        for period in ipc["periods"]:
            total_rel=Decimal(0); food_cost=Decimal(0)
            for d in DIVISION_IDS:
                rel=ipc["rows"][(period,region,d)]["index_decimal"]/base_idx[d]
                total_rel += s["total"][d]*rel
                food_cost += s["food"][d]*rel
            food_rel=food_cost/s["food_share"]
            ice=s["ice_base"]*total_rel/food_rel
            b=basket["rows"][(period,region)]
            official=b["cbt_decimal"]/b["cba_decimal"]
            rows.append({
                "period":period,"region_id":region,
                "reconstructed_old_ice":ice,
                "observed_official_ice":official,
                "ice_difference":ice-official,
                "relative_difference":ice/official-Decimal(1),
            })
    output=Path(output).expanduser().resolve(); output.mkdir(parents=True,exist_ok=True)
    _write_csv(output/"old_method_reconstruction.csv",list(rows[0]),rows)
    qa={
        "schema":"cedlas-dt370-old-method-reconstruction/v1",
        "max_abs_ice_difference":str(max(abs(r["ice_difference"]) for r in rows)),
        "max_abs_relative_difference":str(max(abs(r["relative_difference"]) for r in rows)),
        "base_period":BASE_PERIOD,
        "food_scope":"coicop01_plus_full_coicop02",
        "scientific_poverty_execution_performed":False,
        "interpretation":"approximation diagnostic; IPC divisions do not exactly equal poverty-basket items",
    }
    (output/"qa.json").write_bytes(canonical_json(qa))
    return output
