"""Tests for DomainPermissionRegistry snapshot/restore support."""

from __future__ import annotations

import pytest

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.errors import DomainPermissionRegistryError
from cmm.domains.permission_contracts import (
    DomainAutonomyLimits,
    DomainPermissionPolicy,
)
from cmm.domains.permission_registry import DomainPermissionRegistry


def _policy(policy_id: str, domain_id: str, version: str = "1.0.0") -> DomainPermissionPolicy:
    return DomainPermissionPolicy(
        policy_id=policy_id,
        domain_id=domain_id,
        version=version,
        allowed_capabilities=(PermissionCapability.RESOURCE_READ,),
        prohibited_capabilities=(),
        allowed_resource_kinds=(),
        allow_memory_read=True,
        autonomy_limits=DomainAutonomyLimits(maximum_autonomy_level=1),
        enabled=True,
        metadata={},
    )


def test_snapshot_state_exists():
    """RED: snapshot_state() must exist."""
    registry = DomainPermissionRegistry()
    assert hasattr(registry, "snapshot_state")


def test_restore_state_exists():
    """RED: restore_state() must exist."""
    registry = DomainPermissionRegistry()
    assert hasattr(registry, "restore_state")


def test_round_trip_restores_exact_state():
    """Snapshot → mutate → restore → snapshot equals initial."""
    registry = DomainPermissionRegistry()
    registry.register(_policy("p1", "domain:test1"))
    registry.register(_policy("p2", "domain:test2"))

    before = registry.snapshot_state()

    registry.register(_policy("p3", "domain:test3"))

    after_mutation = registry.snapshot_state()
    assert len(after_mutation.policies) == 3

    registry.restore_state(before)
    after_restore = registry.snapshot_state()

    assert after_restore.policies == before.policies
    assert len(after_restore.policies) == 2


def test_preexisting_entries_preserved():
    """Restore preserves pre-existing entries."""
    registry = DomainPermissionRegistry()
    registry.register(_policy("p1", "domain:test1"))

    before = registry.snapshot_state()

    registry.register(_policy("p2", "domain:test2"))

    registry.restore_state(before)

    assert registry.get("p1") is not None
    with pytest.raises(DomainPermissionRegistryError):
        registry.get("p2")


def test_empty_registry_round_trip():
    """Empty registry snapshot/restore works."""
    registry = DomainPermissionRegistry()
    before = registry.snapshot_state()
    registry.restore_state(before)
    after = registry.snapshot_state()
    assert after.policies == before.policies
    assert after.policies == ()


def test_multiple_versions_restored():
    """Multiple versions of the same policy are restored."""
    registry = DomainPermissionRegistry()
    registry.register(_policy("p1", "domain:test1", "1.0.0"))
    registry.register(_policy("p1", "domain:test1", "2.0.0"))

    before = registry.snapshot_state()
    assert len(before.policies) == 2

    registry.register(_policy("p2", "domain:test2", "1.0.0"))
    registry.restore_state(before)

    assert registry.get("p1", "1.0.0") is not None
    assert registry.get("p1", "2.0.0") is not None
    with pytest.raises(DomainPermissionRegistryError):
        registry.get("p2", "1.0.0")


def test_deterministic_order():
    """Snapshot policies are in deterministic order."""
    registry = DomainPermissionRegistry()
    registry.register(_policy("b", "domain:b"))
    registry.register(_policy("a", "domain:a"))

    snap = registry.snapshot_state()
    ids = [p.policy_id for p in snap.policies]
    assert ids == sorted(ids)


def test_snapshot_deeply_immutable():
    """Snapshot is deeply immutable."""
    registry = DomainPermissionRegistry()
    registry.register(_policy("p1", "domain:test1"))
    snap = registry.snapshot_state()

    with pytest.raises(AttributeError):
        snap.policies[0].policy_id = "changed"  # type: ignore[misc]


def test_wrong_type_rejected():
    """restore_state rejects wrong types."""
    registry = DomainPermissionRegistry()
    with pytest.raises(DomainPermissionRegistryError):
        registry.restore_state("not a snapshot")  # type: ignore[arg-type]


def test_invalid_snapshot_does_not_mutate():
    """Invalid snapshot does not modify the registry."""
    registry = DomainPermissionRegistry()
    registry.register(_policy("p1", "domain:test1"))
    before = registry.snapshot_state()

    with pytest.raises(DomainPermissionRegistryError):
        registry.restore_state(object())  # type: ignore[arg-type]

    after = registry.snapshot_state()
    assert after.policies == before.policies


def test_double_restore_idempotent():
    """Two consecutive restores are idempotent."""
    registry = DomainPermissionRegistry()
    registry.register(_policy("p1", "domain:test1"))
    before = registry.snapshot_state()

    registry.register(_policy("p2", "domain:test2"))
    registry.restore_state(before)
    registry.restore_state(before)

    after = registry.snapshot_state()
    assert after.policies == before.policies


def test_duplicate_policy_id_version_rejected():
    """A well-typed snapshot with duplicate (policy_id, version) keys is rejected without mutation."""
    from cmm.domains.permission_registry import DomainPermissionRegistrySnapshot

    registry = DomainPermissionRegistry()
    registry.register(_policy("p1", "domain:test1"))
    before = registry.snapshot_state()

    duplicate = DomainPermissionRegistrySnapshot(
        policies=(
            _policy("p1", "domain:test1"),
            _policy("p1", "domain:test1"),
        ),
    )
    with pytest.raises(DomainPermissionRegistryError):
        registry.restore_state(duplicate)

    after = registry.snapshot_state()
    assert after.policies == before.policies