# Quality baselines

Measured 2026-11-09 on `src/docutemplate` (Python 3.15, 69 tests passing) with pytest-cov,
Ruff's McCabe check (`C901`) and radon. `scripts/ci-local.sh` fails if coverage drops below
`MIN_COVERAGE` or any function's complexity exceeds `MAX_CC`. Both only move in the improving
direction: raise the floor or lower the ceiling when the numbers improve, and record the new
values here. Never lower the bar.

| Measure | Baseline | Ratchet |
|---|---|---|
| Line + branch coverage (`pytest --cov=docutemplate --cov-branch`) | 98.13% (327 statements, 2 missed; 154 branches, 7 partial) | `MIN_COVERAGE=98` (also `--cov-fail-under` in `pyproject.toml`) |
| Highest cyclomatic complexity, Ruff `C901` | 22 (`core._finalize`) | `MAX_CC=22` |
| Highest cyclomatic complexity, radon | 43 (`core._finalize`, rank F) | not gated (radon is not a dependency) |
| Average cyclomatic complexity, radon | 8.32 (rank B, 19 blocks) | not gated |

## Coverage by file

| File | Cover | Missing |
|---|---|---|
| `core.py` | 98% | lines 99, 143; partial branches 101->96, 114->120, 176->174, 258->256, 287->295 |
| everything else (`__init__`, `__main__`, `cli`, `errors`) | 100% | |

## Functions over the portfolio limit of 10

Ruff and radon count differently (radon also counts boolean operators and comprehensions), so
both are listed. The portfolio standard is 10 per function; these are the ones to split, tests
first, when the code they hold is next touched.

| Function | Ruff `C901` | radon |
|---|---|---|
| `core._finalize` | 22 | 43 |
| `core.fill` | 15 | 21 |
| `core._value` | 11 | 15 |
| `core._inspect` | 10 | 14 |
| `core._field_info` | 9 | 13 |
| `cli._load_data` | 9 | 12 |
| `core._render` | 8 | 10 |

## Gaps

- No mutation testing is configured (no `mutmut` setup); runs that change `core.py` should
  scope one by hand (`mutmut run --paths-to-mutate src/docutemplate/core.py`).
- Six functions exceed the portfolio ceiling of 10; the ratchet holds the line at 22 until
  `_finalize` is split.

Reproduce: `python -m pip install -e '.[dev,images]' radon`, then `scripts/ci-local.sh`,
`python -m ruff check --select C901 --config lint.mccabe.max-complexity=10 src` and
`python -m radon cc -s -a src/docutemplate`.
