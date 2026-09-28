# Codex C2 — one bounded signed-sales ENGHo rerun

Run this only after the signed-sales review patch is merged to `main`.

## Purpose

Replace the temporary clipped-sales primary candidate with the source-semantic ENGHo accounting:

```text
negative_expenditure_policy = preserve_signed_sales
```

Do not alter any other scientific choice.

Keep fixed:

- ENGHo parent `engho-2017-2018-ff05578d65ae`;
- national weighted p29-p48 reference population;
- food = COICOP01 + alcoholic beverages 021;
- tobacco non-food;
- restaurants non-food;
- May 2018 base;
- regional IPC release `indec-ipc-regional-divisions-v1-2809f9093513-d84ce096c28f`;
- official basket parent `regional-baskets-v2-price-fb884d2b770bbe6f`;
- all Phase-B price mappings and arithmetic.

The previous clipped releases are diagnostics and must not be deleted:

```text
OLD_A=/home/matias/data/engho-2017-18/engel-reference/engel-reference-83557070694b9306
OLD_B=/home/matias/data/engho-2017-18/engel-sensitivity/engel-sensitivity-10ec46dfd65c0d21
```

## 1. Synchronize and test

```bash
cd /home/matias/repos/2025/canastasINDEC
git switch main
git pull --ff-only
make check
```

Confirm the active Artifact-A method is:

```text
research.argentina-engel-reference-structure/engho-2017-18-p29-p48-signed-sales-v2
```

## 2. Rebuild Artifact A

```bash
make engel-reference-build \
  ENGHO_RELEASE=/home/matias/data/engho-2017-18/releases/engho-2017-2018-ff05578d65ae \
  ENGHO_UPSTREAM_RECEIPT=/home/matias/data/engho-2017-18/commissioning/M1-commissioning-receipt.json \
  ENGEL_REFERENCE_OUTPUT=/home/matias/data/engho-2017-18/engel-reference
```

Capture the new release as `NEW_A`.

```bash
make engel-reference-check RELEASE_DIR="$NEW_A"
make engel-reference-commission \
  RELEASE_DIR="$NEW_A" \
  ENGEL_COMMISSION_OUTPUT=/home/matias/data/engho-2017-18/engel-phase-a-commissioning-signed-sales
```

Required:

- G1 PASS;
- G2 PASS;
- G3/G4 diagnostic;
- `negative_expenditure_policy=preserve_signed_sales`;
- the same 1,000 negative source rows remain visible;
- zero poverty execution.

## 3. Rebuild Artifact B

```bash
IPC_RELEASE=/home/matias/repos/2025/IPC-Argentina/artifacts/indec_ipc_regional_divisions/indec-ipc-regional-divisions-v1-2809f9093513-d84ce096c28f
OFFICIAL_BASKET_RELEASE=/home/matias/data/poverty-backfill-2024-2025/baskets/releases/regional-baskets-v2-price-fb884d2b770bbe6f

make engel-paths-build \
  ENGEL_REFERENCE_RELEASE="$NEW_A" \
  ENGEL_IPC_RELEASE="$IPC_RELEASE" \
  ENGEL_OFFICIAL_BASKET_RELEASE="$OFFICIAL_BASKET_RELEASE" \
  ENGEL_SENSITIVITY_OUTPUT=/home/matias/data/engho-2017-18/engel-sensitivity
```

Capture as `NEW_B`.

```bash
make engel-paths-check RELEASE_DIR="$NEW_B"
make engel-paths-commission \
  RELEASE_DIR="$NEW_B" \
  ENGEL_PATH_COMMISSION_OUTPUT=/home/matias/data/engho-2017-18/engel-phase-b-commissioning-signed-sales
```

Required: P PASS, A PASS, M PASS with documented approximations, G5 PASS.

## 4. Compare signed-sales primary against clipped diagnostic

Do not compare poverty. Compare only Artifact-A structure and Artifact-B threshold paths.

Produce:

```text
/home/matias/data/engho-2017-18/engel-signed-sales-delta/
    artifact_a_region_delta.csv
    artifact_b_level_trajectory_delta.csv
    summary.json
```

At minimum report by region:

- old/new food share;
- old/new base ICE;
- absolute and percentage change in ICE;
- old/new level factor;
- change in level factor;
- old/new trajectory min/max;
- whether the largest-divergence month changes.

Also report:

- signed total of the 1,000 negative rows;
- absolute negative-sales total;
- purchases-only counterfactual total;
- negative-sales share of that counterfactual;
- the same quantities restricted to selected p29-p48 households;
- exact IPC manifest SHA-256 used by Artifact B.

This is the scientific materiality check for the convention.

## Acceptance

PASS only if:

1. all original structural gates still pass;
2. signed sales are preserved rather than clipped;
3. article fallback remains exactly two rows unless source evidence explains otherwise;
4. all parent identities remain unchanged except the new Artifact-A identity and derived Artifact-B identity;
5. the signed-sales delta is finite and fully explained by the accounting change;
6. no estimator parameter is tuned against CEDLAS or any other publication.

If any gate fails, stop and return BLOCKED with the exact failure.

## Return

Return the new Artifact-A ID + manifest SHA, new Artifact-B ID + manifest SHA, exact IPC manifest SHA, gate statuses, national/regional food shares and ICE, signed-vs-clipped deltas, G5 trajectory ranges, and PASS/BLOCKED.

Do not touch `indice-pobreza-UBA`, income modeling, welfare inference, Census, geography, or the public Atlas.
