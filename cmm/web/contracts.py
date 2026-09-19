"""Normalized web-capability data contracts (frozen, provider-independent)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urlsplit

__all__ = [
    "Citation",
    "FetchedSource",
    "FetchRequest",
    "WebResultItem",
    "WebSearchRequest",
    "WebSearchResult",
    "domain_of",
    "utc_now",
]


def utc_now() -> datetime:
    return datetime.now(UTC)


def domain_of(url: str) -> str:
    """Return the registrable host of a URL, or the raw host when unusual."""

    host = (urlsplit(url).hostname or "").lower()
    return host.removeprefix("www.")


@dataclass(frozen=True, slots=True)
class WebSearchRequest:
    query: str
    limit: int = 8
    allowed_domains: tuple[str, ...] = ()
    prohibited_domains: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.query, str) or not self.query.strip():
            raise ValueError("query must be a non-empty string")
        if not isinstance(self.limit, int) or self.limit < 1 or self.limit > 20:
            raise ValueError("limit must be between 1 and 20")


@dataclass(frozen=True, slots=True)
class WebResultItem:
    title: str
    url: str
    domain: str
    snippet: str
    rank: int
    backend_id: str
    searched_at: datetime

    def __post_init__(self) -> None:
        if urlsplit(self.url).scheme not in ("http", "https"):
            raise ValueError("result url must be http(s)")


@dataclass(frozen=True, slots=True)
class WebSearchResult:
    query: str
    items: tuple[WebResultItem, ...]
    backend_id: str
    searched_at: datetime
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FetchRequest:
    url: str
    max_bytes: int = 2_000_000
    timeout: float = 15.0

    def __post_init__(self) -> None:
        if urlsplit(self.url).scheme not in ("http", "https"):
            raise ValueError("fetch url must be http(s)")
        if self.max_bytes < 1 or self.max_bytes > 20_000_000:
            raise ValueError("max_bytes must be between 1 and 20_000_000")
        if not 0 < self.timeout <= 120:
            raise ValueError("timeout must be within (0, 120] seconds")


@dataclass(frozen=True, slots=True)
class FetchedSource:
    url: str
    final_url: str
    domain: str
    title: str
    text: str
    content_type: str
    retrieved_at: datetime
    truncated: bool
    fetched: bool = True


@dataclass(frozen=True, slots=True)
class Citation:
    index: int
    title: str
    url: str
    domain: str
    snippet: str
    inspected: bool
    retrieved_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ResearchLimits:
    max_searches: int = 3
    max_reads: int = 4
    max_turns: int = 8


@dataclass(frozen=True, slots=True)
class ResearchOutcome:
    answer: str
    citations: tuple[Citation, ...]
    sources: tuple[FetchedSource, ...] = field(default=())
    searches: int = 0
    reads: int = 0
    warnings: tuple[str, ...] = ()
