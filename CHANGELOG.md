# Changelog

All notable changes to this project are documented here, in the
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format.

## [Unreleased]

### Added
- `docs/internal/architecture.md`: architecture doc and diagram. (2026-11-09)
- `docs/compatibility.md`: results from filling the IRS W-9 and Form 1040.

### Security
- A template can no longer make docutemplate embed a local image file the caller did not
  supply: docutemplate reads an image path only when the data holds that path, and raises
  `FieldError` for any other path a tooltip renders. (2026-11-11)
- A template can no longer read or embed a file through a `Path` in the data
  (`{{ picture.with_name('other.png').read_bytes() }}`): docutemplate blocks a template's
  access to the attributes and methods of a path object. (2026-11-11)
- A crafted PDF whose fields form a `/Parent` cycle no longer hangs `fill`. (2026-11-11)
- Raise dependency floors past releases with published advisories: `pypdf>=6.21.4` and
  `Pillow>=13`, the latter now a core requirement (PyPDFForm installs it in any case).
  (2026-11-11)

### Changed
- docutemplate rejects an image template that builds a path (`{{ folder }}/photo.png`)
  unless the data also holds the finished path; pass the full path, a `Path` or the image
  bytes in the data instead. (2026-11-11)
- A template can print or pass on a `Path` from the data but can no longer read its
  attributes (`{{ picture.name }}`); pass those values in the data instead. (2026-11-11)
- Pillow is installed with the package; the `images` extra remains as an alias and
  installs the same packages. (2026-11-11)
- README: a new paragraph in the image section says which rendered paths docutemplate
  reads (a path the data holds as a string or `Path`, in a dict, list or tuple), because it
  now refuses any other path; a new PDF security section says what docutemplate blocks
  in a template, what it trusts in the data and which limits it leaves to the caller (a
  timeout and a memory cap on a separate process); and a line under the install commands
  says Pillow comes with the package. No existing README line changes. (2026-11-11)

### Fixed
- Pin `pypdf<7`: a fresh install resolved pypdf 7, which broke image and signature stamping.
- Filling a hybrid XFA/AcroForm PDF (such as IRS forms) now removes the XFA data, so Acrobat
  shows the filled values instead of the stale XFA copy. (2026-11-09)

## [0.1.0]

### Added
- Fill PDF forms from Jinja templates stored in field tooltips: `fill` and `inspect` API,
  `docutemplate` CLI with JSON and CSV data, checkboxes, radios, choices, hierarchical
  fields, image stamping and flattening.
