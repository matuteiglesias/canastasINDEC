#!/usr/bin/env python3
"""Source-owned, metadata-only WP03-A basket receipt. No science approval inference."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path

CONTRACT = "evidence:producer-run-receipt@1"
PRODUCER = "producer.github.basket-source-probe"
REPO = "matuteiglesias/canastasINDEC"
OUTPUT_TYPE = "publicdata.argentina-basket-candidate@1"
DURABILITY = "candidate_release"
STEP_NAMES = ("preflight", "source_acquire", "source_lock", "ipc_parent", "candidate_build",
              "candidate_qa", "packaging", "publication")
STATUS = {"success", "failure", "skipped", "cancelled", "unknown"}
DIGEST = re.compile(r"^[a-f0-9]{64}$")
IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
SOURCES = {"445.1": "indec_cba_regional_monthly", "446.1": "indec_cbt_regional_monthly"}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def valid_hash(s):
    return isinstance(s, str) and bool(DIGEST.fullmatch(s))


def valid_id(s):
    return isinstance(s, str) and bool(IDENTITY.fullmatch(s))


def check(condition, reason):
    if not condition:
        raise ValueError(reason)


def valid_time(s):
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d.tzinfo is not None and d.utcoffset().total_seconds() == 0
    except (TypeError, ValueError, AttributeError):
        return False


def verify_source(root: Path) -> tuple[list[str], str]:
    lock = read(root / "run/source_lock.json")
    check(lock.get("schema") == "regional-basket-source-lock/v1", "source_schema")
    snapshots = lock.get("snapshots", [])
    check(isinstance(snapshots, list) and len(snapshots) == 2, "source_count")
    observed = {}
    for snap in snapshots:
        dist = snap.get("distribution_id")
        check(dist in SOURCES and dist not in observed, "source_distribution")
        check(snap.get("source_id") == SOURCES[dist], "source_identity")
        digest = snap.get("sha256")
        check(valid_hash(digest), "source_digest")
        # The portable lock is verified against exact on-disk bytes by the preceding
        # basket-source-lock-check stage. Recheck here without printing source rows.
        rel = snap.get("cache_file", "")
        check(isinstance(rel, str) and not Path(rel).is_absolute()
              and ".." not in Path(rel).parts, "source_path")
        snapshot = (root / "run" / rel).resolve()
        check(snapshot.is_relative_to((root / "run").resolve()), "source_escape")
        check(snapshot.is_file() and sha(snapshot) == digest, "source_bytes")
        observed[dist] = digest
    check(set(observed) == set(SOURCES), "source_set")
    return [observed[d] for d in sorted(SOURCES)], sha(root / "run/source_lock.json")


def verify_parent(root: Path) -> tuple[str, str]:
    lock = read(root / "run/ipc_release_lock.json")
    check(lock.get("schema") == "ecosystem-consumer-lock/v1", "ipc_schema")
    check(lock.get("producer") == "matuteiglesias/IPC-Argentina", "ipc_producer")
    check(lock.get("status") == "approved", "ipc_unapproved")
    check(lock.get("artifact_type") == "research.argentina-monetary-conversion/v1", "ipc_artifact")
    rid, digest = lock.get("release_id"), lock.get("manifest_sha256")
    check(valid_id(rid) and valid_hash(digest), "ipc_identity")
    check(lock.get("release_tag") == "approved-" + rid, "ipc_tag")
    # Resolve via fixed trusted directory instead of reading arbitrary paths from lock.
    manifest = root / "run/ipc_release" / rid / "manifest.json"
    check(manifest.is_file() and sha(manifest) == digest, "ipc_parent_hash")
    data = read(manifest)
    check(data.get("release_id") == rid and data.get("status") == "approved", "ipc_manifest")
    check(data.get("artifact_type") == lock["artifact_type"], "ipc_manifest_type")
    return rid, digest


def verify_candidate(root: Path, source_shas: list[str], parent: tuple[str, str]) -> dict:
    discovery_path = root / "build/basket-publication/discovery.json"
    discovery = read(discovery_path)
    check(discovery.get("schema") == "ecosystem-release-discovery/v1", "discovery_schema")
    check(discovery.get("producer") == REPO, "discovery_producer")
    check(discovery.get("status") == "candidate", "discovery_not_candidate")
    check(discovery.get("artifact_type") == "research.argentina-regional-baskets/v1", "discovery_type")
    rid = discovery.get("release_id")
    check(valid_id(rid), "basket_release_id")
    gh = discovery.get("github_release", {})
    check(gh.get("tag") == "candidate-" + rid and gh.get("asset_name") == rid + ".zip",
          "basket_release_tag")
    check(valid_hash(gh.get("asset_sha256")) and valid_hash(gh.get("manifest_sha256")),
          "basket_release_hash")
    release = root / "artifacts/basket_releases" / rid
    manifest_file = release / "manifest.json"
    check(manifest_file.is_file() and sha(manifest_file) == gh["manifest_sha256"],
          "basket_manifest_hash")
    manifest = read(manifest_file)
    check(manifest.get("release_id") == rid and manifest.get("status") == "candidate",
          "basket_manifest_identity")
    check(manifest.get("artifact_type") == discovery["artifact_type"], "basket_manifest_type")
    check(manifest.get("source_snapshot_identities") == source_shas,
          "basket_source_mismatch")
    dep = manifest.get("price_dependency", {})
    check(dep.get("status") == "approved" and
          (dep.get("release_id"), dep.get("manifest_sha256")) == parent,
          "basket_ipc_parent_mismatch")
    check(discovery.get("price_dependency") == dep, "basket_discovery_parent_mismatch")
    check(read(release / "price_dependency_lock.json") == dep, "basket_parent_lock_mismatch")
    from basket_release.v2_core import validate_v2_candidate, _immutable_source_provenance
    check(read(release / "source_lock.json") ==
          _immutable_source_provenance(read(root / "run/source_lock.json")),
          "basket_source_provenance")
    validate_v2_candidate(release)
    qa = read(release / "qa.json")
    hard = qa.get("hard_failures")
    check(isinstance(hard, list) and not hard, "basket_qa_hard_failure")
    check(qa.get("result") in {"pass", "pass_with_warnings"}, "basket_qa_not_pass")
    if qa.get("result") == "pass_with_warnings":
        check(isinstance(qa.get("warnings"), list) and bool(qa["warnings"]),
              "basket_warning_mismatch")
    asset = root / "build/basket-publication" / gh["asset_name"]
    check(asset.is_file() and sha(asset) == gh["asset_sha256"], "basket_asset_mismatch")
    return {"release_id": rid, "tag": gh["tag"], "asset_sha256": gh["asset_sha256"],
            "discovery_sha256": sha(discovery_path),
            "source_sha256": source_shas, "parent_release_id": parent[0],
            "parent_manifest_sha256": parent[1], "qa_result": qa["result"]}


def verify_publication(root: Path, candidate: dict):
    proof = read(root / "build/basket-publication/publication_verified.json")
    check(proof.get("verification") == "byte_equivalent_prerelease", "publication_unverified")
    check(proof.get("is_prerelease") is True, "publication_not_prerelease")
    for key in ("tag", "release_id", "asset_sha256", "discovery_sha256"):
        check(proof.get(key) == candidate[key], "publication_" + key)


def build_receipt(root: Path, *, scheduler_run_id: str, attempt: str, event: str,
                  job_status: str, started_at: str, finished_at: str,
                  step_outcomes: dict[str, str]) -> dict:
    check(re.fullmatch(r"[0-9]+", scheduler_run_id) is not None, "run_id")
    check(re.fullmatch(r"[1-9][0-9]*", attempt) is not None, "attempt")
    check(valid_time(started_at) and valid_time(finished_at)
          and started_at <= finished_at, "time")
    check(event in {"schedule", "workflow_dispatch"}, "event")
    check(job_status in {"success", "failure", "cancelled"}, "job_status")
    check(set(step_outcomes) == set(STEP_NAMES) and set(step_outcomes.values()) <= STATUS,
          "step_outcomes")
    stages = {name: {"success": "success", "failure": "failed", "cancelled": "failed",
                     "skipped": "skipped", "unknown": "unknown"}[step_outcomes[name]]
              for name in STEP_NAMES}
    errors: list[str] = []
    candidate = None
    source = parent = None

    # Use only prior-step outcomes and verified files from THIS job, never
    # evidence left in the repository or assumptions from a green job.
    if stages["source_lock"] == "success":
        try:
            source = verify_source(root)
        except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError):
            stages["source_lock"] = "failed"
            errors.append("source_lock_invalid")
    if stages["ipc_parent"] == "success":
        try:
            parent = verify_parent(root)
        except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError):
            stages["ipc_parent"] = "failed"
            errors.append("ipc_parent_invalid")
    if source and parent and all(stages[n] == "success" for n in
                                 ("candidate_build", "candidate_qa", "packaging")):
        try:
            candidate = verify_candidate(root, source[0], parent)
        except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError):
            stages["candidate_qa"] = "failed"
            errors.append("basket_candidate_invalid")
    if stages["publication"] == "success":
        try:
            check(candidate is not None, "missing_candidate")
            verify_publication(root, candidate)
        except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError):
            stages["publication"] = "failed"
            errors.append("publication_proof_invalid")

    published = candidate is not None and stages["publication"] == "success" and all(
        stages[n] == "success" for n in STEP_NAMES)
    if published:
        output_state = "valid"
    elif any(v == "failed" for v in stages.values()):
        output_state = "invalid" if candidate else "partial"
    else:
        output_state = "partial" if candidate else "missing"

    fail = any(v == "failed" for v in stages.values()) or job_status != "success"
    unknown = any(v in {"skipped", "unknown"} for v in stages.values())
    execution = "failed" if job_status != "success" or any(
        stages[n] == "failed" for n in STEP_NAMES) else ("degraded" if unknown else "healthy")
    artifact_state = ("healthy" if published else
                      "failed" if candidate and stages["publication"] == "failed" else
                      "degraded" if candidate else "unknown")
    warnings = sorted(set(errors + (
        ["basket_qa_pass_with_warnings"] if candidate and candidate["qa_result"] == "pass_with_warnings" else []
    ) + (["workflow_incomplete"] if fail or unknown else [])))
    refs = [f"github-actions:{REPO}:{scheduler_run_id}:attempt:{attempt}"]
    if source:
        refs += [f"source-sha256:{digest}" for digest in source[0]]
    if parent:
        refs += [f"approved-ipc:{parent[0]}:sha256:{parent[1]}"]
    if candidate:
        refs += [f"candidate:{candidate['release_id']}:sha256:{candidate['asset_sha256']}"]
    return {
        "contract": CONTRACT,
        "run_id": f"github-actions:{REPO}:{scheduler_run_id}:{attempt}",
        "scheduler_run_id": scheduler_run_id,
        "producer_id": PRODUCER,
        "trigger": "schedule" if event == "schedule" else "manual",
        "started_at": started_at,
        "finished_at": finished_at,
        "stages": stages,
        "outputs": [{"type": OUTPUT_TYPE, "state": output_state,
                     "durability": DURABILITY,
                     "ref": f"https://github.com/{REPO}/releases/tag/{candidate['tag']}" if published else None}],
        "result": {
            "scheduler_state": "healthy",
            "execution_state": execution,
            "artifact_state": artifact_state,
            "terminal_state": "healthy" if published else ("failed" if stages["publication"] == "failed" else "unknown"),
            "authority_state": "canonical" if published else "hold",
        },
        "warnings": warnings,
        "evidence_refs": refs,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--scheduler-run-id", required=True)
    p.add_argument("--run-attempt", required=True)
    p.add_argument("--event-name", required=True)
    p.add_argument("--job-status", required=True)
    p.add_argument("--started-at", required=True)
    p.add_argument("--step-outcomes", required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    outcomes = json.loads(a.step_outcomes)
    payload = build_receipt(a.root, scheduler_run_id=a.scheduler_run_id,
                            attempt=a.run_attempt, event=a.event_name,
                            job_status=a.job_status, started_at=a.started_at,
                            finished_at=datetime.now(timezone.utc).strftime(UTC_FORMAT),
                            step_outcomes=outcomes)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"producer_id": PRODUCER, "run_id": payload["run_id"],
                      "output_state": payload["outputs"][0]["state"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
