PY ?= python3

.PHONY: help check smoke regenerate release-fixture release-check basket-lineage-report

help:
	@echo "canastasINDEC command surface"
	@echo ""
	@echo "  make check       Verify the committed derived snapshot offline"
	@echo "  make smoke       Alias for the bounded offline snapshot check"
	@echo "  make regenerate  Attempt source-dependent basket regeneration"
	@echo "  make release-fixture       Rebuild the deterministic synthetic fixture"
	@echo "  make release-check         Validate the synthetic release and negative case"
	@echo "  make basket-lineage-report Report committed lineage/status counts offline"
	@echo ""
	@echo "Regeneration depends on IPC-Argentina and external source compatibility."

check:
	$(PY) scripts/verify_snapshot.py

smoke: check

release-fixture:
	$(PY) scripts/build_fixture_release.py

release-check: release-fixture
	$(PY) scripts/validate_release.py fixtures/releases/synthetic-baskets/manifest.json
	@! $(PY) scripts/validate_release.py fixtures/releases/tampered-baskets/manifest.json

basket-lineage-report:
	$(PY) scripts/basket_lineage_report.py

regenerate:
	$(PY) computar_canastas.py
