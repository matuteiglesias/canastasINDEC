"""Choice-attribution paths around the CEDLAS DT370 replication.

Consumes aggregate-only provenance outputs plus governed IPC/basket parents.
No respondent-level data are read here.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

from basket_release.core import BuildError
from .artifact import canonical_json, _write_csv
from .cedlas_dt370 import (
    ARTIFACT_TYPE as CEDLAS_ARTIFACT_TYPE,
    METHOD_ID as CEDLAS_METHOD_ID,
    PUBLISHED_OLD_ICE_RATIO,
    published_national_vector,
)
from .phase_b_parents import load_ipc_parent, load_official_basket_parent, sha256
from .trajectory_contracts import BASE_PERIOD, DIVISION_IDS, REGIONS

ARTIFACT_TYPE="research.argentina-regional-baskets-cedlas-choice-attribution/v1"
METHOD_ID="research.argentina-regional-baskets-cedlas-choice-attribution/v1"

def _d(value) -> Decimal:
    x=Decimal(str(value))
    if not x.is_finite():
        raise BuildError("cedlas_choice_nonfinite")
    return x

def _read_csv(path: Path) -> list[dict[str,str]]:
    with path.open(newline="",encoding="utf-8") as h:
        return list(csv.DictReader(h))

def _shares_from_row(row: dict[str,str]) -> dict[str,Decimal]:
    shares={f"coicop{i:02d}":_d(row[f"division_{i:02d}_share"]) for i in range(1,13)}
    total=sum(shares.values(),Decimal(0))
    if abs(total-Decimal(1))>Decimal("0.002"):
        raise BuildError(f"cedlas_choice_share_sum:{total}")
    # Household-table expenditure shares can have tiny rounding residuals.
    return {k:v/total for k,v in shares.items()}

def _block_reallocate(
    base: dict[str,Decimal],
    *,
    food_fraction_div02: Decimal,
    target_ice: Decimal,
) -> tuple[dict[str,Decimal],dict[str,Decimal]]:
    f=_d(food_fraction_div02)
    if f<0 or f>1:
        raise BuildError("cedlas_choice_food_fraction_out_of_range")
    target_food=Decimal(1)/target_ice
    food_raw={"coicop01":base["coicop01"],"coicop02":base["coicop02"]*f}
    nonfood_raw={d:base[d] for d in DIVISION_IDS[2:]}
    nonfood_raw["coicop02"]=base["coicop02"]*(Decimal(1)-f)
    sf=sum(food_raw.values(),Decimal(0)); sn=sum(nonfood_raw.values(),Decimal(0))
    if sf<=0 or sn<=0:
        raise BuildError("cedlas_choice_invalid_blocks")
    total={d:Decimal(0) for d in DIVISION_IDS}
    food={d:Decimal(0) for d in DIVISION_IDS}
    for d,w in food_raw.items():
        x=w/sf*target_food; total[d]+=x; food[d]+=x
    for d,w in nonfood_raw.items():
        total[d]+=w/sn*(Decimal(1)-target_food)
    return total,food

def _direct_structure(
    shares: dict[str,Decimal],
    *,
    food_fraction_div02: Decimal,
) -> dict:
    f=_d(food_fraction_div02)
    if f<0 or f>1:
        raise BuildError("cedlas_choice_food_fraction_out_of_range")
    food_component={d:Decimal(0) for d in DIVISION_IDS}
    food_component["coicop01"]=shares["coicop01"]
    food_component["coicop02"]=shares["coicop02"]*f
    food_share=sum(food_component.values(),Decimal(0))
    if food_share<=0:
        raise BuildError("cedlas_choice_nonpositive_food")
    return {
        "division_share":shares,
        "food_component_share":food_component,
        "food_share_base":food_share,
        "ice_base":Decimal(1)/food_share,
    }

def _inherited_structure(
    national: dict[str,Decimal],
    region: str,
    *,
    food_fraction_div02: Decimal,
) -> dict:
    f=_d(food_fraction_div02)
    national_food=national["coicop01"]+f*national["coicop02"]
    national_ice=Decimal(1)/national_food
    ice=national_ice*PUBLISHED_OLD_ICE_RATIO[region]
    total,food=_block_reallocate(national,food_fraction_div02=f,target_ice=ice)
    return {
        "division_share":total,"food_component_share":food,
        "food_share_base":Decimal(1)/ice,"ice_base":ice,
    }

def _path(ipc: dict, region: str, structure: dict) -> list[dict]:
    base={d:ipc["rows"][(BASE_PERIOD,region,d)]["index_decimal"] for d in DIVISION_IDS}
    out=[]
    for period in ipc["periods"]:
        total_rel=Decimal(0); food_cost=Decimal(0)
        for d in DIVISION_IDS:
            rel=ipc["rows"][(period,region,d)]["index_decimal"]/base[d]
            total_rel+=structure["division_share"][d]*rel
            food_cost+=structure["food_component_share"][d]*rel
        food_rel=food_cost/structure["food_share_base"]
        ice=structure["ice_base"]*total_rel/food_rel
        out.append({"period":period,"ICE":ice,"total_price_relative":total_rel,"food_price_relative":food_rel})
    return out

def build_choice_attribution(
    provenance_dir: Path,
    ipc_root: Path,
    basket_root: Path,
    output_parent: Path,
) -> Path:
    provenance_dir=Path(provenance_dir).expanduser().resolve()
    national_rows=_read_csv(provenance_dir/"national_reference_variants.csv")
    regional_rows=_read_csv(provenance_dir/"regional_reference_variants.csv")
    split=json.loads((provenance_dir/"division02_split_summary.json").read_text(encoding="utf-8"))
    by_n={r["variant"]:r for r in national_rows}
    by_r={(r["variant"],r["region_id"]):r for r in regional_rows}
    required_n={"equal_group_average_microdata","pooled_low_very_low_microdata"}
    if not required_n.issubset(by_n):
        raise BuildError("cedlas_choice_missing_national_provenance")
    alcohol_equal=_d(split["equal_group_average_alcohol_fraction_of_division02"])
    alcohol_pooled=_d(split["pooled_alcohol_fraction_of_division02"])

    published=published_national_vector()
    equal=_shares_from_row(by_n["equal_group_average_microdata"])
    pooled=_shares_from_row(by_n["pooled_low_very_low_microdata"])
    variants=[
        {
            "variant_id":"paper_exact",
            "reference":"published_equal_group",
            "national":published,"regionalization":"inherited_old_ice_ratio",
            "food_fraction":Decimal(1),
        },
        {
            "variant_id":"paper_vector_alcohol_only",
            "reference":"published_equal_group",
            "national":published,"regionalization":"inherited_old_ice_ratio",
            "food_fraction":alcohol_equal,
        },
        {
            "variant_id":"microdata_equal_inherited_full02",
            "reference":"microdata_equal_group",
            "national":equal,"regionalization":"inherited_old_ice_ratio",
            "food_fraction":Decimal(1),
        },
        {
            "variant_id":"microdata_pooled_inherited_full02",
            "reference":"microdata_pooled",
            "national":pooled,"regionalization":"inherited_old_ice_ratio",
            "food_fraction":Decimal(1),
        },
        {
            "variant_id":"microdata_equal_direct_full02",
            "reference":"microdata_equal_group",
            "regionalization":"direct_region",
            "food_fraction":Decimal(1),
        },
        {
            "variant_id":"microdata_pooled_direct_full02",
            "reference":"microdata_pooled",
            "regionalization":"direct_region",
            "food_fraction":Decimal(1),
        },
        {
            "variant_id":"microdata_equal_direct_alcohol_only",
            "reference":"microdata_equal_group",
            "regionalization":"direct_region",
            "food_fraction":alcohol_equal,
        },
        {
            "variant_id":"microdata_pooled_direct_alcohol_only",
            "reference":"microdata_pooled",
            "regionalization":"direct_region",
            "food_fraction":alcohol_pooled,
        },
    ]
    ipc=load_ipc_parent(ipc_root); basket=load_official_basket_parent(basket_root)
    if ipc["periods"]!=basket["periods"]:
        raise BuildError("cedlas_choice_parent_period_mismatch")

    threshold_rows=[]; structure_rows=[]
    for v in variants:
        for region in REGIONS:
            if v["regionalization"]=="inherited_old_ice_ratio":
                structure=_inherited_structure(v["national"],region,food_fraction_div02=v["food_fraction"])
            else:
                key=("equal_group_average" if v["reference"]=="microdata_equal_group" else "pooled_low_very_low",region)
                if key not in by_r:
                    raise BuildError(f"cedlas_choice_missing_direct_region:{key}")
                shares=_shares_from_row(by_r[key])
                structure=_direct_structure(shares,food_fraction_div02=v["food_fraction"])
            structure_rows.append({
                "variant_id":v["variant_id"],"region_id":region,
                "reference_population_structure":v["reference"],
                "regionalization":v["regionalization"],
                "coicop02_food_fraction":v["food_fraction"],
                "tobacco_in_food":str(v["food_fraction"]==1).lower(),
                "ice_base":structure["ice_base"],
                "food_share_base":structure["food_share_base"],
                **{f"division_{i:02d}_share":structure["division_share"][f"coicop{i:02d}"] for i in range(1,13)},
            })
            for p in _path(ipc,region,structure):
                b=basket["rows"][(p["period"],region)]
                cbt=b["cba_decimal"]*p["ICE"]
                threshold_rows.append({
                    "variant_id":v["variant_id"],"period":p["period"],"region_id":region,
                    "CBA_official":b["cba_decimal"],"CBT_official":b["cbt_decimal"],
                    "ICE_variant":p["ICE"],"CBT_variant":cbt,
                    "threshold_ratio":cbt/b["cbt_decimal"],
                    "total_price_relative":p["total_price_relative"],
                    "food_price_relative":p["food_price_relative"],
                    "reference_population_structure":v["reference"],
                    "regionalization":v["regionalization"],
                    "coicop02_food_fraction":v["food_fraction"],
                })
    seed={
        "artifact_type":ARTIFACT_TYPE,
        "ipc_manifest_sha256":ipc["manifest_sha256"],
        "basket_manifest_sha256":basket["manifest_sha256"],
        "provenance_receipt":sha256(provenance_dir/"receipt.json"),
    }
    release_id="cedlas-choice-attribution-"+hashlib.sha256(canonical_json(seed)).hexdigest()[:16]
    output_parent=Path(output_parent).expanduser().resolve(); output_parent.mkdir(parents=True,exist_ok=True)
    final=output_parent/release_id
    if final.exists():
        return final
    staging=Path(tempfile.mkdtemp(prefix=f".{release_id}.",dir=output_parent))
    try:
        _write_csv(staging/"threshold_paths.csv",list(threshold_rows[0]),threshold_rows)
        _write_csv(staging/"structures.csv",list(structure_rows[0]),structure_rows)
        variant_meta=[{
            "variant_id":v["variant_id"],"reference_population_structure":v["reference"],
            "regionalization":v["regionalization"],"coicop02_food_fraction":v["food_fraction"],
        } for v in variants]
        _write_csv(staging/"variants.csv",list(variant_meta[0]),variant_meta)
        qa={
            "result":"pass",
            "variant_count":len(variants),
            "monthly_rows":len(threshold_rows),
            "respondent_level_data_consumed":False,
            "provenance_is_aggregate_only":True,
            "paper_exact_variant":"paper_exact",
            "scientific_poverty_execution_performed":False,
        }
        (staging/"qa.json").write_bytes(canonical_json(qa))
        parents={
            "provenance_receipt_sha256":sha256(provenance_dir/"receipt.json"),
            "ipc_release_id":ipc["release_id"],"ipc_manifest_sha256":ipc["manifest_sha256"],
            "basket_release_id":basket["release_id"],"basket_manifest_sha256":basket["manifest_sha256"],
        }
        (staging/"parent_locks.json").write_bytes(canonical_json(parents))
        payloads=["threshold_paths.csv","structures.csv","variants.csv","qa.json","parent_locks.json"]
        files={n:{"bytes":(staging/n).stat().st_size,"sha256":sha256(staging/n)} for n in payloads}
        manifest={
            "schema":"research-artifact-manifest/v1","artifact_type":ARTIFACT_TYPE,
            "release_id":release_id,"status":"candidate_diagnostic_attribution",
            "method_id":METHOD_ID,"cedlas_replication_artifact_type":CEDLAS_ARTIFACT_TYPE,
            "cedlas_replication_method_id":CEDLAS_METHOD_ID,
            "scientific_poverty_execution_performed":False,"files":files,**parents,
        }
        (staging/"manifest.json").write_bytes(canonical_json(manifest))
        os.replace(staging,final)
        return final
    except Exception:
        shutil.rmtree(staging,ignore_errors=True); raise
