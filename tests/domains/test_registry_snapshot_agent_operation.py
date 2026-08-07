"""Tests for InMemoryAgentOperationRegistry snapshot/restore support."""

from __future__ import annotations

import pytest

from cmm.agent_runtime.operation_execution_contracts import OperationDescriptor
from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry


def _descriptor(name: str, version: str = "1.0.0") -> OperationDescriptor:
    return OperationDescriptor(
        name=name,
        version=version,
        description=f"test {name}",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        enabled=True,
        metadata={},
    )


def test_snapshot_state_exists():
    """RED: snapshot_state() must exist."""
    registry = InMemoryAgentOperationRegistry()
    assert hasattr(registry, "snapshot_state")


def test_restore_state_exists():
    """RED: restore_state() must exist."""
    registry = InMemoryAgentOperationRegistry()
    assert hasattr(registry, "restore_state")


def test_round_trip_restores_exact_state():
    """Snapshot → mutate → restore → snapshot equals initial."""
    registry = InMemoryAgentOperationRegistry()
    registry.register(_descriptor("op1"))
    registry.register(_descriptor("op2"))

    before = registry.snapshot_state()

    registry.register(_descriptor("op3"))

    after_mutation = registry.snapshot_state()
    assert len(after_mutation.descriptors) == 3

    registry.restore_state(before)
    after_restore = registry.snapshot_state()

    assert after_restore.descriptors == before.descriptors
    assert len(after_restore.descriptors) == 2


def test_preexisting_entries_preserved():
    """Restore preserves pre-existing entries."""
    registry = InMemoryAgentOperationRegistry()
    registry.register(_descriptor("op1"))

    before = registry.snapshot_state()

    registry.register(_descriptor("op2"))

    registry.restore_state(before)

    assert registry.contains("op1", "1.0.0")
    assert not registry.contains("op2", "1.0.0")


def test_empty_registry_round_trip():
    """Empty registry snapshot/restore works."""
    registry = InMemoryAgentOperationRegistry()
    before = registry.snapshot_state()
    registry.restore_state(before)
    after = registry.snapshot_state()
    assert after.descriptors == before.descriptors
    assert after.descriptors == ()


def test_multiple_versions_restored():
    """Multiple versions of the same operation are restored."""
    registry = InMemoryAgentOperationRegistry()
    registry.register(_descriptor("op1", "1.0.0"))
    registry.register(_descriptor("op1", "2.0.0"))

    before = registry.snapshot_state()
    assert len(before.descriptors) == 2

    registry.register(_descriptor("op2", "1.0.0"))
    registry.restore_state(before)

    assert registry.contains("op1", "1.0.0")
    assert registry.contains("op1", "2.0.0")
    assert not registry.contains("op2", "1.0.0")


def test_deterministic_order():
    """Snapshot descriptors preserve registration order."""
    registry = InMemoryAgentOperationRegistry()
    registry.register(_descriptor("b"))
    registry.register(_descriptor("a"))

    snap = registry.snapshot_state()
    names = [d.name for d in snap.descriptors]
    assert names == ["b", "a"]


def test_snapshot_deeply_immutable():
    """Snapshot is deeply immutable."""
    registry = InMemoryAgentOperationRegistry()
    registry.register(_descriptor("op1"))
    snap = registry.snapshot_state()

    with pytest.raises(AttributeError):
        snap.descriptors[0].name = "changed"  # type: ignore[misc]


def test_wrong_type_rejected():
    """restore_state rejects wrong types."""
    registry = InMemoryAgentOperationRegistry()
    with pytest.raises(TypeError):
        registry.restore_state("not a snapshot")  # type: ignore[arg-type]


def test_invalid_snapshot_does_not_mutate():
    """Invalid snapshot does not modify the registry."""
    registry = InMemoryAgentOperationRegistry()
    registry.register(_descriptor("op1"))
    before = registry.snapshot_state()

    with pytest.raises(TypeError):
        registry.restore_state(object())  # type: ignore[arg-type]

    after = registry.snapshot_state()
    assert after.descriptors == before.descriptors


def test_double_restore_idempotent():
    """Two consecutive restores are idempotent."""
    registry = InMemoryAgentOperationRegistry()
    registry.register(_descriptor("op1"))
    before = registry.snapshot_state()

    registry.register(_descriptor("op2"))
    registry.restore_state(before)
    registry.restore_state(before)

    after = registry.snapshot_state()
    assert after.descriptors == before.descriptors


def test_duplicate_descriptors_rejected():
    """A well-typed snapshot with duplicate descriptors is rejected."""
    from cmm.agent_runtime.operation_registry import AgentOperationRegistrySnapshot

    registry = InMemoryAgentOperationRegistry()
    op1 = _descriptor("op1")
    registry.register(op1)
    before = registry.snapshot_state()

    duplicate = AgentOperationRegistrySnapshot(
        descriptors=(op1, op1),
        order=(("op1", "1.0.0"), ("op1", "1.0.0")),
    )
    with pytest.raises(TypeError):
        registry.restore_state(duplicate)

    after = registry.snapshot_state()
    assert after.descriptors == before.descriptors


def test_order_missing_descriptor_rejected():
    """A well-typed snapshot with order referencing a missing descriptor is rejected."""
    from cmm.agent_runtime.operation_registry import AgentOperationRegistrySnapshot

    registry = InMemoryAgentOperationRegistry()
    op1 = _descriptor("op1")
    registry.register(op1)
    before = registry.snapshot_state()

    invalid = AgentOperationRegistrySnapshot(
        descriptors=(op1,),
        order=(("op1", "1.0.0"), ("op2", "1.0.0")),
    )
    with pytest.raises(TypeError):
        registry.restore_state(invalid)

    after = registry.snapshot_state()
    assert after.descriptors == before.descriptors


def test_order_count_mismatch_rejected():
    """A well-typed snapshot where order count does not match descriptors is rejected."""
    from cmm.agent_runtime.operation_registry import AgentOperationRegistrySnapshot

    registry = InMemoryAgentOperationRegistry()
    op1 = _descriptor("op1")
    registry.register(op1)
    before = registry.snapshot_state()

    invalid = AgentOperationRegistrySnapshot(
        descriptors=(op1,),
        order=(("op1", "1.0.0"), ("op1", "2.0.0")),
    )
    with pytest.raises(TypeError):
        registry.restore_state(invalid)

    after = registry.snapshot_state()
    assert after.descriptors == before.descriptors
