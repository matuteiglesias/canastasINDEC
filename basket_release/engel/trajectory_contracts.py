"""Frozen Phase-B contracts for ENGHo level/trajectory sensitivity."""
from __future__ import annotations

from decimal import Decimal

from .contracts import (
    ARTIFACT_TYPE as REFERENCE_ARTIFACT_TYPE,
    METHOD_ID as REFERENCE_METHOD_ID,
    BASE_PERIOD as REFERENCE_BASE_PERIOD,
    DIVISION_IDS,
)

ARTIFACT_TYPE = "research.argentina-regional-baskets-engel-sensitivity/v1"
METHOD_ID = "research.argentina-regional-baskets-engel-sensitivity/engho17-fixed-base-regional-ipc-v1"
STATUS = "candidate"
VALUE_STATUS = "diagnostic_threshold_sensitivity"

IPC_ARTIFACT_TYPE = "publicdata.indec-ipc-regional-divisions/v1"
IPC_INDEX_BASE = "2016-12=100"
IPC_VALUE_STATUS = "direct_official_observation"

OFFICIAL_BASKET_ARTIFACT_TYPE = "research.argentina-regional-baskets/v1"
OFFICIAL_BASKET_METHOD_ID = "research.argentina-regional-baskets/source-observed-plus-price-consensus-v2"

BASE_PERIOD = "2018-05-01"
WINDOW_START = "2018-05-01"
WINDOW_END = "2025-12-01"
REFERENCE_BASE_PERIOD_EXPECTED = "2018-05"

REGIONS = (
    "gran_buenos_aires",
    "pampeana",
    "noreste",
    "noroeste",
    "cuyo",
    "patagonia",
)

ARITHMETIC_TOLERANCE = Decimal("1e-18")
SHARE_TOLERANCE = Decimal("1e-16")

PRICE_SOURCE = "publicdata.indec-ipc-regional-divisions/v1"
PRICE_MAPPING_STATUS = "direct_division_mapping"
FOOD_PRICE_MAPPING_STATUS = "direct_division_plus_shared_subdivision_price"

WARNINGS = (
    "engho_food_block_not_identical_to_official_cba",
    "coicop02_shared_price_for_alcohol_and_tobacco",
    "coicop11_shared_price_for_restaurants_and_hotels",
    "fixed_base_engho_expenditure_structure_is_experimental_sensitivity",
    "artifact_b_does_not_authorize_poverty_estimation",
)

LINE_PATH_IDS = (
    "official",
    "engho17_level_only",
    "engho17_level_plus_trajectory",
)

assert REFERENCE_BASE_PERIOD == REFERENCE_BASE_PERIOD_EXPECTED
assert DIVISION_IDS == tuple(f"coicop{i:02d}" for i in range(1, 13))
