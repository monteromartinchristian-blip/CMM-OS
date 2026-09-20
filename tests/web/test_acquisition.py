"""The canonical information-acquisition binding of the one web backend."""

from __future__ import annotations

from datetime import UTC, datetime

from cmm.agent_runtime.enums import (
    InformationAcquisitionSource,
    InformationAcquisitionStrategy,
)
from cmm.web.acquisition import WebSearchAcquisitionHandler, register_web_search_handler
from cmm.web.contracts import WebResultItem, WebSearchResult
from cmm.web.errors import WebCapabilityError

NOW = datetime(2026, 9, 19, tzinfo=UTC)


class FakeRequest:
    def __init__(self, query=""):
        self.query = query
        self.gap = None


class FakeSearchService:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def search(self, request, cancel_event=None):
        if self.error is not None:
            raise self.error
        return self.result


RESULT = WebSearchResult(
    query="q",
    items=(
        WebResultItem(
            title="T",
            url="https://example.com/a",
            domain="example.com",
            snippet="s",
            rank=1,
            backend_id="duckduckgo-html",
            searched_at=NOW,
        ),
    ),
    backend_id="duckduckgo-html",
    searched_at=NOW,
)


def test_handler_maps_results_into_the_canonical_acquisition_shape():
    handler = WebSearchAcquisitionHandler(
        search_service=FakeSearchService(result=RESULT)
    )
    outcome = handler.execute(FakeRequest(query="q"), None)
    assert isinstance(outcome.source, InformationAcquisitionSource)
    assert outcome.source == InformationAcquisitionSource.EXTERNAL_SOURCE
    assert outcome.source_ids == ("https://example.com/a",)
    assert outcome.provenance == "cmm.web/duckduckgo-html"
    assert outcome.errors == ()


def test_handler_reports_normalized_errors_without_raising():
    handler = WebSearchAcquisitionHandler(
        search_service=FakeSearchService(
            error=WebCapabilityError("down", code="SEARCH_BACKEND_UNAVAILABLE")
        )
    )
    outcome = handler.execute(FakeRequest(query="q"), None)
    assert outcome.errors == ("SEARCH_BACKEND_UNAVAILABLE",)
    assert outcome.items == ()


def test_handler_reports_a_missing_query():
    handler = WebSearchAcquisitionHandler(
        search_service=FakeSearchService(result=RESULT)
    )
    outcome = handler.execute(FakeRequest(query=""), None)
    assert outcome.errors and outcome.confidence == 0.0


def test_registration_uses_the_canonical_strategy_enum():
    class FakeAcquisitionService:
        def __init__(self):
            self.registered = {}

        def register_handler(self, strategy, handler):
            self.registered[strategy] = handler

    service = FakeAcquisitionService()
    handler = register_web_search_handler(service)
    assert (
        service.registered[InformationAcquisitionStrategy.SEARCH_EXTERNAL_SOURCE]
        is handler
    )
