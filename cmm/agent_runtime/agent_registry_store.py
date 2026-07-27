"""Phase 9.23 – Agent Registry Store.

The store is the *only* persistence abstraction used by the registry in
phase 9.23. It stores ``AgentDescriptor`` instances indexed by
``(agent_id, version)``. Multiple versions of the same agent may coexist.

Responsibilities:

* deterministic ordering on read;
* thread-safe operations;
* alias and capability indexing;
* defensive snapshots;
* no external mutation (no live views returned).

The interface uses ``typing.Protocol`` so future in-memory, sqlite or
remote stores can be plugged in without changing the registry.
"""

from __future__ import annotations

import threading
from types import MappingProxyType
from typing import Protocol

from cmm.agent_runtime.agent_registry_contracts import AgentDescriptor, AgentVersion
from cmm.agent_runtime.agent_registry_errors import (
    AgentRegistryConflictError,
    AgentRegistryNotFoundError,
)


class AgentRegistryStore(Protocol):
    """Storage abstraction for agent descriptors.

    Implementations must be thread-safe and must return defensive
    snapshots – never live mutable state.
    """

    def add(self, descriptor: AgentDescriptor) -> None:
        """Register a new descriptor.

        Raises ``AgentRegistryConflictError`` when the same identity is
        already present (``(agent_id, version)``).
        """
        ...

    def remove(self, agent_id: str, version: AgentVersion) -> AgentDescriptor:
        """Remove and return the descriptor for ``(agent_id, version)``.

        Raises ``AgentRegistryNotFoundError`` when missing.
        """
        ...

    def get(self, agent_id: str, version: AgentVersion) -> AgentDescriptor | None:
        """Return the descriptor for ``(agent_id, version)`` or ``None``."""
        ...

    def list(self) -> tuple[AgentDescriptor, ...]:
        """Return a deterministic tuple of all stored descriptors."""
        ...

    def find_by_alias(self, alias: str) -> tuple[AgentDescriptor, ...]:
        """Return all descriptors exposing ``alias`` (deterministic)."""
        ...

    def find_by_capability(self, capability: str) -> tuple[AgentDescriptor, ...]:
        """Return all descriptors declaring capability ``capability``."""
        ...


class InMemoryAgentRegistryStore:
    """Thread-safe, deterministic, in-memory store.

    No persistence. Intended to be created fresh per test and per
    registry lifetime.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # canonical `_entries`: (agent_id, version.canonical()) -> AgentDescriptor
        self._entries: dict[tuple[str, str], AgentDescriptor] = {}
        # alias -> set of `(agent_id, version.canonical())`
        self._alias_index: dict[str, set[tuple[str, str]]] = {}
        # capability name -> set of `(agent_id, version.canonical())`
        self._capability_index: dict[str, set[tuple[str, str]]] = {}

    # ── internal helpers ────────────────────────────────────────────────────

    @staticmethod
    def _key(agent_id: str, version: AgentVersion) -> tuple[str, str]:
        return (agent_id, version.canonical())

    def _canonical_descriptors(
        self,
        keys: set[tuple[str, str]],
    ) -> tuple[AgentDescriptor, ...]:
        items: list[AgentDescriptor] = []
        for key in keys:
            d = self._entries.get(key)
            if d is not None:
                items.append(d)
        items.sort(key=lambda d: (d.agent_id, d.version.canonical(), d.lifecycle.value))
        return tuple(items)

    # ── AgentRegistryStore interface ───────────────────────────────────────

    def add(self, descriptor: AgentDescriptor) -> None:
        with self._lock:
            key = self._key(descriptor.agent_id, descriptor.version)
            if key in self._entries:
                raise AgentRegistryConflictError(
                    "Descriptor identity already registered",
                    {
                        "agent_id": descriptor.agent_id,
                        "version": descriptor.version.canonical(),
                    },
                )
            self._entries[key] = descriptor
            for alias in descriptor.aliases:
                bucket = self._alias_index.setdefault(alias, set())
                bucket.add(key)
            for cap in descriptor.capabilities:
                bucket = self._capability_index.setdefault(cap.name, set())
                bucket.add(key)

    def remove(self, agent_id: str, version: AgentVersion) -> AgentDescriptor:
        with self._lock:
            key = self._key(agent_id, version)
            descriptor = self._entries.pop(key, None)
            if descriptor is None:
                raise AgentRegistryNotFoundError(
                    "Descriptor not found",
                    {"agent_id": agent_id, "version": version.canonical()},
                )
            # rebuild indexes deterministically.
            for alias in descriptor.aliases:
                bucket = self._alias_index.get(alias)
                if bucket is not None:
                    bucket.discard(key)
                    if not bucket:
                        del self._alias_index[alias]
            for cap in descriptor.capabilities:
                bucket = self._capability_index.get(cap.name)
                if bucket is not None:
                    bucket.discard(key)
                    if not bucket:
                        del self._capability_index[cap.name]
            return descriptor

    def get(self, agent_id: str, version: AgentVersion) -> AgentDescriptor | None:
        with self._lock:
            return self._entries.get(self._key(agent_id, version))

    def list(self) -> tuple[AgentDescriptor, ...]:
        with self._lock:
            items = list(self._entries.values())
            items.sort(
                key=lambda d: (d.agent_id, d.version.canonical(), d.lifecycle.value)
            )
            return tuple(items)

    def find_by_alias(self, alias: str) -> tuple[AgentDescriptor, ...]:
        with self._lock:
            keys = self._alias_index.get(alias, set())
            return self._canonical_descriptors(set(keys))

    def find_by_capability(self, capability: str) -> tuple[AgentDescriptor, ...]:
        with self._lock:
            keys = self._capability_index.get(capability, set())
            return self._canonical_descriptors(set(keys))

    # ── Internal helpers used by AgentRegistry ─────────────────────────────

    def raw_snapshot(self) -> MappingProxyType[tuple[str, str], AgentDescriptor]:
        with self._lock:
            return MappingProxyType(dict(self._entries))

    def contains(self, agent_id: str, version: AgentVersion) -> bool:
        with self._lock:
            return self._key(agent_id, version) in self._entries

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._alias_index.clear()
            self._capability_index.clear()


__all__ = [
    "AgentRegistryStore",
    "InMemoryAgentRegistryStore",
]
