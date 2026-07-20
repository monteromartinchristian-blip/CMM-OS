from __future__ import annotations

from pathlib import Path

from kernel.documents.document import Document
from kernel.planner.read_pdf_operation import ReadPDFOperation


def _fixture(name: str) -> Path:
    return Path(__file__).parent.parent / "fixtures" / "sample_pdf" / name


def test_read_pdf_operation_returns_document() -> None:
    operation = ReadPDFOperation(path=str(_fixture("hello.pdf")))

    document = operation.execute()

    assert isinstance(document, Document)
    assert len(document.pages) == 1
    assert "Hello PDF" in document.text
