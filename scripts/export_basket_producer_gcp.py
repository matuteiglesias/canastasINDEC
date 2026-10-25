#!/usr/bin/env python3
"""WP03-A metadata-only, deterministic Cloud Logging exporter (keyless OIDC)."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from emit_basket_producer_receipt import (
    CONTRACT, DURABILITY, OUTPUT_TYPE, PRODUCER, REPO, STEP_NAMES, valid_time,
)

PROJECT = "estate-observability-510700"
LOG = "estate-producer-run"
ENDPOINT = "https://logging.googleapis.com/v2/entries:write"
ALLOWED_WARNINGS = {
    "source_lock_invalid", "ipc_parent_invalid", "basket_candidate_invalid",
    "publication_proof_invalid", "basket_qa_pass_with_warnings", "workflow_incomplete",
}
STAGE_VALUES = {"success", "failed", "skipped", "not_applicable", "unknown"}
RESULT_VALUES = {
    "scheduler_state": {"healthy", "degraded", "failed", "unknown", "not_applicable"},
    "execution_state": {"healthy", "degraded", "failed", "unknown", "not_applicable"},
    "artifact_state": {"healthy", "degraded", "failed", "stale", "unknown", "not_applicable"},
    "terminal_state": {"healthy", "degraded", "failed", "unknown", "not_applicable"},
    "authority_state": {"canonical", "candidate", "duplicate", "superseded", "hold", "unknown"},
}
RECEIPT_KEYS = {"contract", "run_id", "scheduler_run_id", "producer_id",
                "trigger", "started_at", "finished_at", "stages", "outputs",
                "result", "warnings", "evidence_refs"}


class ExportError(ValueError):
    pass


def require(condition: bool, message: str):
    if not condition:
        raise ExportError(message)


def canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate(receipt: dict[str, Any], run_id: str, attempt: str):
    require(isinstance(receipt, dict) and set(receipt) == RECEIPT_KEYS,
            "unknown receipt fields")
    require(bool(re.fullmatch(r"[0-9]+", run_id)) and
            bool(re.fullmatch(r"[1-9][0-9]*", attempt)), "invalid run identity")
    require(receipt["contract"] == CONTRACT and receipt["producer_id"] == PRODUCER,
            "wrong producer")
    require(receipt["scheduler_run_id"] == run_id and
            receipt["run_id"] == f"github-actions:{REPO}:{run_id}:{attempt}",
            "run identity mismatch")
    require(receipt["trigger"] in {"schedule", "manual"}, "invalid trigger")
    require(valid_time(receipt["started_at"]) and valid_time(receipt["finished_at"])
            and receipt["started_at"] <= receipt["finished_at"], "invalid timestamps")
    stages = receipt["stages"]
    require(isinstance(stages, dict) and set(stages) == set(STEP_NAMES)
            and set(stages.values()) <= STAGE_VALUES, "invalid stages")
    results = receipt["result"]
    require(isinstance(results, dict) and set(results) == set(RESULT_VALUES)
            and all(results[k] in vals for k, vals in RESULT_VALUES.items()),
            "invalid result axes")
    outputs = receipt["outputs"]
    require(isinstance(outputs, list) and len(outputs) == 1, "invalid outputs")
    output = outputs[0]
    require(isinstance(output, dict) and set(output) == {"type", "state", "durability", "ref"},
            "unrecognized output fields")
    require(output["type"] == OUTPUT_TYPE and output["durability"] == DURABILITY,
            "incorrect output contract")
    require(output["state"] in {"valid", "invalid", "partial", "missing", "unknown"},
            "invalid output state")
    published = output["state"] == "valid"
    require(not published or (
        all(v == "success" for v in stages.values()) and
        results["artifact_state"] == "healthy" and
        results["terminal_state"] == "healthy" and
        results["authority_state"] == "canonical"), "unverified success")
    require(output["ref"] is None if not published else bool(re.fullmatch(
        rf"https://github\.com/{REPO}/releases/tag/candidate-[A-Za-z0-9._-]{{1,120}}",
        output["ref"])), "invalid release reference")
    warnings = receipt["warnings"]
    require(isinstance(warnings, list) and all(w in ALLOWED_WARNINGS for w in warnings),
            "unsafe warnings")
    refs = receipt["evidence_refs"]
    require(isinstance(refs, list) and 1 <= len(refs) <= 6
            and refs[0] == f"github-actions:{REPO}:{run_id}:attempt:{attempt}",
            "invalid evidence refs")
    patterns = (r"source-sha256:[0-9a-f]{64}",
                r"approved-ipc:[A-Za-z0-9._-]{1,120}:sha256:[0-9a-f]{64}",
                r"candidate:[A-Za-z0-9._-]{1,120}:sha256:[0-9a-f]{64}")
    require(all(isinstance(ref, str) and any(re.fullmatch(p, ref) for p in patterns)
                for ref in refs[1:]), "unsafe evidence reference")
    # No additional fields, free-form source warnings, log paths, commands or data rows.
    raw = canonical_json(receipt).lower()
    require(not any(v in raw for v in ("/home/", "/users/", "\\users\\",
        '"token"', '"secret"', '"password"', '"environment"', '"cwd"', '"command"',
        '"source_rows"', '"raw_data"', '"api_key"', '"credential"')),
        "private data detected")


def build_entry(receipt: dict[str, Any], run_id: str, attempt: str) -> dict[str, Any]:
    validate(receipt, run_id, attempt)
    digest = hashlib.sha256(canonical_json(receipt).encode("utf-8")).hexdigest()
    identity = {"producer_id": PRODUCER, "run_id": receipt["run_id"],
                "receipt_sha256": digest}
    insert_id = hashlib.sha256(canonical_json(identity).encode("utf-8")).hexdigest()
    axes = receipt["result"]
    health = {axes["execution_state"], axes["artifact_state"], axes["terminal_state"]}
    severity = "ERROR" if "failed" in health else (
        "WARNING" if health & {"unknown", "degraded"} else "INFO")
    return {
        "logName": f"projects/{PROJECT}/logs/{LOG}",
        "resource": {"type": "global", "labels": {"project_id": PROJECT}},
        "timestamp": receipt["finished_at"], "severity": severity,
        "insertId": insert_id,
        "labels": {"producer_id": PRODUCER, "source_contract": CONTRACT,
                   "receipt_sha256": digest},
        "jsonPayload": {
            "contract": CONTRACT, "receipt": receipt, "receipt_sha256": digest,
            "logical_receipt_id": PRODUCER + ":" + receipt["run_id"],
            "producer": {"producer_id": PRODUCER,
                         "owner": "repo.canastasINDEC",
                         "scheduler_kind": "github_actions",
                         "observation_mode": "semantic_receipt",
                         "authority_state": axes["authority_state"]},
        },
    }


def write_entry(session, entry: dict, dry_run: bool):
    resp = session.post(
        ENDPOINT, params={"dryRun": "true"} if dry_run else None,
        json={"logName": entry["logName"], "resource": entry["resource"],
              "entries": [entry], "partialSuccess": False}, timeout=30,
    )
    if not resp.ok:
        raise ExportError(f"Cloud Logging HTTP {resp.status_code}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--scheduler-run-id", required=True)
    parser.add_argument("--run-attempt", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    try:
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        entry = build_entry(receipt, args.scheduler_run_id, args.run_attempt)
        if args.write:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
            credentials, _ = google.auth.default(scopes=[
                "https://www.googleapis.com/auth/logging.write"])
            session = AuthorizedSession(credentials)
            write_entry(session, entry, dry_run=True)
            write_entry(session, entry, dry_run=False)
        print(json.dumps({"producer_id": PRODUCER, "insert_id": entry["insertId"],
                          "receipt_sha256": entry["labels"]["receipt_sha256"],
                          "mode": "exported" if args.write else "validated"}, sort_keys=True))
        return 0
    except (ExportError, OSError, ValueError, KeyError, TypeError, ImportError):
        print("basket receipt export failed validation or transport", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
