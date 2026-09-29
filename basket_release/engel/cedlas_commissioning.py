"""Commission CEDLAS DT370 forensic threshold replication against published intermediate targets."""
from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path

from .artifact import canonical_json
from .cedlas_dt370 import validate_replication_artifact

def commission_replication(release: Path, output: Path) -> Path:
    release=Path(release).expanduser().resolve()
    validation=validate_replication_artifact(release)
    qa=json.loads((release/"qa.json").read_text(encoding="utf-8"))
    with (release/"table3_validation.csv").open(newline="",encoding="utf-8") as h:
        table3=list(csv.DictReader(h))
    with (release/"table4_validation.csv").open(newline="",encoding="utf-8") as h:
        table4=list(csv.DictReader(h))
    table3_ice=all(str(r["ice_round_2_match"]).lower()=="true" for r in table3)
    table3_share=max(Decimal(r["max_share_round_1_pp_error"]) for r in table3)
    table4_max=max(abs(Decimal(r["difference"])) for r in table4)
    primary_exact=qa.get("tobacco_in_food") is True and qa.get("regionalization")=="paper_published_ratio"
    summary={
        "schema":"cedlas-dt370-replication-commissioning/v1",
        "release_id":validation["release_id"],
        "primary_paper_specification":primary_exact,
        "table3_ice_rounding":"pass" if table3_ice else "fail",
        "table3_regional_share_rounding":"pass" if table3_share<=Decimal("0.1") else "fail",
        "table3_max_share_round_1_pp_error":str(table3_share),
        "table4_max_abs_ice_difference":str(table4_max),
        "table4_rounded_0_01_match":"pass" if table4_max < Decimal("0.015") else "diagnostic_mismatch",
        "poverty_replication_status":"not_run_in_canastas",
        "scientific_poverty_execution_performed":False,
        "interpretation":[
            "Table 3 proves the published national-vector/regionalization algebra.",
            "Table 4 tests whether the governed regional-division IPC surface reproduces the paper's price trajectory.",
            "Poverty Table 5 replication belongs downstream in indice-pobreza-UBA."
        ],
    }
    output=Path(output).expanduser().resolve(); output.mkdir(parents=True,exist_ok=True)
    (output/"commissioning.json").write_bytes(canonical_json(summary))
    report=[
        "# CEDLAS DT370 replication commissioning","",
        f"Release: {validation['release_id']}","",
        f"Table 3 ICE rounding: {summary['table3_ice_rounding']}",
        f"Table 3 regional-share rounding: {summary['table3_regional_share_rounding']} (max {table3_share} pp)",
        f"Table 4 max |ICE difference|: {table4_max}",
        f"Table 4 0.01-rounding target: {summary['table4_rounded_0_01_match']}","",
        "No poverty calculation is performed in Canastas."
    ]
    (output/"report.md").write_text("\n".join(report)+"\n",encoding="utf-8")
    return output
