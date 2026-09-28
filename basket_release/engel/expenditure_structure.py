"""Household expenditure profiling and reference-structure aggregation."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation

from basket_release.core import BuildError
from .article_classification import classify_expenditure_row
from .contracts import DIVISION_IDS, IMPUTATION_VARIABLE
from .reference_population import effective_sample_size


def _parsed_amount(value: str) -> Decimal:
    try:
        amount = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError) as exc:
        raise BuildError(f"invalid_expenditure_amount: {value!r}") from exc
    if not amount.is_finite():
        raise BuildError("invalid_expenditure_amount: nonfinite")
    return amount


def _amount(value: str) -> Decimal:
    """Return analysis amount; documented ENGHo sales are clipped to zero."""
    amount = _parsed_amount(value)
    return max(amount, Decimal(0))


def build_household_expenditure_profiles(
    expenditure_rows: list[dict[str, str]],
    article_mapping: dict[str, dict],
    known_households: set[str],
) -> tuple[dict[str, dict], dict]:
    """Classify every expenditure row exactly once and collapse to household profiles."""
    profiles: dict[str, dict] = {}
    mapped_rows = 0
    zero_amount_rows = 0
    negative_amount_rows = 0
    negative_amount_total = Decimal(0)
    article_mapping_fallback_rows = 0
    imputed_amount = Decimal(0)
    observed_amount = Decimal(0)
    restaurant_amount = Decimal(0)
    tobacco_amount = Decimal(0)
    alcohol_amount = Decimal(0)

    for row in expenditure_rows:
        household_id = str(row.get("id", "")).strip()
        if household_id not in known_households:
            raise BuildError(f"expenditure_unknown_household: {household_id!r}")
        classification = classify_expenditure_row(row, article_mapping)
        if classification.get("article_mapping_fallback"):
            article_mapping_fallback_rows += 1
        parsed_amount = _parsed_amount(row.get("monto", ""))
        amount = max(parsed_amount, Decimal(0))
        mapped_rows += 1
        if amount == 0:
            zero_amount_rows += 1
        if amount < 0:
            negative_amount_rows += 1
        if parsed_amount < 0:
            negative_amount_rows += 1
            negative_amount_total += parsed_amount
        profile = profiles.setdefault(
            household_id,
            {
                "total": Decimal(0),
                "food": Decimal(0),
                "nonfood": Decimal(0),
                "restaurant": Decimal(0),
                "tobacco": Decimal(0),
                "alcohol": Decimal(0),
                "imputed": Decimal(0),
                "divisions": {division: Decimal(0) for division in DIVISION_IDS},
                "rows": 0,
            },
        )
        profile["rows"] += 1
        profile["total"] += amount
        profile["divisions"][classification["division_id"]] += amount
        if classification["food"]:
            profile["food"] += amount
        else:
            profile["nonfood"] += amount
        if classification["restaurant"]:
            profile["restaurant"] += amount
            restaurant_amount += amount
        if classification["tobacco"]:
            profile["tobacco"] += amount
            tobacco_amount += amount
        if classification["alcoholic_beverage"]:
            profile["alcohol"] += amount
            alcohol_amount += amount
        if str(row.get(IMPUTATION_VARIABLE, "")).strip() == "1":
            profile["imputed"] += amount
            imputed_amount += amount
        else:
            observed_amount += amount

    # Households with no expenditure rows remain explicit zero profiles so regional
    # household counts and reference-population support are not conditioned on spending.
    for household_id in known_households:
        profiles.setdefault(
            household_id,
            {
                "total": Decimal(0),
                "food": Decimal(0),
                "nonfood": Decimal(0),
                "restaurant": Decimal(0),
                "tobacco": Decimal(0),
                "alcohol": Decimal(0),
                "imputed": Decimal(0),
                "divisions": {division: Decimal(0) for division in DIVISION_IDS},
                "rows": 0,
            },
        )

    # Mechanical accounting identities are hard gates.
    for household_id, profile in profiles.items():
        if profile["food"] + profile["nonfood"] != profile["total"]:
            raise BuildError(f"food_nonfood_reconciliation_failure: {household_id}")
        if sum(profile["divisions"].values(), Decimal(0)) != profile["total"]:
            raise BuildError(f"division_reconciliation_failure: {household_id}")

    raw_total = observed_amount + imputed_amount
    diagnostics = {
        "input_expenditure_rows": len(expenditure_rows),
        "mapped_expenditure_rows": mapped_rows,
        "mapping_coverage": Decimal(mapped_rows) / Decimal(len(expenditure_rows)) if expenditure_rows else Decimal(1),
        "zero_amount_rows": zero_amount_rows,
        "raw_total_expenditure": raw_total,
        "raw_imputed_expenditure": imputed_amount,
        "raw_imputed_expenditure_share": (imputed_amount / raw_total) if raw_total else Decimal(0),
        "raw_restaurant_expenditure": restaurant_amount,
        "raw_tobacco_expenditure": tobacco_amount,
        "raw_alcohol_expenditure": alcohol_amount,
        "unknown_article_rows": 0,
        "article_mapping_fallback_rows": article_mapping_fallback_rows,
        "negative_expenditure_rows": negative_amount_rows,
        "negative_expenditure_raw_total": negative_amount_total,
        "negative_expenditure_policy": "clip_at_zero_with_warning",
    }
    return profiles, diagnostics


def aggregate_structure(selected: list[dict], profiles: dict[str, dict]) -> dict[str, dict]:
    """Aggregate point or replicate-weight structures for national + six regions."""
    if not selected:
        raise BuildError("cannot_aggregate_empty_reference_population")
    selected_by_id = {row["id"]: row for row in selected}
    national_weight = sum((row["weight"] for row in selected), Decimal(0))
    if national_weight <= 0:
        raise BuildError("reference_population_nonpositive_weight")

    groups = {"national": list(selected)}
    for region in ("gran_buenos_aires", "pampeana", "noreste", "noroeste", "cuyo", "patagonia"):
        groups[region] = [row for row in selected if row["region_id"] == region]

    result: dict[str, dict] = {}
    for region_id, households in groups.items():
        if not households:
            raise BuildError(f"reference_population_empty_region: {region_id}")
        weighted_households = sum((row["weight"] for row in households), Decimal(0))
        food = Decimal(0)
        total = Decimal(0)
        restaurant = Decimal(0)
        tobacco = Decimal(0)
        alcohol = Decimal(0)
        imputed = Decimal(0)
        divisions = {division: Decimal(0) for division in DIVISION_IDS}
        for household in households:
            profile = profiles[household["id"]]
            weight = household["weight"]
            total += weight * profile["total"]
            food += weight * profile["food"]
            restaurant += weight * profile["restaurant"]
            tobacco += weight * profile["tobacco"]
            alcohol += weight * profile["alcohol"]
            imputed += weight * profile["imputed"]
            for division in DIVISION_IDS:
                divisions[division] += weight * profile["divisions"][division]
        if total <= 0:
            raise BuildError(f"reference_population_nonpositive_expenditure: {region_id}")
        food_share = food / total
        if food_share <= 0 or food_share >= 1:
            raise BuildError(f"reference_population_invalid_food_share: {region_id}")
        division_shares = {division: value / total for division, value in divisions.items()}
        share_sum = sum(division_shares.values(), Decimal(0))
        if abs(share_sum - Decimal(1)) > Decimal("1e-24"):
            raise BuildError(f"division_share_reconciliation_failure: {region_id}")
        result[region_id] = {
            "unweighted_households": len(households),
            "weighted_households": weighted_households,
            "weighted_population_share": weighted_households / national_weight,
            "effective_sample_size": effective_sample_size(households),
            "food_expenditure": food,
            "total_expenditure": total,
            "food_share": food_share,
            "ice_base": Decimal(1) / food_share,
            "restaurant_expenditure": restaurant,
            "tobacco_expenditure": tobacco,
            "alcohol_expenditure": alcohol,
            "imputed_expenditure_share": imputed / total,
            "division_shares": division_shares,
        }
    return result


def selected_accounting(
    selected_ids: set[str],
    expenditure_rows: list[dict[str, str]],
    article_mapping: dict[str, dict],
) -> dict:
    """Compact G2 diagnostics restricted to the selected reference cohort."""
    total_rows = 0
    mapped_rows = 0
    raw_total = Decimal(0)
    food = Decimal(0)
    nonfood = Decimal(0)
    divisions = defaultdict(Decimal)
    restaurants = Decimal(0)
    tobacco = Decimal(0)
    for row in expenditure_rows:
        if str(row.get("id", "")).strip() not in selected_ids:
            continue
        total_rows += 1
        classification = classify_expenditure_row(row, article_mapping)
        mapped_rows += 1
        amount = _amount(row.get("monto", ""))
        raw_total += amount
        divisions[classification["division_id"]] += amount
        if classification["food"]:
            food += amount
        else:
            nonfood += amount
        if classification["restaurant"]:
            restaurants += amount
        if classification["tobacco"]:
            tobacco += amount
    return {
        "selected_expenditure_rows": total_rows,
        "mapped_selected_expenditure_rows": mapped_rows,
        "mapping_coverage": Decimal(mapped_rows) / Decimal(total_rows) if total_rows else Decimal(1),
        "raw_total": raw_total,
        "food_plus_nonfood": food + nonfood,
        "food_nonfood_residual": raw_total - food - nonfood,
        "division_total": sum(divisions.values(), Decimal(0)),
        "division_residual": raw_total - sum(divisions.values(), Decimal(0)),
        "restaurant_expenditure": restaurants,
        "tobacco_expenditure": tobacco,
    }
