"""Normalized search: backend parsing, fallback, domain policy, error codes."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from cmm.web.contracts import WebSearchRequest
from cmm.web.errors import WebCapabilityError
from cmm.web.backends.duckduckgo_html import DuckDuckGoHtmlBackend
from cmm.web.backends.wikipedia_rest import WikipediaRestBackend
from cmm.web.service import WebSearchService

DDG_HTML = """
<html><body>
<div class="result">
  <a rel="nofollow" class="result__a"
     href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.boe.es%2Fbuscador%2Fdoc.php%3Fid%3DBOE-A-1&amp;rut=1">
     BOE — Documento</a>
  <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.boe.es">
     Fragmento <b>resaltado</b> del resultado.</a>
</div>
<div class="result">
  <a class="result__a" href="https://example.org/page">Example Org</a>
  <div class="result__snippet">Second snippet body.</div>
</div>
</body></html>
"""


@dataclass
class FakeResponse:
    status_code: int = 200
    text: str = ""
    headers: dict | None = None


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def test_ddg_backend_parses_normalized_items():
    transport = FakeTransport([FakeResponse(200, DDG_HTML)])
    backend = DuckDuckGoHtmlBackend(transport=transport, sleep=lambda _: None)
    items = backend.search("boe documento", 8)
    assert [item.url for item in items] == [
        "https://www.boe.es/buscador/doc.php?id=BOE-A-1",
        "https://example.org/page",
    ]
    first = items[0]
    assert first.title == "BOE — Documento"
    assert first.domain == "boe.es"
    assert "Fragmento" in first.snippet
    assert (first.rank, first.backend_id) == (1, "duckduckgo-html")
    assert transport.calls[0][0] == "POST"


def test_ddg_block_is_soft_and_service_falls_back_to_wikipedia():
    blocked = DuckDuckGoHtmlBackend(
        transport=FakeTransport([FakeResponse(202, ""), FakeResponse(202, "")]),
        sleep=lambda _: None,
    )
    wiki_json = (
        '{"pages":[{"key":"Madrid","title":"Madrid",'
        '"excerpt":"Capital of <em>Spain</em>."}]}'
    )
    wiki = WikipediaRestBackend(transport=FakeTransport([FakeResponse(200, wiki_json)]))
    service = WebSearchService(backends=(blocked, wiki))
    result = service.search(WebSearchRequest(query="madrid"))
    assert result.backend_id == "wikipedia-rest"
    assert result.items[0].url == "https://en.wikipedia.org/wiki/Madrid"
    assert "<" not in result.items[0].snippet


def test_all_backends_failing_normalizes_one_error():
    failing = DuckDuckGoHtmlBackend(
        transport=FakeTransport([RuntimeError("boom"), RuntimeError("boom")]),
        sleep=lambda _: None,
    )
    service = WebSearchService(backends=(failing,))
    with pytest.raises(WebCapabilityError) as info:
        service.search(WebSearchRequest(query="x"))
    assert info.value.code == "SEARCH_BACKEND_UNAVAILABLE"
    assert "boom" not in info.value.message


def test_timeout_maps_to_search_timeout():
    class TimeoutError_(Exception):
        pass

    TimeoutError_.__name__ = "ConnectTimeout"
    backend = DuckDuckGoHtmlBackend(
        transport=FakeTransport([TimeoutError_(), TimeoutError_()]),
        sleep=lambda _: None,
    )
    with pytest.raises(WebCapabilityError) as info:
        backend.search("x", 5)
    assert info.value.code == "SEARCH_TIMEOUT"


def test_domain_policy_filters_results():
    transport = FakeTransport([FakeResponse(200, DDG_HTML)])
    service = WebSearchService(
        backends=(DuckDuckGoHtmlBackend(transport=transport, sleep=lambda _: None),)
    )
    result = service.search(
        WebSearchRequest(query="boe", allowed_domains=("boe.es",))
    )
    assert [item.domain for item in result.items] == ["boe.es"]

    transport2 = FakeTransport([FakeResponse(200, DDG_HTML)])
    service2 = WebSearchService(
        backends=(DuckDuckGoHtmlBackend(transport=transport2, sleep=lambda _: None),)
    )
    with pytest.raises(WebCapabilityError) as info:
        service2.search(
            WebSearchRequest(query="boe", prohibited_domains=("boe.es", "example.org"))
        )
    assert info.value.code == "SEARCH_BLOCKED"


def test_cancel_before_backend_raises_cancelled():
    from threading import Event

    event = Event()
    event.set()
    service = WebSearchService(
        backends=(DuckDuckGoHtmlBackend(transport=FakeTransport([])),)
    )
    with pytest.raises(WebCapabilityError) as info:
        service.search(WebSearchRequest(query="x"), cancel_event=event)
    assert info.value.code == "CANCELLED"


def test_request_contract_validation():
    with pytest.raises(ValueError):
        WebSearchRequest(query="  ")
    with pytest.raises(ValueError):
        WebSearchRequest(query="x", limit=0)
