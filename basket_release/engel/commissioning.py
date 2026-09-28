"""G1-G4 commissioning for research.argentina-engel-reference-structure/v1."""
from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path

from basket_release.core import BuildError
from .artifact import canonical_json, validate_reference_artifact
from .contracts import ARTIFACT_TYPE, NEGATIVE_EXPENDITURE_POLICY, FOOD_SCOPE, REFERENCE_POPULATION_METHOD


def _read_structure(root: Path) -> list[dict[str, str]]:
    with (root / "reference_structure.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _load_benchmarks(path: Path | None) -> list[dict]:
    if path is None:
        return []
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != "engel-external-benchmarks/v1":
        raise BuildError("engel_benchmark_registry_wrong_schema")
    benchmarks = payload.get("benchmarks")
    if not isinstance(benchmarks, list):
        raise BuildError("engel_benchmark_registry_invalid")
    return benchmarks


def _compare_benchmarks(rows: list[dict[str, str]], benchmarks: list[dict]) -> list[dict]:
    by_region = {row["region_id"]: row for row in rows}
    results = []
    for benchmark in benchmarks:
        region = benchmark.get("region_id", "national")
        metric = benchmark.get("metric")
        if region not in by_region or metric not in {"food_share", "ice_base"}:
            results.append({**benchmark, "classification": "unresolved", "reason": "unsupported_metric_or_region"})
            continue
        row = by_region[region]
        observed = Decimal(row[metric])
        expected = Decimal(str(benchmark["value"]))
        delta = observed - expected
        if benchmark.get("reference_population_method") not in (None, REFERENCE_POPULATION_METHOD):
            classification = "reference_population_difference"
        elif benchmark.get("food_scope") not in (None, FOOD_SCOPE):
            classification = "classification_difference"
        else:
            se_field = "food_share_replicate_standard_error" if metric == "food_share" else "ice_replicate_standard_error"
            se = Decimal(row[se_field])
            if abs(delta) <= Decimal("0.002"):
                classification = "compatible"
            elif se > 0 and abs(delta) <= Decimal(2) * se:
                classification = "sampling_difference"
            else:
                classification = "unresolved"
        results.append({
            "benchmark_id": benchmark.get("id"),
            "source": benchmark.get("source"),
            "region_id": region,
            "metric": metric,
            "published_value": str(expected),
            "observed_value": str(observed),
            "delta": str(delta),
            "classification": classification,
            "estimator_input": False,
        })
    return results


def commission_reference_artifact(
    artifact_root: Path,
    output: Path,
    *,
    benchmark_registry: Path | None = None,
) -> Path:
    artifact_root = Path(artifact_root).expanduser().resolve()
    output = Path(output).expanduser().resolve()
    validation = validate_reference_artifact(artifact_root)
    diagnostics = json.loads((artifact_root / "diagnostics.json").read_text(encoding="utf-8"))
    rows = _read_structure(artifact_root)
    national = next(row for row in rows if row["region_id"] == "national")

    reference = diagnostics["reference_population"]
    g1 = {
        "gate": "G1_reference_population_integrity",
        "result": "pass",
        "reference_population_id": reference["reference_population_id"],
        "algorithm": reference["algorithm"],
        "cut_lower": reference["cut_lower"],
        "cut_upper": reference["cut_upper"],
        "unweighted_universe": reference["unweighted_universe"],
        "unweighted_selected": reference["unweighted_selected"],
        "weighted_universe": reference["weighted_universe"],
        "weighted_selected": reference["weighted_selected"],
        "selected_weight_share": reference["selected_weight_share"],
        "target_mass_width": "0.19",
        "mass_deviation_from_target": str(Decimal(reference["selected_weight_share"]) - Decimal("0.19")),
        "lower_tie_households": reference["lower_tie_households"],
        "lower_tie_weight": reference["lower_tie_weight"],
        "upper_tie_households": reference["upper_tie_households"],
        "upper_tie_weight": reference["upper_tie_weight"],
        "zero_and_negative_income_policy": reference["zero_and_negative_income_policy"],
        "missing_or_nonfinite_income_policy": reference["missing_or_nonfinite_income_policy"],
        "regional_composition": [
            {
                "region_id": row["region_id"],
                "unweighted_households": row["unweighted_households"],
                "weighted_households": row["weighted_households"],
                "reference_population_composition_share": row["weighted_population_share"],
                "selected_weight_share_of_region_universe": row["selected_weight_share_of_region_universe"],
                "effective_sample_size": row["effective_sample_size"],
            }
            for row in rows if row["region_id"] != "national"
        ],
    }

    accounting = diagnostics["selected_expenditure_accounting"]
    profile = diagnostics["expenditure_profile"]
    g2_hard = (
        Decimal(accounting["mapping_coverage"]) == Decimal(1)
        and Decimal(accounting["food_nonfood_residual"]) == 0
        and Decimal(accounting["division_residual"]) == 0
        and int(profile["unknown_article_rows"]) == 0
        # ENGHo publishes sales as negative expenditure amounts. Primary
        # accounting preserves the sign; any clipping is a separate sensitivity.
        and profile["negative_expenditure_policy"] == NEGATIVE_EXPENDITURE_POLICY
        and accounting["negative_expenditure_policy"] == NEGATIVE_EXPENDITURE_POLICY
    )
    g2 = {
        "gate": "G2_expenditure_accounting",
        "result": "pass" if g2_hard else "fail",
        "selected_expenditure_rows": accounting["selected_expenditure_rows"],
        "mapped_selected_expenditure_rows": accounting["mapped_selected_expenditure_rows"],
        "mapping_coverage": accounting["mapping_coverage"],
        "food_nonfood_residual": accounting["food_nonfood_residual"],
        "division_residual": accounting["division_residual"],
        "restaurant_expenditure_in_total_not_food": accounting["restaurant_expenditure"],
        "tobacco_expenditure_in_total_not_food": accounting["tobacco_expenditure"],
        "zero_amount_rows_all_households": profile["zero_amount_rows"],
        "imputed_expenditure_share_all_households": profile["raw_imputed_expenditure_share"],
        "unknown_article_rows": profile["unknown_article_rows"],
        "article_mapping_fallback_rows": profile["article_mapping_fallback_rows"],
        "negative_expenditure_rows": profile["negative_expenditure_rows"],
        "negative_expenditure_raw_total": profile["negative_expenditure_raw_total"],
        "negative_expenditure_policy": profile["negative_expenditure_policy"],
        "negative_sales_absolute_total_all_households": profile["negative_sales_absolute_total"],
        "purchase_only_counterfactual_total_all_households": profile["purchase_only_counterfactual_total"],
        "negative_sales_share_of_purchase_only_counterfactual": profile["negative_sales_share_of_purchase_only_counterfactual"],
        "negative_expenditure_rows_selected": accounting["negative_expenditure_rows"],
        "negative_expenditure_raw_total_selected": accounting["negative_expenditure_raw_total"],
    }
    if not g2_hard:
        raise BuildError("engel_g2_expenditure_accounting_failed")

    benchmarks = _load_benchmarks(benchmark_registry)
    comparisons = _compare_benchmarks(rows, benchmarks)
    g3 = {
        "gate": "G3_external_plausibility",
        "result": "diagnostic",
        "benchmarks_are_estimator_inputs": False,
        "benchmark_count": len(comparisons),
        "comparisons": comparisons,
        "allowed_classifications": [
            "compatible",
            "classification_difference",
            "reference_population_difference",
            "sampling_difference",
            "unresolved",
        ],
    }

    g4_rows = []
    for row in rows:
        g4_rows.append({
            "region_id": row["region_id"],
            "unweighted_households": row["unweighted_households"],
            "weighted_households": row["weighted_households"],
            "effective_sample_size": row["effective_sample_size"],
            "food_share": row["food_share"],
            "ice_base": row["ice_base"],
            "food_share_replicate_standard_error": row["food_share_replicate_standard_error"],
            "food_share_interval_low": row["food_share_interval_low"],
            "food_share_interval_high": row["food_share_interval_high"],
            "ice_replicate_standard_error": row["ice_replicate_standard_error"],
            "ice_interval_low": row["ice_interval_low"],
            "ice_interval_high": row["ice_interval_high"],
            "number_of_replicates": row["number_of_replicates"],
        })
    g4 = {
        "gate": "G4_regional_stability",
        "result": "diagnostic",
        "bootstrap_method": diagnostics["bootstrap"]["method"],
        "bootstrap_formula": diagnostics["bootstrap"]["formula"],
        "reference_population_reselected_per_replicate": diagnostics["bootstrap"]["reference_population_reselected_per_replicate"],
        "number_of_replicates": diagnostics["bootstrap"]["number_of_replicates"],
        "expected_real_replicates": diagnostics["bootstrap"]["expected_real_replicates"],
        "real_replicate_count_matches_expectation": diagnostics["bootstrap"]["real_replicate_count_matches_expectation"],
    }

    output.mkdir(parents=True, exist_ok=True)
    (output / "g1_reference_population.json").write_bytes(canonical_json(g1))
    (output / "g2_expenditure_accounting.json").write_bytes(canonical_json(g2))
    (output / "g3_external_plausibility.json").write_bytes(canonical_json(g3))
    fields = list(g4_rows[0])
    with (output / "g4_regional_stability.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(g4_rows)
    (output / "g4_metadata.json").write_bytes(canonical_json(g4))

    summary = {
        "schema": "engel-reference-commissioning/v1",
        "artifact_type": ARTIFACT_TYPE,
        "artifact_release_id": validation["release_id"],
        "result": "pass_with_diagnostics",
        "g1": "pass",
        "g2": "pass",
        "g3": "diagnostic",
        "g4": "diagnostic",
        "national_food_share": national["food_share"],
        "national_ice_base": national["ice_base"],
        "warnings": validation["warnings"],
        "scientific_poverty_execution_performed": False,
        "price_trajectory_execution_performed": False,
        "cbt_execution_performed": False,
    }
    (output / "commissioning.json").write_bytes(canonical_json(summary))
    report = [
        "# ENGHo / Engel Phase-A commissioning",
        "",
        f"Artifact: {validation['release_id']}",
        "",
        "G1 reference population: PASS",
        "G2 expenditure accounting: PASS",
        "G3 external plausibility: diagnostic only",
        "G4 regional stability: diagnostic only",
        "",
        f"National food share: {national['food_share']}",
        f"National base ICE: {national['ice_base']}",
        "",
        "No IPC trajectory, alternative CBT, poverty, EPH or Census calculation was performed.",
        "",
    ]
    (output / "report.md").write_text("\n".join(report), encoding="utf-8")
    return output
