# Poverty-slice basket readiness

## Finding: not ready to construct a real candidate slice

A `candidate` (never `approved`) could wrap unchanged values only after Matías supplies/approves the bounded consumer period and resolves immutable upstream identities. No `indice-pobreza-UBA` checkout or consumer audit is present in this workspace, so its provisional slice could not be verified read-only. Guessing its date would violate this packet. No downstream repository was accessed or changed.

## Available evidence

- The principal monthly artifact covers 2003-01 through 2025-12 and has all six region IDs in `contracts/regions.json` for every month.
- It contains 3,312 measure cells: 1,908 pre-source `imputed` cells (2003-01 through 2016-03), 1,344 `derived` cells in the declared source-observation range (2016-04 through 2025-07), and 60 repeated-tail `synthetic` cells (2025-08 through 2025-12). There are zero auditable `observed` cells because source row IDs and raw inputs were not retained.
- Monthly identity uses first-of-month dates. Quarterly artifacts use the 15th of the middle month, but their generation vintages differ and the mixed-reference file stops at 2023-Q2.
- All six committed region spellings can be canonicalized without changing mappings; the source mapping itself remains subject to approval.
- The principal values are re-expressed to the CPI level of their producing execution month, apparently 2025-10 from commit evidence. That level and the consumed IPC file have no retained immutable hash, so the reference is unresolved rather than an approved monetary contract.
- CBA/CBT are present and ordered, but the adult-equivalent source definition, official source vintage/license, internal missing-cell history, and projected IPC boundary are not evidenced by a run manifest.

## Exact producer artifacts needed

1. An immutable observed-nominal source artifact with retrieval date, URL/vintage, license, hashes, raw source observation IDs, approved region dictionary, unit/adult definition, and actual coverage.
2. A pinned `publicdata.price-index@1` artifact with revision, SHA-256, observed/projected boundary, and approved conversion semantics.
3. A per-cell lineage export preserving input status through imputation, quarterly aggregation, and monetary re-expression.
4. The consumer's immutable requested slice contract (period frequency/range, regions, unit/reference, and allowed statuses).
5. A run manifest binding code revision, inputs, formulas, output hashes, and human lifecycle status.

**Readiness answer:** no real candidate slice is currently reproducible under the required contract without making unresolved methodological/authority choices. The committed values need not change to package a future candidate, but missing identities and the unavailable consumer boundary must first be supplied; synthetic or imputed cells must not be silently accepted.
