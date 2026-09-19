"""The provider-independent search service over ordered backends."""

from __future__ import annotations

from threading import Event
from typing import Protocol

from cmm.web.contracts import (
    WebResultItem,
    WebSearchRequest,
    WebSearchResult,
    domain_of,
    utc_now,
)
from cmm.web.errors import WebCapabilityError

__all__ = ["SearchBackend", "WebSearchService", "default_backends"]


class SearchBackend(Protocol):
    backend_id: str

    def search(self, query: str, limit: int) -> tuple[WebResultItem, ...]: ...


def default_backends() -> tuple[SearchBackend, ...]:
    from cmm.web.backends.duckduckgo_html import DuckDuckGoHtmlBackend
    from cmm.web.backends.wikipedia_rest import WikipediaRestBackend

    return (DuckDuckGoHtmlBackend(), WikipediaRestBackend())


class WebSearchService:
    """One normalized search boundary; backend identity never escapes."""

    def __init__(self, backends: tuple[SearchBackend, ...] | None = None) -> None:
        resolved = tuple(backends) if backends is not None else default_backends()
        if not resolved:
            raise ValueError("at least one search backend is required")
        self._backends = resolved

    def search(
        self, request: WebSearchRequest, cancel_event: Event | None = None
    ) -> WebSearchResult:
        query = request.query.strip()
        failures: list[WebCapabilityError] = []
        for backend in self._backends:
            if cancel_event is not None and cancel_event.is_set():
                raise WebCapabilityError(
                    "The web search was cancelled.", code="CANCELLED"
                )
            try:
                items = backend.search(query, request.limit)
            except WebCapabilityError as error:
                failures.append(error)
                continue
            filtered = self._apply_domain_policy(items, request)
            if not filtered:
                failures.append(
                    WebCapabilityError(
                        "The web search backend returned no allowed result.",
                        code="SEARCH_BLOCKED",
                    )
                )
                continue
            return WebSearchResult(
                query=query,
                items=filtered,
                backend_id=backend.backend_id,
                searched_at=utc_now(),
            )
        code = failures[0].code if failures else "SEARCH_BACKEND_UNAVAILABLE"
        if code == "CANCELLED":
            raise WebCapabilityError("The web search was cancelled.", code="CANCELLED")
        raise WebCapabilityError(
            "No web search backend could answer the request.", code=code
        )

    @staticmethod
    def _apply_domain_policy(
        items: tuple[WebResultItem, ...], request: WebSearchRequest
    ) -> tuple[WebResultItem, ...]:
        allowed = tuple(domain_of(f"https://{d}") for d in request.allowed_domains)
        prohibited = tuple(
            domain_of(f"https://{d}") for d in request.prohibited_domains
        )
        kept: list[WebResultItem] = []
        for item in items:
            if allowed and not any(
                item.domain == domain or item.domain.endswith(f".{domain}")
                for domain in allowed
            ):
                continue
            if any(
                item.domain == domain or item.domain.endswith(f".{domain}")
                for domain in prohibited
            ):
                continue
            kept.append(item)
        return tuple(kept)
