PY ?= python3

.PHONY: help check smoke regenerate release-fixture release-check basket-lineage-report basket-source-probe basket-source-lock basket-source-lock-check basket-candidate basket-candidate-check basket-candidate-smoke poverty-basket-2024q1 poverty-basket-2024q1-check candidate-fixtures

help:
	@echo "canastasINDEC command surface"
	@echo ""
	@echo "  make check       Verify the committed derived snapshot offline"
	@echo "  make smoke       Alias for the bounded offline snapshot check"
	@echo "  make regenerate  Attempt source-dependent basket regeneration"
	@echo "  make release-fixture       Rebuild the deterministic synthetic fixture"
	@echo "  make release-check         Validate the synthetic release and negative case"
	@echo "  make basket-lineage-report Report committed lineage/status counts offline"
	@echo "  make basket-source-probe    Probe both official source distributions"
	@echo "  make basket-source-lock     Download and pin both official sources"
	@echo "  make basket-candidate       Build from SOURCE_LOCK and copied PRICE_RELEASE"
	@echo "  make basket-candidate-check Validate RELEASE_DIR offline"
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

basket-source-probe:
	$(PY) -m basket_release source-probe

basket-source-lock:
	$(PY) -m basket_release source-lock

basket-source-lock-check:
	$(PY) -m basket_release source-lock-check $(SOURCE_LOCK)

basket-candidate:
	@test -n "$(SOURCE_LOCK)" -a -n "$(PRICE_RELEASE)" || (echo "SOURCE_LOCK and copied immutable PRICE_RELEASE are required" >&2; exit 2)
	$(PY) -m basket_release build --source-lock $(SOURCE_LOCK) --price-release $(PRICE_RELEASE)

basket-candidate-check:
	@test -n "$(RELEASE_DIR)" || (echo "RELEASE_DIR is required" >&2; exit 2)
	$(PY) -m basket_release validate $(RELEASE_DIR)

basket-candidate-smoke: basket-candidate-check

poverty-basket-2024q1:
	@test -n "$(RELEASE_DIR)" || (echo "RELEASE_DIR is required" >&2; exit 2)
	$(PY) -m basket_release integration $(RELEASE_DIR)

poverty-basket-2024q1-check:
	@test -n "$(BUNDLE_DIR)" || (echo "BUNDLE_DIR is required" >&2; exit 2)
	$(PY) -m basket_release validate $(BUNDLE_DIR)

candidate-fixtures:
	$(PY) scripts/build_candidate_fixtures.py

regenerate:
	$(PY) computar_canastas.py
