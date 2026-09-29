# Real ENGHo / Engel commissioning review — 2026-09-28

## Decision

The real C1 bundle and the subsequent signed-sales rerun prove that the Phase-A and Phase-B machinery works end to end on the commissioned parents. The first clipped-sales artifacts are retained only as a sensitivity; the signed-sales pair is now the primary frozen candidate/diagnostic pair.

The blocking issue is narrow: the first run clipped 1,000 negative ENGHo expenditure rows to zero. INDEC documents household sales as negative expenditure amounts. Clipping therefore changes the consumption accounting concept rather than merely cleaning invalid data.

Primary policy is:

```text
negative_expenditure_policy = preserve_signed_sales
```

The signed-sales rerun passed G1/G2 and P/A/M/G5 with no code changes. The clipped artifacts remain valuable as a named diagnostic sensitivity.

## Exact reviewed bundle

- ENGHo parent: `engho-2017-2018-ff05578d65ae`; local M1 PASS with the existing 50-person-row custody warning. The exact upstream producer commit was not independently reconstructed from the cloud review and is therefore not invented here.
- Regional IPC: `indec-ipc-regional-divisions-v1-2809f9093513-d84ce096c28f`, producer commit `eccf1a6cabfff3f09e69871fca2cda9f1e1ad36f`, P1 PASS.
- Official basket parent: `regional-baskets-v2-price-fb884d2b770bbe6f`, manifest `5b3b8b035615b4c8087f6cad9240f15add6eba2a39fea0794aefa6dd427a2c86`.
- Clipped Artifact A: `engel-reference-83557070694b9306`, manifest `69f3c38e2295b0c6c3c924db4bc6ead61b11b07e4b12df5fcab68b8767fbf1d7`; G1/G2 PASS, G3/G4 diagnostic.
- Clipped Artifact B: `engel-sensitivity-10ec46dfd65c0d21`, manifest `f5bcab3823b51a337d10faecce611c3c6ff78f584eca2ba9ade94e808ce165f3`; P/A/G5 PASS and M PASS with documented approximations.

PR #26 correctly made the 1,000 negative rows and two hierarchy fallbacks observable, but its clipping convention is superseded for the primary method.

## Signed-sales primary pair

- Artifact A: `engel-reference-080d0d1bdf25fd2f`, manifest `b3b24b76da2664de73dd16e210d60c2ecdd21670e5b7afddb709a4b7327e32ff`; G1/G2 PASS, G3/G4 diagnostic.
- Artifact B: `engel-sensitivity-95d0632b226c375d`; P/A/G5 PASS and M PASS with documented approximations.
- 1,000 signed sales rows remain in source accounting; they are 1.846% of the purchases-only counterfactual.
- Inside the selected p29–p48 cohort: 142 negative rows, signed total -913,904.
- National food share moved 0.272523 → 0.275894 and national ICE 3.669412 → 3.624574 (-1.22%) versus the clipped sensitivity.
- Level factors fell in all six regions; trajectory ranges changed only slightly. The largest-divergence month changed only for Noreste (2025-10 → 2025-07).

The Artifact-B manifest hash was not included in the local agent notification. Downstream consumers must hash the local immutable manifest directly rather than inventing it.

## Classification of findings

| Finding | Classification | Disposition |
| --- | --- | --- |
| 1,000 negative `monto` rows | methodological/source-semantic issue | preserve their sign in the primary method; retain clipping as sensitivity |
| two article codes absent from article catalogue but with valid division/group hierarchy | source-data limitation | transparent hierarchy fallback is acceptable; continue fail-closed if hierarchy is unavailable |
| COICOP02 prices alcohol and tobacco together | price-resolution approximation | retain explicit warning; food/non-food identity remains separate |
| COICOP11 prices restaurants and hotels together | price-resolution approximation | retain explicit warning |
| replicate-weight intervals | sampling uncertainty | retain as G4 diagnostic |
| differences from CEDLAS/Sigaut-Gravina levels | external-study methodological difference | validation/falsification only; never tune weights or mappings to match |

## External plausibility

The clipped run moves all six base CBT levels upward relative to the incumbent official line: level factors range from about 1.35 to 1.50. Directionally this agrees with published ENGHo-2017/18 exercises that find a more demanding total basket when food has a smaller budget share.

The levels are not an exact replication target. CEDLAS DT 370 uses households with low/very-low educational climate rather than the exact p29-p48 cohort, fixes May 2018 as the base, and reports a national inverse Engel coefficient of about 2.86 with regional values 2.65–3.24. Its regional values are constructed by preserving older regional/national relative ratios. Our primary design instead selects p29-p48 nationally and estimates regional expenditure structures directly. Restaurant and alcohol/tobacco treatment also differs.

The unusually large clipped-run level factors therefore warrant the signed-sales rerun before scientific freeze. That is a falsification check, not parameter tuning.

## What is already established

The following mechanisms are commissioned:

```text
ENGHo immutable parent handoff                 PASS
national weighted p29-p48 selection           PASS
article accounting / food conventions         PASS with 2 transparent hierarchy fallbacks
replicate-weight uncertainty machinery         diagnostic and operational
regional INDEC division price surface          P1 PASS
Phase-B level/trajectory arithmetic            PASS
division contribution reconciliation           PASS
three threshold-path identities                PASS
```

No poverty rate, EPH classification, Census inference, province/department estimate, or Atlas change was performed.

## Hard-stop status

```text
ENGHo acquisition/republication              commissioned by local M1 receipt
INDEC regional division price surface       commissioned
p29-p48 Engel reference machinery           commissioned
regional ENGHo17 ICE machinery              commissioned
level/trajectory decomposition              commissioned
clipped alternative threshold paths         diagnostic sensitivity
primary signed-sales threshold paths        COMMISSIONED CANDIDATE / DIAGNOSTIC
```

No further upstream ENGHo/Engel methodological work is required before handing the **candidate/diagnostic** signed-sales threshold paths to Poverty for a separately authorized observed-EPH ablation.
