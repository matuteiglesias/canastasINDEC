"""Compare two basket artifacts without silently replacing an accepted parent.

This module is deliberately conservative.  It distinguishes byte/serialization
changes from target-period scientific value changes and can compare optional JSON
manifests.  The intended use is lineage archaeology for governed poverty inputs,
not promotion of a candidate release.

CLI example::

    python -m basket_release.lineage_compare \
      --accepted data/CB_Reg_defl_Q.csv \
      --candidate /tmp/CB_Reg_defl_Q.main.csv \
      --period 2024-Q3 \
      --accepted-sha 114efe353c98bd875bfef882d13a636df32ab92c930c985fe967062d6d0cb002 \
      --output /tmp/canastas-lineage-report.json

Classification:

A  full CSV content is scientifically identical after harmless serialization
   normalization (row/column order, numeric spelling, surrounding whitespace).
B  full CSV content is identical but supplied lineage/manifest metadata differs.
C  requested period's six-region CBA/CBT values are identical, but the broader
   artifact or lineage differs.
D  requested period's scientific monetary inputs differ.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REGION_ALIASES = {
    "gran_buenos_aires": {
        "gran_buenos_aires", "gran buenos aires", "gba", "g_b_a", "g_buenos_aires"
    },
    "noroeste": {"noroeste", "noa", "northwest"},
    "noreste": {"noreste", "nea", "northeast"},
    "cuyo": {"cuyo"},
    "pampeana": {"pampeana", "pampeana_region", "pampean"},
    "patagonia": {"patagonia", "patagonica", "patagonica_region"},
}

PERIOD_ALIASES = {
    "date", "fecha", "period", "periodo", "periodo_referencia", "quarter", "q", "time"
}
REGION_COLUMN_ALIASES = {"region", "region_id", "region_name", "reg", "reg_name"}
CBA_ALIASES = {
    "cba", "canasta_basica_alimentaria", "canasta_basica_alimentos", "food_basket"
}
CBT_ALIASES = {
    "cbt", "canasta_basica_total", "total_basket"
}
MISSING = {"", "na", "nan", "none", "null", "n/a"}


class LineageCompareError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _norm_name(value: str) -> str:
    value = value.replace("\ufeff", "").strip().casefold()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value


def _norm_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _norm_scalar(value: str) -> str:
    text = value.strip()
    if _norm_text(text) in MISSING:
        return ""
    # Normalize plain finite decimals while leaving dates/codes such as 2024-Q3 alone.
    if re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?", text):
        numeric = text.replace(",", ".")
        try:
            d = Decimal(numeric)
        except InvalidOperation:
            return text
        if not d.is_finite():
            return text
        rendered = format(d.normalize(), "f")
        if "." in rendered:
            rendered = rendered.rstrip("0").rstrip(".")
        return "0" if rendered in {"-0", "+0", ""} else rendered
    return text.strip()


def _sniff_dialect(path: Path) -> csv.Dialect:
    sample = path.read_text(encoding="utf-8-sig", errors="replace")[:65536]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        return csv.excel


@dataclass(frozen=True)
class CanonicalCsv:
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    digest: str


def canonical_csv(path: Path) -> CanonicalCsv:
    dialect = _sniff_dialect(path)
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh, dialect=dialect)
        if reader.fieldnames is None:
            raise LineageCompareError(f"CSV has no header: {path}")
        pairs = [(name, _norm_name(name)) for name in reader.fieldnames]
        # Ignore pandas-style unnamed index columns only when the header is genuinely unnamed.
        pairs = [(raw, norm) for raw, norm in pairs if norm and not norm.startswith("unnamed_")]
        normalized = [norm for _, norm in pairs]
        if len(normalized) != len(set(normalized)):
            raise LineageCompareError(f"normalized duplicate columns in {path}: {normalized}")
        columns = tuple(sorted(normalized))
        raw_by_norm = {norm: raw for raw, norm in pairs}
        rows: list[tuple[str, ...]] = []
        for row in reader:
            rows.append(tuple(_norm_scalar(row.get(raw_by_norm[col], "")) for col in columns))
    rows.sort()
    payload = json.dumps({"columns": columns, "rows": rows}, separators=(",", ":"), ensure_ascii=False)
    return CanonicalCsv(columns, tuple(rows), hashlib.sha256(payload.encode()).hexdigest())


def _region(value: str) -> str | None:
    n = _norm_name(value)
    n_text = _norm_text(value)
    for canonical, aliases in REGION_ALIASES.items():
        normalized_aliases = {_norm_name(a) for a in aliases} | {_norm_text(a) for a in aliases}
        if n in normalized_aliases or n_text in normalized_aliases:
            return canonical
    return None


def _quarter_target(period: str) -> tuple[int, int]:
    m = re.fullmatch(r"\s*(\d{4})[-_ ]?[Qq]([1-4])\s*", period)
    if not m:
        raise LineageCompareError(f"period must look like YYYY-QN, got {period!r}")
    return int(m.group(1)), int(m.group(2))


def _period_matches(value: str, target: tuple[int, int]) -> bool:
    text = value.strip()
    year, quarter = target
    m = re.fullmatch(r"(\d{4})[-_ ]?[Qq]([1-4])", text)
    if m:
        return (int(m.group(1)), int(m.group(2))) == target
    m = re.match(r"(\d{4})[-/](\d{1,2})(?:[-/]\d{1,2})?", text)
    if m:
        y, month = int(m.group(1)), int(m.group(2))
        return y == year and ((month - 1) // 3 + 1) == quarter
    return False


def _decimal(value: str, *, field: str) -> Decimal:
    text = value.strip().replace(",", ".")
    try:
        d = Decimal(text)
    except InvalidOperation as exc:
        raise LineageCompareError(f"non-numeric {field}: {value!r}") from exc
    if not d.is_finite():
        raise LineageCompareError(f"non-finite {field}: {value!r}")
    return d


def _read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    dialect = _sniff_dialect(path)
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh, dialect=dialect)
        if reader.fieldnames is None:
            raise LineageCompareError(f"CSV has no header: {path}")
        names = list(reader.fieldnames)
        return names, list(reader)


def _choose_column(fieldnames: Sequence[str], aliases: set[str]) -> str | None:
    for raw in fieldnames:
        if _norm_name(raw) in aliases:
            return raw
    return None


def _metric_column(fieldnames: Sequence[str], aliases: set[str]) -> str | None:
    return _choose_column(fieldnames, aliases)


def _parse_wide_metric_column(name: str) -> tuple[str, str] | None:
    n = _norm_name(name)
    metric: str | None = None
    if "cba" in n or "canasta_basica_alimentaria" in n:
        metric = "CBA"
    elif "cbt" in n or "canasta_basica_total" in n:
        metric = "CBT"
    if metric is None:
        return None
    for canonical, aliases in REGION_ALIASES.items():
        tokens = {_norm_name(a) for a in aliases} | {canonical}
        if any(token and token in n for token in tokens):
            return metric, canonical
    return None


def extract_period_values(path: Path, period: str) -> dict[str, dict[str, str]]:
    """Return six-region target-period CBA/CBT values in canonical decimal spelling."""
    target = _quarter_target(period)
    fieldnames, rows = _read_rows(path)
    period_col = _choose_column(fieldnames, PERIOD_ALIASES)
    if period_col is None:
        # Historical CSVs frequently write their pandas index as a blank/unnamed first field.
        period_col = fieldnames[0]

    region_col = _choose_column(fieldnames, REGION_COLUMN_ALIASES)
    cba_col = _metric_column(fieldnames, CBA_ALIASES)
    cbt_col = _metric_column(fieldnames, CBT_ALIASES)
    out: dict[str, dict[str, str]] = {}

    if region_col and cba_col and cbt_col:
        for row in rows:
            if not _period_matches(row.get(period_col, ""), target):
                continue
            region = _region(row.get(region_col, ""))
            if region is None:
                continue
            if region in out:
                raise LineageCompareError(f"duplicate {period} row for region {region} in {path}")
            out[region] = {
                "CBA": _norm_scalar(str(_decimal(row.get(cba_col, ""), field=f"{region}.CBA"))),
                "CBT": _norm_scalar(str(_decimal(row.get(cbt_col, ""), field=f"{region}.CBT"))),
            }
    else:
        metric_columns: dict[str, tuple[str, str]] = {}
        for name in fieldnames:
            parsed = _parse_wide_metric_column(name)
            if parsed:
                metric_columns[name] = parsed
        target_rows = [row for row in rows if _period_matches(row.get(period_col, ""), target)]
        if len(target_rows) != 1:
            raise LineageCompareError(
                f"expected one wide row for {period} in {path}; found {len(target_rows)}; "
                f"columns={fieldnames}"
            )
        row = target_rows[0]
        for name, (metric, region) in metric_columns.items():
            out.setdefault(region, {})[metric] = _norm_scalar(
                str(_decimal(row.get(name, ""), field=f"{region}.{metric}"))
            )

    expected_regions = set(REGION_ALIASES)
    missing_regions = sorted(expected_regions - set(out))
    missing_metrics = sorted(
        f"{region}.{metric}"
        for region in expected_regions
        for metric in ("CBA", "CBT")
        if metric not in out.get(region, {})
    )
    if missing_regions or missing_metrics:
        raise LineageCompareError(
            f"could not recover complete {period} basket slice from {path}; "
            f"missing_regions={missing_regions}; missing_metrics={missing_metrics}; columns={fieldnames}"
        )
    return {region: out[region] for region in sorted(out)}


def _json_diff(a: Any, b: Any, prefix: str = "$") -> list[dict[str, Any]]:
    if type(a) is not type(b):
        return [{"path": prefix, "accepted": a, "candidate": b}]
    if isinstance(a, dict):
        diffs: list[dict[str, Any]] = []
        for key in sorted(set(a) | set(b)):
            p = f"{prefix}.{key}"
            if key not in a:
                diffs.append({"path": p, "accepted": "<missing>", "candidate": b[key]})
            elif key not in b:
                diffs.append({"path": p, "accepted": a[key], "candidate": "<missing>"})
            else:
                diffs.extend(_json_diff(a[key], b[key], p))
        return diffs
    if isinstance(a, list):
        if a == b:
            return []
        return [{"path": prefix, "accepted": a, "candidate": b}]
    if a != b:
        return [{"path": prefix, "accepted": a, "candidate": b}]
    return []


def _load_manifest(path: Path | None) -> Any | None:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _value_diffs(
    accepted: Mapping[str, Mapping[str, str]],
    candidate: Mapping[str, Mapping[str, str]],
) -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    for region in sorted(set(accepted) | set(candidate)):
        for metric in ("CBA", "CBT"):
            av = accepted.get(region, {}).get(metric)
            cv = candidate.get(region, {}).get(metric)
            if av == cv:
                continue
            item: dict[str, Any] = {"region": region, "metric": metric, "accepted": av, "candidate": cv}
            try:
                ad, cd = Decimal(av), Decimal(cv)  # type: ignore[arg-type]
                item["delta"] = str(cd - ad)
                item["relative_delta"] = None if ad == 0 else str((cd - ad) / ad)
            except Exception:
                pass
            diffs.append(item)
    return diffs


def compare(
    *,
    accepted: Path,
    candidate: Path,
    period: str,
    accepted_manifest: Path | None = None,
    candidate_manifest: Path | None = None,
    accepted_sha: str | None = None,
    candidate_sha: str | None = None,
) -> dict[str, Any]:
    accepted_raw_sha = sha256_file(accepted)
    candidate_raw_sha = sha256_file(candidate)
    if accepted_sha and accepted_raw_sha != accepted_sha:
        raise LineageCompareError(
            f"accepted SHA mismatch: expected {accepted_sha}, observed {accepted_raw_sha} ({accepted})"
        )
    if candidate_sha and candidate_raw_sha != candidate_sha:
        raise LineageCompareError(
            f"candidate SHA mismatch: expected {candidate_sha}, observed {candidate_raw_sha} ({candidate})"
        )

    a_csv = canonical_csv(accepted)
    c_csv = canonical_csv(candidate)
    a_slice = extract_period_values(accepted, period)
    c_slice = extract_period_values(candidate, period)
    value_diffs = _value_diffs(a_slice, c_slice)

    a_manifest = _load_manifest(accepted_manifest)
    c_manifest = _load_manifest(candidate_manifest)
    manifest_diffs: list[dict[str, Any]] = []
    manifests_supplied = accepted_manifest is not None or candidate_manifest is not None
    if accepted_manifest is not None and candidate_manifest is not None:
        manifest_diffs = _json_diff(a_manifest, c_manifest)
    elif manifests_supplied:
        manifest_diffs = [{
            "path": "$",
            "accepted": "supplied" if accepted_manifest else "<missing>",
            "candidate": "supplied" if candidate_manifest else "<missing>",
        }]

    full_values_equal = a_csv.digest == c_csv.digest
    target_values_equal = not value_diffs
    raw_equal = accepted_raw_sha == candidate_raw_sha

    if not target_values_equal:
        classification = "D"
        label = "materially_different_monetary_input"
    elif full_values_equal and manifest_diffs:
        classification = "B"
        label = "metadata_lineage_only"
    elif full_values_equal:
        classification = "A"
        label = "byte_or_serialization_only"
    else:
        classification = "C"
        label = "scientifically_equivalent_target_values_different_parent_or_broader_artifact"

    return {
        "schema": "research.basket-lineage-comparison/v1",
        "period": period,
        "classification": classification,
        "classification_label": label,
        "promotion_authorized": False,
        "accepted": {
            "path": str(accepted),
            "sha256": accepted_raw_sha,
            "canonical_csv_sha256": a_csv.digest,
            "period_values": a_slice,
            "manifest": str(accepted_manifest) if accepted_manifest else None,
        },
        "candidate": {
            "path": str(candidate),
            "sha256": candidate_raw_sha,
            "canonical_csv_sha256": c_csv.digest,
            "period_values": c_slice,
            "manifest": str(candidate_manifest) if candidate_manifest else None,
        },
        "comparison": {
            "raw_bytes_equal": raw_equal,
            "canonical_full_csv_equal": full_values_equal,
            "target_period_values_equal": target_values_equal,
            "target_value_differences": value_diffs,
            "manifest_differences": manifest_diffs,
        },
        "decision_rule": {
            "A": "full scientific table equal after harmless serialization normalization",
            "B": "full scientific table equal; supplied lineage metadata differs",
            "C": "target-period six-region CBA/CBT values equal; broader artifact or lineage differs",
            "D": "target-period CBA/CBT values differ",
        },
        "next_action": {
            "A": "safe to treat monetary content as equivalent; retain accepted parent until explicit release promotion",
            "B": "inspect manifest differences; do not replace accepted parent merely to normalize lineage metadata",
            "C": "target-period poverty input is scientifically equivalent, but preserve both parent identities and document lineage",
            "D": "do not replace accepted parent; investigate IPC/source/reference/value differences before any new scientific run",
        }[classification],
    }


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--accepted", type=Path, required=True)
    p.add_argument("--candidate", type=Path, required=True)
    p.add_argument("--period", required=True, help="Target quarter, e.g. 2024-Q3")
    p.add_argument("--accepted-manifest", type=Path)
    p.add_argument("--candidate-manifest", type=Path)
    p.add_argument("--accepted-sha")
    p.add_argument("--candidate-sha")
    p.add_argument("--output", type=Path)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = compare(
            accepted=args.accepted,
            candidate=args.candidate,
            period=args.period,
            accepted_manifest=args.accepted_manifest,
            candidate_manifest=args.candidate_manifest,
            accepted_sha=args.accepted_sha,
            candidate_sha=args.candidate_sha,
        )
    except LineageCompareError as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}, indent=2))
        return 2
    rendered = json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
