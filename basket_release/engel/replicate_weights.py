"""Official ENGHo replicate-weight diagnostics for Phase-A reference structures."""
from __future__ import annotations

import re
from decimal import Decimal

from basket_release.core import BuildError
from .contracts import (
    BOOTSTRAP_VARIANCE_FORMULA,
    BOOTSTRAP_VARIANCE_METHOD,
    EXPECTED_REPLICATES_REAL,
    INTERVAL_Z,
)
from .expenditure_structure import aggregate_structure
from .reference_population import select_reference_population


_REP_RE = re.compile(r"^(?:whog_)?(?:w_)?rep(?:lica)?_?(\d+)$", re.IGNORECASE)


def discover_replicate_columns(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        raise BuildError("empty_replicate_weight_table")
    found = []
    for name in rows[0]:
        match = _REP_RE.match(name.strip())
        if match:
            found.append((int(match.group(1)), name))
    found.sort()
    columns = [name for _, name in found]
    if not columns:
        raise BuildError("no_engho_replicate_weight_columns")
    numbers = [number for number, _ in found]
    if numbers != list(range(1, len(numbers) + 1)):
        raise BuildError(f"noncontiguous_replicate_weight_columns: {numbers[:5]}...{numbers[-5:]}")
    return columns


def _replicate_weight_maps(rows: list[dict[str, str]], columns: list[str]) -> list[dict[str, str]]:
    by_id: dict[str, dict[str, str]] = {}
    for row in rows:
        household_id = str(row.get("id", "")).strip()
        if not household_id:
            raise BuildError("replicate_weight_missing_household_id")
        if household_id in by_id:
            raise BuildError(f"duplicate_replicate_household_id: {household_id}")
        by_id[household_id] = row
    maps = []
    for column in columns:
        maps.append({household_id: row.get(column, "") for household_id, row in by_id.items()})
    return maps


def _households_with_weight(
    household_rows: list[dict[str, str]],
    weights: dict[str, str],
    field: str = "__replicate_weight",
) -> list[dict[str, str]]:
    result = []
    for row in household_rows:
        household_id = str(row.get("id", "")).strip()
        if household_id not in weights:
            raise BuildError(f"replicate_weight_missing_household: {household_id}")
        copied = dict(row)
        copied[field] = weights[household_id]
        result.append(copied)
    extra = set(weights) - {str(row.get("id", "")).strip() for row in household_rows}
    if extra:
        raise BuildError(f"replicate_weight_unknown_households: {len(extra)}")
    return result


def bootstrap_diagnostics(
    household_rows: list[dict[str, str]],
    replicate_rows: list[dict[str, str]],
    profiles: dict[str, dict],
    point_structure: dict[str, dict],
) -> dict:
    """Re-run the full national p29-p48 selection for every official replicate.

    INDEC's MSE bootstrap estimator is used:
        variance = (1/B) * sum((theta_rep - theta_point)^2)
    """
    columns = discover_replicate_columns(replicate_rows)
    maps = _replicate_weight_maps(replicate_rows, columns)
    estimates = {
        region: {"food_share": [], "ice_base": []}
        for region in point_structure
    }
    reference_population_shares = []
    for weights in maps:
        rep_households = _households_with_weight(household_rows, weights)
        selection = select_reference_population(rep_households, weight_field="__replicate_weight")
        reference_population_shares.append(selection["selected_weight_share"])
        structure = aggregate_structure(selection["selected"], profiles)
        for region, row in structure.items():
            estimates[region]["food_share"].append(row["food_share"])
            estimates[region]["ice_base"].append(row["ice_base"])

    b = Decimal(len(columns))
    z = Decimal(INTERVAL_Z)
    output: dict[str, dict] = {}
    for region, metrics in estimates.items():
        output[region] = {}
        for metric, rep_values in metrics.items():
            point = point_structure[region][metric]
            variance = sum(((value - point) ** 2 for value in rep_values), Decimal(0)) / b
            se = variance.sqrt()
            output[region][metric] = {
                "estimate": point,
                "replicate_standard_error": se,
                "lower_interval": point - z * se,
                "upper_interval": point + z * se,
                "number_of_replicates": len(columns),
                "variance": variance,
            }
    return {
        "method": BOOTSTRAP_VARIANCE_METHOD,
        "formula": BOOTSTRAP_VARIANCE_FORMULA,
        "replicate_columns": columns,
        "number_of_replicates": len(columns),
        "expected_real_replicates": EXPECTED_REPLICATES_REAL,
        "real_replicate_count_matches_expectation": len(columns) == EXPECTED_REPLICATES_REAL,
        "reference_population_reselected_per_replicate": True,
        "replicate_reference_population_share_min": min(reference_population_shares),
        "replicate_reference_population_share_max": max(reference_population_shares),
        "regions": output,
    }
