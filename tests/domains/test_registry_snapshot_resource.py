"""Tests for InMemoryDomainResourceRegistry snapshot/restore support."""

from __future__ import annotations

import pytest

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.errors import DomainResourceRegistryError
from cmm.domains.resource_contracts import (
    DomainResourceDefinition,
    DomainResourceTemporalPolicy,
)
from cmm.domains.resource_registry import InMemoryDomainResourceRegistry


def _resource(resource_id: str, kind: str, domain: str) -> DomainResourceDefinition:
    return DomainResourceDefinition(
        id=resource_id,
        kind=kind,
        domain_id=domain,
        adapter="cognitive.test",
        entity_types=(kind,),
        default_sensitivity=SensitivityLevel.INTERNAL,
        default_reliability=0.5,
        temporal_policy=DomainResourceTemporalPolicy(
            effective_date_required=False,
            expiration_required=False,
            historical_allowed=True,
        ),
        metadata={},
    )


def test_snapshot_state_exists():
    """RED: snapshot_state() must exist."""
    registry = InMemoryDomainResourceRegistry()
    assert hasattr(registry, "snapshot_state")


def test_restore_state_exists():
    """RED: restore_state() must exist."""
    registry = InMemoryDomainResourceRegistry()
    assert hasattr(registry, "restore_state")


def test_round_trip_restores_exact_state():
    """Snapshot → mutate → restore → snapshot equals initial."""
    registry = InMemoryDomainResourceRegistry()
    registry.register(_resource("r1", "kind1", "domain:test1"))
    registry.register(_resource("r2", "kind2", "domain:test1"))

    before = registry.snapshot_state()

    registry.register(_resource("r3", "kind3", "domain:test2"))

    after_mutation = registry.snapshot_state()
    assert len(after_mutation.definitions) == 3

    registry.restore_state(before)
    after_restore = registry.snapshot_state()

    assert after_restore.definitions == before.definitions
    assert len(after_restore.definitions) == 2


def test_preexisting_entries_preserved():
    """Restore preserves pre-existing entries."""
    registry = InMemoryDomainResourceRegistry()
    registry.register(_resource("r1", "kind1", "domain:test1"))

    before = registry.snapshot_state()

    registry.register(_resource("r2", "kind2", "domain:test2"))

    registry.restore_state(before)

    assert registry.get("r1") is not None
    assert registry.get("r2") is None


def test_empty_registry_round_trip():
    """Empty registry snapshot/restore works."""
    registry = InMemoryDomainResourceRegistry()
    before = registry.snapshot_state()
    registry.restore_state(before)
    after = registry.snapshot_state()
    assert after.definitions == before.definitions
    assert after.definitions == ()


def test_deterministic_order():
    """Snapshot definitions are in deterministic order."""
    registry = InMemoryDomainResourceRegistry()
    registry.register(_resource("b", "kind_b", "domain:b"))
    registry.register(_resource("a", "kind_a", "domain:a"))

    snap = registry.snapshot_state()
    ids = [d.id for d in snap.definitions]
    assert ids == sorted(ids)


def test_snapshot_deeply_immutable():
    """Snapshot is deeply immutable."""
    registry = InMemoryDomainResourceRegistry()
    registry.register(_resource("r1", "kind1", "domain:test1"))
    snap = registry.snapshot_state()

    with pytest.raises(AttributeError):
        snap.definitions[0].id = "changed"  # type: ignore[misc]


def test_wrong_type_rejected():
    """restore_state rejects wrong types."""
    registry = InMemoryDomainResourceRegistry()
    with pytest.raises(DomainResourceRegistryError):
        registry.restore_state("not a snapshot")  # type: ignore[arg-type]


def test_invalid_snapshot_does_not_mutate():
    """Invalid snapshot does not modify the registry."""
    registry = InMemoryDomainResourceRegistry()
    registry.register(_resource("r1", "kind1", "domain:test1"))
    before = registry.snapshot_state()

    with pytest.raises(DomainResourceRegistryError):
        registry.restore_state(object())  # type: ignore[arg-type]

    after = registry.snapshot_state()
    assert after.definitions == before.definitions


def test_double_restore_idempotent():
    """Two consecutive restores are idempotent."""
    registry = InMemoryDomainResourceRegistry()
    registry.register(_resource("r1", "kind1", "domain:test1"))
    before = registry.snapshot_state()

    registry.register(_resource("r2", "kind2", "domain:test2"))
    registry.restore_state(before)
    registry.restore_state(before)

    after = registry.snapshot_state()
    assert after.definitions == before.definitions


def test_duplicate_definition_ids_rejected():
    """A well-typed snapshot with duplicate definition ids is rejected without mutation."""
    from cmm.domains.resource_registry import DomainResourceRegistrySnapshot

    registry = InMemoryDomainResourceRegistry()
    registry.register(_resource("r1", "kind1", "domain:test1"))
    before = registry.snapshot_state()

    duplicate = DomainResourceRegistrySnapshot(
        definitions=(
            _resource("r1", "kind1", "domain:test1"),
            _resource("r1", "kind2", "domain:test1"),
        ),
    )
    with pytest.raises(DomainResourceRegistryError):
        registry.restore_state(duplicate)

    after = registry.snapshot_state()
    assert after.definitions == before.definitions