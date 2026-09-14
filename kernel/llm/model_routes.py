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

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum


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


class ModelRouteCatalog:
    """In-memory route catalog keyed by normalized route id."""

    def __init__(self) -> None:
        self._routes: dict[str, ModelRoute] = {}

    def register(self, route: ModelRoute) -> ModelRoute:
        """Record ``route`` as seen now, rejecting an existing route id.

        ``register()`` means "seen now", so it pins ``available=True`` even
        when the caller passes ``available=False``, stamps ``last_seen_at``,
        and keeps a caller-provided ``first_seen_at`` (defaulting it to now).
        Raises ``ValueError`` for a duplicate id or a naive ``first_seen_at``.
        """
        if route.first_seen_at is not None:
            _ensure_aware(route.first_seen_at, "first_seen_at")
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
        self._routes[key] = stored
        return stored

    def get(self, route_id: str) -> ModelRoute | None:
        """Look up by normalized id; unknown or blank ids return ``None``."""
        key = _normalize_lookup_key(route_id)
        if key is None:
            return None
        return self._routes.get(key)

    def mark_seen(self, route_id: str, at: datetime | None = None) -> ModelRoute:
        """Refresh ``last_seen_at`` and restore availability for a known route.

        ``at`` is accepted positionally or as a keyword to match the plan's
        ``mark_seen(route_id, at)`` interface (Task 2,
        2026-09-13-cmm-provider-registry-core); the previous keyword-only
        spelling was a spec deviation. Keyword callers remain unaffected.
        Raises ``ValueError`` for an unknown id or a naive ``at``.
        """
        current = self._require(route_id)
        if at is not None:
            _ensure_aware(at, "at")
        now = at or datetime.now(timezone.utc)
        updated = replace(current, last_seen_at=now, available=True)
        self._routes[current.route_id] = updated
        return updated

    def mark_unavailable(self, route_id: str) -> ModelRoute:
        """Flag a known route unavailable; identity and history are retained.

        Raises ``ValueError`` for an unknown or blank id.
        """
        current = self._require(route_id)
        updated = replace(current, available=False)
        self._routes[current.route_id] = updated
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
            self._routes[key]
            for key in sorted(self._routes)
            if self._routes[key].canonical_model_id == wanted
        )

    def filter_required_capabilities(
        self, required: tuple[str, ...]
    ) -> tuple[ModelRoute, ...]:
        """Return available routes whose claims satisfy every required name.

        A capability satisfies only when it is present, ``supported`` and not
        ``UNKNOWN`` confidence, so an unknown capability can never back
        capability-required automation.
        """
        result: list[ModelRoute] = []
        for route in self._routes.values():
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

    def _require(self, route_id: str) -> ModelRoute:
        """Resolve a lookup key to a stored route or raise ``ValueError``."""
        key = _normalize_lookup_key(route_id)
        if key is None or key not in self._routes:
            raise ValueError(f"unknown route_id: {route_id}")
        return self._routes[key]
