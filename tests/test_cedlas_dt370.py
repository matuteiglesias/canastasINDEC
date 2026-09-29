import csv
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from basket_release.engel.cedlas_dt370 import (
    PUBLISHED_COMBINED_PCT,
    VERY_LOW_PCT,
    LOW_PCT,
    build_replication_artifact,
    national_ice,
    regional_structure,
    table3_validation,
    validate_replication_artifact,
)
from basket_release.engel.cedlas_provenance import commission_low_education_provenance
from basket_release.engel.cedlas_old_reconstruction import reconstruct_old_method
from engel_phase_b_fixture_factory import create_ipc_parent, create_official_basket_parent


class CedlasDT370Tests(unittest.TestCase):
    def test_published_combined_is_exact_equal_group_average(self):
        self.assertEqual(
            PUBLISHED_COMBINED_PCT,
            tuple((a+b)/Decimal(2) for a,b in zip(VERY_LOW_PCT,LOW_PCT)),
        )
        self.assertEqual(national_ice(),Decimal(1)/Decimal("0.35"))

    def test_table3_algebra_matches_published_rounding(self):
        validation=table3_validation()
        self.assertTrue(all(row["ice_round_2_match"] for row in validation))
        self.assertLessEqual(max(row["max_share_round_1_pp_error"] for row in validation),Decimal("0.1"))
        gba=regional_structure("gran_buenos_aires")
        self.assertEqual((gba["division_share"]["coicop01"]*100).quantize(Decimal("0.1")),Decimal("32.6"))
        self.assertEqual((gba["division_share"]["coicop02"]*100).quantize(Decimal("0.1")),Decimal("2.5"))

    def test_tobacco_food_switch_is_explicit(self):
        exact=national_ice(coicop02_food_fraction=Decimal(1))
        none=national_ice(coicop02_food_fraction=Decimal(0))
        partial=national_ice(coicop02_food_fraction=Decimal("0.6"))
        self.assertLess(exact,partial)
        self.assertLess(partial,none)

    def test_synthetic_full_artifact_and_old_control(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            ipc=create_ipc_parent(root/"ipc")
            basket=create_official_basket_parent(root/"basket")
            release=build_replication_artifact(ipc,basket,root/"out")
            result=validate_replication_artifact(release)
            self.assertEqual(result["monthly_rows"],92*6)
            self.assertTrue(result["tobacco_in_food"])
            qa=json.loads((release/"qa.json").read_text())
            self.assertTrue(qa["table3_all_ice_round_2_match"])
            old=reconstruct_old_method(ipc,basket,root/"old")
            self.assertTrue((old/"old_method_reconstruction.csv").is_file())

    def test_low_education_provenance_outputs_aggregates_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); release=root/"engho"; tables=release/"tables"; tables.mkdir(parents=True)
            fields=["id","pondera","region","clima_educativo","gastot"]+[f"gc_{i:02d}" for i in range(1,13)]
            rows=[]
            for i,climate in enumerate((1,1,2,2),1):
                shares=VERY_LOW_PCT if climate==1 else LOW_PCT
                total=Decimal("1000")
                row={"id":f"h{i}","pondera":"1","region":"1","clima_educativo":str(climate),"gastot":str(total)}
                for j,pct in enumerate(shares,1):
                    row[f"gc_{j:02d}"]=str(total*pct/Decimal(100))
                rows.append(row)
            with (tables/"households.txt").open("w",newline="",encoding="utf-8") as h:
                w=csv.DictWriter(h,fieldnames=fields,delimiter="|",lineterminator="\n");w.writeheader();w.writerows(rows)
            ex_fields=["id","division","grupo","monto"]
            ex_rows=[
                {"id":"h1","division":"02","grupo":"021","monto":"20"},
                {"id":"h1","division":"02","grupo":"022","monto":"6"},
                {"id":"h3","division":"02","grupo":"021","monto":"18"},
                {"id":"h3","division":"02","grupo":"022","monto":"5"},
            ]
            with (tables/"expenditures.txt").open("w",newline="",encoding="utf-8") as h:
                w=csv.DictWriter(h,fieldnames=ex_fields,delimiter="|",lineterminator="\n");w.writeheader();w.writerows(ex_rows)
            (release/"output-manifest.json").write_text(json.dumps({
                "artifact_type":"publicdata.indec-engho-microdata/v1",
                "release_id":"synthetic-engho",
                "files":[
                    {"role":"households","file":"tables/households.txt","delimiter":"|"},
                    {"role":"expenditures","file":"tables/expenditures.txt","delimiter":"|"},
                ]
            }))
            out=commission_low_education_provenance(release,root/"prov")
            qa=json.loads((out/"qa.json").read_text())
            self.assertEqual(Decimal(qa["very_low_max_abs_pp_difference_vs_published_table1"]),Decimal(0))
            self.assertEqual(Decimal(qa["low_max_abs_pp_difference_vs_published_table1"]),Decimal(0))
            self.assertTrue(qa["published_combined_is_exact_mean_of_published_subgroups"])
            text=(out/"national_reference_variants.csv").read_text()
            self.assertNotIn("h1",text)


if __name__=="__main__":
    unittest.main()
