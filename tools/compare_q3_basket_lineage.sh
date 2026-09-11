#!/usr/bin/env bash
set -euo pipefail

# Run from the canastasINDEC repository root.
ACCEPTED="${ACCEPTED:-data/CB_Reg_defl_Q.csv}"
PERIOD="${PERIOD:-2024-Q3}"
EXPECTED_ACCEPTED_SHA="${EXPECTED_ACCEPTED_SHA:-114efe353c98bd875bfef882d13a636df32ab92c930c985fe967062d6d0cb002}"
OUT="${OUT:-/tmp/canastas-q3-lineage-report.json}"

if [[ ! -f "$ACCEPTED" ]]; then
  echo "accepted file not found: $ACCEPTED" >&2
  exit 2
fi

observed=$(sha256sum "$ACCEPTED" | awk '{print $1}')
if [[ "$observed" != "$EXPECTED_ACCEPTED_SHA" ]]; then
  echo "refusing to compare: accepted artifact drifted" >&2
  echo "expected: $EXPECTED_ACCEPTED_SHA" >&2
  echo "observed: $observed" >&2
  exit 2
fi

candidate=$(mktemp --suffix=.csv)
trap 'rm -f "$candidate"' EXIT

git show origin/main:data/CB_Reg_defl_Q.csv > "$candidate"
candidate_sha=$(sha256sum "$candidate" | awk '{print $1}')

echo "accepted_sha=$observed"
echo "origin_main_candidate_sha=$candidate_sha"

PYTHONPATH=. python3 -m basket_release.lineage_compare \
  --accepted "$ACCEPTED" \
  --candidate "$candidate" \
  --period "$PERIOD" \
  --accepted-sha "$EXPECTED_ACCEPTED_SHA" \
  --output "$OUT"

echo "report=$OUT"
