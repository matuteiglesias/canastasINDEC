# Agent guidance

## Repository purpose

This repository preserves a historical analytical transformation of regional CBA/CBT series. It is a derived artifact producer, not an official basket-series authority.

`SYSTEM.yaml`, `README.md`, and `DATA_STATUS.json` define the current boundary. Read them before changing code, data, status language, or commands.

## Authority and interpretation

Matías retains authority over methodology, source selection, downstream use, and publication claims.

Do not describe committed outputs as official observed monthly CBA/CBT values. Preserve the distinctions among:

- source-derived observations;
- deflation and rebasing;
- imputation;
- projected or repeated periods inherited from `IPC-Argentina`;
- the synthetic tail declared in `DATA_STATUS.json`;
- the date a file was generated.

A later artifact date does not prove fresher observed data.

## Safe command surface

These commands have different safety classes:

```bash
make check
make smoke
make regenerate
```

- `make check` and `make smoke` verify the committed snapshot offline. They do not validate the official source or repair the methodology.
- `make regenerate` is source-dependent and may contact external systems, consume projected IPC periods, and replace generated data. Run it only with explicit authorization and after confirming upstream compatibility.

Do not alias regeneration to a generic check, test, or smoke target.

## Data and generated artifacts

Treat these as generated analytical outputs:

- `data/`;
- figures such as `CB.jpg`;
- any regenerated CSV derived from external sources or `IPC-Argentina`.

Do not hand-edit generated values to make a verifier pass. Correct the transformation or status declaration, regenerate intentionally, and record provenance.

Before committing regenerated data, report:

- source and retrieval date;
- upstream IPC snapshot and observed/projected boundary;
- command executed;
- row and period coverage;
- imputation or synthetic-tail behavior;
- representative differences from the previous artifact;
- downstream compatibility implications.

Do not commit large source downloads, credentials, caches, or local environment files.

## Cross-repository boundary

This repository consumes the price-index artifact from `IPC-Argentina` and may feed poverty-estimation work. It does not own either system.

Do not edit sibling repositories from this repository. A required upstream or downstream change must be represented as a separate, explicit compatibility packet.

## Change rules

Keep changes narrow and reviewable.

For documentation or status changes:

- preserve the warning that the main artifact is derived and partly synthetic;
- keep `README.md`, `DATA_STATUS.json`, and `SYSTEM.yaml` semantically aligned;
- do not claim source freshness or methodological correctness without a sourced run.

For code changes:

- prefer a small fixture or the committed snapshot for verification;
- preserve deterministic offline checks;
- add tests for changed transformation semantics where practical;
- avoid broad dependency or notebook modernization.

## Stop conditions

Stop and report rather than guessing when:

- the official source schema or endpoint has changed;
- `IPC-Argentina` contains projected periods whose propagation is unclear;
- the regenerated artifact changes historical values unexpectedly;
- the synthetic-tail boundary no longer matches the declared method;
- downstream consumers require a different unit or methodology;
- source or data licensing is uncertain.

## Completion evidence

A completion report must state:

- files changed;
- commands actually run and their results;
- whether network access or regeneration occurred;
- observed, projected, imputed, and synthetic coverage after the change;
- generated files added or replaced;
- unresolved methodological or rights questions.

Never report successful snapshot verification as proof that the data are official, current, or methodologically repaired.
