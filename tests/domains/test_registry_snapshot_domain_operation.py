"""Tests for InMemoryDomainOperationRegistry snapshot/restore support."""

from __future__ import annotations

from dataclasses import replace

import pytest

from cmm.agent_runtime.operation_registry import (
    AgentOperationRegistrySnapshot,
    InMemoryAgentOperationRegistry,
)
from cmm.domains.enums import DomainOperationType
from cmm.domains.errors import DomainOperationRegistryError
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.operation_registry import (
    DomainOperationRegistrySnapshot,
    InMemoryDomainOperationRegistry,
)


class _Impl:
    def __init__(self, definition):
        self.definition = definition

    def execute(self, request):
        return {"success": True, "output": {}, "effects": ()}


def _operation(op_id: str, version: str = "1.0.0") -> DomainOperationDefinition:
    return DomainOperationDefinition(
        operation_id=f"test.{op_id}",
        domain_id="domain:test",
        version=version,
        name=op_id,
        description=f"test {op_id}",
        operation_type=DomainOperationType.ANALYSIS,
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        required_resources=(),
        required_permissions=(),
        risk_level="low",
        reversible=False,
        requires_approval=False,
        validation_policy_id=None,
        rollback_policy_id=None,
        enabled=True,
        metadata={},
    )


def _registry():
    return InMemoryDomainOperationRegistry(InMemoryAgentOperationRegistry())


def test_snapshot_state_exists():
    """RED: snapshot_state() must exist."""
    registry = _registry()
    assert hasattr(registry, "snapshot_state")


def test_restore_state_exists():
    """RED: restore_state() must exist."""
    registry = _registry()
    assert hasattr(registry, "restore_state")


def test_round_trip_restores_exact_state():
    """Snapshot → mutate → restore → snapshot equals initial."""
    registry = _registry()
    op1 = _operation("op1")
    op2 = _operation("op2")
    registry.register(op1, _Impl(op1))
    registry.register(op2, _Impl(op2))

    before = registry.snapshot_state()

    op3 = _operation("op3")
    registry.register(op3, _Impl(op3))

    after_mutation = registry.snapshot_state()
    assert len(after_mutation.definitions) == 3

    registry.restore_state(before)
    after_restore = registry.snapshot_state()

    assert after_restore.definitions == before.definitions
    assert len(after_restore.definitions) == 2


def test_preexisting_entries_preserved():
    """Restore preserves pre-existing entries."""
    registry = _registry()
    op1 = _operation("op1")
    registry.register(op1, _Impl(op1))

    before = registry.snapshot_state()

    op2 = _operation("op2")
    registry.register(op2, _Impl(op2))

    registry.restore_state(before)

    assert registry.get("test.op1", "1.0.0") is not None
    with pytest.raises(DomainOperationRegistryError):
        registry.get("test.op2", "1.0.0")


def test_empty_registry_round_trip():
    """Empty registry snapshot/restore works."""
    registry = _registry()
    before = registry.snapshot_state()
    registry.restore_state(before)
    after = registry.snapshot_state()
    assert after.definitions == before.definitions
    assert after.definitions == ()


def test_multiple_versions_restored():
    """Multiple versions of the same operation are restored."""
    registry = _registry()
    op1a = _operation("op1", "1.0.0")
    op1b = _operation("op1", "2.0.0")
    registry.register(op1a, _Impl(op1a))
    registry.register(op1b, _Impl(op1b))

    before = registry.snapshot_state()
    assert len(before.definitions) == 2

    op2 = _operation("op2")
    registry.register(op2, _Impl(op2))
    registry.restore_state(before)

    assert registry.get("test.op1", "1.0.0") is not None
    assert registry.get("test.op1", "2.0.0") is not None
    with pytest.raises(DomainOperationRegistryError):
        registry.get("test.op2", "1.0.0")


def test_common_registry_restored():
    """The common registry is restored along with the domain registry."""
    registry = _registry()
    op1 = _operation("op1")
    registry.register(op1, _Impl(op1))

    before = registry.snapshot_state()

    op2 = _operation("op2")
    registry.register(op2, _Impl(op2))

    # Common registry has both
    assert registry.common_registry.contains("test.op1", "1.0.0")
    assert registry.common_registry.contains("test.op2", "1.0.0")

    registry.restore_state(before)

    # Common registry restored to only op1
    assert registry.common_registry.contains("test.op1", "1.0.0")
    assert not registry.common_registry.contains("test.op2", "1.0.0")


def test_implementations_restored():
    """Implementations are restored along with definitions."""
    registry = _registry()
    op1 = _operation("op1")
    impl1 = _Impl(op1)
    registry.register(op1, impl1)

    before = registry.snapshot_state()

    op2 = _operation("op2")
    registry.register(op2, _Impl(op2))

    registry.restore_state(before)

    assert registry.get_implementation("test.op1", "1.0.0") is impl1
    with pytest.raises(DomainOperationRegistryError):
        registry.get_implementation("test.op2", "1.0.0")


def test_deterministic_order():
    """Snapshot definitions are in deterministic order."""
    registry = _registry()
    op_b = _operation("b")
    op_a = _operation("a")
    registry.register(op_b, _Impl(op_b))
    registry.register(op_a, _Impl(op_a))

    snap = registry.snapshot_state()
    ids = [d.operation_id for d in snap.definitions]
    assert ids == sorted(ids)


def test_snapshot_deeply_immutable():
    """Snapshot is deeply immutable."""
    registry = _registry()
    op1 = _operation("op1")
    registry.register(op1, _Impl(op1))
    snap = registry.snapshot_state()

    with pytest.raises(AttributeError):
        snap.definitions[0].operation_id = "changed"  # type: ignore[misc]


def test_wrong_type_rejected():
    """restore_state rejects wrong types."""
    registry = _registry()
    with pytest.raises(DomainOperationRegistryError):
        registry.restore_state("not a snapshot")  # type: ignore[arg-type]


def test_invalid_snapshot_does_not_mutate():
    """Invalid snapshot does not modify the registry."""
    registry = _registry()
    op1 = _operation("op1")
    registry.register(op1, _Impl(op1))
    before = registry.snapshot_state()

    with pytest.raises(DomainOperationRegistryError):
        registry.restore_state(object())  # type: ignore[arg-type]

    after = registry.snapshot_state()
    assert after.definitions == before.definitions


def test_double_restore_idempotent():
    """Two consecutive restores are idempotent."""
    registry = _registry()
    op1 = _operation("op1")
    registry.register(op1, _Impl(op1))
    before = registry.snapshot_state()

    op2 = _operation("op2")
    registry.register(op2, _Impl(op2))
    registry.restore_state(before)
    registry.restore_state(before)

    after = registry.snapshot_state()
    assert after.definitions == before.definitions


def test_duplicate_definitions_rejected():
    """A well-typed snapshot with duplicate definitions is rejected."""
    registry = _registry()
    op1 = _operation("op1")
    registry.register(op1, _Impl(op1))
    before = registry.snapshot_state()

    duplicate = DomainOperationRegistrySnapshot(
        definitions=(op1, op1),
        implementations=(("test.op1", "1.0.0", _Impl(op1)),),
        common_registry=before.common_registry,
    )
    with pytest.raises(DomainOperationRegistryError):
        registry.restore_state(duplicate)

    after = registry.snapshot_state()
    assert after.definitions == before.definitions


def test_implementation_missing_definition_rejected():
    """A well-typed snapshot with an implementation referencing a missing definition is rejected."""
    registry = _registry()
    op1 = _operation("op1")
    registry.register(op1, _Impl(op1))
    before = registry.snapshot_state()

    invalid = DomainOperationRegistrySnapshot(
        definitions=(op1,),
        implementations=(("test.op2", "1.0.0", _Impl(op1)),),
        common_registry=before.common_registry,
    )
    with pytest.raises(DomainOperationRegistryError):
        registry.restore_state(invalid)

    after = registry.snapshot_state()
    assert after.definitions == before.definitions


def test_nested_common_registry_invalid_does_not_mutate():
    """A well-typed snapshot with an invalid nested common registry does not mutate local state."""
    registry = _registry()
    op1 = _operation("op1")
    registry.register(op1, _Impl(op1))
    before = registry.snapshot_state()

    # Invalid nested common registry: order references a missing descriptor,
    # while descriptors cross-match the domain definitions (so the domain↔common
    # cross-consistency validation passes and the nested internal validation is
    # what rejects it).
    invalid_common = AgentOperationRegistrySnapshot(
        descriptors=(op1.to_operation_descriptor(),),
        order=(("test.other", "1.0.0"),),
    )
    invalid = DomainOperationRegistrySnapshot(
        definitions=(op1,),
        implementations=(("test.op1", "1.0.0", _Impl(op1)),),
        common_registry=invalid_common,
    )
    with pytest.raises(TypeError):
        registry.restore_state(invalid)

    after = registry.snapshot_state()
    assert after.definitions == before.definitions
    assert registry.common_registry.contains("test.op1", "1.0.0")
    after = registry.snapshot_state()
    assert after.definitions == before.definitions
    assert registry.common_registry.contains("test.op1", "1.0.0")


# ── Audit v2 P1 — cross-layer snapshot consistency ─────────────────────────────
# Each snapshot below is well typed and internally valid, but is inconsistent
# across the domain layer (definitions/implementations) and the common layer
# (descriptors).  restore_state must reject them WITHOUT mutating either layer.


def test_enabled_definition_without_implementation_rejected_without_mutation():
    """Enabled definition requires an executable implementation."""
    registry = _registry()
    keep = _operation("keep")
    registry.register(keep, _Impl(keep))
    before = registry.snapshot_state()

    op1 = _operation("op1")  # enabled=True
    common = AgentOperationRegistrySnapshot(
        descriptors=(op1.to_operation_descriptor(),),
        order=(("test.op1", "1.0.0"),),
    )
    snapshot = DomainOperationRegistrySnapshot(
        definitions=(op1,),
        implementations=(),
        common_registry=common,
    )
    with pytest.raises(DomainOperationRegistryError):
        registry.restore_state(snapshot)

    after = registry.snapshot_state()
    assert after.definitions == before.definitions
    assert registry.common_registry.contains("test.keep", "1.0.0")
    assert registry.common_registry.contains("test.op1", "1.0.0") is False


def test_mismatched_implementation_definition_rejected_without_mutation():
    """An implementation bound to a different definition is rejected."""
    registry = _registry()
    keep = _operation("keep")
    registry.register(keep, _Impl(keep))
    before = registry.snapshot_state()

    op1 = _operation("op1")
    other = _operation("other")
    impl_for_other = _Impl(other)  # impl.definition is `other`, not `op1`
    common = AgentOperationRegistrySnapshot(
        descriptors=(op1.to_operation_descriptor(),),
        order=(("test.op1", "1.0.0"),),
    )
    snapshot = DomainOperationRegistrySnapshot(
        definitions=(op1,),
        implementations=(("test.op1", "1.0.0", impl_for_other),),
        common_registry=common,
    )
    with pytest.raises(DomainOperationRegistryError):
        registry.restore_state(snapshot)

    after = registry.snapshot_state()
    assert after.definitions == before.definitions
    assert registry.common_registry.contains("test.op1", "1.0.0") is False


def test_common_descriptor_mismatch_rejected_without_mutation():
    """A common descriptor that differs from the definition descriptor is rejected."""
    registry = _registry()
    keep = _operation("keep")
    registry.register(keep, _Impl(keep))
    before = registry.snapshot_state()

    op1 = _operation("op1")  # enabled=True
    impl = _Impl(op1)
    mismatched = replace(op1.to_operation_descriptor(), enabled=False)
    common = AgentOperationRegistrySnapshot(
        descriptors=(mismatched,),
        order=(("test.op1", "1.0.0"),),
    )
    snapshot = DomainOperationRegistrySnapshot(
        definitions=(op1,),
        implementations=(("test.op1", "1.0.0", impl),),
        common_registry=common,
    )
    with pytest.raises(DomainOperationRegistryError):
        registry.restore_state(snapshot)

    after = registry.snapshot_state()
    assert after.definitions == before.definitions
    assert registry.common_registry.contains("test.op1", "1.0.0") is False


def test_missing_common_descriptor_rejected_without_mutation():
    """A common registry missing the definition descriptor is rejected."""
    registry = _registry()
    keep = _operation("keep")
    registry.register(keep, _Impl(keep))
    before = registry.snapshot_state()

    op1 = _operation("op1")
    impl = _Impl(op1)
    common = AgentOperationRegistrySnapshot(descriptors=(), order=())
    snapshot = DomainOperationRegistrySnapshot(
        definitions=(op1,),
        implementations=(("test.op1", "1.0.0", impl),),
        common_registry=common,
    )
    with pytest.raises(DomainOperationRegistryError):
        registry.restore_state(snapshot)

    after = registry.snapshot_state()
    assert after.definitions == before.definitions
    assert registry.common_registry.contains("test.keep", "1.0.0")
    assert registry.common_registry.contains("test.op1", "1.0.0") is False


def test_extra_common_descriptor_rejected_without_mutation():
    """A common registry with an extra descriptor is rejected (exact match required)."""
    registry = _registry()
    keep = _operation("keep")
    registry.register(keep, _Impl(keep))
    before = registry.snapshot_state()

    op1 = _operation("op1")
    op2 = _operation("op2")
    impl = _Impl(op1)
    common = AgentOperationRegistrySnapshot(
        descriptors=(
            op1.to_operation_descriptor(),
            op2.to_operation_descriptor(),
        ),
        order=(("test.op1", "1.0.0"), ("test.op2", "1.0.0")),
    )
    snapshot = DomainOperationRegistrySnapshot(
        definitions=(op1,),
        implementations=(("test.op1", "1.0.0", impl),),
        common_registry=common,
    )
    with pytest.raises(DomainOperationRegistryError):
        registry.restore_state(snapshot)

    after = registry.snapshot_state()
    assert after.definitions == before.definitions
    assert registry.common_registry.contains("test.op2", "1.0.0") is False
    assert registry.common_registry.contains("test.op1", "1.0.0") is False
