"""Phase 9.23 – Agent Registry.

Façade in front of an ``AgentRegistryStore``. The registry:

* validates descriptors before storage;
* enforces alias uniqueness across agents (unless the alias targets the
  same identity);
* exposes ``register/unregister/get/list/find_by_*`` plus lifecycle
  transitions ``enable/disable/deprecate/retire``;
* never mutates immutable descriptors in-place – lifecycle changes go
  through :py:meth:`AgentDescriptor.with_lifecycle` and re-registration;
* is fully thread-safe.

Registry does *not* decide resolution policy: that's the resolver's job.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.agent_registry_contracts import (
    AgentDescriptor,
    AgentVersion,
)
from cmm.agent_runtime.agent_registry_enums import (
    AgentKind,
    AgentLifecycle,
    AgentRegistrationStatus,
)
from cmm.agent_runtime.agent_registry_errors import (
    AgentRegistryAliasConflictError,
    AgentRegistryConflictError,
    AgentRegistryDisabledError,
    AgentRegistryError,
    AgentRegistryNotFoundError,
)
from cmm.agent_runtime.agent_registry_store import (
    AgentRegistryStore,
    InMemoryAgentRegistryStore,
)
from cmm.agent_runtime.agent_registry_validation import AgentDescriptorValidator


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class AgentRegistrySnapshot:
    """Immutable, JSON-safe snapshot of registry state."""

    def __init__(
        self,
        captured_at: datetime,
        descriptors: tuple[AgentDescriptor, ...],
        snapshot_version: str,
    ) -> None:
        self.captured_at = captured_at
        self.descriptors = descriptors
        self.snapshot_version = snapshot_version

    def to_dict(self) -> dict[str, Any]:
        return {
            "captured_at": self.captured_at.isoformat(),
            "snapshot_version": self.snapshot_version,
            "descriptors": [d.to_dict() for d in self.descriptors],
        }


class AgentRegistry:
    """High-level registry for agent descriptors."""

    _SNAPSHOT_VERSION = "9.23.0"

    def __init__(
        self,
        store: AgentRegistryStore | None = None,
        *,
        validator: AgentDescriptorValidator | None = None,
    ) -> None:
        self._store: AgentRegistryStore = store or InMemoryAgentRegistryStore()
        self._validator = validator or AgentDescriptorValidator()
        self._lock = threading.RLock()
        # alias registry: alias -> { (agent_id, version.canonical()) }
        self._alias_owners: dict[str, set[tuple[str, str]]] = {}

    # ── alias bookkeeping ──────────────────────────────────────────────────

    @staticmethod
    def _key(agent_id: str, version: AgentVersion) -> tuple[str, str]:
        return (agent_id, version.canonical())

    def _reserve_aliases(self, descriptor: AgentDescriptor) -> set[str]:
        """Reserve aliases for ``descriptor``.

        Returns the set of aliases that were *newly* reserved (i.e. not
        already owned by this same identity). If the reservation fails,
        the caller must call :py:meth:`_release_reserved_aliases` with
        that set to roll back.
        """
        identity = self._key(descriptor.agent_id, descriptor.version)
        reserved: set[str] = set()
        for alias in descriptor.aliases:
            owners = self._alias_owners.setdefault(alias, set())
            if identity in owners:
                continue
            if owners:
                # Different identity claims the same alias -> conflict.
                self._release_reserved_aliases(descriptor, reserved)
                raise AgentRegistryAliasConflictError(
                    "Alias already registered for a different identity",
                    {"alias": alias, "agent_id": descriptor.agent_id},
                )
            owners.add(identity)
            reserved.add(alias)
        return reserved

    def _release_aliases(self, descriptor: AgentDescriptor) -> None:
        for alias in descriptor.aliases:
            owners = self._alias_owners.get(alias)
            if owners is None:
                continue
            identity = self._key(descriptor.agent_id, descriptor.version)
            owners.discard(identity)
            if not owners:
                del self._alias_owners[alias]

    def _release_reserved_aliases(
        self, descriptor: AgentDescriptor, aliases: set[str]
    ) -> None:
        """Release aliases that were reserved in *this* call only."""
        identity = self._key(descriptor.agent_id, descriptor.version)
        for alias in aliases:
            owners = self._alias_owners.get(alias)
            if owners is None:
                continue
            owners.discard(identity)
            if not owners:
                del self._alias_owners[alias]

    # ── internal helpers ─────────────────────────────────────────────────

    def _lifecycle_transition(
        self, agent_id: str, version: AgentVersion, target: AgentLifecycle
    ) -> AgentDescriptor:
        with self._lock:
            current = self._store.get(agent_id, version)
            if current is None:
                raise AgentRegistryNotFoundError(
                    "Descriptor not found",
                    {"agent_id": agent_id, "version": version.canonical()},
                )
            if target == current.lifecycle:
                return current
            if current.lifecycle == AgentLifecycle.RETIRED:
                raise AgentRegistryDisabledError(
                    "Retired descriptor cannot be transitioned",
                    {"agent_id": agent_id, "version": version.canonical()},
                )
            new_descriptor = current.with_lifecycle(target)
            # Remove old, insert new (preserving alias ownership because
            # identity is unchanged).
            self._store.remove(agent_id, version)
            self._store.add(new_descriptor)
            return new_descriptor

    # ── public API ────────────────────────────────────────────────────────

    def register(self, descriptor: AgentDescriptor) -> AgentRegistrationStatus:
        with self._lock:
            self._validator.validate(descriptor)
            existing = self._store.get(descriptor.agent_id, descriptor.version)
            if existing is not None:
                # Same identity already present -> conflict.
                if existing == descriptor:
                    return AgentRegistrationStatus.REGISTERED
                raise AgentRegistryConflictError(
                    "Descriptor identity already registered",
                    {
                        "agent_id": descriptor.agent_id,
                        "version": descriptor.version.canonical(),
                    },
                )
            # Alias conflicts must be raised before persisting.
            reserved = self._reserve_aliases(descriptor)
            try:
                self._store.add(descriptor)
            except AgentRegistryConflictError:
                self._release_reserved_aliases(descriptor, reserved)
                raise
            except AgentRegistryError:
                self._release_reserved_aliases(descriptor, reserved)
                raise
            except Exception:  # noqa: BLE001 - defensive store boundary
                # Defensive boundary: unexpected store failures must
                # roll back alias ownership and surface a safe
                # ``AgentRegistryError`` without leaking the original
                # message.
                self._release_reserved_aliases(descriptor, reserved)
                raise AgentRegistryError(
                    "Failed to register descriptor",
                    {"agent_id": descriptor.agent_id},
                ) from None
            return AgentRegistrationStatus.REGISTERED

    def unregister(self, agent_id: str, version: AgentVersion) -> AgentDescriptor:
        with self._lock:
            descriptor = self._store.get(agent_id, version)
            if descriptor is None:
                raise AgentRegistryNotFoundError(
                    "Descriptor not found",
                    {"agent_id": agent_id, "version": version.canonical()},
                )
            removed = self._store.remove(agent_id, version)
            self._release_aliases(removed)
            return removed

    def get(
        self, agent_id: str, version: AgentVersion | None = None
    ) -> AgentDescriptor | None:
        with self._lock:
            if version is None:
                return self._latest_active(agent_id)
            return self._store.get(agent_id, version)

    def _latest_active(self, agent_id: str) -> AgentDescriptor | None:
        versions = [
            d
            for d in self._store.list()
            if d.agent_id == agent_id and d.lifecycle == AgentLifecycle.ACTIVE
        ]
        if not versions:
            return None
        versions.sort(key=lambda d: d.version.canonical())
        return versions[-1]

    def get_latest(self, agent_id: str) -> AgentDescriptor | None:
        with self._lock:
            versions = [d for d in self._store.list() if d.agent_id == agent_id]
            if not versions:
                return None

            # Sort by lifecycle priority ACTIVE first, then by version.
            def _sort_key(d: AgentDescriptor) -> tuple[int, str]:
                priority = 0 if d.lifecycle == AgentLifecycle.ACTIVE else 1
                return (priority, d.version.canonical())

            versions.sort(key=_sort_key)
            return versions[0]

    def get_required(
        self, agent_id: str, version: AgentVersion | None = None
    ) -> AgentDescriptor:
        descriptor = self.get(agent_id, version)
        if descriptor is None:
            version_str = version.canonical() if version else "latest"
            raise AgentRegistryNotFoundError(
                "Agent descriptor not found",
                {"agent_id": agent_id, "version": version_str},
            )
        return descriptor

    def list(
        self,
        *,
        lifecycle: AgentLifecycle | None = None,
        kind: AgentKind | None = None,
    ) -> tuple[AgentDescriptor, ...]:
        with self._lock:
            items = list(self._store.list())
            if lifecycle is not None:
                items = [d for d in items if d.lifecycle == lifecycle]
            if kind is not None:
                items = [d for d in items if d.kind == kind]
            return tuple(items)

    def find_by_alias(self, alias: str) -> tuple[AgentDescriptor, ...]:
        return self._store.find_by_alias(alias)

    def find_by_capability(self, capability: str) -> tuple[AgentDescriptor, ...]:
        return self._store.find_by_capability(capability)

    def find_by_kind(self, kind: AgentKind) -> tuple[AgentDescriptor, ...]:
        with self._lock:
            return self.list(kind=kind)

    def find_by_tag(self, tag: str) -> tuple[AgentDescriptor, ...]:
        with self._lock:
            items = [d for d in self._store.list() if tag in d.tags]
            items.sort(
                key=lambda d: (d.agent_id, d.version.canonical(), d.lifecycle.value)
            )
            return tuple(items)

    # ── lifecycle transitions ─────────────────────────────────────────────

    def enable(self, agent_id: str, version: AgentVersion) -> AgentDescriptor:
        return self._lifecycle_transition(agent_id, version, AgentLifecycle.ACTIVE)

    def disable(self, agent_id: str, version: AgentVersion) -> AgentDescriptor:
        # DISABLED is reachable through with_lifecycle.
        with self._lock:
            current = self._store.get(agent_id, version)
            if current is None:
                raise AgentRegistryNotFoundError(
                    "Descriptor not found",
                    {"agent_id": agent_id, "version": version.canonical()},
                )
            if current.lifecycle in (AgentLifecycle.RETIRED,):
                raise AgentRegistryDisabledError(
                    "Retired descriptor cannot be disabled again",
                    {"agent_id": agent_id, "version": version.canonical()},
                )
            new_descriptor = current.with_lifecycle(AgentLifecycle.DISABLED)
            self._store.remove(agent_id, version)
            self._store.add(new_descriptor)
            return new_descriptor

    def deprecate(self, agent_id: str, version: AgentVersion) -> AgentDescriptor:
        return self._lifecycle_transition(agent_id, version, AgentLifecycle.DEPRECATED)

    def retire(
        self,
        agent_id: str,
        version: AgentVersion | None = None,
    ) -> AgentDescriptor:
        """Retire a descriptor.

        When ``version`` is None all versions are retired. Retiring a
        descriptor means it is fully removed from the registry because
        RETIRED descriptors are rejected at construct time.
        """
        with self._lock:
            if version is None:
                removed: list[AgentDescriptor] = []
                for d in list(self._store.list()):
                    if d.agent_id == agent_id:
                        removed.append(self._store.remove(agent_id, d.version))
                        self._release_aliases(d)
                if not removed:
                    raise AgentRegistryNotFoundError(
                        "Agent not found",
                        {"agent_id": agent_id},
                    )
                # RETIRED state is implicit: descriptor simply absent.
                # We synthesize a marker only for caller reference.
                marker = removed[0]
                return marker
            current = self._store.get(agent_id, version)
            if current is None:
                raise AgentRegistryNotFoundError(
                    "Descriptor not found",
                    {"agent_id": agent_id, "version": version.canonical()},
                )
            removed_desc = self._store.remove(agent_id, version)
            self._release_aliases(removed_desc)
            return removed_desc

    def contains(self, agent_id: str, version: AgentVersion | None = None) -> bool:
        with self._lock:
            if version is not None:
                return self._store.get(agent_id, version) is not None
            return any(d.agent_id == agent_id for d in self._store.list())

    def snapshot(self) -> AgentRegistrySnapshot:
        with self._lock:
            return AgentRegistrySnapshot(
                captured_at=_now_utc(),
                descriptors=self._store.list(),
                snapshot_version=self._SNAPSHOT_VERSION,
            )

    def alias_owners(self) -> MappingProxyType[str, tuple[tuple[str, str], ...]]:
        with self._lock:
            out: dict[str, tuple[tuple[str, str], ...]] = {}
            for alias, owners in self._alias_owners.items():
                sorted_owners = tuple(sorted(owners))
                out[alias] = sorted_owners
            return MappingProxyType(out)

    def register_many(
        self, descriptors: Iterable[AgentDescriptor]
    ) -> tuple[AgentRegistrationStatus, ...]:
        results: list[AgentRegistrationStatus] = []
        for d in descriptors:
            results.append(self.register(d))
        return tuple(results)


__all__ = ["AgentRegistry", "AgentRegistrySnapshot"]
