from __future__ import annotations

from pathlib import Path

from kernel.documents.document import Document
from kernel.documents.pdf_reader import PDFReader


def _fixture(name: str) -> Path:
    return Path(__file__).parent.parent / "fixtures" / "sample_pdf" / name


def test_pdf_reader_reads_text_and_metadata() -> None:
    document = PDFReader().read(_fixture("hello.pdf"))

    assert isinstance(document, Document)
    assert len(document.pages) == 1
    assert "Hello PDF" in document.pages[0].text
    assert document.metadata.pages == 1
    assert document.metadata.source.endswith("hello.pdf")
    assert document.is_empty is False
    assert "Hello PDF" in document.text


def test_pdf_reader_handles_empty_document() -> None:
    document = PDFReader().read(_fixture("empty.pdf"))

    assert isinstance(document, Document)
    assert len(document.pages) == 0
    assert document.metadata.pages == 0
    assert document.text == ""
    assert document.is_empty is True
