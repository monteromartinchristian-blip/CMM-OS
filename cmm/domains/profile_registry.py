"""Phase 10.11 – Domain Profile Registry.

In-memory registry for ``DomainProfileDefinition`` records. No persistence,
no adapter loading, no filesystem or network access, no profile execution.
Registered definitions are returned as immutable tuples in deterministic
order. Exactly one active base profile is permitted per domain.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from cmm.domains.errors import DomainProfileRegistryError
from cmm.domains.identifiers import DomainId
from cmm.domains.profile_contracts import DomainProfileDefinition

INITIAL_DOMAIN_PROFILE_NAMES: tuple[str, ...] = (
    "GeneralProfile",
    "HealthProfile",
    "RelationshipProfile",
    "UniversityProfile",
    "OppositionProfile",
    "ReflectionProfile",
    "ConcernProfile",
    "LanguageProfile",
    "NilProfile",
    "SportProfile",
    "LifePlanProfile",
    "ProjectProfile",
)


@runtime_checkable
class DomainProfileRegistry(Protocol):
    """Protocol for a Domain Profile definition registry."""

    def register(self, profile: DomainProfileDefinition) -> DomainProfileDefinition: ...

    def get(self, profile_id: str) -> DomainProfileDefinition | None: ...

    def get_by_domain(self, domain_id: DomainId) -> DomainProfileDefinition | None: ...

    def list_all(self) -> tuple[DomainProfileDefinition, ...]: ...


class InMemoryDomainProfileRegistry:
    """Deterministic in-memory ``DomainProfileRegistry`` implementation."""

    def __init__(self) -> None:
        self._profiles: dict[str, DomainProfileDefinition] = {}
        self._by_domain: dict[DomainId, str] = {}

    def register(self, profile: DomainProfileDefinition) -> DomainProfileDefinition:
        if not isinstance(profile, DomainProfileDefinition):
            raise DomainProfileRegistryError(
                "profile must be a DomainProfileDefinition",
                field="profile",
            )
        if profile.id in self._profiles:
            raise DomainProfileRegistryError(
                f"duplicate profile id: {profile.id!r}",
                field="id",
                details={"id": profile.id},
            )
        if profile.domain_id in self._by_domain:
            raise DomainProfileRegistryError(
                f"domain already has an active base profile: {profile.domain_id.slug!r}",
                field="domain_id",
                details={"domain_id": profile.domain_id.slug},
            )
        self._profiles[profile.id] = profile
        self._by_domain[profile.domain_id] = profile.id
        return profile

    def get(self, profile_id: str) -> DomainProfileDefinition | None:
        return self._profiles.get(profile_id)

    def get_by_domain(self, domain_id: DomainId) -> DomainProfileDefinition | None:
        profile_id = self._by_domain.get(domain_id)
        if profile_id is None:
            return None
        return self._profiles.get(profile_id)

    def list_all(self) -> tuple[DomainProfileDefinition, ...]:
        matches = list(self._profiles.values())
        matches.sort(key=lambda p: (p.domain_id.slug, p.id))
        return tuple(matches)


__all__ = [
    "INITIAL_DOMAIN_PROFILE_NAMES",
    "DomainProfileRegistry",
    "InMemoryDomainProfileRegistry",
]
