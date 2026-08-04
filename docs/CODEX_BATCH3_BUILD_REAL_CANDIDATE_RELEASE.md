# Codex work packet — build the real regional basket candidate release

## Mission

Recover the official monthly regional CBA and CBT inputs, pin them by content identity, consume a copied immutable IPC candidate release, and publish the first real `candidate` regional basket artifact plus a bounded 2024-Q1 integration bundle for the poverty consumer.

This is an implementation and source-recovery task, not another audit.

Read and obey:

1. every applicable `AGENTS.md`;
2. `docs/BASKET_METHOD_DECISION_RECORD_V1.md`;
3. `contracts/source_registry.json`;
4. `docs/BASKET_PRODUCT_FAMILIES.md`;
5. `docs/ARTIFACT_COMPATIBILITY.md`;
6. `docs/POVERTY_SLICE_BASKET_READINESS.md`;
7. `contracts/regions.json`, `contracts/periods.json`, `contracts/monetary_references.json`, and `contracts/lineage_graph.json`;
8. `computar_canastas.py`, legacy notebook exports, `DATA_STATUS.json`, the current fixture builder, validators, and `Makefile`.

The owner has approved the candidate-v1 policy. Missing historical provenance is generally a warning. Corrupted bytes, incompatible identities, incomplete specifically requested slices, and invalid values remain hard failures.

## Approved boundary

### Own here

- official CBA/CBT source acquisition and snapshots;
- source parsing and canonical six-region normalization;
- observed-nominal monthly candidate product;
- Jan-2016-reference monthly and quarterly derived products;
- cell-level lineage and QA;
- immutable candidate release directory;
- bounded 2024-Q1 integration bundle;
- consumer preflight and warning propagation.

### Do not own

- official INDEC publication;
- price-index methodology;
- province-to-region geography methodology;
- adult-equivalence household calculation;
- income prediction;
- poverty classification or aggregation;
- Atlas/publication deployment;
- automatic promotion above `candidate`.

## Required implementation

### 1. Source acquisition and source lock

Implement bounded acquisition for the two official distributions in `contracts/source_registry.json`:

```text
445.1 — regional monthly CBA
446.1 — regional monthly CBT
```

Record for each successful snapshot:

- source ID;
- dataset and distribution ID;
- dataset page and resolved CSV URL;
- retrieval timestamp;
- byte size and SHA-256;
- HTTP headers useful for provenance;
- parser ID;
- actual schema;
- actual period coverage;
- source/publisher and license language.

Store source bytes outside Git by default under a cache or run-local input directory. Support offline rebuild from a pinned source lock.

Add commands equivalent to:

```bash
make basket-source-probe
make basket-source-lock
make basket-source-lock-check
```

Do not hide an unavailable or changed source. Record a diagnostic and stop candidate construction when either CBA or CBT cannot be pinned, because both are required for the core candidate.

### 2. Canonical source normalization

Create one deterministic long-form source table with at least:

```text
period
region_id
measure
nominal_value
unit
value_status
source_id
source_snapshot_sha256
source_cell_identity
parser_id
```

Rules:

- normalize `period` to first-of-month dates;
- normalize source column spelling mechanically to the six approved region IDs;
- preserve source values without rebasing or rounding;
- require unique `period + region_id + measure`;
- require finite positive values;
- require `CBA <= CBT` for every complete region-period;
- sort deterministically;
- retain incomplete source periods in the source/QA layer, but do not place them in complete-core outputs.

When source metadata confirms or clarifies the unit, preserve the exact wording in the source snapshot manifest and map it to the candidate contract. Do not modify values because metadata wording differs from expectations.

### 3. Complete-core coverage

Derive the set of months containing both CBA and CBT for all six regions.

Emit:

- actual raw source coverage;
- complete-core coverage;
- incomplete-period report with missing region/measure cells;
- first and last complete month;
- counts by source, measure, region, and status.

Do not fill core missing cells with column means, later periods, forward fill, or repeated tails.

A release may still be built when incomplete periods exist outside its declared complete-core coverage. A specifically requested slice must fail if incomplete.

### 4. Pinned IPC candidate dependency

Implement a consumer interface for a copied immutable release of:

```text
artifact_type: research.argentina-price-composite/v1
method_id: research.argentina-price-composite/legacy-compatible-v1
monetary_reference_id: research.argentina-price-composite/legacy-compatible-v1@2016-01=100
```

Do not fetch `IPC-Argentina/main` during execution.

Before loading price rows, run a standard-library preflight that verifies:

- manifest envelope and checksum identity;
- safe paths;
- declared files, sizes and SHA-256;
- artifact and method identities;
- monetary-reference identity;
- required monthly periods;
- allowed row statuses;
- absence of projected rows in products that forbid projection.

Allow a structurally valid `candidate` IPC artifact with declared warning-level provenance limitations. Propagate those warnings into the basket manifest and limitations.

Reject corruption, incompatible identity, missing required periods, or a projected row used as an observed-core conversion input.

### 5. Observed-nominal candidate product

Produce the primary monthly table from unchanged official source values:

```text
observed_nominal_monthly.csv
```

At minimum include:

```text
period
region_id
CBA_nominal
CBT_nominal
unit
value_status
CBA_source_identity
CBT_source_identity
release_id
```

Use only complete-core months. Preserve full numeric precision from the source.

### 6. Jan-2016-reference product

Using the pinned price candidate, calculate separately:

```text
value_2016_01 = nominal_value / price_index_at_period * price_index_2016_01
```

Produce:

```text
reference_2016_01_monthly.csv
```

Require one compatible price row for every converted month. Record the exact price release ID, manifest hash, row status, and conversion formula in cell-level or table-level lineage.

Do not round the canonical analytical output unless a contract explicitly defines rounding. Presentation tables may round separately.

Add checks against double conversion and monetary-reference mismatch.

### 7. Quarterly product

Create calendar-quarter means from the complete three monthly rows for every region and measure.

Produce:

```text
reference_2016_01_quarterly.csv
```

Rules:

- arithmetic mean of three monthly values;
- all three months required;
- six regions and both measures required;
- representative date is the 15th day of the middle month;
- row status is `derived_quarterly_mean`;
- lineage lists the three monthly input periods and price release identity.

Add explicit tests for quarter completeness and representative-date generation.

### 8. Bounded 2024-Q1 poverty handoff

Build a copyable immutable integration bundle for:

```text
period: 2024-Q1
representative_date: 2024-02-15
regions: all six
measures: CBA and CBT
monetary_reference: research.argentina-price-composite/legacy-compatible-v1@2016-01=100
status: candidate
```

Suggested path:

```text
artifacts/integration/poverty-baskets-2024q1-<content-id>/
```

Include:

```text
manifest.json
compatibility.json
regional_baskets.csv
qa.json
limitations.md
checksums.sha256
```

The table must have one row per canonical region with CBA and CBT columns or an equivalently explicit long format.

The manifest must declare:

- source snapshot identities;
- price candidate identity and manifest hash;
- exact three monthly periods;
- quarterly method;
- representative date;
- unit and monetary reference;
- all warnings inherited and generated;
- `scientific_poverty_execution_performed: false`.

Do not calculate household thresholds, join Census persons, or classify poverty.

### 9. Full candidate release

Create a content-addressed immutable release such as:

```text
artifacts/basket_releases/<release-id>/
```

At minimum include:

```text
manifest.json
compatibility.json
source_lock.json
price_dependency_lock.json
observed_nominal_monthly.csv
reference_2016_01_monthly.csv
reference_2016_01_quarterly.csv
cell_lineage.csv
coverage.json
qa.json
limitations.md
checksums.sha256
```

Use `research-artifact-manifest/v1` and declare:

```text
artifact_type: research.argentina-regional-baskets/v1
status: candidate
method_id: research.argentina-regional-baskets/source-observed-plus-legacy-price-reference-v1
```

The release creation time must be deterministic from declared provenance, not an unrecorded wall-clock dependency.

Do not place the legacy backcast or synthetic tail in the candidate core files.

### 10. Legacy compatibility outputs

Preserve the existing historical backcast and projected/repeated tail only through an explicit, separately invoked compatibility command or report.

Classify cells as:

```text
legacy_imputed_backcast
projected
synthetic_tail
```

Do not regenerate these by default as part of the core candidate.

Do not delete the old committed artifact or historical notebooks in this task. Compare them with the new candidate and explain differences.

### 11. Warning-versus-failure behavior

Hard failures include:

```text
source_checksum_mismatch
unparseable_pinned_source
conflicting_duplicate
nonfinite_or_nonpositive_value
cba_exceeds_cbt
missing_required_region_or_measure_in_requested_slice
corrupted_or_incompatible_price_release
missing_required_price_period
projected_price_used_for_core_conversion
double_conversion
nondeterministic_output
unsafe_path
```

Warnings include:

```text
historical_source_bytes_not_retained
source_unit_metadata_wording_incomplete
incomplete_period_omitted_outside_requested_slice
price_candidate_has_provenance_warnings
source_cell_id_unavailable_but_snapshot_pinned
legacy_backcast_excluded
synthetic_tail_excluded
province_mapping_out_of_scope
```

The candidate validator must return success-with-warnings for a valid release carrying warning conditions.

### 12. Consumer validator

Expose a standard-library-only preflight where practical:

```bash
python -m <package>.validate <release-directory>
```

Validate envelope, artifact type, method, files, hashes, period coverage, region coverage, unit, monetary reference, statuses, CBA/CBT ordering, and source/price identities before pandas loads the tables.

Support a research policy that accepts a candidate with warnings, while preserving hard integrity failures.

### 13. Province and geography handoff

Document clearly that the six basket regions are not provincial indexes.

Produce no guessed province mapping.

Prepare a small expected geography contract for downstream work:

```text
geography entity -> exactly one basket region_id
```

Record that Buenos Aires province requires subprovincial classification between Gran Buenos Aires and Pampeana. This must not block the six-region basket release itself.

## Commands

Add a clear surface, approximately:

```bash
make basket-source-probe
make basket-source-lock
make basket-source-lock-check
make basket-candidate
make basket-candidate-check
make basket-candidate-smoke
make poverty-basket-2024q1
make poverty-basket-2024q1-check
```

Keep current offline snapshot and fixture checks. Do not make source-dependent regeneration part of a generic `check` or `smoke` target.

## Live-source execution policy

This task authorizes contacting the official CBA/CBT endpoints and consuming a provided copied IPC candidate release.

Before committing real generated candidate outputs:

- report source hashes and actual coverage;
- report the price release identity and warnings;
- compare representative periods/regions against the old committed tables;
- explain every historical difference by source, conversion, missingness, reference, or rounding policy;
- preserve old snapshot evidence;
- avoid committing large raw downloads;
- stop on unexplained value changes or ordering failures.

When network access or the IPC candidate is unavailable, implement the entire path and test it with pinned small fixtures, then report the exact missing input. Do not fabricate live source hashes or a real candidate release.

## Non-goals

- no poverty calculation;
- no household adult-equivalence multiplication;
- no imputed historical candidate core;
- no projected/repeated candidate core;
- no new basket methodology;
- no province mapping guess;
- no current-month wall-clock publication;
- no automatic scheduled refresh;
- no official-current claim;
- no automatic promotion above candidate.

## Acceptance criteria

```text
official 445.1 and 446.1 snapshots are pinned by SHA-256
six source regions are normalized deterministically
complete-core monthly coverage is measured rather than imputed
observed nominal values remain unchanged
one copied immutable IPC candidate is validated before conversion
Jan-2016 monthly and quarterly products share an explicit monetary reference
2024-Q1 produces six complete regional CBA/CBT rows or fails honestly
cell lineage connects every candidate value to source snapshots and price identity
legacy backcast and synthetic tail remain outside the core candidate
one immutable basket candidate passes preflight with warnings allowed
one copyable poverty-input bundle is created without poverty execution
province mapping remains an explicit downstream geography contract
```

## Completion report

State:

- official source URLs contacted and resolved;
- source hashes, schemas, periods and region columns;
- complete and incomplete coverage;
- price candidate release ID, manifest hash and warning set;
- candidate basket release ID and path;
- 2024-Q1 integration bundle ID and path;
- exact method and monetary-reference identities;
- representative differences from legacy files;
- warnings versus hard failures;
- commands run and exact results;
- committed outputs and excluded source bytes;
- confirmation that no poverty calculation occurred;
- remaining blockers for reviewed or approved status.
