"""Generate AcroForm fixtures locally; no downloaded or checked-in PDFs."""

from io import BytesIO

import pytest
from reportlab.pdfgen.canvas import Canvas


@pytest.fixture
def make_pdf():
    def create(templates=None):
        templates = templates or {}
        output = BytesIO()
        canvas = Canvas(output, pagesize=(612, 792))
        form = canvas.acroForm
        form.textfield(
            name="full_name",
            tooltip=templates.get("full_name", "{{ first }} {{ last }}"),
            x=40,
            y=700,
            width=400,
            height=25,
        )
        form.textfield(
            name="filtered",
            tooltip=templates.get("filtered", "{{ first | upper }}"),
            x=40,
            y=660,
            width=400,
            height=25,
        )
        form.textfield(
            name="plain",
            tooltip="Ordinary help text",
            value="original",
            x=40,
            y=620,
            width=400,
            height=25,
        )
        form.textfield(name="untouched", value="keep me", x=40, y=580)
        form.checkbox(name="consent", tooltip=templates.get("consent", "{{ agreed }}"), x=40, y=530)
        for index, option in enumerate(["email", "post"]):
            form.radio(
                name="contact",
                tooltip=templates.get("contact", "{{ contact_method }}"),
                value=option,
                selected=index == 0,
                x=40 + index * 40,
                y=480,
            )
        form.choice(
            name="country",
            tooltip=templates.get("country", "{{ country_code }}"),
            options=[("New Zealand", "NZ"), ("Australia", "AU")],
            value="NZ",
            x=40,
            y=420,
            width=200,
        )
        canvas.showPage()
        canvas.save()
        return output.getvalue()

    return create


@pytest.fixture
def data():
    return {
        "first": "Ada",
        "last": "Lovelace",
        "agreed": True,
        "contact_method": "post",
        "country_code": "AU",
    }
