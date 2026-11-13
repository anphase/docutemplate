#!/bin/sh
# Full local gate: scripts/check.sh (ruff, mypy, pytest) with the coverage floor and the
# cyclomatic-complexity ceiling recorded in docs/quality/baseline.md. These numbers only
# ever move in the improving direction: raise MIN_COVERAGE or lower MAX_CC when the code
# improves, and update the baseline doc in the same change.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
if [ -d .venv ]; then
    PATH="$PWD/.venv/bin:$PATH"
    export PATH
fi

MIN_COVERAGE=98
MAX_CC=22

scripts/check.sh --cov-fail-under="$MIN_COVERAGE" "$@"
python -m ruff check --select C901 --config "lint.mccabe.max-complexity=$MAX_CC" src tests
echo "ci-local: ok (coverage >= ${MIN_COVERAGE}%, complexity <= ${MAX_CC})"
