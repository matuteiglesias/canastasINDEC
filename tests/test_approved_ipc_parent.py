import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from basket_release.core import BuildError
from basket_release.v2_core import load_v2_price_release

ROOT = Path(__file__).parents[1]
FIX = ROOT / "fixtures/candidate_inputs"


class ApprovedIPCParentModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(
            ["python3", "scripts/build_candidate_fixtures.py"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )

    def test_candidate_parent_is_rejected_when_approved_is_required(self):
        with self.assertRaisesRegex(
            BuildError,
            "price_release_status_mismatch",
        ):
            load_v2_price_release(
                FIX / "price_release_v2",
                {"2024-01-01"},
                require_price_status="approved",
            )

    def test_exact_approved_copy_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "price"
            shutil.copytree(FIX / "price_release_v2", copied)
            manifest_path = copied / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["status"] = "approved"
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n"
            )
            loaded, _, _, thin = load_v2_price_release(
                copied,
                {"2024-01-01"},
                require_price_status="approved",
            )
            self.assertEqual(loaded["status"], "approved")
            self.assertEqual(thin, [])


if __name__ == "__main__":
    unittest.main()
