from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class CapabilityConfidence(str, Enum):
    DECLARED = "declared"
    DISCOVERED = "discovered"
    VERIFIED = "verified"
    UNKNOWN = "unknown"

@dataclass(frozen=True, slots=True)
class RouteCapabilityState:
    name: str
    supported: bool
    confidence: CapabilityConfidence

@dataclass(frozen=True, slots=True)
class ModelRoute:
    route_id: str
    connection_id: str
    provider_model_id: str
    canonical_model_id: str
    available: bool = True
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    capabilities: tuple[RouteCapabilityState, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "route_id", self.route_id.strip())
        object.__setattr__(self, "connection_id", self.connection_id.strip())
        object.__setattr__(self, "provider_model_id", self.provider_model_id.strip())
        object.__setattr__(self, "canonical_model_id", self.canonical_model_id.strip())

class ModelRouteCatalog:
    def __init__(self) -> None:
        self._routes: dict[str, ModelRoute] = {}

    def register(self, route: ModelRoute) -> ModelRoute:
        key = route.route_id
        if key in self._routes:
            raise ValueError(f"duplicate route_id: {key}")
        now = datetime.now(timezone.utc)
        self._routes[key] = ModelRoute(
            route_id=route.route_id,
            connection_id=route.connection_id,
            provider_model_id=route.provider_model_id,
            canonical_model_id=route.canonical_model_id,
            available=True,
            first_seen_at=route.first_seen_at or now,
            last_seen_at=now,
            capabilities=route.capabilities,
        )
        return self._routes[key]

    def get(self, route_id: str) -> ModelRoute | None:
        return self._routes.get(route_id)

    def mark_seen(self, route_id: str, *, at: datetime | None = None) -> ModelRoute:
        current = self._routes[route_id]
        now = at or datetime.now(timezone.utc)
        updated = _replace_route(
            current,
            last_seen_at=now,
            available=True,
        )
        self._routes[route_id] = updated
        return updated

    def mark_unavailable(self, route_id: str) -> ModelRoute:
        current = self._routes[route_id]
        updated = _replace_route(current, available=False)
        self._routes[route_id] = updated
        return updated

    def routes_for_canonical_model(
        self, canonical_model_id: str
    ) -> tuple[ModelRoute, ...]:
        return tuple(
            r for r in self._routes.values()
            if r.canonical_model_id == canonical_model_id
        )

    def filter_required_capabilities(
        self, required: tuple[str, ...]
    ) -> tuple[ModelRoute, ...]:
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

def _replace_route(
    route: ModelRoute,
    *,
    available: bool | None = None,
    first_seen_at: datetime | None = None,
    last_seen_at: datetime | None = None,
    capabilities: tuple[RouteCapabilityState, ...] | None = None,
) -> ModelRoute:
    return ModelRoute(
        route_id=route.route_id,
        connection_id=route.connection_id,
        provider_model_id=route.provider_model_id,
        canonical_model_id=route.canonical_model_id,
        available=available if available is not None else route.available,
        first_seen_at=first_seen_at if first_seen_at is not None else route.first_seen_at,
        last_seen_at=last_seen_at if last_seen_at is not None else route.last_seen_at,
        capabilities=capabilities if capabilities is not None else route.capabilities,
    )
