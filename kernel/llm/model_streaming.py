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

from kernel.llm.model_gateway_contracts import require_identifier
from kernel.llm.model_gateway_errors import ModelGatewayError, ModelGatewayErrorCode

__all__ = [
    "ModelCallCancellation",
    "ModelCallHandle",
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
