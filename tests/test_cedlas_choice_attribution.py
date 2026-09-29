import csv
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from basket_release.engel.cedlas_choice_attribution import build_choice_attribution
from basket_release.engel.trajectory_contracts import REGIONS
from engel_phase_b_fixture_factory import create_ipc_parent, create_official_basket_parent


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf-8") as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]),lineterminator="\n")
        w.writeheader(); w.writerows(rows)


def _provenance(root: Path) -> Path:
    root.mkdir(parents=True,exist_ok=True)
    # Two national variants with deliberately different food shares.
    equal=[Decimal("0.3255"),Decimal("0.0245"),Decimal("0.0685"),Decimal("0.1400"),Decimal("0.0515"),Decimal("0.0630"),Decimal("0.1185"),Decimal("0.0515"),Decimal("0.0700"),Decimal("0.0090"),Decimal("0.0415"),Decimal("0.0355")]
    pooled=[Decimal("0.3000"),Decimal("0.0240"),Decimal("0.0700"),Decimal("0.1450"),Decimal("0.0520"),Decimal("0.0640"),Decimal("0.1250"),Decimal("0.0520"),Decimal("0.0750"),Decimal("0.0100"),Decimal("0.0450"),Decimal("0.0380")]
    # Normalize pooled exactly.
    s=sum(pooled); pooled=[x/s for x in pooled]
    def row(name,shares):
        return {
            "variant":name,"households":"100","weight_mass":"1000",
            **{f"division_{i:02d}_share":str(shares[i-1]) for i in range(1,13)},
            "food_share_div01_plus_div02":str(shares[0]+shares[1]),
            "ice_div01_plus_div02":str(Decimal(1)/(shares[0]+shares[1])),
            "food_share_div01_only":str(shares[0]),
            "ice_div01_only":str(Decimal(1)/shares[0]),
        }
    _write_csv(root/"national_reference_variants.csv",[
        row("equal_group_average_microdata",equal),
        row("pooled_low_very_low_microdata",pooled),
    ])
    regional=[]
    for idx,region in enumerate(REGIONS):
        for variant,base in (("equal_group_average",equal),("pooled_low_very_low",pooled)):
            bump=Decimal(idx)*Decimal("0.001")
            shares=list(base)
            shares[0]+=bump
            shares[-1]-=bump
            regional.append({
                "region_id":region,"variant":variant,"households":"50",
                **{f"division_{i:02d}_share":str(shares[i-1]) for i in range(1,13)},
                "food_share_div01_plus_div02":str(shares[0]+shares[1]),
                "ice_div01_plus_div02":str(Decimal(1)/(shares[0]+shares[1])),
            })
    _write_csv(root/"regional_reference_variants.csv",regional)
    (root/"division02_split_summary.json").write_text(json.dumps({
        "equal_group_average_alcohol_fraction_of_division02":"0.7",
        "pooled_alcohol_fraction_of_division02":"0.65",
        "cedlas_exact_food_fraction_of_division02":"1"
    }))
    (root/"receipt.json").write_text(json.dumps({"schema":"synthetic","outputs_are_aggregates_only":True}))
    return root


class CedlasChoiceAttributionTests(unittest.TestCase):
    def test_builds_all_choice_variants_without_respondent_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            provenance=_provenance(root/"prov")
            ipc=create_ipc_parent(root/"ipc")
            basket=create_official_basket_parent(root/"basket")
            release=build_choice_attribution(provenance,ipc,basket,root/"out")
            manifest=json.loads((release/"manifest.json").read_text())
            qa=json.loads((release/"qa.json").read_text())
            self.assertEqual(manifest["artifact_type"],"research.argentina-regional-baskets-cedlas-choice-attribution/v1")
            self.assertFalse(manifest["scientific_poverty_execution_performed"])
            self.assertFalse(qa["respondent_level_data_consumed"])
            self.assertEqual(qa["variant_count"],8)
            with (release/"variants.csv").open(newline="",encoding="utf-8") as h:
                variants=list(csv.DictReader(h))
            ids={r["variant_id"] for r in variants}
            self.assertIn("paper_exact",ids)
            self.assertIn("microdata_pooled_direct_alcohol_only",ids)
            with (release/"structures.csv").open(newline="",encoding="utf-8") as h:
                structures=list(csv.DictReader(h))
            paper=[r for r in structures if r["variant_id"]=="paper_exact" and r["region_id"]=="gran_buenos_aires"][0]
            alcohol=[r for r in structures if r["variant_id"]=="paper_vector_alcohol_only" and r["region_id"]=="gran_buenos_aires"][0]
            self.assertLess(Decimal(paper["ice_base"]),Decimal(alcohol["ice_base"]))


if __name__=="__main__":
    unittest.main()
