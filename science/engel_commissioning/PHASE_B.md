# Engel commissioning — Phase B

Phase B consumes three immutable parents:

1. research.argentina-engel-reference-structure/v1
2. publicdata.indec-ipc-regional-divisions/v1
3. the current research.argentina-regional-baskets/v1 v2 candidate

It does **not** recompute the p29–p48 cohort or article classification. Artifact A is frozen.

## Price system

For region r, division d, month t, define the official regional price relative:

P(r,d,t) / P(r,d,b), with b = 2018-05.

The Phase-A division expenditure shares are fixed at the base. The total cost relative is:

T(r,t) = sum_d s(r,d) * P_rel(r,d,t).

The frozen food scope is not replaced with COICOP01. Its price-evolved cost is:

F(r,t) =
s(r,01) * P_rel(r,01,t)
+ s(r,021) * P_rel(r,02,t).

Alcoholic beverages group 021 remains food under Artifact A and uses the broader COICOP02 regional index. Tobacco group 022 also uses COICOP02 but remains non-food. Restaurants group 111 remain non-food and use COICOP11.

Therefore:

food_share(r,t) = F(r,t) / T(r,t)

ICE17(r,t) = T(r,t) / F(r,t).

This is a fixed-base sensitivity path, not a new official consumption basket.

## Level / trajectory split

Observed official:

ICE_official(r,t) = CBT_official(r,t) / CBA_official(r,t).

Phase B exposes:

level_factor(r) =
ICE17(r,b) / ICE_official(r,b)

trajectory_factor(r,t) =
(ICE17(r,t) / ICE17(r,b))
/
(ICE_official(r,t) / ICE_official(r,b))

full_factor(r,t) =
level_factor(r) * trajectory_factor(r,t).

The diagnostic paths are:

- official: observed official CBT
- engHo17_level_only: official CBT × level factor
- engHo17_level_plus_trajectory: official CBT × full factor

The unchanged official CBA also yields the direct path:

CBT17(r,t) =
CBA_official(r,t) * ICE17(r,t)

which must equal the full-factor path within the contract tolerance.

## Commissioning

Phase B commissioning has four surfaces:

- **P** — exact three-parent identity and complete May-2018–Dec-2025 rectangle
- **A** — arithmetic identities and base normalization
- **M** — complete price mapping with explicit shared-division approximations
- **G5** — level/trajectory observability, regional extrema, largest-divergence month and division contributions

Literature comparisons remain validation evidence only. No literature number is an estimator input.

No poverty operation is authorized by Artifact B.
