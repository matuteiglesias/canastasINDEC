import json
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


if __name__ == "__main__":
    unittest.main()
