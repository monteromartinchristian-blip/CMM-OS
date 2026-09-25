"""Narrow model-call cancellation for the canonical Model Gateway (Phase 11.21).

Phase 11.21 owns cancellation of *one model call*.  It deliberately does not
create a global workflow, run or session cancellation authority: cancelling a
model call must never cancel unrelated work.

The cancellation object is a small, thread-safe, idempotent token.  Provider
adapters cooperate with it by observing :attr:`ModelCallCancellation.is_cancelled`
(or by registering a listener) and returning promptly; the gateway's stream
normalizer guarantees that a cancelled call ends in exactly one deterministic
``CANCELLED`` terminal event and emits no later content.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from kernel.llm.capabilities import ReasoningEffort
from kernel.llm.model_gateway_contracts import (
    ModelGatewayResponse,
    ModelStreamEvent,
    ModelStreamEventType,
    ModelToolCall,
    ModelUsage,
    require_identifier,
)
from kernel.llm.model_gateway_errors import ModelGatewayError, ModelGatewayErrorCode

__all__ = [
    "ModelCallCancellation",
    "ModelCallHandle",
    "ModelStreamNormalizer",
]

CancellationListener = Callable[[], None]


class ModelCallCancellation:
    """One narrow, idempotent, thread-safe model-call cancellation token."""

    __slots__ = ("_cancelled", "_listeners", "_lock", "_reason")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cancelled = False
        self._reason: str | None = None
        self._listeners: list[CancellationListener] = []

    @property
    def is_cancelled(self) -> bool:
        """Return whether cancellation was requested."""

        return self._cancelled

    @property
    def reason(self) -> str | None:
        """Return the safe cancellation reason, if one was supplied."""

        return self._reason

    def cancel(self, reason: str | None = None) -> bool:
        """Request cancellation; idempotent.

        Returns ``True`` only for the first effective cancellation request, so
        callers can distinguish "I cancelled this call" from "it was already
        cancelled".
        """

        with self._lock:
            if self._cancelled:
                return False
            self._cancelled = True
            self._reason = reason
            listeners = tuple(self._listeners)
            self._listeners.clear()
        for listener in listeners:
            listener()
        return True

    def add_listener(self, listener: CancellationListener) -> None:
        """Register a cooperative listener, fired once on cancellation.

        A listener registered after cancellation fires immediately, so an
        adapter can never miss the transition.
        """

        if not callable(listener):
            raise TypeError("listener must be callable")
        with self._lock:
            if not self._cancelled:
                self._listeners.append(listener)
                return
        listener()

    def raise_if_cancelled(self) -> None:
        """Raise the canonical cancellation outcome when already cancelled."""

        if self._cancelled:
            raise ModelGatewayError(
                ModelGatewayErrorCode.MODEL_CALL_CANCELLED,
                "model call was cancelled",
                retryable=False,
            )


@dataclass(frozen=True, slots=True)
class ModelCallHandle:
    """A handle for one in-flight model call.

    It exposes only that call's request id and its cancellation token: there is
    no workflow, run or session scope reachable from here.
    """

    request_id: str
    cancellation: ModelCallCancellation = field(default_factory=ModelCallCancellation)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", require_identifier(self.request_id, label="request_id")
        )
        if not isinstance(self.cancellation, ModelCallCancellation):
            raise TypeError("cancellation must be a ModelCallCancellation")

    @property
    def cancelled(self) -> bool:
        """Return whether this call was cancelled."""

        return self.cancellation.is_cancelled

    def cancel(self, reason: str | None = None) -> bool:
        """Cancel this model call; idempotent."""

        return self.cancellation.cancel(reason)


class ModelStreamNormalizer:
    """Bookkeeping that makes one provider stream canonically deterministic.

    It assigns contiguous sequence numbers, emits exactly one leading
    ``STARTED`` event, and refuses to emit anything after a terminal event.
    Carrier limits:

    * an adapter ``STARTED`` event is absorbed, never duplicated;
    * a second terminal event is dropped, so a stream can never report two
      outcomes;
    * a stream that ends without a terminal is closed by the caller with an
      explicit ``ERROR``.
    """

    __slots__ = ("_model_id", "_provider_id", "_request_id", "_sequence", "_terminal")

    def __init__(
        self,
        *,
        request_id: str,
        provider_id: str | None = None,
        model_id: str | None = None,
    ) -> None:
        self._request_id = require_identifier(request_id, label="request_id")
        self._provider_id = provider_id
        self._model_id = model_id
        self._sequence = 0
        self._terminal = False

    @property
    def terminal_seen(self) -> bool:
        """Return whether a terminal event was already emitted."""

        return self._terminal

    @property
    def sequence(self) -> int:
        """Return the sequence number the next emitted event will carry."""

        return self._sequence

    def started_event(
        self,
        *,
        effective_reasoning_effort: ReasoningEffort = ReasoningEffort.DEFAULT,
        reasoning_used: bool = False,
    ) -> ModelStreamEvent | None:
        """Emit the single leading ``STARTED`` event (``None`` if already sent)."""

        if self._sequence > 0 or self._terminal:
            return None
        return self._build(
            ModelStreamEventType.STARTED,
            effective_reasoning_effort=effective_reasoning_effort,
            reasoning_used=reasoning_used,
        )

    def content_event(self, content_delta: str) -> ModelStreamEvent | None:
        """Emit one normalized content delta, or drop it after a terminal."""

        if self._terminal:
            return None
        return self._build(
            ModelStreamEventType.CONTENT_DELTA,
            content_delta=content_delta,
        )

    def tool_call_event(self, tool_call: ModelToolCall) -> ModelStreamEvent | None:
        """Emit one normalized tool-call delta, or drop it after a terminal."""

        if self._terminal:
            return None
        return self._build(
            ModelStreamEventType.TOOL_CALL_DELTA,
            tool_call=tool_call,
        )

    def usage_event(self, usage: ModelUsage) -> ModelStreamEvent | None:
        """Emit one normalized usage event, or drop it after a terminal."""

        if self._terminal:
            return None
        return self._build(ModelStreamEventType.USAGE, usage=usage)

    def completed_event(
        self, response: ModelGatewayResponse
    ) -> ModelStreamEvent | None:
        """Emit the single ``COMPLETED`` terminal event."""

        if self._terminal:
            return None
        return self._build(ModelStreamEventType.COMPLETED, response=response)

    def cancelled_event(self) -> ModelStreamEvent | None:
        """Emit the single ``CANCELLED`` terminal event."""

        if self._terminal:
            return None
        return self._build(ModelStreamEventType.CANCELLED)

    def error_event(self, error: ModelGatewayError) -> ModelStreamEvent | None:
        """Emit the single ``ERROR`` terminal event for ``error``."""

        if self._terminal:
            return None
        if error.code is ModelGatewayErrorCode.MODEL_CALL_CANCELLED:
            return self.cancelled_event()
        return self._build(
            ModelStreamEventType.ERROR,
            error_code=error.code.value,
        )

    def _build(self, event_type: ModelStreamEventType, **fields: object):
        if event_type in {
            ModelStreamEventType.COMPLETED,
            ModelStreamEventType.CANCELLED,
            ModelStreamEventType.ERROR,
        }:
            if self._terminal:
                return None
            self._terminal = True
        event = ModelStreamEvent(
            event_type=event_type,
            request_id=self._request_id,
            sequence=self._sequence,
            provider_id=self._provider_id,
            model_id=self._model_id,
            **fields,  # type: ignore[arg-type]
        )
        self._sequence += 1
        return event
