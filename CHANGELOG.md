# Changelog

All notable changes to this project are documented here, in the
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.

## [Unreleased]

### Added
- `fill_many` (batch fill that reads the form once and returns a result or error per row) and
  `schema` (JSON Schema of the data a form accepts), for Doculate's template hub. (2026-11-12)
- `docs/quality/baseline.md` records coverage (98%) and cyclomatic-complexity (Ruff C901 max 22)
  baselines; `scripts/ci-local.sh` gates both and only ratchets upward. (2026-11-09)
- `docs/compatibility.md`: results from filling the IRS W-9 and Form 1040.

### Removed
- Internal architecture notes (`docs/internal/`) from the repository. (2026-11-12)

### Fixed
- Pin `pypdf<7`: a fresh install resolved pypdf 7, which broke image and signature stamping.
- Filling a hybrid XFA/AcroForm PDF (such as IRS forms) now removes the XFA data, so Acrobat
  shows the filled values instead of the stale XFA copy. (2026-11-09)

## [0.1.0]

### Added
- Fill PDF forms from Jinja templates stored in field tooltips: `fill` and `inspect` API,
  `docutemplate` CLI with JSON and CSV data, checkboxes, radios, choices, hierarchical
  fields, image stamping and flattening.
