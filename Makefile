# Omega Hive Appliance — Makefile
.PHONY: help install dev test lint build clean docker run

PYTHON ?= python3
VENV   ?= .venv
PIP    := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
BUILD  := $(VENV)/bin/python -m build

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

venv: ## Create virtualenv
	$(PYTHON) -m venv $(VENV)

install: venv ## Install package into venv
	$(PIP) install --upgrade pip
	$(PIP) install .

dev: venv ## Install package + dev deps into venv
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

test: ## Run test suite
	$(PYTEST) -v tests/

build: ## Build sdist + wheel
	$(PIP) install --upgrade build
	$(BUILD) --outdir dist/

clean: ## Remove build artifacts
	rm -rf dist/ build/ *.egg-info .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

docker: ## Build Docker image
	docker build -t hive-appliance:latest .

run: ## Run CLI (pass ARGS="observe" etc.)
	$(VENV)/bin/hive-appliance $(ARGS)
