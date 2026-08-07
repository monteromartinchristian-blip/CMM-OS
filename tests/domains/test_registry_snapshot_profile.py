"""Tests for InMemoryDomainProfileRegistry snapshot/restore support."""

from __future__ import annotations

import pytest

from cmm.domains.errors import DomainProfileRegistryError
from cmm.domains.identifiers import DomainId
from cmm.domains.profile_contracts import DomainProfileDefinition
from cmm.domains.profile_registry import (
    DomainProfileRegistrySnapshot,
    InMemoryDomainProfileRegistry,
)


def _profile(profile_id: str, domain_id: str) -> DomainProfileDefinition:
    return DomainProfileDefinition(
        id=profile_id,
        domain_id=domain_id,
        profile_name=profile_id,
        required_rules=(),
        optional_rules=(),
        prohibited_rules=(),
        allowed_resource_kinds=(),
        priority_resource_kinds=(),
        prohibited_resource_kinds=(),
        minimum_confidence=0.5,
        reasoning_depth="standard",
        allowed_inferences=(),
        prohibited_inferences=(),
        maximum_questions=5,
        escalation_rules=(),
        prohibited_actions=(),
        question_policy=None,
        presentation_policy=None,
        memory_policy=None,
        temporal_policy=None,
        production_policy=None,
        permissions=(),
        metadata={},
    )


def test_snapshot_state_exists():
    """RED: snapshot_state() must exist."""
    registry = InMemoryDomainProfileRegistry()
    assert hasattr(registry, "snapshot_state")


def test_restore_state_exists():
    """RED: restore_state() must exist."""
    registry = InMemoryDomainProfileRegistry()
    assert hasattr(registry, "restore_state")


def test_round_trip_restores_exact_state():
    """Snapshot → mutate → restore → snapshot equals initial."""
    registry = InMemoryDomainProfileRegistry()
    registry.register(_profile("p1", "domain:test1"))
    registry.register(_profile("p2", "domain:test2"))

    before = registry.snapshot_state()

    # Mutate
    registry.register(_profile("p3", "domain:test3"))

    after_mutation = registry.snapshot_state()
    assert len(after_mutation.profiles) == 3

    # Restore
    registry.restore_state(before)
    after_restore = registry.snapshot_state()

    assert after_restore.profiles == before.profiles
    assert len(after_restore.profiles) == 2


def test_preexisting_entries_preserved():
    """Restore preserves pre-existing entries."""
    registry = InMemoryDomainProfileRegistry()
    registry.register(_profile("p1", "domain:test1"))

    before = registry.snapshot_state()

    # Add more
    registry.register(_profile("p2", "domain:test2"))

    registry.restore_state(before)

    # p1 must still exist
    assert registry.get("p1") is not None
    assert registry.get("p2") is None


def test_empty_registry_round_trip():
    """Empty registry snapshot/restore works."""
    registry = InMemoryDomainProfileRegistry()
    before = registry.snapshot_state()
    registry.restore_state(before)
    after = registry.snapshot_state()
    assert after.profiles == before.profiles
    assert after.profiles == ()


def test_multiple_versions_restored():
    """Multiple versions of the same profile are restored."""
    registry = InMemoryDomainProfileRegistry()
    registry.register(_profile("p1", "domain:test1"))
    before = registry.snapshot_state()

    # Try to add a second profile for same domain (should fail)
    with pytest.raises(DomainProfileRegistryError):
        registry.register(_profile("p2", "domain:test1"))

    registry.restore_state(before)
    assert registry.get("p1") is not None


def test_deterministic_order():
    """Snapshot profiles are in deterministic order."""
    registry = InMemoryDomainProfileRegistry()
    registry.register(_profile("b", "domain:b"))
    registry.register(_profile("a", "domain:a"))

    snap = registry.snapshot_state()
    ids = [p.id for p in snap.profiles]
    assert ids == sorted(ids)


def test_snapshot_deeply_immutable():
    """Snapshot is deeply immutable."""
    registry = InMemoryDomainProfileRegistry()
    registry.register(_profile("p1", "domain:test1"))
    snap = registry.snapshot_state()

    with pytest.raises(AttributeError):
        snap.profiles[0].id = "changed"  # type: ignore[misc]


def test_wrong_type_rejected():
    """restore_state rejects wrong types."""
    registry = InMemoryDomainProfileRegistry()
    with pytest.raises(DomainProfileRegistryError):
        registry.restore_state("not a snapshot")  # type: ignore[arg-type]


def test_invalid_snapshot_does_not_mutate():
    """Invalid snapshot does not modify the registry."""
    registry = InMemoryDomainProfileRegistry()
    registry.register(_profile("p1", "domain:test1"))
    before = registry.snapshot_state()

    with pytest.raises(DomainProfileRegistryError):
        registry.restore_state(object())  # type: ignore[arg-type]

    after = registry.snapshot_state()
    assert after.profiles == before.profiles


def test_double_restore_idempotent():
    """Two consecutive restores are idempotent."""
    registry = InMemoryDomainProfileRegistry()
    registry.register(_profile("p1", "domain:test1"))
    before = registry.snapshot_state()

    registry.register(_profile("p2", "domain:test2"))
    registry.restore_state(before)
    registry.restore_state(before)

    after = registry.snapshot_state()
    assert after.profiles == before.profiles


def test_duplicate_profile_ids_rejected():
    """A well-typed snapshot with duplicate profile ids is rejected."""
    registry = InMemoryDomainProfileRegistry()
    registry.register(_profile("p1", "domain:test1"))
    before = registry.snapshot_state()

    duplicate = DomainProfileRegistrySnapshot(
        profiles=(_profile("p1", "domain:test1"), _profile("p1", "domain:test2")),
        by_domain=(
            (DomainId(slug="test1"), "p1"),
            (DomainId(slug="test2"), "p1"),
        ),
    )
    with pytest.raises(DomainProfileRegistryError):
        registry.restore_state(duplicate)

    after = registry.snapshot_state()
    assert after.profiles == before.profiles


def test_by_domain_missing_profile_rejected():
    """A well-typed snapshot with a by_domain entry referencing a missing profile is rejected."""
    registry = InMemoryDomainProfileRegistry()
    registry.register(_profile("p1", "domain:test1"))
    before = registry.snapshot_state()

    invalid = DomainProfileRegistrySnapshot(
        profiles=(_profile("p1", "domain:test1"),),
        by_domain=((DomainId(slug="test1"), "missing"),),
    )
    with pytest.raises(DomainProfileRegistryError):
        registry.restore_state(invalid)

    after = registry.snapshot_state()
    assert after.profiles == before.profiles


def test_by_domain_not_one_to_one_rejected():
    """A well-typed snapshot where by_domain does not map every profile is rejected."""
    registry = InMemoryDomainProfileRegistry()
    registry.register(_profile("p1", "domain:test1"))
    before = registry.snapshot_state()

    # Two profiles but only one by_domain mapping
    invalid = DomainProfileRegistrySnapshot(
        profiles=(
            _profile("p1", "domain:test1"),
            _profile("p2", "domain:test2"),
        ),
        by_domain=((DomainId(slug="test1"), "p1"),),
    )
    with pytest.raises(DomainProfileRegistryError):
        registry.restore_state(invalid)

    after = registry.snapshot_state()
    assert after.profiles == before.profiles
    after = registry.snapshot_state()
    assert after.profiles == before.profiles


# ── Audit v2 P1 — cross-layer domain↔profile consistency ──────────────────────
# The snapshot is structurally valid (unique domains, unique profile ids, every
# profile mapped exactly once) but the by_domain index must agree with each
# profile's own domain_id.  restore_state must reject a mismatch BEFORE mutating.


def test_cross_mapped_profile_domains_rejected_without_mutation():
    """by_domain pointing a profile at a mismatched domain is rejected."""
    registry = InMemoryDomainProfileRegistry()
    p1 = _profile("p1", "domain:test1")
    p2 = _profile("p2", "domain:test2")
    registry.register(p1)
    registry.register(p2)
    before = registry.snapshot_state()

    # Structural validations all pass: two unique domains, two unique profile
    # ids, every profile id exists, one-to-one cardinality.  But the mapping is
    # crossed: each profile is routed to a domain that is not its own.
    crossed = DomainProfileRegistrySnapshot(
        profiles=(p1, p2),
        by_domain=(
            (DomainId(slug="test1"), p2.id),
            (DomainId(slug="test2"), p1.id),
        ),
    )
    with pytest.raises(DomainProfileRegistryError):
        registry.restore_state(crossed)

    # No mutation: both the profile store and the domain index are unchanged.
    after = registry.snapshot_state()
    assert after.profiles == before.profiles
    assert after.by_domain == before.by_domain


def test_profile_snapshot_exact_domain_mapping_restores_successfully():
    """A snapshot whose by_domain exactly matches each profile restores fine."""
    registry = InMemoryDomainProfileRegistry()
    p1 = _profile("p1", "domain:test1")
    p2 = _profile("p2", "domain:test2")
    registry.register(p1)
    registry.register(p2)
    valid = DomainProfileRegistrySnapshot(
        profiles=(p1, p2),
        by_domain=(
            (DomainId(slug="test1"), p1.id),
            (DomainId(slug="test2"), p2.id),
        ),
    )
    registry.restore_state(valid)

    assert registry.get_by_domain(DomainId(slug="test1")) == p1
    assert registry.get_by_domain(DomainId(slug="test2")) == p2
