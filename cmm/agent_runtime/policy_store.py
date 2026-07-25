"""Phase 9.8 – Policy Repository and Store.

Provides decoupled in-memory persistence and lookup for Policies, PolicySets, and versioning.
"""

from __future__ import annotations

from .enums import PolicyScope
from .errors import (
    DuplicatePolicyError,
    DuplicatePolicySetError,
    PolicyNotFoundError,
    PolicySetNotFoundError,
)
from .policy_contracts import Policy, PolicySet, PolicyVersion


class PolicyRepository:
    """Thread-safe, decoupled in-memory repository for Policies and PolicySets."""

    def __init__(self) -> None:
        # Key: (policy_id, version) -> Policy
        self._policies: dict[tuple[str, int], Policy] = {}
        # Key: policy_set_id -> PolicySet
        self._policy_sets: dict[str, PolicySet] = {}
        # Key: policy_id -> list of PolicyVersion
        self._versions: dict[str, list[PolicyVersion]] = {}

    def add_policy(self, policy: Policy) -> Policy:
        """Add a Policy to the repository."""
        key = (policy.id, policy.version)
        if key in self._policies:
            raise DuplicatePolicyError(
                f"Policy with ID '{policy.id}' and version {policy.version} already registered."
            )

        self._policies[key] = policy

        vers = self._versions.setdefault(policy.id, [])
        vers.append(
            PolicyVersion(
                policy_id=policy.id,
                version=policy.version,
                created_at=policy.created_at,
                author_id=policy.actor_id,
                change_summary=policy.description,
            )
        )
        # Keep versions sorted
        vers.sort(key=lambda v: v.version)
        return policy

    def get_policy(self, policy_id: str, version: int | None = None) -> Policy | None:
        """Get a policy by ID and optional version. If version is None, return latest version."""
        p_id = policy_id.strip()
        if version is not None:
            return self._policies.get((p_id, version))

        # Find highest version for policy_id
        matching = [p for (pid, v), p in self._policies.items() if pid == p_id]
        if not matching:
            return None
        matching.sort(key=lambda p: p.version, reverse=True)
        return matching[0]

    def require_policy(self, policy_id: str, version: int | None = None) -> Policy:
        """Get a policy or raise PolicyNotFoundError."""
        policy = self.get_policy(policy_id, version)
        if policy is None:
            v_str = f" v{version}" if version else ""
            raise PolicyNotFoundError(
                f"Policy '{policy_id}'{v_str} not found in repository."
            )
        return policy

    def get_latest_policy_version(self, policy_id: str) -> int:
        """Return the latest version number for a given policy_id or raise PolicyNotFoundError."""
        p_id = policy_id.strip()
        matching_versions = [v for (pid, v) in self._policies if pid == p_id]
        if not matching_versions:
            raise PolicyNotFoundError(f"Policy '{policy_id}' not found in repository.")
        return max(matching_versions)

    def list_policies(
        self,
        scope: PolicyScope | str | None = None,
        enabled_only: bool = True,
        latest_only: bool = True,
    ) -> list[Policy]:
        """List policies matching filters."""
        scope_str = scope.value if isinstance(scope, PolicyScope) else scope

        # Group by policy_id
        grouped: dict[str, list[Policy]] = {}
        for (pid, _), policy in self._policies.items():
            grouped.setdefault(pid, []).append(policy)

        result: list[Policy] = []
        for pid, pols in grouped.items():
            pols_sorted = sorted(pols, key=lambda p: p.version, reverse=True)
            candidates = [pols_sorted[0]] if latest_only else pols_sorted
            for pol in candidates:
                if enabled_only and not pol.enabled:
                    continue
                if scope_str and pol.scope.value != scope_str:
                    continue
                result.append(pol)

        result.sort(key=lambda p: (-p.priority, p.id, p.version))
        return result

    def disable_policy(self, policy_id: str, version: int | None = None) -> Policy:
        """Disable a policy (or all versions if version is None) and return the updated policy."""
        p_id = policy_id.strip()
        target = self.get_policy(p_id, version)
        if target is None:
            v_str = f" v{version}" if version else ""
            raise PolicyNotFoundError(
                f"Policy '{policy_id}'{v_str} not found in repository."
            )

        if version is not None:
            updated = Policy(
                id=target.id,
                name=target.name,
                description=target.description,
                version=target.version,
                enabled=False,
                priority=target.priority,
                scope=target.scope,
                effect=target.effect,
                target=target.target,
                rules=target.rules,
                obligations=target.obligations,
                restrictions=target.restrictions,
                failure_mode=target.failure_mode,
                valid_from=target.valid_from,
                valid_until=target.valid_until,
                actor_id=target.actor_id,
                created_at=target.created_at,
                metadata=target.metadata,
            )
            self._policies[(p_id, target.version)] = updated
            return updated
        else:
            # Disable all versions for this policy_id
            last_updated = target
            for (pid, v), pol in list(self._policies.items()):
                if pid == p_id:
                    upd = Policy(
                        id=pol.id,
                        name=pol.name,
                        description=pol.description,
                        version=pol.version,
                        enabled=False,
                        priority=pol.priority,
                        scope=pol.scope,
                        effect=pol.effect,
                        target=pol.target,
                        rules=pol.rules,
                        obligations=pol.obligations,
                        restrictions=pol.restrictions,
                        failure_mode=pol.failure_mode,
                        valid_from=pol.valid_from,
                        valid_until=pol.valid_until,
                        actor_id=pol.actor_id,
                        created_at=pol.created_at,
                        metadata=pol.metadata,
                    )
                    self._policies[(pid, v)] = upd
                    if v == target.version:
                        last_updated = upd
            return last_updated

    def add_policy_set(self, policy_set: PolicySet) -> PolicySet:
        """Add a PolicySet to the repository."""
        if policy_set.id in self._policy_sets:
            raise DuplicatePolicySetError(
                f"PolicySet with ID '{policy_set.id}' already registered."
            )
        self._policy_sets[policy_set.id] = policy_set
        return policy_set

    def get_policy_set(self, policy_set_id: str) -> PolicySet | None:
        """Get a PolicySet by ID."""
        return self._policy_sets.get(policy_set_id.strip())

    def require_policy_set(self, policy_set_id: str) -> PolicySet:
        """Get a PolicySet or raise PolicySetNotFoundError."""
        ps = self.get_policy_set(policy_set_id)
        if ps is None:
            raise PolicySetNotFoundError(
                f"PolicySet '{policy_set_id}' not found in repository."
            )
        return ps

    def list_policy_sets(
        self, scope: PolicyScope | str | None = None, enabled_only: bool = True
    ) -> list[PolicySet]:
        """List PolicySets matching filters."""
        scope_str = scope.value if isinstance(scope, PolicyScope) else scope
        result: list[PolicySet] = []
        for ps in self._policy_sets.values():
            if enabled_only and not ps.enabled:
                continue
            if scope_str and ps.scope.value != scope_str:
                continue
            result.append(ps)
        result.sort(key=lambda ps: (-ps.priority, ps.id))
        return result

    def clear(self) -> None:
        """Clear all policies, policy sets, and version history."""
        self._policies.clear()
        self._policy_sets.clear()
        self._versions.clear()
