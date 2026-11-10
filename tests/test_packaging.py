"""Dependency floors: each must exclude releases with published advisories."""

import re
import tomllib
from pathlib import Path


def test_dependency_floors_exclude_releases_with_known_advisories():
    pyproject = Path(__file__).parents[1] / "pyproject.toml"
    project = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
    floors = {
        re.split(r"[<>=]", requirement)[0]: tuple(
            int(part) for part in re.search(r">=([\d.]+)", requirement)[1].split(".")
        )
        for requirement in project["dependencies"]
    }
    # Crafted-PDF and crafted-image denial of service fixes (OSV, 2026-11-11).
    assert floors["pypdf"] >= (6, 21, 4)
    # PyPDFForm always installs Pillow, so its floor is a core requirement.
    assert floors["Pillow"] >= (13,)
    # Sandbox escape fixes.
    assert floors["Jinja2"] >= (3, 1, 6)
