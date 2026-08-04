#!/usr/bin/env python3
"""Report deterministic cell provenance for the committed principal snapshot."""
from __future__ import annotations
import csv, json
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
status = json.loads((ROOT / "DATA_STATUS.json").read_text())
counts = Counter()
with (ROOT / status["artifact"]).open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
for row in rows:
    period = date.fromisoformat(row["Q"])
    label = "imputed" if period < date.fromisoformat(status["source_nominal_regional_series_begin"]) else "derived"
    if period >= date.fromisoformat(status["synthetic_tail_from"]): label = "synthetic"
    counts[label] += 2
print(json.dumps({"artifact": status["artifact"], "classification_basis": "DATA_STATUS boundaries and legacy transformation; no raw observation IDs are retained", "cells": len(rows) * 2, "status_counts": dict(sorted(counts.items())), "monetary_reference": "unresolved execution-month CPI identity", "methodology_version": "legacy-script@2f80dfb"}, indent=2))
