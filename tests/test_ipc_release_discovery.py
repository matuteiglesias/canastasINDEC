import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from basket_release.ipc_discovery import materialize, resolve_locked_release
from basket_release.v2_core import MONETARY_REFERENCE_ID, PRICE_ARTIFACT, PRICE_METHOD


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def archive(release_id, manifest):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zf:
        zf.writestr(f"{release_id}/manifest.json", json.dumps(manifest, sort_keys=True).encode())
        zf.writestr(f"{release_id}/monthly_conversion_factors.csv", b"period,consensus_index\n2016-01-01,100\n")
    return out.getvalue()


class IPCReleaseDiscoveryTests(unittest.TestCase):
    def fixture(self):
        rid = "arg-monetary-conversion-v1-fixture"
        manifest = {
            "schema": "research-artifact-manifest/v1",
            "artifact_type": PRICE_ARTIFACT,
            "release_id": rid,
            "status": "candidate",
            "method_id": PRICE_METHOD,
            "monetary_reference_id": MONETARY_REFERENCE_ID,
        }
        raw_zip = archive(rid, manifest)
        manifest_raw = json.dumps(manifest, sort_keys=True).encode()
        tag = f"candidate-{rid}"
        discovery = {
            "schema": "ecosystem-release-discovery/v1",
            "producer": "matuteiglesias/IPC-Argentina",
            "artifact_type": PRICE_ARTIFACT,
            "release_id": rid,
            "status": "candidate",
            "method_id": PRICE_METHOD,
            "monetary_reference_id": MONETARY_REFERENCE_ID,
            "github_release": {
                "tag": tag,
                "asset_name": f"{rid}.zip",
                "asset_sha256": sha(raw_zip),
                "manifest_sha256": sha(manifest_raw),
            },
        }
        urls = {
            "fixture://discovery": (json.dumps(discovery).encode()),
            "fixture://asset": raw_zip,
        }
        release = {
            "url": "fixture://release-api",
            "tag_name": tag,
            "prerelease": True,
            "draft": False,
            "published_at": "2026-08-31T00:00:00Z",
            "assets": [
                {"name": "discovery.json", "browser_download_url": "fixture://discovery"},
                {"name": f"{rid}.zip", "browser_download_url": "fixture://asset"},
            ],
        }
        return rid, manifest, release, urls

    def test_materializes_exact_release_and_writes_relocatable_lock(self):
        rid, _, release, urls = self.fixture()
        def fetch(url, token=None):
            return urls[url]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock_path = root / "run/ipc_release_lock.json"
            lock = materialize(root / "run/ipc_release", lock_path, releases=[release], fetch_bytes=fetch)
            self.assertEqual(lock["release_id"], rid)
            resolved = resolve_locked_release(lock_path)
            self.assertEqual(resolved, root / "run/ipc_release" / rid)
            self.assertTrue((resolved / "manifest.json").is_file())
            self.assertNotIn(str(root.resolve()), lock_path.read_text())

    def test_rejects_asset_checksum_mismatch(self):
        _, _, release, urls = self.fixture()
        urls["fixture://asset"] += b"tamper"
        def fetch(url, token=None):
            return urls[url]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "asset_checksum_mismatch"):
                materialize(Path(tmp) / "out", Path(tmp) / "lock.json", releases=[release], fetch_bytes=fetch)

    def test_rejects_manifest_discovery_mismatch(self):
        _, _, release, urls = self.fixture()
        discovery = json.loads(urls["fixture://discovery"])
        discovery["monetary_reference_id"] = "wrong"
        urls["fixture://discovery"] = json.dumps(discovery).encode()
        def fetch(url, token=None):
            return urls[url]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "incompatible_discovery_monetary_reference"):
                materialize(Path(tmp) / "out", Path(tmp) / "lock.json", releases=[release], fetch_bytes=fetch)


if __name__ == "__main__":
    unittest.main()
