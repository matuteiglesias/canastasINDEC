# Canastas regionales INDEC — poverty-threshold input producer

`canastasINDEC` is the poverty ecosystem's producer for governed **CBA/CBT threshold inputs** derived from exact official regional basket sources. It preserves the historical analytical artifact, but new poverty work should use the source-lock/candidate path.

> **Current state:** the modern v2 candidate path is implemented. It acquires/pins exact official CBA/CBT source bytes, consumes one immutable `IPC-Argentina` conversion parent, builds an observed-nominal core plus explicitly derived views, validates lineage/coverage, and emits a quarter-specific Poverty input. Candidate status is not official publication or automatic scientific approval.

## Modern path

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

## Authority boundary

This repository owns:

- exact source-locking for official regional CBA/CBT evidence;
- basket/threshold source semantics and six source-native region IDs;
- observed-vs-derived/imputed/projected value classification;
- deterministic basket candidate construction and QA;
- explicit monetary-parent lineage without reimplementing IPC methodology;
- bounded quarter-specific threshold inputs for Poverty.

It does **not** own:

- official CBA/CBT publication authority;
- monetary-reference/IPC methodology (`IPC-Argentina`);
- department/province → threshold-area membership (`argentina-geography`);
- poverty classification, adult equivalence or FGT (`indice-pobreza-UBA`);
- Census sampling or welfare inference.

## Legacy artifact

`data/CB_Reg_defl_m.csv` is historical compatibility evidence. It mixes derived price re-expression, historical imputation/backfill and a repeated synthetic tail. It is **not** the current scientific authority and must not be used as an observed current CBA/CBT series.

`DATA_STATUS.json` and `scripts/verify_snapshot.py` remain useful for auditing that legacy snapshot; they do not define the modern candidate boundary.

## Current commands

```bash
make basket-source-probe
make basket-source-lock
make basket-source-lock-check SOURCE_LOCK=run/source_lock.json

# with a copied immutable IPC v2 conversion release:
make basket-candidate-v2 SOURCE_LOCK=run/source_lock.json PRICE_RELEASE=/path/to/ipc-release
make basket-candidate-v2-check RELEASE_DIR=/path/to/basket-release
```

The scheduled Monday job proves the durable source + IPC → basket candidate seam. It deliberately does not promote candidates to reviewed/approved status.

## Publication boundary

The current scheduled path retains candidate evidence as workflow artifacts. Durable cross-repository publication of validated basket candidates remains separately tracked; consumers must never depend on an expiring Actions artifact or a mutable checkout as if it were an immutable release.

## Interpretation

A basket candidate is a research input, not an official INDEC poverty result. Poverty measurement begins only after `indice-pobreza-UBA` combines governed threshold values, adult-equivalence semantics, welfare and an exact threshold-area binding under a named method/release.
