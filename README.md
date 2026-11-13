# docutemplate

Fill PDF forms with Jinja templates stored inside the form. Put `{{ customer.name }}`
in a field's tooltip (`/TU`, its alternate field name), then pass your data to
`docutemplate.fill`. The PDF carries its own mapping; there is no separate mapping
file to keep in sync. Built with PyPDFForm and Jinja2, with no pdftk executable.
Python 3.11 or newer is required. The supported PyPDFForm 3.5 release line
uses its Python PDF backend for filling and appearance generation.

```sh
pip install docutemplate
# For image and handwritten signature fields:
pip install 'docutemplate[images]'
```

docutemplate installs Pillow by default, so the first command supports image and
signature fields; `docutemplate[images]` installs the same packages.

## A 10-line example

Create a fillable `application.pdf` with `{{ customer.name }}` in the name field's
tooltip and `{{ customer.member }}` in a checkbox's tooltip:

```python
from pathlib import Path
from docutemplate import fill

data = {
    "customer": {"name": "Ada Lovelace", "member": True},
}
template = Path("application.pdf")
output = fill(template, data)
Path("completed.pdf").write_bytes(output)
print("Saved completed.pdf")
```

## Put a template in a tooltip

**Adobe Acrobat:** Open **Prepare a form**, add or select a field, then open its
**Properties**. In **General**, give it a unique **Name** and enter a Jinja template
in **Tooltip**. For example, `{{ first_name }} {{ last_name | upper }}`. Save the
fillable PDF. See Adobe's [form field properties guide](https://helpx.adobe.com/acrobat/using/manage-form-field-properties.html).

**LibreOffice Writer:** Enable **View → Toolbars → Form Controls**, turn on
**Design Mode**, and insert a control. Open its **Control Properties** and set
**Name** and **Help text** on the **General** tab. Put the Jinja template in
**Help text**. Choose **File → Export As → Export as PDF** and enable **Create
PDF form**. Save the editable Writer document for future changes. See the
[LibreOffice forms guide](https://books.libreoffice.org/en/WG262/WG26218-Forms.html).
Export behavior varies by control and version; run `docutemplate inspect` to
confirm that the template reached the PDF's `/TU` entry.

Any editor that writes AcroForm fields and their `/TU` tooltips can prepare a
form. Templates support expressions, filters, loops, conditionals, and comments.
A tooltip is a template if it contains `{{`, `{%`, or `{#`; ordinary tooltip prose
is left alone. Tooltip templates remain visible to PDF readers, so keep useful
visible labels on the form.

## Python API

```python
import docutemplate

pdf_bytes = docutemplate.fill("form.pdf", {"first_name": "Ada"})
flat_bytes = docutemplate.fill("form.pdf", {"first_name": "Ada"}, flatten=True)
fields = docutemplate.inspect("form.pdf")
```

`fill(template_pdf, data, *, flatten=False, strict=True) -> bytes` accepts a file
path (`str` or `Path`), PDF bytes, or an open binary stream. Streams are read from
their current position. `data` is a mapping with string keys. Nested dictionaries
work with Jinja's dot or bracket syntax. The input PDF and data are not modified.

| Field | Value |
| --- | --- |
| Text | Rendered string; HTML characters are preserved. |
| Checkbox | False for empty/whitespace, `false`, `0`, `no`, `off`, `none`, or `null` (case insensitive); other rendered strings are true. Direct data values use Python truthiness, with the same string rules. |
| Radio | Rendered export option, as listed by `inspect`; matching is case sensitive. |
| Choice/dropdown | Rendered export option; PyPDFForm can add new options. |
| Image/signature | Image path or bytes, as described below. |

Fields without templates take `data[field_name]` if supplied, otherwise keep their
existing value. A template takes priority over a same-name data entry. `None`
clears text/choice fields and skips image fields. `flatten=True` makes the result
non-interactive and preserves its visible contents.

`inspect(template_pdf) -> list[FieldInfo]` returns JSON-compatible dictionaries:

```json
[
  {"name": "name", "type": "text", "template": "{{ customer.name }}", "options": []},
  {"name": "contact", "type": "radio", "template": "{{ contact }}", "options": ["email", "post"]}
]
```

Types are `text`, `checkbox`, `radio`, `choice`, `image`, `signature`, or `unknown`.
`template` is `null` when there is no Jinja template; `options` contains export
values for radio and choice fields, and is empty for other types. Hierarchical
fields use their fully qualified names, such as `customer.name`.

### Batches and validation

`fill_many(template_pdf, rows, *, flatten=False, strict=True)` reads the form once and
returns one item per row: the filled PDF bytes, or that row's `DocutemplateError`, so one
bad row does not block the rest.

`schema(template_pdf)` returns a JSON Schema object for the data a form accepts: variables
used by tooltip templates are required, and fields without templates are optional keys typed
by field type (boolean for checkboxes, an enum for radio options, string otherwise). Validate
rows against it before calling `fill`.

### Images and handwritten signatures

Install the `images` extra. Set the tooltip to a single expression such as
`{{ signature_image }}` and pass `{"signature_image": Path("signature.png")}` or
`{"signature_image": image_bytes}`. Single expressions retain the original path
or bytes. More complex templates can render a path or the name of a top-level
data key containing the image. Fields without templates also accept paths or
bytes directly by field name. A blank or `None` image is skipped. Signature
fields stamp a handwritten image; they do not create cryptographic signatures.

docutemplate accepts a rendered image path when it matches a string or `Path`
value in your data, including values nested in dicts, lists or tuples. docutemplate also uses a
rendered string to select a top-level data key containing an image path or bytes.
docutemplate raises `FieldError` for any other rendered image path.

Pushbutton fields (`/FT /Btn` with the pushbutton flag) are treated as image
fields. Ordinary AcroForm pushbuttons and PyPDFForm image fields both support
stamping; no special JavaScript action or PyPDFForm marker is required. The
image is drawn into the button's rectangle and the stamped button is removed.
Give each image button a tooltip template or supply its image by field name.

### Errors and template behavior

Templates use `jinja2.sandbox.SandboxedEnvironment` with autoescaping disabled.
`strict=True` uses `StrictUndefined`. Missing variables raise `FieldError` with
the field name and Jinja's variable description; syntax errors also name the
field. Set `strict=False` to use Jinja's ordinary undefined behavior: a missing
value prints as an empty string, though invalid operations can still fail.
Use `default` for optional values: `{{ middle_name | default('') }}`.

Catch `docutemplate.DocutemplateError` for document/template/value errors,
`FieldError` for a particular field (`error.field` gives its name), and `PDFError`
for PDF parsing/filling errors. File access errors remain `OSError` subclasses.
AcroForm PDFs are supported; encrypted PDFs must be decrypted first. XFA-only
forms are not supported. Use trusted data objects; sandboxing restricts template
access but does not impose resource limits on template evaluation.

### PDF security

docutemplate treats PDF templates as untrusted and evaluates them against the
data you pass. It blocks a template's access to attributes whose names start
with an underscore, such as `__class__`, and to the attributes and methods of a
`Path` in your data. docutemplate also detects circular parent references
between fields and stops following those references.

docutemplate trusts the data you pass. docutemplate allows templates to call
public methods on custom data objects, and those calls can change data or
trigger other side effects. docutemplate blocks template calls to mutating
methods on built-in lists, dicts and sets. For forms filled from someone else's data, pass plain strings,
numbers, lists and dicts. docutemplate reads image files from paths supplied in
your data, including paths selected by rendered templates. When your users
supply image or signature values, accept image bytes so they cannot select files
on your machine.

docutemplate sets no time or memory limit on template evaluation or PDF parsing.
When you accept PDFs from others, run each fill in a separate process with a
timeout and a memory cap.

## CLI

```sh
docutemplate inspect FORM.pdf
docutemplate fill FORM.pdf DATA.json -o OUT.pdf
docutemplate fill FORM.pdf DATA.csv -o OUT.pdf --row 2
docutemplate fill FORM.pdf DATA.json -o OUT.pdf --flatten
docutemplate fill FORM.pdf DATA.json -o OUT.pdf --no-strict
python -m docutemplate inspect FORM.pdf
```

`inspect` prints JSON to stdout. JSON input must be an object. CSV input uses its
first row as column names and selects the first data row by default. `--row N`
is **1-based**, excluding the header. CSV values stay strings; use Jinja filters
such as `int` or `float` when needed. UTF-8 input, including a UTF-8 BOM, is
supported. JSON and CSV are the supported input formats. Errors go to stderr
with exit code 2; PDF output is written only after filling succeeds.

## Development

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,images]'
scripts/check.sh
```

The check script uses `.venv` when present and runs Ruff lint/format checks,
strict mypy on the package, and pytest with a 98% branch-coverage threshold.
`scripts/ci-local.sh` runs the same plus the cyclomatic-complexity ceiling; the
baselines and ratchet rules are in `docs/quality/baseline.md`.
Tests build their PDF forms locally and need no network access.

## Credits

docutemplate is inspired by Ram Mehta's pdfjinja (2015, MIT), which introduced keeping Jinja templates in form field tooltips.

[pdfjinja](https://github.com/rammie/pdfjinja) provided the original idea;
docutemplate is an independent implementation using [PyPDFForm](https://github.com/chinapandaman/PyPDFForm)
and [Jinja2](https://jinja.palletsprojects.com/).

## License

MIT. Copyright (c) 2026 anphase. See [LICENSE](LICENSE).
