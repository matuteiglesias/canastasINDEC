# Engel commissioning — Phase A

This surface commissions only `research.argentina-engel-reference-structure/v1`.

It answers four bounded questions:

- **G1**: is the national weighted p29-p48 reference population reproducible and well described?
- **G2**: do expenditure/article accounting and the frozen food rule reconcile exactly?
- **G3**: are external literature values easy to compare without becoming estimator inputs?
- **G4**: how stable are national/regional food-share and inverse-Engel estimates under the official ENGHo replicate weights?

The point reference population is selected nationally using household `ingpch` and `pondera`. For bootstrap diagnostics the complete selection procedure is re-run under each replicate weight, then regional estimates are computed inside that replicate's nationally selected cohort. The variance rule follows INDEC Nota Técnica 4:

`variance = (1/B) * sum((theta_rep - theta_point)^2)`.

## Food convention

The frozen primary rule is:

- COICOP division 01: food;
- COICOP group 021 alcoholic beverages: food for classification continuity;
- COICOP group 022 tobacco: non-food;
- COICOP group 111 restaurant services: non-food;
- all restaurant/hotel spending remains in total consumption expenditure.

No paper-specific alternate method is an estimator input.

## Benchmarks

`benchmarks/registry.json` is intentionally empty at implementation time. Later entries may pin published food-share or ICE values with method metadata. Commissioning classifies disagreements as compatible, classification difference, reference-population difference, sampling difference, or unresolved. A benchmark never changes the estimate.

## Hard boundary

Phase A contains no IPC loading, price evolution, alternative CBT, poverty, EPH, Census or Atlas logic.
