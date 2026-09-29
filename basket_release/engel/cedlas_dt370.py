"""Forensic replication of CEDLAS DT370 updated-consumption threshold paths.

This is a separate validation lane. It never changes the primary signed-sales
p29-p48 Artifact A/B contracts.
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
from .phase_b_parents import load_ipc_parent, load_official_basket_parent, month_sequence, sha256
from .trajectory_contracts import DIVISION_IDS, REGIONS, BASE_PERIOD

ARTIFACT_TYPE = "research.argentina-regional-baskets-cedlas-dt370-replication/v1"
METHOD_ID = "research.argentina-regional-baskets-cedlas-dt370/published-low-education-v1"
STATUS = "candidate_diagnostic_replication"
PAPER_ID = "cedlas-dt370-2026"
PRIMARY_FOOD_SCOPE = "coicop01_plus_full_coicop02"
ARITHMETIC_TOLERANCE = Decimal("1e-18")

# Cuadro 1. Values are percentages. The combined vector is the exact arithmetic
# mean of the two published subgroup vectors before one-decimal display rounding.
VERY_LOW_PCT = (
    Decimal("36.0"), Decimal("2.6"), Decimal("6.3"), Decimal("14.0"),
    Decimal("5.6"), Decimal("6.8"), Decimal("10.4"), Decimal("4.8"),
    Decimal("6.6"), Decimal("0.4"), Decimal("3.0"), Decimal("3.3"),
)
LOW_PCT = (
    Decimal("29.1"), Decimal("2.3"), Decimal("7.4"), Decimal("14.0"),
    Decimal("4.7"), Decimal("5.8"), Decimal("13.3"), Decimal("5.5"),
    Decimal("7.4"), Decimal("1.4"), Decimal("5.3"), Decimal("3.8"),
)
PUBLISHED_COMBINED_PCT = tuple((a+b)/Decimal(2) for a,b in zip(VERY_LOW_PCT,LOW_PCT))

# Cuadro 2 / Paso 3: published relative ratios ICE_region / ICE_national.
PUBLISHED_OLD_ICE_RATIO = {
    "gran_buenos_aires": Decimal("0.998"),
    "pampeana": Decimal("0.998"),
    "noreste": Decimal("0.935"),
    "noroeste": Decimal("0.927"),
    "cuyo": Decimal("1.062"),
    "patagonia": Decimal("1.133"),
}
TABLE2_CBA_MAY2018 = {
    "gran_buenos_aires": Decimal("2418.65"),
    "pampeana": Decimal("2389.72"),
    "noreste": Decimal("2153.60"),
    "noroeste": Decimal("2088.53"),
    "cuyo": Decimal("2153.78"),
    "patagonia": Decimal("2493.43"),
}
TABLE2_CBT_MAY2018 = {
    "gran_buenos_aires": Decimal("6095.00"),
    "pampeana": Decimal("6022.12"),
    "noreste": Decimal("5082.50"),
    "noroeste": Decimal("4887.18"),
    "cuyo": Decimal("5772.13"),
    "patagonia": Decimal("7131.24"),
}
REGION_IMPORTANCE_PCT = {
    "gran_buenos_aires": Decimal("44.7"),
    "pampeana": Decimal("34.2"),
    "noreste": Decimal("4.5"),
    "noroeste": Decimal("6.9"),
    "cuyo": Decimal("5.2"),
    "patagonia": Decimal("4.6"),
}

TABLE3_ICE_TARGET = {
    "gran_buenos_aires": Decimal("2.85"),
    "pampeana": Decimal("2.85"),
    "noreste": Decimal("2.67"),
    "noroeste": Decimal("2.65"),
    "cuyo": Decimal("3.03"),
    "patagonia": Decimal("3.24"),
}
TABLE3_SHARE_TARGET_PCT = {
    "gran_buenos_aires": (Decimal("32.6"),Decimal("2.5"),Decimal("6.9"),Decimal("14.0"),Decimal("5.2"),Decimal("6.3"),Decimal("11.9"),Decimal("5.2"),Decimal("7.0"),Decimal("0.9"),Decimal("4.2"),Decimal("3.6")),
    "pampeana": (Decimal("32.6"),Decimal("2.5"),Decimal("6.9"),Decimal("14.0"),Decimal("5.2"),Decimal("6.3"),Decimal("11.9"),Decimal("5.2"),Decimal("7.0"),Decimal("0.9"),Decimal("4.2"),Decimal("3.6")),
    "noreste": (Decimal("34.8"),Decimal("2.6"),Decimal("6.6"),Decimal("13.5"),Decimal("5.0"),Decimal("6.1"),Decimal("11.4"),Decimal("5.0"),Decimal("6.7"),Decimal("0.9"),Decimal("4.0"),Decimal("3.4")),
    "noroeste": (Decimal("35.1"),Decimal("2.6"),Decimal("6.6"),Decimal("13.4"),Decimal("4.9"),Decimal("6.0"),Decimal("11.4"),Decimal("4.9"),Decimal("6.7"),Decimal("0.9"),Decimal("4.0"),Decimal("3.4")),
    "cuyo": (Decimal("30.7"),Decimal("2.3"),Decimal("7.1"),Decimal("14.5"),Decimal("5.3"),Decimal("6.5"),Decimal("12.2"),Decimal("5.3"),Decimal("7.2"),Decimal("0.9"),Decimal("4.3"),Decimal("3.7")),
    "patagonia": (Decimal("28.7"),Decimal("2.2"),Decimal("7.3"),Decimal("14.9"),Decimal("5.5"),Decimal("6.7"),Decimal("12.6"),Decimal("5.5"),Decimal("7.5"),Decimal("1.0"),Decimal("4.4"),Decimal("3.8")),
}
TABLE4_2025_ICE_TARGET = {
    "gran_buenos_aires": ("2.65","2.64","2.59","2.58","2.60","2.63"),
    "cuyo": ("2.84","2.81","2.75","2.74","2.76","2.78"),
    "noreste": ("2.67","2.66","2.60","2.59","2.60","2.63"),
    "noroeste": ("2.54","2.52","2.48","2.46","2.48","2.50"),
    "pampeana": ("2.58","2.57","2.53","2.52","2.55","2.57"),
    "patagonia": ("2.93","2.91","2.91","2.90","2.92","2.95"),
}
TABLE4_2025_ICE_TARGET = {k: tuple(Decimal(x) for x in v) for k,v in TABLE4_2025_ICE_TARGET.items()}

REGION_CODE_TO_ID = {
    "1":"gran_buenos_aires",
    "2":"pampeana",
    "3":"noroeste",
    "4":"noreste",
    "5":"cuyo",
    "6":"patagonia",
}

def _d(value) -> Decimal:
    out=Decimal(str(value))
    if not out.is_finite():
        raise BuildError("cedlas_nonfinite_decimal")
    return out

def published_national_vector() -> dict[str,Decimal]:
    return {division: pct/Decimal(100) for division,pct in zip(DIVISION_IDS,PUBLISHED_COMBINED_PCT)}

def national_ice(*, coicop02_food_fraction: Decimal=Decimal(1)) -> Decimal:
    f=_d(coicop02_food_fraction)
    if f < 0 or f > 1:
        raise BuildError("cedlas_coicop02_food_fraction_out_of_range")
    v=published_national_vector()
    food=v["coicop01"] + f*v["coicop02"]
    if food <= 0:
        raise BuildError("cedlas_nonpositive_food_share")
    return Decimal(1)/food

def regional_structure(
    region: str,
    *,
    coicop02_food_fraction: Decimal=Decimal(1),
    regionalization: str="paper_published_ratio",
) -> dict:
    if region not in REGIONS:
        raise BuildError(f"cedlas_unknown_region:{region}")
    f=_d(coicop02_food_fraction)
    base=published_national_vector()
    if regionalization == "paper_published_ratio":
        ratio=PUBLISHED_OLD_ICE_RATIO[region]
    elif regionalization == "table2_exact_ratio_to_2_52":
        ratio=(TABLE2_CBT_MAY2018[region]/TABLE2_CBA_MAY2018[region])/Decimal("2.52")
    else:
        raise BuildError(f"cedlas_unknown_regionalization:{regionalization}")
    ice_n=national_ice(coicop02_food_fraction=f)
    ice_r=ice_n*ratio
    food_share=Decimal(1)/ice_r
    food_weights={
        "coicop01":base["coicop01"],
        "coicop02":base["coicop02"]*f,
    }
    nonfood_weights={d:base[d] for d in DIVISION_IDS[2:]}
    nonfood_weights["coicop02"]=base["coicop02"]*(Decimal(1)-f)
    sum_food=sum(food_weights.values(),Decimal(0))
    sum_nonfood=sum(nonfood_weights.values(),Decimal(0))
    if sum_food<=0 or sum_nonfood<=0:
        raise BuildError("cedlas_invalid_food_nonfood_blocks")
    total={d:Decimal(0) for d in DIVISION_IDS}
    food_component={d:Decimal(0) for d in DIVISION_IDS}
    for d,w in food_weights.items():
        x=(w/sum_food)*food_share
        total[d]+=x; food_component[d]+=x
    for d,w in nonfood_weights.items():
        total[d]+=(w/sum_nonfood)*(Decimal(1)-food_share)
    if abs(sum(total.values(),Decimal(0))-Decimal(1)) > Decimal("1e-24"):
        raise BuildError("cedlas_regional_shares_do_not_sum_to_one")
    return {
        "region_id":region,
        "national_ice":ice_n,
        "old_relative_ratio":ratio,
        "ice_base":ice_r,
        "food_share_base":food_share,
        "division_share":total,
        "food_component_share":food_component,
        "coicop02_food_fraction":f,
        "regionalization":regionalization,
    }

def table3_validation(*, coicop02_food_fraction: Decimal=Decimal(1), regionalization: str="paper_published_ratio") -> list[dict]:
    rows=[]
    for region in REGIONS:
        s=regional_structure(region,coicop02_food_fraction=coicop02_food_fraction,regionalization=regionalization)
        rows.append({
            "region_id":region,
            "computed_ice":s["ice_base"],
            "published_ice":TABLE3_ICE_TARGET[region],
            "ice_round_2_match":s["ice_base"].quantize(Decimal("0.01"))==TABLE3_ICE_TARGET[region],
            "max_share_round_1_pp_error":max(
                abs((s["division_share"][d]*100).quantize(Decimal("0.1"))-target)
                for d,target in zip(DIVISION_IDS,TABLE3_SHARE_TARGET_PCT[region])
            ),
        })
    return rows

def _monthly_path(ipc: dict, region: str, structure: dict) -> list[dict]:
    base_indices={d:ipc["rows"][(BASE_PERIOD,region,d)]["index_decimal"] for d in DIVISION_IDS}
    rows=[]
    for period in ipc["periods"]:
        total_rel=Decimal(0)
        food_cost=Decimal(0)
        contributions=[]
        for d in DIVISION_IDS:
            rel=ipc["rows"][(period,region,d)]["index_decimal"]/base_indices[d]
            weighted=structure["division_share"][d]*rel
            food_weighted=structure["food_component_share"][d]*rel
            total_rel+=weighted
            food_cost+=food_weighted
            contributions.append((d,rel,weighted,food_weighted))
        food_price_rel=food_cost/structure["food_share_base"]
        ice=structure["ice_base"]*total_rel/food_price_rel
        rows.append({
            "period":period,
            "region_id":region,
            "ICE_cedlas":ice,
            "total_price_relative":total_rel,
            "food_price_relative":food_price_rel,
            "contributions":contributions,
        })
    return rows

def build_replication_artifact(
    ipc_root: Path,
    official_basket_root: Path,
    output_parent: Path,
    *,
    coicop02_food_fraction: Decimal=Decimal(1),
    regionalization: str="paper_published_ratio",
) -> Path:
    ipc=load_ipc_parent(ipc_root)
    basket=load_official_basket_parent(official_basket_root)
    if ipc["periods"] != basket["periods"]:
        raise BuildError("cedlas_parent_period_inventory_mismatch")
    f=_d(coicop02_food_fraction)
    structures={r:regional_structure(r,coicop02_food_fraction=f,regionalization=regionalization) for r in REGIONS}
    table3=table3_validation(coicop02_food_fraction=f,regionalization=regionalization)
    threshold_rows=[]; weight_rows=[]; contribution_rows=[]
    for region in REGIONS:
        s=structures[region]
        for d in DIVISION_IDS:
            weight_rows.append({
                "region_id":region,
                "division_id":d,
                "base_share":s["division_share"][d],
                "food_component_base_share":s["food_component_share"][d],
                "ice_base":s["ice_base"],
                "food_share_base":s["food_share_base"],
                "old_relative_ratio":s["old_relative_ratio"],
                "coicop02_food_fraction":f,
                "regionalization":regionalization,
            })
        for p in _monthly_path(ipc,region,s):
            b=basket["rows"][(p["period"],region)]
            cba=b["cba_decimal"]; cbt_off=b["cbt_decimal"]
            cbt_cedlas=cba*p["ICE_cedlas"]
            threshold_rows.append({
                "period":p["period"],"region_id":region,
                "CBA_official":cba,"CBT_official":cbt_off,
                "ICE_official":cbt_off/cba,
                "ICE_cedlas":p["ICE_cedlas"],
                "CBT_cedlas":cbt_cedlas,
                "threshold_ratio":cbt_cedlas/cbt_off,
                "total_price_relative":p["total_price_relative"],
                "food_price_relative":p["food_price_relative"],
                "method_id":METHOD_ID,
                "paper_id":PAPER_ID,
                "coicop02_food_fraction":f,
                "tobacco_in_food":str(f==1).lower(),
                "regionalization":regionalization,
                "value_status":"cedlas_replication_candidate",
            })
            for d,rel,weighted,food_weighted in p["contributions"]:
                contribution_rows.append({
                    "period":p["period"],"region_id":region,"division_id":d,
                    "base_share":s["division_share"][d],
                    "food_component_base_share":s["food_component_share"][d],
                    "price_relative":rel,
                    "weighted_cost_contribution":weighted,
                    "food_weighted_cost_contribution":food_weighted,
                })
    seed={
        "artifact_type":ARTIFACT_TYPE,"method_id":METHOD_ID,
        "ipc_manifest_sha256":ipc["manifest_sha256"],
        "basket_manifest_sha256":basket["manifest_sha256"],
        "coicop02_food_fraction":str(f),"regionalization":regionalization,
    }
    release_id="cedlas-dt370-replication-"+hashlib.sha256(canonical_json(seed)).hexdigest()[:16]
    output_parent=Path(output_parent).expanduser().resolve(); output_parent.mkdir(parents=True,exist_ok=True)
    final=output_parent/release_id
    if final.exists():
        validate_replication_artifact(final); return final
    staging=Path(tempfile.mkdtemp(prefix=f".{release_id}.",dir=output_parent))
    try:
        _write_csv(staging/"threshold_paths.csv",list(threshold_rows[0]),threshold_rows)
        _write_csv(staging/"regional_weights.csv",list(weight_rows[0]),weight_rows)
        _write_csv(staging/"division_contributions.csv",list(contribution_rows[0]),contribution_rows)
        _write_csv(staging/"table3_validation.csv",list(table3[0]),table3)
        table4=[]
        for region,targets in TABLE4_2025_ICE_TARGET.items():
            by={(x["period"],x["region_id"]):x for x in threshold_rows}
            for month,target in enumerate(targets,1):
                period=f"2025-{month:02d}-01"; observed=by[(period,region)]["ICE_cedlas"]
                table4.append({
                    "period":period,"region_id":region,"computed_ice":observed,
                    "published_ice":target,"difference":observed-target,
                })
        _write_csv(staging/"table4_validation.csv",list(table4[0]),table4)
        paper_targets={
            "table1_combined_pct":[str(x) for x in PUBLISHED_COMBINED_PCT],
            "table1_very_low_pct":[str(x) for x in VERY_LOW_PCT],
            "table1_low_pct":[str(x) for x in LOW_PCT],
            "table3_ice":{k:str(v) for k,v in TABLE3_ICE_TARGET.items()},
            "table4_2025_ice":{k:[str(x) for x in v] for k,v in TABLE4_2025_ICE_TARGET.items()},
        }
        (staging/"paper_targets.json").write_bytes(canonical_json(paper_targets))
        qa={
            "result":"mechanism_complete_real_ipc_validation_pending",
            "paper_id":PAPER_ID,
            "published_vector_authority":"CEDLAS DT370 Cuadro 1",
            "national_ice":str(national_ice(coicop02_food_fraction=f)),
            "coicop02_food_fraction":str(f),
            "tobacco_in_food":f==1,
            "regionalization":regionalization,
            "table3_all_ice_round_2_match":all(x["ice_round_2_match"] for x in table3),
            "table3_max_share_round_1_pp_error":str(max(x["max_share_round_1_pp_error"] for x in table3)),
            "table4_max_abs_ice_difference":str(max(abs(x["difference"]) for x in table4)),
            "scientific_poverty_execution_performed":False,
            "network_retrieval_performed":False,
            "warnings":[
                "published_table1_vector_sums_to_99_9_due_to_display_rounding",
                "cedlas_primary_food_scope_includes_full_coicop02_alcohol_and_tobacco",
                "regional_ice_relativities_inherited_from_old_official_method",
                "ipc_divisions_are_approximation_to_exact_basket_items",
            ],
        }
        (staging/"qa.json").write_bytes(canonical_json(qa))
        parent_locks={
            "ipc_regional_divisions":{"release_id":ipc["release_id"],"manifest_sha256":ipc["manifest_sha256"]},
            "official_baskets":{"release_id":basket["release_id"],"manifest_sha256":basket["manifest_sha256"]},
        }
        (staging/"parent_locks.json").write_bytes(canonical_json(parent_locks))
        payloads=["threshold_paths.csv","regional_weights.csv","division_contributions.csv","table3_validation.csv","table4_validation.csv","paper_targets.json","qa.json","parent_locks.json"]
        files={n:{"bytes":(staging/n).stat().st_size,"sha256":sha256(staging/n)} for n in payloads}
        manifest={
            "schema":"research-artifact-manifest/v1","artifact_type":ARTIFACT_TYPE,
            "release_id":release_id,"status":STATUS,"method_id":METHOD_ID,"paper_id":PAPER_ID,
            "base_period":BASE_PERIOD,"coicop02_food_fraction":str(f),
            "tobacco_in_food":f==1,"regionalization":regionalization,
            "ipc_regional_divisions_release_id":ipc["release_id"],
            "official_basket_release_id":basket["release_id"],
            "parent_manifest_sha256":{"ipc_regional_divisions":ipc["manifest_sha256"],"official_baskets":basket["manifest_sha256"]},
            "scientific_poverty_execution_performed":False,"files":files,
        }
        (staging/"manifest.json").write_bytes(canonical_json(manifest))
        os.replace(staging,final)
        validate_replication_artifact(final)
        return final
    except Exception:
        shutil.rmtree(staging,ignore_errors=True); raise

def validate_replication_artifact(root: Path) -> dict:
    root=Path(root).expanduser().resolve()
    manifest=json.loads((root/"manifest.json").read_text(encoding="utf-8"))
    if manifest.get("artifact_type")!=ARTIFACT_TYPE or manifest.get("method_id")!=METHOD_ID:
        raise BuildError("cedlas_replication_identity_mismatch")
    if manifest.get("scientific_poverty_execution_performed") is not False:
        raise BuildError("cedlas_replication_scope_violation")
    for name,identity in manifest.get("files",{}).items():
        p=root/name
        if not p.is_file() or p.stat().st_size!=identity["bytes"] or sha256(p)!=identity["sha256"]:
            raise BuildError(f"cedlas_replication_file_mismatch:{name}")
    with (root/"threshold_paths.csv").open(newline="",encoding="utf-8") as h:
        rows=list(csv.DictReader(h))
    expected={(p,r) for p in month_sequence() for r in REGIONS}
    keys={(x["period"],x["region_id"]) for x in rows}
    if keys!=expected or len(rows)!=len(expected):
        raise BuildError("cedlas_replication_threshold_inventory_mismatch")
    return {
        "result":"compatible",
        "release_id":manifest["release_id"],
        "monthly_rows":len(rows),
        "tobacco_in_food":manifest["tobacco_in_food"],
        "coicop02_food_fraction":manifest["coicop02_food_fraction"],
    }
