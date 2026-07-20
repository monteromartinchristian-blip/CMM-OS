"""Reusable document model for structured document ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Metadata:
    """Basic document metadata."""

    source: str | None = None
    title: str | None = None
    author: str | None = None
    pages: int = 0


@dataclass(frozen=True, slots=True)
class Page:
    """A single page in a document."""

    number: int
    text: str = ""


@dataclass(frozen=True, slots=True)
class Document:
    """Structured document with metadata and pages."""

    pages: tuple[Page, ...] = field(default_factory=tuple)
    metadata: Metadata = field(default_factory=Metadata)

    @property
    def text(self) -> str:
        """Return the full text content of the document."""

        return "\n".join(page.text for page in self.pages if page.text)

    @property
    def is_empty(self) -> bool:
        """Return whether the document contains any text content."""

        return len(self.pages) == 0 or all(not page.text.strip() for page in self.pages)
