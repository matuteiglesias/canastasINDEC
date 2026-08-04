import csv, hashlib, json, subprocess, tempfile, unittest
from pathlib import Path
from basket_release.core import BuildError, build, load_price_release

ROOT=Path(__file__).parents[1]; FIX=ROOT/"fixtures/candidate_inputs"
class CandidateReleaseTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): subprocess.run(["python3","scripts/build_candidate_fixtures.py"],cwd=ROOT,check=True,capture_output=True)
 def test_complete_quarter_and_representative_date(self):
  with tempfile.TemporaryDirectory() as tmp:
   release,bundle=build(FIX/"source_lock.json",FIX/"price_release",Path(tmp)/"releases",Path(tmp)/"integration")
   with (release/"reference_2016_01_quarterly.csv").open(newline="") as h: q1=[r for r in csv.DictReader(h) if r["period"]=="2024-Q1"]
   self.assertEqual(12,len(q1)); self.assertEqual({"2024-02-15"},{r["representative_date"] for r in q1})
   with (bundle/"regional_baskets.csv").open(newline="") as h: self.assertEqual(6,len(list(csv.DictReader(h))))
 def test_projected_price_is_hard_failure(self):
  with tempfile.TemporaryDirectory() as tmp:
   copied=Path(tmp)/"price"; subprocess.run(["cp","-a",str(FIX/"price_release"),str(copied)],check=True)
   table=copied/"monthly_prices.csv"; table.write_text(table.read_text().replace("2024-02-01,410,observed","2024-02-01,410,projected"))
   manifest=json.loads((copied/"manifest.json").read_text()); manifest["files"]["monthly_prices.csv"]={"bytes":table.stat().st_size,"sha256":hashlib.sha256(table.read_bytes()).hexdigest()}; (copied/"manifest.json").write_text(json.dumps(manifest))
   with self.assertRaisesRegex(BuildError,"projected_price_used_for_core_conversion"): load_price_release(copied,{"2024-02-01"})
 def test_incomplete_requested_slice_fails(self):
  with tempfile.TemporaryDirectory() as tmp:
   lock=json.loads((FIX/"source_lock.json").read_text()); source=Path(tmp)/"445.1.csv"
   with Path(lock["snapshots"][0]["cache_file"]).open(newline="") as h: rows=list(csv.DictReader(h))
   rows[-1]["patagonia"]=""
   with source.open("w",newline="") as h: w=csv.DictWriter(h,rows[0]);w.writeheader();w.writerows(rows)
   snap=lock["snapshots"][0];snap.update(cache_file=str(source),byte_size=source.stat().st_size,sha256=hashlib.sha256(source.read_bytes()).hexdigest(),row_count=23)
   lock_path=Path(tmp)/"lock.json";lock_path.write_text(json.dumps(lock))
   with self.assertRaisesRegex(BuildError,"missing_required_region_or_measure_in_requested_slice"): build(lock_path,FIX/"price_release",Path(tmp)/"out",Path(tmp)/"integration")
if __name__=="__main__": unittest.main()
