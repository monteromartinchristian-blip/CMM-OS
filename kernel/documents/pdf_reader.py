"""PDF reader that converts PDFs into structured Document instances."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from kernel.documents.document import Document, Metadata, Page


class PDFReader:
    """Read a PDF file and return a structured Document."""

    def read(self, path: Path | str) -> Document:
        pdf_path = Path(path)
        reader = PdfReader(str(pdf_path))

        pages: list[Page] = []
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pages.append(Page(number=index, text=text))

        metadata = Metadata(
            source=str(pdf_path),
            title=getattr(reader.metadata, "title", None) if reader.metadata is not None else None,
            author=getattr(reader.metadata, "author", None) if reader.metadata is not None else None,
            pages=len(reader.pages),
        )

        return Document(pages=tuple(pages), metadata=metadata)
