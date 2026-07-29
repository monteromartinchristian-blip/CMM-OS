"""Phase 9.23 – Agent Factory Registry.

The factory registry owns ``AgentFactory`` instances and is the only
component allowed to invoke them. It enforces:

* unique ``factory_id`` (no silent overwrite);
* scope-correct caching (TRANSIENT/REQUEST/RUN/SINGLETON);
* thread-safe registration and creation;
* structured error mapping (no propagation of internal ``str(exc)``);
* defensive validation of the instance produced by a factory
  (descriptor match, scope match, non-null ``runtime_object``).

The registry never mutates a registered factory.

Caches:

* ``TRANSIENT`` – no cache, every call produces a fresh instance.
* ``REQUEST``  – one instance per ``(factory_id, request_id)`` pair.
* ``RUN``      – one instance per ``(factory_id, run_id)`` pair;
  ``run_id`` is mandatory.
* ``SINGLETON`` – one instance per ``factory_id``; only allowed if
  the factory declared ``thread_safe=True``.

All caches are bounded to the registry instance and can be cleared
with :py:meth:`clear_caches`.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.agent_factory_contracts import (
    AgentFactory,
    AgentFactoryRegistration,
    AgentFactoryRegistrySnapshot,
    assert_descriptor_match,
)
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
    AgentFactoryNotFoundError,
    AgentRegistryValidationError,
)
from cmm.agent_runtime.agent_registry_validation import AgentFactoryValidator


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _new_instance_id() -> str:
    return str(uuid.uuid4())


class AgentFactoryRegistry:
    """Registry and execution coordinator for ``AgentFactory`` instances."""

    _SNAPSHOT_VERSION = "9.23.0"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._factories: dict[str, AgentFactory] = {}
        # Caches: (cache_key) -> AgentInstance
        self._singleton_cache: dict[str, AgentInstance] = {}
        self._request_cache: dict[tuple[str, str], AgentInstance] = {}
        self._run_cache: dict[tuple[str, str], AgentInstance] = {}
        # Stats (best-effort, real values).
        self._creation_attempts: int = 0
        self._creation_successes: int = 0
        self._creation_failures: int = 0

    # ── Registration ───────────────────────────────────────────────────────

    def register(self, factory: AgentFactory) -> AgentFactoryRegistration:
        AgentFactoryValidator.validate_factory(factory)
        with self._lock:
            factory_id = factory.factory_id
            if factory_id in self._factories:
                raise AgentFactoryError(
                    "Factory already registered",
                    {"factory_id": factory_id},
                )
            self._factories[factory_id] = factory
            return AgentFactoryRegistration(
                factory_id=factory_id,
                scope=factory.scope,
                thread_safe=bool(getattr(factory, "thread_safe", False)),
            )

    def unregister(self, factory_id: str) -> AgentFactoryRegistration:
        with self._lock:
            if factory_id not in self._factories:
                raise AgentFactoryNotFoundError(
                    "Factory not registered",
                    {"factory_id": factory_id},
                )
            factory = self._factories.pop(factory_id)
            # Invalidate caches belonging to this factory.
            self._singleton_cache.pop(factory_id, None)
            self._request_cache = {
                k: v for k, v in self._request_cache.items() if k[0] != factory_id
            }
            self._run_cache = {
                k: v for k, v in self._run_cache.items() if k[0] != factory_id
            }
            return AgentFactoryRegistration(
                factory_id=factory_id,
                scope=factory.scope,
                thread_safe=bool(getattr(factory, "thread_safe", False)),
            )

    def get(self, factory_id: str) -> AgentFactory:
        with self._lock:
            factory = self._factories.get(factory_id)
            if factory is None:
                raise AgentFactoryNotFoundError(
                    "Factory not registered",
                    {"factory_id": factory_id},
                )
            return factory

    def contains(self, factory_id: str) -> bool:
        with self._lock:
            return factory_id in self._factories

    def list(self) -> tuple[AgentFactory, ...]:
        with self._lock:
            return tuple(self._factories.values())

    def registrations(self) -> tuple[AgentFactoryRegistration, ...]:
        with self._lock:
            return tuple(
                AgentFactoryRegistration(
                    factory_id=f.factory_id,
                    scope=f.scope,
                    thread_safe=bool(getattr(f, "thread_safe", False)),
                )
                for f in self._factories.values()
            )

    # ── Creation ───────────────────────────────────────────────────────────

    def create(
        self,
        descriptor: AgentDescriptor,
        context: AgentFactoryContext,
    ) -> AgentInstance:
        """Create an instance for ``descriptor`` using its registered factory.

        The result is cached according to the factory scope. The
        function:

        * validates that the factory exists;
        * validates that the factory supports the descriptor;
        * invokes the factory inside a safe boundary (any internal
          exception is converted to ``AgentFactoryCreationError``);
        * verifies that the instance returned by the factory is valid
          (correct descriptor, scope, non-null ``runtime_object``).
        """
        if not isinstance(descriptor, AgentDescriptor):
            raise AgentRegistryValidationError(
                "create() requires an AgentDescriptor",
                {"type": type(descriptor).__name__},
            )
        if not isinstance(context, AgentFactoryContext):
            raise AgentRegistryValidationError(
                "create() requires an AgentFactoryContext",
                {"type": type(context).__name__},
            )
        with self._lock:
            self._creation_attempts += 1
            factory_id = descriptor.factory_id
            factory = self._factories.get(factory_id)
            if factory is None:
                self._creation_failures += 1
                raise AgentFactoryNotFoundError(
                    "Factory not registered for descriptor",
                    {"factory_id": factory_id},
                )
            # Re-validate the factory structurally (cheap) and confirm
            # it supports the descriptor.
            try:
                AgentFactoryValidator.validate_factory(factory)
                AgentFactoryValidator.validate_descriptor_compatibility(
                    factory, descriptor
                )
            except AgentFactoryCompatibilityError:
                self._creation_failures += 1
                raise
            except AgentFactoryError:
                self._creation_failures += 1
                raise

            # Cache lookup.
            cached = self._lookup_cache(factory, context)
            if cached is not None:
                self._creation_successes += 1
                return cached

            # Invoke the factory inside a safe boundary.
            try:
                instance = factory.create(descriptor, context)
            except AgentFactoryCreationError:
                self._creation_failures += 1
                raise
            except Exception as exc:  # noqa: BLE001 - mapped to safe error
                self._creation_failures += 1
                # Never propagate ``str(exc)``; only the fact that the
                # factory raised.
                _ = exc  # explicit no-op to silence linters
                raise AgentFactoryCreationError(
                    "Factory raised an exception during create()",
                    {"factory_id": factory_id},
                ) from None

            if not isinstance(instance, AgentInstance):
                self._creation_failures += 1
                raise AgentFactoryCreationError(
                    "Factory did not return an AgentInstance",
                    {"factory_id": factory_id},
                )
            if instance.runtime_object is None:
                self._creation_failures += 1
                raise AgentFactoryCreationError(
                    "Factory returned an instance with no runtime_object",
                    {"factory_id": factory_id},
                )
            if not instance.instance_id or not instance.instance_id.strip():
                self._creation_failures += 1
                raise AgentFactoryCreationError(
                    "Factory returned an instance with empty instance_id",
                    {"factory_id": factory_id},
                )
            try:
                assert_descriptor_match(instance, descriptor)
            except AgentFactoryCreationError:
                self._creation_failures += 1
                raise
            if instance.scope != factory.scope:
                self._creation_failures += 1
                raise AgentFactoryCreationError(
                    "Factory returned an instance with wrong scope",
                    {
                        "factory_id": factory_id,
                        "factory_scope": factory.scope.value,
                        "instance_scope": instance.scope.value,
                    },
                )

            self._store_cache(factory, context, instance)
            self._creation_successes += 1
            return instance

    # ── Cache management ──────────────────────────────────────────────────

    def _lookup_cache(
        self, factory: AgentFactory, context: AgentFactoryContext
    ) -> AgentInstance | None:
        if factory.scope == AgentFactoryScope.TRANSIENT:
            return None
        if factory.scope == AgentFactoryScope.SINGLETON:
            return self._singleton_cache.get(factory.factory_id)
        if factory.scope == AgentFactoryScope.REQUEST:
            key = (factory.factory_id, context.request_id)
            return self._request_cache.get(key)
        if factory.scope == AgentFactoryScope.RUN:
            if not context.run_id:
                raise AgentFactoryCreationError(
                    "RUN-scoped factory requires a non-empty run_id",
                    {"factory_id": factory.factory_id},
                )
            key = (factory.factory_id, context.run_id)
            return self._run_cache.get(key)
        return None

    def _store_cache(
        self,
        factory: AgentFactory,
        context: AgentFactoryContext,
        instance: AgentInstance,
    ) -> None:
        if factory.scope == AgentFactoryScope.TRANSIENT:
            return
        if factory.scope == AgentFactoryScope.SINGLETON:
            self._singleton_cache[factory.factory_id] = instance
            return
        if factory.scope == AgentFactoryScope.REQUEST:
            self._request_cache[(factory.factory_id, context.request_id)] = instance
            return
        if factory.scope == AgentFactoryScope.RUN:
            if not context.run_id:
                raise AgentFactoryCreationError(
                    "RUN-scoped factory requires a non-empty run_id",
                    {"factory_id": factory.factory_id},
                )
            self._run_cache[(factory.factory_id, context.run_id)] = instance
            return

    def clear_caches(self) -> None:
        with self._lock:
            self._singleton_cache.clear()
            self._request_cache.clear()
            self._run_cache.clear()

    # ── Stats ──────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "factory_count": len(self._factories),
                "singleton_instances": len(self._singleton_cache),
                "request_instances": len(self._request_cache),
                "run_instances": len(self._run_cache),
                "creation_attempts": self._creation_attempts,
                "creation_successes": self._creation_successes,
                "creation_failures": self._creation_failures,
            }

    # ── Snapshot ───────────────────────────────────────────────────────────

    def snapshot(self) -> AgentFactoryRegistrySnapshot:
        with self._lock:
            return AgentFactoryRegistrySnapshot(
                captured_at=_now_utc(),
                factories=self.registrations(),
                snapshot_version=self._SNAPSHOT_VERSION,
            )

    # ── Internal helpers ───────────────────────────────────────────────────

    def _cached_request_keys(self) -> tuple[tuple[str, str], ...]:
        with self._lock:
            return tuple(self._request_cache.keys())

    def _cached_run_keys(self) -> tuple[tuple[str, str], ...]:
        with self._lock:
            return tuple(self._run_cache.keys())

    def _singleton_keys(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._singleton_cache.keys())

    def __contains__(self, factory_id: object) -> bool:
        if not isinstance(factory_id, str):
            return False
        return self.contains(factory_id)


__all__ = [
    "AgentFactoryRegistry",
]


# Silence pyflakes about unused imports.
_ = (MappingProxyType, Iterable)
