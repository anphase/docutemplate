"""Public exceptions for PDF and field failures."""


class DocutemplateError(ValueError):
    """Base exception for invalid documents, templates, and field values."""


class PDFError(DocutemplateError):
    """The input could not be read or filled as a PDF."""


class FieldError(DocutemplateError):
    """An error associated with a named form field."""

    def __init__(self, field: str, message: str) -> None:
        self.field = field
        super().__init__(f"Field {field!r}: {message}")
