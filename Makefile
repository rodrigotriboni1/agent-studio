.DEFAULT_GOAL := help
.PHONY: help dev install db-up db-down api examples test lint typecheck check ui-install ui-dev

VENV ?= .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

$(VENV):  ## Create virtualenv
	python3 -m venv $(VENV)

install: $(VENV) ## Install project + all extras (runtime, rag, mcp, dev)
	$(PIP) install -U pip
	$(PIP) install -e ".[runtime,rag,mcp,dev]"

dev: install db-up ## One-shot dev bootstrap: deps + Postgres/pgvector up
	@echo "agent-studio dev environment ready. Run 'make examples' to see the 3 demos."

db-up: ## Start Postgres + pgvector (docker compose)
	docker compose up -d db
	@echo "waiting for postgres..." && sleep 3

db-down: ## Stop the database
	docker compose down

api: ## Run the FastAPI server (http://localhost:8000)
	$(VENV)/bin/uvicorn api.main:app --reload --port 8000

examples: ## Run the 3 reference examples (agent, RAG, workflow)
	$(PY) -m examples.run_all

test: ## Run the test suite
	$(VENV)/bin/pytest -q

lint: ## Lint with ruff
	$(VENV)/bin/ruff check .

typecheck: ## Type-check with mypy
	$(VENV)/bin/mypy core seams api

check: lint typecheck test ## Full quality gate (used by CI + ralph)

ui-install: ## Install builder UI deps
	cd builder && pnpm install

ui-dev: ## Run the builder UI (http://localhost:5173)
	cd builder && pnpm dev
