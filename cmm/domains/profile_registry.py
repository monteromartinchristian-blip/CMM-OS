"""Phase 10.11 – Domain Profile Registry.

In-memory registry for ``DomainProfileDefinition`` records. No persistence,
no adapter loading, no filesystem or network access, no profile execution.
Registered definitions are returned as immutable tuples in deterministic
order. Exactly one active base profile is permitted per domain.
"""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class DomainProfileRegistrySnapshot:
    """Immutable snapshot of the profile registry state.

    ``profiles`` is the canonical ordered tuple of registered profiles.
    ``by_domain`` is the ordered tuple of ``(domain_id, profile_id)`` pairs
    that reconstructs the secondary domain→profile index.
    """

    profiles: tuple[DomainProfileDefinition, ...]
    by_domain: tuple[tuple[DomainId, str], ...]


@runtime_checkable
class DomainProfileRegistry(Protocol):
    """Protocol for a Domain Profile definition registry."""

    def register(self, profile: DomainProfileDefinition) -> DomainProfileDefinition: ...

    def get(self, profile_id: str) -> DomainProfileDefinition | None: ...

    def get_by_domain(self, domain_id: DomainId) -> DomainProfileDefinition | None: ...

    def list_all(self) -> tuple[DomainProfileDefinition, ...]: ...

    def snapshot_state(self) -> DomainProfileRegistrySnapshot: ...

    def restore_state(self, snapshot: DomainProfileRegistrySnapshot) -> None: ...


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

    # ── Snapshot / restore ───────────────────────────────────────────────────

    def snapshot_state(self) -> DomainProfileRegistrySnapshot:
        """Capture the full registry state for transactional rollback."""
        profiles = tuple(
            sorted(self._profiles.values(), key=lambda p: (p.domain_id.slug, p.id))
        )
        by_domain = tuple(
            sorted(
                ((domain_id, profile_id) for domain_id, profile_id in self._by_domain.items()),
                key=lambda item: (item[0].slug, item[1]),
            )
        )
        return DomainProfileRegistrySnapshot(profiles=profiles, by_domain=by_domain)

    def restore_state(self, snapshot: DomainProfileRegistrySnapshot) -> None:
        """Restore the full registry state from a snapshot.

        Validates the snapshot completely before mutating.  Rejects wrong
        types and invalid snapshots without modifying the registry.
        """
        if not isinstance(snapshot, DomainProfileRegistrySnapshot):
            raise DomainProfileRegistryError(
                "snapshot must be a DomainProfileRegistrySnapshot",
                field="snapshot",
            )
        if not isinstance(snapshot.profiles, tuple):
            raise DomainProfileRegistryError(
                "snapshot.profiles must be a tuple",
                field="snapshot.profiles",
            )
        if not isinstance(snapshot.by_domain, tuple):
            raise DomainProfileRegistryError(
                "snapshot.by_domain must be a tuple",
                field="snapshot.by_domain",
            )
        for profile in snapshot.profiles:
            if not isinstance(profile, DomainProfileDefinition):
                raise DomainProfileRegistryError(
                    "snapshot.profiles contains a non-DomainProfileDefinition",
                    field="snapshot.profiles",
                )
        for item in snapshot.by_domain:
            if not isinstance(item, tuple) or len(item) != 2:
                raise DomainProfileRegistryError(
                    "snapshot.by_domain entries must be (DomainId, str) pairs",
                    field="snapshot.by_domain",
                )
            domain_id, profile_id = item
            if not isinstance(domain_id, DomainId) or not isinstance(profile_id, str):
                raise DomainProfileRegistryError(
                    "snapshot.by_domain entries must be (DomainId, str) pairs",
                    field="snapshot.by_domain",
                )

        # Validate consistency before mutating
        profile_ids = [p.id for p in snapshot.profiles]
        if len(profile_ids) != len(set(profile_ids)):
            raise DomainProfileRegistryError(
                "snapshot.profiles contains duplicate profile ids",
                field="snapshot.profiles",
            )

        profile_id_set = set(profile_ids)
        seen_domains: set[str] = set()
        seen_profile_ids: set[str] = set()
        for domain_id, profile_id in snapshot.by_domain:
            if profile_id not in profile_id_set:
                raise DomainProfileRegistryError(
                    "snapshot.by_domain references a missing profile",
                    field="snapshot.by_domain",
                    details={"profile_id": profile_id},
                )
            domain_slug = domain_id.slug
            if domain_slug in seen_domains:
                raise DomainProfileRegistryError(
                    "snapshot.by_domain contains duplicate domain mappings",
                    field="snapshot.by_domain",
                    details={"domain_id": domain_slug},
                )
            if profile_id in seen_profile_ids:
                raise DomainProfileRegistryError(
                    "snapshot.by_domain maps the same profile to multiple domains",
                    field="snapshot.by_domain",
                    details={"profile_id": profile_id},
                )
            seen_domains.add(domain_slug)
            seen_profile_ids.add(profile_id)

        # One-to-one correspondence: every profile must be mapped exactly once
        if len(snapshot.by_domain) != len(profile_ids):
            raise DomainProfileRegistryError(
                "snapshot.by_domain must map every profile exactly once",
                field="snapshot.by_domain",
            )

        # Semantic invariant: every by_domain mapping must point to a profile
        # whose own domain_id is exactly the mapped domain.  Otherwise the
        # domain->profile index would resolve a profile that claims a different
        # domain.
        profiles_by_id = {p.id: p for p in snapshot.profiles}
        for domain_id, profile_id in snapshot.by_domain:
            profile = profiles_by_id[profile_id]
            if profile.domain_id != domain_id:
                raise DomainProfileRegistryError(
                    "snapshot.by_domain maps a profile to a domain that is not "
                    "its own",
                    field="snapshot.by_domain",
                    details={
                        "profile_id": profile_id,
                        "domain_id": domain_id.slug,
                        "profile_domain_id": profile.domain_id.slug,
                    },
                )

        # All validation passed — mutate
        self._profiles = {p.id: p for p in snapshot.profiles}
        self._by_domain = {domain_id: profile_id for domain_id, profile_id in snapshot.by_domain}


__all__ = [
    "INITIAL_DOMAIN_PROFILE_NAMES",
    "DomainProfileRegistry",
    "DomainProfileRegistrySnapshot",
    "InMemoryDomainProfileRegistry",
]