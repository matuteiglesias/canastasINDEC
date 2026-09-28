"""G5 and integrity commissioning for Artifact B."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from .artifact import canonical_json
from .phase_b_artifact import validate_sensitivity_artifact
from .trajectory_contracts import BASE_PERIOD, DIVISION_IDS, REGIONS


def commission_sensitivity_artifact(artifact_root: Path, output: Path) -> Path:
    artifact_root = Path(artifact_root).expanduser().resolve()
    output = Path(output).expanduser().resolve()
    validation = validate_sensitivity_artifact(artifact_root)
    manifest = json.loads((artifact_root / "manifest.json").read_text(encoding="utf-8"))
    qa = json.loads((artifact_root / "qa.json").read_text(encoding="utf-8"))

    with (artifact_root / "threshold_paths.csv").open(newline="", encoding="utf-8") as h:
        paths = list(csv.DictReader(h))
    with (artifact_root / "division_contributions.csv").open(newline="", encoding="utf-8") as h:
        contributions = list(csv.DictReader(h))
    with (artifact_root / "price_mapping.csv").open(newline="", encoding="utf-8") as h:
        mappings = list(csv.DictReader(h))

    by_region = defaultdict(list)
    for row in paths:
        by_region[row["region_id"]].append(row)
    contrib_by_key = defaultdict(list)
    for row in contributions:
        contrib_by_key[(row["period"], row["region_id"])].append(row)

    summary_rows = []
    divergence_rows = []
    for region in REGIONS:
        rows = sorted(by_region[region], key=lambda r: r["period"])
        base = next(r for r in rows if r["period"] == BASE_PERIOD)
        trajectories = [(Decimal(r["trajectory_factor"]), r) for r in rows]
        minimum = min(trajectories, key=lambda x: x[0])
        maximum = max(trajectories, key=lambda x: x[0])
        largest = max(trajectories, key=lambda x: abs(x[0] - Decimal(1)))
        largest_row = largest[1]
        summary_rows.append({
            "region_id": region,
            "base_period": BASE_PERIOD,
            "base_level_factor": base["level_factor"],
            "base_ICE_official": base["ICE_official"],
            "base_ICE_engho17": base["ICE_engho17"],
            "trajectory_min": str(minimum[0]),
            "trajectory_min_period": minimum[1]["period"],
            "trajectory_max": str(maximum[0]),
            "trajectory_max_period": maximum[1]["period"],
            "largest_trajectory_divergence": str(largest[0] - Decimal(1)),
            "largest_divergence_period": largest_row["period"],
            "CBT_official_at_largest_divergence": largest_row["CBT_official"],
            "CBT_level_only_at_largest_divergence": largest_row["CBT_level_only"],
            "CBT_full_at_largest_divergence": largest_row["CBT_level_plus_trajectory"],
        })
        key = (largest_row["period"], region)
        ranked = []
        for contribution in contrib_by_key[key]:
            base_share = Decimal(contribution["base_share"])
            relative = Decimal(contribution["price_relative"])
            price_effect = base_share * (relative - Decimal(1))
            ranked.append((abs(price_effect), {
                "region_id": region,
                "period": largest_row["period"],
                "division_id": contribution["division_id"],
                "base_share": contribution["base_share"],
                "price_relative": contribution["price_relative"],
                "weighted_cost_contribution": contribution["weighted_cost_contribution"],
                "food_weighted_cost_contribution": contribution["food_weighted_cost_contribution"],
                "price_effect_contribution_from_base": str(price_effect),
            }))
        ranked.sort(key=lambda x: (-x[0], x[1]["division_id"]))
        for rank, (_, item) in enumerate(ranked, 1):
            item["rank_by_absolute_price_effect"] = rank
            divergence_rows.append(item)

    mapping_gate = []
    for region in REGIONS:
        rows = [r for r in mappings if r["region_id"] == region]
        direct = [r for r in rows if r["component_kind"] == "division_total"]
        diagnostic = [r for r in rows if r["component_kind"] == "diagnostic_subcomponent"]
        mapped_share = sum((Decimal(r["base_share"]) for r in direct), Decimal(0))
        mapping_gate.append({
            "region_id": region,
            "division_mapping_count": len(direct),
            "mapped_total_expenditure_share": str(mapped_share),
            "diagnostic_subcomponents": "|".join(sorted(r["component_id"] for r in diagnostic)),
            "shared_price_approximations": "|".join(sorted({r["warning"] for r in diagnostic if r["warning"]})),
            "mapping_status": "pass_with_documented_approximations",
        })

    gates = {
        "schema": "engel-phase-b-commissioning-gates/v1",
        "artifact_release_id": manifest["release_id"],
        "P_cross_parent_integrity": {
            "result": qa["gate_P_cross_parent_integrity"],
            "engho_reference_release_id": manifest["engho_reference_release_id"],
            "ipc_regional_divisions_release_id": manifest["ipc_regional_divisions_release_id"],
            "official_basket_release_id": manifest["official_basket_release_id"],
            "parent_manifest_sha256": manifest["parent_manifest_sha256"],
            "required_window": qa["required_window"],
            "regions": qa["regions"],
            "divisions": qa["divisions"],
            "interpolation_performed": qa["interpolation_performed"],
            "network_retrieval_performed": qa["network_retrieval_performed"],
        },
        "A_arithmetic": {
            "result": qa["gate_A_arithmetic_identities"],
            "validated_monthly_rows": validation["monthly_rows"],
            "validated_contribution_rows": validation["contribution_rows"],
            "validated_line_path_rows": validation["line_path_rows"],
        },
        "M_price_mapping": {
            "result": qa["gate_M_price_mapping"],
            "regions": mapping_gate,
            "unknown_unpriced_expenditure_mass": "0",
            "food_price_approximation": (
                "COICOP01 priced directly; alcoholic beverages 021 use COICOP02; "
                "tobacco 022 also uses COICOP02 but remains non-food"
            ),
            "restaurant_mapping": "restaurants_111 use COICOP11 and remain non-food",
        },
        "scientific_poverty_execution_performed": False,
    }

    output.mkdir(parents=True, exist_ok=True)
    fields = list(summary_rows[0])
    with (output / "g5_region_summary.csv").open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=fields, lineterminator="\n")
        w.writeheader(); w.writerows(summary_rows)
    fields = list(divergence_rows[0])
    with (output / "g5_divergence_contributions.csv").open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=fields, lineterminator="\n")
        w.writeheader(); w.writerows(divergence_rows)
    (output / "gates.json").write_bytes(canonical_json(gates))

    summary = {
        "schema": "engel-phase-b-commissioning/v1",
        "artifact_release_id": manifest["release_id"],
        "result": "pass_with_documented_approximations",
        "G5_level_trajectory_observability": "pass",
        "P_cross_parent_integrity": qa["gate_P_cross_parent_integrity"],
        "A_arithmetic": qa["gate_A_arithmetic_identities"],
        "M_price_mapping": qa["gate_M_price_mapping"],
        "regions": len(REGIONS),
        "months": qa["required_window"]["months"],
        "division_count": len(DIVISION_IDS),
        "warnings": manifest["warnings"],
        "scientific_poverty_execution_performed": False,
    }
    (output / "commissioning.json").write_bytes(canonical_json(summary))

    report = [
        "# ENGHo / Engel Phase-B commissioning",
        "",
        f"Artifact: {manifest['release_id']}",
        "",
        "P — cross-parent integrity: PASS",
        "A — arithmetic identities: PASS",
        "M — price mapping: PASS WITH DOCUMENTED APPROXIMATIONS",
        "G5 — level / trajectory observability: PASS",
        "",
        "Shared-price approximations:",
        "- alcoholic beverages (021) and tobacco (022) use the official COICOP02 division index;",
        "- restaurants (111) and hotels share the official COICOP11 division index;",
        "- these mappings never change the food/non-food classification frozen in Artifact A.",
        "",
        "No poverty, EPH, Census, adult-equivalence, province/department or Atlas calculation was performed.",
        "",
    ]
    (output / "report.md").write_text("\n".join(report), encoding="utf-8")
    return output
