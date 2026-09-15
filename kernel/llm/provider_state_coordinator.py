"""One coordinator for Provider Registry state commits (MAJOR-V2-02).

Every durable Provider Registry mutation that changes phase-owned state goes
through this seam, in one fixed order (spec §5.4):

```text
canonical mutation → sanitized audit records → coherent capture
→ revision + 1 → repository.save() → publish new in-memory revision/audit
```

The canonical components stay exactly where they are:
:class:`~kernel.llm.provider_registry.ProviderRegistry` is still the only
provider identity authority, the manifest catalog, model catalog, connection
registry and route catalog keep their own contracts, and
:class:`~kernel.llm.provider_state_repository.ProviderRegistryStateRepository`
keeps owning persistence. This coordinator owns the *commit* — the revision
counter, the sanitized audit log and the wiring to the repository — so there is
exactly one place a revision can advance or a durable aggregate be written.

Scope rule: this is not a general transaction manager, event bus, persistence
framework, second registry or routing engine. It holds one Provider Registry
aggregate and nothing else.

Failure rule: the in-memory revision and audit log are published only *after*
``repository.save()`` returns, so a failed save leaves the coordinator believing
nothing committed and the previous durable revision untouched. Domain mutations
performed by a caller (for example the connection registration in
:meth:`ProviderOnboardingService.accept`) stay the caller's compensation, and a
failure propagates unchanged to that caller's compensation path. The two
operations that mutate a canonical component themselves —
:meth:`ProviderRegistryStateCoordinator.discover_models` and
:meth:`ProviderRegistryStateCoordinator.update_connection_status` — restore
exactly the state they changed before re-raising, using the smallest snapshot
that component already exposes.

Secret boundary: the coordinator never holds, reads or writes secret material.
Audit records carry sanitized transition facts only, and the persisted aggregate
carries opaque ``credential_ref`` values, as before.
"""

from __future__ import annotations

from datetime import datetime, timezone

from kernel.llm.model_catalog import ModelCatalog
from kernel.llm.model_discovery import (
    DiscoverableModelClient,
    ModelDiscoveryResult,
    discover_models,
)
from kernel.llm.model_routes import ModelRoute, ModelRouteCatalog
from kernel.llm.provider_connections import (
    ConnectionStatus,
    ProviderConnection,
    ProviderConnectionRegistry,
)
from kernel.llm.provider_manifests import ProviderManifest, ProviderManifestRegistry
from kernel.llm.provider_registry import ProviderRegistry
from kernel.llm.provider_state import (
    ProviderRegistryAuditRecord,
    ProviderStateCoherenceError,
)
from kernel.llm.provider_state_repository import (
    ProviderRegistryStateRepository,
    capture_provider_registry_state,
)


class ProviderRegistryStateCoordinator:
    """The single revision/audit commit seam for the Provider Registry.

    Owns the canonical components plus the repository and the durable
    revision/audit state; owns no secrets and no second authority.
    """

    def __init__(
        self,
        *,
        providers: ProviderRegistry,
        manifests: ProviderManifestRegistry,
        models: ModelCatalog,
        connections: ProviderConnectionRegistry,
        routes: ModelRouteCatalog,
        repository: ProviderRegistryStateRepository,
        revision: int = 0,
        audit_log: tuple[ProviderRegistryAuditRecord, ...] = (),
    ) -> None:
        """Wire the coordinator to the canonical graph and its persistence.

        ``revision`` and ``audit_log`` are resumed from the loaded aggregate,
        so a restored runtime continues the same history instead of restarting
        it.

        Graph rule (MAJOR-V3-01): construction fails closed — before any field
        is assigned — unless every component belongs to the exact object graph
        of ``providers``/``connections``. A cross-wired graph holding the same
        normalized provider id in two different ``ProviderRegistry`` objects
        raises :class:`ProviderStateCoherenceError`; nothing is copied, rebound
        or normalized by id.
        """
        if not isinstance(providers, ProviderRegistry):
            raise TypeError("providers must be a ProviderRegistry")
        if not isinstance(manifests, ProviderManifestRegistry):
            raise TypeError("manifests must be a ProviderManifestRegistry")
        if not isinstance(models, ModelCatalog):
            raise TypeError("models must be a ModelCatalog")
        if not isinstance(connections, ProviderConnectionRegistry):
            raise TypeError("connections must be a ProviderConnectionRegistry")
        if not isinstance(routes, ModelRouteCatalog):
            raise TypeError("routes must be a ModelRouteCatalog")
        if not isinstance(repository, ProviderRegistryStateRepository):
            raise TypeError("repository must be a ProviderRegistryStateRepository")
        if isinstance(revision, bool) or not isinstance(revision, int):
            raise TypeError("revision must be an int")
        if revision < 0:
            raise ValueError("revision cannot be negative")
        records = tuple(audit_log)
        if any(
            not isinstance(record, ProviderRegistryAuditRecord) for record in records
        ):
            raise TypeError("audit_log must hold ProviderRegistryAuditRecord entries")
        if manifests.provider_registry is not providers:
            raise ProviderStateCoherenceError(
                "manifest registry is bound to a different ProviderRegistry"
            )
        if models.provider_registry is not providers:
            raise ProviderStateCoherenceError(
                "model catalog is bound to a different ProviderRegistry"
            )
        if connections.provider_registry is not providers:
            raise ProviderStateCoherenceError(
                "connection registry is bound to a different ProviderRegistry"
            )
        if routes.connections is not connections:
            raise ProviderStateCoherenceError(
                "route catalog is bound to a different ProviderConnectionRegistry"
            )

        self._providers = providers
        self._manifests = manifests
        self._models = models
        self._connections = connections
        self._routes = routes
        self._repository = repository
        self._revision = revision
        self._audit_log = records

    @property
    def revision(self) -> int:
        """Return the revision this coordinator has last published."""
        return self._revision

    @property
    def audit_log(self) -> tuple[ProviderRegistryAuditRecord, ...]:
        """Return the sanitized audit history published with that revision."""
        return self._audit_log

    @property
    def providers(self) -> ProviderRegistry:
        """Return the canonical provider authority this coordinator commits.

        Read-only (MAJOR-V3-01): a composition boundary — onboarding, today —
        proves exact object identity through this accessor. There is
        deliberately no setter and no rebinding method.
        """
        return self._providers

    @property
    def manifests(self) -> ProviderManifestRegistry:
        """Return the manifest catalog bound to :attr:`providers` (read-only)."""
        return self._manifests

    @property
    def connections(self) -> ProviderConnectionRegistry:
        """Return the connection registry bound to :attr:`providers` (read-only)."""
        return self._connections

    def persist_connection_acceptance(
        self,
        connection: ProviderConnection,
        *,
        occurred_at: datetime | None = None,
    ) -> None:
        """Commit one accepted connection as a new revision plus one record.

        The caller has already performed the canonical mutation — the
        connection is registered in the canonical
        :class:`ProviderConnectionRegistry` — so this operation only commits the
        aggregate. It validates that the connection really is registered before
        writing anything, so the audit history can never describe a connection
        the persisted aggregate does not contain.

        The status is read from the *registered* connection and decides the
        event type: ``provider.connected`` for a ``CONNECTED`` acceptance,
        ``connection.accepted`` otherwise.
        """
        if not isinstance(connection, ProviderConnection):
            raise TypeError("connection must be a ProviderConnection")
        registered = self._connections.get(connection.connection_id)
        if registered is None:
            raise ValueError(
                f"connection is not registered: {connection.connection_id}"
            )
        self._commit(
            (
                self._audit_record(
                    event_type=(
                        "provider.connected"
                        if registered.status is ConnectionStatus.CONNECTED
                        else "connection.accepted"
                    ),
                    entity_kind="connection",
                    entity_id=registered.connection_id,
                    occurred_at=occurred_at or datetime.now(timezone.utc),
                    detail=(("status", registered.status.value),),
                ),
            )
        )

    def discover_models(
        self,
        connection: ProviderConnection,
        manifest: ProviderManifest,
        client: DiscoverableModelClient,
        *,
        seen_at: datetime,
    ) -> ModelDiscoveryResult:
        """Run one administrative discovery pass and commit its lifecycle.

        Reconciliation stays where it was: the pure, inference-free, I/O-free
        :func:`~kernel.llm.model_discovery.discover_models` still owns the
        rules. This operation wraps it — the pass runs against the canonical
        route catalog, the pre/post route state decides what really changed,
        and everything that changed becomes sanitized audit records committed
        as exactly one new revision.

        Manifest authority rule (MAJOR-V4-03): the ``manifest`` argument is a
        claim, not authority. The method canonicalizes the connection through
        its exact bound connection registry and then requires the caller's
        manifest to *be* the active canonical manifest for the registered
        connection's provider — exact object identity, because a same-id
        manifest with different activation policy would otherwise inject
        foreign metadata into canonical route state. A foreign or stale
        manifest, or a provider with no active canonical metadata, raises
        :class:`ProviderStateCoherenceError` before the client is consulted and
        before any route, audit, revision or repository state can change. The
        caller's manifest is never silently ignored in favour of the canonical
        one: passing the wrong object is a caller composition error.

        Commit rule (MAJOR-V3-02): one discovery pass is at most one mutation
        batch and therefore at most one revision, written only after
        ``repository.save()`` returns. A pass that changed durable route state
        commits — lifecycle transitions (``route.discovered``,
        ``route.unavailable``, ``route.restored``) *and* refreshes, where a
        route that existed before and remains available simply has a newer
        ``last_seen_at``. A refresh is phase-owned state like any other, so it
        is escaped as ``route.refreshed`` rather than being left live-only. The
        pass is a true no-op — nothing durable happens and the revision does
        not advance — only when canonical state is unchanged: an empty
        administrative result, a repeated allowlist deferral with no field
        change, or an identical pass at the same ``seen_at``.

        Failure rule: the pre-pass catalog is the whole snapshot, and it is put
        back verbatim if the pass or the save fails — including a refresh-only
        failure — so a failed discovery leaves routes, revision and audit log
        exactly as they were.
        """
        if not isinstance(connection, ProviderConnection):
            raise TypeError("connection must be a ProviderConnection")
        if not isinstance(manifest, ProviderManifest):
            raise TypeError("manifest must be a ProviderManifest")
        if not isinstance(seen_at, datetime):
            raise TypeError("seen_at must be a datetime")
        if seen_at.tzinfo is None:
            raise ValueError("seen_at must be timezone-aware")
        registered = self._connections.get(connection.connection_id)
        if registered is None:
            raise ValueError(
                f"connection is not registered: {connection.connection_id}"
            )
        canonical_manifest = self._manifests.get(registered.provider_id)
        if canonical_manifest is None or canonical_manifest is not manifest:
            raise ProviderStateCoherenceError(
                "discovery manifest is not the active canonical manifest"
            )

        routes_before = self._routes.list()
        try:
            result = discover_models(
                registered, manifest, client, self._routes, seen_at=seen_at
            )
            routes_after = self._routes.list()
            records = self._discovery_records(
                registered.connection_id, result, routes_before, seen_at
            ) + self._route_refresh_records(
                registered.connection_id, result, routes_before, routes_after, seen_at
            )
            if records:
                self._commit(records)
        except Exception:
            # Undo only what this pass changed: the route catalog, restored to
            # its pre-pass tuple. The revision and audit log were never
            # published (``_commit`` publishes last), so they stand unchanged.
            self._routes.restore_all(routes_before)
            raise
        return result

    def _discovery_records(
        self,
        connection_id: str,
        result: ModelDiscoveryResult,
        routes_before: tuple[ModelRoute, ...],
        seen_at: datetime,
    ) -> tuple[ProviderRegistryAuditRecord, ...]:
        """Derive the sanitized lifecycle records one discovery pass produced.

        Records are derived from the ``ModelDiscoveryResult`` alone: the client
        payload is never consulted, so no provider response can reach the audit
        log, and each record carries only the connection id and an availability
        string.

        ``unavailable_route_ids`` mixes real transitions with repeated reports —
        the reconciler also lists a route that was *already* unavailable and is
        still excluded by the allowlist. Those are filtered against the pre-pass
        snapshot, so a record is only emitted for a route that actually changed,
        which is what keeps a no-op scan from advancing the revision.
        """
        available_before = {
            route.route_id for route in routes_before if route.available
        }
        deferred = frozenset(result.unavailable_route_ids)
        newly_discovered = frozenset(result.new_route_ids)
        records: list[ProviderRegistryAuditRecord] = []
        for route_id in result.new_route_ids:
            records.append(
                self._audit_record(
                    event_type="route.discovered",
                    entity_kind="route",
                    entity_id=route_id,
                    occurred_at=seen_at,
                    detail=(
                        ("connection_id", connection_id),
                        ("available", "false" if route_id in deferred else "true"),
                    ),
                )
            )
        for route_id in result.unavailable_route_ids:
            if route_id not in available_before and route_id not in newly_discovered:
                continue
            records.append(
                self._audit_record(
                    event_type="route.unavailable",
                    entity_kind="route",
                    entity_id=route_id,
                    occurred_at=seen_at,
                    detail=(("connection_id", connection_id), ("available", "false")),
                )
            )
        for route_id in result.restored_route_ids:
            records.append(
                self._audit_record(
                    event_type="route.restored",
                    entity_kind="route",
                    entity_id=route_id,
                    occurred_at=seen_at,
                    detail=(("connection_id", connection_id), ("available", "true")),
                )
            )
        return tuple(records)

    def _route_refresh_records(
        self,
        connection_id: str,
        result: ModelDiscoveryResult,
        routes_before: tuple[ModelRoute, ...],
        routes_after: tuple[ModelRoute, ...],
        seen_at: datetime,
    ) -> tuple[ProviderRegistryAuditRecord, ...]:
        """Derive the sanitized ``route.refreshed`` records of one discovery pass.

        A refresh is the mutation the lifecycle tuples cannot express: a route
        that existed before, still exists, stayed available and was advertised
        again at a newer ``last_seen_at``. Those routes appear in none of
        ``new_route_ids``/``restored_route_ids``/``unavailable_route_ids``, so
        the pre/post snapshots are compared directly, keyed by route id for a
        deterministic walk in canonical id order.

        Lifecycle semantics take precedence (spec §6.6): a route that received
        ``route.discovered``/``route.restored``/``route.unavailable`` in this
        same pass is never also reported as refreshed. Availability on both
        sides must be true, which excludes a vanished (newly unavailable) or
        deferred route by construction, and an already-deferred route is never
        stamped by ``mark_seen`` so it cannot appear here either.

        Detail is sanitized: exactly the connection id and ``available=true``.
        No provider payload, model-list response, credential material or
        timestamp is echoed into the audit log.
        """
        before = {route.route_id: route for route in routes_before}
        after = {route.route_id: route for route in routes_after}
        lifecycle_ids = (
            frozenset(result.new_route_ids)
            | frozenset(result.restored_route_ids)
            | frozenset(result.unavailable_route_ids)
        )
        records: list[ProviderRegistryAuditRecord] = []
        for route_id in sorted(after):
            previous = before.get(route_id)
            current = after[route_id]
            if previous is None or route_id in lifecycle_ids:
                continue
            if not (previous.available and current.available):
                continue
            if previous.last_seen_at == current.last_seen_at:
                continue
            records.append(
                self._audit_record(
                    event_type="route.refreshed",
                    entity_kind="route",
                    entity_id=route_id,
                    occurred_at=seen_at,
                    detail=(
                        ("connection_id", connection_id),
                        ("available", "true"),
                    ),
                )
            )
        return tuple(records)

    def update_connection_status(
        self,
        connection_id: str,
        status: ConnectionStatus,
        *,
        occurred_at: datetime,
    ) -> ProviderConnection:
        """Move one accepted connection to a new status and commit the change.

        This is the one canonical operation for a real status transition, and
        the connection is replaced through the existing canonical
        :class:`~kernel.llm.provider_connections.ProviderConnectionRegistry` —
        no second registry and no validation engine.

        No-op rule: the operation is a *transition* seam, so re-setting the
        status a connection already has is a caller error, not a silent write.
        It is rejected before anything is mutated, and the refusal is explicit
        because a stored no-op would either fabricate an audit record for a
        transition that never happened or record nothing at all.

        Failure rule: if the commit fails, the exact previous connection record
        is put back (status *and* validation timestamp), so a failed transition
        leaves the registry, the revision and the audit log exactly as they
        were.
        """
        if not isinstance(status, ConnectionStatus):
            raise TypeError("status must be a ConnectionStatus")
        if not isinstance(occurred_at, datetime):
            raise TypeError("occurred_at must be a datetime")
        if occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        existing = self._connections.get(connection_id)
        if existing is None:
            raise ValueError(f"unknown connection_id: {connection_id}")
        if existing.status is status:
            raise ValueError(f"connection status unchanged: {existing.status.value}")

        try:
            updated = self._connections.update_status(
                connection_id,
                status,
                validated_at=occurred_at,
            )
            self._commit(
                (
                    self._audit_record(
                        event_type="provider.validation_changed",
                        entity_kind="connection",
                        entity_id=updated.connection_id,
                        occurred_at=occurred_at,
                        detail=(
                            ("old_status", existing.status.value),
                            ("new_status", updated.status.value),
                        ),
                    ),
                )
            )
        except Exception:
            # Undo only what this call changed: the one connection record,
            # restored verbatim. The revision and audit log were never published
            # (``_commit`` publishes last), so they stand unchanged.
            self._connections.replace(existing)
            raise
        return updated

    def _next_revision(self) -> int:
        """Return the revision a successful commit publishes."""
        return self._revision + 1

    def _audit_record(
        self,
        *,
        event_type: str,
        entity_kind: str,
        entity_id: str,
        occurred_at: datetime,
        detail: tuple[tuple[str, str], ...] = (),
    ) -> ProviderRegistryAuditRecord:
        """Build one sanitized audit record stamped with the next revision."""
        return ProviderRegistryAuditRecord(
            revision=self._next_revision(),
            event_type=event_type,
            entity_kind=entity_kind,
            entity_id=entity_id,
            occurred_at=occurred_at,
            detail=detail,
        )

    def _commit(self, records: tuple[ProviderRegistryAuditRecord, ...]) -> int:
        """Publish exactly one new revision carrying ``records``.

        Capture, save, then publish: the in-memory revision and audit log move
        only after ``repository.save()`` returns, so a failed save propagates
        unchanged and leaves both the coordinator and the durable document at
        the previous revision. ``records`` must already carry the next revision
        (see :meth:`_audit_record`); that is checked rather than assumed so an
        incoherent audit revision can never be persisted.
        """
        next_revision = self._next_revision()
        for record in records:
            if record.revision != next_revision:
                raise ValueError(
                    f"audit record revision must be {next_revision}: {record.revision}"
                )
        state = capture_provider_registry_state(
            self._providers,
            self._manifests,
            self._models,
            self._connections,
            self._routes,
            revision=next_revision,
            audit_log=self._audit_log + records,
        )
        self._repository.save(state)
        self._revision = next_revision
        self._audit_log = state.audit_log
        return next_revision
