"""Safe source retrieval: SSRF-guarded, size/time/type limited, normalized."""

from __future__ import annotations

import ipaddress
import socket
from threading import Event
from typing import Any
from urllib.parse import urlsplit

from cmm.web.contracts import FetchedSource, FetchRequest, domain_of, utc_now
from cmm.web.errors import WebCapabilityError
from cmm.web.html_text import extract_text

__all__ = ["fetch_source"]

_ALLOWED_CONTENT_TYPES = frozenset({"text/html", "application/xhtml+xml", "text/plain"})
_MAX_REDIRECTS = 5


def _guard_host(hostname: str) -> None:
    """Refuse non-public destinations (SSRF, local-file and metadata abuse)."""

    try:
        infos = socket.getaddrinfo(hostname, None)
    except OSError as error:
        raise WebCapabilityError(
            "The source host could not be resolved.", code="FETCH_FAILED"
        ) from error
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            raise WebCapabilityError(
                "The source address is not allowed.", code="SOURCE_BLOCKED"
            )


def fetch_source(
    request: FetchRequest,
    cancel_event: Event | None = None,
    *,
    transport: Any | None = None,
) -> FetchedSource:
    """Retrieve one web source as normalized text, or fail normalized."""

    parts = urlsplit(request.url)
    hostname = parts.hostname or ""
    if not hostname:
        raise WebCapabilityError("The source URL has no host.", code="FETCH_FAILED")
    _guard_host(hostname)

    client = transport
    if client is None:
        import httpx  # local import: the dependency is optional at import time

        client = httpx.Client(
            timeout=request.timeout,
            follow_redirects=True,
            max_redirects=_MAX_REDIRECTS,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 "
                    "Safari/605.1.15"
                )
            },
        )

    if cancel_event is not None and cancel_event.is_set():
        raise WebCapabilityError(
            "The source retrieval was cancelled.", code="CANCELLED"
        )

    try:
        response = client.request("GET", request.url)
    except WebCapabilityError:
        raise
    except Exception as error:  # noqa: BLE001 - normalized below
        name = type(error).__name__
        code = "FETCH_FAILED" if "Timeout" not in name else "SEARCH_TIMEOUT"
        raise WebCapabilityError(
            "The source could not be retrieved.", code=code
        ) from None

    status = int(response.status_code)
    if status in (401, 403, 451):
        raise WebCapabilityError("The source refused access.", code="SOURCE_BLOCKED")
    if status >= 400:
        raise WebCapabilityError(
            f"The source returned HTTP {status}.", code="FETCH_FAILED"
        )

    content_type = (
        str(response.headers.get("content-type", "")).split(";")[0].strip().lower()
    )
    if content_type and content_type not in _ALLOWED_CONTENT_TYPES:
        raise WebCapabilityError(
            "The source content type is not readable text.", code="SOURCE_BLOCKED"
        )

    body = response.content
    if isinstance(body, str):  # pragma: no cover - defensive for test doubles
        body = body.encode("utf-8", "replace")
    truncated = len(body) > request.max_bytes
    body = body[: request.max_bytes]
    text_encoding = "utf-8"
    html = body.decode(text_encoding, "replace")
    title, text = (
        extract_text(html)
        if content_type != "text/plain"
        else ("", html.strip()[:24_000])
    )
    if not text.strip():
        raise WebCapabilityError(
            "The source contained no readable text.", code="FETCH_FAILED"
        )

    final_url = str(getattr(response, "url", request.url) or request.url)
    return FetchedSource(
        url=request.url,
        final_url=final_url,
        domain=domain_of(final_url),
        title=title,
        text=text,
        content_type=content_type or "text/html",
        retrieved_at=utc_now(),
        truncated=truncated,
    )
