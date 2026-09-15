"""Provider-specific model routes and canonical-model grouping.

A route is the durable pairing of one connection with one provider-specific
model id. Identity is stable across rediscovery: ids are normalized on entry
so a lookup with different padding or case reaches the same stored route,
while provider model ids stay case-sensitive (they are opaque upstream keys).

Error taxonomy mirrors ``provider_connections``: ``get()`` returns ``None``
for unknown or blank ids, while mutators (``register``, ``mark_seen``,
``mark_unavailable``) raise ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum

from kernel.llm.provider_connections import ProviderConnectionRegistry


def _normalize_identity(value: str, *, label: str) -> str:
    """Strip and lowercase a case-insensitive id; reject blank values."""
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError(f"{label} cannot be empty")
    return normalized


def _normalize_model_id(value: str, *, label: str) -> str:
    """Strip a case-sensitive model id without lowering it."""
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} cannot be empty")
    return normalized


def _normalize_lookup_key(value: str) -> str | None:
    """Apply the catalog's canonical id normalization; None for blank input."""
    normalized = value.strip().lower()
    return normalized or None


def _ensure_aware(value: datetime, label: str) -> datetime:
    """Reject naive datetimes so timestamps stay comparable across stores."""
    if value.tzinfo is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value


class CapabilityConfidence(str, Enum):
    """How the catalog came to believe a capability holds for a route."""

    DECLARED = "declared"
    DISCOVERED = "discovered"
    VERIFIED = "verified"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RouteCapabilityState:
    """One capability claim for a route, with its confidence level."""

    name: str
    supported: bool
    confidence: CapabilityConfidence


@dataclass(frozen=True, slots=True)
class ModelRoute:
    """Stable identity for one connection/model pair, with lifecycle state."""

    route_id: str
    connection_id: str
    provider_model_id: str
    canonical_model_id: str
    available: bool = True
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    capabilities: tuple[RouteCapabilityState, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "route_id",
            _normalize_identity(self.route_id, label="Route id"),
        )
        object.__setattr__(
            self,
            "connection_id",
            _normalize_identity(self.connection_id, label="Connection id"),
        )
        object.__setattr__(
            self,
            "provider_model_id",
            _normalize_model_id(self.provider_model_id, label="Provider model id"),
        )
        object.__setattr__(
            self,
            "canonical_model_id",
            _normalize_model_id(self.canonical_model_id, label="Canonical model id"),
        )


@dataclass(frozen=True, slots=True)
class _RouteBinding:
    """One route together with the canonical connection registration it belongs to.

    Private storage detail (MAJOR-V4-01): identity is the opaque registration
    marker the bound
    :class:`~kernel.llm.provider_connections.ProviderConnectionRegistry`
    published when the route was registered, never the ``connection_id`` alone —
    so a removed or same-id re-registered connection leaves the route visibly
    stale instead of silently current. Binding to the registration rather than
    to one of its ``ProviderConnection`` value objects keeps a route current
    across a field-only rewrite of the same connection (a status transition).
    """

    registration: object
    route: ModelRoute


class ModelRouteCatalog:
    """Route catalog keyed by normalized route id, bound to connections.

    A route is the durable pairing of one connection with one provider model
    id, so it must resolve that connection through the bound
    :class:`~kernel.llm.provider_connections.ProviderConnectionRegistry`
    before any mutation (spec §4.4). Provider identity is never inferred from
    the route id: the connection is the only authority on which provider a
    route belongs to.

    The connection registration this route belongs to is retained privately as
    the route's authority binding (MAJOR-V4-01). Field-only mutations —
    availability, ``last_seen_at``, capability or restore rewrites — keep that
    binding, so a stale route can never be silently re-bound to a same-id
    replacement connection.
    """

    def __init__(self, connections: ProviderConnectionRegistry) -> None:
        """Bind the route catalog to the accepted-connection catalog."""
        if not isinstance(connections, ProviderConnectionRegistry):
            raise TypeError("connections must be a ProviderConnectionRegistry")
        self._connections = connections
        self._routes: dict[str, _RouteBinding] = {}

    @property
    def connections(self) -> ProviderConnectionRegistry:
        """Return the connection catalog routes resolve against."""
        return self._connections

    def register(self, route: ModelRoute) -> ModelRoute:
        """Record ``route`` as seen now, rejecting an existing route id.

        ``register()`` means "seen now", so it pins ``available=True`` even
        when the caller passes ``available=False``, stamps ``last_seen_at``,
        and keeps a caller-provided ``first_seen_at`` (defaulting it to now).
        Raises ``ValueError`` for a duplicate id, a naive ``first_seen_at``,
        or a route whose ``connection_id`` was never accepted.
        """
        if route.first_seen_at is not None:
            _ensure_aware(route.first_seen_at, "first_seen_at")
        registration = self._connections.registration(route.connection_id)
        if registration is None:
            raise ValueError(f"unknown connection_id: {route.connection_id}")
        now = datetime.now(timezone.utc)
        stored = replace(
            route,
            available=True,
            first_seen_at=route.first_seen_at or now,
            last_seen_at=now,
        )
        key = stored.route_id
        if key in self._routes:
            raise ValueError(f"duplicate route_id: {key}")
        self._routes[key] = _RouteBinding(registration=registration, route=stored)
        return stored

    def restore(self, route: ModelRoute) -> ModelRoute:
        """Insert a persisted route verbatim, keeping its recorded history.

        ``register()`` means "seen now" (it pins ``available=True`` and stamps
        ``last_seen_at``), so rebuilding a catalog from persistence must not go
        through it: a restart would rewrite availability and timestamps. This
        seam stores the route exactly as persisted while enforcing the same
        referential rule — the connection must already be accepted — and the
        same aware-timestamp rule. Raises ``ValueError`` for an unknown
        connection, a duplicate route id or a naive timestamp.

        A restore establishes a *fresh* binding to the connection registration
        the rebuilt registry holds now (MAJOR-V4-01): a rebuilt runtime is one
        new coherent authority generation, and no object identity is persisted.
        """
        if route.first_seen_at is not None:
            _ensure_aware(route.first_seen_at, "first_seen_at")
        if route.last_seen_at is not None:
            _ensure_aware(route.last_seen_at, "last_seen_at")
        registration = self._connections.registration(route.connection_id)
        if registration is None:
            raise ValueError(f"unknown connection_id: {route.connection_id}")
        key = route.route_id
        if key in self._routes:
            raise ValueError(f"duplicate route_id: {key}")
        self._routes[key] = _RouteBinding(registration=registration, route=route)
        return route

    def restore_all(self, routes: Iterable[ModelRoute]) -> None:
        """Replace every stored route with ``routes``, verbatim.

        The rollback seam for a coordinated mutation: a pass that fails to
        persist must leave the catalog *exactly* as it was, which the other
        mutators cannot express — ``register()`` rejects an existing id and
        re-stamps availability, ``restore()`` rejects duplicates, and nothing
        removes what the pass added.

        Every entry is validated with the same referential and timestamp rules
        as :meth:`restore`, and the catalog is swapped only once the whole input
        validated, so a rejected input leaves the current catalog untouched.
        Availability, capabilities and both timestamps are kept exactly as
        given: this is a state-restoration seam, never a "seen now" seam and
        never a deletion policy (routes are still only ever marked unavailable).

        Authority bindings are restored with the records (MAJOR-V4-01): a record
        already stored keeps the exact registration it was bound to, so undoing
        a pass can never re-bind a stale route to a same-id replacement
        connection. A record the catalog does not currently hold is bound to the
        connection registration accepted now.
        """
        entries: dict[str, _RouteBinding] = {}
        for route in routes:
            if not isinstance(route, ModelRoute):
                raise TypeError("routes must hold ModelRoute entries")
            if route.first_seen_at is not None:
                _ensure_aware(route.first_seen_at, "first_seen_at")
            if route.last_seen_at is not None:
                _ensure_aware(route.last_seen_at, "last_seen_at")
            registration = self._connections.registration(route.connection_id)
            if registration is None:
                raise ValueError(f"unknown connection_id: {route.connection_id}")
            if route.route_id in entries:
                raise ValueError(f"duplicate route_id: {route.route_id}")
            existing = self._routes.get(route.route_id)
            entries[route.route_id] = _RouteBinding(
                registration=(
                    existing.registration if existing is not None else registration
                ),
                route=route,
            )
        self._routes = entries

    def list(self) -> tuple[ModelRoute, ...]:
        """Return every stored route sorted by route id.

        Unavailable routes are included: disappearance is not deletion, so a
        persistence or inventory consumer must still see the route's identity
        and history (``MODEL_DISAPPEARANCE_HISTORY_PRESERVED``).
        """
        return tuple(self._routes[key].route for key in sorted(self._routes))

    def get(self, route_id: str) -> ModelRoute | None:
        """Look up by normalized id; unknown or blank ids return ``None``."""
        key = _normalize_lookup_key(route_id)
        if key is None:
            return None
        binding = self._routes.get(key)
        return None if binding is None else binding.route

    def is_bound_to_current_connection(self, route: ModelRoute) -> bool:
        """Return whether ``route`` still belongs to the current connection authority.

        Authority coherence check (MAJOR-V4-01), read-only: it reports whether
        the route stored under ``route``'s id is that same route and is bound to
        the connection registration the bound registry currently holds for its
        connection id. It never mutates, rebinds or repairs — a stale route
        stays visible and answers ``False``.
        """
        binding = self._routes.get(route.route_id)
        if binding is None:
            return False
        if binding.route is not route and binding.route != route:
            return False
        current_registration = self._connections.registration(route.connection_id)
        return current_registration is binding.registration

    def mark_seen(self, route_id: str, at: datetime | None = None) -> ModelRoute:
        """Refresh ``last_seen_at`` and restore availability for a known route.

        ``at`` is accepted positionally or as a keyword to match the plan's
        ``mark_seen(route_id, at)`` interface (Task 2,
        2026-09-13-cmm-provider-registry-core); the previous keyword-only
        spelling was a spec deviation. Keyword callers remain unaffected.
        Raises ``ValueError`` for an unknown id or a naive ``at``. The stored
        connection registration is kept: this is a field-only update of the same
        registration (MAJOR-V4-01).
        """
        binding = self._require(route_id)
        if at is not None:
            _ensure_aware(at, "at")
        now = at or datetime.now(timezone.utc)
        updated = replace(binding.route, last_seen_at=now, available=True)
        self._routes[binding.route.route_id] = _RouteBinding(
            registration=binding.registration, route=updated
        )
        return updated

    def mark_unavailable(self, route_id: str) -> ModelRoute:
        """Flag a known route unavailable; identity and history are retained.

        Raises ``ValueError`` for an unknown or blank id. The stored connection
        registration is kept: this is a field-only update of the same
        registration (MAJOR-V4-01).
        """
        binding = self._require(route_id)
        updated = replace(binding.route, available=False)
        self._routes[binding.route.route_id] = _RouteBinding(
            registration=binding.registration, route=updated
        )
        return updated

    def routes_for_canonical_model(
        self, canonical_model_id: str
    ) -> tuple[ModelRoute, ...]:
        """Return routes for one canonical model, sorted by route id.

        Matching is case-sensitive on the stored canonical id; unavailable
        routes are included because they remain part of the model's history.
        """
        wanted = canonical_model_id.strip()
        return tuple(
            self._routes[key].route
            for key in sorted(self._routes)
            if self._routes[key].route.canonical_model_id == wanted
        )

    def filter_required_capabilities(
        self, required: tuple[str, ...]
    ) -> tuple[ModelRoute, ...]:
        """Return available routes whose claims satisfy every required name.

        A capability satisfies only when it is present, ``supported`` and not
        ``UNKNOWN`` confidence, so an unknown capability can never back
        capability-required automation. The result is in canonical route-id
        order — never insertion order — so equal catalogs filter
        deterministically regardless of how their routes were added.
        """
        result: list[ModelRoute] = []
        for route_id in sorted(self._routes):
            route = self._routes[route_id].route
            if not route.available:
                continue
            capability_lookup = {c.name: c for c in route.capabilities}
            ok = True
            for name in required:
                state = capability_lookup.get(name)
                if state is None or not state.supported:
                    ok = False
                    break
                if state.confidence is CapabilityConfidence.UNKNOWN:
                    ok = False
                    break
            if ok:
                result.append(route)
        return tuple(result)

    def _require(self, route_id: str) -> _RouteBinding:
        """Resolve a lookup key to a stored binding or raise ``ValueError``."""
        key = _normalize_lookup_key(route_id)
        if key is None or key not in self._routes:
            raise ValueError(f"unknown route_id: {route_id}")
        return self._routes[key]
