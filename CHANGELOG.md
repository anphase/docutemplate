# Changelog

All notable changes to this project are documented here, in the
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.

## [Unreleased]

### Added
- `docs/internal/architecture.md`: architecture doc and diagram. (2026-11-09)
- `docs/compatibility.md`: results from filling the IRS W-9 and Form 1040.

### Security
- A template can no longer name a local image file to embed in the output: an image path
  is read only when the data holds it, and a literal or assembled path in a tooltip raises
  `FieldError`. (2026-11-11)
- A crafted PDF whose fields form a `/Parent` cycle no longer hangs `fill`. (2026-11-11)
- Raise dependency floors past releases with published advisories: `pypdf>=6.21.4` and
  `Pillow>=13`, the latter now a core requirement (PyPDFForm installs it in any case).
  (2026-11-11)

### Changed
- Image templates that build a path (`{{ folder }}/photo.png`) are rejected; pass the full
  path, a `Path` or the image bytes in the data instead. (2026-11-11)
- Pillow is installed with the package; the `images` extra remains as an alias, so the
  README no longer asks for it in the install and image sections. (2026-11-11)
- README: the image section says what a template may render now that a tooltip cannot
  name a file, and a Security section states what is trusted. (2026-11-11)

### Fixed
- Pin `pypdf<7`: a fresh install resolved pypdf 7, which broke image and signature stamping.
- Filling a hybrid XFA/AcroForm PDF (such as IRS forms) now removes the XFA data, so Acrobat
  shows the filled values instead of the stale XFA copy. (2026-11-09)

## [0.1.0]

### Added
- Fill PDF forms from Jinja templates stored in field tooltips: `fill` and `inspect` API,
  `docutemplate` CLI with JSON and CSV data, checkboxes, radios, choices, hierarchical
  fields, image stamping and flattening.
