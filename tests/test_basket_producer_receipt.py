"""WP03-A receipt invariants; metadata-only synthetic fixtures, no basket data."""
import copy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from emit_basket_producer_receipt import build_receipt, verify_source, verify_parent, verify_candidate, STEP_NAMES
from export_basket_producer_gcp import build_entry, ExportError

SHA = lambda s: hashlib.sha256(s).hexdigest()
RID = "regional-baskets-v2-price-fixture"
PARENT = "arg-monetary-conversion-v1-approved-fixture"
STEPS = {n: "success" for n in STEP_NAMES}


def write(path: Path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestWP03ABasket(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source_hashes = []
        sources = []
        for dist, source in (("445.1", "indec_cba_regional_monthly"),
                             ("446.1", "indec_cbt_regional_monthly")):
            path = self.root / "run/source_snapshots" / (dist + ".csv")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("synthetic:" + source).encode())
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.source_hashes.append(digest)
            sources.append({"distribution_id": dist, "source_id": source,
                            "cache_file": "source_snapshots/" + dist + ".csv",
                            "sha256": digest})
        write(self.root / "run/source_lock.json",
              {"schema": "regional-basket-source-lock/v1", "snapshots": sources})
        self.parent_sha = write(self.root / "run/ipc_release" / PARENT / "manifest.json",
                                {"release_id": PARENT, "status": "approved",
                                 "artifact_type": "research.argentina-monetary-conversion/v1"})
        write(self.root / "run/ipc_release_lock.json",
              {"schema": "ecosystem-consumer-lock/v1", "producer": "matuteiglesias/IPC-Argentina",
               "status": "approved", "artifact_type": "research.argentina-monetary-conversion/v1",
               "release_id": PARENT, "manifest_sha256": self.parent_sha,
               "release_tag": "approved-" + PARENT})
        self.dependency = {"release_id": PARENT, "manifest_sha256": self.parent_sha,
                           "status": "approved"}
        base = self.root / "artifacts/basket_releases" / RID
        write(base / "price_dependency_lock.json", self.dependency)
        from basket_release.v2_core import _immutable_source_provenance
        write(base / "source_lock.json", _immutable_source_provenance(
            json.loads((self.root / "run/source_lock.json").read_text())))
        write(base / "qa.json", {"result": "pass_with_warnings", "warnings": ["fixture-warning"],
                                "hard_failures": []})
        self.manifest_sha = write(base / "manifest.json", {
            "release_id": RID, "status": "candidate",
            "artifact_type": "research.argentina-regional-baskets/v1",
            "price_dependency": self.dependency,
            "source_snapshot_identities": self.source_hashes})
        asset = self.root / "build/basket-publication" / (RID + ".zip")
        asset.parent.mkdir(parents=True, exist_ok=True)
        asset.write_bytes(b"synthetic-archive-no-data")
        self.asset_sha = hashlib.sha256(asset.read_bytes()).hexdigest()
        self.discovery_sha = write(asset.parent / "discovery.json", {
            "schema": "ecosystem-release-discovery/v1",
            "producer": "matuteiglesias/canastasINDEC",
            "status": "candidate", "release_id": RID,
            "artifact_type": "research.argentina-regional-baskets/v1",
            "price_dependency": self.dependency,
            "github_release": {
                "tag": "candidate-" + RID, "asset_name": RID + ".zip",
                "asset_sha256": self.asset_sha, "manifest_sha256": self.manifest_sha}})
        self.proof = {"verification": "byte_equivalent_prerelease", "is_prerelease": True,
                      "tag": "candidate-" + RID, "release_id": RID,
                      "asset_sha256": self.asset_sha,
                      "discovery_sha256": self.discovery_sha}
        write(asset.parent / "publication_verified.json", self.proof)
        # The independent scientific validator is tested by the repository's
        # own v2 tests; receipt fixtures test its invocation and boundary.
        self.validator = patch("basket_release.v2_core.validate_v2_candidate")
        self.mock_validator = self.validator.start()
        self.addCleanup(self.validator.stop)

    def receipt(self, **overrides):
        kw = dict(scheduler_run_id="12345", attempt="1", event="schedule",
                  job_status="success", started_at="2026-10-25T01:00:00Z",
                  finished_at="2026-10-25T01:01:00Z", step_outcomes=dict(STEPS))
        kw.update(overrides)
        return build_receipt(self.root, **kw)

    def test_verified_candidate_warnings_are_not_failure(self):
        r = self.receipt()
        self.assertEqual(r["outputs"][0]["state"], "valid")
        self.assertEqual(r["result"]["artifact_state"], "healthy")
        self.assertEqual(r["result"]["authority_state"], "canonical")
        self.assertIn("basket_qa_pass_with_warnings", r["warnings"])
        self.mock_validator.assert_called()
        self.assertEqual(build_entry(r, "12345", "1")["severity"], "INFO")

    def test_wrong_parent_or_unapproved_parent(self):
        p = self.root / "run/ipc_release_lock.json"
        d = json.loads(p.read_text())
        d["status"] = "candidate"
        write(p, d)
        r = self.receipt()
        self.assertIn("ipc_parent_invalid", r["warnings"])
        self.assertNotEqual(r["outputs"][0]["state"], "valid")
        d["status"] = "approved"
        d["manifest_sha256"] = "a" * 64
        write(p, d)
        self.assertNotEqual(self.receipt()["outputs"][0]["state"], "valid")

    def test_hard_qa_failure_and_source_drift(self):
        path = self.root / "artifacts/basket_releases" / RID / "qa.json"
        write(path, {"result": "fail", "hard_failures": ["bad"], "warnings": []})
        self.assertIn("basket_candidate_invalid", self.receipt()["warnings"])
        (self.root / "run/source_snapshots/445.1.csv").write_bytes(b"tampered")
        r = self.receipt()
        self.assertIn("source_lock_invalid", r["warnings"])

    def test_asset_discrepancy_or_publication_missing(self):
        path = self.root / "build/basket-publication" / (RID + ".zip")
        path.write_bytes(b"different")
        self.assertIn("basket_candidate_invalid", self.receipt()["warnings"])
        path.write_bytes(b"synthetic-archive-no-data")
        (self.root / "build/basket-publication/publication_verified.json").unlink()
        self.assertIn("publication_proof_invalid", self.receipt()["warnings"])

    def test_early_failure_no_false_success(self):
        steps = dict(STEPS)
        for key in ("source_acquire", "source_lock", "ipc_parent", "candidate_build",
                    "candidate_qa", "packaging", "publication"):
            steps[key] = "skipped"
        steps["preflight"] = "failure"
        r = self.receipt(step_outcomes=steps, job_status="failure")
        self.assertEqual(r["outputs"][0]["state"], "partial")
        self.assertEqual(r["result"]["artifact_state"], "unknown")
        self.assertEqual(r["result"]["terminal_state"], "unknown")

    def test_transport_is_separate_and_replay_stable(self):
        r = self.receipt()
        a = build_entry(r, "12345", "1")
        b = build_entry(copy.deepcopy(r), "12345", "1")
        self.assertEqual(a["insertId"], b["insertId"])
        different = self.receipt(attempt="2")
        self.assertNotEqual(a["insertId"], build_entry(different, "12345", "2")["insertId"])
        with self.assertRaises(ExportError):
            build_entry(r, "12345", "2")

    def test_privacy_fail_closed(self):
        r = self.receipt()
        r["warnings"] = ["password=mysecret"]
        with self.assertRaises(ExportError):
            build_entry(r, "12345", "1")
        r = self.receipt()
        r["private_table"] = "raw"
        with self.assertRaises(ExportError):
            build_entry(r, "12345", "1")
        r = self.receipt()
        r["evidence_refs"].append("/home/user/dataset.csv")
        with self.assertRaises(ExportError):
            build_entry(r, "12345", "1")

    def test_step_success_without_proof_fails_closed(self):
        self.proof["is_prerelease"] = False
        write(self.root / "build/basket-publication/publication_verified.json", self.proof)
        r = self.receipt()
        self.assertEqual(r["stages"]["publication"], "failed")
        self.assertNotEqual(r["outputs"][0]["state"], "valid")

    def test_parent_manifest_drift(self):
        write(self.root / "run/ipc_release" / PARENT / "manifest.json",
              {"release_id": PARENT, "status": "approved", "artifact_type": "changed"})
        self.assertEqual(self.receipt()["stages"]["ipc_parent"], "failed")


if __name__ == "__main__":
    unittest.main()
