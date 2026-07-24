"""Thread-safe cooperative cancellation registry for Validation API (Phase 7.12)."""

from __future__ import annotations

import threading

from ..pipeline import CancellationToken


class ValidationCancellationRegistry:
    """Thread-safe registry for cooperative validation cancellation tokens."""

    def __init__(self) -> None:
        self._tokens: dict[str, CancellationToken] = {}
        self._lock = threading.Lock()

    def register(self, validation_id: str) -> CancellationToken:
        """Register and return a new CancellationToken for *validation_id*."""
        with self._lock:
            token = CancellationToken()
            self._tokens[validation_id] = token
            return token

    def get_token(self, validation_id: str) -> CancellationToken | None:
        """Return the CancellationToken for *validation_id* if active."""
        with self._lock:
            return self._tokens.get(validation_id)

    def cancel(self, validation_id: str) -> bool:
        """Signal cancellation for *validation_id*. Returns True if active token found."""
        with self._lock:
            token = self._tokens.get(validation_id)
            if token is not None:
                token.cancel()
                return True
            return False

    def unregister(self, validation_id: str) -> None:
        """Remove *validation_id* token when execution finishes."""
        with self._lock:
            self._tokens.pop(validation_id, None)


__all__ = ["ValidationCancellationRegistry"]
