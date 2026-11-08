"""Command line interface with JSON and CSV input."""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from .core import fill, inspect
from .errors import DocutemplateError


def _load_data(path: Path, row: int | None) -> dict[str, object]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        selected = 1 if row is None else row
        if selected < 1:
            raise ValueError("--row must be at least 1 (the first data row)")
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for index, record in enumerate(csv.DictReader(stream), 1):
                if index == selected:
                    if None in record or any(value is None for value in record.values()):
                        raise ValueError(f"CSV row {selected} does not match its header")
                    return dict(record)
        raise ValueError(f"CSV row {selected} does not exist")
    if row is not None:
        raise ValueError("--row is only available for CSV input")
    if suffix != ".json":
        raise ValueError("Unsupported data format; use .json or .csv")
    with path.open(encoding="utf-8-sig") as stream:
        data: object = json.load(stream)
    if not isinstance(data, dict):
        raise ValueError("JSON data must be an object mapping names to values")
    return cast(dict[str, object], data)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI. Return zero on success; argparse reports errors with code 2."""
    parser = argparse.ArgumentParser(prog="docutemplate", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fill_parser = commands.add_parser("fill", help="fill a PDF from JSON or a CSV row")
    fill_parser.add_argument("form", type=Path)
    fill_parser.add_argument("data", type=Path)
    fill_parser.add_argument("-o", "--output", type=Path, required=True)
    fill_parser.add_argument("--flatten", action="store_true")
    fill_parser.add_argument("--row", type=int, help="CSV data row, starting at 1 (default: 1)")
    fill_parser.add_argument("--no-strict", action="store_true", help="allow missing variables")
    inspect_parser = commands.add_parser("inspect", help="print field descriptions as JSON")
    inspect_parser.add_argument("form", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            print(json.dumps(inspect(args.form), indent=2, ensure_ascii=False))
        else:
            data = _load_data(args.data, args.row)
            result = fill(args.form, data, flatten=args.flatten, strict=not args.no_strict)
            args.output.write_bytes(result)
    except (DocutemplateError, OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0
