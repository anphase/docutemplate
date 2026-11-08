# Compatibility with real-world forms

What `docutemplate` fills, checked against forms from outside its own test suite.
Fixtures in `tests/` are generated locally; the forms below were downloaded, filled
and read back with pypdf, and are not stored in the repository.

## Tested

| Form | Source | Result |
| --- | --- | --- |
| IRS Form W-9 (`fw9.pdf`) | irs.gov, US public domain | 15 text and 8 checkbox fields found; all fill, every value reads back, checked boxes get an on-state appearance. |
| IRS Form 1040 (`f1040.pdf`) | irs.gov, US public domain | 126 text and 73 checkbox fields found; all fill and read back, flatten works. |

Both are hybrid XFA/AcroForm files from Adobe LiveCycle with deeply nested names such as
`topmostSubform[0].Page1[0].f1_01[0]`. Use those full names as `data` keys.

## Gaps found and fixed

- **XFA data wins in Acrobat.** Hybrid XFA forms carry a second copy of the form data, and
  Acrobat shows that copy instead of the AcroForm values, so a filled form looked blank.
  `fill` now removes the `/XFA` entry (the result is a plain AcroForm); `flatten=True`
  already dropped the whole AcroForm.

## Known limits

- Text longer than a field's `/MaxLen` is truncated by the PDF backend, which prints a
  `Length of text ... exceeds maximum length` line to stdout. The stored value is not cut.
- Government forms rarely carry template tooltips (`/TU` holds help prose, which is ignored),
  so fill them by field name from JSON or CSV, or add templates with a PDF editor.
- Pure XFA forms (no AcroForm fields) have nothing to fill and are not supported.

## Not yet tested

- **Adobe Acrobat** and **LibreOffice Writer** exports: neither application was available on
  the machine used for this pass. Their generated files use the same AcroForm structures
  covered by the fixtures (flat and hierarchical names, `/Opt` choice pairs, radio kids),
  but a real export has not been run. Contributions of such a file with a bug report are welcome.

## Dependency note

`pypdf` 7 removed an API PyPDFForm 3.5 uses for image stamping, so image and signature
fields failed with a fresh install. `pypdf` is now declared directly as `>=5,<7`.
