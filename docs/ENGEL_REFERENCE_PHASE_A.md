# ENGHo 2017/18 Engel reference structure — Phase A

## Purpose

`canastasINDEC` now has a bounded experimental surface for constructing a reference expenditure structure from a governed `publicdata.indec-engho-microdata/v1` parent.

The artifact is:

`research.argentina-engel-reference-structure/v1`

with method:

`research.argentina-engel-reference-structure/engho-2017-18-p29-p48-v1`.

It is **candidate/diagnostic research evidence**, not an official INDEC basket and not a poverty result.

## Frozen method

1. Rank the national household universe by ENGHo `ingpch`.
2. Use `pondera` as the household expansion weight.
3. Find weighted ECDF support-value cutpoints at 0.29 and 0.48.
4. Select `income >= q29 && income < q48`.
5. Keep ties whole at both cut values. This may move achieved mass slightly away from exactly 19 percentage points.
6. Zero and negative finite income values remain rankable. Missing/non-numeric/non-finite income fails closed.
7. Select nationally before calculating the six regional structures.
8. Estimate expenditure shares by weighting household-level monthly consumption profiles.
9. Food is COICOP 01 plus COICOP group 021 alcoholic beverages. Tobacco (022) and restaurant services (111) are non-food but remain in total expenditure.
10. Base inverse Engel coefficient is `1 / food_share`.

May 2018 is retained only as base-period metadata for later Phase B work. No price series is consumed here.

## Parent boundary

The loader verifies the immutable ENGHo parent manifest and the household, expenditure, article and replicate-weight table checksums. It deliberately does not consume the persons table.

The current real M1 run reported a 50-row persons-table discrepancy against the 2020 manual. That remains upstream custody evidence and is not a Phase-A scientific filter. A real run can pass the M1 receipt via `--upstream-receipt` so the warning is preserved in lineage.

## Efficient accounting

The ~902k expenditure rows are classified once and collapsed to household profiles. The 200 replicate calculations then operate on household profiles, not by rescanning the expenditure file 200 times.

Unknown article codes, negative expenditure amounts, missing household identities, inconsistent article/division identities, or failed accounting identities stop the build.

## Bootstrap diagnostics

The official replicate weights are used with the INDEC MSE-bootstrap variance convention:

`v_B(theta) = (1/B) sum_b (theta_b - theta_point)^2`.

The national p29-p48 selection is re-estimated under every replicate before regional food share and ICE are calculated. Reported intervals are point estimate ± 1.96 standard errors and are commissioning diagnostics only.

## Commands

```bash
python3 -m basket_release.engel build-reference \
  --engho-release /path/to/immutable/engho-release \
  --output artifacts/engel_reference

python3 -m basket_release.engel validate-reference \
  artifacts/engel_reference/engel-reference-...

python3 -m basket_release.engel commission-reference \
  --release artifacts/engel_reference/engel-reference-... \
  --output artifacts/engel_commissioning \
  --benchmarks science/engel_commissioning/benchmarks/registry.json
```

The same commands have Make wrappers.

## Non-goals

Phase A does not load IPC, evolve prices, calculate a time-varying Engel coefficient, construct alternative CBT paths, calculate adult equivalence, estimate poverty, or touch Census/Atlas products.
