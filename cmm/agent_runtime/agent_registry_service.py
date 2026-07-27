"""Phase 9.23 – Agent Registry Service.

The :class:`AgentRegistryService` is the single entry point used by
the Agent Runtime, the CLI, the future HTTP layer and the future n8n
adapter. It coordinates:

* :class:`AgentRegistry`          – descriptor storage and lifecycle
* :class:`AgentFactoryRegistry`    – factory storage and instance
  creation (with scope-based caches)
* :class:`AgentResolver`           – requirement → descriptor
  resolution (with compatibility + scoring)
* :class:`AgentCompatibilityChecker` – structured compatibility
  verdicts

The service:

* never mutates internal state of its collaborators;
* uses dependency injection for every component (no globals);
* exposes ``health()`` and ``stats()`` driven by real data;
* exposes ``snapshot()`` returning immutable, JSON-safe snapshots;
* isolates internal errors and converts them to safe, structured
  exceptions.

This module also defines :class:`AgentRegistryHealth` and
:class:`AgentRegistryStats` value objects returned by ``health()``
and ``stats()``.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.agent_factory import AgentFactoryRegistry
from cmm.agent_runtime.agent_factory_contracts import AgentFactory
from cmm.agent_runtime.agent_registry import AgentRegistry
from cmm.agent_runtime.agent_registry_contracts import (
    AgentDescriptor,
    AgentFactoryContext,
    AgentInstance,
    AgentProvisioningResult,
    AgentRequirement,
    AgentResolution,
    AgentVersion,
)
from cmm.agent_runtime.agent_registry_enums import (
    AgentFactoryScope,
    AgentKind,
    AgentLifecycle,
    AgentRegistrationStatus,
    AgentResolutionStrategy,
)
from cmm.agent_runtime.agent_registry_errors import (
    AgentFactoryCreationError,
    AgentFactoryNotFoundError,
    AgentRegistryNotFoundError,
    AgentResolutionError,
)
from cmm.agent_runtime.agent_registry_store import (
    InMemoryAgentRegistryStore,
)
from cmm.agent_runtime.agent_registry_validation import (
    AgentRequirementValidator,
)
from cmm.agent_runtime.agent_resolver import (
    AgentCompatibilityChecker,
    AgentResolver,
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ── Health / Stats value objects ────────────────────────────────────────────


@dataclass(frozen=True)
class AgentRegistryHealth:
    """Immutable health snapshot of the service."""

    registry_available: bool
    factory_registry_available: bool
    resolver_available: bool
    registered_agents: int
    active_agents: int
    disabled_agents: int
    registered_factories: int
    resolvable_agents: int
    unavailable_factories: tuple[str, ...]
    captured_at: datetime = field(default_factory=_now_utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_available": self.registry_available,
            "factory_registry_available": self.factory_registry_available,
            "resolver_available": self.resolver_available,
            "registered_agents": self.registered_agents,
            "active_agents": self.active_agents,
            "disabled_agents": self.disabled_agents,
            "registered_factories": self.registered_factories,
            "resolvable_agents": self.resolvable_agents,
            "unavailable_factories": list(self.unavailable_factories),
            "captured_at": self.captured_at.isoformat(),
        }


@dataclass(frozen=True)
class AgentRegistryStats:
    """Immutable statistics snapshot of the service."""

    agents_by_kind: MappingProxyType[str, int]
    agents_by_lifecycle: MappingProxyType[str, int]
    agents_by_version: MappingProxyType[str, int]
    capability_count: int
    factory_count: int
    instances_by_scope: MappingProxyType[str, int]
    resolution_attempts: int
    resolution_successes: int
    resolution_failures: int
    creation_attempts: int
    creation_successes: int
    creation_failures: int
    captured_at: datetime = field(default_factory=_now_utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agents_by_kind": dict(self.agents_by_kind),
            "agents_by_lifecycle": dict(self.agents_by_lifecycle),
            "agents_by_version": dict(self.agents_by_version),
            "capability_count": self.capability_count,
            "factory_count": self.factory_count,
            "instances_by_scope": dict(self.instances_by_scope),
            "resolution_attempts": self.resolution_attempts,
            "resolution_successes": self.resolution_successes,
            "resolution_failures": self.resolution_failures,
            "creation_attempts": self.creation_attempts,
            "creation_successes": self.creation_successes,
            "creation_failures": self.creation_failures,
            "captured_at": self.captured_at.isoformat(),
        }


# ── Service ─────────────────────────────────────────────────────────────────


class AgentRegistryService:
    """Façade for the Agent Registry & Factory subsystem."""

    def __init__(
        self,
        *,
        registry: AgentRegistry | None = None,
        factory_registry: AgentFactoryRegistry | None = None,
        resolver: AgentResolver | None = None,
        compatibility_checker: AgentCompatibilityChecker | None = None,
    ) -> None:
        self._registry = registry or AgentRegistry(store=InMemoryAgentRegistryStore())
        self._factory_registry = factory_registry or AgentFactoryRegistry()
        # The compatibility checker needs the factory registry to
        # surface ``FACTORY_UNAVAILABLE`` verdicts.
        checker = compatibility_checker or AgentCompatibilityChecker(
            factory_registry=self._factory_registry
        )
        self._compatibility_checker = checker
        self._resolver = resolver or AgentResolver(
            registry=self._registry,
            compatibility_checker=checker,
        )
        self._lock = threading.RLock()
        # service-level resolution counters
        self._resolution_attempts: int = 0
        self._resolution_successes: int = 0
        self._resolution_failures: int = 0

    # ── Components accessors ───────────────────────────────────────────────

    @property
    def registry(self) -> AgentRegistry:
        return self._registry

    @property
    def factory_registry(self) -> AgentFactoryRegistry:
        return self._factory_registry

    @property
    def resolver(self) -> AgentResolver:
        return self._resolver

    @property
    def compatibility_checker(self) -> AgentCompatibilityChecker:
        return self._compatibility_checker

    # ── Registration helpers ──────────────────────────────────────────────

    def register_agent(self, descriptor: AgentDescriptor) -> AgentRegistrationStatus:
        return self._registry.register(descriptor)

    def unregister_agent(self, agent_id: str, version: AgentVersion) -> AgentDescriptor:
        return self._registry.unregister(agent_id, version)

    def register_factory(self, factory: AgentFactory):
        return self._factory_registry.register(factory)

    def unregister_factory(self, factory_id: str):
        return self._factory_registry.unregister(factory_id)

    # ── Listing helpers ───────────────────────────────────────────────────

    def list_agents(
        self,
        *,
        lifecycle: AgentLifecycle | None = None,
        kind: AgentKind | None = None,
    ) -> tuple[AgentDescriptor, ...]:
        return self._registry.list(lifecycle=lifecycle, kind=kind)

    def get_agent(
        self,
        agent_id: str,
        version: AgentVersion | None = None,
    ) -> AgentDescriptor | None:
        return self._registry.get(agent_id, version=version)

    # ── Resolution ────────────────────────────────────────────────────────

    def resolve_agent(
        self,
        requirement: AgentRequirement,
        *,
        strategy: AgentResolutionStrategy | None = None,
        request_id: str | None = None,
    ) -> AgentResolution:
        AgentRequirementValidator.validate(requirement)
        with self._lock:
            self._resolution_attempts += 1
        try:
            resolution = self._resolver.resolve(
                requirement, strategy=strategy, request_id=request_id
            )
        except (AgentResolutionError, AgentRegistryNotFoundError) as exc:
            with self._lock:
                self._resolution_failures += 1
            raise AgentResolutionError(
                f"Resolution failed: {exc.error_code}",
                exc.details,
            ) from None
        with self._lock:
            if resolution.selected is not None:
                self._resolution_successes += 1
            else:
                self._resolution_failures += 1
        return resolution

    def create_agent(
        self,
        descriptor: AgentDescriptor,
        factory_context: AgentFactoryContext,
    ) -> AgentInstance:
        return self._factory_registry.create(descriptor, factory_context)

    def resolve_and_create(
        self,
        requirement: AgentRequirement,
        *,
        factory_context: AgentFactoryContext,
        strategy: AgentResolutionStrategy | None = None,
    ) -> AgentProvisioningResult:
        AgentRequirementValidator.validate(requirement)
        resolution = self.resolve_agent(
            requirement, strategy=strategy, request_id=factory_context.request_id
        )
        if resolution.selected is None:
            return AgentProvisioningResult(
                resolution=resolution,
                instance=None,
                request_id=factory_context.request_id,
            )
        try:
            instance = self._factory_registry.create(
                resolution.selected, factory_context
            )
        except AgentFactoryCreationError as exc:
            raise AgentFactoryCreationError(
                f"Factory creation failed: {exc.error_code}",
                exc.details,
            ) from None
        return AgentProvisioningResult(
            resolution=resolution,
            instance=instance,
            request_id=factory_context.request_id,
        )

    # ── Health & Stats ────────────────────────────────────────────────────

    def health(self) -> AgentRegistryHealth:
        with self._lock:
            descriptors = self._registry.list()
            factory_count = len(self._factory_registry.list())
            active = [d for d in descriptors if d.lifecycle == AgentLifecycle.ACTIVE]
            disabled = [
                d for d in descriptors if d.lifecycle == AgentLifecycle.DISABLED
            ]
            unavailable: list[str] = []
            resolvable = 0
            for d in descriptors:
                if d.lifecycle == AgentLifecycle.ACTIVE:
                    if self._factory_registry.contains(d.factory_id):
                        try:
                            factory = self._factory_registry.get(d.factory_id)
                            if bool(factory.supports(d)):
                                resolvable += 1
                            else:
                                unavailable.append(d.factory_id)
                        except AgentFactoryNotFoundError:
                            unavailable.append(d.factory_id)
                    else:
                        unavailable.append(d.factory_id)
            return AgentRegistryHealth(
                registry_available=True,
                factory_registry_available=True,
                resolver_available=True,
                registered_agents=len(descriptors),
                active_agents=len(active),
                disabled_agents=len(disabled),
                registered_factories=factory_count,
                resolvable_agents=resolvable,
                unavailable_factories=tuple(sorted(set(unavailable))),
            )

    def stats(self) -> AgentRegistryStats:
        with self._lock:
            descriptors = self._registry.list()
            agents_by_kind: dict[str, int] = {}
            agents_by_lifecycle: dict[str, int] = {}
            agents_by_version: dict[str, int] = {}
            capability_count = 0
            for d in descriptors:
                agents_by_kind[d.kind.value] = agents_by_kind.get(d.kind.value, 0) + 1
                agents_by_lifecycle[d.lifecycle.value] = (
                    agents_by_lifecycle.get(d.lifecycle.value, 0) + 1
                )
                agents_by_version[d.version.canonical()] = (
                    agents_by_version.get(d.version.canonical(), 0) + 1
                )
                capability_count += len(d.capabilities)
            factory_stats = self._factory_registry.stats()
            resolver_stats = self._resolver.stats()
            instances_by_scope: dict[str, int] = {
                AgentFactoryScope.TRANSIENT.value: 0,
                AgentFactoryScope.REQUEST.value: factory_stats["request_instances"],
                AgentFactoryScope.RUN.value: factory_stats["run_instances"],
                AgentFactoryScope.SINGLETON.value: factory_stats["singleton_instances"],
            }
            return AgentRegistryStats(
                agents_by_kind=MappingProxyType(dict(agents_by_kind)),
                agents_by_lifecycle=MappingProxyType(dict(agents_by_lifecycle)),
                agents_by_version=MappingProxyType(dict(agents_by_version)),
                capability_count=capability_count,
                factory_count=factory_stats["factory_count"],
                instances_by_scope=MappingProxyType(instances_by_scope),
                resolution_attempts=resolver_stats["resolution_attempts"]
                + self._resolution_attempts,
                resolution_successes=resolver_stats["resolution_successes"]
                + self._resolution_successes,
                resolution_failures=resolver_stats["resolution_failures"]
                + self._resolution_failures,
                creation_attempts=factory_stats["creation_attempts"],
                creation_successes=factory_stats["creation_successes"],
                creation_failures=factory_stats["creation_failures"],
            )

    # ── Snapshot ───────────────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        return {
            "registry": self._registry.snapshot().to_dict(),
            "factories": self._factory_registry.snapshot().to_dict(),
            "stats": self.stats().to_dict(),
            "health": self.health().to_dict(),
            "snapshot_version": "9.23.0",
            "captured_at": _now_utc().isoformat(),
        }

    # ── Misc helpers ──────────────────────────────────────────────────────

    def resolve_latest_active(self, agent_id: str) -> AgentDescriptor | None:
        return self._registry.get_latest(agent_id)


__all__ = [
    "AgentRegistryHealth",
    "AgentRegistryService",
    "AgentRegistryStats",
]
