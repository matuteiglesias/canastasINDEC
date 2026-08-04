# Codex work packet — Portfolio Batch 3 preparation: regional basket lineage

## Mission

Prepare `canastasINDEC` for a later methodology-approved regional CBA/CBT release that can be consumed safely by the poverty research pipeline.

This packet must separate official observed basket inputs from this repository's analytical transformations, imputations, deflation/re-expression, and synthetic extensions. It must not change the current methodology or publish a new poverty threshold.

The immediate question is:

> What exact regional basket values, units, periods, source observations, price references, and transformations exist—and what would be required to issue one immutable candidate release for a bounded poverty slice?

## Read first

1. Read all applicable `AGENTS.md` files.
2. Read `README.md`, `SYSTEM.yaml`, `DATA_STATUS.json`, `Makefile`, source/acquisition code, transformations, current data outputs, tests, CI, and methodology notes.
3. Inspect commit history around source tables, regional imputations, quarterly conversion, deflation/re-expression, synthetic tails, and file renames.
4. Inspect `IPC-Argentina` read-only to identify every consumed series/file and the exact conversion semantics.
5. Inspect `indice-pobreza-UBA` consumer audit read-only for the required canonical basket contract.
6. Do not modify those repositories from this task.

## Authority and boundaries

This repository may own:

- acquisition and normalization of declared official basket observations;
- explicit regional transformations and research-derived basket products;
- periodic conversion and monetary-reference transformations;
- provenance, status classification, and release manifests.

It does not own:

- official INDEC poverty statistics;
- authority over source values;
- household poverty classification;
- price-index methodology owned by another producer;
- automatic approval of mean imputation, backcasting, projection, or re-expression.

## Required deliverables

### 1. Basket product-family inventory

Create `docs/BASKET_PRODUCT_FAMILIES.md` assigning every input/output table to a family such as:

```text
official_observed_nominal
normalized_observed_nominal
regional_derived_nominal
quarterly_conversion
constant_reference_reexpression
imputed_history
projected_or_synthetic_extension
historical_unresolved
```

For every table record:

- path;
- CBA/CBT meaning;
- geographic level and region dictionary;
- unit, currency, and adult-equivalent basis;
- frequency and period semantics;
- source coverage;
- transformed/imputed/projected coverage;
- producing code/config;
- price-series dependency;
- downstream consumers;
- current limitations.

Names such as `defl`, `regional`, or `Q` are not sufficient documentation.

### 2. Source and transformation graph

Create a machine-readable graph from official source observations to every derived output, including:

- source publisher/file/URL evidence;
- region mappings;
- CBA/CBT construction or selection;
- missing-region imputation;
- monthly-to-quarterly conversion;
- deflation or re-expression;
- use of IPC/composite price series;
- backcasting;
- projection/synthetic extension;
- output files.

Each edge must cite exact code/config and parameters.

### 3. Cell-level status classification

For every region-period-measure cell, expose a deterministic status vocabulary:

```text
observed
derived
imputed
interpolated
projected
synthetic
unresolved
```

Also record:

- source observation ID where present;
- transformation chain ID;
- monetary reference;
- methodology version;
- warnings.

A row-level status is insufficient when CBA and CBT or regions have different provenance.

### 4. Canonical region and period dictionaries

Create machine-readable dictionaries for:

- region IDs and labels;
- source-region labels and normalization;
- coverage expectations;
- monthly versus quarterly period identity;
- representative-date conventions, if any;
- adult-equivalent unit.

Do not let consumers join on free-text region spelling.

### 5. Monetary-reference contract

For each output, declare:

- nominal versus constant/reference-reexpressed values;
- source currency;
- source period;
- output price reference;
- price artifact ID and hash;
- conversion formula;
- whether the transformation is reversible;
- rounding policy.

Do not use wall-clock “today” as a monetary reference.

Where the price artifact is not yet versioned, retain a provisional unresolved ID and block approved release mode.

### 6. Shared artifact envelope

Adopt `research-artifact-manifest/v1` for fixture/candidate releases while preserving basket-specific extensions.

Keep distinct artifact identities, for example:

```text
publicdata.regional-baskets-observed/v1
research.regional-baskets-derived/v1
research.regional-baskets-monetary-reference/v1
```

A consumer must be able to distinguish observed nominal source data from an imputed/projected/re-expressed analytical product.

Use statuses:

```text
synthetic
candidate
reviewed
approved
```

No automatic promotion.

### 7. Compatibility declaration and preflight

Provide a standard-library validator and compatibility declaration for the poverty consumer contract. It must validate:

- manifest schema/type/status;
- immutable files and hashes;
- safe relative paths;
- region dictionary identity;
- period and coverage;
- CBA/CBT columns and adult-equivalent unit;
- currency and monetary reference;
- price artifact identity;
- cell-status policy;
- complete region-period coverage;
- duplicate keys;
- approved-mode policy for imputed/projected/synthetic cells.

### 8. Synthetic fixture release

Create a deterministic fixture containing:

- multiple regions;
- monthly observed CBA and CBT;
- one missing region-period cell;
- one declared imputation;
- quarterly conversion;
- one monetary-reference transformation;
- CBA/CBT ordering;
- explicit cell statuses;
- a tampered/invalid fixture for negative tests.

The fixture demonstrates mechanics only and must not reproduce or imply approved real thresholds.

### 9. Candidate-slice readiness report

Create `docs/POVERTY_SLICE_BASKET_READINESS.md` evaluating whether one real immutable release can cover the provisional bounded slice described in `indice-pobreza-UBA`.

Do not silently accept its provisional date. Report:

- real periods currently covered;
- whether monthly or quarterly identity is available;
- regions covered;
- source/derived status by cell;
- monetary references available;
- price dependencies;
- unresolved methodology;
- exact producer artifacts needed;
- whether a candidate—not approved—release could be constructed without changing values.

### 10. Decision packet

Create `docs/BASKET_METHOD_DECISIONS_REQUIRED.md` with evidence and consequences for:

- official source vintages;
- region definitions;
- missing-region treatment;
- monthly/quarterly convention;
- mean or other imputation;
- historical backcasting;
- projected/synthetic extensions;
- nominal versus constant/reference values;
- price index/composite dependency;
- CBA/CBT ordering and validation;
- publication/use limitations.

Do not choose automatically.

## Command surface

Provide commands equivalent to:

```bash
make check
make release-fixture
make release-check
make basket-lineage-report
```

Offline checks must not fetch live data or overwrite tracked real outputs.

## Human checkpoints

Stop before:

- changing real basket values;
- approving a source or region mapping;
- selecting an imputation method;
- changing quarterly conversion;
- selecting a price series or monetary reference;
- approving synthetic/projected cells;
- constructing a real poverty-consumer release;
- changing downstream poverty calculations.

## Non-goals

- No poverty estimate or classification.
- No live refresh.
- No new basket methodology.
- No silent replacement of current files.
- No official-statistics claim.
- No large data commits.
- No downstream repository mutation.

## Acceptance criteria

```text
every basket file belongs to an explicit product family
the full source/transformation graph is machine-readable
region, period, unit, and monetary-reference contracts are explicit
every region-period-measure cell has observed/derived/imputed/projected status
a deterministic synthetic fixture release validates independently
observed nominal and analytical derived products have distinct artifact identities
candidate slice readiness is reported without selecting methodology
Matías receives a bounded decision packet with downstream consequences
no real values or poverty outputs are changed
```

## Completion report

Report:

- files and product families inventoried;
- transformation graph coverage;
- cell counts by status;
- region/period and monetary-reference findings;
- fixture release IDs/hashes;
- candidate-slice readiness;
- exact checks run;
- decisions required;
- confirmation that no real basket method, value, poverty calculation, or official claim changed.
