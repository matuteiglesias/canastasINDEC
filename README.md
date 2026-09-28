# Canastas regionales INDEC — poverty-threshold input producer

`canastasINDEC` is the poverty ecosystem's producer for governed **CBA/CBT threshold inputs** derived from exact official regional basket sources. It also hosts a separate experimental ENGHo/Engel research surface; that surface does not change the incumbent basket candidate or Poverty-input semantics.

> **Current state:** the modern v2 basket candidate path remains the current threshold-input authority. Separately, ENGHo/Engel **Phase A** implements `research.argentina-engel-reference-structure/v1`: a candidate/diagnostic p29–p48 reference expenditure structure with article accounting and replicate-weight uncertainty, but no price trajectory, alternative CBT or poverty calculation.

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
- food = COICOP 01 + group 021 alcoholic beverages;
- tobacco (022) and restaurant services (111) remain non-food while staying in total consumption;
- May 2018 is metadata only for the future Phase-B base;
- official ENGHo replicate weights provide diagnostic uncertainty using INDEC's MSE-bootstrap rule.

The persons table is not consumed by the Phase-A estimator. A real M1 commissioning warning can be attached through `--upstream-receipt` and retained as lineage without filtering records.

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

## Authority boundary

This repository owns:

- exact source-locking for official regional CBA/CBT evidence;
- basket/threshold source semantics and six source-native region IDs;
- observed-vs-derived/imputed/projected value classification;
- deterministic basket candidate construction and QA;
- explicit monetary-parent lineage without reimplementing IPC methodology;
- bounded quarter-specific threshold inputs for Poverty;
- experimental ENGHo reference-population expenditure/Engel-base construction and its commissioning diagnostics.

It does **not** own:

- official CBA/CBT publication authority;
- monetary-reference/IPC methodology (`IPC-Argentina`);
- ENGHo raw-microdata custody (`microdatos-EPH-INDEC`);
- department/province → threshold-area membership (`argentina-geography`);
- poverty classification, adult equivalence or FGT (`indice-pobreza-UBA`);
- Census sampling or welfare inference.

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
