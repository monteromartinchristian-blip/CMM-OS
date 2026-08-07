"""Explicit, in-memory registry for domain permission policies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import RLock

from cmm.domains.errors import DomainPermissionRegistryError
from cmm.domains.permission_contracts import DomainPermissionPolicy
from cmm.domains.registry_contracts import parse_semver


@dataclass(frozen=True, slots=True)
class DomainPermissionRegistrySnapshot:
    """Immutable snapshot of the permission registry state.

    ``policies`` is the canonical ordered tuple of registered policies.
    """

    policies: tuple[DomainPermissionPolicy, ...]


class DomainPermissionRegistry:
    """Injectable registry; registration never evaluates or discovers policies."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._policies: dict[tuple[str, str], DomainPermissionPolicy] = {}

    def register(self, policy: DomainPermissionPolicy) -> None:
        if not isinstance(policy, DomainPermissionPolicy):
            raise DomainPermissionRegistryError("policy must be DomainPermissionPolicy")
        key = (policy.policy_id, policy.version)
        with self._lock:
            if key in self._policies:
                raise DomainPermissionRegistryError("policy id/version already registered")
            self._policies[key] = policy

    def get(self, policy_id: str, version: str | None = None) -> DomainPermissionPolicy:
        with self._lock:
            if version is not None:
                try:
                    return self._policies[(policy_id, version)]
                except KeyError as exc:
                    raise DomainPermissionRegistryError("permission policy not found") from exc
            matches = [p for (pid, _), p in self._policies.items() if pid == policy_id]
            if not matches:
                raise DomainPermissionRegistryError("permission policy not found")
            return max(matches, key=lambda p: parse_semver(p.version))

    def for_domain(self, domain_id: str) -> tuple[DomainPermissionPolicy, ...]:
        with self._lock:
            return tuple(sorted((p for p in self._policies.values() if p.domain_id == domain_id), key=lambda p: (p.domain_id, parse_semver(p.version))))

    def active_for_domain(
        self, domain_id: str, *, now: datetime | None = None
    ) -> DomainPermissionPolicy | None:
        if now is not None and now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        candidates = tuple(
            policy
            for policy in self.for_domain(domain_id)
            if policy.enabled and (policy.expires_at is None or (now is not None and now < policy.expires_at))
        )
        return max(candidates, key=lambda p: parse_semver(p.version), default=None)

    def list_policies(self) -> tuple[DomainPermissionPolicy, ...]:
        with self._lock:
            return tuple(sorted(self._policies.values(), key=lambda p: (p.domain_id, parse_semver(p.version), p.policy_id)))

    # ── Snapshot / restore ───────────────────────────────────────────────────

    def snapshot_state(self) -> DomainPermissionRegistrySnapshot:
        """Capture the full registry state for transactional rollback."""
        with self._lock:
            policies = tuple(
                sorted(
                    self._policies.values(),
                    key=lambda p: (p.domain_id, parse_semver(p.version), p.policy_id),
                )
            )
        return DomainPermissionRegistrySnapshot(policies=policies)

    def restore_state(self, snapshot: DomainPermissionRegistrySnapshot) -> None:
        """Restore the full registry state from a snapshot.

        Validates the snapshot completely before mutating.  Rejects wrong
        types and invalid snapshots without modifying the registry.
        """
        if not isinstance(snapshot, DomainPermissionRegistrySnapshot):
            raise DomainPermissionRegistryError(
                "snapshot must be a DomainPermissionRegistrySnapshot",
                field="snapshot",
            )
        if not isinstance(snapshot.policies, tuple):
            raise DomainPermissionRegistryError(
                "snapshot.policies must be a tuple",
                field="snapshot.policies",
            )
        for policy in snapshot.policies:
            if not isinstance(policy, DomainPermissionPolicy):
                raise DomainPermissionRegistryError(
                    "snapshot.policies contains a non-DomainPermissionPolicy",
                    field="snapshot.policies",
                )

        # Reject duplicate (policy_id, version) keys before reconstructing
        keys = [(p.policy_id, p.version) for p in snapshot.policies]
        if len(keys) != len(set(keys)):
            raise DomainPermissionRegistryError(
                "snapshot.policies contains duplicate (policy_id, version) keys",
                field="snapshot.policies",
            )

        # All validation passed — mutate
        with self._lock:
            self._policies = {
                (p.policy_id, p.version): p for p in snapshot.policies
            }


__all__ = [
    "DomainPermissionRegistry",
    "DomainPermissionRegistrySnapshot",
]
