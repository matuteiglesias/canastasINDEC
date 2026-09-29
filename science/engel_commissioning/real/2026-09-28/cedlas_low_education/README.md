# CEDLAS DT370 low-education provenance

This directory contains the aggregate-only real-data provenance outputs used
by the 2026-09-28 CEDLAS DT370 forensic run.

Parent ENGHo release: `engho-2017-2018-ff05578d65ae`.

The run excludes eight low-education households with `gastot <= 0` from
expenditure-share denominators because their expenditure share is undefined
(four `clima_educativo=1`, four `clima_educativo=2`). Their counts, weights,
and signed totals are recorded in `qa.json` and `receipt.json`. This is a
diagnostic warning, not a respondent-level output or an imputation.

All files here are aggregate summaries. No household identifiers or raw
microdata are committed.

Key outputs:

- `national_reference_variants.csv`
- `regional_reference_variants.csv`
- `division02_alcohol_tobacco_split.csv`
- `division02_split_summary.json`
- `qa.json`
- `receipt.json`
