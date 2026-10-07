import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from basket_release.ipc_discovery import materialize
from basket_release.v2_core import (
    MONETARY_REFERENCE_ID,
    PRICE_ARTIFACT,
    PRICE_METHOD,
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def archive(release_id: str, manifest: dict) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zf:
        zf.writestr(
            f"{release_id}/manifest.json",
            json.dumps(manifest, sort_keys=True).encode(),
        )
        zf.writestr(
            f"{release_id}/monthly_conversion_factors.csv",
            b"period,consensus_index\n2016-01-01,100\n",
        )
    return out.getvalue()


def fixture(status: str):
    rid = f"arg-monetary-conversion-v1-{status}-fixture"
    manifest = {
        "schema": "research-artifact-manifest/v1",
        "artifact_type": PRICE_ARTIFACT,
        "release_id": rid,
        "status": status,
        "method_id": PRICE_METHOD,
        "monetary_reference_id": MONETARY_REFERENCE_ID,
    }
    raw_zip = archive(rid, manifest)
    manifest_raw = json.dumps(manifest, sort_keys=True).encode()
    tag = f"{status}-{rid}"
    discovery = {
        "schema": "ecosystem-release-discovery/v1",
        "producer": "matuteiglesias/IPC-Argentina",
        "artifact_type": PRICE_ARTIFACT,
        "release_id": rid,
        "status": status,
        "method_id": PRICE_METHOD,
        "monetary_reference_id": MONETARY_REFERENCE_ID,
        "github_release": {
            "tag": tag,
            "asset_name": f"{rid}.zip",
            "asset_sha256": sha(raw_zip),
            "manifest_sha256": sha(manifest_raw),
        },
    }
    prefix = f"fixture://{status}"
    urls = {
        f"{prefix}/discovery": json.dumps(discovery).encode(),
        f"{prefix}/asset": raw_zip,
    }
    release = {
        "url": f"{prefix}/release-api",
        "tag_name": tag,
        "prerelease": status == "candidate",
        "draft": False,
        "published_at": "2026-10-07T00:00:00Z",
        "assets": [
            {
                "name": "discovery.json",
                "browser_download_url": f"{prefix}/discovery",
            },
            {
                "name": f"{rid}.zip",
                "browser_download_url": f"{prefix}/asset",
            },
        ],
    }
    return rid, release, urls


class ApprovedIPCDiscoveryTests(unittest.TestCase):
    def test_materializes_approved_release_when_required(self):
        rid, release, urls = fixture("approved")

        def fetch(url, token=None):
            return urls[url]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock = materialize(
                root / "release",
                root / "lock.json",
                releases=[release],
                fetch_bytes=fetch,
                required_status="approved",
            )
            self.assertEqual(lock["release_id"], rid)
            self.assertEqual(lock["status"], "approved")

    def test_required_approved_skips_newer_candidate(self):
        _, candidate, candidate_urls = fixture("candidate")
        approved_id, approved, approved_urls = fixture("approved")
        urls = {**candidate_urls, **approved_urls}

        def fetch(url, token=None):
            return urls[url]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock = materialize(
                root / "release",
                root / "lock.json",
                releases=[candidate, approved],
                fetch_bytes=fetch,
                required_status="approved",
            )
            self.assertEqual(lock["release_id"], approved_id)
            self.assertEqual(lock["status"], "approved")

    def test_approved_release_cannot_be_marked_prerelease(self):
        _, release, urls = fixture("approved")
        release["prerelease"] = True

        def fetch(url, token=None):
            return urls[url]

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(
                ValueError,
                "approved_release_must_not_be_prerelease",
            ):
                materialize(
                    Path(tmp) / "release",
                    Path(tmp) / "lock.json",
                    releases=[release],
                    fetch_bytes=fetch,
                    required_status="approved",
                )


if __name__ == "__main__":
    unittest.main()
