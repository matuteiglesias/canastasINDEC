import json
import shutil
import tempfile
import unittest
from pathlib import Path

from basket_release.core import BuildError
from scripts.portable_source_lock import export_portable, validate_portable

ROOT = Path(__file__).parents[1]
FIX = ROOT / "fixtures/candidate_inputs"


class PortableSourceLockTests(unittest.TestCase):
    def _runtime_bundle(self, parent: Path) -> tuple[Path, Path]:
        run = parent / "run"
        snapshots = run / "source_snapshots"
        snapshots.mkdir(parents=True)
        lock = json.loads((FIX / "source_lock.json").read_text())
        for snap in lock["snapshots"]:
            source = FIX / f"{snap['distribution_id']}.csv"
            target = snapshots / source.name
            shutil.copy2(source, target)
            snap["cache_file"] = str(target.resolve())
        runtime = run / "source_lock.runtime.json"
        runtime.write_text(json.dumps(lock))
        return runtime, run / "source_lock.json"

    def test_exported_bundle_survives_relocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime, portable = self._runtime_bundle(root)
            exported = export_portable(runtime, portable)
            self.assertTrue(all(not Path(s["cache_file"]).is_absolute() for s in exported["snapshots"]))
            self.assertEqual(validate_portable(portable)["snapshots"], 2)
            relocated = root / "relocated"
            shutil.copytree(portable.parent, relocated)
            self.assertEqual(validate_portable(relocated / "source_lock.json")["snapshots"], 2)

    def test_relative_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime, portable = self._runtime_bundle(root)
            export_portable(runtime, portable)
            lock = json.loads(portable.read_text())
            lock["snapshots"][0]["cache_file"] = "../outside.csv"
            portable.write_text(json.dumps(lock))
            with self.assertRaisesRegex(BuildError, "unsafe_source_snapshot_path"):
                validate_portable(portable)


if __name__ == "__main__":
    unittest.main()
