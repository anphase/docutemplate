"""Template evaluation and the PyPDFForm adapter."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from io import BytesIO
from os import PathLike, fspath
from pathlib import Path
from typing import Any, BinaryIO, Literal, TypedDict

from jinja2 import StrictUndefined, TemplateError, Undefined, nodes
from jinja2.sandbox import SandboxedEnvironment
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, TextStringObject
from PyPDFForm import PdfWrapper
from PyPDFForm.middleware.checkbox import Checkbox
from PyPDFForm.middleware.image import Image
from PyPDFForm.middleware.radio import Radio

from .errors import FieldError, PDFError

PdfSource = str | PathLike[str] | bytes | BinaryIO
FieldType = Literal["text", "checkbox", "radio", "choice", "image", "signature", "unknown"]


class FieldInfo(TypedDict):
    """JSON-compatible description of a field; options are export values."""

    name: str
    type: FieldType
    template: str | None
    options: list[str]


def _source_bytes(source: PdfSource) -> bytes:
    if isinstance(source, bytes):
        return source
    if isinstance(source, (str, PathLike)):
        return Path(source).read_bytes()
    return source.read()


def _has_template(tooltip: str) -> bool:
    return any(marker in tooltip for marker in ("{{", "{%", "{#"))


def _field_info(name: str, field: Any) -> FieldInfo:
    # pypdf is PyPDFForm's PDF backend. Read the original dictionaries because
    # PyPDFForm's public schema omits /TU and radio export names.
    kind = str(field.get("/FT", ""))
    flags = int(field.get("/Ff", 0))
    field_type: FieldType = "unknown"
    options: list[str] = []
    if kind == "/Tx":
        field_type = "text"
    elif kind == "/Sig":
        field_type = "signature"
    elif kind == "/Ch":
        field_type = "choice"
        options = [
            str(item[0] if isinstance(item, list) else item) for item in field.get("/Opt", [])
        ]
    elif kind == "/Btn":
        if flags & (1 << 16):
            field_type = "image"
        elif flags & (1 << 15):
            field_type = "radio"
            for ref in field.get("/Kids", []):
                child = ref.get_object()
                states = child.get("/AP", {}).get("/N", {})
                options.extend(str(key)[1:] for key in states if str(key) != "/Off")
        else:
            field_type = "checkbox"
    tooltip = str(field.get("/TU", ""))
    return {
        "name": name,
        "type": field_type,
        "template": tooltip if _has_template(tooltip) else None,
        "options": options,
    }


def _inspect(content: bytes) -> list[FieldInfo]:
    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted:
            raise PDFError("Encrypted PDFs are not supported; decrypt the form first")
        result = {
            name: _field_info(name, field)
            for name, field in (reader.get_fields() or {}).items()
            if field.get("/FT")
            and not any("/T" in ref.get_object() for ref in field.get("/Kids", []))
        }
        # Some form creators write widgets without registering AcroForm roots.
        for page in reader.pages:
            for ref in page.get("/Annots", []):
                field = ref.get_object()
                if field.get("/Subtype") != "/Widget":
                    continue
                name, merged, _ = _ancestry(field)
                if name and merged.get("/FT"):
                    result[name] = _field_info(name, merged)
        return list(result.values())
    except PDFError:
        raise
    except Exception as exc:
        raise PDFError(f"Cannot read PDF: {exc}") from exc


def _ancestry(field: Any) -> tuple[str, dict[str, Any], Any]:
    """Resolve full names and inherited properties, retaining the root field."""
    chain = []
    seen = set()
    while id(field) not in seen:
        seen.add(id(field))
        chain.append(field)
        if "/Parent" not in field:
            break
        field = field["/Parent"].get_object()
    merged = {}
    names = []
    for item in reversed(chain):
        merged.update(item)
        if "/T" in item:
            names.append(str(item["/T"]))
    return ".".join(names), merged, chain[-1]


def _owner(widget: Any) -> Any:
    """Return the terminal field, which may be separate from its widget."""
    seen = {id(widget)}
    while "/T" not in widget and "/Parent" in widget:
        parent = widget["/Parent"].get_object()
        if id(parent) in seen:  # a crafted /Parent cycle must not loop forever
            break
        seen.add(id(parent))
        widget = parent
    return widget


def _prepare(content: bytes) -> bytes:
    """Expose inherited terminal properties to backends requiring local keys."""
    writer = PdfWriter(clone_from=PdfReader(BytesIO(content)))
    for page in writer.pages:
        for ref in page.get("/Annots", []):
            widget = ref.get_object()
            if widget.get("/Subtype") != "/Widget":
                continue
            _, inherited, _ = _ancestry(widget)
            field = _owner(widget)
            for key in ("/FT", "/Ff", "/TU", "/DA", "/Q", "/Opt", "/MaxLen", "/V", "/DV"):
                if key in inherited and key not in field:
                    field[NameObject(key)] = inherited[key]
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def inspect(template_pdf: PdfSource) -> list[FieldInfo]:
    """Describe named AcroForm fields, tooltip templates, and export options.

    Accept a path, PDF bytes, or an open binary stream (read from its current
    position). Plain tooltip prose is reported as a null template.
    """
    return _inspect(_source_bytes(template_pdf))


def _finalize(
    content: bytes,
    choice_values: Mapping[str, str],
    button_values: Mapping[str, bool | str],
    *,
    flatten: bool,
) -> bytes:
    """Generate visible appearances with PyPDFForm's pure Python PDF backend."""
    writer = PdfWriter(clone_from=PdfReader(BytesIO(content)))
    roots = []
    for page in writer.pages:
        for ref in page.get("/Annots", []):
            annotation = ref.get_object()
            if annotation.get("/Subtype") == "/Widget":
                name, inherited, root = _ancestry(annotation)
                root_ref = root.indirect_reference
                if root_ref not in roots:
                    roots.append(root_ref)
                field = _owner(annotation)
                if name in button_values:
                    requested = button_values[name]
                    states = annotation.get("/AP", {}).get("/N", {})
                    state = (
                        next((str(key) for key in states if str(key) != "/Off"), "/Off")
                        if requested is True
                        else "/Off"
                        if requested is False
                        else f"/{requested}"
                    )
                    # Set the owning field before get_fields() collects values.
                    # pypdf then selects each widget's matching appearance, so
                    # radio export names never depend on /Kids or page order.
                    field[NameObject("/V")] = NameObject(state)
                if name in choice_values:
                    value = choice_values[name]
                    field[NameObject("/V")] = TextStringObject(value)
                    options = inherited.get("/Opt", [])
                    if value not in _field_info(name, inherited)["options"]:
                        field[NameObject("/Opt")] = ArrayObject([*options, TextStringObject(value)])
    if roots:
        acroform = writer.root_object.setdefault(
            NameObject("/AcroForm"), DictionaryObject()
        ).get_object()
        acroform[NameObject("/Fields")] = ArrayObject(roots)
        # Hybrid XFA forms (e.g. IRS) make Acrobat show the XFA data, not the
        # AcroForm values filled here; dropping it leaves a plain AcroForm.
        acroform.pop("/XFA", None)
    fields = writer.get_fields() or {}
    values: dict[str, str | list[str]] = {}
    for name, field in fields.items():
        kind = field.get("/FT")
        if kind not in {"/Tx", "/Ch", "/Btn"} or int(field.get("/Ff", 0)) & (1 << 16):
            continue
        value = field.get("/V", "/Off" if kind == "/Btn" else "")
        values[name] = [str(item) for item in value] if isinstance(value, list) else str(value)
    choices_to_restore = []
    # PyPDFForm 3.5 stores text in /AP while filling. Replace those placeholders
    # with streams so viewers can display values without regenerating them.
    for page in writer.pages:
        for ref in page.get("/Annots", []):
            annotation = ref.get_object()
            if "/AP" in annotation and not isinstance(annotation["/AP"], DictionaryObject):
                del annotation["/AP"]
            name, inherited, _ = _ancestry(annotation)
            options = inherited.get("/Opt", [])
            if inherited.get("/FT") == "/Ch" and any(
                isinstance(option, list) for option in options
            ):
                field = annotation if "/Opt" in annotation else annotation["/Parent"].get_object()
                choices_to_restore.append((field, field["/Opt"], field.get("/V")))
                labels = {
                    str(item[0]): str(item[1]) if len(item) > 1 else str(item[0])
                    for item in options
                    if isinstance(item, list)
                }
                # pypdf's appearance generator expects display strings.
                # Render using labels, then restore export values and /Opt pairs.
                field[NameObject("/Opt")] = ArrayObject(
                    [
                        TextStringObject(labels.get(str(item[0]), str(item[0])))
                        if isinstance(item, list)
                        else item
                        for item in options
                    ]
                )
                selected = values[name]
                values[name] = (
                    [labels.get(item, item) for item in selected]
                    if isinstance(selected, list)
                    else labels.get(selected, selected)
                )
    if values:
        writer.update_page_form_field_values(None, values, auto_regenerate=False, flatten=flatten)
    for field, options, value in choices_to_restore:
        field[NameObject("/Opt")] = options
        if value is not None:
            field[NameObject("/V")] = value
    # The PDF button value is a name object, including on radio group parents.
    for page in writer.pages:
        for ref in page.get("/Annots", []):
            annotation = ref.get_object()
            field = _owner(annotation)
            if field.get("/FT") == "/Btn" and "/V" in field:
                field[NameObject("/V")] = NameObject(str(field["/V"]))
    if flatten:
        writer.remove_annotations(subtypes="/Widget")
        writer.root_object.pop("/AcroForm", None)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _render(
    env: SandboxedEnvironment, source: str, data: Mapping[str, object], *, image: bool
) -> object:
    # A single image expression must retain bytes/Path values, without using
    # NativeEnvironment (which would change the semantics of text fields).
    tree = env.parse(source)
    if image and len(tree.body) == 1 and isinstance(tree.body[0], nodes.Output):
        output = [
            node
            for node in tree.body[0].nodes
            if not isinstance(node, nodes.TemplateData) or node.data.strip()
        ]
        if len(output) == 1 and not isinstance(output[0], nodes.TemplateData):
            expression = nodes.Template([nodes.Assign(nodes.Name("result", "store"), output[0])])
            expression.set_environment(env)
            template = env.from_string(expression)
            value: object = vars(template.make_module(dict(data)))["result"]
            if isinstance(value, Undefined):
                return str(value)  # trigger StrictUndefined, or clear a lax image
            return value
    return env.from_string(source).render(dict(data))


def _strings(value: object, seen: set[int] | None = None) -> Iterator[str]:
    """Yield every string (and path) the data holds, at any depth."""
    seen = set() if seen is None else seen
    if isinstance(value, str):
        yield value
    elif isinstance(value, PathLike):
        yield fspath(value)
    elif isinstance(value, (Mapping, list, tuple)) and id(value) not in seen:
        seen.add(id(value))  # data may hold a self-referencing container
        for item in value.values() if isinstance(value, Mapping) else value:
            yield from _strings(item, seen)


def _image(value: object, data: Mapping[str, object]) -> bytes | None:
    # A rendered key can select bytes from data, e.g. a conditional template
    # returning 'approved_signature'. A single expression can return bytes directly.
    if isinstance(value, str) and value in data:
        value = data[value]
    elif isinstance(value, (str, PathLike)) and value and fspath(value) not in _strings(data):
        # Template PDFs are untrusted: one must not pick a local file to
        # embed in the output. Paths are honoured only when the data holds them.
        raise ValueError("a template cannot name an image file; pass its path in the data")
    if value is None or value == "":
        return None
    if isinstance(value, (str, PathLike)):
        value = Path(fspath(value)).read_bytes()
    if not isinstance(value, bytes):
        raise ValueError("expected an image path or image bytes")
    from PIL import Image

    with Image.open(BytesIO(value)) as image:
        image.verify()
    return value


def _value(info: FieldInfo, value: object, data: Mapping[str, object]) -> object:
    kind = info["type"]
    if kind == "checkbox":
        if isinstance(value, str):
            return value.strip().casefold() not in {"", "false", "0", "no", "off", "none", "null"}
        return bool(value)
    if kind == "radio":
        option = str(value)
        if option in info["options"]:
            return option
        raise ValueError(f"invalid radio option {option!r}; choose from {info['options']!r}")
    if kind in {"image", "signature"}:
        return _image(value, data)
    return "" if value is None else str(value)


def fill(
    template_pdf: PdfSource,
    data: Mapping[str, object],
    *,
    flatten: bool = False,
    strict: bool = True,
) -> bytes:
    """Render tooltip templates and fill a PDF, returning new PDF bytes.

    Fields without templates use data[name] when supplied, otherwise retain
    their original values. Missing variables raise FieldError in strict mode.
    Image/signature fields stamp images; they do not create digital signatures.
    """
    content = _source_bytes(template_pdf)
    fields = _inspect(content)
    env = SandboxedEnvironment(autoescape=False, undefined=StrictUndefined if strict else Undefined)
    values: dict[str, Any] = {}
    choice_values: dict[str, str] = {}
    button_values: dict[str, bool | str] = {}
    for info in fields:
        name = info["name"]
        source = info["template"]
        if source is None and name not in data:
            continue
        try:
            value = (
                data[name]
                if source is None
                else _render(env, source, data, image=info["type"] in {"image", "signature"})
            )
            value = _value(info, value, data)
            if info["type"] == "choice":
                choice_values[name] = str(value)
            if info["type"] in {"checkbox", "radio"}:
                button_values[name] = value if isinstance(value, bool) else str(value)
            if value is not None:
                values[name] = value
        except (TemplateError, ValueError, TypeError, OSError) as exc:
            raise FieldError(name, str(exc)) from exc
    try:
        form = PdfWrapper(_prepare(content), use_full_widget_name=True)
        for info in fields:
            name = info["name"]
            # Construct middleware from PDF field types, not PyPDFForm's /AS
            # heuristics or proprietary image action marker. Keep buttons idle
            # until _finalize sets their export states directly.
            if info["type"] == "checkbox":
                form.widgets[name] = Checkbox(name)
            elif info["type"] == "radio":
                form.widgets[name] = Radio(name)
            elif info["type"] == "image":
                form.widgets[name] = Image(name)
        # Validate assignments separately, then fill once: image stamping may
        # remove all image widgets, so sequential fills would lose later images.
        for name, value in values.items():
            try:
                # PyPDFForm's choice middleware uses display labels. Let its
                # pypdf backend set export values while preserving /Opt pairs.
                form.widgets[name].value = (
                    None if name in choice_values or name in button_values else value
                )
            except Exception as exc:
                raise FieldError(name, f"cannot fill value: {exc}") from exc
        form.fill({})
        return _finalize(bytes(form.read()), choice_values, button_values, flatten=flatten)
    except FieldError:
        raise
    except Exception as exc:
        raise PDFError(f"Cannot fill PDF: {exc}") from exc
