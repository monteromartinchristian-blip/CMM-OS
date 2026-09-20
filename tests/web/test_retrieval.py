"""Safe retrieval: SSRF guard, type/size limits, extraction, normalization."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from cmm.web.contracts import FetchRequest
from cmm.web.errors import WebCapabilityError
from cmm.web.html_text import extract_text
from cmm.web.retrieval import fetch_source


@pytest.fixture(autouse=True)
def offline_dns(monkeypatch):
    """Resolve public test hosts without touching the network."""

    import socket

    real = socket.getaddrinfo
    local_hosts = {"127.0.0.1", "localhost", "::1", "192.168.1.1", "169.254.169.254"}

    def fake(host, *args, **kwargs):
        if host in local_hosts:
            return real(host, *args, **kwargs)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake)


@dataclass
class FakeResponse:
    status_code: int = 200
    content: bytes = b""
    headers: dict = field(default_factory=lambda: {"content-type": "text/html"})
    url: str = "https://example.com/page"


class FakeTransport:
    def __init__(self, response):
        self.response = response

    def request(self, method, url, **kwargs):
        if isinstance(self.response, BaseException):
            raise self.response
        return self.response


HTML = (
    "<html><head><title>  Pagina Real  </title>"
    "<style>body{}</style><script>var secret=1;</script></head>"
    "<body><h1>Titular</h1><p>Texto   principal.</p></body></html>"
)


def test_loopback_and_private_hosts_are_refused():
    for url in (
        "http://127.0.0.1/admin",
        "http://localhost:8000/v1/models",
        "http://[::1]/x",
        "http://192.168.1.1/router",
        "http://169.254.169.254/latest/meta-data",
    ):
        with pytest.raises(WebCapabilityError) as info:
            fetch_source(FetchRequest(url=url), transport=FakeTransport(FakeResponse()))
        assert info.value.code == "SOURCE_BLOCKED", url


def test_html_is_extracted_without_scripts_and_title_is_kept():
    source = fetch_source(
        FetchRequest(url="https://example.com/page"),
        transport=FakeTransport(FakeResponse(content=HTML.encode())),
    )
    assert source.title == "Pagina Real"
    assert "secret" not in source.text
    assert "Texto principal." in source.text
    assert source.domain == "example.com"
    assert source.fetched is True and source.truncated is False


def test_oversized_body_is_truncated_not_rejected():
    body = b"<p>" + b"x" * 5000 + b"</p>"
    source = fetch_source(
        FetchRequest(url="https://example.com/big", max_bytes=1000),
        transport=FakeTransport(
            FakeResponse(content=body, url="https://example.com/big")
        ),
    )
    assert source.truncated is True
    assert len(source.text) <= 1000


def test_non_text_content_types_are_blocked():
    with pytest.raises(WebCapabilityError) as info:
        fetch_source(
            FetchRequest(url="https://example.com/file.bin"),
            transport=FakeTransport(
                FakeResponse(
                    content=b"MZ", headers={"content-type": "application/octet-stream"}
                )
            ),
        )
    assert info.value.code == "SOURCE_BLOCKED"


def test_http_errors_normalize():
    with pytest.raises(WebCapabilityError) as info:
        fetch_source(
            FetchRequest(url="https://example.com/forbidden"),
            transport=FakeTransport(FakeResponse(status_code=403)),
        )
    assert info.value.code == "SOURCE_BLOCKED"
    with pytest.raises(WebCapabilityError) as info:
        fetch_source(
            FetchRequest(url="https://example.com/gone"),
            transport=FakeTransport(FakeResponse(status_code=500)),
        )
    assert info.value.code == "FETCH_FAILED"


def test_transport_failure_normalizes_without_leaking_detail():
    with pytest.raises(WebCapabilityError) as info:
        fetch_source(
            FetchRequest(url="https://example.com/x"),
            transport=FakeTransport(RuntimeError("bearer=SECRET")),
        )
    assert info.value.code == "FETCH_FAILED"
    assert "SECRET" not in info.value.message


def test_plain_text_passes_through():
    source = fetch_source(
        FetchRequest(url="https://example.com/notes.txt"),
        transport=FakeTransport(
            FakeResponse(
                content=b"linea uno\nlinea dos",
                headers={"content-type": "text/plain; charset=utf-8"},
            )
        ),
    )
    assert source.text.startswith("linea uno")


def test_extract_text_strips_skipped_tags():
    title, text = extract_text(
        "<html><head><title>T</title><script>bad()</script></head>"
        "<body><div>uno</div><noscript>no</noscript>dos</body></html>"
    )
    assert title == "T"
    assert "bad()" not in text and "no" not in text.split()
    assert "uno" in text and "dos" in text
