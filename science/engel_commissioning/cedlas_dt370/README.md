# CEDLAS DT370 updated-consumption replication lane

This lane reproduces the **published consumption-pattern experiment** in Albina, Gasparini and Tornarolli (CEDLAS DT 370, 2026). It is deliberately separate from the primary signed-sales p29-p48 ENGHo Artifact A/B.

## Paper-exact chain

1. Start from the published ENGHo 2017/18 division shares for households with **very low** and **low** educational climate.
2. The paper's displayed combined vector is the simple arithmetic mean of those two published subgroup vectors.
3. Treat COICOP division 01 **and the whole division 02 (alcoholic beverages and tobacco)** as the food block.
4. This gives national food share 35% and national ICE = 1/0.35 = 2.857142...
5. Preserve the paper's published old regional/national ICE ratios to obtain the six May-2018 regional ICEs.
6. Within each regional food/non-food block, preserve the national internal composition.
7. Rebase regional division IPC to May 2018 and evolve total and food price indices.
8. Construct monthly ICE and CBT as official CBA × replicated ICE.

Published Tables 1, 3 and 4 are immutable validation targets, never estimator inputs beyond the explicitly published structure itself.

## Tobacco switch

The primary replication uses:

`coicop02_food_fraction = 1`

which exactly matches the paper's treatment of the full alcohol+tobacco division as food.

The implementation accepts any fraction in [0,1] so tobacco treatment can be ablated without changing the rest of the chain. The ENGHo provenance audit estimates the alcohol share of division 02 from group 021 versus 022, permitting a later alcohol-only counterfactual.

## Low-education provenance

`cedlas-low-education-provenance` consumes only the governed ENGHo release and writes aggregates:

- very-low microdata division shares;
- low microdata division shares;
- equal-group average;
- pooled low+very-low structure;
- direct regional structures;
- division-02 alcohol/tobacco split.

It writes no household IDs or respondent-level records.

This lets us distinguish:

- published-table reconstruction;
- literal microdata pooling;
- equal weighting of the two education groups;
- inherited versus direct regionalization;
- tobacco-in-food versus alcohol-only food scope.

## Old-method control

`cedlas-old-method-reconstruction` uses the 2004/05 published division weights and the May-2018 official regional ICEs to reconstruct the incumbent ICE path with the same 12-division IPC machinery. It is an approximation diagnostic, because IPC divisions do not exactly match the products in the official poverty baskets.

## Commands

```bash
make cedlas-dt370-test

make cedlas-dt370-build \
  ENGEL_IPC_RELEASE=/path/to/regional-ipc \
  ENGEL_OFFICIAL_BASKET_RELEASE=/path/to/official-basket \
  CEDLAS_OUTPUT=/path/to/output

make cedlas-dt370-check RELEASE_DIR=/path/to/cedlas-release
make cedlas-dt370-commission RELEASE_DIR=/path/to/cedlas-release

make cedlas-dt370-provenance \
  ENGHO_RELEASE=/path/to/engho-release \
  CEDLAS_PROVENANCE_OUTPUT=/path/to/provenance

make cedlas-dt370-old-reconstruction \
  ENGEL_IPC_RELEASE=/path/to/regional-ipc \
  ENGEL_OFFICIAL_BASKET_RELEASE=/path/to/official-basket
```

The Poverty-side Table-5 replication is implemented in `indice-pobreza-UBA/science/measurement_alignment/cedlas_dt370.py`.
