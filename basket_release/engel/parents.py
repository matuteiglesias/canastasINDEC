"""Verification and loading of immutable publicdata.indec-engho-microdata/v1 parents."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path, PurePosixPath

from basket_release.core import BuildError
from .contracts import (
    ARTICLE_REQUIRED,
    EXPENDITURE_REQUIRED,
    HOUSEHOLD_REQUIRED,
    PARENT_ARTIFACT_TYPE,
    REPLICATE_ID_REQUIRED,
    SURVEY_VINTAGE,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_child(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or relative in {"", "."}:
        raise BuildError(f"engho_parent_unsafe_path: {relative}")
    path = (root / relative).resolve()
    if root.resolve() not in path.parents:
        raise BuildError(f"engho_parent_unsafe_path: {relative}")
    return path


def _folded(fieldnames: list[str] | None) -> dict[str, str]:
    return {(name or "").strip().casefold(): name for name in (fieldnames or [])}


def _read_table(path: Path, delimiter: str) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        fields = reader.fieldnames or []
        rows = list(reader)
    return rows, fields


def load_engho_parent(root: Path, upstream_receipt: Path | None = None) -> dict:
    """Verify an immutable ENGHo parent and load only Phase-A-required tables.

    Persons are deliberately not loaded: Phase A is household/expenditure/article/
    replicate-weight based. Any upstream person-table warning is lineage only.
    """
    root = Path(root).expanduser().resolve()
    manifest_path = root / "output-manifest.json"
    if not manifest_path.is_file():
        raise BuildError("engho_parent_missing_manifest")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get("artifact_type") != PARENT_ARTIFACT_TYPE:
        raise BuildError("engho_parent_wrong_artifact_type")
    if manifest.get("survey_vintage") != SURVEY_VINTAGE:
        raise BuildError("engho_parent_wrong_vintage")
    files = manifest.get("files")
    if not isinstance(files, list):
        raise BuildError("engho_parent_invalid_file_inventory")
    by_role = {item.get("role"): item for item in files}
    required_roles = {"households", "expenditures", "articles", "replicate_weights"}
    if not required_roles.issubset(by_role):
        raise BuildError(f"engho_parent_missing_roles: {sorted(required_roles-set(by_role))}")

    tables: dict[str, list[dict[str, str]]] = {}
    schemas: dict[str, list[str]] = {}
    requirements = {
        "households": HOUSEHOLD_REQUIRED,
        "expenditures": EXPENDITURE_REQUIRED,
        "articles": ARTICLE_REQUIRED,
        "replicate_weights": REPLICATE_ID_REQUIRED,
    }
    for role in sorted(required_roles):
        item = by_role[role]
        path = _safe_child(root, item.get("file", ""))
        if not path.is_file():
            raise BuildError(f"engho_parent_missing_table: {role}")
        expected_size = item.get("bytes")
        expected_sha = item.get("sha256")
        if expected_size is not None and path.stat().st_size != int(expected_size):
            raise BuildError(f"engho_parent_table_size_mismatch: {role}")
        if expected_sha and sha256(path) != expected_sha:
            raise BuildError(f"engho_parent_table_checksum_mismatch: {role}")
        delimiter = item.get("delimiter") or "|"
        if delimiter not in {"|", ";", ",", "\t"}:
            raise BuildError(f"engho_parent_unsupported_delimiter: {role}")
        rows, fields = _read_table(path, delimiter)
        folded = _folded(fields)
        missing = sorted(requirements[role] - set(folded))
        if missing:
            raise BuildError(f"engho_parent_missing_columns: {role}: {missing}")
        # Canonicalize only field names to lowercase semantics; values are untouched.
        canonical = []
        for row in rows:
            canonical.append({key.strip().casefold(): value for key, value in row.items() if key is not None})
        tables[role] = canonical
        schemas[role] = [name.strip().casefold() for name in fields]

    warnings = list(manifest.get("warnings") or [])
    receipt_identity = None
    if upstream_receipt is not None:
        receipt_path = Path(upstream_receipt).expanduser().resolve()
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("release_id") != manifest.get("release_id"):
            raise BuildError("engho_upstream_receipt_release_mismatch")
        declared_hash = receipt.get("release_manifest_sha256") or receipt.get("manifest_sha256")
        actual_hash = hashlib.sha256(manifest_bytes).hexdigest()
        if declared_hash and declared_hash != actual_hash:
            raise BuildError("engho_upstream_receipt_manifest_mismatch")
        warnings.extend(receipt.get("warnings") or [])
        receipt_identity = {
            "path_name": receipt_path.name,
            "sha256": sha256(receipt_path),
            "receipt_type": receipt.get("receipt_type"),
            "status": receipt.get("status"),
        }

    return {
        "root": root,
        "manifest": manifest,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "release_id": manifest["release_id"],
        "tables": tables,
        "schemas": schemas,
        "warnings": sorted(set(str(x) for x in warnings)),
        "upstream_receipt": receipt_identity,
        "persons_consumed": False,
    }
