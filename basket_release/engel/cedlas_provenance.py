"""Aggregate-only ENGHo provenance checks for CEDLAS DT370 Table 1.

Consumes governed ENGHo household/expenditure tables and emits no respondent-level data.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from basket_release.core import BuildError
from .artifact import canonical_json, _write_csv
from .cedlas_dt370 import (
    DIVISION_IDS, VERY_LOW_PCT, LOW_PCT, PUBLISHED_COMBINED_PCT,
    REGION_CODE_TO_ID,
)

REQUIRED_HOUSEHOLD_FIELDS = {"id","pondera","region","clima_educativo","gastot"} | {f"gc_{i:02d}" for i in range(1,13)}
REQUIRED_EXPENDITURE_FIELDS = {"id","division","grupo","monto"}

def _decimal(value, field: str) -> Decimal:
    try:
        x=Decimal(str(value).strip().replace(",","."))
    except Exception as exc:
        raise BuildError(f"cedlas_provenance_invalid_decimal:{field}") from exc
    if not x.is_finite():
        raise BuildError(f"cedlas_provenance_nonfinite:{field}")
    return x

def _role_file(release: Path, role: str) -> tuple[Path,str]:
    manifest_path=release/"output-manifest.json"
    if not manifest_path.is_file():
        raise BuildError("cedlas_provenance_engho_manifest_missing")
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("artifact_type")!="publicdata.indec-engho-microdata/v1":
        raise BuildError("cedlas_provenance_wrong_engho_artifact")
    matches=[x for x in manifest.get("files",[]) if x.get("role")==role]
    if len(matches)!=1:
        raise BuildError(f"cedlas_provenance_role_inventory:{role}")
    item=matches[0]
    path=release/item["file"]
    if not path.is_file():
        raise BuildError(f"cedlas_provenance_role_file_missing:{role}")
    return path,item.get("delimiter","|")

def _read(path: Path, delimiter: str):
    with path.open(newline="",encoding="utf-8") as h:
        reader=csv.DictReader(h,delimiter=delimiter)
        for row in reader:
            yield {str(k).strip().casefold():v for k,v in row.items()}

def _shares(rows: list[dict]) -> dict[str,Decimal]:
    total=sum((r["weight"]*r["gastot"] for r in rows),Decimal(0))
    if total<=0:
        raise BuildError("cedlas_provenance_nonpositive_total_expenditure")
    return {
        d:sum((r["weight"]*r[d] for r in rows),Decimal(0))/total
        for d in DIVISION_IDS
    }

def _variant_row(name: str, shares: dict[str,Decimal], households: int, weight_mass: Decimal) -> dict:
    return {
        "variant":name,"households":households,"weight_mass":weight_mass,
        **{f"division_{i:02d}_share":shares[f"coicop{i:02d}"] for i in range(1,13)},
        "food_share_div01_plus_div02":shares["coicop01"]+shares["coicop02"],
        "ice_div01_plus_div02":Decimal(1)/(shares["coicop01"]+shares["coicop02"]),
        "food_share_div01_only":shares["coicop01"],
        "ice_div01_only":Decimal(1)/shares["coicop01"],
    }

def commission_low_education_provenance(engho_release: Path, output: Path) -> Path:
    engho_release=Path(engho_release).expanduser().resolve()
    hh_path,hh_delim=_role_file(engho_release,"households")
    ex_path,ex_delim=_role_file(engho_release,"expenditures")
    groups={1:[],2:[]}; household_meta={}
    excluded_nonpositive_gastot=defaultdict(lambda: {"rows":0,"weight":Decimal(0),"signed_gastot":Decimal(0)})
    for raw in _read(hh_path,hh_delim):
        if not REQUIRED_HOUSEHOLD_FIELDS.issubset(raw):
            missing=sorted(REQUIRED_HOUSEHOLD_FIELDS-set(raw))
            raise BuildError(f"cedlas_provenance_household_fields_missing:{missing}")
        climate=int(raw["clima_educativo"])
        if climate not in (1,2):
            continue
        region=REGION_CODE_TO_ID.get(str(raw["region"]).strip())
        if region is None:
            raise BuildError(f"cedlas_provenance_unknown_region:{raw['region']}")
        row={
            "id":raw["id"],"climate":climate,"region":region,
            "weight":_decimal(raw["pondera"],"pondera"),
            "gastot":_decimal(raw["gastot"],"gastot"),
        }
        if row["weight"]<=0:
            raise BuildError("cedlas_provenance_nonpositive_weight_or_gastot")
        if row["gastot"]<=0:
            x=excluded_nonpositive_gastot[climate]
            x["rows"]+=1
            x["weight"]+=row["weight"]
            x["signed_gastot"]+=row["weight"]*row["gastot"]
            continue
        for i,d in enumerate(DIVISION_IDS,1):
            row[d]=_decimal(raw[f"gc_{i:02d}"],f"gc_{i:02d}")
        groups[climate].append(row); household_meta[row["id"]]=row
    if not groups[1] or not groups[2]:
        raise BuildError("cedlas_provenance_missing_low_education_groups")

    very=_shares(groups[1]); low=_shares(groups[2])
    equal={d:(very[d]+low[d])/Decimal(2) for d in DIVISION_IDS}
    pooled=_shares(groups[1]+groups[2])
    national_rows=[
        _variant_row("very_low_microdata",very,len(groups[1]),sum((r["weight"] for r in groups[1]),Decimal(0))),
        _variant_row("low_microdata",low,len(groups[2]),sum((r["weight"] for r in groups[2]),Decimal(0))),
        _variant_row("equal_group_average_microdata",equal,len(groups[1])+len(groups[2]),sum((r["weight"] for r in groups[1]+groups[2]),Decimal(0))),
        _variant_row("pooled_low_very_low_microdata",pooled,len(groups[1])+len(groups[2]),sum((r["weight"] for r in groups[1]+groups[2]),Decimal(0))),
    ]

    regional_rows=[]
    for region in REGION_CODE_TO_ID.values():
        r1=[r for r in groups[1] if r["region"]==region]
        r2=[r for r in groups[2] if r["region"]==region]
        if not r1 or not r2:
            continue
        s1=_shares(r1); s2=_shares(r2)
        eq={d:(s1[d]+s2[d])/Decimal(2) for d in DIVISION_IDS}
        pool=_shares(r1+r2)
        for name,shares,rows in (("equal_group_average",eq,r1+r2),("pooled_low_very_low",pool,r1+r2)):
            regional_rows.append({
                "region_id":region,"variant":name,"households":len(rows),
                **{f"division_{i:02d}_share":shares[f"coicop{i:02d}"] for i in range(1,13)},
                "food_share_div01_plus_div02":shares["coicop01"]+shares["coicop02"],
                "ice_div01_plus_div02":Decimal(1)/(shares["coicop01"]+shares["coicop02"]),
            })

    split=defaultdict(lambda:{"alcohol":Decimal(0),"tobacco":Decimal(0),"division02":Decimal(0),"rows":0})
    for raw in _read(ex_path,ex_delim):
        if not REQUIRED_EXPENDITURE_FIELDS.issubset(raw):
            missing=sorted(REQUIRED_EXPENDITURE_FIELDS-set(raw))
            raise BuildError(f"cedlas_provenance_expenditure_fields_missing:{missing}")
        meta=household_meta.get(raw["id"])
        if meta is None:
            continue
        division=str(raw["division"]).strip().upper()
        if division.startswith("A") and division[1:].isdigit():
            division=division[1:]
        division=division.zfill(2)
        if division!="02":
            continue
        group=str(raw["grupo"]).strip().upper()
        if group.startswith("A") and group[1:].isdigit():
            group=group[1:]
        group=group.zfill(3)
        amount=_decimal(raw["monto"],"monto")
        weighted=meta["weight"]*amount
        key=(meta["climate"],meta["region"])
        split[key]["division02"]+=weighted; split[key]["rows"]+=1
        if group.startswith("021"):
            split[key]["alcohol"]+=weighted
        elif group.startswith("022"):
            split[key]["tobacco"]+=weighted

    split_rows=[]
    for (climate,region),x in sorted(split.items()):
        denom=x["division02"]
        split_rows.append({
            "climate":climate,"region_id":region,"rows":x["rows"],
            "division02_weighted_total":denom,
            "alcohol_021_weighted_total":x["alcohol"],
            "tobacco_022_weighted_total":x["tobacco"],
            "alcohol_fraction_of_division02":x["alcohol"]/denom if denom else "",
            "tobacco_fraction_of_division02":x["tobacco"]/denom if denom else "",
        })
    # pooled and equal-climate national split summaries
    climate_split={}
    for climate in (1,2):
        xs=[x for (c,_),x in split.items() if c==climate]
        denom=sum((x["division02"] for x in xs),Decimal(0))
        alcohol=sum((x["alcohol"] for x in xs),Decimal(0))
        tobacco=sum((x["tobacco"] for x in xs),Decimal(0))
        climate_split[climate]=(denom,alcohol,tobacco)
    pooled_den=sum(x[0] for x in climate_split.values()); pooled_alc=sum(x[1] for x in climate_split.values())
    f1=climate_split[1][1]/climate_split[1][0]; f2=climate_split[2][1]/climate_split[2][0]
    split_summary={
        "pooled_alcohol_fraction_of_division02":str(pooled_alc/pooled_den),
        "equal_group_average_alcohol_fraction_of_division02":str((f1+f2)/Decimal(2)),
        "cedlas_exact_food_fraction_of_division02":"1",
        "primary_signed_sales_food_scope_note":"p29-p48 primary includes alcohol021 and excludes tobacco022",
    }

    def max_pp(shares: dict[str,Decimal], target_pct) -> Decimal:
        return max(abs(shares[d]*100-target) for d,target in zip(DIVISION_IDS,target_pct))
    qa={
        "result":"diagnostic",
        "very_low_max_abs_pp_difference_vs_published_table1":str(max_pp(very,VERY_LOW_PCT)),
        "low_max_abs_pp_difference_vs_published_table1":str(max_pp(low,LOW_PCT)),
        "equal_group_average_max_abs_pp_difference_vs_published_combined":str(max_pp(equal,PUBLISHED_COMBINED_PCT)),
        "pooled_vs_equal_max_abs_pp_difference":str(max(abs(pooled[d]-equal[d])*100 for d in DIVISION_IDS)),
        "published_combined_is_exact_mean_of_published_subgroups":all((a+b)/2==c for a,b,c in zip(VERY_LOW_PCT,LOW_PCT,PUBLISHED_COMBINED_PCT)),
        "excluded_nonpositive_gastot_rows":sum(x["rows"] for x in excluded_nonpositive_gastot.values()),
        "excluded_nonpositive_gastot_by_climate":{
            str(c):{"rows":x["rows"],"weight":str(x["weight"]),"weighted_signed_gastot":str(x["signed_gastot"])}
            for c,x in sorted(excluded_nonpositive_gastot.items())
        },
        "respondent_level_output_written":False,
    }
    output=Path(output).expanduser().resolve(); output.mkdir(parents=True,exist_ok=True)
    _write_csv(output/"national_reference_variants.csv",list(national_rows[0]),national_rows)
    _write_csv(output/"regional_reference_variants.csv",list(regional_rows[0]),regional_rows)
    if split_rows:
        _write_csv(output/"division02_alcohol_tobacco_split.csv",list(split_rows[0]),split_rows)
    (output/"division02_split_summary.json").write_bytes(canonical_json(split_summary))
    (output/"qa.json").write_bytes(canonical_json(qa))
    (output/"receipt.json").write_bytes(canonical_json({
        "schema":"cedlas-dt370-engho-provenance/v1",
        "engho_release_id":json.loads((engho_release/"output-manifest.json").read_text())["release_id"],
        "reference_groups":{"very_low":1,"low":2},
        "household_fields":["pondera","clima_educativo","region","gastot"]+[f"gc_{i:02d}" for i in range(1,13)],
        "expenditure_split_fields":["id","division","grupo","monto"],
        "outputs_are_aggregates_only":True,
        "qa":qa,
        "warnings":["nonpositive_gastot_rows_excluded_from_low_education_shares"],
    }))
    return output
