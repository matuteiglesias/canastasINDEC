"""Level/trajectory decomposition against observed official CBA/CBT."""
from __future__ import annotations

from decimal import Decimal

from basket_release.core import BuildError
from .trajectory_contracts import ARITHMETIC_TOLERANCE, BASE_PERIOD, REGIONS, WARNINGS


def build_threshold_paths(price_rows: list[dict], official_basket: dict) -> list[dict]:
    by_key = {(r["period"], r["region_id"]): r for r in price_rows}
    base = {}
    for region in REGIONS:
        p = by_key[(BASE_PERIOD, region)]
        o = official_basket["rows"][(BASE_PERIOD, region)]
        ice_off = o["cbt_decimal"] / o["cba_decimal"]
        base[region] = {
            "ice_engho": p["ICE_engho17"],
            "ice_official": ice_off,
            "level_factor": p["ICE_engho17"] / ice_off,
        }

    rows = []
    for period in official_basket["periods"]:
        for region in REGIONS:
            p = by_key[(period, region)]
            o = official_basket["rows"][(period, region)]
            cba = o["cba_decimal"]
            cbt = o["cbt_decimal"]
            ice_off = cbt / cba
            b = base[region]
            trajectory = (p["ICE_engho17"] / b["ice_engho"]) / (ice_off / b["ice_official"])
            level = b["level_factor"]
            full = level * trajectory
            cbt_engho = cba * p["ICE_engho17"]
            cbt_level = cbt * level
            cbt_full = cbt * full

            scale = max(Decimal(1), abs(cbt_engho))
            identities = {
                "official_ice": abs(ice_off - (cbt / cba)),
                "full_factor": abs(full - (p["ICE_engho17"] / ice_off)),
                "level_trajectory": abs(full - level * trajectory),
                "full_threshold": abs(cbt_full - cbt_engho),
                "level_threshold": abs(cbt_level - cbt * level),
            }
            if any(v > ARITHMETIC_TOLERANCE * scale for v in identities.values()):
                raise BuildError(
                    f"engel_phase_b_arithmetic_identity_failure:{period}:{region}:{identities}"
                )
            if period == BASE_PERIOD and abs(trajectory - Decimal(1)) > ARITHMETIC_TOLERANCE:
                raise BuildError(f"engel_phase_b_base_trajectory_not_one:{region}")

            rows.append({
                "period": period,
                "region_id": region,
                "CBA_official": cba,
                "CBT_official": cbt,
                "ICE_official": ice_off,
                "ICE_engho17": p["ICE_engho17"],
                "CBT_engho17": cbt_engho,
                "level_factor": level,
                "trajectory_factor": trajectory,
                "full_factor": full,
                "CBT_level_only": cbt_level,
                "CBT_level_plus_trajectory": cbt_full,
                "food_base_share": p["food_base_share"],
                "food_price_relative": p["food_price_relative"],
                "total_expenditure_price_relative": p["total_expenditure_price_relative"],
                "food_share_engho17": p["food_share_engho17"],
                "official_line_path_id": "official",
                "level_only_line_path_id": "engho17_level_only",
                "full_line_path_id": "engho17_level_plus_trajectory",
                "value_status": "diagnostic_threshold_sensitivity",
                "warnings": "|".join(WARNINGS),
            })
    return rows
