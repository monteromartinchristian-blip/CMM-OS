"""Stdlib HTML text extraction — no parsing dependency, no script leakage."""

from __future__ import annotations

import re
from html.parser import HTMLParser

__all__ = ["extract_text", "extract_title"]

_SKIP_TAGS = frozenset(
    {"script", "style", "noscript", "template", "svg", "head", "iframe"}
)
_WHITESPACE = re.compile(r"[ \t\r\f\v]+")
_NEWLINES = re.compile(r"\n{3,}")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag in ("p", "br", "div", "li", "h1", "h2", "h3", "h4", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if self._skip_depth == 0 and data.strip():
            self.parts.append(data)


def _normalize(text: str) -> str:
    text = _WHITESPACE.sub(" ", text)
    text = _NEWLINES.sub("\n\n", text)
    return text.strip()


def extract_text(html: str, *, window: int = 24_000) -> tuple[str, str]:
    """Return ``(title, text)`` extracted from an HTML document."""

    parser = _TextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001, S110 - malformed HTML degrades, never crashes
        pass
    title = _normalize("".join(parser.title_parts))
    text = _normalize("".join(parser.parts))
    return title, text[:window]


def extract_title(html: str) -> str:
    return extract_text(html, window=0)[0]
