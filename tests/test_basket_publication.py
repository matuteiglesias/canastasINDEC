import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from basket_release.v2_core import build_v2
from scripts.package_v2_candidate import package

ROOT = Path(__file__).parents[1]
FIX = ROOT / "fixtures/candidate_inputs"


class BasketPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(
            ["python3", "scripts/build_candidate_fixtures.py"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )

    def test_validated_candidate_packages_deterministically(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release, _ = build_v2(
                FIX / "source_lock.json",
                FIX / "price_release_v2",
                root / "releases",
            )
            first = package(release, root / "a")
            second = package(release, root / "b")
            d1 = json.loads(Path(first["discovery"]).read_text())
            d2 = json.loads(Path(second["discovery"]).read_text())
            self.assertEqual(d1, d2)
            self.assertEqual(d1["status"], "candidate")
            self.assertEqual(d1["release_id"], release.name)
            self.assertEqual(
                d1["price_dependency"]["release_id"],
                json.loads((release / "manifest.json").read_text())[
                    "price_dependency"
                ]["release_id"],
            )
            self.assertEqual(
                Path(first["asset"]).read_bytes(),
                Path(second["asset"]).read_bytes(),
            )

    def test_retrieval_time_does_not_change_candidate_identity_or_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_release, _ = build_v2(
                FIX / "source_lock.json",
                FIX / "price_release_v2",
                root / "first-releases",
            )
            first = package(first_release, root / "first-package")

            lock = json.loads((FIX / "source_lock.json").read_text())
            for snapshot in lock["snapshots"]:
                snapshot["retrieved_at_utc"] = "2099-12-31T23:59:59Z"
            changed_lock = root / "timestamp-only-source-lock.json"
            changed_lock.write_text(json.dumps(lock))
            second_release, _ = build_v2(
                changed_lock,
                FIX / "price_release_v2",
                root / "second-releases",
            )
            second = package(second_release, root / "second-package")

            self.assertEqual(first_release.name, second_release.name)
            published_lock = json.loads(
                (first_release / "source_lock.json").read_text()
            )
            self.assertNotIn("retrieved_at_utc", published_lock["snapshots"][0])
            self.assertNotIn("cache_file", published_lock["snapshots"][0])
            self.assertNotIn("created_at", json.loads(Path(first["discovery"]).read_text()))
            self.assertEqual(
                Path(first["asset"]).read_bytes(),
                Path(second["asset"]).read_bytes(),
            )
            self.assertEqual(
                Path(first["discovery"]).read_bytes(),
                Path(second["discovery"]).read_bytes(),
            )

    def test_eligibility_and_substantive_provenance_change_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            approved_price = root / "approved-price"
            shutil.copytree(FIX / "price_release_v2", approved_price)
            price_manifest_path = approved_price / "manifest.json"
            price_manifest = json.loads(price_manifest_path.read_text())
            price_manifest["status"] = "approved"
            price_manifest_path.write_text(
                json.dumps(price_manifest, indent=2, sort_keys=True) + "\n"
            )

            rows_only, rows_bundle = build_v2(
                FIX / "source_lock.json",
                approved_price,
                root / "rows-only",
                root / "rows-only-integration",
            )
            approved_parent, approved_bundle = build_v2(
                FIX / "source_lock.json",
                approved_price,
                root / "approved-parent",
                root / "approved-parent-integration",
                require_price_status="approved",
            )
            self.assertNotEqual(rows_only.name, approved_parent.name)
            self.assertNotEqual(rows_bundle.name, approved_bundle.name)

            provenance_lock = json.loads((FIX / "source_lock.json").read_text())
            provenance_lock["snapshots"][0]["publisher_catalog"] = (
                "fixture://changed-provenance"
            )
            provenance_path = root / "changed-provenance-lock.json"
            provenance_path.write_text(json.dumps(provenance_lock))
            changed_provenance, _ = build_v2(
                provenance_path,
                approved_price,
                root / "changed-provenance",
            )
            self.assertNotEqual(rows_only.name, changed_provenance.name)


if __name__ == "__main__":
    unittest.main()
