#!/bin/bash
# Linting tools for CFD Trading Bot
# Run: ./lint.sh

set -e

echo "Running linting tools..."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track errors
ERRORS=0

# Function to run a linting tool
run_lint() {
    local name="$1"
    local cmd="$2"
    echo -n "Running $name... "
    if eval "$cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${RED}FAILED${NC}"
        eval "$cmd" 2>&1 || true
        ERRORS=$((ERRORS + 1))
    fi
}

# Function to run with output
run_lint_output() {
    local name="$1"
    local cmd="$2"
    echo -e "\n${YELLOW}=== $name ===${NC}"
    eval "$cmd" 2>&1 || true
}

echo -e "\n${YELLOW}=== Quick syntax checks (fast) ===${NC}"

# Fast: Syntax and import errors only
run_lint "flake8 (syntax)" "cd backend && python -m flake8 --select=E9,F63,F7,F82 --exclude=venv,temporary,.venv"

# Fast: Black check
run_lint "black (format)" "cd backend && python -m black --check --exclude='venv|temporary' ."

# Fast: isort check
run_lint "isort (imports)" "cd backend && python -m isort --check-only --diff --skip-gitignore ."

echo -e "\n${YELLOW}=== Full linting (slower) ===${NC}"

# Slower: Full flake8
run_lint_output "flake8 (full)" "cd backend && python -m flake8 --exclude=venv,temporary,.venv"

# Pylint
run_lint_output "pylint" "cd backend && python -m pylint --disable=C0111,C0103,R0903,R0913,R0914 --good-names=i,j,k,ex,_,db *.py 2>/dev/null || true"

# Mypy (type checking)
run_lint_output "mypy" "cd backend && python -m mypy --ignore-missing-imports --exclude='venv|temporary|docker' . 2>/dev/null || true"

# Pyright
run_lint_output "pyright" "cd backend && python -m pyright . 2>/dev/null || true"

echo -e "\n${YELLOW}=== Summary ===${NC}"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}All quick checks passed!${NC}"
else
    echo -e "${RED}$ERRORS quick checks failed${NC}"
fi

echo -e "\nTo run individually:"
echo "  flake8 --select=E9,F63,F7,F82 ."
echo "  flake8 ."
echo "  pylint *.py"
echo "  mypy ."
echo "  pyright ."
echo "  black ."
echo "  isort . -c"
