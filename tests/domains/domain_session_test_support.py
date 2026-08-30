"""Shared test support for Phase 10.34 Domain Sessions.

Successful Domain Session resumption must cross the real shared-session
persistence boundary. A no-op callback is not durable persistence.
"""

from __future__ import annotations

from typing import Any

from cmm.domains.session_persistence import SharedSessionDomainAdapter
from cmm.runtime.sessions import InMemorySessionStore


class FailingSessionStore:
    """Shared store double whose durable save always fails."""

    def __init__(self, error: Exception | None = None) -> None:
        self._inner = InMemorySessionStore()
        self._error = error or RuntimeError("shared session persistence failed")

    def load(self, session_id: str) -> Any:
        return self._inner.load(session_id)

    def save(self, state: Any) -> Any:
        raise self._error


def shared_session_adapter() -> SharedSessionDomainAdapter:
    """Return an isolated authoritative shared-session adapter."""
    return SharedSessionDomainAdapter(store=InMemorySessionStore())


def failing_shared_session_adapter(
    error: Exception | None = None,
) -> SharedSessionDomainAdapter:
    """Return an adapter whose authoritative store rejects the commit."""
    return SharedSessionDomainAdapter(store=FailingSessionStore(error))
