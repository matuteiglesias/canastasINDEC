# Codex C1 — real ENGHo/Engel Phase A + Phase B commissioning

> Historical commissioning handoff. C1 was executed on 2026-09-28. Its first real Artifact A/B run clipped documented negative ENGHo sales and is retained as diagnostic evidence. The primary follow-up is now `docs/CODEX_C2_ENGEL_SIGNED_SALES_RERUN.md`.

This handoff executes the real-data path after the cloud implementation is merged.

It does **not** change Poverty, EPH, Census, geography, or Atlas repositories.

## Known commissioned upstream evidence

ENGHo M1:

- release ID: `engho-2017-2018-ff05578d65ae`
- expected local release root:
  `/home/matias/data/engho-2017-18/releases/engho-2017-2018-ff05578d65ae`
- adjudicated receipt:
  `/home/matias/data/engho-2017-18/commissioning/M1-commissioning-receipt.json`
- status: PASS with explicit 50-person-row custody warning

Regional IPC P1:

- release ID:
  `indec-ipc-regional-divisions-v1-2809f9093513-d84ce096c28f`
- known local release root:
  `/home/matias/repos/2025/IPC-Argentina/artifacts/indec_ipc_regional_divisions/indec-ipc-regional-divisions-v1-2809f9093513-d84ce096c28f`
- status: PASS
- coverage: six regions × twelve divisions, May 2018 through December 2025, no missing/duplicate cells

Do not refetch or rebuild either parent unless its immutable bytes are absent locally.

## C1.0 — synchronize and verify code

Work in the local `canastasINDEC` checkout.

```bash
git switch main
git pull --ff-only
make check
```

The main commit must contain both:

- `research.argentina-engel-reference-structure/v1`
- `research.argentina-regional-baskets-engel-sensitivity/v1`

## C1.1 — materialize real Artifact A

```bash
make engel-reference-build \
  ENGHO_RELEASE=/home/matias/data/engho-2017-18/releases/engho-2017-2018-ff05578d65ae \
  ENGHO_UPSTREAM_RECEIPT=/home/matias/data/engho-2017-18/commissioning/M1-commissioning-receipt.json \
  ENGEL_REFERENCE_OUTPUT=/home/matias/data/engho-2017-18/engel-reference
```

Capture the printed immutable Artifact-A release path as `REFERENCE_RELEASE`.

Then:

```bash
make engel-reference-check RELEASE_DIR="$REFERENCE_RELEASE"

make engel-reference-commission \
  RELEASE_DIR="$REFERENCE_RELEASE" \
  ENGEL_COMMISSION_OUTPUT=/home/matias/data/engho-2017-18/engel-phase-a-commissioning
```

Required structural result:

- G1 PASS
- G2 PASS
- G3 diagnostic
- G4 diagnostic
- no poverty/price-trajectory/CBT execution

The known M1 persons-table warning is lineage only. Do not filter people or modify ENGHo.

If G1/G2 fail, stop. Do not continue to Phase B.

## C1.2 — identify the exact official basket parent

Artifact B requires a local immutable release satisfying:

```text
artifact_type =
research.argentina-regional-baskets/v1

method_id =
research.argentina-regional-baskets/source-observed-plus-price-consensus-v2
```

and containing `observed_nominal_monthly.csv` with complete official CBA/CBT coverage for every region/month from 2018-05 through 2025-12.

Do **not** use:

- `data/CB_Reg_defl_m.csv`;
- a legacy-compatible basket release;
- a quarterly Poverty input child;
- a mutable source CSV in place of the immutable basket parent.

A bounded discovery helper is acceptable:

```bash
python3 - <<'PY'
import json
from pathlib import Path

for manifest_path in Path("artifacts").rglob("manifest.json"):
    try:
        manifest = json.loads(manifest_path.read_text())
    except Exception:
        continue
    if (
        manifest.get("artifact_type") == "research.argentina-regional-baskets/v1"
        and manifest.get("method_id")
        == "research.argentina-regional-baskets/source-observed-plus-price-consensus-v2"
        and (manifest_path.parent / "observed_nominal_monthly.csv").is_file()
    ):
        print(manifest_path.parent)
PY
```

If more than one candidate is found, validate each and choose by exact intended parent identity/provenance, not modification time.

If no valid complete parent exists, report `BLOCKED: official basket v2 parent unavailable` and stop. Do not substitute legacy evidence.

Set the resolved path as `OFFICIAL_BASKET_RELEASE`.

## C1.3 — build real Artifact B

Use the already commissioned P1 regional IPC release:

```bash
IPC_RELEASE=/home/matias/repos/2025/IPC-Argentina/artifacts/indec_ipc_regional_divisions/indec-ipc-regional-divisions-v1-2809f9093513-d84ce096c28f

make engel-paths-build \
  ENGEL_REFERENCE_RELEASE="$REFERENCE_RELEASE" \
  ENGEL_IPC_RELEASE="$IPC_RELEASE" \
  ENGEL_OFFICIAL_BASKET_RELEASE="$OFFICIAL_BASKET_RELEASE" \
  ENGEL_SENSITIVITY_OUTPUT=/home/matias/data/engho-2017-18/engel-sensitivity
```

Capture the printed immutable Artifact-B path as `SENSITIVITY_RELEASE`.

Then:

```bash
make engel-paths-check RELEASE_DIR="$SENSITIVITY_RELEASE"

make engel-paths-commission \
  RELEASE_DIR="$SENSITIVITY_RELEASE" \
  ENGEL_PATH_COMMISSION_OUTPUT=/home/matias/data/engho-2017-18/engel-phase-b-commissioning
```

## Acceptance

PASS requires:

### Parent gate P

- exact Artifact-A release/hash recorded;
- exact P1 IPC release/hash recorded;
- exact official basket release/hash recorded;
- six regions;
- twelve divisions;
- every month 2018-05 through 2025-12;
- no missing/duplicate IPC cell;
- no interpolation;
- no network retrieval by Canastas.

### Arithmetic gate A

For every region/month:

- `ICE_official = CBT_official / CBA_official`;
- May-2018 `ICE_engho17` equals Artifact-A regional base ICE;
- `full_factor = level_factor × trajectory_factor`;
- `CBT_level_only = CBT_official × level_factor`;
- `CBT_level_plus_trajectory = CBT_official × full_factor`;
- `CBT_engho17 = CBA_official × ICE_engho17`;
- direct and multiplicative full paths reconcile.

### Mapping gate M

- all twelve frozen division shares mapped;
- zero unpriced expenditure mass;
- COICOP01 priced directly;
- alcohol 021 uses COICOP02 and remains food;
- tobacco 022 uses COICOP02 and remains non-food;
- restaurants 111 use COICOP11 and remain non-food;
- shared-division approximations explicitly reported.

### G5

Produce:

- regional base level factors;
- regional trajectory minima/maxima;
- month of largest trajectory divergence by region;
- twelve-division contribution table for each largest-divergence month.

## Required final return

Return:

1. Artifact-A release path and ID;
2. Artifact-A commissioning directory and G1–G4 status;
3. exact official basket parent path and ID;
4. Artifact-B release path and ID;
5. Artifact-B commissioning directory;
6. regional base level factors;
7. regional trajectory ranges;
8. largest-divergence months;
9. any material mapping or regional-support warning;
10. PASS/BLOCKED.

Do not compute poverty rates.

Do not change any downstream repository.

Do not promote Artifact B to production.
