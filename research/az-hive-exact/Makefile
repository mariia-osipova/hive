.PHONY: help setup verify live smoke train

PYTHON := .venv/bin/python
OUT ?= runs/manual-$(shell date -u +%Y%m%dT%H%M%SZ)
ALGORITHM ?= mcts
CONFIG ?= nn_architecture/symmetries/4-layers/1

help:
	@echo 'make setup   Install the pinned environment and build original native code'
	@echo 'make verify  Check source identity and fidelity regressions'
	@echo 'make live    Human vs MCTS in the terminal (ALGORITHM=minimax/az-mcts/policy/random)'
	@echo 'make smoke   All five automated algorithms in live games; no training'
	@echo 'make train   Explicitly start original full-budget training later'

setup:
	python3 -m venv .venv
	$(PYTHON) -m pip install -r requirements-macos.lock.txt
	$(PYTHON) scripts/bootstrap.py

verify:
	$(PYTHON) scripts/test_fidelity.py

live:
	$(PYTHON) -u scripts/play_live.py --white human --black $(ALGORITHM) --output $(OUT)

smoke:
	$(PYTHON) -u scripts/play_live.py --suite --output $(OUT)

train:
	$(PYTHON) -u scripts/run_original.py --config $(CONFIG) --output $(OUT)
