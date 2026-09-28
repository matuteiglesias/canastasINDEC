"""Deterministic national weighted p29-p48 reference-population selection."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from basket_release.core import BuildError
from .contracts import (
    HOUSEHOLD_ID_VARIABLE,
    PERCENTILE_HIGH,
    PERCENTILE_LOW,
    QUANTILE_ALGORITHM,
    RANKING_VARIABLE,
    REFERENCE_POPULATION_METHOD,
    REGION_CODE_MAP,
    REGION_VARIABLE,
    WEIGHT_VARIABLE,
)


def _decimal(value: str, label: str, *, allow_zero: bool = True, allow_negative: bool = True) -> Decimal:
    try:
        number = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError) as exc:
        raise BuildError(f"invalid_{label}: {value!r}") from exc
    if not number.is_finite():
        raise BuildError(f"invalid_{label}: nonfinite")
    if not allow_negative and number < 0:
        raise BuildError(f"invalid_{label}: negative")
    if not allow_zero and number <= 0:
        raise BuildError(f"invalid_{label}: nonpositive")
    return number


def prepare_households(
    rows: list[dict[str, str]],
    weight_field: str = WEIGHT_VARIABLE,
    *,
    allow_zero_weight: bool = False,
) -> list[dict]:
    prepared = []
    seen = set()
    for row in rows:
        household_id = str(row.get(HOUSEHOLD_ID_VARIABLE, "")).strip()
        if not household_id:
            raise BuildError("missing_household_id")
        if household_id in seen:
            raise BuildError(f"duplicate_household_id: {household_id}")
        seen.add(household_id)
        # Zero and negative incomes remain rankable. Missing/non-numeric values fail closed
        # so the reference universe never changes silently.
        income = _decimal(row.get(RANKING_VARIABLE, ""), "ranking_income")
        weight = _decimal(
            row.get(weight_field, ""),
            "household_weight",
            allow_zero=allow_zero_weight,
            allow_negative=False,
        )
        region_code = str(row.get(REGION_VARIABLE, "")).strip()
        if region_code not in REGION_CODE_MAP:
            raise BuildError(f"invalid_engho_region_code: {region_code!r}")
        prepared.append({
            "id": household_id,
            "income": income,
            "weight": weight,
            "region_id": REGION_CODE_MAP[region_code],
        })
    if not prepared:
        raise BuildError("empty_household_universe")
    return prepared


def weighted_cutpoint(prepared: list[dict], probability: Decimal) -> Decimal:
    if probability <= 0 or probability >= 1:
        raise BuildError("weighted_quantile_probability_out_of_bounds")
    grouped: dict[Decimal, Decimal] = defaultdict(Decimal)
    total = Decimal(0)
    for row in prepared:
        grouped[row["income"]] += row["weight"]
        total += row["weight"]
    threshold = total * probability
    cumulative = Decimal(0)
    for income in sorted(grouped):
        cumulative += grouped[income]
        if cumulative >= threshold:
            return income
    return max(grouped)


def select_reference_population(
    household_rows: list[dict[str, str]],
    *,
    weight_field: str = WEIGHT_VARIABLE,
    percentile_low: Decimal = Decimal(PERCENTILE_LOW),
    percentile_high: Decimal = Decimal(PERCENTILE_HIGH),
    allow_zero_weight: bool = False,
) -> dict:
    """Select the national weighted reference cohort.

    Cutpoints are weighted ECDF support values. The selected interval is
    lower-inclusive and upper-exclusive: income >= q(p29) and income < q(p48).
    This keeps all households tied at either income value together; consequently
    achieved mass can deviate from exactly 19 percentage points.
    """
    prepared = prepare_households(
        household_rows,
        weight_field=weight_field,
        allow_zero_weight=allow_zero_weight,
    )
    lower = weighted_cutpoint(prepared, percentile_low)
    upper = weighted_cutpoint(prepared, percentile_high)
    if upper <= lower:
        raise BuildError("reference_population_cutpoints_not_ordered")
    selected = [row for row in prepared if row["income"] >= lower and row["income"] < upper]
    if not selected:
        raise BuildError("empty_reference_population")

    total_weight = sum((row["weight"] for row in prepared), Decimal(0))
    selected_weight = sum((row["weight"] for row in selected), Decimal(0))
    lower_ties = [row for row in prepared if row["income"] == lower]
    upper_ties = [row for row in prepared if row["income"] == upper]

    selection_payload = {
        "algorithm": QUANTILE_ALGORITHM,
        "ranking_variable": RANKING_VARIABLE,
        "weight_variable": weight_field,
        "percentile_low": str(percentile_low),
        "percentile_high": str(percentile_high),
        "lower_cut": str(lower),
        "upper_cut": str(upper),
        "selected_ids": sorted(row["id"] for row in selected),
    }
    cohort_hash = hashlib.sha256(
        (json.dumps(selection_payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    ).hexdigest()

    return {
        "prepared": prepared,
        "selected": selected,
        "selected_ids": {row["id"] for row in selected},
        "cut_lower": lower,
        "cut_upper": upper,
        "unweighted_universe": len(prepared),
        "unweighted_selected": len(selected),
        "weighted_universe": total_weight,
        "weighted_selected": selected_weight,
        "selected_weight_share": selected_weight / total_weight,
        "lower_tie_households": len(lower_ties),
        "lower_tie_weight": sum((row["weight"] for row in lower_ties), Decimal(0)),
        "upper_tie_households": len(upper_ties),
        "upper_tie_weight": sum((row["weight"] for row in upper_ties), Decimal(0)),
        "cohort_hash": cohort_hash,
        "method": REFERENCE_POPULATION_METHOD,
        "algorithm": QUANTILE_ALGORITHM,
        "weight_field": weight_field,
    }


def effective_sample_size(selected: list[dict], region_id: str | None = None) -> Decimal:
    rows = selected if region_id in (None, "national") else [row for row in selected if row["region_id"] == region_id]
    if not rows:
        return Decimal(0)
    total = sum((row["weight"] for row in rows), Decimal(0))
    squared = sum((row["weight"] * row["weight"] for row in rows), Decimal(0))
    if squared == 0:
        return Decimal(0)
    return (total * total) / squared
