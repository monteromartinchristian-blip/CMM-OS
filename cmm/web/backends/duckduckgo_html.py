"""DuckDuckGo HTML backend — key-free real web search.

POST form mode with a browser User-Agent is the reliable shape (GET on the
lite endpoint is challenge-prone).  Anti-bot interstitials (202/403) are
normalized as ``SEARCH_BLOCKED`` so the service can fall through to the next
backend instead of failing the run.
"""

from __future__ import annotations

import time
from html.parser import HTMLParser
from typing import Any, Protocol
from urllib.parse import parse_qs, unquote, urlsplit

from cmm.web.contracts import WebResultItem, domain_of, utc_now
from cmm.web.errors import WebCapabilityError

__all__ = ["DuckDuckGoHtmlBackend", "HttpTransport"]

ENDPOINT = "https://html.duckduckgo.com/html/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15"
)


class HttpTransport(Protocol):
    """Minimal transport contract (httpx.Client satisfies it)."""

    def request(self, method: str, url: str, **kwargs: Any) -> Any: ...


class _ResultParser(HTMLParser):
    """Collect result anchors and snippets from the DDG HTML layout."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []  # (href, title)
        self.snippets: list[str] = []
        self._current_link: list[str] | None = None
        self._current_href: str | None = None
        self._in_snippet = False
        self._snippet_parts: list[str] = []

    @staticmethod
    def _classes(attrs) -> set[str]:
        for name, value in attrs:
            if name == "class" and value:
                return set(value.split())
        return set()

    def handle_starttag(self, tag: str, attrs) -> None:
        classes = self._classes(attrs)
        if tag == "a" and "result__a" in classes:
            href = dict(attrs).get("href", "")
            self._current_link = []
            self._current_href = href
        elif tag in ("a", "div") and "result__snippet" in classes:
            self._in_snippet = True
            self._snippet_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_link is not None:
            title = "".join(self._current_link).strip()
            if self._current_href:
                self.links.append((self._current_href, title))
            self._current_link = None
            self._current_href = None
        if tag in ("a", "div") and self._in_snippet:
            self._in_snippet = False
            self.snippets.append(" ".join("".join(self._snippet_parts).split()))

    def handle_data(self, data: str) -> None:
        if self._current_link is not None:
            self._current_link.append(data)
        if self._in_snippet:
            self._snippet_parts.append(data)


def _resolve_result_url(href: str) -> str | None:
    """Decode DDG's redirect wrapper into the real destination URL."""

    if href.startswith("//"):
        href = "https:" + href
    parts = urlsplit(href)
    if parts.netloc.endswith("duckduckgo.com") and parts.path.startswith("/l/"):
        uddg = parse_qs(parts.query).get("uddg", [""])[0]
        href = unquote(uddg)
    if urlsplit(href).scheme not in ("http", "https"):
        return None
    return href


class DuckDuckGoHtmlBackend:
    backend_id = "duckduckgo-html"

    def __init__(
        self,
        *,
        transport: HttpTransport | None = None,
        sleep: Any = time.sleep,
        attempts: int = 2,
    ) -> None:
        self._transport = transport
        self._sleep = sleep
        self._attempts = max(1, attempts)

    def _client(self) -> HttpTransport:
        if self._transport is not None:
            return self._transport
        import httpx  # local import: the dependency is optional at import time

        return httpx.Client(timeout=15.0, follow_redirects=True)

    def search(self, query: str, limit: int) -> tuple[WebResultItem, ...]:
        last_error: WebCapabilityError | None = None
        for attempt in range(self._attempts):
            if attempt:
                self._sleep(0.5 * attempt)
            try:
                response = self._client().request(
                    "POST",
                    ENDPOINT,
                    data={"q": query, "kl": "es-es"},
                    headers={"User-Agent": USER_AGENT},
                )
            except Exception as error:  # noqa: BLE001 - normalized below
                name = type(error).__name__
                if "Timeout" in name:
                    last_error = WebCapabilityError(
                        "The web search backend timed out.", code="SEARCH_TIMEOUT"
                    )
                else:
                    last_error = WebCapabilityError(
                        "The web search backend could not be reached.",
                        code="SEARCH_BACKEND_UNAVAILABLE",
                    )
                continue
            status = int(response.status_code)
            if status in (202, 403, 429):
                last_error = WebCapabilityError(
                    "The web search backend refused the request.",
                    code="SEARCH_BLOCKED",
                )
                continue
            if status != 200:
                last_error = WebCapabilityError(
                    "The web search backend returned an error.",
                    code="SEARCH_BACKEND_UNAVAILABLE",
                )
                continue
            return self._parse(response.text, limit)
        assert last_error is not None  # noqa: S101 - loop always assigns
        raise last_error

    def _parse(self, html: str, limit: int) -> tuple[WebResultItem, ...]:
        parser = _ResultParser()
        parser.feed(html)
        parser.close()
        searched_at = utc_now()
        items: list[WebResultItem] = []
        seen: set[str] = set()
        for rank, (href, title) in enumerate(parser.links, start=1):
            url = _resolve_result_url(href)
            if url is None or url in seen or not title:
                continue
            seen.add(url)
            snippet = (
                parser.snippets[len(items)]
                if len(items) < len(parser.snippets)
                else ""
            )
            items.append(
                WebResultItem(
                    title=title,
                    url=url,
                    domain=domain_of(url),
                    snippet=snippet,
                    rank=rank,
                    backend_id=self.backend_id,
                    searched_at=searched_at,
                )
            )
            if len(items) >= limit:
                break
        if not items:
            raise WebCapabilityError(
                "The web search backend returned no parseable result.",
                code="SEARCH_BACKEND_UNAVAILABLE",
            )
        return tuple(items)
