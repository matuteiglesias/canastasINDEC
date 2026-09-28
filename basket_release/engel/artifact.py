"""Build and validate the Phase-A ENGHo reference expenditure artifact."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import tempfile
from collections import defaultdict
from decimal import Decimal
from pathlib import Path, PurePosixPath

from basket_release.core import BuildError
from .article_classification import build_article_mapping
from .contracts import (
    ARTIFACT_TYPE,
    BASE_PERIOD,
    DIVISION_IDS,
    FOOD_SCOPE,
    METHOD_ID,
    PERCENTILE_HIGH,
    PERCENTILE_LOW,
    RANKING_VARIABLE,
    REFERENCE_POPULATION_METHOD,
    REGIONS,
    RESTAURANTS_IN_FOOD,
    STATUS,
    SURVEY_VINTAGE,
    TOBACCO_IN_FOOD,
    VALUE_STATUS,
    WEIGHT_VARIABLE,
)
from .expenditure_structure import (
    aggregate_structure,
    build_household_expenditure_profiles,
    selected_accounting,
)
from .parents import load_engho_parent, sha256
from .reference_population import effective_sample_size, select_reference_population
from .replicate_weights import bootstrap_diagnostics


def _jsonable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def canonical_json(value) -> bytes:
    return (json.dumps(_jsonable(value), indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _jsonable(row.get(field, "")) for field in fields})


def _safe_file(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or relative in {"", "."}:
        raise BuildError(f"engel_artifact_unsafe_path: {relative}")
    path = (root / relative).resolve()
    if root.resolve() not in path.parents:
        raise BuildError(f"engel_artifact_unsafe_path: {relative}")
    return path


def _reference_population_id(parent: dict, selection: dict) -> str:
    payload = {
        "parent_release_id": parent["release_id"],
        "parent_manifest_sha256": parent["manifest_sha256"],
        "method_id": METHOD_ID,
        "reference_population_method": REFERENCE_POPULATION_METHOD,
        "ranking_variable": RANKING_VARIABLE,
        "weight_variable": WEIGHT_VARIABLE,
        "percentile_low": PERCENTILE_LOW,
        "percentile_high": PERCENTILE_HIGH,
        "algorithm": selection["algorithm"],
        "cohort_hash": selection["cohort_hash"],
    }
    digest = hashlib.sha256(canonical_json(payload)).hexdigest()
    return "engho17-refpop-" + digest[:16]


def _universe_region_weights(prepared: list[dict]) -> dict[str, Decimal]:
    totals = defaultdict(Decimal)
    totals["national"] = sum((row["weight"] for row in prepared), Decimal(0))
    for row in prepared:
        totals[row["region_id"]] += row["weight"]
    return dict(totals)


def build_reference_artifact(
    parent_root: Path,
    output_parent: Path,
    *,
    upstream_receipt: Path | None = None,
) -> Path:
    parent = load_engho_parent(parent_root, upstream_receipt=upstream_receipt)
    households = parent["tables"]["households"]
    expenditures = parent["tables"]["expenditures"]
    articles = parent["tables"]["articles"]
    replicates = parent["tables"]["replicate_weights"]

    selection = select_reference_population(households)
    reference_population_id = _reference_population_id(parent, selection)
    article_mapping = build_article_mapping(articles)
    known_households = {row["id"] for row in selection["prepared"]}
    profiles, profile_diagnostics = build_household_expenditure_profiles(
        expenditures, article_mapping, known_households
    )
    point = aggregate_structure(selection["selected"], profiles)
    bootstrap = bootstrap_diagnostics(households, replicates, profiles, point)
    accounting = selected_accounting(selection["selected_ids"], expenditures, article_mapping)
    universe_region_weights = _universe_region_weights(selection["prepared"])

    rows = []
    for region_id in REGIONS:
        row = point[region_id]
        universe_weight = universe_region_weights[region_id]
        metric_food = bootstrap["regions"][region_id]["food_share"]
        metric_ice = bootstrap["regions"][region_id]["ice_base"]
        payload = {
            "engho_vintage": SURVEY_VINTAGE,
            "reference_population_id": reference_population_id,
            "reference_population_method": REFERENCE_POPULATION_METHOD,
            "ranking_variable": RANKING_VARIABLE,
            "weight_variable": WEIGHT_VARIABLE,
            "percentile_low": PERCENTILE_LOW,
            "percentile_high": PERCENTILE_HIGH,
            "region_id": region_id,
            "unweighted_households": row["unweighted_households"],
            "weighted_households": row["weighted_households"],
            "weighted_population_share": row["weighted_population_share"],
            "selected_weight_share_of_region_universe": row["weighted_households"] / universe_weight,
            "effective_sample_size": row["effective_sample_size"],
            "food_expenditure": row["food_expenditure"],
            "total_expenditure": row["total_expenditure"],
            "food_share": row["food_share"],
            "ice_base": row["ice_base"],
            "food_scope": FOOD_SCOPE,
            "restaurants_in_food": str(RESTAURANTS_IN_FOOD).lower(),
            "tobacco_in_food": str(TOBACCO_IN_FOOD).lower(),
            "restaurant_expenditure": row["restaurant_expenditure"],
            "tobacco_expenditure": row["tobacco_expenditure"],
            "alcohol_expenditure": row["alcohol_expenditure"],
            "imputed_expenditure_share": row["imputed_expenditure_share"],
            "base_period": BASE_PERIOD,
            "method_id": METHOD_ID,
            "engho_parent_release_id": parent["release_id"],
            "engho_parent_manifest_sha256": parent["manifest_sha256"],
            "value_status": VALUE_STATUS,
            "food_share_replicate_standard_error": metric_food["replicate_standard_error"],
            "food_share_interval_low": metric_food["lower_interval"],
            "food_share_interval_high": metric_food["upper_interval"],
            "ice_replicate_standard_error": metric_ice["replicate_standard_error"],
            "ice_interval_low": metric_ice["lower_interval"],
            "ice_interval_high": metric_ice["upper_interval"],
            "number_of_replicates": bootstrap["number_of_replicates"],
        }
        for division in DIVISION_IDS:
            payload[f"division_{division[-2:]}_share"] = row["division_shares"][division]
        rows.append(payload)

    method_seed = {
        "artifact_type": ARTIFACT_TYPE,
        "method_id": METHOD_ID,
        "parent_release_id": parent["release_id"],
        "parent_manifest_sha256": parent["manifest_sha256"],
        "reference_population_id": reference_population_id,
    }
    release_id = "engel-reference-" + hashlib.sha256(canonical_json(method_seed)).hexdigest()[:16]
    output_parent = Path(output_parent).expanduser().resolve()
    output_parent.mkdir(parents=True, exist_ok=True)
    final = output_parent / release_id
    if final.exists():
        validate_reference_artifact(final)
        return final
    staging = Path(tempfile.mkdtemp(prefix=f".{release_id}.", dir=output_parent))
    try:
        fields = [
            "engho_vintage", "reference_population_id", "reference_population_method",
            "ranking_variable", "weight_variable", "percentile_low", "percentile_high",
            "region_id", "unweighted_households", "weighted_households",
            "weighted_population_share", "selected_weight_share_of_region_universe",
            "effective_sample_size", "food_expenditure", "total_expenditure",
            "food_share", "ice_base",
            *[f"division_{i:02d}_share" for i in range(1, 13)],
            "food_scope", "restaurants_in_food", "tobacco_in_food",
            "restaurant_expenditure", "tobacco_expenditure", "alcohol_expenditure",
            "imputed_expenditure_share", "base_period", "method_id",
            "engho_parent_release_id", "engho_parent_manifest_sha256", "value_status",
            "food_share_replicate_standard_error", "food_share_interval_low",
            "food_share_interval_high", "ice_replicate_standard_error",
            "ice_interval_low", "ice_interval_high", "number_of_replicates",
        ]
        _write_csv(staging / "reference_structure.csv", fields, rows)

        mapping_fields = [
            "article_code", "division_code", "division_id", "group_code",
            "food", "alcoholic_beverage", "tobacco", "restaurant", "hotel",
            "article_desc", "division_desc", "group_desc",
        ]
        mapping_rows = [article_mapping[key] for key in sorted(article_mapping)]
        _write_csv(staging / "article_mapping.csv", mapping_fields, mapping_rows)

        diagnostics = {
            "reference_population": {
                "reference_population_id": reference_population_id,
                "algorithm": selection["algorithm"],
                "method": selection["method"],
                "cut_lower": selection["cut_lower"],
                "cut_upper": selection["cut_upper"],
                "unweighted_universe": selection["unweighted_universe"],
                "unweighted_selected": selection["unweighted_selected"],
                "weighted_universe": selection["weighted_universe"],
                "weighted_selected": selection["weighted_selected"],
                "selected_weight_share": selection["selected_weight_share"],
                "lower_tie_households": selection["lower_tie_households"],
                "lower_tie_weight": selection["lower_tie_weight"],
                "upper_tie_households": selection["upper_tie_households"],
                "upper_tie_weight": selection["upper_tie_weight"],
                "cohort_hash": selection["cohort_hash"],
                "zero_and_negative_income_policy": "retained_and_ranked",
                "missing_or_nonfinite_income_policy": "hard_failure",
            },
            "expenditure_profile": profile_diagnostics,
            "selected_expenditure_accounting": accounting,
            "bootstrap": bootstrap,
            "parent": {
                "release_id": parent["release_id"],
                "manifest_sha256": parent["manifest_sha256"],
                "warnings": parent["warnings"],
                "persons_consumed": parent["persons_consumed"],
                "upstream_receipt": parent["upstream_receipt"],
            },
            "scientific_poverty_execution_performed": False,
            "price_trajectory_execution_performed": False,
            "cbt_execution_performed": False,
        }
        (staging / "diagnostics.json").write_bytes(canonical_json(diagnostics))

        warnings = list(parent["warnings"])
        if bootstrap["number_of_replicates"] != bootstrap["expected_real_replicates"]:
            warnings.append("replicate_count_differs_from_real_engho_expected_200")
        qa = {
            "result": "pass_with_warnings" if warnings else "pass",
            "warnings": sorted(set(warnings)),
            "hard_failures": [],
            "g1_reference_population_integrity": "pass",
            "g2_expenditure_accounting": "pass",
            "g4_regional_stability_available": True,
            "persons_table_consumed": False,
            "scientific_poverty_execution_performed": False,
            "price_trajectory_execution_performed": False,
            "cbt_execution_performed": False,
        }
        (staging / "qa.json").write_bytes(canonical_json(qa))

        files = {}
        for path in sorted(staging.iterdir()):
            if path.is_file():
                files[path.name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
        manifest = {
            "schema": "research-artifact-manifest/v1",
            "artifact_type": ARTIFACT_TYPE,
            "release_id": release_id,
            "status": STATUS,
            "method_id": METHOD_ID,
            "survey_vintage": SURVEY_VINTAGE,
            "base_period": BASE_PERIOD,
            "reference_population_id": reference_population_id,
            "engho_parent": {
                "artifact_type": parent["manifest"]["artifact_type"],
                "release_id": parent["release_id"],
                "manifest_sha256": parent["manifest_sha256"],
                "warnings": parent["warnings"],
                "upstream_receipt": parent["upstream_receipt"],
            },
            "regions": list(REGIONS),
            "division_ids": list(DIVISION_IDS),
            "food_scope": FOOD_SCOPE,
            "restaurants_in_food": RESTAURANTS_IN_FOOD,
            "tobacco_in_food": TOBACCO_IN_FOOD,
            "warnings": sorted(set(warnings)),
            "scientific_poverty_execution_performed": False,
            "price_trajectory_execution_performed": False,
            "cbt_execution_performed": False,
            "files": files,
        }
        (staging / "manifest.json").write_bytes(canonical_json(manifest))
        os.replace(staging, final)
        validate_reference_artifact(final)
        return final
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def validate_reference_artifact(root: Path) -> dict:
    root = Path(root).expanduser().resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise BuildError("engel_artifact_missing_manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("artifact_type") != ARTIFACT_TYPE or manifest.get("method_id") != METHOD_ID:
        raise BuildError("engel_artifact_identity_mismatch")
    if manifest.get("status") != STATUS:
        raise BuildError("engel_artifact_status_mismatch")
    if any(manifest.get(key) is not False for key in (
        "scientific_poverty_execution_performed",
        "price_trajectory_execution_performed",
        "cbt_execution_performed",
    )):
        raise BuildError("engel_phase_a_scope_violation")
    for name, identity in manifest.get("files", {}).items():
        path = _safe_file(root, name)
        if not path.is_file() or path.stat().st_size != identity.get("bytes") or sha256(path) != identity.get("sha256"):
            raise BuildError(f"engel_artifact_file_mismatch: {name}")

    with (root / "reference_structure.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != len(REGIONS) or {row["region_id"] for row in rows} != set(REGIONS):
        raise BuildError("engel_artifact_region_inventory_mismatch")
    for row in rows:
        division_sum = sum((Decimal(row[f"division_{i:02d}_share"]) for i in range(1, 13)), Decimal(0))
        if abs(division_sum - Decimal(1)) > Decimal("1e-20"):
            raise BuildError(f"engel_artifact_division_share_failure: {row['region_id']}")
        food_share = Decimal(row["food_share"])
        ice = Decimal(row["ice_base"])
        if abs(ice * food_share - Decimal(1)) > Decimal("1e-20"):
            raise BuildError(f"engel_artifact_ice_identity_failure: {row['region_id']}")
        if row["restaurants_in_food"] != "false" or row["tobacco_in_food"] != "false":
            raise BuildError("engel_artifact_food_scope_violation")
    return {
        "result": "compatible_with_warnings" if manifest.get("warnings") else "compatible",
        "release_id": manifest["release_id"],
        "artifact_type": ARTIFACT_TYPE,
        "method_id": METHOD_ID,
        "rows": len(rows),
        "warnings": manifest.get("warnings", []),
    }
