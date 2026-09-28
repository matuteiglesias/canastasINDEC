"""Explicit mapping from frozen ENGHo Phase-A shares to regional IPC divisions."""
from __future__ import annotations

from decimal import Decimal

from basket_release.core import BuildError
from .contracts import FOOD_SCOPE
from .trajectory_contracts import DIVISION_IDS, PRICE_SOURCE, SHARE_TOLERANCE


def decimal(row: dict[str, str], field: str) -> Decimal:
    try:
        value = Decimal(str(row[field]))
    except Exception as exc:
        raise BuildError(f"engel_phase_b_invalid_decimal:{field}") from exc
    if not value.is_finite():
        raise BuildError(f"engel_phase_b_nonfinite:{field}")
    return value


def regional_price_map(reference_row: dict[str, str]) -> dict:
    """Translate one frozen regional Artifact-A row into transparent price components."""
    total = decimal(reference_row, "total_expenditure")
    if total <= 0:
        raise BuildError("engel_phase_b_nonpositive_reference_total")
    food_share = decimal(reference_row, "food_share")
    alcohol_share = decimal(reference_row, "alcohol_expenditure") / total
    tobacco_share = decimal(reference_row, "tobacco_expenditure") / total
    restaurant_share = decimal(reference_row, "restaurant_expenditure") / total
    division_shares = {
        f"coicop{i:02d}": decimal(reference_row, f"division_{i:02d}_share")
        for i in range(1, 13)
    }
    if abs(sum(division_shares.values(), Decimal(0)) - Decimal(1)) > SHARE_TOLERANCE:
        raise BuildError("engel_phase_b_reference_division_shares_do_not_reconcile")
    if abs((division_shares["coicop01"] + alcohol_share) - food_share) > SHARE_TOLERANCE:
        raise BuildError("engel_phase_b_food_scope_not_reconstructible")
    if abs((alcohol_share + tobacco_share) - division_shares["coicop02"]) > SHARE_TOLERANCE:
        raise BuildError("engel_phase_b_coicop02_subdivision_does_not_reconcile")
    if restaurant_share > division_shares["coicop11"] + SHARE_TOLERANCE:
        raise BuildError("engel_phase_b_restaurant_share_exceeds_coicop11")
    if reference_row.get("food_scope") != FOOD_SCOPE:
        raise BuildError("engel_phase_b_reference_food_scope_mismatch")
    if reference_row.get("restaurants_in_food") != "false" or reference_row.get("tobacco_in_food") != "false":
        raise BuildError("engel_phase_b_reference_food_flags_mismatch")

    divisions = []
    for division in DIVISION_IDS:
        food_component_share = Decimal(0)
        if division == "coicop01":
            food_component_share = division_shares[division]
        elif division == "coicop02":
            food_component_share = alcohol_share
        divisions.append({
            "division_id": division,
            "analytical_component": division,
            "base_share": division_shares[division],
            "food_component_base_share": food_component_share,
            "price_source": PRICE_SOURCE,
            "price_series_id": division,
            "mapping_status": "direct_division_mapping",
        })

    diagnostics = [
        {
            "component_id": "alcoholic_beverages_021",
            "base_share": alcohol_share,
            "food": True,
            "price_series_id": "coicop02",
            "mapping_status": "shared_division_price",
            "warning": "coicop02_shared_price_for_alcohol_and_tobacco",
        },
        {
            "component_id": "tobacco_022",
            "base_share": tobacco_share,
            "food": False,
            "price_series_id": "coicop02",
            "mapping_status": "shared_division_price",
            "warning": "coicop02_shared_price_for_alcohol_and_tobacco",
        },
        {
            "component_id": "restaurants_111",
            "base_share": restaurant_share,
            "food": False,
            "price_series_id": "coicop11",
            "mapping_status": "shared_division_price",
            "warning": "coicop11_shared_price_for_restaurants_and_hotels",
        },
    ]
    return {
        "region_id": reference_row["region_id"],
        "division_components": divisions,
        "diagnostic_components": diagnostics,
        "food_base_share": food_share,
        "alcohol_share": alcohol_share,
        "tobacco_share": tobacco_share,
        "restaurant_share": restaurant_share,
    }
