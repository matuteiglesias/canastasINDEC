import csv
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from basket_release.core import BuildError
from basket_release.engel.phase_b_artifact import (
    build_sensitivity_artifact,
    validate_sensitivity_artifact,
)
from basket_release.engel.phase_b_commissioning import commission_sensitivity_artifact
from basket_release.engel.phase_b_parents import month_sequence
from basket_release.engel.trajectory_contracts import BASE_PERIOD, DIVISION_IDS, REGIONS
from engel_phase_b_fixture_factory import (
    create_phase_b_parents,
    rehash_ipc,
    rehash_reference,
)


class EngelPhaseBTests(unittest.TestCase):
    def test_full_window_artifact_builds_and_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            reference,ipc,basket=create_phase_b_parents(root/"parents")
            release=build_sensitivity_artifact(reference,ipc,basket,root/"out")
            result=validate_sensitivity_artifact(release)
            self.assertEqual(result["monthly_rows"],len(month_sequence())*6)
            self.assertEqual(result["contribution_rows"],len(month_sequence())*6*12)
            self.assertEqual(result["line_path_rows"],len(month_sequence())*6*3)
            manifest=json.loads((release/"manifest.json").read_text())
            self.assertFalse(manifest["scientific_poverty_execution_performed"])
            self.assertFalse(manifest["reference_population_recomputed"])
            self.assertFalse(manifest["articles_reclassified"])
            self.assertFalse(manifest["cba_modified"])

    def test_base_normalization_and_factorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            reference,ipc,basket=create_phase_b_parents(root/"parents")
            release=build_sensitivity_artifact(reference,ipc,basket,root/"out")
            with (release/"threshold_paths.csv").open(newline="",encoding="utf-8") as h:
                rows=list(csv.DictReader(h))
            base=[r for r in rows if r["period"]==BASE_PERIOD]
            self.assertEqual(len(base),6)
            for row in base:
                self.assertAlmostEqual(float(Decimal(row["trajectory_factor"])),1.0,places=12)
                self.assertAlmostEqual(
                    float(Decimal(row["full_factor"])),
                    float(Decimal(row["level_factor"])),
                    places=12,
                )
                self.assertAlmostEqual(
                    float(Decimal(row["CBT_engho17"])),
                    float(Decimal(row["CBT_level_plus_trajectory"])),
                    places=8,
                )
                self.assertAlmostEqual(float(Decimal(row["food_price_relative"])),1.0,places=12)
                self.assertAlmostEqual(float(Decimal(row["total_expenditure_price_relative"])),1.0,places=12)

    def test_food_path_uses_coicop01_plus_alcohol_not_all_coicop02(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            reference,ipc,basket=create_phase_b_parents(root/"parents")
            release=build_sensitivity_artifact(reference,ipc,basket,root/"out")
            with (release/"price_mapping.csv").open(newline="",encoding="utf-8") as h:
                rows=list(csv.DictReader(h))
            region="gran_buenos_aires"
            alcohol=next(r for r in rows if r["region_id"]==region and r["component_id"]=="alcoholic_beverages_021")
            tobacco=next(r for r in rows if r["region_id"]==region and r["component_id"]=="tobacco_022")
            restaurant=next(r for r in rows if r["region_id"]==region and r["component_id"]=="restaurants_111")
            self.assertEqual(alcohol["price_series_id"],"coicop02")
            self.assertNotEqual(Decimal(alcohol["food_component_base_share"]),0)
            self.assertEqual(tobacco["price_series_id"],"coicop02")
            self.assertEqual(Decimal(tobacco["food_component_base_share"]),0)
            self.assertEqual(restaurant["price_series_id"],"coicop11")
            self.assertEqual(Decimal(restaurant["food_component_base_share"]),0)

    def test_contributions_reconcile_total_and_food_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            reference,ipc,basket=create_phase_b_parents(root/"parents")
            release=build_sensitivity_artifact(reference,ipc,basket,root/"out")
            with (release/"threshold_paths.csv").open(newline="",encoding="utf-8") as h:
                paths={(r["period"],r["region_id"]):r for r in csv.DictReader(h)}
            with (release/"division_contributions.csv").open(newline="",encoding="utf-8") as h:
                rows=list(csv.DictReader(h))
            key=(month_sequence()[20],"pampeana")
            selected=[r for r in rows if (r["period"],r["region_id"])==key]
            self.assertEqual({r["division_id"] for r in selected},set(DIVISION_IDS))
            total=sum(Decimal(r["weighted_cost_contribution"]) for r in selected)
            food=sum(Decimal(r["food_weighted_cost_contribution"]) for r in selected)
            path=paths[key]
            self.assertAlmostEqual(float(total),float(Decimal(path["total_expenditure_price_relative"])),places=12)
            declared_food=Decimal(path["food_base_share"])*Decimal(path["food_price_relative"])
            self.assertAlmostEqual(float(food),float(declared_food),places=12)

    def test_commissioning_emits_p_a_m_and_g5(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            reference,ipc,basket=create_phase_b_parents(root/"parents")
            release=build_sensitivity_artifact(reference,ipc,basket,root/"out")
            out=commission_sensitivity_artifact(release,root/"commission")
            summary=json.loads((out/"commissioning.json").read_text())
            self.assertEqual(summary["G5_level_trajectory_observability"],"pass")
            self.assertEqual(summary["P_cross_parent_integrity"],"pass")
            self.assertEqual(summary["A_arithmetic"],"pass")
            self.assertEqual(summary["M_price_mapping"],"pass_with_documented_approximations")
            self.assertFalse(summary["scientific_poverty_execution_performed"])
            with (out/"g5_region_summary.csv").open(newline="",encoding="utf-8") as h:
                regional=list(csv.DictReader(h))
            self.assertEqual({r["region_id"] for r in regional},set(REGIONS))
            with (out/"g5_divergence_contributions.csv").open(newline="",encoding="utf-8") as h:
                contributions=list(csv.DictReader(h))
            self.assertEqual(len(contributions),6*12)

    def test_missing_ipc_cell_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            reference,ipc,basket=create_phase_b_parents(root/"parents")
            table=ipc/"regional_division_indices.csv"
            with table.open(newline="",encoding="utf-8") as h: rows=list(csv.DictReader(h))
            fields=list(rows[0]); rows=rows[1:]
            with table.open("w",newline="",encoding="utf-8") as h:
                w=csv.DictWriter(h,fieldnames=fields,lineterminator="\n");w.writeheader();w.writerows(rows)
            rehash_ipc(ipc)
            with self.assertRaisesRegex(BuildError,"ipc_required_window_missing"):
                build_sensitivity_artifact(reference,ipc,basket,root/"out")

    def test_duplicate_ipc_cell_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            reference,ipc,basket=create_phase_b_parents(root/"parents")
            table=ipc/"regional_division_indices.csv"
            with table.open(newline="",encoding="utf-8") as h: rows=list(csv.DictReader(h))
            fields=list(rows[0]); rows.append(dict(rows[0]))
            with table.open("w",newline="",encoding="utf-8") as h:
                w=csv.DictWriter(h,fieldnames=fields,lineterminator="\n");w.writeheader();w.writerows(rows)
            rehash_ipc(ipc)
            with self.assertRaisesRegex(BuildError,"ipc_duplicate_cell"):
                build_sensitivity_artifact(reference,ipc,basket,root/"out")

    def test_missing_ipc_division_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            reference,ipc,basket=create_phase_b_parents(root/"parents")
            table=ipc/"regional_division_indices.csv"
            with table.open(newline="",encoding="utf-8") as h: rows=list(csv.DictReader(h))
            fields=list(rows[0]); rows=[r for r in rows if r["division_id"]!="coicop12"]
            with table.open("w",newline="",encoding="utf-8") as h:
                w=csv.DictWriter(h,fieldnames=fields,lineterminator="\n");w.writeheader();w.writerows(rows)
            rehash_ipc(ipc)
            with self.assertRaisesRegex(BuildError,"ipc_required_window_missing"):
                build_sensitivity_artifact(reference,ipc,basket,root/"out")

    def test_wrong_reference_method_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            reference,ipc,basket=create_phase_b_parents(root/"parents")
            manifest_path=reference/"manifest.json"
            manifest=json.loads(manifest_path.read_text())
            manifest["method_id"]="wrong-method"
            manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
            with self.assertRaisesRegex(BuildError,"engel_artifact_identity_mismatch|reference_parent_identity_mismatch"):
                build_sensitivity_artifact(reference,ipc,basket,root/"out")

    def test_unknown_food_price_mapping_fails_instead_of_falling_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            reference,ipc,basket=create_phase_b_parents(root/"parents")
            table=reference/"reference_structure.csv"
            with table.open(newline="",encoding="utf-8") as h: rows=list(csv.DictReader(h))
            fields=list(rows[0])
            for row in rows:
                if row["region_id"]=="gran_buenos_aires":
                    row["food_scope"]="unsupported_future_scope"
            with table.open("w",newline="",encoding="utf-8") as h:
                w=csv.DictWriter(h,fieldnames=fields,lineterminator="\n");w.writeheader();w.writerows(rows)
            rehash_reference(reference)
            with self.assertRaisesRegex(BuildError,"reference_food_scope_mismatch"):
                build_sensitivity_artifact(reference,ipc,basket,root/"out")

    def test_official_cba_is_preserved_and_three_line_paths_are_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            reference,ipc,basket=create_phase_b_parents(root/"parents")
            release=build_sensitivity_artifact(reference,ipc,basket,root/"out")
            with (basket/"observed_nominal_monthly.csv").open(newline="",encoding="utf-8") as h:
                official={(r["period"],r["region_id"]):r for r in csv.DictReader(h)}
            with (release/"threshold_paths.csv").open(newline="",encoding="utf-8") as h:
                paths=list(csv.DictReader(h))
            for row in paths[:30]:
                self.assertEqual(Decimal(row["CBA_official"]),Decimal(official[(row["period"],row["region_id"])]["CBA_nominal"]))
            with (release/"line_paths.csv").open(newline="",encoding="utf-8") as h:
                lines=list(csv.DictReader(h))
            first=(month_sequence()[12],"cuyo")
            values={r["line_path_id"]:Decimal(r["threshold_value"]) for r in lines if (r["period"],r["region_id"])==first}
            self.assertEqual(set(values),{"official","engho17_level_only","engho17_level_plus_trajectory"})
            self.assertNotEqual(values["official"],values["engho17_level_only"])
            self.assertNotEqual(values["engho17_level_only"],values["engho17_level_plus_trajectory"])

    def test_build_is_idempotent_and_parent_lineage_is_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            reference,ipc,basket=create_phase_b_parents(root/"parents")
            first=build_sensitivity_artifact(reference,ipc,basket,root/"out")
            second=build_sensitivity_artifact(reference,ipc,basket,root/"out")
            self.assertEqual(first,second)
            locks=json.loads((first/"parent_locks.json").read_text())
            self.assertEqual(locks["engho_reference"]["release_id"],json.loads((reference/"manifest.json").read_text())["release_id"])
            self.assertEqual(locks["ipc_regional_divisions"]["release_id"],json.loads((ipc/"manifest.json").read_text())["release_id"])
            self.assertEqual(locks["official_baskets"]["release_id"],json.loads((basket/"manifest.json").read_text())["release_id"])


if __name__=="__main__":
    unittest.main()
