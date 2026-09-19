"""Binding of the one web-search implementation into the canonical Agent
Runtime information-acquisition seam (no parallel capability authority)."""

from __future__ import annotations

from typing import Any

from cmm.agent_runtime.enums import (
    InformationAcquisitionSource,
    InformationAcquisitionStrategy,
)
from cmm.agent_runtime.information_acquisition import AcquisitionSearchResult
from cmm.web.contracts import WebSearchRequest
from cmm.web.errors import WebCapabilityError
from cmm.web.service import WebSearchService

__all__ = ["WebSearchAcquisitionHandler", "register_web_search_handler"]


class WebSearchAcquisitionHandler:
    """Read-only handler executing ``search_external_source`` via cmm.web."""

    def __init__(self, search_service: WebSearchService | None = None) -> None:
        self._search = search_service or WebSearchService()

    def execute(self, request: Any, candidate: Any) -> AcquisitionSearchResult:
        query = _request_query(request)
        if not query:
            return AcquisitionSearchResult(
                query="",
                source=InformationAcquisitionSource.EXTERNAL_SOURCE,
                errors=("no query in the acquisition request",),
                confidence=0.0,
            )
        try:
            result = self._search.search(WebSearchRequest(query=query))
        except WebCapabilityError as error:
            return AcquisitionSearchResult(
                query=query,
                source=InformationAcquisitionSource.EXTERNAL_SOURCE,
                errors=(error.code,),
                confidence=0.0,
                provenance="cmm.web",
            )
        return AcquisitionSearchResult(
            query=query,
            source=InformationAcquisitionSource.EXTERNAL_SOURCE,
            source_ids=tuple(item.url for item in result.items),
            provenance=f"cmm.web/{result.backend_id}",
            confidence=0.8,
            items=result.items,
            metadata={"backend_id": result.backend_id},
        )


def register_web_search_handler(
    acquisition_service: Any, handler: WebSearchAcquisitionHandler | None = None
) -> WebSearchAcquisitionHandler:
    """Register the canonical external-search handler on an acquisition service."""

    resolved = handler or WebSearchAcquisitionHandler()
    acquisition_service.register_handler(
        InformationAcquisitionStrategy.SEARCH_EXTERNAL_SOURCE, resolved
    )
    return resolved


def _request_query(request: Any) -> str:
    for attribute in ("query", "question"):
        value = getattr(request, attribute, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    gap = getattr(request, "gap", None)
    if isinstance(gap, str):
        return gap.strip()
    for attribute in ("description", "query", "question"):
        value = getattr(gap, attribute, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
