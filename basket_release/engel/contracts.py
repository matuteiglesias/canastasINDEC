"""Frozen scientific and artifact contracts for ENGHo/Engel Phase A."""
from __future__ import annotations

ARTIFACT_TYPE = "research.argentina-engel-reference-structure/v1"
METHOD_ID = "research.argentina-engel-reference-structure/engho-2017-18-p29-p48-signed-sales-v2"
PARENT_ARTIFACT_TYPE = "publicdata.indec-engho-microdata/v1"
SURVEY_VINTAGE = "2017-2018"
BASE_PERIOD = "2018-05"
STATUS = "candidate"
VALUE_STATUS = "diagnostic_reference_structure"

RANKING_VARIABLE = "ingpch"
WEIGHT_VARIABLE = "pondera"
REGION_VARIABLE = "region"
HOUSEHOLD_ID_VARIABLE = "id"
EXPENDITURE_AMOUNT_VARIABLE = "monto"
ARTICLE_VARIABLE = "articulo"
DIVISION_VARIABLE = "division"
GROUP_VARIABLE = "grupo"
IMPUTATION_VARIABLE = "r_imputado"
NEGATIVE_EXPENDITURE_POLICY = "preserve_signed_sales"

PERCENTILE_LOW = "0.29"
PERCENTILE_HIGH = "0.48"
QUANTILE_ALGORITHM = "weighted-ecdf-cutpoints-lower-inclusive-upper-exclusive/v1"
REFERENCE_POPULATION_METHOD = (
    "national weighted household per-capita income p29-p48; "
    "weighted empirical cutpoints; lower inclusive, upper exclusive; "
    "ties kept whole by income value"
)

REGIONS = (
    "national",
    "gran_buenos_aires",
    "pampeana",
    "noreste",
    "noroeste",
    "cuyo",
    "patagonia",
)
REGION_CODE_MAP = {
    "1": "gran_buenos_aires",
    "2": "pampeana",
    "3": "noroeste",
    "4": "noreste",
    "5": "cuyo",
    "6": "patagonia",
}
DIVISION_IDS = tuple(f"coicop{i:02d}" for i in range(1, 13))

FOOD_SCOPE = "coicop01_plus_coicop021_alcoholic_beverages"
RESTAURANTS_IN_FOOD = False
TOBACCO_IN_FOOD = False
RESTAURANT_GROUP = "111"
HOTEL_GROUP = "112"
ALCOHOLIC_BEVERAGE_GROUP = "021"
TOBACCO_GROUP = "022"

BOOTSTRAP_VARIANCE_METHOD = "indec-engho-nt4-mse-bootstrap-v1"
BOOTSTRAP_VARIANCE_FORMULA = "variance=(1/B)*sum((theta_rep-theta_point)^2)"
EXPECTED_REPLICATES_REAL = 200
INTERVAL_Z = "1.96"

HOUSEHOLD_REQUIRED = {
    HOUSEHOLD_ID_VARIABLE,
    RANKING_VARIABLE,
    WEIGHT_VARIABLE,
    REGION_VARIABLE,
}
EXPENDITURE_REQUIRED = {
    HOUSEHOLD_ID_VARIABLE,
    ARTICLE_VARIABLE,
    EXPENDITURE_AMOUNT_VARIABLE,
}
ARTICLE_REQUIRED = {
    ARTICLE_VARIABLE,
    DIVISION_VARIABLE,
    GROUP_VARIABLE,
}
REPLICATE_ID_REQUIRED = {HOUSEHOLD_ID_VARIABLE}

UPSTREAM_PERSON_COUNT_WARNING = (
    "M1 real-data commissioning observed 68,725 person rows versus 68,675 in the "
    "2020 INDEC user-manual table; Phase A does not consume the persons table."
)
