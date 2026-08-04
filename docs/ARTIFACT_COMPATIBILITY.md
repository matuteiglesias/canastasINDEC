# Regional basket compatibility declaration

Fixture and future candidate envelopes use `research-artifact-manifest/v1`. Their basket-specific artifact identity must distinguish observed nominal (`publicdata.regional-baskets-observed/v1`), analytical derived (`research.regional-baskets-derived/v1`), and monetary-reference (`research.regional-baskets-monetary-reference/v1`) products.

`scripts/validate_release.py` is the standard-library preflight. It verifies schema and lifecycle status, safe relative paths and SHA-256 identities, dictionary identity, coverage, units, immutable price-artifact identity, cell vocabulary, observed source IDs, unique cell keys, complete region-period-measure pairs, and CBA ≤ CBT. `--approved` additionally rejects a non-approved manifest and any status outside its declared approved policy. Promotion among `synthetic`, `candidate`, `reviewed`, and `approved` is exclusively human-controlled.

The present real files cannot pass this release contract: they lack immutable source and price identities, cell source IDs, and one common run envelope. Snapshot checks remain useful but do not establish officiality, currency, or methodological approval.
