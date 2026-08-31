import csv
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from basket_release.core import BuildError
from basket_release.v2_core import (
    MONETARY_REFERENCE_ID,
    PRICE_ARTIFACT,
    PRICE_METHOD,
    build_v2,
    load_v2_price_release,
    validate_v2_candidate,
)
from scripts.portable_source_lock import export_portable

ROOT=Path(__file__).parents[1]; FIX=ROOT/"fixtures/candidate_inputs"


class IpcV2HandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(["python3","scripts/build_candidate_fixtures.py"],cwd=ROOT,check=True,capture_output=True)

    def test_copied_conversion_release_builds_independent_basket_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            release,bundle=build_v2(FIX/"source_lock.json",FIX/"price_release_v2",Path(tmp)/"releases",Path(tmp)/"integration")
            result=validate_v2_candidate(release); integrated=validate_v2_candidate(bundle)
            manifest=json.loads((release/"manifest.json").read_text())
            self.assertEqual(manifest["monetary_reference_id"],MONETARY_REFERENCE_ID)
            self.assertEqual(manifest["price_dependency"]["artifact_type"],PRICE_ARTIFACT)
            self.assertEqual(manifest["price_dependency"]["method_id"],PRICE_METHOD)
            self.assertEqual(result["monthly_rows"],24)
            self.assertEqual(integrated["rows"],6)
            self.assertNotIn("IPC-Argentina",json.dumps(manifest))

    def test_thin_price_period_is_rejected_for_basket_conversion(self):
        with tempfile.TemporaryDirectory() as tmp:
            copied=Path(tmp)/"price"; shutil.copytree(FIX/"price_release_v2",copied)
            table=copied/"monthly_conversion_factors.csv"
            rows=list(csv.DictReader(table.open()))
            rows[-1]["approved_mode_eligible"]="false"; rows[-1]["coverage_class"]="thin_coverage"
            with table.open("w",newline="",encoding="utf-8") as handle:
                writer=csv.DictWriter(handle,fieldnames=rows[0],lineterminator="\n"); writer.writeheader(); writer.writerows(rows)
            manifest=json.loads((copied/"manifest.json").read_text())
            manifest["files"][0]={"path":table.name,"size":table.stat().st_size,"sha256":hashlib.sha256(table.read_bytes()).hexdigest()}
            (copied/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
            with self.assertRaisesRegex(BuildError,"price_period_not_approved_mode_eligible"):
                load_v2_price_release(copied,{"2024-03-01"})

    def test_v2_builder_consumes_relocated_portable_source_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); run=root/"original"/"run"; snapshots=run/"source_snapshots"; snapshots.mkdir(parents=True)
            lock=json.loads((FIX/"source_lock.json").read_text())
            for snap in lock["snapshots"]:
                source=FIX/f"{snap['distribution_id']}.csv"; target=snapshots/source.name; shutil.copy2(source,target); snap["cache_file"]=str(target.resolve())
            runtime=run/"source_lock.runtime.json"; runtime.write_text(json.dumps(lock))
            portable=run/"source_lock.json"; export_portable(runtime,portable)
            relocated=root/"relocated"; shutil.copytree(run,relocated)
            release,_=build_v2(relocated/"source_lock.json",FIX/"price_release_v2",root/"out")
            self.assertEqual(validate_v2_candidate(release)["monthly_rows"],24)


if __name__=="__main__": unittest.main()
