PY ?= python3
SOURCE_LOCK ?= run/source_lock.json
BASKET_SOURCE_RUNTIME_LOCK ?= run/source_lock.runtime.json
BASKET_SOURCE_SNAPSHOTS ?= run/source_snapshots
ENGHO_RELEASE ?=
ENGHO_UPSTREAM_RECEIPT ?=
ENGEL_REFERENCE_OUTPUT ?= artifacts/engel_reference
ENGEL_COMMISSION_OUTPUT ?= artifacts/engel_commissioning
ENGEL_BENCHMARKS ?= science/engel_commissioning/benchmarks/registry.json

.PHONY: help check smoke regenerate release-fixture release-check basket-lineage-report basket-source-probe basket-source-lock basket-source-lock-check basket-candidate basket-candidate-check basket-candidate-smoke basket-candidate-v2 basket-candidate-v2-check poverty-basket-2024q1 poverty-basket-2024q1-check poverty-basket-2024q1-v2 poverty-basket-2024q1-v2-check candidate-fixtures engel-reference-test engel-reference-build engel-reference-check engel-reference-commission

help:
	@echo "canastasINDEC command surface"
	@echo ""
	@echo "  make check       Verify the committed derived snapshot and Phase-A unit contracts offline"
	@echo "  make smoke       Alias for the bounded offline snapshot check"
	@echo "  make regenerate  Attempt source-dependent basket regeneration"
	@echo "  make release-fixture       Rebuild the deterministic synthetic fixture"
	@echo "  make release-check         Validate the synthetic release and negative case"
	@echo "  make basket-lineage-report Report committed lineage/status counts offline"
	@echo "  make basket-source-probe    Probe both official source distributions"
	@echo "  make basket-source-lock     Download and pin both official sources into one relocatable lock bundle"
	@echo "  make basket-candidate       Build legacy-compatible candidate from copied PRICE_RELEASE"
	@echo "  make basket-candidate-v2    Build opt-in candidate from copied IPC v2 conversion release"
	@echo "  make basket-candidate-check Validate legacy-compatible RELEASE_DIR offline"
	@echo "  make basket-candidate-v2-check Validate IPC-v2 RELEASE_DIR offline"
	@echo "  make engel-reference-test   Run bounded synthetic ENGHo/Engel Phase-A tests"
	@echo "  make engel-reference-build  Build Artifact A from immutable ENGHO_RELEASE"
	@echo "  make engel-reference-check  Validate RELEASE_DIR as Artifact A"
	@echo "  make engel-reference-commission Run G1-G4 commissioning on RELEASE_DIR"
	@echo ""
	@echo "Regeneration depends on IPC-Argentina and external source compatibility."

check:
	$(PY) scripts/verify_snapshot.py
	PYTHONPATH=.:tests $(PY) -m unittest discover -s tests -p 'test_engel_reference.py' -v

smoke: check

engel-reference-test:
	PYTHONPATH=.:tests $(PY) -m unittest discover -s tests -p 'test_engel_reference.py' -v

engel-reference-build:
	@test -n "$(ENGHO_RELEASE)" || (echo "ENGHO_RELEASE is required" >&2; exit 2)
	$(PY) -m basket_release.engel build-reference --engho-release "$(ENGHO_RELEASE)" --output "$(ENGEL_REFERENCE_OUTPUT)" $(if $(ENGHO_UPSTREAM_RECEIPT),--upstream-receipt "$(ENGHO_UPSTREAM_RECEIPT)",)

engel-reference-check:
	@test -n "$(RELEASE_DIR)" || (echo "RELEASE_DIR is required" >&2; exit 2)
	$(PY) -m basket_release.engel validate-reference "$(RELEASE_DIR)"

engel-reference-commission:
	@test -n "$(RELEASE_DIR)" || (echo "RELEASE_DIR is required" >&2; exit 2)
	$(PY) -m basket_release.engel commission-reference --release "$(RELEASE_DIR)" --output "$(ENGEL_COMMISSION_OUTPUT)" --benchmarks "$(ENGEL_BENCHMARKS)"

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
	rm -rf "$(BASKET_SOURCE_SNAPSHOTS)" "$(BASKET_SOURCE_RUNTIME_LOCK)" "$(SOURCE_LOCK)"
	mkdir -p "$$(dirname "$(SOURCE_LOCK)")"
	$(PY) -m basket_release source-lock --cache "$(BASKET_SOURCE_SNAPSHOTS)" --lock "$(BASKET_SOURCE_RUNTIME_LOCK)"
	PYTHONPATH=. $(PY) scripts/portable_source_lock.py export --runtime "$(BASKET_SOURCE_RUNTIME_LOCK)" --output "$(SOURCE_LOCK)"
	rm -f "$(BASKET_SOURCE_RUNTIME_LOCK)"

basket-source-lock-check:
	PYTHONPATH=. $(PY) scripts/portable_source_lock.py check --lock "$(SOURCE_LOCK)"

basket-candidate:
	@test -n "$(PRICE_RELEASE)" || (echo "PRICE_RELEASE is required; SOURCE_LOCK defaults to $(SOURCE_LOCK)" >&2; exit 2)
	$(PY) -m basket_release build --source-lock $(SOURCE_LOCK) --price-release $(PRICE_RELEASE)

basket-candidate-check:
	@test -n "$(RELEASE_DIR)" || (echo "RELEASE_DIR is required" >&2; exit 2)
	$(PY) -m basket_release validate $(RELEASE_DIR)

basket-candidate-smoke: basket-candidate-check

basket-candidate-v2:
	@test -n "$(PRICE_RELEASE)" || (echo "PRICE_RELEASE must be a copied immutable research.argentina-monetary-conversion/v1 release" >&2; exit 2)
	$(PY) -m basket_release build-v2 --source-lock "$(SOURCE_LOCK)" --price-release "$(PRICE_RELEASE)" $(if $(filter 1 true yes,$(ALLOW_THIN_PRICE_COVERAGE)),--allow-thin-price-coverage,)

basket-candidate-v2-check:
	@test -n "$(RELEASE_DIR)" || (echo "RELEASE_DIR is required" >&2; exit 2)
	$(PY) -m basket_release validate-v2 "$(RELEASE_DIR)"

poverty-basket-2024q1:
	@test -n "$(RELEASE_DIR)" || (echo "RELEASE_DIR is required" >&2; exit 2)
	$(PY) -m basket_release integration $(RELEASE_DIR)

poverty-basket-2024q1-check:
	@test -n "$(BUNDLE_DIR)" || (echo "BUNDLE_DIR is required" >&2; exit 2)
	$(PY) -m basket_release validate $(BUNDLE_DIR)

poverty-basket-2024q1-v2:
	@test -n "$(RELEASE_DIR)" || (echo "RELEASE_DIR is required" >&2; exit 2)
	$(PY) -m basket_release integration-v2 "$(RELEASE_DIR)"

poverty-basket-2024q1-v2-check:
	@test -n "$(BUNDLE_DIR)" || (echo "BUNDLE_DIR is required" >&2; exit 2)
	$(PY) -m basket_release validate-v2 "$(BUNDLE_DIR)"

candidate-fixtures:
	$(PY) scripts/build_candidate_fixtures.py

regenerate:
	$(PY) computar_canastas.py
