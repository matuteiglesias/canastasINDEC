# Canastas regionales INDEC — poverty-threshold input producer

`canastasINDEC` is the poverty ecosystem's producer for governed **CBA/CBT threshold inputs** derived from exact official regional basket sources. It also hosts a separate experimental ENGHo/Engel research surface; that surface does not change the incumbent basket candidate or Poverty-input semantics.

> **Current state:** the modern v2 basket candidate path remains the current threshold-input authority. The ENGHo/Engel research surface is now commissioned with signed-sales accounting. The first clipped-sales real run is retained as a diagnostic sensitivity; the primary candidate/diagnostic pair is Artifact A `engel-reference-080d0d1bdf25fd2f` and Artifact B `engel-sensitivity-95d0632b226c375d`. No Poverty calculation is authorized by these upstream artifacts.

## Modern threshold path

```text
official regional CBA/CBT distributions
        ↓ exact source lock
observed nominal six-region evidence
        +
immutable IPC monetary-conversion parent
        ↓
governed basket v2 candidate
        ↓
quarter-specific Poverty threshold input
        ↓
indice-pobreza-UBA
```

The source-native threshold areas are the six governed basket-region IDs:

`gran_buenos_aires`, `cuyo`, `noreste`, `noroeste`, `pampeana`, `patagonia`.

These are **threshold-area identities, not province IDs**. Geographic membership belongs to a separate governed binding; `argentina-geography` owns territorial interpretation and Poverty consumes the binding. In particular, Buenos Aires cannot be assigned wholesale to one basket region.

## Experimental ENGHo / Engel Phase A

```text
publicdata.indec-engho-microdata/v1
        ↓ immutable parent verification
national weighted p29–p48 on household ingpch
        ↓
national + six-region expenditure structure
        ↓
research.argentina-engel-reference-structure/v1
        ↓
G1–G4 commissioning
        STOP
```

Frozen Phase-A choices:

- ENGHo 2017/18;
- national weighted p29–p48 using `ingpch` and `pondera`;
- weighted ECDF cutpoints, lower inclusive and upper exclusive;
- zero/negative finite incomes remain rankable; missing/non-finite income fails closed;
- national selection occurs before regional grouping;
- documented negative ENGHo sales are preserved with their negative sign; clipping is only a named purchases-only sensitivity;
- food = COICOP 01 + group 021 alcoholic beverages;
- tobacco (022) and restaurant services (111) remain non-food while staying in total consumption;
- May 2018 is metadata only for the future Phase-B base;
- official ENGHo replicate weights provide diagnostic uncertainty using INDEC's MSE-bootstrap rule.

The persons table is not consumed by the Phase-A estimator. A real M1 commissioning warning can be attached through `--upstream-receipt` and retained as lineage without filtering records.

### Real commissioning review

The 2026-09-28 real run proved G1/G2 and P/A/M/G5 end-to-end. Its initial Artifact A (`engel-reference-83557070694b9306`) and Artifact B (`engel-sensitivity-10ec46dfd65c0d21`) clipped 1,000 documented negative sales rows and are therefore retained only as a diagnostic sensitivity. The primary method identity is now `research.argentina-engel-reference-structure/engho-2017-18-p29-p48-signed-sales-v2`.

See `science/engel_commissioning/real/2026-09-28/COMMISSIONING_REVIEW.md` for the durable review. `docs/CODEX_C2_ENGEL_SIGNED_SALES_RERUN.md` is retained as the historical execution handoff for the completed rerun.

### Phase-A commands

```bash
make engel-reference-test

make engel-reference-build \
  ENGHO_RELEASE=/path/to/engho-2017-2018-release \
  ENGHO_UPSTREAM_RECEIPT=/path/to/M1-commissioning-receipt.json

make engel-reference-check RELEASE_DIR=/path/to/engel-reference-...

make engel-reference-commission \
  RELEASE_DIR=/path/to/engel-reference-... \
  ENGEL_COMMISSION_OUTPUT=/tmp/engel-commissioning
```

See [`docs/ENGEL_REFERENCE_PHASE_A.md`](docs/ENGEL_REFERENCE_PHASE_A.md).

## Experimental ENGHo / Engel Phase B

Phase B consumes only immutable copies of:

```text
Artifact A: research.argentina-engel-reference-structure/v1
        +
direct official publicdata.indec-ipc-regional-divisions/v1
        +
observed nominal research.argentina-regional-baskets/v1
        ↓
research.argentina-regional-baskets-engel-sensitivity/v1
```

The required window is May 2018 through December 2025. All six regions and all twelve COICOP divisions must be complete; missing cells, duplicate cells, non-official IPC statuses, wrong bases, or incompatible parent methods are hard failures. Canastas performs no network retrieval and no interpolation in this path.

The price system holds the Phase-A expenditure structure fixed at May 2018. Total expenditure uses all twelve division shares. The frozen food block remains **COICOP01 + alcoholic beverages group 021**: COICOP01 uses the regional division-01 index, while alcoholic beverages use the broader division-02 index. Tobacco also uses division 02 but remains non-food. Restaurants remain non-food and use division 11. These shared-price approximations are explicit diagnostics, not hidden recodes.

For each region, Phase B exposes:

- the official inverse Engel coefficient `CBT_official / CBA_official`;
- the ENGHo17 fixed-base price-evolved inverse Engel coefficient;
- a **level factor** at May 2018;
- a **trajectory factor** relative to that base;
- a **full factor = level × trajectory**;
- three long-form line paths: `official`, `engho17_level_only`, and `engho17_level_plus_trajectory`;
- division-level price contributions for every region/month.

The official CBA is copied unchanged into the diagnostic surface. Artifact B never constructs a new nutritional CBA.

### Phase-B commands

```bash
make engel-phase-b-test

make engel-paths-build \
  ENGEL_REFERENCE_RELEASE=/path/to/artifact-a \
  ENGEL_IPC_RELEASE=/path/to/indec-regional-division-release \
  ENGEL_OFFICIAL_BASKET_RELEASE=/path/to/current-v2-basket-release

make engel-paths-check RELEASE_DIR=/path/to/engel-sensitivity-...

make engel-paths-commission \
  RELEASE_DIR=/path/to/engel-sensitivity-... \
  ENGEL_PATH_COMMISSION_OUTPUT=/tmp/engel-phase-b-commissioning
```

Commissioning implements cross-parent gate **P**, arithmetic gate **A**, price-mapping gate **M**, and observability suite **G5**. See [`science/engel_commissioning/PHASE_B.md`](science/engel_commissioning/PHASE_B.md).

## CEDLAS DT370 forensic replication

A separate validation lane reproduces the published updated-consumption exercise in Albina, Gasparini and Tornarolli (CEDLAS DT 370, 2026). It does not modify the primary p29–p48 signed-sales method.

The paper-exact lane uses the published low/very-low educational-climate division vector, treats the whole COICOP-02 alcohol+tobacco division as food, inherits the paper's old regional/national ICE ratios, evolves the resulting regional weights with the governed regional-division IPC parent, and reconstructs monthly CBT from the unchanged official CBA.

The implementation also exposes a `coicop02_food_fraction` switch, an aggregate-only ENGHo provenance audit for `clima_educativo`, direct regional low-education structures, an alcohol/tobacco split diagnostic, and an old-method IPC reconstruction control.

A second artifact, `research.argentina-regional-baskets-cedlas-choice-attribution/v1`, turns those ingredients into explicit threshold variants. It separates the published equal-group vector from literal pooled low+very-low households, inherited historical regional ICE ratios from direct regional structures, and full-COICOP02 food treatment from alcohol-only treatment. These variants are forensic diagnostics only and never mutate the primary signed-sales p29-p48 Artifact A/B.

See `science/engel_commissioning/cedlas_dt370/README.md` and `contracts/cedlas_dt370_replication_v1.json`.

## Authority boundary

This repository owns:

- exact source-locking for official regional CBA/CBT evidence;
- basket/threshold source semantics and six source-native region IDs;
- observed-vs-derived/imputed/projected value classification;
- deterministic basket candidate construction and QA;
- explicit monetary-parent lineage without reimplementing IPC methodology;
- bounded quarter-specific threshold inputs for Poverty;
- experimental ENGHo reference-population expenditure/Engel-base construction and its commissioning diagnostics;
- experimental fixed-base regional IPC Engel level/trajectory sensitivity paths and their P/A/M/G5 diagnostics.

It does **not** own:

- official CBA/CBT publication authority;
- monetary-reference/IPC methodology (`IPC-Argentina`);
- ENGHo raw-microdata custody (`microdatos-EPH-INDEC`);
- department/province → threshold-area membership (`argentina-geography`);
- poverty classification, adult equivalence or FGT (`indice-pobreza-UBA`);
- Census sampling or welfare inference;
- any promotion of ENGHo sensitivity lines to official or production poverty thresholds.

The Phase-A Engel artifact is not an official poverty basket and has no downstream authorization by itself.

## Legacy artifact

`data/CB_Reg_defl_m.csv` is historical compatibility evidence. It mixes derived price re-expression, historical imputation/backfill and a repeated synthetic tail. It is **not** the current scientific authority and must not be used as an observed current CBA/CBT series.

`DATA_STATUS.json` and `scripts/verify_snapshot.py` remain useful for auditing that legacy snapshot; they do not define the modern candidate boundary.

## Current threshold commands

```bash
make basket-source-probe
make basket-source-lock
make basket-source-lock-check SOURCE_LOCK=run/source_lock.json

make basket-candidate-v2 SOURCE_LOCK=run/source_lock.json PRICE_RELEASE=/path/to/ipc-release
make basket-candidate-v2-check RELEASE_DIR=/path/to/basket-release
```

The scheduled Monday job proves the durable source + IPC → basket candidate seam. It deliberately does not promote candidates to reviewed/approved status.

## Publication boundary

The current scheduled threshold path retains candidate evidence as workflow artifacts. Durable cross-repository publication of validated basket candidates remains separately tracked; consumers must never depend on an expiring Actions artifact or a mutable checkout as if it were an immutable release.

A basket candidate or Engel reference artifact is research input, not an official INDEC poverty result. Poverty measurement begins only after `indice-pobreza-UBA` combines governed threshold values, adult-equivalence semantics, welfare and an exact threshold-area binding under a named method/release.
