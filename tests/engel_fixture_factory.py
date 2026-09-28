"""Synthetic publicdata.indec-engho-microdata/v1 parent for Phase-A tests."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="|", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_engho_parent(root: Path, *, unknown_article: bool = False, negative_amount: bool = False) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    tables = root / "tables"

    households = []
    replicates = []
    persons = []
    for i in range(1, 61):
        household_id = f"H{i:03d}"
        households.append({
            "id": household_id,
            "ingpch": str(i - 3),  # explicitly includes negative and zero incomes
            "pondera": "1",
            "region": str(((i - 1) % 6) + 1),
        })
        replicates.append({
            "id": household_id,
            "whog_rep1": "1",
            "whog_rep2": "1.05" if i % 2 else "0.95",
            "whog_rep3": "1.10" if i % 3 == 0 else "0.95",
            "whog_rep4": "0" if i % 10 == 0 else ("0.90" if i % 5 == 0 else "1.02"),
        })
        persons.append({"id": household_id, "miembro": "1"})

    article_rows = []
    for division in range(1, 13):
        d = f"{division:02d}"
        if division == 2:
            continue
        if division == 11:
            continue
        group = f"{division:02d}1"
        article_rows.append({
            "articulo": f"A{group}",
            "division": d,
            "grupo": group,
            "clase": group + "1",
            "subclase": group + "11",
            "articulo_desc": f"synthetic division {division}",
            "division_desc": f"division {division}",
            "grupo_desc": f"group {group}",
        })
    article_rows.extend([
        {
            "articulo": "A021", "division": "02", "grupo": "021", "clase": "0211",
            "subclase": "02111", "articulo_desc": "alcoholic beverage",
            "division_desc": "alcohol and tobacco", "grupo_desc": "alcoholic beverages",
        },
        {
            "articulo": "A022", "division": "02", "grupo": "022", "clase": "0221",
            "subclase": "02211", "articulo_desc": "tobacco",
            "division_desc": "alcohol and tobacco", "grupo_desc": "tobacco",
        },
        {
            "articulo": "A111", "division": "11", "grupo": "111", "clase": "1111",
            "subclase": "11111", "articulo_desc": "restaurant meal",
            "division_desc": "restaurants and hotels", "grupo_desc": "restaurants",
        },
        {
            "articulo": "A112", "division": "11", "grupo": "112", "clase": "1121",
            "subclase": "11211", "articulo_desc": "hotel",
            "division_desc": "restaurants and hotels", "grupo_desc": "hotels",
        },
    ])

    expenditures = []
    for i in range(1, 61):
        household_id = f"H{i:03d}"
        for article in article_rows:
            division = int(article["division"])
            if article["articulo"] == "A011":
                amount = 55 + (i % 5)
            elif article["articulo"] == "A021":
                amount = 6
            elif article["articulo"] == "A022":
                amount = 3
            elif article["articulo"] == "A111":
                amount = 9
            elif article["articulo"] == "A112":
                amount = 4
            else:
                amount = 8 + division + (i % 3)
            expenditures.append({
                "id": household_id,
                "miembro": "0",
                "articulo": article["articulo"],
                "division": article["division"],
                "grupo": article["grupo"],
                "monto": str(amount),
                "r_imputado": "1" if i % 10 == 0 and division == 4 else "2",
                "forma_pago": "1",
                "tipo_negocio": "4" if article["articulo"] == "A111" else "1",
                "modo_adq": "1",
                "lugar_adq": "2",
            })

    if unknown_article:
        expenditures[0]["articulo"] = "UNKNOWN"
    if negative_amount:
        expenditures[0]["monto"] = "-1"

    _write(tables / "households.txt", ["id", "ingpch", "pondera", "region"], households)
    _write(tables / "persons.txt", ["id", "miembro"], persons)
    _write(
        tables / "expenditures.txt",
        ["id", "miembro", "articulo", "division", "grupo", "monto", "r_imputado",
         "forma_pago", "tipo_negocio", "modo_adq", "lugar_adq"],
        expenditures,
    )
    _write(
        tables / "articles.txt",
        ["articulo", "division", "grupo", "clase", "subclase",
         "articulo_desc", "division_desc", "grupo_desc"],
        article_rows,
    )
    _write(
        tables / "replicate_weights.txt",
        ["id", "whog_rep1", "whog_rep2", "whog_rep3", "whog_rep4"],
        replicates,
    )

    role_paths = {
        "households": tables / "households.txt",
        "persons": tables / "persons.txt",
        "expenditures": tables / "expenditures.txt",
        "articles": tables / "articles.txt",
        "replicate_weights": tables / "replicate_weights.txt",
    }
    manifest_files = []
    for role, path in role_paths.items():
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle, delimiter="|")
            header = next(reader)
            row_count = sum(1 for _ in reader)
        manifest_files.append({
            "role": role,
            "file": path.relative_to(root).as_posix(),
            "normalized_filename": path.name,
            "bytes": path.stat().st_size,
            "sha256": _sha(path),
            "delimiter": "|",
            "encoding": "utf-8",
            "rows": row_count,
            "columns": len(header),
            "column_names": header,
        })
    manifest = {
        "schema_version": 1,
        "artifact_type": "publicdata.indec-engho-microdata/v1",
        "release_id": "engho-2017-2018-synthetic-phase-a",
        "publisher": "INDEC-synthetic-fixture",
        "survey_vintage": "2017-2018",
        "warnings": ["synthetic_person_table_warning_for_lineage_test"],
        "files": manifest_files,
        "scientific_transformations_performed": False,
    }
    (root / "output-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return root
