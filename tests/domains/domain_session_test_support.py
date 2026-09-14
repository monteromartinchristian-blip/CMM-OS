"""Shared test support for Phase 10.34 Domain Sessions.

Successful Domain Session resumption must cross the real shared-session
persistence boundary. A no-op callback is not durable persistence.
"""

from __future__ import annotations

from typing import Any

from cmm.domains.enums import DomainResolutionStatus
from cmm.domains.identifiers import DomainId
from cmm.domains.resolution_contracts import DomainResolutionContext
from cmm.domains.resolver_contracts import DomainResolutionResult
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


class StubDomainResolver:
    """Deterministic canonical resolver double for Phase 10.34 tests."""

    def __init__(
        self,
        primary_slug: str = "general",
        supporting_slugs: tuple[str, ...] = (),
        resolution_id: str = "res-stub-001",
        status: DomainResolutionStatus = DomainResolutionStatus.RESOLVED,
        confidence: float = 0.95,
    ) -> None:
        self.primary_slug = primary_slug
        self.supporting_slugs = supporting_slugs
        self.resolution_id = resolution_id
        self.status = status
        self.confidence = confidence
        self.invoked_with: list[DomainResolutionContext] = []

    def resolve(self, context: DomainResolutionContext) -> DomainResolutionResult:
        self.invoked_with.append(context)
        return DomainResolutionResult(
            id=self.resolution_id,
            context_id=context.id,
            status=self.status,
            primary_domain=DomainId(slug=self.primary_slug),
            supporting_domains=tuple(DomainId(slug=s) for s in self.supporting_slugs),
            confidence=self.confidence,
        )


def shared_session_adapter() -> SharedSessionDomainAdapter:
    """Return an isolated authoritative shared-session adapter."""
    return SharedSessionDomainAdapter(store=InMemorySessionStore())


def failing_shared_session_adapter(
    error: Exception | None = None,
) -> SharedSessionDomainAdapter:
    """Return an adapter whose authoritative store rejects the commit."""
    return SharedSessionDomainAdapter(store=FailingSessionStore(error))
