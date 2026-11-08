#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
if [ -d .venv ]; then
    PATH="$PWD/.venv/bin:$PATH"
    export PATH
fi
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest "$@"
