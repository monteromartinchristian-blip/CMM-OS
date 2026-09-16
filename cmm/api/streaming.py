"""Phase 11.3 — the SSE serialization boundary of the v1 HTTP adapter.

This module owns streaming delivery and nothing else: :func:`serialize_sse`
turns one public ``ApplicationStreamEvent`` into one deterministic SSE frame,
:func:`events_for_response` projects one safe public ``ApplicationResponse``
into the frozen event sequence of the stream route, and :func:`sse_frames`
yields them in order.  All three are pure functions over public contracts.

Three boundaries are deliberate:

- **adapter only** — a frame carries the application contract's own
  ``to_dict()`` projection and nothing else.  No field is renamed, reordered or
  invented here, so the application layer stays the owner of the public stream
  shape and a drifted event fails loudly at serialization instead of being
  published;
- **deterministic frames** — sorted compact JSON, no non-finite number and a
  frozen frame grammar, so the same event always produces the same bytes and the
  order of a stream is decided by its sequence, never by iteration of a mapping;
- **one result, no second execution engine** — the sequence is projected from
  one already-computed safe response.  The stream route invokes the application
  command exactly once, before the response body starts, so a stream can not
  re-run a command.  There is no background task system, no worker, no
  active-request registry, no WebSocket and no provider token stream: Phase 11.3
  streams the delivery of one result, not a new inference runtime.

See ``docs/reference/phase-11-application-backend.md``.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator

from cmm.application import (
    ApplicationResponse,
    ApplicationStreamEvent,
    StreamEventKind,
)

__all__ = [
    "SSE_MEDIA_TYPE",
    "events_for_response",
    "serialize_sse",
    "sse_frames",
]

#: The one media type of the frozen streaming transport.
SSE_MEDIA_TYPE = "text/event-stream"


def serialize_sse(event: ApplicationStreamEvent) -> str:
    """Return the one deterministic SSE frame of *event*.

    The frame grammar is frozen::

        event: <kind>
        id: <request_id>:<sequence>
        data: <canonical json>

    ``id`` carries the public correlation identity and the deterministic
    sequence of the event, so a client can order and correlate a stream without
    reading the payload.  ``data`` is the application contract's own public
    projection, serialized with sorted keys, no insignificant whitespace and
    ``allow_nan=False``, so a value the public grammar forbids fails closed here
    rather than producing a frame a client can not parse.  A line break inside
    the payload is escaped by the JSON encoding, so an event can never open a
    second frame or a second SSE field; the correlation identity can not carry
    one either, because a public identifier reaches this adapter through a
    header value, which can not contain a line break.
    """

    if not isinstance(event, ApplicationStreamEvent):
        raise TypeError(
            f"event must be an ApplicationStreamEvent, not {type(event).__name__}"
        )

    payload = json.dumps(
        event.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return (
        f"event: {event.kind.value}\n"
        f"id: {event.request_id}:{event.sequence}\n"
        f"data: {payload}\n"
        "\n"
    )


def events_for_response(
    response: ApplicationResponse,
) -> tuple[ApplicationStreamEvent, ...]:
    """Return the frozen public event sequence of one safe response.

    A successful response is delivered as ``STARTED``/``DATA``/``COMPLETED`` and
    a failed response as ``STARTED``/``ERROR``.  The projection is total and
    deterministic: identities come from the response, indices are the stream
    sequence, the ``DATA`` payload is exactly what the non-streaming route
    returns in ``data``, and the terminal event always names the terminal public
    status.  Because every event is projected from the safe response — and never
    from an internal object, exception or raw canonical payload — a frame can not
    carry hidden reasoning, provider output or internal error text.
    """

    if not isinstance(response, ApplicationResponse):
        raise TypeError(
            f"response must be an ApplicationResponse, not {type(response).__name__}"
        )

    started = ApplicationStreamEvent(
        request_id=response.request_id,
        sequence=0,
        kind=StreamEventKind.STARTED,
    )

    if response.error is not None:
        # The public contract requires an application error for the failed and
        # blocked statuses, so a response carrying one is the failure case and
        # its error event is terminal.
        return (
            started,
            ApplicationStreamEvent(
                request_id=response.request_id,
                sequence=1,
                kind=StreamEventKind.ERROR,
                data={"status": response.status.value},
                error=response.error,
            ),
        )

    return (
        started,
        ApplicationStreamEvent(
            request_id=response.request_id,
            sequence=1,
            kind=StreamEventKind.DATA,
            data=response.data,
        ),
        ApplicationStreamEvent(
            request_id=response.request_id,
            sequence=2,
            kind=StreamEventKind.COMPLETED,
            data={"status": response.status.value},
        ),
    )


def sse_frames(events: Iterable[ApplicationStreamEvent]) -> Iterator[str]:
    """Return the SSE frames of *events*, in the given deterministic order."""

    for event in events:
        yield serialize_sse(event)
