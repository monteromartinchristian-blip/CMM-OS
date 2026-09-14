"""Provider inventory projections for usage consumers.

Snapshots are the provider-independent boundary CMM Usage (and later
CMMChat) consume: primitive-serializable, deterministic, and free of
secrets, isolation profile paths, and raw external config metadata.
Builders project domain objects (``ProviderConnection``,
``ConnectionProposal``, ``ModelRoute``) into snapshots; only public
identity, lifecycle status, and capability claims cross the boundary.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone

from kernel.llm.model_routes import ModelRoute
from kernel.llm.provider_connections import (
    BillingClass,
    ConnectionStatus,
    ProviderConnection,
)
from kernel.llm.provider_onboarding import ConnectionProposal

PROVIDER_DETECTED = "provider.detected"
PROVIDER_CONNECTED = "provider.connected"
PROVIDER_DISCONNECTED = "provider.disconnected"
PROVIDER_VALIDATION_CHANGED = "provider.validation_changed"
MODEL_DISCOVERED = "model.discovered"
MODEL_AVAILABLE = "model.available"
MODEL_UNAVAILABLE = "model.unavailable"
MODEL_CAPABILITIES_CHANGED = "model.capabilities_changed"

PROVIDER_EVENT_NAMES: tuple[str, ...] = (
    PROVIDER_DETECTED,
    PROVIDER_CONNECTED,
    PROVIDER_DISCONNECTED,
    PROVIDER_VALIDATION_CHANGED,
    MODEL_DISCOVERED,
    MODEL_AVAILABLE,
    MODEL_UNAVAILABLE,
    MODEL_CAPABILITIES_CHANGED,
)


def _isoformat(value: datetime | None, *, label: str) -> str | None:
    """Render an aware datetime as ISO-8601; reject naive values."""
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.isoformat()


def _require_text(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} cannot be empty")
    return value


def _optional_text(value: object, *, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} cannot be empty")
    return value


@dataclass(frozen=True, slots=True)
class ProviderConnectionSnapshot:
    """Public projection of one connection; no secrets or paths."""

    connection_id: str
    provider_id: str
    display_name: str
    billing_class: str
    status: str
    connected: bool
    created_at: str | None = None
    last_validated_at: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.connection_id, label="connection_id")
        _require_text(self.provider_id, label="provider_id")
        _require_text(self.display_name, label="display_name")
        _require_text(self.billing_class, label="billing_class")
        _require_text(self.status, label="status")
        if not isinstance(self.connected, bool):
            raise TypeError("connected must be a bool")
        _optional_text(
            self.created_at, label="created_at"
        ) if self.created_at is not None else None
        if self.last_validated_at is not None:
            _optional_text(self.last_validated_at, label="last_validated_at")

    def to_dict(self) -> dict[str, object]:
        """Return a primitive-serializable mapping of this snapshot."""
        return {
            "connection_id": self.connection_id,
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "billing_class": self.billing_class,
            "status": self.status,
            "connected": self.connected,
            "created_at": self.created_at,
            "last_validated_at": self.last_validated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ProviderConnectionSnapshot:
        """Rebuild a snapshot from a ``to_dict()`` mapping."""
        if not isinstance(payload, dict):
            raise TypeError("payload must be a mapping")
        try:
            return cls(
                connection_id=_require_text(
                    payload["connection_id"], label="connection_id"
                ),
                provider_id=_require_text(payload["provider_id"], label="provider_id"),
                display_name=_require_text(
                    payload["display_name"], label="display_name"
                ),
                billing_class=_require_text(
                    payload["billing_class"], label="billing_class"
                ),
                status=_require_text(payload["status"], label="status"),
                connected=payload["connected"],
                created_at=payload.get("created_at"),
                last_validated_at=payload.get("last_validated_at"),
            )
        except KeyError as exc:
            raise ValueError(f"missing field: {exc.args[0]}") from None


@dataclass(frozen=True, slots=True)
class RouteCapabilitySnapshot:
    """One capability claim projected from a model route."""

    name: str
    supported: bool
    confidence: str

    def __post_init__(self) -> None:
        _require_text(self.name, label="name")
        if not isinstance(self.supported, bool):
            raise TypeError("supported must be a bool")
        _require_text(self.confidence, label="confidence")

    def to_dict(self) -> dict[str, object]:
        """Return a primitive-serializable mapping of this claim."""
        return {
            "name": self.name,
            "supported": self.supported,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> RouteCapabilitySnapshot:
        """Rebuild a claim from a ``to_dict()`` mapping."""
        if not isinstance(payload, dict):
            raise TypeError("payload must be a mapping")
        try:
            supported = payload["supported"]
            if not isinstance(supported, bool):
                raise TypeError("supported must be a bool")
            return cls(
                name=_require_text(payload["name"], label="name"),
                supported=supported,
                confidence=_require_text(payload["confidence"], label="confidence"),
            )
        except KeyError as exc:
            raise ValueError(f"missing field: {exc.args[0]}") from None


@dataclass(frozen=True, slots=True)
class ModelRouteSnapshot:
    """Public projection of one model route and its capability claims."""

    route_id: str
    connection_id: str
    provider_id: str
    provider_model_id: str
    canonical_model_id: str
    available: bool
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    capabilities: tuple[RouteCapabilitySnapshot, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.route_id, label="route_id")
        _require_text(self.connection_id, label="connection_id")
        _require_text(self.provider_id, label="provider_id")
        _require_text(self.provider_model_id, label="provider_model_id")
        _require_text(self.canonical_model_id, label="canonical_model_id")
        if not isinstance(self.available, bool):
            raise TypeError("available must be a bool")
        if self.first_seen_at is not None:
            _optional_text(self.first_seen_at, label="first_seen_at")
        if self.last_seen_at is not None:
            _optional_text(self.last_seen_at, label="last_seen_at")
        caps = (
            (self.capabilities,)
            if isinstance(self.capabilities, dict)
            else tuple(self.capabilities)
        )
        for cap in caps:
            if not isinstance(cap, RouteCapabilitySnapshot):
                raise TypeError("capabilities must hold RouteCapabilitySnapshot")
        object.__setattr__(self, "capabilities", tuple(caps))

    def to_dict(self) -> dict[str, object]:
        """Return a primitive-serializable mapping of this snapshot."""
        return {
            "route_id": self.route_id,
            "connection_id": self.connection_id,
            "provider_id": self.provider_id,
            "provider_model_id": self.provider_model_id,
            "canonical_model_id": self.canonical_model_id,
            "available": self.available,
            "first_seen_at": self.first_seen_at,
            "last_seen_at": self.last_seen_at,
            "capabilities": [cap.to_dict() for cap in self.capabilities],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ModelRouteSnapshot:
        """Rebuild a snapshot from a ``to_dict()`` mapping."""
        if not isinstance(payload, dict):
            raise TypeError("payload must be a mapping")
        try:
            available = payload["available"]
            if not isinstance(available, bool):
                raise TypeError("available must be a bool")
            raw_caps = payload.get("capabilities", ())
            if not isinstance(raw_caps, (list, tuple)):
                raise TypeError("capabilities must be a list")
            first = payload.get("first_seen_at")
            last = payload.get("last_seen_at")
            return cls(
                route_id=_require_text(payload["route_id"], label="route_id"),
                connection_id=_require_text(
                    payload["connection_id"], label="connection_id"
                ),
                provider_id=_require_text(payload["provider_id"], label="provider_id"),
                provider_model_id=_require_text(
                    payload["provider_model_id"], label="provider_model_id"
                ),
                canonical_model_id=_require_text(
                    payload["canonical_model_id"],
                    label="canonical_model_id",
                ),
                available=available,
                first_seen_at=first,  # type: ignore[arg-type]
                last_seen_at=last,  # type: ignore[arg-type]
                capabilities=tuple(
                    RouteCapabilitySnapshot.from_dict(item) for item in raw_caps
                ),
            )
        except KeyError as exc:
            raise ValueError(f"missing field: {exc.args[0]}") from None


@dataclass(frozen=True, slots=True)
class ProviderInventorySnapshot:
    """Join of connection and route snapshots taken at one instant."""

    generated_at: str
    connections: tuple[ProviderConnectionSnapshot, ...] = ()
    routes: tuple[ModelRouteSnapshot, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.generated_at, label="generated_at")
        conns = tuple(self.connections)
        for conn in conns:
            if not isinstance(conn, ProviderConnectionSnapshot):
                raise TypeError("connections must hold ProviderConnectionSnapshot")
        object.__setattr__(self, "connections", tuple(conns))
        routes = tuple(self.routes)
        for route in routes:
            if not isinstance(route, ModelRouteSnapshot):
                raise TypeError("routes must hold ModelRouteSnapshot")
        object.__setattr__(self, "routes", tuple(routes))

    def to_dict(self) -> dict[str, object]:
        """Return a primitive-serializable mapping of this inventory."""
        return {
            "generated_at": self.generated_at,
            "connections": [conn.to_dict() for conn in self.connections],
            "routes": [route.to_dict() for route in self.routes],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ProviderInventorySnapshot:
        """Rebuild an inventory from a ``to_dict()`` mapping."""
        if not isinstance(payload, dict):
            raise TypeError("payload must be a mapping")
        try:
            raw_conns = payload.get("connections", ())
            raw_routes = payload.get("routes", ())
            if not isinstance(raw_conns, (list, tuple)):
                raise TypeError("connections must be a list")
            if not isinstance(raw_routes, (list, tuple)):
                raise TypeError("routes must be a list")
            return cls(
                generated_at=_require_text(
                    payload["generated_at"], label="generated_at"
                ),
                connections=tuple(
                    ProviderConnectionSnapshot.from_dict(item) for item in raw_conns
                ),
                routes=tuple(ModelRouteSnapshot.from_dict(item) for item in raw_routes),
            )
        except KeyError as exc:
            raise ValueError(f"missing field: {exc.args[0]}") from None


def connection_snapshot_from_connection(
    connection: ProviderConnection,
) -> ProviderConnectionSnapshot:
    """Project an accepted connection; drop credential and path refs."""
    if not isinstance(connection, ProviderConnection):
        raise TypeError("connection must be a ProviderConnection")
    billing = connection.billing_class
    status = connection.status
    billing_value = billing.value if isinstance(billing, BillingClass) else str(billing)
    status_value = status.value if isinstance(status, ConnectionStatus) else str(status)
    return ProviderConnectionSnapshot(
        connection_id=connection.connection_id,
        provider_id=connection.provider_id,
        display_name=connection.display_name,
        billing_class=billing_value,
        status=status_value,
        connected=status == ConnectionStatus.CONNECTED,
        created_at=_isoformat(connection.created_at, label="created_at"),
        last_validated_at=_isoformat(
            connection.last_validated_at, label="last_validated_at"
        ),
    )


def connection_snapshot_from_proposal(
    proposal: ConnectionProposal,
) -> ProviderConnectionSnapshot:
    """Project a pre-acceptance proposal as a detected connection."""
    if not isinstance(proposal, ConnectionProposal):
        raise TypeError("proposal must be a ConnectionProposal")
    billing = proposal.billing_class
    billing_value = billing.value if isinstance(billing, BillingClass) else str(billing)
    return ProviderConnectionSnapshot(
        connection_id=f"{proposal.provider_id}:{proposal.account}",
        provider_id=proposal.provider_id,
        display_name=proposal.display_name,
        billing_class=billing_value,
        status=ConnectionStatus.DETECTED.value,
        connected=False,
        created_at=None,
        last_validated_at=None,
    )


def route_snapshot_from_route(
    route: ModelRoute, provider_id: str
) -> ModelRouteSnapshot:
    """Project a route; keep ids, availability, and capability claims."""
    if not isinstance(route, ModelRoute):
        raise TypeError("route must be a ModelRoute")
    resolved = _require_text(provider_id, label="provider_id").strip().lower()
    return ModelRouteSnapshot(
        route_id=route.route_id,
        connection_id=route.connection_id,
        provider_id=resolved,
        provider_model_id=route.provider_model_id,
        canonical_model_id=route.canonical_model_id,
        available=route.available,
        first_seen_at=_isoformat(route.first_seen_at, label="first_seen_at"),
        last_seen_at=_isoformat(route.last_seen_at, label="last_seen_at"),
        capabilities=tuple(
            RouteCapabilitySnapshot(
                name=cap.name,
                supported=cap.supported,
                confidence=cap.confidence.value
                if hasattr(cap.confidence, "value")
                else str(cap.confidence),
            )
            for cap in route.capabilities
        ),
    )


def build_inventory_snapshot(
    connections: Iterable[ProviderConnection],
    routes: Iterable[ModelRoute],
) -> ProviderInventorySnapshot:
    """Join connections and routes into one timestamped inventory."""
    items = tuple(connections)
    for item in items:
        if not isinstance(item, ProviderConnection):
            raise TypeError("connections must hold ProviderConnection")
    paths = tuple(routes)
    for path in paths:
        if not isinstance(path, ModelRoute):
            raise TypeError("routes must hold ModelRoute")
    providers = {conn.connection_id: conn.provider_id for conn in items}
    snapshots = tuple(connection_snapshot_from_connection(conn) for conn in items)
    route_snaps = tuple(
        route_snapshot_from_route(
            path,
            provider_id=providers.get(
                path.connection_id, path.connection_id.split(":")[0]
            ),
        )
        for path in paths
    )
    return ProviderInventorySnapshot(
        generated_at=datetime.now(timezone.utc).isoformat(),
        connections=snapshots,
        routes=route_snaps,
    )
