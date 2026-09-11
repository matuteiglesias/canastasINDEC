# Basket lineage repair: accepted Q3 parent vs current main

This repository must not replace an accepted poverty-input basket merely because a newer producer can emit a 2024-Q3 slice.

The battle-tested Q8/Q3 parent is currently identified by:

```
SHA-256 114efe353c98bd875bfef882d13a636df32ab92c930c985fe967062d6d0cb002
```

The comparison command intentionally answers a narrower question first: **does current main change the monetary input actually used for 2024-Q3 poverty measurement?**

Run from the repository root:

```bash
tools/compare_q3_basket_lineage.sh
```

The command refuses to proceed if the accepted working artifact no longer has the pinned SHA. It reads the candidate directly from `origin/main` without modifying the worktree and emits a JSON report.

## Classification

- **A — byte/serialization only:** the full scientific CSV table is identical after harmless serialization normalization.
- **B — metadata lineage only:** the full scientific table is identical, but supplied manifests differ.
- **C — scientifically equivalent target values, different parent:** the 2024-Q3 six-region CBA/CBT values are identical, but the broader artifact/lineage differs.
- **D — materially different monetary input:** one or more 2024-Q3 regional CBA/CBT values differ.

No class automatically authorizes replacement of the accepted parent. In particular, A/B/C establish increasing forms of equivalence; promotion is still an explicit release decision. D requires a new scientific run if the candidate is intentionally adopted.

## What the report preserves

The report records raw SHA-256 values, normalized full-table digests, the exact target-period six-region CBA/CBT values, numerical deltas when values differ, and optional JSON-manifest diffs. It always writes `promotion_authorized: false`.

## Historical accepted input

Prior evidence identified the accepted local artifact as `data/CB_Reg_defl_Q.csv`, expressed on the repository's 2016-01 reference scale. For 2024-Q3 the six regions were all present. The battle test used this accepted lineage; this tool exists so repository hygiene cannot silently substitute a different monetary parent.
