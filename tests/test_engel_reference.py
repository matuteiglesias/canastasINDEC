import csv
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from basket_release.core import BuildError
from basket_release.engel.article_classification import build_article_mapping
from basket_release.engel.artifact import build_reference_artifact, validate_reference_artifact
from basket_release.engel.commissioning import commission_reference_artifact
from basket_release.engel.reference_population import select_reference_population
from tests.engel_fixture_factory import create_engho_parent


class EngelReferencePhaseATests(unittest.TestCase):
    def test_reference_artifact_builds_and_stays_phase_a_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent = create_engho_parent(root / "parent")
            release = build_reference_artifact(parent, root / "artifacts")
            result = validate_reference_artifact(release)
            self.assertEqual(result["rows"], 7)
            manifest = json.loads((release / "manifest.json").read_text())
            self.assertFalse(manifest["scientific_poverty_execution_performed"])
            self.assertFalse(manifest["price_trajectory_execution_performed"])
            self.assertFalse(manifest["cbt_execution_performed"])
            self.assertIn("synthetic_person_table_warning_for_lineage_test", manifest["warnings"])

            with (release / "reference_structure.csv").open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual({r["region_id"] for r in rows}, {
                "national", "gran_buenos_aires", "pampeana", "noreste", "noroeste", "cuyo", "patagonia"
            })
            for row in rows:
                self.assertEqual(row["restaurants_in_food"], "false")
                self.assertEqual(row["tobacco_in_food"], "false")
                shares = sum(Decimal(row[f"division_{i:02d}_share"]) for i in range(1, 13))
                self.assertAlmostEqual(float(shares), 1.0, places=12)
                self.assertAlmostEqual(float(Decimal(row["food_share"]) * Decimal(row["ice_base"])), 1.0, places=12)

            diagnostics = json.loads((release / "diagnostics.json").read_text())
            self.assertFalse(diagnostics["parent"]["persons_consumed"])
            self.assertTrue(diagnostics["bootstrap"]["reference_population_reselected_per_replicate"])
            self.assertEqual(diagnostics["bootstrap"]["number_of_replicates"], 4)

    def test_commissioning_emits_g1_to_g4(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release = build_reference_artifact(create_engho_parent(root / "parent"), root / "artifacts")
            out = commission_reference_artifact(release, root / "commissioning")
            summary = json.loads((out / "commissioning.json").read_text())
            self.assertEqual(summary["g1"], "pass")
            self.assertEqual(summary["g2"], "pass")
            self.assertEqual(summary["g3"], "diagnostic")
            self.assertEqual(summary["g4"], "diagnostic")
            self.assertFalse(summary["scientific_poverty_execution_performed"])
            g1 = json.loads((out / "g1_reference_population.json").read_text())
            self.assertGreater(Decimal(g1["selected_weight_share"]), Decimal("0.15"))
            self.assertLess(Decimal(g1["selected_weight_share"]), Decimal("0.23"))

    def test_weighted_cutpoints_keep_ties_whole_and_rank_zero_negative(self):
        rows = [
            {"id": "a", "ingpch": "-1", "pondera": "1", "region": "1"},
            {"id": "b", "ingpch": "0", "pondera": "1", "region": "2"},
            {"id": "c", "ingpch": "1", "pondera": "1", "region": "3"},
            {"id": "d", "ingpch": "2", "pondera": "1", "region": "4"},
            {"id": "e", "ingpch": "2", "pondera": "1", "region": "5"},
            {"id": "f", "ingpch": "3", "pondera": "1", "region": "6"},
            {"id": "g", "ingpch": "4", "pondera": "1", "region": "1"},
            {"id": "h", "ingpch": "5", "pondera": "1", "region": "2"},
            {"id": "i", "ingpch": "6", "pondera": "1", "region": "3"},
            {"id": "j", "ingpch": "7", "pondera": "1", "region": "4"},
        ]
        selection = select_reference_population(
            rows, percentile_low=Decimal("0.30"), percentile_high=Decimal("0.60")
        )
        self.assertEqual(selection["cut_lower"], Decimal("1"))
        self.assertEqual(selection["cut_upper"], Decimal("3"))
        self.assertEqual(selection["selected_ids"], {"c", "d", "e"})
        self.assertEqual(selection["upper_tie_households"], 1)

    def test_missing_ranking_value_fails_closed(self):
        rows = [{"id": "a", "ingpch": "", "pondera": "1", "region": "1"}]
        with self.assertRaisesRegex(BuildError, "invalid_ranking_income"):
            select_reference_population(rows)

    def test_unknown_article_and_negative_expenditure_fail(self):
        for option in ("unknown", "negative"):
            with self.subTest(option=option), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                parent = create_engho_parent(
                    root / "parent",
                    unknown_article=(option == "unknown"),
                    negative_amount=(option == "negative"),
                )
                pattern = "unknown_article_code" if option == "unknown" else "negative_expenditure_amount"
                with self.assertRaisesRegex(BuildError, pattern):
                    build_reference_artifact(parent, root / "artifacts")

    def test_food_rule_is_coicop1_plus_alcohol_not_tobacco_or_restaurant(self):
        rows = [
            {"articulo": "f", "division": "01", "grupo": "011"},
            {"articulo": "a", "division": "02", "grupo": "021"},
            {"articulo": "t", "division": "02", "grupo": "022"},
            {"articulo": "r", "division": "11", "grupo": "111"},
            {"articulo": "h", "division": "11", "grupo": "112"},
        ]
        mapping = build_article_mapping(rows)
        self.assertTrue(mapping["f"]["food"])
        self.assertTrue(mapping["a"]["food"])
        self.assertFalse(mapping["t"]["food"])
        self.assertFalse(mapping["r"]["food"])
        self.assertFalse(mapping["h"]["food"])
        self.assertTrue(mapping["r"]["restaurant"])
        self.assertTrue(mapping["t"]["tobacco"])

    def test_build_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent = create_engho_parent(root / "parent")
            first = build_reference_artifact(parent, root / "artifacts")
            second = build_reference_artifact(parent, root / "artifacts")
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
