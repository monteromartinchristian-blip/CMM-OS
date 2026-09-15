"""Durable provider-connection identity for the Provider Registry.

Accepted connections carry a reference into native secret storage; this module
never persists credential material itself.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum

from kernel.llm.exceptions import ProviderError
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec

# Secure-reference scheme allowlist. Interpolated into the error message so
# code and message cannot drift (review round 1, finding 4).
ALLOWED_CREDENTIAL_SCHEMES: tuple[str, ...] = ("keychain://",)

# Substrings that mark a reference as carrying plaintext secret material,
# checked against the whole lowercased ref (not just its prefix) so a key
# embedded after a legitimate scheme is still rejected (finding 3).
_SECRET_MARKERS: tuple[str, ...] = ("sk-", "api-key", "password=", "token=")


def _normalize_identifier(value: str, *, label: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError(f"{label} cannot be empty")
    return normalized


def _normalize_lookup_key(value: str) -> str | None:
    """Apply the registry's canonical id normalization; None for blank input."""
    normalized = value.strip().lower()
    return normalized or None


class BillingClass(str, Enum):
    """How a connection is billed; drives routing and usage enrichment."""

    SUBSCRIPTION = "subscription"
    PAYG = "payg"
    API = "api"
    FREE_OR_API = "free_or_api"


class ConnectionStatus(str, Enum):
    """Lifecycle status of an accepted provider connection."""

    DETECTED = "detected"
    CONNECTED = "connected"
    AUTH_REQUIRED = "auth_required"
    WARNING = "warning"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ProviderConnection:
    """Stable identity for one accepted connection; secrets stay external."""

    connection_id: str
    provider_id: str
    display_name: str
    billing_class: BillingClass
    credential_ref: str | None
    endpoint: str
    isolation_profile_ref: str | None
    status: ConnectionStatus
    created_at: datetime | None = None
    last_validated_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "connection_id",
            _normalize_identifier(self.connection_id, label="Connection id"),
        )
        object.__setattr__(
            self,
            "provider_id",
            _normalize_identifier(self.provider_id, label="Provider id"),
        )
        if not self.display_name.strip():
            raise ValueError("display_name cannot be empty")

        # Coerce enum-typed fields so bare strings cannot enter the inventory
        # through dataclasses.replace()-based mutation paths (finding 5).
        object.__setattr__(self, "billing_class", BillingClass(self.billing_class))
        object.__setattr__(self, "status", ConnectionStatus(self.status))

        normalized_endpoint = self.endpoint.strip()
        if not normalized_endpoint:
            raise ValueError("endpoint cannot be empty")
        object.__setattr__(self, "endpoint", normalized_endpoint)

        if self.credential_ref is not None:
            ref = self.credential_ref.strip()
            lowered = ref.lower()
            if any(marker in lowered for marker in _SECRET_MARKERS):
                raise ValueError("credential_ref must not contain plaintext secrets")
            if not lowered.startswith(ALLOWED_CREDENTIAL_SCHEMES):
                raise ValueError(
                    "credential_ref must use a secure ref scheme: "
                    + ", ".join(ALLOWED_CREDENTIAL_SCHEMES)
                )
            object.__setattr__(self, "credential_ref", ref)


class _ConnectionRegistration:
    """Stable in-memory identity of one accepted connection registration.

    Private storage detail (MAJOR-V4-01). A registration is created by
    :meth:`ProviderConnectionRegistry.register` and lives until that connection
    is removed. ``update_status()`` and ``replace()`` rewrite the *record this
    registration holds* rather than creating a new registration, because a
    frozen ``ProviderConnection`` value object is replaced by every field
    change: the connection's status can transition while it remains the very
    same accepted connection that dependent routes were registered under.

    The record keeps the exact ``ProviderSpec`` object resolved at registration,
    so a removed — or same-id re-registered — provider leaves the connection
    stale instead of silently current. The registration carries no id, counter
    or persisted token: identity is plain object identity inside one live
    runtime, and nothing about it is serialized.

    Callers outside this module receive one only as an opaque identity marker
    (see :meth:`ProviderConnectionRegistry.registration`); its fields are this
    module's private business and are deliberately underscore-prefixed.
    """

    __slots__ = ("_connection", "_provider")

    def __init__(self, provider: ProviderSpec, connection: ProviderConnection) -> None:
        self._provider = provider
        self._connection = connection


class ProviderConnectionRegistry:
    """Catalog of accepted connections, referentially bound to providers.

    Every connection is validated against the canonical
    :class:`ProviderRegistry` it was constructed with, *before* any mutation,
    so a connection can never reference a provider the authority does not
    hold (spec §4.4). The binding is explicit — there is no default or hidden
    registry a caller could accidentally create a second inventory with.
    """

    def __init__(self, provider_registry: ProviderRegistry) -> None:
        """Bind the connection catalog to the canonical provider authority."""
        if not isinstance(provider_registry, ProviderRegistry):
            raise TypeError("provider_registry must be a ProviderRegistry")
        self._provider_registry = provider_registry
        self._items: dict[str, _ConnectionRegistration] = {}

    @property
    def provider_registry(self) -> ProviderRegistry:
        """Return the canonical authority this catalog resolves providers in."""
        return self._provider_registry

    def register(self, connection: ProviderConnection) -> ProviderConnection:
        """Store ``connection`` under its normalized id; reject duplicates.

        Raises the canonical ``ProviderError`` for an unregistered provider
        (before any mutation) and ``ValueError`` for a duplicate id.

        The exact ``ProviderSpec`` resolved here is retained privately as this
        connection's authority binding (MAJOR-V4-01): a later removal of that
        provider — or its same-id replacement by a different object — leaves the
        connection bound to a non-current authority, which capture refuses to
        persist. A fresh registration is also a fresh identity, so a same-id
        re-registration never revives the previous registration's dependents.
        """
        provider = self._provider_registry.get(connection.provider_id)
        key = connection.connection_id
        if key in self._items:
            raise ValueError(f"duplicate connection_id: {key}")
        self._items[key] = _ConnectionRegistration(
            provider=provider, connection=connection
        )
        return connection

    def get(self, connection_id: str) -> ProviderConnection | None:
        """Look up by normalized id; unknown or blank ids return ``None``."""
        registration = self.registration(connection_id)
        return None if registration is None else registration._connection

    def registration(self, connection_id: str) -> _ConnectionRegistration | None:
        """Return the stable registration identity held for ``connection_id``.

        Read-only (MAJOR-V4-01): the returned object *is* the registration the
        registry currently holds — or ``None`` for an unknown or blank id. A
        dependent catalog binds to it so a removed or same-id re-registered
        connection is a different authority, while a field-only rewrite of the
        same registration (:meth:`update_status`, :meth:`replace`) stays
        current. No copy is made and nothing is mutated.
        """
        key = _normalize_lookup_key(connection_id)
        if key is None:
            return None
        return self._items.get(key)

    def is_bound_to_current_provider(self, connection: ProviderConnection) -> bool:
        """Return whether ``connection`` still belongs to the current authority.

        Authority coherence check (MAJOR-V4-01), read-only: it reports whether
        the connection stored under ``connection``'s id is that same record and
        is bound to the exact ``ProviderSpec`` the canonical registry currently
        resolves for its provider id. It never mutates, rebinds or repairs — a
        stale entry stays visible and answers ``False``.
        """
        key = _normalize_lookup_key(connection.connection_id)
        registration = self._items.get(key) if key is not None else None
        if registration is None:
            return False
        if (
            registration._connection is not connection
            and registration._connection != connection
        ):
            return False
        try:
            current_provider = self._provider_registry.get(connection.provider_id)
        except ProviderError:
            return False
        return current_provider is registration._provider

    def list(self, provider_id: str | None = None) -> tuple[ProviderConnection, ...]:
        """Return connections sorted by id, optionally filtered by provider."""
        values = tuple(self._items[key]._connection for key in sorted(self._items))
        if provider_id is None:
            return values
        wanted = _normalize_lookup_key(provider_id)
        return tuple(v for v in values if v.provider_id == wanted)

    def update_status(
        self,
        connection_id: str,
        status: ConnectionStatus,
        *,
        validated_at: datetime | None = None,
    ) -> ProviderConnection:
        """Set ``status``; ``validated_at=None`` keeps the previous timestamp.

        Unlike ``get()``, which returns ``None`` for unknown ids, this raises
        ``ValueError`` for unknown ids and for values outside the status enum.

        The rewritten record keeps this registration's authority binding and
        its identity: the connection is the same accepted connection with a
        field changed, so nothing is re-resolved — it can therefore never be
        silently rebound to a same-id replacement provider or appear to
        dependent routes as a different connection (MAJOR-V4-01).
        """
        key = _normalize_lookup_key(connection_id)
        registration = self._items.get(key) if key is not None else None
        if key is None or registration is None:
            raise ValueError(f"unknown connection_id: {connection_id}")
        current = registration._connection
        updated = replace(
            current,
            status=status,
            last_validated_at=validated_at or current.last_validated_at,
        )
        registration._connection = updated
        return updated

    def replace(self, connection: ProviderConnection) -> ProviderConnection:
        """Put one previously stored connection record back, verbatim.

        The rollback seam for a coordinated mutation: ``update_status()`` is a
        forward mutation (it re-derives the record from its current fields), so
        undoing it exactly — including a ``last_validated_at`` that was ``None``
        before — needs a seam that stores the record as it was, with no field
        rebuilt. The record must already exist (this replaces, it does not
        insert, so it can never resurrect a removed connection), and its
        provider must still be canonical, mirroring :meth:`register`. Raises
        ``TypeError`` for a non-connection, ``ValueError`` for an unknown id and
        the canonical ``ProviderError`` for an unregistered provider.

        The stored authority binding is preserved rather than re-resolved: this
        restores a previous value of the *same* registration, so rebinding here
        would be a silent rebinding path — and a dependent route, which is bound
        to this registration rather than to one of its values, stays current
        (MAJOR-V4-01).
        """
        if not isinstance(connection, ProviderConnection):
            raise TypeError("connection must be a ProviderConnection")
        self._provider_registry.get(connection.provider_id)
        key = connection.connection_id
        registration = self._items.get(key)
        if registration is None:
            raise ValueError(f"unknown connection_id: {key}")
        registration._connection = connection
        return connection

    def remove(self, connection_id: str) -> ProviderConnection:
        """Remove and return one accepted connection (rollback/teardown seam).

        Raises ``ValueError`` for an unknown or blank id, mirroring the other
        mutators; ``get()`` keeps its ``None``-for-unknown contract.
        """
        key = _normalize_lookup_key(connection_id)
        if key is None or key not in self._items:
            raise ValueError(f"unknown connection_id: {connection_id}")
        return self._items.pop(key)._connection
