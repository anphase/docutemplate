import json
import subprocess
import sys
from io import BytesIO

import pytest
from pypdf import PdfReader

from docutemplate.cli import _load_data, main


def test_inspect_cli(make_pdf, tmp_path, capsys):
    form = tmp_path / "form.pdf"
    form.write_bytes(make_pdf())
    assert main(["inspect", str(form)]) == 0
    assert json.loads(capsys.readouterr().out)[0]["name"] == "full_name"


def test_fill_cli_json(make_pdf, data, tmp_path):
    form, source, output = [tmp_path / name for name in ["form.pdf", "data.json", "out.pdf"]]
    form.write_bytes(make_pdf())
    source.write_text(json.dumps(data))
    assert main(["fill", str(form), str(source), "-o", str(output)]) == 0
    fields = PdfReader(BytesIO(output.read_bytes())).get_fields()
    assert fields["full_name"]["/V"] == "Ada Lovelace"
    assert main(["fill", str(form), str(source), "-o", str(output), "--flatten"]) == 0
    assert not PdfReader(output).get_fields()


def test_csv_row_selection(make_pdf, tmp_path):
    form, source, output = [tmp_path / name for name in ["form.pdf", "data.csv", "out.pdf"]]
    form.write_bytes(make_pdf())
    source.write_text(
        "\ufefffirst,last,agreed,contact_method,country_code\n"
        "Ada,Lovelace,true,email,NZ\nGrace,Hopper,false,post,AU\n"
    )
    assert _load_data(source, None)["first"] == "Ada"
    assert main(["fill", str(form), str(source), "-o", str(output), "--row", "2"]) == 0
    fields = PdfReader(output).get_fields()
    assert fields["full_name"]["/V"] == "Grace Hopper"
    assert fields["consent"]["/V"] == "/Off"


@pytest.mark.parametrize(
    "filename,content,row,message",
    [
        ("a.csv", "first\nAda\n", 0, "at least 1"),
        ("a.csv", "first\nAda\n", 2, "does not exist"),
        ("a.csv", "first,last\nAda\n", 1, "does not match"),
        ("a.csv", "first\nAda,extra\n", 1, "does not match"),
        ("a.json", "{}", 1, "only available for CSV"),
        ("a.yaml", "first: Ada", None, "Unsupported"),
        ("a.json", "[]", None, "must be an object"),
        ("a.json", "invalid", None, "Expecting value"),
    ],
)
def test_data_errors(tmp_path, filename, content, row, message):
    source = tmp_path / filename
    source.write_text(content)
    with pytest.raises(ValueError, match=message):
        _load_data(source, row)


def test_cli_errors(tmp_path, capsys):
    with pytest.raises(SystemExit) as error:
        main(["inspect", str(tmp_path / "missing.pdf")])
    assert error.value.code == 2
    assert "error:" in capsys.readouterr().err
    with pytest.raises(SystemExit) as error:
        main([])
    assert error.value.code == 2


def test_no_strict_and_no_partial_output(make_pdf, tmp_path):
    form, source, output = [tmp_path / name for name in ["form.pdf", "data.json", "out.pdf"]]
    form.write_bytes(make_pdf({"contact": "{{ contact | default('email') }}"}))
    source.write_text("{}")
    output.write_bytes(b"existing")
    with pytest.raises(SystemExit):
        main(["fill", str(form), str(source), "-o", str(output)])
    assert output.read_bytes() == b"existing"
    assert main(["fill", str(form), str(source), "-o", str(output), "--no-strict"]) == 0


def test_module_and_console_entrypoints(make_pdf, tmp_path):
    form = tmp_path / "form.pdf"
    form.write_bytes(make_pdf())
    for command in [
        [sys.executable, "-m", "docutemplate"],
        [str(__import__("pathlib").Path(sys.executable).parent / "docutemplate")],
    ]:
        result = subprocess.run([*command, "inspect", str(form)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)[0]["name"] == "full_name"
