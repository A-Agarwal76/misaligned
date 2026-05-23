# ============================================================
# ASEF — AI Safety Evaluation Framework
# ============================================================
# WARNING: This framework is for defensive AI alignment research
# only. Do not use for offensive purposes.
# ============================================================

.PHONY: install test lint format run docker-build docker-up docker-down \
        generate-datasets run-eval clean help

PYTHON   ?= python
PIP      ?= pip
PYTEST   ?= pytest
RUFF     ?= ruff
MYPY     ?= mypy
UVICORN  ?= uvicorn

API_HOST ?= 0.0.0.0
API_PORT ?= 8000

# ---- Default target ----
help: ## Show this help message
	@echo "ASEF — AI Safety Evaluation Framework"
	@echo "======================================"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ---- Setup ----
install: ## Install package in editable mode with dev dependencies
	$(PIP) install -e ".[dev]"

# ---- Quality ----
test: ## Run test suite with coverage
	$(PYTEST) tests/ -v --cov=asef

lint: ## Run linters (ruff + mypy)
	$(RUFF) check asef/
	$(MYPY) asef/

format: ## Auto-format code with ruff
	$(RUFF) format asef/

# ---- Run ----
run: ## Start the API server with hot-reload
	$(UVICORN) asef.main:app --reload --host $(API_HOST) --port $(API_PORT)

# ---- Docker ----
docker-build: ## Build Docker images via docker-compose
	docker-compose build

docker-up: ## Start all services in background
	docker-compose up -d

docker-down: ## Stop all services
	docker-compose down

# ---- Scripts ----
generate-datasets: ## Generate synthetic evaluation datasets
	$(PYTHON) scripts/generate_datasets.py

run-eval: ## Run a full evaluation sweep
	$(PYTHON) scripts/run_evaluation.py

# ---- Housekeeping ----
clean: ## Remove caches, compiled files, and local databases
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.db" -delete 2>/dev/null || true
	find . -type f -name "*.sqlite" -delete 2>/dev/null || true
	rm -rf build/ dist/ htmlcov/ .coverage
	@echo "Cleaned."
