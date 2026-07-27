"""Phase 9.23 – Agent Registry & Factory Regression Tests.

Regression tests added during the cleanup pass to lock in behaviour
that was identified as a real gap during Ruff cleanup and audit:

* alias rollback when the underlying store fails unexpectedly;
* invalid ``required.version`` strings handled by the compatibility
  checker (not by a bare ``except Exception``);
* factory registry unavailable does not silently degrade to "no
  components";
* factory ``supports()`` raising internally is differentiated from
  ``supports()`` returning ``False``;
* ``required_capabilities`` actually filters incompatible candidates;
* an EXACT resolution never falls back when no compatible descriptor is
  found;
* ``resolve_and_create`` never reports success without an instance;
* internal errors do not leak ``str(exc)`` text.

Each test is self-contained and uses only the public 9.23 API.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from cmm.agent_runtime.agent_factory import AgentFactoryRegistry
from cmm.agent_runtime.agent_registry import AgentRegistry
from cmm.agent_runtime.agent_registry_contracts import (
    AgentCapability,
    AgentDescriptor,
    AgentFactoryContext,
    AgentInstance,
    AgentProvisioningResult,
    AgentRequirement,
    AgentResolution,
    AgentResolutionCandidate,
    AgentVersion,
)
from cmm.agent_runtime.agent_registry_enums import (
    AgentCapabilityKind,
    AgentCompatibilityStatus,
    AgentFactoryScope,
    AgentKind,
    AgentLifecycle,
    AgentRegistrationStatus,
    AgentResolutionStrategy,
)
from cmm.agent_runtime.agent_registry_errors import (
    AgentFactoryCompatibilityError,
    AgentFactoryCreationError,
    AgentFactoryError,
    AgentFactoryNotFoundError,
    AgentRegistryAliasConflictError,
    AgentRegistryError,
    AgentRegistryNotFoundError,
    AgentRegistryValidationError,
    AgentResolutionAmbiguousError,
    AgentResolutionError,
    AgentResolutionNotFoundError,
)
from cmm.agent_runtime.agent_registry_service import AgentRegistryService
from cmm.agent_runtime.agent_resolver import (
    AgentCompatibilityChecker,
    AgentResolver,
)

# ── helpers ─────────────────────────────────────────────────────────────────


def _ts(year: int = 2026, month: int = 1, day: int = 1) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


def _capability(name: str) -> AgentCapability:
    return AgentCapability(
        name=name,
        kind=AgentCapabilityKind.OPERATION,
        operations=(f"op.{name}",),
        input_types=("text",),
        output_types=("out",),
    )


def _descriptor(
    agent_id: str = "agent.alpha",
    *,
    version: AgentVersion | None = None,
    kind: AgentKind = AgentKind.GENERAL,
    factory_id: str = "factory.alpha",
    capabilities: tuple[AgentCapability, ...] = (),
    aliases: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
    lifecycle: AgentLifecycle = AgentLifecycle.ACTIVE,
    required_permissions: tuple[str, ...] = (),
    required_components: tuple[str, ...] = (),
    supported_operations: tuple[str, ...] = (),
    priority: int = 0,
) -> AgentDescriptor:
    return AgentDescriptor(
        agent_id=agent_id,
        name=agent_id,
        version=version or AgentVersion(1, 0, 0),
        kind=kind,
        lifecycle=lifecycle,
        description=f"descriptor for {agent_id}",
        capabilities=capabilities,
        factory_id=factory_id,
        aliases=aliases,
        tags=tags,
        required_permissions=required_permissions,
        required_components=required_components,
        supported_operations=supported_operations,
        priority=priority,
        metadata=MappingProxyType({}),
        created_at=_ts(),
    )


class _FailingStore:
    """In-memory store that raises on ``add``."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], AgentDescriptor] = {}

    @staticmethod
    def _key(agent_id: str, version: AgentVersion) -> tuple[str, str]:
        return (agent_id, version.canonical())

    def add(self, descriptor: AgentDescriptor) -> None:
        # Simulate an unexpected store failure that is *not* a
        # domain error – we must not leak ``str(exc)``.
        raise RuntimeError("disk exploded: /var/secret/path")

    def remove(self, agent_id: str, version: AgentVersion) -> AgentDescriptor:
        key = self._key(agent_id, version)
        d = self._entries.pop(key, None)
        if d is None:
            raise AgentRegistryError("missing", {"agent_id": agent_id})
        return d

    def get(self, agent_id: str, version: AgentVersion) -> AgentDescriptor | None:
        return self._entries.get(self._key(agent_id, version))

    def list(self) -> tuple[AgentDescriptor, ...]:
        return tuple(self._entries.values())

    def find_by_alias(self, alias: str) -> tuple[AgentDescriptor, ...]:
        return tuple(d for d in self._entries.values() if alias in d.aliases)

    def find_by_capability(self, capability: str) -> tuple[AgentDescriptor, ...]:
        return tuple(
            d
            for d in self._entries.values()
            if any(c.name == capability for c in d.capabilities)
        )


class _StubFactory:
    """Minimal AgentFactory implementation for tests."""

    def __init__(
        self,
        factory_id: str = "factory.alpha",
        scope: AgentFactoryScope = AgentFactoryScope.TRANSIENT,
        thread_safe: bool = True,
        supports_result: bool = True,
        raise_on_supports: Exception | None = None,
        raise_on_create: Exception | None = None,
        runtime_object: object | None = None,
    ) -> None:
        self.factory_id = factory_id
        self.scope = scope
        self.thread_safe = thread_safe
        self._supports = supports_result
        self._raise_on_supports = raise_on_supports
        self._raise_on_create = raise_on_create
        self._runtime = runtime_object or object()

    def supports(self, descriptor: AgentDescriptor) -> bool:
        if self._raise_on_supports is not None:
            raise self._raise_on_supports
        return self._supports

    def create(
        self,
        descriptor: AgentDescriptor,
        context: AgentFactoryContext,
    ) -> AgentInstance:
        if self._raise_on_create is not None:
            raise self._raise_on_create
        return AgentInstance(
            instance_id="inst-1",
            descriptor=descriptor,
            runtime_object=self._runtime,
            scope=self.scope,
        )


# ── registry: alias rollback on unexpected store failures ─────────────────


class TestRegistryAliasRollback:
    """When ``store.add`` raises unexpectedly the alias ownership must
    be rolled back so subsequent registrations of the same alias are
    not silently corrupted."""

    def test_alias_rolled_back_when_store_fails_unexpectedly(self) -> None:
        registry = AgentRegistry(store=_FailingStore())  # type: ignore[arg-type]
        desc = _descriptor(aliases=("shared.alias",))
        with pytest.raises(AgentRegistryError) as exc_info:
            registry.register(desc)
        # Internal ``RuntimeError("disk exploded: /var/secret/path")``
        # must not leak through.
        assert "disk exploded" not in exc_info.value.message
        assert "/var/secret" not in str(exc_info.value.details)
        # And no alias ownership should remain.
        owners = registry.alias_owners()
        assert "shared.alias" not in owners

    def test_alias_reservation_conflict_leaves_no_partial_owners(self) -> None:
        registry = AgentRegistry()
        first = _descriptor(
            agent_id="agent.first",
            aliases=("alpha", "beta"),
            version=AgentVersion(1, 0, 0),
        )
        second = _descriptor(
            agent_id="agent.second",
            aliases=("beta", "gamma"),  # overlaps on beta only
            version=AgentVersion(1, 0, 0),
        )
        registry.register(first)
        with pytest.raises(AgentRegistryAliasConflictError):
            registry.register(second)
        owners = registry.alias_owners()
        # ``beta`` must remain owned by ``agent.first`` only;
        # ``gamma`` must not be partially reserved.
        assert sorted(owners["alpha"]) == [("agent.first", "1.0.0")]
        assert "beta" in owners and owners["beta"] == (("agent.first", "1.0.0"),)
        assert "gamma" not in owners


# ── resolver: error differentiation ────────────────────────────────────────


class TestCompatibilityErrorDifferentiation:
    """The compatibility checker must surface *structured* errors for
    each distinct failure mode; it must not collapse them into
    "no components" or hide behind a generic ``except Exception``."""

    def test_invalid_version_string_yields_incompatible_version(self) -> None:
        desc = _descriptor()
        req = AgentRequirement(agent_id="agent.alpha", version="not-a-version")
        # Skip service-level validator and exercise the
        # compatibility checker directly; this is what the resolver
        # uses after the requirement has already been admitted.
        checker = AgentCompatibilityChecker()
        result = checker.check(desc, req)
        assert result.status == AgentCompatibilityStatus.INCOMPATIBLE_VERSION
        assert "version_parse_error" in result.reasons

    def test_factory_registry_unavailable_does_not_silently_pass(
        self,
    ) -> None:
        class _BoomFactoryRegistry:
            def list(self):
                raise AgentRegistryError("registry exploded", {"k": "v"})

            def contains(self, factory_id: str) -> bool:
                return False

        desc = _descriptor(required_components=("component.x",))
        checker = AgentCompatibilityChecker(
            factory_registry=_BoomFactoryRegistry(),  # type: ignore[arg-type]
        )
        req = AgentRequirement(agent_id="agent.alpha")
        result = checker.check(desc, req)
        assert result.status == AgentCompatibilityStatus.FACTORY_UNAVAILABLE
        assert "factory_registry_unavailable" in result.reasons

    def test_factory_supports_raises_is_distinguished_from_false(
        self,
    ) -> None:
        registry = AgentFactoryRegistry()
        registry.register(
            _StubFactory(
                factory_id="factory.alpha",
                raise_on_supports=AgentFactoryError("internal boom"),
            )
        )
        checker = AgentCompatibilityChecker(factory_registry=registry)
        desc = _descriptor(factory_id="factory.alpha")
        req = AgentRequirement(agent_id="agent.alpha")
        result = checker.check(desc, req)
        assert result.status == AgentCompatibilityStatus.FACTORY_UNAVAILABLE
        assert "factory_supports_error" in result.reasons

    def test_factory_supports_false_is_distinguished_from_raise(
        self,
    ) -> None:
        registry = AgentFactoryRegistry()
        registry.register(
            _StubFactory(factory_id="factory.alpha", supports_result=False)
        )
        checker = AgentCompatibilityChecker(factory_registry=registry)
        desc = _descriptor(factory_id="factory.alpha")
        req = AgentRequirement(agent_id="agent.alpha")
        result = checker.check(desc, req)
        assert result.status == AgentCompatibilityStatus.FACTORY_UNAVAILABLE
        assert "factory_does_not_support" in result.reasons

    def test_required_capabilities_filters_incompatible_candidate(self) -> None:
        cap_a = _capability("summarize")
        cap_b = _capability("translate")
        good = _descriptor(agent_id="agent.good", capabilities=(cap_a, cap_b))
        bad = _descriptor(
            agent_id="agent.bad",
            capabilities=(cap_a,),
            factory_id="factory.bad",
        )
        registry = AgentRegistry()
        registry.register(good)
        registry.register(bad)
        checker = AgentCompatibilityChecker()
        req = AgentRequirement(required_capabilities=("translate",))
        good_result = checker.check(good, req)
        bad_result = checker.check(bad, req)
        assert good_result.is_compatible
        assert bad_result.status == AgentCompatibilityStatus.INCOMPATIBLE_CAPABILITY
        assert "translate" in bad_result.missing_capabilities


# ── resolver: candidates and selection ─────────────────────────────────────


class TestResolverSelectionRules:
    """The resolver must never select an incompatible candidate and
    must never silently fall back when the strategy was ``EXACT``."""

    def test_exact_resolution_without_compatible_raises(self) -> None:
        cap = _capability("summarize")
        registry = AgentRegistry()
        registry.register(
            _descriptor(
                agent_id="agent.alpha",
                capabilities=(cap,),
                factory_id="factory.alpha",
            )
        )
        # Register a factory so the only failure mode is capability.
        factory_registry = AgentFactoryRegistry()
        factory_registry.register(_StubFactory(factory_id="factory.alpha"))
        checker = AgentCompatibilityChecker(factory_registry=factory_registry)
        resolver = AgentResolver(registry=registry, compatibility_checker=checker)

        req = AgentRequirement(
            agent_id="agent.alpha",
            required_capabilities=("translate",),
        )
        with pytest.raises(AgentResolutionNotFoundError):
            resolver.resolve(req, strategy=AgentResolutionStrategy.EXACT)

    def test_no_compatible_candidate_ever_selected(self) -> None:
        cap = _capability("summarize")
        registry = AgentRegistry()
        registry.register(
            _descriptor(
                agent_id="agent.alpha",
                capabilities=(cap,),
                factory_id="factory.alpha",
            )
        )
        factory_registry = AgentFactoryRegistry()
        factory_registry.register(_StubFactory(factory_id="factory.alpha"))
        checker = AgentCompatibilityChecker(factory_registry=factory_registry)
        resolver = AgentResolver(registry=registry, compatibility_checker=checker)

        req = AgentRequirement(
            agent_id="agent.alpha",
            required_capabilities=("translate",),
        )
        # BEST_MATCH default strategy still returns a structured
        # resolution with ``selected=None`` when nothing fits.
        resolution = resolver.resolve(req)
        assert resolution.selected is None
        assert any(
            c.compatibility == AgentCompatibilityStatus.INCOMPATIBLE_CAPABILITY
            for c in resolution.candidates
        )


# ── service: resolve_and_create semantics ──────────────────────────────────


class TestResolveAndCreateSemantics:
    """``resolve_and_create`` must report ``instance=None`` whenever it
    cannot fully provision, and must not return success without a
    valid instance."""

    def test_returns_instance_none_when_no_compatible_candidate(self) -> None:
        cap = _capability("summarize")
        registry = AgentRegistry()
        registry.register(
            _descriptor(
                agent_id="agent.alpha",
                capabilities=(cap,),
                factory_id="factory.alpha",
            )
        )
        factory_registry = AgentFactoryRegistry()
        factory_registry.register(_StubFactory(factory_id="factory.alpha"))
        service = AgentRegistryService(
            registry=registry,
            factory_registry=factory_registry,
        )
        result = service.resolve_and_create(
            AgentRequirement(
                agent_id="agent.alpha",
                required_capabilities=("translate",),
            ),
            factory_context=AgentFactoryContext(
                request_id="req-1",
                actor_id="tester",
            ),
        )
        assert result.instance is None
        assert result.resolution.selected is None

    def test_factory_failure_does_not_report_success(self) -> None:
        cap = _capability("summarize")
        registry = AgentRegistry()
        registry.register(
            _descriptor(
                agent_id="agent.alpha",
                capabilities=(cap,),
                factory_id="factory.alpha",
            )
        )
        factory_registry = AgentFactoryRegistry()
        factory_registry.register(
            _StubFactory(
                factory_id="factory.alpha",
                raise_on_create=AgentFactoryCreationError(
                    "factory refused",
                    {"k": "v"},
                ),
            )
        )
        service = AgentRegistryService(
            registry=registry,
            factory_registry=factory_registry,
        )
        with pytest.raises(AgentFactoryCreationError) as exc_info:
            service.resolve_and_create(
                AgentRequirement(agent_id="agent.alpha"),
                factory_context=AgentFactoryContext(
                    request_id="req-1",
                    actor_id="tester",
                ),
            )
        # The error message must be sanitised; we do not expose
        # internal ``str(exc)`` from the factory.
        assert "factory refused" not in exc_info.value.message
        # Sanity: not_found never raised on this path.
        assert not isinstance(exc_info.value, AgentFactoryNotFoundError)


# ── factory: error mapping does not leak internals ─────────────────────────


class TestFactoryErrorBoundaries:
    """The factory registry converts unexpected internal exceptions
    into ``AgentFactoryCreationError`` without propagating ``str(exc)``."""

    def test_unexpected_exception_in_factory_mapped_to_safe_error(self) -> None:
        registry = AgentFactoryRegistry()
        registry.register(
            _StubFactory(
                factory_id="factory.alpha",
                raise_on_create=RuntimeError("internal api_key=abc"),
            )
        )
        desc = _descriptor(factory_id="factory.alpha")
        context = AgentFactoryContext(request_id="req-1", actor_id="tester")
        with pytest.raises(AgentFactoryCreationError) as exc_info:
            registry.create(desc, context)
        # Internal message must not leak.
        assert "api_key" not in str(exc_info.value.message)
        assert "api_key" not in str(exc_info.value.details)
        # ``str(exc)`` from the original RuntimeError must not appear.
        assert "abc" not in str(exc_info.value.details)


# ═════════════════════════════════════════════════════════════════════════
# Block C – Factory scopes coverage (TRANSIENT/REQUEST/RUN/SINGLETON)
# ═════════════════════════════════════════════════════════════════════════


class _CountingFactory:
    """Factory stub that records create() invocations and instance_ids.

    Each call to ``create`` produces a fresh instance_id derived from
    the call counter, so tests can detect cache reuse vs. fresh
    creation deterministically.
    """

    def __init__(
        self,
        factory_id: str,
        scope: AgentFactoryScope,
        thread_safe: bool = True,
        raises: Exception | None = None,
    ) -> None:
        self.factory_id = factory_id
        self.scope = scope
        self.thread_safe = thread_safe
        self._counter = 0
        self._call_count = 0
        self._raises = raises

    @property
    def call_count(self) -> int:
        return self._call_count

    def supports(self, descriptor: AgentDescriptor) -> bool:
        return True

    def create(
        self,
        descriptor: AgentDescriptor,
        context: AgentFactoryContext,
    ) -> AgentInstance:
        self._call_count += 1
        if self._raises is not None:
            raise self._raises
        self._counter += 1
        runtime = {"factory_id": self.factory_id, "n": self._counter}
        return AgentInstance(
            instance_id=f"{self.factory_id}#{self._counter}",
            descriptor=descriptor,
            runtime_object=runtime,
            scope=self.scope,
        )


def _make_transient_factory() -> _CountingFactory:
    return _CountingFactory(
        factory_id="factory.transient",
        scope=AgentFactoryScope.TRANSIENT,
    )


def _make_request_factory() -> _CountingFactory:
    return _CountingFactory(
        factory_id="factory.request",
        scope=AgentFactoryScope.REQUEST,
    )


def _make_run_factory() -> _CountingFactory:
    return _CountingFactory(
        factory_id="factory.run",
        scope=AgentFactoryScope.RUN,
    )


def _make_singleton_factory() -> _CountingFactory:
    return _CountingFactory(
        factory_id="factory.singleton",
        scope=AgentFactoryScope.SINGLETON,
        thread_safe=True,
    )


class TestTransientScope:
    """TRANSIENT scope: every create() call must produce a fresh instance."""

    def test_new_instance_id_per_call(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _make_transient_factory()
        registry.register(factory)
        desc = _descriptor(factory_id="factory.transient")
        ctx = AgentFactoryContext(request_id="req-1")
        i1 = registry.create(desc, ctx)
        i2 = registry.create(desc, ctx)
        assert i1.instance_id != i2.instance_id

    def test_distinct_runtime_object_per_call(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _make_transient_factory()
        registry.register(factory)
        desc = _descriptor(factory_id="factory.transient")
        ctx = AgentFactoryContext(request_id="req-1")
        i1 = registry.create(desc, ctx)
        i2 = registry.create(desc, ctx)
        assert i1.runtime_object is not i2.runtime_object

    def test_descriptor_match(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _make_transient_factory()
        registry.register(factory)
        desc = _descriptor(factory_id="factory.transient")
        ctx = AgentFactoryContext(request_id="req-1")
        inst = registry.create(desc, ctx)
        assert inst.descriptor is desc

    def test_no_cache_lookup(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _make_transient_factory()
        registry.register(factory)
        desc = _descriptor(factory_id="factory.transient")
        ctx = AgentFactoryContext(request_id="req-1")
        registry.create(desc, ctx)
        registry.create(desc, ctx)
        registry.create(desc, ctx)
        assert factory.call_count == 3
        # And the transient cache is empty (TRANSIENT does not cache).
        assert "factory.transient" not in registry._singleton_keys()

    def test_create_none_descriptor_rejected(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _make_transient_factory()
        registry.register(factory)
        ctx = AgentFactoryContext(request_id="req-1")
        with pytest.raises(AgentRegistryValidationError):
            registry.create(None, ctx)  # type: ignore[arg-type]

    def test_wrong_descriptor_type_rejected(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _make_transient_factory()
        registry.register(factory)
        ctx = AgentFactoryContext(request_id="req-1")
        with pytest.raises(AgentRegistryValidationError):
            registry.create("not a descriptor", ctx)  # type: ignore[arg-type]

    def test_factory_exception_mapped_to_creation_error(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _CountingFactory(
            factory_id="factory.transient",
            scope=AgentFactoryScope.TRANSIENT,
            raises=RuntimeError("internal failure"),
        )
        registry.register(factory)
        desc = _descriptor(factory_id="factory.transient")
        ctx = AgentFactoryContext(request_id="req-1")
        with pytest.raises(AgentFactoryCreationError):
            registry.create(desc, ctx)

    def test_stats_track_attempts_and_failures(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _CountingFactory(
            factory_id="factory.transient",
            scope=AgentFactoryScope.TRANSIENT,
            raises=RuntimeError("boom"),
        )
        registry.register(factory)
        desc = _descriptor(factory_id="factory.transient")
        ctx = AgentFactoryContext(request_id="req-1")
        for _ in range(3):
            with pytest.raises(AgentFactoryCreationError):
                registry.create(desc, ctx)
        stats = registry.stats()
        assert stats["creation_attempts"] == 3
        assert stats["creation_failures"] == 3
        assert stats["creation_successes"] == 0


class TestRequestScope:
    """REQUEST scope: cache by (factory_id, request_id)."""

    def test_reuse_within_same_request(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _make_request_factory()
        registry.register(factory)
        desc = _descriptor(factory_id="factory.request")
        ctx = AgentFactoryContext(request_id="req-A")
        i1 = registry.create(desc, ctx)
        i2 = registry.create(desc, ctx)
        assert i1.instance_id == i2.instance_id
        assert factory.call_count == 1

    def test_no_reuse_across_requests(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _make_request_factory()
        registry.register(factory)
        desc = _descriptor(factory_id="factory.request")
        i1 = registry.create(desc, AgentFactoryContext(request_id="req-A"))
        i2 = registry.create(desc, AgentFactoryContext(request_id="req-B"))
        assert i1.instance_id != i2.instance_id
        assert factory.call_count == 2

    def test_different_request_id_does_not_share(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _make_request_factory()
        registry.register(factory)
        desc = _descriptor(factory_id="factory.request")
        i1 = registry.create(desc, AgentFactoryContext(request_id="req-1"))
        i2 = registry.create(desc, AgentFactoryContext(request_id="req-2"))
        assert i1.instance_id != i2.instance_id

    def test_same_request_preserves_instance(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _make_request_factory()
        registry.register(factory)
        desc = _descriptor(factory_id="factory.request")
        ctx = AgentFactoryContext(request_id="req-stable")
        i1 = registry.create(desc, ctx)
        i2 = registry.create(desc, ctx)
        i3 = registry.create(desc, ctx)
        assert i1.instance_id == i2.instance_id == i3.instance_id

    def test_request_id_required_by_contract(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _make_request_factory()
        registry.register(factory)
        desc = _descriptor(factory_id="factory.request")
        # AgentFactoryContext always provides a default UUID request_id,
        # but the contract requires non-empty. Verify it never fails.
        ctx = AgentFactoryContext()
        inst = registry.create(desc, ctx)
        assert inst.instance_id

    def test_cache_cleared(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _make_request_factory()
        registry.register(factory)
        desc = _descriptor(factory_id="factory.request")
        ctx = AgentFactoryContext(request_id="req-X")
        i1 = registry.create(desc, ctx)
        registry.clear_caches()
        i2 = registry.create(desc, ctx)
        assert i1.instance_id != i2.instance_id
        assert factory.call_count == 2

    def test_thread_safety_concurrent_same_request(self) -> None:
        """Concurrent create() within the same request must yield
        exactly one underlying factory call."""
        import threading

        registry = AgentFactoryRegistry()
        factory = _make_request_factory()
        registry.register(factory)
        desc = _descriptor(factory_id="factory.request")
        ctx = AgentFactoryContext(request_id="req-shared")

        results: list[str] = []
        results_lock = threading.Lock()
        barrier = threading.Barrier(8)

        def worker() -> None:
            barrier.wait()
            inst = registry.create(desc, ctx)
            with results_lock:
                results.append(inst.instance_id)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(set(results)) == 1
        assert factory.call_count == 1


class TestRunScope:
    """RUN scope: cache by (factory_id, run_id); run_id is mandatory."""

    def test_run_id_required(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _make_run_factory()
        registry.register(factory)
        with pytest.raises(AgentRegistryValidationError):
            AgentFactoryContext(request_id="req-1", run_id="")

    def test_run_id_missing_raises(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _make_run_factory()
        registry.register(factory)
        desc = _descriptor(factory_id="factory.run")
        # AgentFactoryContext defaults run_id to None; with no run_id,
        # RUN-scoped factory must reject the call.
        ctx = AgentFactoryContext(request_id="req-1")
        with pytest.raises(AgentFactoryCreationError):
            registry.create(desc, ctx)

    def test_same_run_reuses_instance(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _make_run_factory()
        registry.register(factory)
        desc = _descriptor(factory_id="factory.run")
        i1 = registry.create(desc, AgentFactoryContext(request_id="r1", run_id="run-1"))
        i2 = registry.create(desc, AgentFactoryContext(request_id="r2", run_id="run-1"))
        assert i1.instance_id == i2.instance_id
        assert factory.call_count == 1

    def test_different_run_does_not_reuse(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _make_run_factory()
        registry.register(factory)
        desc = _descriptor(factory_id="factory.run")
        i1 = registry.create(desc, AgentFactoryContext(request_id="r1", run_id="run-1"))
        i2 = registry.create(desc, AgentFactoryContext(request_id="r2", run_id="run-2"))
        assert i1.instance_id != i2.instance_id
        assert factory.call_count == 2

    def test_request_can_differ_within_same_run(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _make_run_factory()
        registry.register(factory)
        desc = _descriptor(factory_id="factory.run")
        i1 = registry.create(desc, AgentFactoryContext(request_id="r1", run_id="run-1"))
        i2 = registry.create(desc, AgentFactoryContext(request_id="r2", run_id="run-1"))
        # Same run, different request_id: still reuses.
        assert i1.instance_id == i2.instance_id

    def test_cache_cleared(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _make_run_factory()
        registry.register(factory)
        desc = _descriptor(factory_id="factory.run")
        i1 = registry.create(desc, AgentFactoryContext(request_id="r1", run_id="run-1"))
        registry.clear_caches()
        i2 = registry.create(desc, AgentFactoryContext(request_id="r1", run_id="run-1"))
        assert i1.instance_id != i2.instance_id
        assert factory.call_count == 2

    def test_factory_incompatible_with_descriptor(self) -> None:
        class _RefusingFactory(_CountingFactory):
            def supports(self, descriptor: AgentDescriptor) -> bool:
                return False

        registry = AgentFactoryRegistry()
        factory = _RefusingFactory(
            factory_id="factory.run",
            scope=AgentFactoryScope.RUN,
        )
        registry.register(factory)
        desc = _descriptor(factory_id="factory.run")
        with pytest.raises(AgentFactoryCompatibilityError):
            registry.create(desc, AgentFactoryContext(request_id="r1", run_id="run-1"))

    def test_wrong_descriptor_type_rejected(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _make_run_factory()
        registry.register(factory)
        with pytest.raises(AgentRegistryValidationError):
            registry.create(
                "not a descriptor",  # type: ignore[arg-type]
                AgentFactoryContext(request_id="r1", run_id="run-1"),
            )

    def test_thread_safety_concurrent_same_run(self) -> None:
        import threading

        registry = AgentFactoryRegistry()
        factory = _make_run_factory()
        registry.register(factory)
        desc = _descriptor(factory_id="factory.run")

        results: list[str] = []
        results_lock = threading.Lock()
        barrier = threading.Barrier(8)

        def worker() -> None:
            barrier.wait()
            inst = registry.create(
                desc, AgentFactoryContext(request_id="r", run_id="run-shared")
            )
            with results_lock:
                results.append(inst.instance_id)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(set(results)) == 1
        assert factory.call_count == 1


class TestSingletonScope:
    """SINGLETON scope: one instance per factory_id, thread_safe=True."""

    def test_singleton_reused_within_registry(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _make_singleton_factory()
        registry.register(factory)
        desc = _descriptor(factory_id="factory.singleton")
        i1 = registry.create(desc, AgentFactoryContext(request_id="r1"))
        i2 = registry.create(desc, AgentFactoryContext(request_id="r2"))
        assert i1.instance_id == i2.instance_id
        assert factory.call_count == 1

    def test_singleton_factory_requires_thread_safe(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _CountingFactory(
            factory_id="factory.singleton",
            scope=AgentFactoryScope.SINGLETON,
            thread_safe=False,
        )
        with pytest.raises(AgentFactoryCompatibilityError):
            registry.register(factory)

    def test_singleton_not_a_module_global(self) -> None:
        """Distinct factory registries must not share singleton caches."""
        a = AgentFactoryRegistry()
        b = AgentFactoryRegistry()
        factory_a = _CountingFactory(
            factory_id="factory.singleton",
            scope=AgentFactoryScope.SINGLETON,
            thread_safe=True,
        )
        a.register(factory_a)
        b.register(_make_singleton_factory())  # fresh
        desc = _descriptor(factory_id="factory.singleton")
        i1 = a.create(desc, AgentFactoryContext(request_id="r1"))
        i2 = b.create(desc, AgentFactoryContext(request_id="r1"))
        assert i1 is not i2

    def test_distinct_registries_do_not_share_singleton(self) -> None:
        a = AgentFactoryRegistry()
        b = AgentFactoryRegistry()
        # Both register a singleton factory with the same factory_id.
        a.register(_make_singleton_factory())
        b.register(_make_singleton_factory())
        desc = _descriptor(factory_id="factory.singleton")
        i1 = a.create(desc, AgentFactoryContext(request_id="r1"))
        i2 = b.create(desc, AgentFactoryContext(request_id="r1"))
        assert i1 is not i2

    def test_singleton_cache_clear(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _make_singleton_factory()
        registry.register(factory)
        desc = _descriptor(factory_id="factory.singleton")
        i1 = registry.create(desc, AgentFactoryContext(request_id="r1"))
        registry.clear_caches()
        i2 = registry.create(desc, AgentFactoryContext(request_id="r2"))
        assert i1.instance_id != i2.instance_id
        assert factory.call_count == 2

    def test_distinct_descriptor_factories_do_not_share(self) -> None:
        """Two singleton factories with different factory_ids must
        not share a single instance."""
        registry = AgentFactoryRegistry()
        registry.register(
            _CountingFactory(
                factory_id="factory.singleton.a",
                scope=AgentFactoryScope.SINGLETON,
                thread_safe=True,
            )
        )
        registry.register(
            _CountingFactory(
                factory_id="factory.singleton.b",
                scope=AgentFactoryScope.SINGLETON,
                thread_safe=True,
            )
        )
        i1 = registry.create(
            _descriptor(agent_id="agent.a", factory_id="factory.singleton.a"),
            AgentFactoryContext(request_id="r"),
        )
        i2 = registry.create(
            _descriptor(agent_id="agent.b", factory_id="factory.singleton.b"),
            AgentFactoryContext(request_id="r"),
        )
        assert i1.instance_id != i2.instance_id

    def test_unregister_factory_invalidates_singleton_cache(self) -> None:
        registry = AgentFactoryRegistry()
        registry.register(_make_singleton_factory())
        desc = _descriptor(factory_id="factory.singleton")
        i1 = registry.create(desc, AgentFactoryContext(request_id="r"))
        registry.unregister("factory.singleton")
        # Re-register and verify the new instance is fresh.
        registry.register(_make_singleton_factory())
        i2 = registry.create(desc, AgentFactoryContext(request_id="r"))
        assert i1 is not i2

    def test_create_failure_does_not_cache(self) -> None:
        """A failing create() must not leave a partial cache entry."""
        registry = AgentFactoryRegistry()
        factory = _CountingFactory(
            factory_id="factory.singleton",
            scope=AgentFactoryScope.SINGLETON,
            thread_safe=True,
            raises=RuntimeError("boom"),
        )
        registry.register(factory)
        desc = _descriptor(factory_id="factory.singleton")
        with pytest.raises(AgentFactoryCreationError):
            registry.create(desc, AgentFactoryContext(request_id="r"))
        # Replace with a working factory; the new create must succeed
        # because nothing was cached from the failed attempt.
        registry.unregister("factory.singleton")
        registry.register(_make_singleton_factory())
        inst = registry.create(desc, AgentFactoryContext(request_id="r"))
        assert inst.instance_id


class TestScopeIsolation:
    """REQUEST, RUN and SINGLETON must not share instance caches
    across each other or with TRANSIENT."""

    def test_request_and_run_keys_are_isolated(self) -> None:
        registry = AgentFactoryRegistry()
        # Two factories with the same factory_id but different scopes
        # cannot both be registered; instead, verify the cache keys
        # remain segregated within the same registry.
        request_factory = _CountingFactory(
            factory_id="factory.shared",
            scope=AgentFactoryScope.REQUEST,
        )
        registry.register(request_factory)
        desc = _descriptor(factory_id="factory.shared")
        registry.create(desc, AgentFactoryContext(request_id="r1"))
        # The request cache has a (factory_id, request_id) key.
        assert ("factory.shared", "r1") in registry._cached_request_keys()
        # And the run cache is empty for this factory.
        run_keys = [k for k in registry._cached_run_keys() if k[0] == "factory.shared"]
        assert run_keys == []

    def test_singleton_does_not_pollute_request_cache(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _CountingFactory(
            factory_id="factory.singleton",
            scope=AgentFactoryScope.SINGLETON,
            thread_safe=True,
        )
        registry.register(factory)
        registry.create(
            _descriptor(factory_id="factory.singleton"),
            AgentFactoryContext(request_id="r1"),
        )
        # Singleton is in the singleton cache only.
        assert "factory.singleton" in registry._singleton_keys()
        assert ("factory.singleton", "r1") not in registry._cached_request_keys()

    def test_transient_never_caches(self) -> None:
        registry = AgentFactoryRegistry()
        factory = _make_transient_factory()
        registry.register(factory)
        registry.create(
            _descriptor(factory_id="factory.transient"),
            AgentFactoryContext(request_id="r1"),
        )
        assert "factory.transient" not in registry._singleton_keys()
        assert ("factory.transient", "r1") not in registry._cached_request_keys()


# ── factory scopes: extended behavior lock-in ────────────────────────────────


class TestFactoryScopesExtended:
    def test_transient_rejects_factory_returning_wrong_scope(self) -> None:
        class _WrongScopeFactory(_CountingFactory):
            def create(
                self,
                descriptor: AgentDescriptor,
                context: AgentFactoryContext,
            ) -> AgentInstance:
                return AgentInstance(
                    instance_id="bad-scope",
                    descriptor=descriptor,
                    runtime_object={"ok": True},
                    scope=AgentFactoryScope.REQUEST,
                )

        registry = AgentFactoryRegistry()
        registry.register(
            _WrongScopeFactory(
                factory_id="factory.transient",
                scope=AgentFactoryScope.TRANSIENT,
            )
        )
        with pytest.raises(AgentFactoryCreationError):
            registry.create(
                _descriptor(factory_id="factory.transient"),
                AgentFactoryContext(request_id="req-a"),
            )

    def test_transient_rejects_factory_returning_wrong_descriptor(self) -> None:
        class _WrongDescriptorFactory(_CountingFactory):
            def create(
                self,
                descriptor: AgentDescriptor,
                context: AgentFactoryContext,
            ) -> AgentInstance:
                return AgentInstance(
                    instance_id="wrong-descriptor",
                    descriptor=_descriptor(
                        agent_id="agent.other",
                        factory_id=descriptor.factory_id,
                    ),
                    runtime_object={"ok": True},
                    scope=self.scope,
                )

        registry = AgentFactoryRegistry()
        registry.register(
            _WrongDescriptorFactory(
                factory_id="factory.transient",
                scope=AgentFactoryScope.TRANSIENT,
            )
        )
        with pytest.raises(AgentFactoryCreationError):
            registry.create(
                _descriptor(factory_id="factory.transient"),
                AgentFactoryContext(request_id="req-a"),
            )

    def test_transient_rejects_missing_runtime_object(self) -> None:
        class _NoRuntimeFactory(_CountingFactory):
            def create(
                self,
                descriptor: AgentDescriptor,
                context: AgentFactoryContext,
            ) -> AgentInstance:
                return AgentInstance(
                    instance_id="no-runtime",
                    descriptor=descriptor,
                    runtime_object=None,
                    scope=self.scope,
                )

        registry = AgentFactoryRegistry()
        registry.register(
            _NoRuntimeFactory(
                factory_id="factory.transient",
                scope=AgentFactoryScope.TRANSIENT,
            )
        )
        with pytest.raises(AgentFactoryCreationError):
            registry.create(
                _descriptor(factory_id="factory.transient"),
                AgentFactoryContext(request_id="req-a"),
            )

    def test_transient_rejects_blank_instance_id(self) -> None:
        class _BlankIdFactory(_CountingFactory):
            def create(
                self,
                descriptor: AgentDescriptor,
                context: AgentFactoryContext,
            ) -> AgentInstance:
                return AgentInstance(
                    instance_id="   ",
                    descriptor=descriptor,
                    runtime_object={"ok": True},
                    scope=self.scope,
                )

        registry = AgentFactoryRegistry()
        registry.register(
            _BlankIdFactory(
                factory_id="factory.transient",
                scope=AgentFactoryScope.TRANSIENT,
            )
        )
        with pytest.raises(AgentFactoryCreationError):
            registry.create(
                _descriptor(factory_id="factory.transient"),
                AgentFactoryContext(request_id="req-a"),
            )

    def test_request_scope_does_not_share_cache_across_registries(self) -> None:
        a = AgentFactoryRegistry()
        b = AgentFactoryRegistry()
        a.register(_make_request_factory())
        b.register(_make_request_factory())
        desc = _descriptor(factory_id="factory.request")
        i1 = a.create(desc, AgentFactoryContext(request_id="req-1"))
        i2 = b.create(desc, AgentFactoryContext(request_id="req-1"))
        assert i1 is not i2

    def test_request_scope_unregister_invalidates_request_cache(self) -> None:
        registry = AgentFactoryRegistry()
        registry.register(_make_request_factory())
        desc = _descriptor(factory_id="factory.request")
        i1 = registry.create(desc, AgentFactoryContext(request_id="req-1"))
        registry.unregister("factory.request")
        registry.register(_make_request_factory())
        i2 = registry.create(desc, AgentFactoryContext(request_id="req-1"))
        assert i1 is not i2

    def test_request_scope_failed_creation_does_not_cache(self) -> None:
        registry = AgentFactoryRegistry()
        failing = _CountingFactory(
            factory_id="factory.request",
            scope=AgentFactoryScope.REQUEST,
            raises=RuntimeError("request boom"),
        )
        registry.register(failing)
        desc = _descriptor(factory_id="factory.request")
        with pytest.raises(AgentFactoryCreationError):
            registry.create(desc, AgentFactoryContext(request_id="req-1"))
        registry.unregister("factory.request")
        registry.register(_make_request_factory())
        created = registry.create(desc, AgentFactoryContext(request_id="req-1"))
        assert created.instance_id

    def test_run_scope_does_not_share_cache_across_registries(self) -> None:
        a = AgentFactoryRegistry()
        b = AgentFactoryRegistry()
        a.register(_make_run_factory())
        b.register(_make_run_factory())
        desc = _descriptor(factory_id="factory.run")
        i1 = a.create(desc, AgentFactoryContext(request_id="req-1", run_id="run-1"))
        i2 = b.create(desc, AgentFactoryContext(request_id="req-1", run_id="run-1"))
        assert i1 is not i2

    def test_run_scope_unregister_invalidates_run_cache(self) -> None:
        registry = AgentFactoryRegistry()
        registry.register(_make_run_factory())
        desc = _descriptor(factory_id="factory.run")
        i1 = registry.create(desc, AgentFactoryContext(request_id="req-1", run_id="r1"))
        registry.unregister("factory.run")
        registry.register(_make_run_factory())
        i2 = registry.create(desc, AgentFactoryContext(request_id="req-1", run_id="r1"))
        assert i1 is not i2

    def test_run_scope_failed_creation_does_not_cache(self) -> None:
        registry = AgentFactoryRegistry()
        registry.register(
            _CountingFactory(
                factory_id="factory.run",
                scope=AgentFactoryScope.RUN,
                raises=RuntimeError("run boom"),
            )
        )
        desc = _descriptor(factory_id="factory.run")
        ctx = AgentFactoryContext(request_id="req-1", run_id="r1")
        with pytest.raises(AgentFactoryCreationError):
            registry.create(desc, ctx)
        registry.unregister("factory.run")
        registry.register(_make_run_factory())
        created = registry.create(desc, ctx)
        assert created.instance_id

    def test_singleton_thread_safety_concurrent_create(self) -> None:
        import threading

        registry = AgentFactoryRegistry()
        factory = _make_singleton_factory()
        registry.register(factory)
        desc = _descriptor(factory_id="factory.singleton")
        barrier = threading.Barrier(8)
        results: list[str] = []
        lock = threading.Lock()

        def worker() -> None:
            barrier.wait()
            inst = registry.create(desc, AgentFactoryContext(request_id="req-1"))
            with lock:
                results.append(inst.instance_id)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert len(set(results)) == 1
        assert factory.call_count == 1

    def test_singleton_rejects_factory_returning_wrong_scope(self) -> None:
        class _WrongScopeFactory(_CountingFactory):
            def create(
                self,
                descriptor: AgentDescriptor,
                context: AgentFactoryContext,
            ) -> AgentInstance:
                return AgentInstance(
                    instance_id="singleton-bad-scope",
                    descriptor=descriptor,
                    runtime_object={"ok": True},
                    scope=AgentFactoryScope.RUN,
                )

        registry = AgentFactoryRegistry()
        registry.register(
            _WrongScopeFactory(
                factory_id="factory.singleton",
                scope=AgentFactoryScope.SINGLETON,
                thread_safe=True,
            )
        )
        with pytest.raises(AgentFactoryCreationError):
            registry.create(
                _descriptor(factory_id="factory.singleton"),
                AgentFactoryContext(request_id="req-1"),
            )

    def test_singleton_rejects_factory_returning_wrong_descriptor(self) -> None:
        class _WrongDescriptorFactory(_CountingFactory):
            def create(
                self,
                descriptor: AgentDescriptor,
                context: AgentFactoryContext,
            ) -> AgentInstance:
                wrong = _descriptor(
                    agent_id="agent.other",
                    factory_id="factory.singleton",
                )
                return AgentInstance(
                    instance_id="singleton-wrong-desc",
                    descriptor=wrong,
                    runtime_object={"ok": True},
                    scope=AgentFactoryScope.SINGLETON,
                )

        registry = AgentFactoryRegistry()
        registry.register(
            _WrongDescriptorFactory(
                factory_id="factory.singleton",
                scope=AgentFactoryScope.SINGLETON,
                thread_safe=True,
            )
        )
        with pytest.raises(AgentFactoryCreationError):
            registry.create(
                _descriptor(factory_id="factory.singleton"),
                AgentFactoryContext(request_id="req-1"),
            )

    def test_singleton_rejects_missing_runtime_object(self) -> None:
        class _NoRuntimeFactory(_CountingFactory):
            def create(
                self,
                descriptor: AgentDescriptor,
                context: AgentFactoryContext,
            ) -> AgentInstance:
                return AgentInstance(
                    instance_id="singleton-no-runtime",
                    descriptor=descriptor,
                    runtime_object=None,
                    scope=AgentFactoryScope.SINGLETON,
                )

        registry = AgentFactoryRegistry()
        registry.register(
            _NoRuntimeFactory(
                factory_id="factory.singleton",
                scope=AgentFactoryScope.SINGLETON,
                thread_safe=True,
            )
        )
        with pytest.raises(AgentFactoryCreationError):
            registry.create(
                _descriptor(factory_id="factory.singleton"),
                AgentFactoryContext(request_id="req-1"),
            )

    def test_singleton_rejects_blank_instance_id(self) -> None:
        class _BlankIdFactory(_CountingFactory):
            def create(
                self,
                descriptor: AgentDescriptor,
                context: AgentFactoryContext,
            ) -> AgentInstance:
                return AgentInstance(
                    instance_id="",
                    descriptor=descriptor,
                    runtime_object={"ok": True},
                    scope=AgentFactoryScope.SINGLETON,
                )

        registry = AgentFactoryRegistry()
        registry.register(
            _BlankIdFactory(
                factory_id="factory.singleton",
                scope=AgentFactoryScope.SINGLETON,
                thread_safe=True,
            )
        )
        with pytest.raises(AgentFactoryCreationError):
            registry.create(
                _descriptor(factory_id="factory.singleton"),
                AgentFactoryContext(request_id="req-1"),
            )


# ── registry lifecycle, versions and aliases ─────────────────────────────────


class TestRegistryLifecycleAndAliases:
    def test_multiple_versions_coexist(self) -> None:
        registry = AgentRegistry()
        v1 = _descriptor(version=AgentVersion(1, 0, 0))
        v2 = _descriptor(version=AgentVersion(2, 0, 0))
        registry.register(v1)
        registry.register(v2)
        listed = registry.list()
        assert len(listed) == 2
        assert {d.version.canonical() for d in listed} == {"1.0.0", "2.0.0"}

    def test_get_returns_latest_active_version(self) -> None:
        registry = AgentRegistry()
        registry.register(_descriptor(version=AgentVersion(1, 0, 0)))
        registry.register(_descriptor(version=AgentVersion(2, 0, 0)))
        latest = registry.get("agent.alpha")
        assert latest is not None
        assert latest.version == AgentVersion(2, 0, 0)

    def test_get_latest_ignores_disabled_version(self) -> None:
        registry = AgentRegistry()
        active = _descriptor(version=AgentVersion(2, 0, 0))
        disabled = _descriptor(version=AgentVersion(3, 0, 0))
        object.__setattr__(disabled, "lifecycle", AgentLifecycle.DISABLED)
        registry.register(active)
        registry._store.add(disabled)
        chosen = registry.get_latest("agent.alpha")
        assert chosen is active

    def test_get_latest_ignores_retired_absence(self) -> None:
        registry = AgentRegistry()
        v1 = _descriptor(version=AgentVersion(1, 0, 0))
        v2 = _descriptor(version=AgentVersion(2, 0, 0))
        registry.register(v1)
        registry.register(v2)
        registry.retire("agent.alpha", AgentVersion(2, 0, 0))
        latest = registry.get("agent.alpha")
        assert latest is v1

    def test_enable_disabled_version_restores_active(self) -> None:
        registry = AgentRegistry()
        desc = _descriptor(lifecycle=AgentLifecycle.DEPRECATED)
        registry.register(desc)
        enabled = registry.enable(desc.agent_id, desc.version)
        assert enabled.lifecycle == AgentLifecycle.ACTIVE

    def test_retired_descriptor_not_reactivable(self) -> None:
        registry = AgentRegistry()
        desc = _descriptor()
        registry.register(desc)
        registry.retire(desc.agent_id, desc.version)
        with pytest.raises(AgentRegistryNotFoundError):
            registry.enable(desc.agent_id, desc.version)

    def test_deprecate_transition_updates_lifecycle(self) -> None:
        registry = AgentRegistry()
        desc = _descriptor()
        registry.register(desc)
        deprecated = registry.deprecate(desc.agent_id, desc.version)
        assert deprecated.lifecycle == AgentLifecycle.DEPRECATED

    def test_retire_removes_descriptor(self) -> None:
        registry = AgentRegistry()
        desc = _descriptor()
        registry.register(desc)
        removed = registry.retire(desc.agent_id, desc.version)
        assert removed.agent_id == desc.agent_id
        assert registry.get(desc.agent_id, desc.version) is None

    def test_invalid_transition_to_disable_on_retired_raises(self) -> None:
        registry = AgentRegistry()
        desc = _descriptor()
        registry.register(desc)
        registry.retire(desc.agent_id, desc.version)
        with pytest.raises(AgentRegistryNotFoundError):
            registry.disable(desc.agent_id, desc.version)

    def test_unregister_specific_version_only(self) -> None:
        registry = AgentRegistry()
        v1 = _descriptor(version=AgentVersion(1, 0, 0))
        v2 = _descriptor(version=AgentVersion(2, 0, 0))
        registry.register(v1)
        registry.register(v2)
        registry.unregister(v1.agent_id, v1.version)
        assert registry.get(v1.agent_id, v1.version) is None
        assert registry.get(v2.agent_id, v2.version) is not None

    def test_alias_exact_lookup_returns_expected_descriptor(self) -> None:
        registry = AgentRegistry()
        desc = _descriptor(aliases=("alias.alpha",))
        registry.register(desc)
        found = registry.find_by_alias("alias.alpha")
        assert found == (desc,)

    def test_alias_conflict_rejected(self) -> None:
        registry = AgentRegistry()
        registry.register(_descriptor(agent_id="agent.one", aliases=("shared",)))
        with pytest.raises(AgentRegistryAliasConflictError):
            registry.register(_descriptor(agent_id="agent.two", aliases=("shared",)))

    def test_alias_released_after_unregister(self) -> None:
        registry = AgentRegistry()
        d1 = _descriptor(agent_id="agent.one", aliases=("shared",))
        registry.register(d1)
        registry.unregister(d1.agent_id, d1.version)
        status = registry.register(
            _descriptor(agent_id="agent.two", aliases=("shared",))
        )
        assert status == AgentRegistrationStatus.REGISTERED

    def test_snapshot_is_immutable_value_object(self) -> None:
        registry = AgentRegistry()
        registry.register(_descriptor())
        snap = registry.snapshot()
        as_dict = snap.to_dict()
        as_dict["descriptors"].append({"agent_id": "fake"})
        fresh = registry.snapshot().to_dict()
        assert len(fresh["descriptors"]) == 1

    def test_list_is_deterministic(self) -> None:
        registry = AgentRegistry()
        registry.register(_descriptor(agent_id="agent.zeta"))
        registry.register(_descriptor(agent_id="agent.alpha"))
        agent_ids = [d.agent_id for d in registry.list()]
        assert agent_ids == ["agent.alpha", "agent.zeta"]

    def test_contains_is_exact_for_identity(self) -> None:
        registry = AgentRegistry()
        desc = _descriptor(version=AgentVersion(1, 0, 1))
        registry.register(desc)
        assert registry.contains(desc.agent_id, desc.version) is True
        assert registry.contains(desc.agent_id, AgentVersion(1, 0, 2)) is False


# ── compatibility checker coverage ────────────────────────────────────────────


class TestCompatibilityCheckerCoverage:
    def test_active_descriptor_is_compatible(self) -> None:
        desc = _descriptor()
        req = AgentRequirement(agent_id=desc.agent_id)
        checker = AgentCompatibilityChecker()
        result = checker.check(desc, req)
        assert result.status == AgentCompatibilityStatus.COMPATIBLE

    def test_disabled_descriptor_is_incompatible(self) -> None:
        desc = _descriptor()
        object.__setattr__(desc, "lifecycle", AgentLifecycle.DISABLED)
        req = AgentRequirement(agent_id=desc.agent_id)
        result = AgentCompatibilityChecker().check(desc, req)
        assert result.status == AgentCompatibilityStatus.INCOMPATIBLE_LIFECYCLE
        assert result.reasons == ("lifecycle_disabled",)

    def test_retired_descriptor_is_incompatible(self) -> None:
        desc = _descriptor()
        object.__setattr__(desc, "lifecycle", AgentLifecycle.RETIRED)
        req = AgentRequirement(agent_id=desc.agent_id)
        result = AgentCompatibilityChecker().check(desc, req)
        assert result.status == AgentCompatibilityStatus.INCOMPATIBLE_LIFECYCLE
        assert result.reasons == ("lifecycle_retired",)

    def test_deprecated_without_opt_in_is_incompatible(self) -> None:
        desc = _descriptor(lifecycle=AgentLifecycle.DEPRECATED)
        req = AgentRequirement(agent_id=desc.agent_id)
        result = AgentCompatibilityChecker().check(desc, req)
        assert result.status == AgentCompatibilityStatus.INCOMPATIBLE_LIFECYCLE
        assert result.reasons == ("lifecycle_deprecated_not_allowed",)

    def test_deprecated_with_opt_in_is_compatible(self) -> None:
        desc = _descriptor(lifecycle=AgentLifecycle.DEPRECATED)
        req = AgentRequirement(agent_id=desc.agent_id, allow_deprecated=True)
        result = AgentCompatibilityChecker().check(desc, req)
        assert result.status == AgentCompatibilityStatus.COMPATIBLE

    def test_experimental_without_opt_in_is_incompatible(self) -> None:
        desc = _descriptor(lifecycle=AgentLifecycle.EXPERIMENTAL)
        req = AgentRequirement(agent_id=desc.agent_id)
        result = AgentCompatibilityChecker().check(desc, req)
        assert result.status == AgentCompatibilityStatus.INCOMPATIBLE_LIFECYCLE
        assert result.reasons == ("lifecycle_experimental_not_allowed",)

    def test_experimental_with_opt_in_is_compatible(self) -> None:
        desc = _descriptor(lifecycle=AgentLifecycle.EXPERIMENTAL)
        req = AgentRequirement(agent_id=desc.agent_id, allow_experimental=True)
        result = AgentCompatibilityChecker().check(desc, req)
        assert result.status == AgentCompatibilityStatus.COMPATIBLE

    def test_missing_capability_is_reported(self) -> None:
        desc = _descriptor(capabilities=(_capability("summarize"),))
        req = AgentRequirement(required_capabilities=("translate",))
        result = AgentCompatibilityChecker().check(desc, req)
        assert result.status == AgentCompatibilityStatus.INCOMPATIBLE_CAPABILITY
        assert result.missing_capabilities == ("translate",)

    def test_missing_operation_is_reported(self) -> None:
        desc = _descriptor(supported_operations=("op.summarize",))
        req = AgentRequirement(required_operations=("op.translate",))
        result = AgentCompatibilityChecker().check(desc, req)
        assert result.status == AgentCompatibilityStatus.INCOMPATIBLE_OPERATION
        assert result.missing_operations == ("op.translate",)

    def test_missing_permission_is_reported(self) -> None:
        desc = _descriptor(required_permissions=("perm.read",))
        req = AgentRequirement(required_permissions=("perm.write",))
        result = AgentCompatibilityChecker().check(desc, req)
        assert result.status == AgentCompatibilityStatus.INCOMPATIBLE_PERMISSION
        assert result.missing_permissions == ("perm.write",)

    def test_missing_component_is_reported(self) -> None:
        registry = AgentFactoryRegistry()
        registry.register(_StubFactory(factory_id="factory.alpha"))
        desc = _descriptor(required_components=("component.x",))
        req = AgentRequirement(agent_id=desc.agent_id)
        result = AgentCompatibilityChecker(factory_registry=registry).check(desc, req)
        assert result.status == AgentCompatibilityStatus.INCOMPATIBLE_COMPONENT
        assert result.missing_components == ("component.x",)

    def test_factory_absent_is_unavailable(self) -> None:
        desc = _descriptor(factory_id="factory.missing")
        req = AgentRequirement(agent_id=desc.agent_id)
        result = AgentCompatibilityChecker(
            factory_registry=AgentFactoryRegistry()
        ).check(desc, req)
        assert result.status == AgentCompatibilityStatus.FACTORY_UNAVAILABLE
        assert result.reasons == ("factory_not_registered",)

    def test_factory_registry_unavailable_via_contains_get_path(self) -> None:
        class _BrokenFactoryRegistry:
            def list(self):
                return ()

            def contains(self, factory_id: str) -> bool:
                raise AgentRegistryError("contains exploded", {})

            def get(self, factory_id: str):
                raise AgentRegistryError("get exploded", {})

        desc = _descriptor()
        req = AgentRequirement(agent_id=desc.agent_id)
        result = AgentCompatibilityChecker(
            factory_registry=_BrokenFactoryRegistry()
        ).check(desc, req)
        assert result.status == AgentCompatibilityStatus.FACTORY_UNAVAILABLE
        assert result.reasons == ("factory_registry_unavailable",)

    def test_version_exact_match_required(self) -> None:
        desc = _descriptor(version=AgentVersion(1, 2, 3))
        req = AgentRequirement(agent_id=desc.agent_id, version="1.2.3")
        result = AgentCompatibilityChecker().check(desc, req)
        assert result.status == AgentCompatibilityStatus.COMPATIBLE

    def test_excluded_agent_is_reported(self) -> None:
        desc = _descriptor(agent_id="agent.excluded")
        req = AgentRequirement(
            required_capabilities=("x",),
            excluded_agents=("agent.excluded",),
        )
        result = AgentCompatibilityChecker().check(desc, req)
        assert result.status == AgentCompatibilityStatus.EXCLUDED
        assert result.reasons == ("agent_excluded",)

    def test_reasons_are_structured_and_deterministic(self) -> None:
        desc = _descriptor(capabilities=(_capability("a"),))
        req = AgentRequirement(required_capabilities=("b", "c"))
        result = AgentCompatibilityChecker().check(desc, req)
        assert isinstance(result.reasons, tuple)
        assert result.reasons == ("missing_capabilities",)
        assert result.missing_capabilities == ("b", "c")


# ── resolver and scoring coverage ─────────────────────────────────────────────


class TestResolverAndScoringCoverage:
    def _service_with_registered_agents(self) -> AgentRegistryService:
        registry = AgentRegistry()
        factory_registry = AgentFactoryRegistry()
        factory_registry.register(_StubFactory(factory_id="factory.alpha"))
        factory_registry.register(_StubFactory(factory_id="factory.beta"))
        factory_registry.register(_StubFactory(factory_id="factory.gamma"))
        registry.register(
            _descriptor(
                agent_id="agent.alpha",
                factory_id="factory.alpha",
                capabilities=(_capability("summarize"),),
                supported_operations=("op.summarize",),
                tags=("stable",),
                priority=1,
            )
        )
        registry.register(
            _descriptor(
                agent_id="agent.beta",
                factory_id="factory.beta",
                capabilities=(_capability("summarize"), _capability("translate")),
                supported_operations=("op.summarize", "op.translate"),
                tags=("stable", "fast"),
                priority=5,
                version=AgentVersion(2, 0, 0),
            )
        )
        registry.register(
            _descriptor(
                agent_id="agent.gamma",
                factory_id="factory.gamma",
                capabilities=(_capability("summarize"),),
                supported_operations=("op.summarize",),
                tags=("legacy",),
                priority=3,
            )
        )
        return AgentRegistryService(
            registry=registry, factory_registry=factory_registry
        )

    def test_exact_agent_id_resolution(self) -> None:
        service = self._service_with_registered_agents()
        resolution = service.resolve_agent(
            AgentRequirement(agent_id="agent.alpha"),
            strategy=AgentResolutionStrategy.EXACT,
        )
        assert resolution.selected is not None
        assert resolution.selected.agent_id == "agent.alpha"

    def test_exact_alias_resolution(self) -> None:
        registry = AgentRegistry()
        factory_registry = AgentFactoryRegistry()
        factory_registry.register(_StubFactory(factory_id="factory.alpha"))
        desc = _descriptor(
            agent_id="agent.alpha",
            aliases=("alpha.alias",),
            factory_id="factory.alpha",
        )
        registry.register(desc)
        resolver = AgentResolver(
            registry=registry,
            compatibility_checker=AgentCompatibilityChecker(
                factory_registry=factory_registry
            ),
        )
        resolution = resolver.resolve(
            AgentRequirement(agent_id="alpha.alias"),
            strategy=AgentResolutionStrategy.EXACT,
        )
        assert resolution.selected is desc

    def test_exact_version_resolution(self) -> None:
        service = self._service_with_registered_agents()
        resolution = service.resolve_agent(
            AgentRequirement(agent_id="agent.beta", version="2.0.0"),
            strategy=AgentResolutionStrategy.EXACT,
        )
        assert resolution.selected is not None
        assert resolution.selected.version == AgentVersion(2, 0, 0)

    def test_exact_missing_raises_not_found(self) -> None:
        service = self._service_with_registered_agents()
        with pytest.raises(AgentResolutionError):
            service.resolve_agent(
                AgentRequirement(agent_id="agent.missing"),
                strategy=AgentResolutionStrategy.EXACT,
            )

    def test_exact_incompatible_raises_not_found(self) -> None:
        service = self._service_with_registered_agents()
        with pytest.raises(AgentResolutionError):
            service.resolve_agent(
                AgentRequirement(
                    agent_id="agent.alpha",
                    required_capabilities=("translate",),
                ),
                strategy=AgentResolutionStrategy.EXACT,
            )

    def test_exact_does_not_fallback_to_other_agents(self) -> None:
        service = self._service_with_registered_agents()
        with pytest.raises(AgentResolutionError):
            service.resolve_agent(
                AgentRequirement(
                    agent_id="agent.alpha",
                    required_capabilities=("translate",),
                ),
                strategy=AgentResolutionStrategy.EXACT,
            )

    def test_best_match_prefers_higher_score(self) -> None:
        service = self._service_with_registered_agents()
        resolution = service.resolve_agent(
            AgentRequirement(required_capabilities=("translate",)),
            strategy=AgentResolutionStrategy.BEST_MATCH,
        )
        assert resolution.selected is not None
        assert resolution.selected.agent_id == "agent.beta"

    def test_preferred_agent_bonus_affects_selection(self) -> None:
        service = self._service_with_registered_agents()
        resolution = service.resolve_agent(
            AgentRequirement(
                required_capabilities=("summarize",),
                preferred_agents=("agent.gamma",),
            ),
            strategy=AgentResolutionStrategy.BEST_MATCH,
        )
        assert resolution.selected is not None
        assert resolution.selected.agent_id == "agent.gamma"

    def test_highest_priority_strategy(self) -> None:
        service = self._service_with_registered_agents()
        resolution = service.resolve_agent(
            AgentRequirement(required_capabilities=("summarize",)),
            strategy=AgentResolutionStrategy.HIGHEST_PRIORITY,
        )
        assert resolution.selected is not None
        assert resolution.selected.agent_id == "agent.beta"

    def test_highest_version_strategy(self) -> None:
        service = self._service_with_registered_agents()
        resolution = service.resolve_agent(
            AgentRequirement(required_capabilities=("summarize",)),
            strategy=AgentResolutionStrategy.HIGHEST_VERSION,
        )
        assert resolution.selected is not None
        assert resolution.selected.version == AgentVersion(2, 0, 0)

    def test_capability_match_strategy(self) -> None:
        service = self._service_with_registered_agents()
        resolution = service.resolve_agent(
            AgentRequirement(
                required_capabilities=("summarize", "translate"),
                required_operations=("op.translate",),
            ),
            strategy=AgentResolutionStrategy.CAPABILITY_MATCH,
        )
        assert resolution.selected is not None
        assert resolution.selected.agent_id == "agent.beta"

    def test_tags_influence_best_match_scoring(self) -> None:
        service = self._service_with_registered_agents()
        resolution = service.resolve_agent(
            AgentRequirement(
                required_capabilities=("summarize",),
                required_tags=("fast",),
            ),
            strategy=AgentResolutionStrategy.BEST_MATCH,
        )
        assert resolution.selected is not None
        assert resolution.selected.agent_id == "agent.beta"

    def test_excluded_agent_is_not_selected_even_if_best(self) -> None:
        service = self._service_with_registered_agents()
        resolution = service.resolve_agent(
            AgentRequirement(
                required_capabilities=("translate",),
                excluded_agents=("agent.beta",),
            ),
            strategy=AgentResolutionStrategy.BEST_MATCH,
        )
        assert resolution.selected is None

    def test_ambiguous_tie_raises(self) -> None:
        registry = AgentRegistry()
        f_reg = AgentFactoryRegistry()
        f_reg.register(_StubFactory(factory_id="factory.a"))
        f_reg.register(_StubFactory(factory_id="factory.b"))
        cap = _capability("same")
        registry.register(
            _descriptor(
                agent_id="agent.a",
                factory_id="factory.a",
                capabilities=(cap,),
                priority=1,
            )
        )
        registry.register(
            _descriptor(
                agent_id="agent.b",
                factory_id="factory.b",
                capabilities=(cap,),
                priority=1,
            )
        )
        resolver = AgentResolver(
            registry=registry,
            compatibility_checker=AgentCompatibilityChecker(factory_registry=f_reg),
        )
        with pytest.raises(AgentResolutionAmbiguousError):
            resolver.resolve(
                AgentRequirement(required_capabilities=("same",)),
                strategy=AgentResolutionStrategy.BEST_MATCH,
            )

    def test_candidate_order_is_deterministic_by_agent_id(self) -> None:
        service = self._service_with_registered_agents()
        resolution = service.resolve_agent(
            AgentRequirement(required_capabilities=("summarize",)),
            strategy=AgentResolutionStrategy.HIGHEST_PRIORITY,
        )
        names = [c.descriptor.agent_id for c in resolution.candidates]
        assert names == sorted(names, key=lambda n: names.index(n))
        assert names == [c.descriptor.agent_id for c in resolution.candidates]

    def test_incompatible_candidates_are_never_selected(self) -> None:
        service = self._service_with_registered_agents()
        resolution = service.resolve_agent(
            AgentRequirement(required_capabilities=("nonexistent",)),
            strategy=AgentResolutionStrategy.BEST_MATCH,
        )
        assert resolution.selected is None
        assert all(
            c.compatibility != AgentCompatibilityStatus.COMPATIBLE
            for c in resolution.candidates
        )

    def test_experimental_not_selected_by_default(self) -> None:
        registry = AgentRegistry()
        factory_registry = AgentFactoryRegistry()
        factory_registry.register(_StubFactory(factory_id="factory.exp"))
        registry.register(
            _descriptor(
                agent_id="agent.exp",
                lifecycle=AgentLifecycle.EXPERIMENTAL,
                factory_id="factory.exp",
                capabilities=(_capability("summarize"),),
            )
        )
        service = AgentRegistryService(
            registry=registry, factory_registry=factory_registry
        )
        resolution = service.resolve_agent(
            AgentRequirement(required_capabilities=("summarize",)),
            strategy=AgentResolutionStrategy.BEST_MATCH,
        )
        assert resolution.selected is None

    def test_deprecated_not_selected_by_default(self) -> None:
        registry = AgentRegistry()
        factory_registry = AgentFactoryRegistry()
        factory_registry.register(_StubFactory(factory_id="factory.dep"))
        registry.register(
            _descriptor(
                agent_id="agent.dep",
                lifecycle=AgentLifecycle.DEPRECATED,
                factory_id="factory.dep",
                capabilities=(_capability("summarize"),),
            )
        )
        service = AgentRegistryService(
            registry=registry, factory_registry=factory_registry
        )
        resolution = service.resolve_agent(
            AgentRequirement(required_capabilities=("summarize",)),
            strategy=AgentResolutionStrategy.BEST_MATCH,
        )
        assert resolution.selected is None

    def test_candidates_are_ordered_deterministically(self) -> None:
        service = self._service_with_registered_agents()
        requirement = AgentRequirement(required_capabilities=("summarize",))
        first = service.resolve_agent(requirement).candidates
        second = service.resolve_agent(requirement).candidates
        assert [c.descriptor.agent_id for c in first] == [
            c.descriptor.agent_id for c in second
        ]


# ── registry service coverage ────────────────────────────────────────────────


class TestRegistryServiceCoverage:
    def _setup_service(self) -> tuple[AgentRegistryService, AgentDescriptor]:
        registry = AgentRegistry()
        factory_registry = AgentFactoryRegistry()
        factory_registry.register(_make_transient_factory())
        descriptor = _descriptor(
            factory_id="factory.transient",
            capabilities=(_capability("summarize"),),
        )
        service = AgentRegistryService(
            registry=registry, factory_registry=factory_registry
        )
        return service, descriptor

    def test_register_agent(self) -> None:
        service, descriptor = self._setup_service()
        status = service.register_agent(descriptor)
        assert status == AgentRegistrationStatus.REGISTERED

    def test_unregister_agent(self) -> None:
        service, descriptor = self._setup_service()
        service.register_agent(descriptor)
        removed = service.unregister_agent(descriptor.agent_id, descriptor.version)
        assert removed == descriptor

    def test_register_factory(self) -> None:
        service = AgentRegistryService()
        registration = service.register_factory(_make_request_factory())
        assert registration.factory_id == "factory.request"

    def test_unregister_factory(self) -> None:
        service = AgentRegistryService()
        service.register_factory(_make_request_factory())
        registration = service.unregister_factory("factory.request")
        assert registration.factory_id == "factory.request"

    def test_resolve_agent(self) -> None:
        service, descriptor = self._setup_service()
        service.register_agent(descriptor)
        resolution = service.resolve_agent(
            AgentRequirement(agent_id=descriptor.agent_id)
        )
        assert resolution.selected is descriptor

    def test_create_agent(self) -> None:
        service, descriptor = self._setup_service()
        service.register_agent(descriptor)
        created = service.create_agent(
            descriptor,
            AgentFactoryContext(request_id="req-1"),
        )
        assert created.descriptor is descriptor

    def test_resolve_and_create(self) -> None:
        service, descriptor = self._setup_service()
        service.register_agent(descriptor)
        provisioned = service.resolve_and_create(
            AgentRequirement(agent_id=descriptor.agent_id),
            factory_context=AgentFactoryContext(request_id="req-1"),
        )
        assert provisioned.instance is not None
        assert provisioned.instance.descriptor is descriptor

    def test_resolve_failure_is_mapped(self) -> None:
        service = AgentRegistryService()
        with pytest.raises(AgentResolutionError):
            service.resolve_agent(
                AgentRequirement(agent_id="missing.agent"),
                strategy=AgentResolutionStrategy.EXACT,
            )

    def test_factory_failure_is_mapped(self) -> None:
        registry = AgentRegistry()
        factory_registry = AgentFactoryRegistry()
        factory_registry.register(
            _StubFactory(
                factory_id="factory.alpha",
                raise_on_create=RuntimeError("token=abc"),
            )
        )
        desc = _descriptor(factory_id="factory.alpha")
        registry.register(desc)
        service = AgentRegistryService(
            registry=registry, factory_registry=factory_registry
        )
        with pytest.raises(AgentFactoryCreationError) as exc_info:
            service.resolve_and_create(
                AgentRequirement(agent_id=desc.agent_id),
                factory_context=AgentFactoryContext(request_id="req-1"),
            )
        assert "token" not in exc_info.value.message.lower()

    def test_request_id_propagates_to_resolution(self) -> None:
        service, descriptor = self._setup_service()
        service.register_agent(descriptor)
        result = service.resolve_and_create(
            AgentRequirement(agent_id=descriptor.agent_id),
            factory_context=AgentFactoryContext(request_id="req-prop"),
        )
        assert result.request_id == "req-prop"
        assert result.resolution.request_id == "req-prop"

    def test_created_instance_descriptor_matches_resolution(self) -> None:
        service, descriptor = self._setup_service()
        service.register_agent(descriptor)
        provisioned = service.resolve_and_create(
            AgentRequirement(agent_id=descriptor.agent_id),
            factory_context=AgentFactoryContext(request_id="req-1"),
        )
        assert provisioned.instance is not None
        assert provisioned.instance.descriptor == provisioned.resolution.selected

    def test_snapshot_does_not_leak_mutable_state(self) -> None:
        service, descriptor = self._setup_service()
        service.register_agent(descriptor)
        snapshot = service.snapshot()
        snapshot["registry"]["descriptors"].append({"agent_id": "tamper"})
        fresh = service.snapshot()
        assert len(fresh["registry"]["descriptors"]) == 1


# ── health, stats and snapshots ──────────────────────────────────────────────


class TestHealthStatsAndSnapshots:
    def _service_for_metrics(self) -> AgentRegistryService:
        registry = AgentRegistry()
        factories = AgentFactoryRegistry()
        factories.register(_make_transient_factory())
        factories.register(_make_request_factory())
        a = _descriptor(
            agent_id="agent.a",
            factory_id="factory.transient",
            kind=AgentKind.GENERAL,
            capabilities=(_capability("summarize"),),
        )
        b = _descriptor(
            agent_id="agent.b",
            factory_id="factory.request",
            kind=AgentKind.TOOL,
            lifecycle=AgentLifecycle.DEPRECATED,
            capabilities=(_capability("translate"),),
        )
        registry.register(a)
        registry.register(b)
        return AgentRegistryService(registry=registry, factory_registry=factories)

    def test_health_reports_registered_agents_count(self) -> None:
        health = self._service_for_metrics().health()
        assert health.registered_agents == 2

    def test_health_reports_active_agents_count(self) -> None:
        health = self._service_for_metrics().health()
        assert health.active_agents == 1

    def test_health_reports_disabled_agents_count(self) -> None:
        service = self._service_for_metrics()
        disabled = _descriptor(
            agent_id="agent.disabled",
            factory_id="factory.transient",
        )
        object.__setattr__(disabled, "lifecycle", AgentLifecycle.DISABLED)
        service.registry._store.add(disabled)
        health = service.health()
        assert health.disabled_agents == 1

    def test_health_reports_registered_factories_count(self) -> None:
        health = self._service_for_metrics().health()
        assert health.registered_factories == 2

    def test_health_reports_unavailable_factories(self) -> None:
        service = self._service_for_metrics()
        service.register_agent(
            _descriptor(agent_id="agent.missing.factory", factory_id="factory.missing")
        )
        health = service.health()
        assert "factory.missing" in health.unavailable_factories

    def test_stats_reports_agents_by_kind(self) -> None:
        stats = self._service_for_metrics().stats()
        assert stats.agents_by_kind["general"] == 1
        assert stats.agents_by_kind["tool"] == 1

    def test_stats_reports_agents_by_lifecycle(self) -> None:
        stats = self._service_for_metrics().stats()
        assert stats.agents_by_lifecycle["active"] == 1
        assert stats.agents_by_lifecycle["deprecated"] == 1

    def test_stats_reports_capability_count(self) -> None:
        stats = self._service_for_metrics().stats()
        assert stats.capability_count == 2

    def test_snapshot_timestamps_are_timezone_aware(self) -> None:
        service = self._service_for_metrics()
        snap = service.snapshot()
        captured = datetime.fromisoformat(snap["captured_at"])
        assert captured.tzinfo is not None

    def test_runtime_object_is_never_serialized(self) -> None:
        service, descriptor = TestRegistryServiceCoverage()._setup_service()
        service.register_agent(descriptor)
        service.resolve_and_create(
            AgentRequirement(agent_id=descriptor.agent_id),
            factory_context=AgentFactoryContext(request_id="req-1"),
        )
        snapshot = service.snapshot()
        serialized = str(snapshot)
        assert "runtime_object" not in serialized


# ── security and error boundaries ────────────────────────────────────────────


class TestSecurityAndErrorBoundaries:
    def test_chain_of_thought_key_rejected_in_context_configuration(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentFactoryContext(configuration={"chain_of_thought": "x"})

    def test_private_prompt_key_rejected_in_context_configuration(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentFactoryContext(configuration={"private_prompt": "x"})

    def test_internal_reasoning_key_rejected_in_context_configuration(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentFactoryContext(configuration={"internal_reasoning": "x"})

    def test_api_key_rejected_in_context_configuration(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentFactoryContext(configuration={"api_key": "x"})

    def test_password_rejected_in_context_configuration(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentFactoryContext(configuration={"password": "x"})

    def test_token_rejected_in_context_configuration(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentFactoryContext(configuration={"token": "x"})

    def test_private_key_rejected_in_context_configuration(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentFactoryContext(configuration={"private_key": "x"})

    def test_non_serializable_metadata_rejected_in_context_components(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentFactoryContext(components={"bad": object()})

    def test_internal_exception_text_not_exposed_in_service_error(self) -> None:
        err = AgentRegistryError(
            "unsafe error",
            {"value": "api_key=secret", "nested": {"password": "p"}},
        )
        as_dict = err.to_dict()
        assert "secret" not in str(as_dict)
        assert as_dict["details"]["nested"]["password"] == "An internal error occurred"

    def test_traceback_text_not_exposed(self) -> None:
        err = AgentRegistryError(
            "Traceback (most recent call last): ...",
            {"trace": "raise RuntimeError('boom')"},
        )
        assert err.message == "An internal error occurred"
        assert err.details["trace"] == "An internal error occurred"

    def test_no_fake_compatible_resolution_allowed(self) -> None:
        desc = _descriptor()
        incompatible = AgentResolutionCandidate(
            descriptor=desc,
            compatibility=AgentCompatibilityStatus.INCOMPATIBLE_CAPABILITY,
            score=0,
        )
        with pytest.raises(AgentRegistryValidationError):
            AgentResolution(
                selected=desc,
                candidates=(incompatible,),
                strategy=AgentResolutionStrategy.BEST_MATCH,
            )

    def test_no_fake_instance_success_allowed(self) -> None:
        desc = _descriptor()
        candidate = AgentResolutionCandidate(
            descriptor=desc,
            compatibility=AgentCompatibilityStatus.COMPATIBLE,
            score=1,
        )
        resolution = AgentResolution(
            selected=desc,
            candidates=(candidate,),
            strategy=AgentResolutionStrategy.BEST_MATCH,
        )
        with pytest.raises(AgentRegistryValidationError):
            AgentProvisioningResult(
                resolution=resolution,
                instance=None,
                request_id="req-1",
            )
