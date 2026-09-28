"""Build and validate Artifact B: ENGHo regional Engel sensitivity paths."""
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
from .artifact import canonical_json, _write_csv
from .phase_b_parents import (
    load_ipc_parent,
    load_official_basket_parent,
    load_reference_parent,
    month_sequence,
    sha256,
)
from .price_path import build_price_paths
from .threshold_paths import build_threshold_paths
from .trajectory_contracts import (
    ARITHMETIC_TOLERANCE,
    ARTIFACT_TYPE,
    BASE_PERIOD,
    DIVISION_IDS,
    LINE_PATH_IDS,
    METHOD_ID,
    REGIONS,
    STATUS,
    VALUE_STATUS,
    WARNINGS,
    WINDOW_END,
    WINDOW_START,
)


THRESHOLD_FIELDS = [
    "period", "region_id",
    "CBA_official", "CBT_official", "ICE_official",
    "ICE_engho17", "CBT_engho17",
    "level_factor", "trajectory_factor", "full_factor",
    "CBT_level_only", "CBT_level_plus_trajectory",
    "food_base_share", "food_price_relative", "total_expenditure_price_relative",
    "food_share_engho17",
    "official_line_path_id", "level_only_line_path_id", "full_line_path_id",
    "engho_reference_release_id", "ipc_regional_divisions_release_id",
    "official_basket_release_id", "method_id", "base_period",
    "value_status", "warnings",
]

CONTRIBUTION_FIELDS = [
    "period", "region_id", "division_id", "base_share",
    "food_component_base_share", "price_relative",
    "weighted_cost_contribution", "food_weighted_cost_contribution",
    "contribution_to_total_price_relative", "price_series_id",
    "price_source_release_id", "value_status",
]

MAPPING_FIELDS = [
    "region_id", "component_id", "component_kind", "base_share",
    "food_component_base_share", "price_source", "price_series_id",
    "mapping_status", "warning",
]

LINE_FIELDS = [
    "period", "region_id", "line_path_id", "threshold_value",
    "source_line", "status", "method_id",
]


def _safe(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or relative in {"", "."}:
        raise BuildError(f"engel_phase_b_unsafe_artifact_path:{relative}")
    path = (root / relative).resolve()
    if root.resolve() not in path.parents:
        raise BuildError(f"engel_phase_b_unsafe_artifact_path:{relative}")
    return path


def _close(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= ARITHMETIC_TOLERANCE * max(Decimal(1), abs(a), abs(b))


def build_sensitivity_artifact(
    reference_root: Path,
    ipc_root: Path,
    official_basket_root: Path,
    output_parent: Path,
) -> Path:
    reference = load_reference_parent(reference_root)
    ipc = load_ipc_parent(ipc_root)
    basket = load_official_basket_parent(official_basket_root)

    if ipc["periods"] != basket["periods"]:
        raise BuildError("engel_phase_b_parent_period_inventory_mismatch")

    price_rows, contributions, mapping_rows = build_price_paths(reference, ipc)
    thresholds = build_threshold_paths(price_rows, basket)

    for row in thresholds:
        row.update({
            "engho_reference_release_id": reference["release_id"],
            "ipc_regional_divisions_release_id": ipc["release_id"],
            "official_basket_release_id": basket["release_id"],
            "method_id": METHOD_ID,
            "base_period": BASE_PERIOD,
            "value_status": VALUE_STATUS,
        })

    line_rows = []
    for row in thresholds:
        for path_id, field, source_line in (
            ("official", "CBT_official", "observed_official_cbt"),
            ("engho17_level_only", "CBT_level_only", "official_cbt_times_level_factor"),
            ("engho17_level_plus_trajectory", "CBT_level_plus_trajectory", "official_cbt_times_full_factor"),
        ):
            line_rows.append({
                "period": row["period"],
                "region_id": row["region_id"],
                "line_path_id": path_id,
                "threshold_value": row[field],
                "source_line": source_line,
                "status": "diagnostic",
                "method_id": METHOD_ID,
            })

    identity_seed = {
        "artifact_type": ARTIFACT_TYPE,
        "method_id": METHOD_ID,
        "base_period": BASE_PERIOD,
        "reference_manifest_sha256": reference["manifest_sha256"],
        "ipc_manifest_sha256": ipc["manifest_sha256"],
        "official_basket_manifest_sha256": basket["manifest_sha256"],
    }
    release_id = "engel-sensitivity-" + hashlib.sha256(canonical_json(identity_seed)).hexdigest()[:16]

    output_parent = Path(output_parent).expanduser().resolve()
    output_parent.mkdir(parents=True, exist_ok=True)
    final = output_parent / release_id
    if final.exists():
        validate_sensitivity_artifact(final)
        return final

    staging = Path(tempfile.mkdtemp(prefix=f".{release_id}.", dir=output_parent))
    try:
        _write_csv(staging / "threshold_paths.csv", THRESHOLD_FIELDS, thresholds)
        _write_csv(staging / "division_contributions.csv", CONTRIBUTION_FIELDS, contributions)
        _write_csv(staging / "price_mapping.csv", MAPPING_FIELDS, mapping_rows)
        _write_csv(staging / "line_paths.csv", LINE_FIELDS, line_rows)

        parent_locks = {
            "engho_reference": {
                "artifact_type": reference["manifest"]["artifact_type"],
                "method_id": reference["manifest"]["method_id"],
                "release_id": reference["release_id"],
                "manifest_sha256": reference["manifest_sha256"],
                "warnings": reference["warnings"],
            },
            "ipc_regional_divisions": {
                "artifact_type": ipc["manifest"]["artifact_type"],
                "release_id": ipc["release_id"],
                "manifest_sha256": ipc["manifest_sha256"],
                "source_snapshot_sha256": ipc["manifest"].get("source_snapshot_sha256"),
            },
            "official_baskets": {
                "artifact_type": basket["manifest"]["artifact_type"],
                "method_id": basket["manifest"]["method_id"],
                "release_id": basket["release_id"],
                "manifest_sha256": basket["manifest_sha256"],
                "warnings": basket["warnings"],
            },
        }
        (staging / "parent_locks.json").write_bytes(canonical_json(parent_locks))

        inherited = sorted(set(reference["warnings"] + basket["warnings"]))
        all_warnings = sorted(set(WARNINGS + tuple(inherited)))
        qa = {
            "result": "pass_with_warnings",
            "gate_P_cross_parent_integrity": "pass",
            "gate_A_arithmetic_identities": "pass",
            "gate_M_price_mapping": "pass_with_documented_approximations",
            "required_window": {"start": WINDOW_START, "end": WINDOW_END, "months": len(month_sequence())},
            "regions": list(REGIONS),
            "divisions": list(DIVISION_IDS),
            "line_path_ids": list(LINE_PATH_IDS),
            "interpolation_performed": False,
            "network_retrieval_performed": False,
            "reference_population_recomputed": False,
            "articles_reclassified": False,
            "cba_modified": False,
            "adult_equivalence_calculated": False,
            "scientific_poverty_execution_performed": False,
            "warnings": all_warnings,
            "hard_failures": [],
        }
        (staging / "qa.json").write_bytes(canonical_json(qa))
        limitations = """# Limitations

This is a candidate/diagnostic Engel sensitivity artifact, not an official INDEC poverty basket and not a poverty result.

The Phase-A ENGHo expenditure structure is held fixed at the May-2018 base. Regional COICOP division indices provide price relatives only. COICOP02 prices both alcoholic beverages (food under the frozen research convention) and tobacco (non-food); COICOP11 prices restaurant and hotel expenditure. These shared-division price approximations are explicit in price_mapping.csv.

The official regional CBA is held unchanged. The ENGHo food expenditure block is not assumed to be the nutritional CBA. Artifact B changes only the inverse-Engel structure used to form experimental CBT paths.

No interpolation, EPH calculation, poverty classification, Census inference or Atlas operation occurs here.
"""
        (staging / "limitations.md").write_text(limitations, encoding="utf-8")

        payloads = [
            "threshold_paths.csv", "division_contributions.csv", "price_mapping.csv",
            "line_paths.csv", "parent_locks.json", "qa.json", "limitations.md",
        ]
        files = {
            name: {"bytes": (staging / name).stat().st_size, "sha256": sha256(staging / name)}
            for name in payloads
        }
        manifest = {
            "schema": "research-artifact-manifest/v1",
            "artifact_type": ARTIFACT_TYPE,
            "release_id": release_id,
            "status": STATUS,
            "method_id": METHOD_ID,
            "base_period": BASE_PERIOD,
            "window": {"start": WINDOW_START, "end": WINDOW_END},
            "regions": list(REGIONS),
            "division_ids": list(DIVISION_IDS),
            "line_path_ids": list(LINE_PATH_IDS),
            "engho_reference_release_id": reference["release_id"],
            "ipc_regional_divisions_release_id": ipc["release_id"],
            "official_basket_release_id": basket["release_id"],
            "parent_manifest_sha256": {
                "engho_reference": reference["manifest_sha256"],
                "ipc_regional_divisions": ipc["manifest_sha256"],
                "official_baskets": basket["manifest_sha256"],
            },
            "warnings": all_warnings,
            "reference_population_recomputed": False,
            "articles_reclassified": False,
            "cba_modified": False,
            "adult_equivalence_calculated": False,
            "scientific_poverty_execution_performed": False,
            "files": files,
        }
        (staging / "manifest.json").write_bytes(canonical_json(manifest))
        os.replace(staging, final)
        validate_sensitivity_artifact(final)
        return final
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def validate_sensitivity_artifact(root: Path) -> dict:
    root = Path(root).expanduser().resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise BuildError("engel_phase_b_manifest_missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("artifact_type") != ARTIFACT_TYPE or manifest.get("method_id") != METHOD_ID:
        raise BuildError("engel_phase_b_artifact_identity_mismatch")
    if manifest.get("status") != STATUS or manifest.get("base_period") != BASE_PERIOD:
        raise BuildError("engel_phase_b_artifact_status_or_base_mismatch")
    for key in (
        "reference_population_recomputed",
        "articles_reclassified",
        "cba_modified",
        "adult_equivalence_calculated",
        "scientific_poverty_execution_performed",
    ):
        if manifest.get(key) is not False:
            raise BuildError(f"engel_phase_b_scope_violation:{key}")
    for name, identity in manifest.get("files", {}).items():
        path = _safe(root, name)
        if not path.is_file() or path.stat().st_size != identity.get("bytes") or sha256(path) != identity.get("sha256"):
            raise BuildError(f"engel_phase_b_artifact_file_mismatch:{name}")

    with (root / "threshold_paths.csv").open(newline="", encoding="utf-8") as h:
        paths = list(csv.DictReader(h))
    expected_keys = {(p, r) for p in month_sequence() for r in REGIONS}
    keys = {(r["period"], r["region_id"]) for r in paths}
    if keys != expected_keys or len(paths) != len(expected_keys):
        raise BuildError("engel_phase_b_threshold_inventory_mismatch")

    by_key = {(r["period"], r["region_id"]): r for r in paths}
    for row in paths:
        cba = Decimal(row["CBA_official"])
        cbt = Decimal(row["CBT_official"])
        ice_off = Decimal(row["ICE_official"])
        ice_new = Decimal(row["ICE_engho17"])
        level = Decimal(row["level_factor"])
        trajectory = Decimal(row["trajectory_factor"])
        full = Decimal(row["full_factor"])
        cbt_new = Decimal(row["CBT_engho17"])
        cbt_level = Decimal(row["CBT_level_only"])
        cbt_full = Decimal(row["CBT_level_plus_trajectory"])
        if not _close(ice_off, cbt / cba):
            raise BuildError("engel_phase_b_validate_official_ice")
        if not _close(full, level * trajectory) or not _close(full, ice_new / ice_off):
            raise BuildError("engel_phase_b_validate_factorization")
        if not _close(cbt_level, cbt * level):
            raise BuildError("engel_phase_b_validate_level_line")
        if not _close(cbt_full, cbt * full) or not _close(cbt_full, cbt_new):
            raise BuildError("engel_phase_b_validate_full_line")
        if not _close(cbt_new, cba * ice_new):
            raise BuildError("engel_phase_b_validate_engho_line")
        if row["period"] == BASE_PERIOD and not _close(trajectory, Decimal(1)):
            raise BuildError("engel_phase_b_validate_base_trajectory")

    with (root / "division_contributions.csv").open(newline="", encoding="utf-8") as h:
        contributions = list(csv.DictReader(h))
    groups = defaultdict(list)
    for row in contributions:
        groups[(row["period"], row["region_id"])].append(row)
    if set(groups) != expected_keys:
        raise BuildError("engel_phase_b_contribution_inventory_mismatch")
    for key, rows in groups.items():
        if len(rows) != 12 or {r["division_id"] for r in rows} != set(DIVISION_IDS):
            raise BuildError(f"engel_phase_b_contribution_division_inventory:{key}")
        total = sum((Decimal(r["weighted_cost_contribution"]) for r in rows), Decimal(0))
        food = sum((Decimal(r["food_weighted_cost_contribution"]) for r in rows), Decimal(0))
        threshold = by_key[key]
        declared_total = Decimal(threshold["total_expenditure_price_relative"])
        declared_food = Decimal(threshold["food_base_share"]) * Decimal(threshold["food_price_relative"])
        if not _close(total, declared_total) or not _close(food, declared_food):
            raise BuildError(f"engel_phase_b_contribution_reconciliation:{key}")
        if not _close(Decimal(threshold["ICE_engho17"]), total / food):
            raise BuildError(f"engel_phase_b_contribution_ice_reconciliation:{key}")

    with (root / "line_paths.csv").open(newline="", encoding="utf-8") as h:
        line_rows = list(csv.DictReader(h))
    line_keys = {(r["period"], r["region_id"], r["line_path_id"]) for r in line_rows}
    expected_line_keys = {(p, r, line) for p in month_sequence() for r in REGIONS for line in LINE_PATH_IDS}
    if line_keys != expected_line_keys or len(line_rows) != len(expected_line_keys):
        raise BuildError("engel_phase_b_line_path_inventory_mismatch")

    with (root / "price_mapping.csv").open(newline="", encoding="utf-8") as h:
        mapping = list(csv.DictReader(h))
    for region in REGIONS:
        direct = [r for r in mapping if r["region_id"] == region and r["component_kind"] == "division_total"]
        diagnostics = [r for r in mapping if r["region_id"] == region and r["component_kind"] == "diagnostic_subcomponent"]
        if len(direct) != 12 or {r["price_series_id"] for r in direct} != set(DIVISION_IDS):
            raise BuildError(f"engel_phase_b_mapping_division_inventory:{region}")
        if {r["component_id"] for r in diagnostics} != {"alcoholic_beverages_021", "tobacco_022", "restaurants_111"}:
            raise BuildError(f"engel_phase_b_mapping_diagnostics_inventory:{region}")

    return {
        "result": "compatible_with_warnings",
        "release_id": manifest["release_id"],
        "artifact_type": ARTIFACT_TYPE,
        "method_id": METHOD_ID,
        "monthly_rows": len(paths),
        "contribution_rows": len(contributions),
        "line_path_rows": len(line_rows),
        "warnings": manifest.get("warnings", []),
    }
