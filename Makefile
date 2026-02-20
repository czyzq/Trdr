# Makefile for CFD Trading Bot
# Usage: make <target>

.PHONY: help lint lint-fast lint-full format check install

help:
	@echo "Available targets:"
	@echo "  lint-fast  - Quick syntax and format checks"
	@echo "  lint-full  - Full linting with all tools"
	@echo "  format     - Auto-format code"
	@echo "  check      - Type checking (mypy, pyright)"
	@echo "  install    - Install dev dependencies"
	@echo "  lint       - Alias for lint-fast"

lint-fast: lint
lint:
	@echo "Running quick checks..."
	@cd backend && python -m flake8 --select=E9,F63,F7,F82 --exclude=venv,temporary,.venv || true
	@cd backend && python -m black --check --exclude='venv|temporary' . || true
	@cd backend && python -m isort --check-only --skip-gitignore . || true
	@echo "Quick checks done!"

lint-full:
	@echo "Running full linting..."
	@cd backend && python -m flake8 --exclude=venv,temporary,.venv || true
	@cd backend && python -m pylint --disable=C0111,C0103,R0903,R0913,R0914 --good-names=i,j,k,ex,_,db . 2>/dev/null || true
	@cd backend && python -m mypy --ignore-missing-imports --exclude='venv|temporary|docker' . 2>/dev/null || true
	@cd backend && python -m pyright . 2>/dev/null || true

format:
	@echo "Formatting code..."
	@cd backend && python -m black . || true
	@cd backend && python -m isort . || true

check:
	@cd backend && python -m mypy --ignore-missing-imports . 2>/dev/null || true
	@cd backend && python -m pyright . 2>/dev/null || true

install:
	@echo "Installing linting tools..."
	@pip install flake8 pylint mypy pyright black isort
