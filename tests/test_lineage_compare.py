import json
from pathlib import Path

from basket_release.lineage_compare import compare


REGIONS = [
    "cuyo",
    "gran_buenos_aires",
    "noreste",
    "noroeste",
    "pampeana",
    "patagonia",
]


def _long_csv(path: Path, *, q3_delta: float = 0.0, q4_delta: float = 0.0, reverse=False):
    rows = []
    for period, base, delta in [
        ("2024-08-15", 1000.0, q3_delta),
        ("2024-11-15", 2000.0, q4_delta),
    ]:
        for i, region in enumerate(REGIONS):
            rows.append((period, region, base + i + delta, 2 * (base + i + delta)))
    if reverse:
        rows.reverse()
    with path.open("w") as fh:
        fh.write("fecha,region,CBA,CBT\n")
        for period, region, cba, cbt in rows:
            fh.write(f"{period},{region},{cba:.3f},{cbt:.3f}\n")


def test_a_serialization_only(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    _long_csv(a)
    _long_csv(b, reverse=True)
    result = compare(accepted=a, candidate=b, period="2024-Q3")
    assert result["classification"] == "A"
    assert result["comparison"]["target_period_values_equal"] is True


def test_b_metadata_only(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    _long_csv(a)
    _long_csv(b)
    ma, mb = tmp_path / "a.json", tmp_path / "b.json"
    ma.write_text(json.dumps({"release_id": "accepted", "source": "same"}))
    mb.write_text(json.dumps({"release_id": "candidate", "source": "same"}))
    result = compare(
        accepted=a,
        candidate=b,
        period="2024-Q3",
        accepted_manifest=ma,
        candidate_manifest=mb,
    )
    assert result["classification"] == "B"


def test_c_same_q3_but_different_broader_artifact(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    _long_csv(a)
    _long_csv(b, q4_delta=17.0)
    result = compare(accepted=a, candidate=b, period="2024-Q3")
    assert result["classification"] == "C"
    assert result["comparison"]["canonical_full_csv_equal"] is False
    assert result["comparison"]["target_period_values_equal"] is True


def test_d_q3_values_changed(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    _long_csv(a)
    _long_csv(b, q3_delta=1.0)
    result = compare(accepted=a, candidate=b, period="2024-Q3")
    assert result["classification"] == "D"
    assert result["comparison"]["target_value_differences"]


def test_wide_format(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    cols = ["fecha"]
    for region in REGIONS:
        cols += [f"CBA_{region}", f"CBT_{region}"]
    values = ["2024-08-15"]
    for i, _ in enumerate(REGIONS):
        values += [str(1000 + i), str(2000 + i)]
    text = ",".join(cols) + "\n" + ",".join(values) + "\n"
    a.write_text(text)
    b.write_text(text)
    result = compare(accepted=a, candidate=b, period="2024-Q3")
    assert result["classification"] == "A"
    assert set(result["accepted"]["period_values"]) == set(REGIONS)
