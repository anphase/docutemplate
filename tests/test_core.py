from io import BytesIO

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject, TextStringObject
from PyPDFForm import Fields, PdfWrapper

from docutemplate import FieldError, PDFError, __version__, core, fill, inspect


def fields(pdf):
    return PdfReader(BytesIO(pdf)).get_fields()


def test_fill_all_types(make_pdf, data):
    original = make_pdf()
    result = fill(original, data)
    values = fields(result)
    assert result.startswith(b"%PDF-")
    assert values["full_name"]["/V"] == "Ada Lovelace"
    assert values["filtered"]["/V"] == "ADA"
    assert values["plain"]["/V"] == "original"
    assert values["untouched"]["/V"] == "keep me"
    assert values["consent"]["/V"] != "/Off"
    assert values["contact"]["/V"] == "/post"
    assert values["country"]["/V"] == "AU"
    assert fields(original)["full_name"]["/V"] == ""
    assert __version__ == "0.1.0"


def test_paths_streams_and_fallback(make_pdf, data, tmp_path):
    path = tmp_path / "form.pdf"
    path.write_bytes(make_pdf())
    data.update(plain="new", untouched=None)
    result = fill(path, data)
    assert fields(result)["plain"]["/V"] == "new"
    assert fields(result)["untouched"]["/V"] == ""
    assert inspect(str(path)) == inspect(BytesIO(path.read_bytes()))
    with path.open("rb") as stream:
        assert fields(fill(stream, data))["full_name"]["/V"] == "Ada Lovelace"


def test_inspect(make_pdf):
    info = {field["name"]: field for field in inspect(make_pdf())}
    assert info["full_name"] == {
        "name": "full_name",
        "type": "text",
        "template": "{{ first }} {{ last }}",
        "options": [],
    }
    assert info["plain"]["template"] is None
    assert info["consent"]["type"] == "checkbox"
    assert info["contact"]["options"] == ["email", "post"]
    assert info["country"]["options"] == ["NZ", "AU"]


def test_missing_strict_and_lax(make_pdf, data):
    pdf = make_pdf({"filtered": "{{ absent }}"})
    with pytest.raises(FieldError, match="filtered.*absent") as error:
        fill(pdf, data)
    assert error.value.field == "filtered"
    assert fields(fill(pdf, data, strict=False))["filtered"]["/V"] == ""


@pytest.mark.parametrize("source", ["{{ first", "{% if first %}"])
def test_syntax_error(make_pdf, data, source):
    with pytest.raises(FieldError, match="filtered"):
        fill(make_pdf({"filtered": source}), data)


def test_sandbox(make_pdf, data):
    with pytest.raises(FieldError, match="filtered.*unsafe"):
        fill(make_pdf({"filtered": "{{ first.__class__.__mro__ }}"}), data)


def test_blocks_comments_filters_autoescape(make_pdf, data):
    data["first"] = "<Ada>"
    pdf = make_pdf(
        {
            "full_name": "{% if agreed %}{{ first }}{% else %}no{% endif %}",
            "filtered": "{# note #}{{ missing | default('fallback') }}",
        }
    )
    values = fields(fill(pdf, data))
    assert values["full_name"]["/V"] == "<Ada>"
    assert values["filtered"]["/V"] == "fallback"


@pytest.mark.parametrize(
    "value,checked",
    [
        (True, True),
        (False, False),
        (1, True),
        (0, False),
        ("true", True),
        (" yes ", True),
        ("FALSE", False),
        ("0", False),
        ("no", False),
        ("off", False),
        ("None", False),
        ("null", False),
        ("", False),
    ],
)
def test_checkbox(make_pdf, data, value, checked):
    data["agreed"] = value
    assert (fields(fill(make_pdf(), data))["consent"]["/V"] != "/Off") == checked


def test_checkbox_without_template(make_pdf, data):
    pdf = make_pdf({"consent": "Tick to agree"})
    data["consent"] = False
    assert fields(fill(pdf, data))["consent"]["/V"] == "/Off"


def test_invalid_radio(make_pdf, data):
    data["contact_method"] = "unknown"
    with pytest.raises(FieldError, match="contact.*unknown.*email.*post"):
        fill(make_pdf(), data)


def test_flatten(make_pdf, data):
    result = fill(make_pdf(), data, flatten=True)
    reader = PdfReader(BytesIO(result))
    assert not reader.get_fields()
    assert all(not page.get("/Annots") for page in reader.pages)
    assert "Ada Lovelace" in reader.pages[0].extract_text()
    assert "keep me" in reader.pages[0].extract_text()


def test_invalid_pdf_and_missing_file(tmp_path):
    with pytest.raises(PDFError, match="Cannot read PDF"):
        inspect(b"not a PDF")
    with pytest.raises(FileNotFoundError):
        fill(tmp_path / "missing.pdf", {})


def test_blank_and_encrypted_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    output = BytesIO()
    writer.write(output)
    assert inspect(output.getvalue()) == []
    assert fill(output.getvalue(), {}).startswith(b"%PDF-")
    writer.encrypt("secret")
    output = BytesIO()
    writer.write(output)
    with pytest.raises(PDFError, match="Encrypted"):
        fill(output.getvalue(), {})


def test_choice_without_export_values():
    assert core._field_info("x", {"/FT": "/Ch", "/Opt": ["one", "two"]})["options"] == [
        "one",
        "two",
    ]
    assert core._field_info("x", {"/FT": "/Other"})["type"] == "unknown"


def image_form(photo="{{ picture }}"):
    blank = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(blank)
    form = PdfWrapper(blank.getvalue())
    form.create_field(
        Fields.ImageField(
            name="photo", page_number=1, x=50, y=500, tooltip=photo, width=100, height=80
        )
    )
    form.create_field(
        Fields.SignatureField(
            name="signature",
            page_number=1,
            x=50,
            y=300,
            tooltip="{{ signing }}",
            width=100,
            height=50,
        )
    )
    return form.read()


def png():
    from PIL import Image

    output = BytesIO()
    Image.new("RGB", (12, 8), color="blue").save(output, format="PNG")
    return output.getvalue()


@pytest.mark.parametrize("mode", ["bytes", "path", "string", "lookup"])
def test_images_and_signatures(tmp_path, mode):
    pdf = image_form()
    info = {entry["name"]: entry for entry in inspect(pdf)}
    assert info["photo"]["type"] == "image"
    assert info["signature"]["type"] == "signature"
    image = tmp_path / "stamp.png"
    image.write_bytes(png())
    value = {"bytes": png(), "path": image, "string": str(image), "lookup": "asset"}[mode]
    result = fill(pdf, {"picture": value, "signing": value, "asset": png()})
    page = PdfReader(BytesIO(result)).pages[0]
    assert len(page.images) >= 1


def test_image_errors_and_empty():
    pdf = image_form()
    with pytest.raises(FieldError, match="photo.*path or image bytes"):
        fill(pdf, {"picture": 7, "signing": None})
    with pytest.raises(FieldError, match="photo.*picture"):
        fill(pdf, {})
    assert fill(pdf, {}, strict=False).startswith(b"%PDF-")
    assert fill(pdf, {"picture": None, "signing": ""}).startswith(b"%PDF-")
    with pytest.raises(FieldError, match="photo"):
        fill(pdf, {"picture": b"invalid image", "signing": None})


def test_image_complex_template():
    env = core.SandboxedEnvironment(autoescape=False)
    source = "{% if enabled %}asset{% endif %}"
    assert core._render(env, source, {"enabled": True}, image=True) == "asset"
    assert (
        core._value(
            {"name": "x", "type": "choice", "template": None, "options": []}, None, {}, set()
        )
        == ""
    )


def test_backend_failure(make_pdf, data, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("backend failed")

    monkeypatch.setattr(core, "PdfWrapper", broken)
    with pytest.raises(PDFError, match="Cannot fill PDF.*backend failed"):
        fill(make_pdf(), data)


def test_hierarchical_names(make_pdf, data):
    writer = PdfWriter(clone_from=PdfReader(BytesIO(make_pdf())))
    root = writer.root_object["/AcroForm"].get_object()
    original = root["/Fields"][0].get_object()
    parent = DictionaryObject(
        {
            NameObject("/T"): TextStringObject("person"),
            NameObject("/Kids"): ArrayObject([original.indirect_reference]),
        }
    )
    ref = writer._add_object(parent)
    original[NameObject("/Parent")] = ref
    original[NameObject("/T")] = TextStringObject("name")
    root["/Fields"][0] = ref
    output = BytesIO()
    writer.write(output)
    assert "person.name" in {entry["name"] for entry in inspect(output.getvalue())}
    data.update(first="Grace", last="Hopper")
    result = fill(output.getvalue(), data)
    assert fields(result)["person.name"]["/V"] == "Grace Hopper"


def test_multi_select_value_is_preserved(make_pdf, data):
    writer = PdfWriter(clone_from=PdfReader(BytesIO(make_pdf())))
    for ref in writer.root_object["/AcroForm"]["/Fields"]:
        field = ref.get_object()
        if field.get("/T") == "country":
            field[NameObject("/TU")] = TextStringObject("Ordinary help")
            field[NameObject("/Ff")] = NumberObject(1 << 21)
            field[NameObject("/V")] = ArrayObject([TextStringObject("NZ"), TextStringObject("AU")])
    output = BytesIO()
    writer.write(output)
    result = fill(output.getvalue(), data)
    assert fields(result)["country"]["/V"] == ["NZ", "AU"]


def test_both_images_are_stamped_and_flattened():
    result = fill(image_form(), {"picture": png(), "signing": png()}, flatten=True)
    page = PdfReader(BytesIO(result)).pages[0]
    assert page.get_contents().get_data().count(b" Do") == 2
    assert not page.get("/Annots")


def test_direct_image_data_and_whitespace_template():
    writer = PdfWriter(clone_from=PdfReader(BytesIO(image_form())))
    for ref in writer.pages[0]["/Annots"]:
        field = ref.get_object()
        field[NameObject("/TU")] = TextStringObject(
            "Help text" if field["/T"] == "photo" else "  {{ signing }}  "
        )
    output = BytesIO()
    writer.write(output)
    result = fill(output.getvalue(), {"photo": png(), "signing": png()})
    assert PdfReader(BytesIO(result)).pages[0].get_contents().get_data().count(b" Do") == 2


def test_invalid_image_path():
    with pytest.raises(FieldError, match="photo"):
        fill(image_form(), {"picture": "/does-not-exist/stamp.png", "signing": None})


def test_backend_assignment_error(make_pdf, data, monkeypatch):
    class UnsupportedForm:
        widgets = {}

    monkeypatch.setattr(core, "PdfWrapper", lambda *a, **kw: UnsupportedForm())
    with pytest.raises(FieldError, match="full_name.*cannot fill"):
        fill(make_pdf(), data)


def test_module_main_in_process(monkeypatch):
    import runpy

    from docutemplate import cli

    monkeypatch.setattr(cli, "main", lambda: 0)
    with pytest.raises(SystemExit) as error:
        runpy.run_module("docutemplate", run_name="__main__")
    assert error.value.code == 0


def test_appearances_show_values_and_choice_labels(make_pdf, data):
    result = fill(make_pdf(), data)
    reader = PdfReader(BytesIO(result))
    annotations = {
        ref.get_object().get("/T"): ref.get_object() for ref in reader.pages[0]["/Annots"]
    }
    assert b"Ada Lovelace" in annotations["full_name"]["/AP"]["/N"].get_data()
    assert b"Australia" in annotations["country"]["/AP"]["/N"].get_data()
    radio = reader.get_fields()["contact"]
    assert [ref.get_object()["/AS"] for ref in radio["/Kids"]] == ["/Off", "/post"]
    flattened = PdfReader(BytesIO(fill(make_pdf(), data, flatten=True)))
    assert "Australia" in flattened.pages[0].extract_text()


def pdf_bytes(writer):
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.mark.parametrize("option", ["email", "post"])
def test_radio_with_reordered_kids(make_pdf, data, option):
    writer = PdfWriter(clone_from=PdfReader(BytesIO(make_pdf())))
    radio = writer.get_fields()["contact"]
    # Change the real field dictionary, not get_fields()'s extracted copy.
    owner = radio.indirect_reference.get_object()
    owner[NameObject("/Kids")] = ArrayObject(reversed(owner["/Kids"]))
    original = pdf_bytes(writer)
    assert next(info for info in inspect(original) if info["name"] == "contact")["options"] == [
        "post",
        "email",
    ]
    data["contact_method"] = option
    result = fields(fill(original, data))["contact"]
    assert result["/V"] == f"/{option}"
    for ref in result["/Kids"]:
        widget = ref.get_object()
        expected = f"/{option}" if f"/{option}" in widget["/AP"]["/N"] else "/Off"
        assert widget["/AS"] == expected


def split_checkbox(writer):
    roots = writer.root_object["/AcroForm"]["/Fields"]
    for index, ref in enumerate(roots):
        widget = ref.get_object()
        if widget.get("/T") == "consent":
            owner = DictionaryObject({NameObject("/Kids"): ArrayObject([ref])})
            for key in ("/T", "/FT", "/Ff", "/TU", "/V", "/DV"):
                if key in widget:
                    owner[NameObject(key)] = widget.pop(key)
            owner_ref = writer._add_object(owner)
            widget[NameObject("/Parent")] = owner_ref
            roots[index] = owner_ref
            return owner, widget
    raise AssertionError("checkbox fixture missing")


@pytest.mark.parametrize("checked", [True, False])
def test_checkbox_parent_owns_value(make_pdf, data, checked):
    writer = PdfWriter(clone_from=PdfReader(BytesIO(make_pdf())))
    owner, widget = split_checkbox(writer)
    initial = NameObject("/Off" if checked else "/Yes")
    owner[NameObject("/V")] = initial
    widget[NameObject("/AS")] = initial
    data["agreed"] = checked
    result = fields(fill(pdf_bytes(writer), data))["consent"]
    expected = "/Yes" if checked else "/Off"
    assert result["/V"] == expected
    assert result["/Kids"][0].get_object()["/AS"] == expected


def test_hierarchical_inherited_type_and_tooltip(make_pdf, data):
    writer = PdfWriter(clone_from=PdfReader(BytesIO(make_pdf())))
    roots = writer.root_object["/AcroForm"]["/Fields"]
    child = roots[0].get_object()
    parent = DictionaryObject(
        {
            NameObject("/T"): TextStringObject("person"),
            NameObject("/FT"): child.pop("/FT"),
            NameObject("/TU"): child.pop("/TU"),
            NameObject("/Kids"): ArrayObject([roots[0]]),
        }
    )
    roots[0] = writer._add_object(parent)
    child[NameObject("/Parent")] = roots[0]
    child[NameObject("/T")] = TextStringObject("name")
    original = pdf_bytes(writer)
    info = {entry["name"]: entry for entry in inspect(original)}
    assert "person" not in info
    assert info["person.name"]["template"] == "{{ first }} {{ last }}"
    result = fill(original, data)
    assert fields(result)["person.name"]["/V"] == "Ada Lovelace"
    widget = PdfReader(BytesIO(result)).pages[0]["/Annots"][0].get_object()
    assert b"Ada Lovelace" in widget["/AP"]["/N"].get_data()
    flattened = PdfReader(BytesIO(fill(original, data, flatten=True)))
    assert "Ada Lovelace" in flattened.pages[0].extract_text()
    assert not flattened.get_fields()


@pytest.mark.parametrize("split", [False, True])
@pytest.mark.parametrize("checked", [True, False])
def test_checkbox_custom_on_state(make_pdf, data, split, checked):
    writer = PdfWriter(clone_from=PdfReader(BytesIO(make_pdf())))
    widget = next(
        ref.get_object()
        for ref in writer.pages[0]["/Annots"]
        if ref.get_object().get("/T") == "consent"
    )
    for appearances in widget["/AP"].values():
        appearances = appearances.get_object()
        appearances[NameObject("/Accepted")] = appearances.pop("/Yes")
    widget[NameObject("/V")] = NameObject("/Accepted")
    widget[NameObject("/AS")] = NameObject("/Accepted")
    if split:
        split_checkbox(writer)
    original = pdf_bytes(writer)
    assert next(info for info in inspect(original) if info["name"] == "consent")["type"] == (
        "checkbox"
    )
    data["agreed"] = checked
    result = fill(original, data)
    expected = "/Accepted" if checked else "/Off"
    assert fields(result)["consent"]["/V"] == expected
    widget = next(
        ref.get_object()
        for ref in PdfReader(BytesIO(result)).pages[0]["/Annots"]
        if core._ancestry(ref.get_object())[0] == "consent"
    )
    assert widget["/AS"] == expected
    assert "/Yes" not in widget["/AP"]["/N"]
    # A second fill must also work when the custom checkbox starts unchecked.
    data["agreed"] = not checked
    assert fields(fill(result, data))["consent"]["/V"] == ("/Off" if checked else "/Accepted")


@pytest.mark.parametrize("flatten", [False, True])
def test_ordinary_pushbutton_image(flatten):
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    button = DictionaryObject(
        {
            NameObject("/Subtype"): NameObject("/Widget"),
            NameObject("/FT"): NameObject("/Btn"),
            NameObject("/Ff"): NumberObject(1 << 16),
            NameObject("/T"): TextStringObject("photo"),
            NameObject("/TU"): TextStringObject("{{ picture }}"),
            NameObject("/Rect"): ArrayObject(map(NumberObject, [50, 500, 150, 580])),
        }
    )
    ref = writer._add_object(button)
    page[NameObject("/Annots")] = ArrayObject([ref])
    writer.root_object[NameObject("/AcroForm")] = DictionaryObject(
        {NameObject("/Fields"): ArrayObject([ref])}
    )
    original = pdf_bytes(writer)
    assert inspect(original)[0]["type"] == "image"
    result = fill(original, {"picture": png()}, flatten=flatten)
    page = PdfReader(BytesIO(result)).pages[0]
    assert len(page.images) == 1
    assert page.get_contents().get_data().count(b" Do") == 1


@pytest.mark.parametrize("flatten", [False, True])
def test_xfa_hybrid_form_drops_xfa(make_pdf, data, flatten):
    # IRS-style hybrid forms carry an XFA copy of the data that Acrobat prefers
    # over the AcroForm values, so a filled form would still show blanks.
    writer = PdfWriter(clone_from=PdfReader(BytesIO(make_pdf())))
    writer.root_object["/AcroForm"][NameObject("/XFA")] = ArrayObject(
        [TextStringObject("template"), writer._add_object(DictionaryObject())]
    )
    buffer = BytesIO()
    writer.write(buffer)
    out = PdfReader(BytesIO(fill(buffer.getvalue(), data, flatten=flatten)))
    acroform = out.trailer["/Root"].get("/AcroForm", {})
    assert "/XFA" not in acroform
    if not flatten:
        assert out.get_fields()["full_name"]["/V"] == "Ada Lovelace"


class _Node(dict):
    """A dictionary standing in for a pypdf object, with a budget of dereferences."""

    budget = 50

    def get_object(self):
        _Node.budget -= 1
        assert _Node.budget > 0, "parent chain was followed without end"
        return self


def test_owner_stops_on_a_parent_cycle():
    _Node.budget = 50
    first, second = _Node(), _Node()
    first["/Parent"], second["/Parent"] = second, first
    assert core._owner(first) is second
    alone = _Node()
    alone["/Parent"] = alone
    assert core._owner(alone) is alone
    named = _Node({"/T": "group"})
    child = _Node({"/Parent": named})
    assert core._owner(child) is named


def cyclic_parent_form(*, self_parent):
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    widget = writer._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/Widget"),
                NameObject("/Rect"): ArrayObject([NumberObject(0)] * 4),
            }
        )
    )
    parent = widget if self_parent else writer._add_object(DictionaryObject())
    widget.get_object()[NameObject("/Parent")] = parent
    parent.get_object()[NameObject("/Parent")] = widget
    page[NameObject("/Annots")] = ArrayObject([widget])
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.mark.parametrize("self_parent", [True, False])
def test_fill_terminates_on_a_cyclic_parent_chain(self_parent):
    import faulthandler

    pdf = cyclic_parent_form(self_parent=self_parent)
    faulthandler.dump_traceback_later(20, exit=True)  # a hang fails the run, not stalls it
    try:
        assert inspect(pdf) == []
        assert fill(pdf, {}).startswith(b"%PDF-")
    finally:
        faulthandler.cancel_dump_traceback_later()


@pytest.mark.parametrize(
    "tooltip",
    ["{{{{ '{path}' }}}}", "{{{{ folder }}}}/private.png", "{{{{ folder ~ '/private.png' }}}}"],
)
def test_template_cannot_name_an_image_file(tmp_path, tooltip):
    image = tmp_path / "private.png"
    image.write_bytes(png())
    pdf = image_form(photo=tooltip.format(path=image))
    with pytest.raises(FieldError, match="photo.*template cannot name an image file"):
        fill(pdf, {"folder": str(tmp_path), "signing": None})


def test_template_may_select_an_image_path_held_in_the_data(tmp_path):
    image = tmp_path / "stamp.png"
    image.write_bytes(png())
    pdf = image_form(photo="{% if picture %}{{ picture }}{% endif %}")
    result = fill(pdf, {"picture": str(image), "signing": None})
    assert len(PdfReader(BytesIO(result)).pages[0].images) == 1
    assert fill(pdf, {"picture": "", "signing": None}).startswith(b"%PDF-")


def test_template_may_select_an_image_path_nested_in_the_data(tmp_path):
    image = tmp_path / "stamp.png"
    image.write_bytes(png())
    pdf = image_form(photo="{{ customer.photos[0] }}")
    result = fill(pdf, {"customer": {"photos": [str(image)]}, "signing": None})
    assert len(PdfReader(BytesIO(result)).pages[0].images) == 1
    result = fill(pdf, {"customer": {"photos": (str(image),)}, "signing": None})
    assert len(PdfReader(BytesIO(result)).pages[0].images) == 1


def test_template_may_select_a_path_object_held_in_the_data(tmp_path):
    image = tmp_path / "stamp.png"
    image.write_bytes(png())
    pdf = image_form(photo="{% if picture %}{{ picture }}{% endif %}")
    result = fill(pdf, {"picture": image, "signing": None})
    assert len(PdfReader(BytesIO(result)).pages[0].images) == 1


def test_template_cannot_derive_an_image_path_from_a_path_object(tmp_path):
    (tmp_path / "private.png").write_bytes(png())
    held = tmp_path / "stamp.png"
    held.write_bytes(png())
    pdf = image_form(photo="{{ folder / 'private.png' }}")
    with pytest.raises(FieldError, match="photo.*template cannot name an image file"):
        fill(pdf, {"picture": held, "folder": tmp_path, "signing": None})
    result = fill(image_form(photo="{{ picture }}"), {"picture": held, "signing": None})
    assert len(PdfReader(BytesIO(result)).pages[0].images) == 1


@pytest.mark.parametrize(
    "template",
    [
        "{{ picture.parent.joinpath('private.png').read_bytes() }}",
        "{{ picture.with_name('private.png').read_bytes() }}",
        "{{ (folder / 'private.png').read_bytes() }}",
        "{{ (picture | attr('read_bytes'))() }}",
        "{{ ([picture] | map(attribute='read_bytes') | first)() }}",
    ],
)
@pytest.mark.parametrize("strict", [True, False])
def test_template_cannot_use_a_path_object_to_reach_files(tmp_path, template, strict):
    (tmp_path / "private.png").write_bytes(png())
    held = tmp_path / "stamp.png"
    held.write_bytes(png())
    data = {"picture": held, "folder": tmp_path, "signing": None}
    with pytest.raises(FieldError, match="photo"):
        fill(image_form(photo=template), data, strict=strict)


def test_template_cannot_read_a_file_into_a_text_field(make_pdf, data, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("classified")
    pdf = make_pdf({"filtered": "{{ note.read_text() }}"})
    with pytest.raises(FieldError, match="filtered.*unsafe"):
        fill(pdf, {**data, "note": secret})
    printed = fill(make_pdf({"filtered": "{{ note }}"}), {**data, "note": secret})
    assert fields(printed)["filtered"]["/V"] == str(secret)


def test_self_referencing_data_does_not_break_image_selection(tmp_path):
    image = tmp_path / "stamp.png"
    image.write_bytes(png())
    loop: dict[str, object] = {}
    loop["self"] = loop
    pdf = image_form(photo="{% if picture %}{{ picture }}{% endif %}")
    result = fill(pdf, {"loop": loop, "picture": str(image), "signing": None})
    assert len(PdfReader(BytesIO(result)).pages[0].images) == 1


@pytest.mark.parametrize(
    "template",
    [
        "{% set ignored = allowed.append(folder ~ '/private.png') %}{{ folder }}/private.png",
        "{% set ignored = nested.update(extra=folder ~ '/private.png') %}{{ nested.extra }}",
        "{% set ignored = nested.update(extra=folder ~ '/private.png') %}extra",
    ],
)
def test_template_cannot_widen_the_data_to_name_an_image_file(tmp_path, template):
    (tmp_path / "private.png").write_bytes(png())
    data = {"folder": str(tmp_path), "allowed": [], "nested": {}, "signing": None}
    with pytest.raises(FieldError, match="photo"):
        fill(image_form(photo=template), data)
    assert data["allowed"] == [] and data["nested"] == {}
