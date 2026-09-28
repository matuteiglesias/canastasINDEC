"""Transparent COICOP mapping and frozen food-scope rules for ENGHo Phase A."""
from __future__ import annotations

import re

from basket_release.core import BuildError
from .contracts import (
    ALCOHOLIC_BEVERAGE_GROUP,
    ARTICLE_VARIABLE,
    DIVISION_IDS,
    DIVISION_VARIABLE,
    GROUP_VARIABLE,
    HOTEL_GROUP,
    RESTAURANT_GROUP,
    TOBACCO_GROUP,
)


def _digits(value: str) -> str:
    return "".join(re.findall(r"\d", str(value or "")))


def normalize_division(value: str) -> str:
    digits = _digits(value)
    if not digits:
        raise BuildError(f"invalid_article_division: {value!r}")
    number = int(digits)
    if number < 1 or number > 12:
        raise BuildError(f"invalid_article_division: {value!r}")
    return f"{number:02d}"


def normalize_group(value: str, division: str) -> str:
    digits = _digits(value)
    if not digits:
        raise BuildError(f"invalid_article_group: {value!r}")
    # Official files may render hierarchical codes with punctuation or without
    # left-padding. Normalize to the standard 3-digit COICOP group identity.
    if len(digits) >= 3:
        group = digits[:3]
    elif len(digits) == 2:
        if digits.startswith(str(int(division))):
            group = division + digits[-1]
        else:
            group = division + digits[-1]
    else:
        group = division + digits
    if len(group) != 3 or not group.startswith(division):
        raise BuildError(f"article_group_division_mismatch: division={division} group={value!r}")
    return group


def build_article_mapping(article_rows: list[dict[str, str]]) -> dict[str, dict]:
    mapping: dict[str, dict] = {}
    for row in article_rows:
        code = str(row.get(ARTICLE_VARIABLE, "")).strip()
        if not code:
            raise BuildError("missing_article_code")
        if code in mapping:
            raise BuildError(f"duplicate_article_code: {code}")
        division = normalize_division(row.get(DIVISION_VARIABLE, ""))
        group = normalize_group(row.get(GROUP_VARIABLE, ""), division)
        division_id = f"coicop{division}"
        if division_id not in DIVISION_IDS:
            raise BuildError(f"unsupported_article_division: {division_id}")
        is_alcohol = group == ALCOHOLIC_BEVERAGE_GROUP
        is_tobacco = group == TOBACCO_GROUP
        is_restaurant = group == RESTAURANT_GROUP
        is_hotel = group == HOTEL_GROUP
        # Frozen primary rule: ordinary food/non-alcoholic beverages plus
        # alcoholic beverages are food; tobacco and restaurants are not.
        is_food = division == "01" or is_alcohol
        if is_tobacco or is_restaurant:
            is_food = False
        mapping[code] = {
            "article_code": code,
            "division_code": division,
            "division_id": division_id,
            "group_code": group,
            "food": is_food,
            "alcoholic_beverage": is_alcohol,
            "tobacco": is_tobacco,
            "restaurant": is_restaurant,
            "hotel": is_hotel,
            "article_desc": str(row.get("articulo_desc", "") or ""),
            "division_desc": str(row.get("division_desc", "") or ""),
            "group_desc": str(row.get("grupo_desc", "") or ""),
        }
    if not mapping:
        raise BuildError("empty_article_mapping")
    return mapping


def _classification_from_hierarchy(code: str, raw_division: str, raw_group: str) -> dict:
    division = normalize_division(raw_division)
    group = normalize_group(raw_group, division)
    division_id = f"coicop{division}"
    is_alcohol = group == ALCOHOLIC_BEVERAGE_GROUP
    is_tobacco = group == TOBACCO_GROUP
    is_restaurant = group == RESTAURANT_GROUP
    is_hotel = group == HOTEL_GROUP
    is_food = division == "01" or is_alcohol
    if is_tobacco or is_restaurant:
        is_food = False
    return {
        "article_code": code,
        "division_code": division,
        "division_id": division_id,
        "group_code": group,
        "food": is_food,
        "alcoholic_beverage": is_alcohol,
        "tobacco": is_tobacco,
        "restaurant": is_restaurant,
        "hotel": is_hotel,
        "article_desc": "",
        "division_desc": "",
        "group_desc": "",
        "article_mapping_fallback": True,
    }


def classify_expenditure_row(row: dict[str, str], mapping: dict[str, dict]) -> dict:
    code = str(row.get(ARTICLE_VARIABLE, "")).strip()
    if code not in mapping:
        raw_division = str(row.get(DIVISION_VARIABLE, "") or "").strip()
        raw_group = str(row.get(GROUP_VARIABLE, "") or "").strip()
        if raw_division and raw_group:
            return _classification_from_hierarchy(code, raw_division, raw_group)
        raise BuildError(f"unknown_article_code: {code!r}")
    article = mapping[code]
    # Expenditure rows themselves carry hierarchy fields in the official file.
    # When present, use them as a cross-source integrity check, never as a silent
    # override of the official article classification table.
    raw_division = str(row.get(DIVISION_VARIABLE, "") or "").strip()
    if raw_division:
        if normalize_division(raw_division) != article["division_code"]:
            raise BuildError(f"expenditure_article_division_mismatch: {code}")
    raw_group = str(row.get(GROUP_VARIABLE, "") or "").strip()
    if raw_group:
        if normalize_group(raw_group, article["division_code"]) != article["group_code"]:
            raise BuildError(f"expenditure_article_group_mismatch: {code}")
    return article
