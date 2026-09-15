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
failure propagates unchanged to that caller's compensation path.

Secret boundary: the coordinator never holds, reads or writes secret material.
Audit records carry sanitized transition facts only, and the persisted aggregate
carries opaque ``credential_ref`` values, as before.
"""

from __future__ import annotations

from datetime import datetime, timezone

from kernel.llm.model_catalog import ModelCatalog
from kernel.llm.model_routes import ModelRouteCatalog
from kernel.llm.provider_connections import (
    ConnectionStatus,
    ProviderConnection,
    ProviderConnectionRegistry,
)
from kernel.llm.provider_manifests import ProviderManifestRegistry
from kernel.llm.provider_registry import ProviderRegistry
from kernel.llm.provider_state import ProviderRegistryAuditRecord
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
