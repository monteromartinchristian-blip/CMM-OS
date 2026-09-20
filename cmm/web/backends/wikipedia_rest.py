"""Wikipedia REST search backend — structured JSON fallback/enrichment."""

from __future__ import annotations

import json
import re

from cmm.web.backends.duckduckgo_html import HttpTransport
from cmm.web.contracts import WebResultItem, domain_of, utc_now
from cmm.web.errors import WebCapabilityError

__all__ = ["WikipediaRestBackend"]

ENDPOINT = "https://en.wikipedia.org/w/rest.php/v1/search/page"
_TAG = re.compile(r"<[^>]+>")


class WikipediaRestBackend:
    backend_id = "wikipedia-rest"

    def __init__(self, *, transport: HttpTransport | None = None) -> None:
        self._transport = transport

    def _client(self) -> HttpTransport:
        if self._transport is not None:
            return self._transport
        import httpx  # local import: the dependency is optional at import time

        return httpx.Client(timeout=15.0, follow_redirects=True)

    def search(self, query: str, limit: int) -> tuple[WebResultItem, ...]:
        try:
            response = self._client().request(
                "GET",
                ENDPOINT,
                params={"q": query, "limit": min(limit, 10)},
                headers={"User-Agent": "CMM-OS-WebCapability/1.0"},
            )
        except Exception as error:  # noqa: BLE001 - normalized below
            name = type(error).__name__
            code = (
                "SEARCH_TIMEOUT" if "Timeout" in name else "SEARCH_BACKEND_UNAVAILABLE"
            )
            raise WebCapabilityError(
                "The web search backend could not be reached.", code=code
            ) from None
        if int(response.status_code) != 200:
            raise WebCapabilityError(
                "The web search backend returned an error.",
                code="SEARCH_BACKEND_UNAVAILABLE",
            )
        try:
            payload = json.loads(response.text)
            pages = payload.get("pages", [])
        except (json.JSONDecodeError, AttributeError) as error:
            raise WebCapabilityError(
                "The web search backend returned a malformed result.",
                code="SEARCH_BACKEND_UNAVAILABLE",
            ) from error
        searched_at = utc_now()
        items: list[WebResultItem] = []
        for rank, page in enumerate(pages, start=1):
            key = str(page.get("key") or "").strip()
            title = str(page.get("title") or "").strip()
            if not key or not title:
                continue
            url = f"https://en.wikipedia.org/wiki/{key}"
            snippet = _TAG.sub("", str(page.get("excerpt") or "")).strip()
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
                "The web search backend returned no result.",
                code="SEARCH_BACKEND_UNAVAILABLE",
            )
        return tuple(items)
