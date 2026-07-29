"""Phase 9.23 – Agent Factory Contracts.

This module defines:

* the ``AgentFactory`` ``Protocol`` that all factory implementations
  must follow;
* the ``AgentFactoryContext`` immutable input to a factory;
* the ``AgentFactoryRegistration`` structured result of registering a
  factory;
* a typed ``AgentFactoryErrorInfo`` payload used by the factory
  registry to surface failures safely.

The factory contract is intentionally minimal: it does not specify how
the runtime object is implemented, what fields it has, or how it
serializes. The contract only guarantees that:

1. ``factory_id`` is stable and unique within a registry;
2. ``scope`` is one of the four documented scopes;
3. ``supports()`` is a pure predicate;
4. ``create()`` returns an ``AgentInstance`` (never ``None``);
5. the ``runtime_object`` produced is opaque.

All factories are duck-typed. They are *not* required to inherit from
a base class, only to expose the documented attributes/methods.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from cmm.agent_runtime.agent_registry_contracts import (
    AgentDescriptor,
    AgentFactoryContext,
    AgentInstance,
)
from cmm.agent_runtime.agent_registry_enums import AgentFactoryScope
from cmm.agent_runtime.agent_registry_errors import (
    AgentFactoryCompatibilityError,
    AgentFactoryCreationError,
    AgentFactoryError,
)

# ── AgentFactory protocol ───────────────────────────────────────────────────


@runtime_checkable
class AgentFactory(Protocol):
    """Minimal contract for any concrete factory implementation."""

    @property
    def factory_id(self) -> str:
        """Stable identifier of the factory."""
        ...

    @property
    def scope(self) -> AgentFactoryScope:
        """Lifetime scope of created instances."""
        ...

    @property
    def thread_safe(self) -> bool:
        """Whether the factory is safe to call from multiple threads.

        Required to be ``True`` for ``SINGLETON`` factories.
        """
        ...

    def supports(self, descriptor: AgentDescriptor) -> bool:
        """Return ``True`` if this factory can create instances of ``descriptor``."""
        ...

    def create(
        self,
        descriptor: AgentDescriptor,
        context: AgentFactoryContext,
    ) -> AgentInstance:
        """Create a new ``AgentInstance`` for ``descriptor``.

        Must raise ``AgentFactoryCreationError`` on failure; must never
        return ``None`` or an instance whose descriptor does not match
        the requested one.
        """
        ...


# ── Registration result ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentFactoryRegistration:
    """Structured outcome of registering a factory."""

    factory_id: str
    scope: AgentFactoryScope
    thread_safe: bool
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not isinstance(self.factory_id, str) or not self.factory_id.strip():
            raise AgentFactoryError(
                "AgentFactoryRegistration factory_id must be non-empty",
                {"field": "factory_id"},
            )
        if not isinstance(self.scope, AgentFactoryScope):
            raise AgentFactoryError(
                "AgentFactoryRegistration scope must be AgentFactoryScope",
                {"field": "scope"},
            )
        if not isinstance(self.thread_safe, bool):
            raise AgentFactoryError(
                "AgentFactoryRegistration thread_safe must be bool",
                {"field": "thread_safe"},
            )
        if self.registered_at.tzinfo is None:
            raise AgentFactoryError(
                "AgentFactoryRegistration registered_at must be tz-aware",
                {"field": "registered_at"},
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "factory_id": self.factory_id,
            "scope": self.scope.value,
            "thread_safe": self.thread_safe,
            "registered_at": self.registered_at.isoformat(),
        }


# ── Factory registry snapshot ────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentFactoryRegistrySnapshot:
    """Immutable, JSON-safe snapshot of the factory registry state."""

    captured_at: datetime
    factories: tuple[AgentFactoryRegistration, ...]
    snapshot_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "captured_at": self.captured_at.isoformat(),
            "snapshot_version": self.snapshot_version,
            "factories": [f.to_dict() for f in self.factories],
        }


# ── Internal helper used by factories for defensive checks ──────────────────


def assert_descriptor_match(instance: AgentInstance, expected: AgentDescriptor) -> None:
    """Raise ``AgentFactoryCreationError`` if ``instance.descriptor`` ≠ ``expected``."""
    if instance.descriptor != expected:
        raise AgentFactoryCreationError(
            "Factory returned an instance with a non-matching descriptor",
            {
                "expected_agent_id": expected.agent_id,
                "expected_version": expected.version.canonical(),
                "actual_agent_id": instance.descriptor.agent_id,
                "actual_version": instance.descriptor.version.canonical(),
            },
        )


def assert_compatible_scope(factory: Any, expected_scope: AgentFactoryScope) -> None:
    """Raise ``AgentFactoryCompatibilityError`` if factory scope ≠ expected."""
    actual = getattr(factory, "scope", None)
    if actual != expected_scope:
        raise AgentFactoryCompatibilityError(
            "Factory scope does not match expected scope",
            {
                "expected": expected_scope.value,
                "actual": getattr(actual, "value", str(actual)),
            },
        )


__all__ = [
    "AgentFactory",
    "AgentFactoryRegistration",
    "AgentFactoryRegistrySnapshot",
    "assert_compatible_scope",
    "assert_descriptor_match",
]
