# Basket methodology decisions required from Matías

| Decision | Current evidence | Consequence if unresolved |
|---|---|---|
| Official source vintage and license | Live datasets 445.1/446.1; no retained bytes, retrieval timestamp, checksum, or rights note | Cannot identify `observed` cells or issue an immutable source artifact. |
| Region definitions/mapping | Six lowercase IDs match committed tables; script notes source spelling differences | Joining is mechanically canonical but not methodologically approved. |
| Missing regions/cells | Generic column-mean fill after reindexing; no missingness log | Cannot distinguish absent history, missing region, or isolated missing measure; approval blocked. |
| Monthly/quarterly convention | Calendar-quarter mean labelled on middle-month day 15 | Consumer must approve aggregation and representative-date convention. |
| Imputation | Full-column mean, including later periods, supplies missing history | Creates non-causal backcast; whether acceptable is an authority decision. |
| Historical backcast | IPC calendar extends output to 2003 although regional nominal source begins 2016-04 | Pre-source cells cannot be represented as observations. |
| Projection/synthetic extension | Repeated tail begins 2025-08; IPC projection history unavailable | Candidate must exclude or explicitly allow these cells. |
| Nominal vs reference values | Outputs mix January-2016, quarter-current, January-2023, and execution-month references | Select a stable output contract; do not infer it from file names. |
| Price dependency | Mutable IPC GitHub paths; no revision/hash or observed/projected boundary | Monetary transformation cannot be reproduced or approved. |
| Ordering validation | Current and fixture checks require positive CBA ≤ CBT | Confirm whether equality/exception policy and rounding are acceptable. |
| Publication/use | Repository is a derived historical producer, not official authority | Candidate must retain warnings; no poverty classification or official-current claim. |

No choice is made here. Changing any item requires a separate methodology-approved task and, where applicable, a compatibility packet for the upstream price producer or downstream poverty consumer.
