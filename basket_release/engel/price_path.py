"""Fixed-base ENGHo expenditure-price paths from official regional IPC divisions."""
from __future__ import annotations

from decimal import Decimal

from basket_release.core import BuildError
from .price_mapping import regional_price_map
from .trajectory_contracts import ARITHMETIC_TOLERANCE, BASE_PERIOD, DIVISION_IDS, REGIONS


def build_price_paths(reference: dict, ipc: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """Return monthly path rows, division contributions, and mapping diagnostics."""
    path_rows = []
    contributions = []
    mapping_rows = []
    for region in REGIONS:
        refrow = reference["rows"][region]
        mapping = regional_price_map(refrow)
        base_indices = {
            division: ipc["rows"][(BASE_PERIOD, region, division)]["index_decimal"]
            for division in DIVISION_IDS
        }
        for component in mapping["division_components"]:
            mapping_rows.append({
                "region_id": region,
                "component_id": component["analytical_component"],
                "component_kind": "division_total",
                "base_share": component["base_share"],
                "food_component_base_share": component["food_component_base_share"],
                "price_source": component["price_source"],
                "price_series_id": component["price_series_id"],
                "mapping_status": component["mapping_status"],
                "warning": "",
            })
        for component in mapping["diagnostic_components"]:
            mapping_rows.append({
                "region_id": region,
                "component_id": component["component_id"],
                "component_kind": "diagnostic_subcomponent",
                "base_share": component["base_share"],
                "food_component_base_share": component["base_share"] if component["food"] else Decimal(0),
                "price_source": "publicdata.indec-ipc-regional-divisions/v1",
                "price_series_id": component["price_series_id"],
                "mapping_status": component["mapping_status"],
                "warning": component["warning"],
            })

        for period in ipc["periods"]:
            total_cost = Decimal(0)
            food_cost = Decimal(0)
            rels = {}
            for component in mapping["division_components"]:
                division = component["division_id"]
                value = ipc["rows"][(period, region, division)]["index_decimal"]
                relative = value / base_indices[division]
                rels[division] = relative
                weighted = component["base_share"] * relative
                food_weighted = component["food_component_base_share"] * relative
                total_cost += weighted
                food_cost += food_weighted
                contributions.append({
                    "period": period,
                    "region_id": region,
                    "division_id": division,
                    "base_share": component["base_share"],
                    "food_component_base_share": component["food_component_base_share"],
                    "price_relative": relative,
                    "weighted_cost_contribution": weighted,
                    "food_weighted_cost_contribution": food_weighted,
                    "contribution_to_total_price_relative": weighted,
                    "price_series_id": division,
                    "price_source_release_id": ipc["release_id"],
                    "value_status": "diagnostic_price_contribution",
                })
            if total_cost <= 0 or food_cost <= 0:
                raise BuildError(f"engel_phase_b_nonpositive_cost_path:{period}:{region}")
            food_base = mapping["food_base_share"]
            food_price_relative = food_cost / food_base
            food_share = food_cost / total_cost
            ice = total_cost / food_cost
            if period == BASE_PERIOD:
                if abs(total_cost - Decimal(1)) > ARITHMETIC_TOLERANCE:
                    raise BuildError(f"engel_phase_b_total_base_not_one:{region}")
                if abs(food_price_relative - Decimal(1)) > ARITHMETIC_TOLERANCE:
                    raise BuildError(f"engel_phase_b_food_base_not_one:{region}")
                if abs(food_share - food_base) > ARITHMETIC_TOLERANCE:
                    raise BuildError(f"engel_phase_b_food_base_share_mismatch:{region}")
                ref_ice = Decimal(refrow["ice_base"])
                if abs(ice - ref_ice) > ARITHMETIC_TOLERANCE:
                    raise BuildError(f"engel_phase_b_base_ice_mismatch:{region}")
            path_rows.append({
                "period": period,
                "region_id": region,
                "food_base_share": food_base,
                "food_cost_relative_to_base_total": food_cost,
                "total_expenditure_price_relative": total_cost,
                "food_price_relative": food_price_relative,
                "food_share_engho17": food_share,
                "ICE_engho17": ice,
                "coicop01_price_relative": rels["coicop01"],
                "coicop02_price_relative": rels["coicop02"],
            })
    return path_rows, contributions, mapping_rows
