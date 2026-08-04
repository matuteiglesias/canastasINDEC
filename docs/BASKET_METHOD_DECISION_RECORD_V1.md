# Regional basket method decision record — candidate v1

**Owner:** Matías Iglesias  
**Decision date:** 2026-08-04  
**Lifecycle authorized:** `candidate` only  
**Core artifact identity:** `research.argentina-regional-baskets/v1`

## Purpose

Produce a real, immutable regional CBA/CBT candidate from the official monthly source CSVs and a pinned analytical price release, so downstream poverty integration can consume copied artifacts rather than mutable URLs or sibling repositories.

The operating principle is:

> Preserve integrity as a hard gate, but treat incomplete historical provenance as a warning when the requested candidate values can be reconstructed from pinned inputs.

This repository remains a derived historical/research producer. It does not become the official authority for CBA, CBT, poverty thresholds, or poverty classification.

## Approved official inputs

Use the sources declared in `contracts/source_registry.json`:

- Datos Argentina distribution `445.1` for regional monthly CBA;
- Datos Argentina distribution `446.1` for regional monthly CBT;
- one copied immutable `research.argentina-price-composite/v1` release for monetary conversion.

Record for CBA and CBT:

- dataset and distribution IDs;
- dataset page and resolved file URL;
- retrieval timestamp;
- byte size and SHA-256;
- HTTP metadata useful for provenance;
- actual schema and coverage;
- source/publisher language;
- license declaration;
- parser version.

The price dependency must be content-addressed or copied into the run/release input area. Do not read `raw.githubusercontent.com/.../main` or a sibling checkout during release execution.

## Canonical regions

Approve the six source-native region IDs as the candidate contract:

```text
gran_buenos_aires
cuyo
noreste
noroeste
pampeana
patagonia
```

These are basket regions, not province-level indexes.

A province-to-region mapping is a separate geography contract. In particular, Buenos Aires province cannot be assigned wholesale to one basket region because Gran Buenos Aires and Pampeana require subprovincial classification.

Source spelling normalization to the six IDs above is mechanical and approved when it does not change membership.

## Approved product hierarchy

### 1. Core observed-nominal monthly product

This is the primary candidate product.

Use unchanged source values from the official CBA and CBT CSVs for periods where both measures and all six regions are present.

Each cell must preserve:

```text
period
region_id
measure: CBA | CBT
value
unit
value_status: observed_source
source_id
source_snapshot_sha256
source_row_or_cell_identity when recoverable
release_id
```

The candidate unit is `ARS_per_equivalent_adult`, subject to preserving the exact official metadata wording in the manifest. A missing or ambiguous metadata phrase is a warning; it is not permission to alter values or silently reinterpret the unit.

### 2. Jan-2016-reference monthly product

Build a separate analytical product by converting the observed nominal values with the pinned price release:

```text
value_2016_01 = nominal_value / price_index_at_period * price_index_2016_01
```

Declare:

```text
monetary_reference_id: research.argentina-price-composite/legacy-compatible-v1@2016-01=100
value_status: derived_monetary_conversion
```

Do not call these cells observed basket values. Their basket inputs are observed; their monetary reference is analytically derived.

### 3. Quarterly product

Use the arithmetic mean of the three monthly values in a calendar quarter.

Label the quarter with the 15th day of the middle month, preserving the existing consumer convention. For example:

```text
2024-Q1 -> 2024-02-15
```

Require all three months for both measures and all six regions in the candidate core. Incomplete quarters may be omitted with a warning; do not fill them silently.

### 4. First downstream handoff slice

Prepare a bounded candidate integration bundle for:

```text
period: 2024-Q1
representative_date: 2024-02-15
regions: all six canonical regions
measures: CBA, CBT
monetary_reference: Jan-2016 legacy-compatible composite
status: candidate
```

This bundle is an input artifact only. It does not calculate poverty.

## Legacy products retained outside the core

### Pre-source historical backcast

The existing pre-2016-04 full-column-mean fill is retained only as a separate compatibility artifact with status:

```text
legacy_imputed_backcast
```

It is not part of the candidate core and must not be described as observed or source-derived history.

### Projected or repeated tail

Any period inherited from projected IPC values or repeated basket values must live in a separate artifact or clearly separated table with status:

```text
projected
synthetic_tail
```

It is excluded from the candidate core and from the 2024-Q1 handoff.

### Execution-month/current-price tables

Wall-clock-dependent “current price” outputs are not canonical release products. They may be generated only with an explicit requested reference period that is recorded in configuration and the manifest.

## Missingness policy

For the core observed-nominal and Jan-2016-reference products:

- do not use full-column means;
- do not borrow a later value;
- do not forward-fill or repeat a tail;
- do not silently drop one region or one measure.

A period without both CBA and CBT for all six regions is excluded from the complete-core coverage and recorded with a warning/report. A specifically requested integration period fails when its required cells are incomplete.

This allows the full candidate release to move forward with its actual complete coverage while protecting a requested downstream slice.

## Ordering and numerical invariants

Hard requirements for every emitted candidate cell/region-period:

```text
CBA > 0
CBT > 0
CBA <= CBT
finite values
unique period + region + measure
```

Equality is structurally acceptable. Unexpected equality should be reported for review but is not automatically invalid.

For monetary conversion:

- price index values must be finite and positive;
- requested period coverage must exist;
- the exact monetary-reference identity must match the release declaration;
- no value may be converted twice.

## Price dependency policy

A `candidate` IPC release with machine-readable provenance warnings may be used for a basket candidate.

Warnings propagate into the basket manifest and limitations. The basket build must still reject:

- checksum mismatch;
- corrupted or unsafe paths;
- incompatible artifact type;
- incompatible method identity;
- incompatible monetary-reference identity;
- missing requested price period;
- projected price rows when the requested product forbids them.

## Failure versus warning policy

### Hard failures

- official CBA or CBT snapshot checksum mismatch;
- unparseable pinned CSV;
- conflicting duplicate period/region values;
- nonfinite or nonpositive values;
- `CBA > CBT`;
- missing one of the six regions or one measure in a specifically requested candidate slice;
- incompatible or corrupted price release;
- missing price period required for conversion;
- double monetary conversion;
- nondeterministic output from the same pinned inputs.

### Warning-level conditions

- exact old source bytes were not retained for a historical committed output;
- source metadata wording does not fully resolve the equivalent-adult description;
- incomplete periods are omitted outside the requested slice;
- price release carries declared warning-level provenance limitations;
- legacy backcast, projection, or synthetic-tail products are excluded from core;
- source row IDs are unavailable but source bytes and cell coordinates are pinned;
- province-to-region mapping is not part of this release.

## Publication language

Permitted:

- “official-source nominal input” for unchanged cells from the pinned official CSVs;
- “derived regional basket candidate” for transformed outputs;
- “Jan-2016 analytical monetary reference”;
- “legacy imputed backcast” and “synthetic tail” where applicable;
- “research input; not a poverty result.”

Not permitted:

- claiming the transformed tables are official INDEC publications;
- calling pre-source imputed cells observations;
- calling projected/repeated cells current official values;
- presenting the candidate as an official poverty threshold release;
- automatic promotion above `candidate`.

## Downstream contract

`indice-pobreza-UBA` should consume a copied immutable candidate integration bundle containing manifest, compatibility declaration, checksums, six-region quarterly values, monetary-reference identity, source identities, and warnings.

It must not fetch this repository's branch or execute this repository at runtime.

## Decisions superseded

This record answers the open candidate-v1 choices in `docs/BASKET_METHOD_DECISIONS_REQUIRED.md`. Alternative imputation, backcast, projection, mapping, or monetary-reference policies require a new method identity and separate review.
