PY ?= python3

.PHONY: help check smoke regenerate

help:
	@echo "canastasINDEC command surface"
	@echo ""
	@echo "  make check       Verify the committed derived snapshot offline"
	@echo "  make smoke       Alias for the bounded offline snapshot check"
	@echo "  make regenerate  Attempt source-dependent basket regeneration"
	@echo ""
	@echo "Regeneration depends on IPC-Argentina and external source compatibility."

check:
	$(PY) scripts/verify_snapshot.py

smoke: check

regenerate:
	$(PY) computar_canastas.py
