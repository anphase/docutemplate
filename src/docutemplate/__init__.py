"""Fill PDF forms from Jinja templates embedded in field tooltips."""

from .core import FieldInfo, PdfSource, fill, fill_many, inspect, schema
from .errors import DocutemplateError, FieldError, PDFError

__version__ = "0.1.0"
__all__ = [
    "DocutemplateError",
    "FieldError",
    "FieldInfo",
    "PDFError",
    "PdfSource",
    "fill",
    "fill_many",
    "inspect",
    "schema",
]
