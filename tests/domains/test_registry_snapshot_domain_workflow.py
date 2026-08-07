"""Tests for InMemoryDomainWorkflowRegistry snapshot/restore support."""

from __future__ import annotations

from dataclasses import replace

import pytest

from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.domains.workflow_errors import DomainWorkflowRegistryError
from cmm.domains.workflow_registry import (
    DomainWorkflowRegistrySnapshot,
    InMemoryDomainWorkflowRegistry,
)
from cmm.workflows.contracts import WorkflowNode
from cmm.workflows.enums import WorkflowNodeType
from cmm.workflows.errors import WorkflowRegistryError
from cmm.workflows.registry import (
    InMemoryWorkflowRegistry,
    WorkflowRegistrySnapshot,
)


def _workflow(wf_id: str, version: str = "1.0.0") -> DomainWorkflowDefinition:
    return DomainWorkflowDefinition(
        workflow_id=wf_id,
        domain_id="domain:test",
        version=version,
        name=wf_id,
        description=f"test {wf_id}",
        nodes=(
            WorkflowNode(
                node_id="start",
                node_type=WorkflowNodeType.COMPLETE,
                name="Start",
            ),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        purpose="test",
        metadata={},
    )


def _registry():
    return InMemoryDomainWorkflowRegistry(InMemoryWorkflowRegistry())


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
    registry.register(_workflow("wf1"))
    registry.register(_workflow("wf2"))

    before = registry.snapshot_state()

    registry.register(_workflow("wf3"))

    after_mutation = registry.snapshot_state()
    assert len(after_mutation.definitions) == 3

    registry.restore_state(before)
    after_restore = registry.snapshot_state()

    assert after_restore.definitions == before.definitions
    assert len(after_restore.definitions) == 2


def test_preexisting_entries_preserved():
    """Restore preserves pre-existing entries."""
    registry = _registry()
    registry.register(_workflow("wf1"))

    before = registry.snapshot_state()

    registry.register(_workflow("wf2"))

    registry.restore_state(before)

    assert registry.get("wf1", "1.0.0") is not None
    with pytest.raises(KeyError):
        registry.get("wf2", "1.0.0")


def test_empty_registry_round_trip():
    """Empty registry snapshot/restore works."""
    registry = _registry()
    before = registry.snapshot_state()
    registry.restore_state(before)
    after = registry.snapshot_state()
    assert after.definitions == before.definitions
    assert after.definitions == ()


def test_multiple_versions_restored():
    """Multiple versions of the same workflow are restored."""
    registry = _registry()
    registry.register(_workflow("wf1", "1.0.0"))
    registry.register(_workflow("wf1", "2.0.0"))

    before = registry.snapshot_state()
    assert len(before.definitions) == 2

    registry.register(_workflow("wf2", "1.0.0"))
    registry.restore_state(before)

    assert registry.get("wf1", "1.0.0") is not None
    assert registry.get("wf1", "2.0.0") is not None
    with pytest.raises(KeyError):
        registry.get("wf2", "1.0.0")


def test_common_registry_restored():
    """The common workflow registry is restored along with the domain registry."""
    registry = _registry()
    registry.register(_workflow("wf1"))

    before = registry.snapshot_state()

    registry.register(_workflow("wf2"))

    # Common registry has both
    assert registry.common_registry.get("wf1", "1.0.0") is not None
    assert registry.common_registry.get("wf2", "1.0.0") is not None

    registry.restore_state(before)

    # Common registry restored to only wf1
    assert registry.common_registry.get("wf1", "1.0.0") is not None
    with pytest.raises(WorkflowRegistryError):
        registry.common_registry.get("wf2", "1.0.0")


def test_deterministic_order():
    """Snapshot definitions are in deterministic order."""
    registry = _registry()
    registry.register(_workflow("b"))
    registry.register(_workflow("a"))

    snap = registry.snapshot_state()
    ids = [d.workflow_id for d in snap.definitions]
    assert ids == sorted(ids)


def test_snapshot_deeply_immutable():
    """Snapshot is deeply immutable."""
    registry = _registry()
    registry.register(_workflow("wf1"))
    snap = registry.snapshot_state()

    with pytest.raises(AttributeError):
        snap.definitions[0].workflow_id = "changed"  # type: ignore[misc]


def test_wrong_type_rejected():
    """restore_state rejects wrong types."""
    registry = _registry()
    with pytest.raises(WorkflowRegistryError):
        registry.restore_state("not a snapshot")  # type: ignore[arg-type]


def test_invalid_snapshot_does_not_mutate():
    """Invalid snapshot does not modify the registry."""
    registry = _registry()
    registry.register(_workflow("wf1"))
    before = registry.snapshot_state()

    with pytest.raises(WorkflowRegistryError):
        registry.restore_state(object())  # type: ignore[arg-type]

    after = registry.snapshot_state()
    assert after.definitions == before.definitions


def test_double_restore_idempotent():
    """Two consecutive restores are idempotent."""
    registry = _registry()
    registry.register(_workflow("wf1"))
    before = registry.snapshot_state()

    registry.register(_workflow("wf2"))
    registry.restore_state(before)
    registry.restore_state(before)

    after = registry.snapshot_state()
    assert after.definitions == before.definitions
    assert after.common_registry == before.common_registry


def test_duplicate_domain_workflow_definitions_rejected():
    """A well-typed snapshot with duplicate (workflow_id, version) domain definitions is rejected."""
    registry = _registry()
    registry.register(_workflow("wf1"))
    before = registry.snapshot_state()

    duplicate = DomainWorkflowRegistrySnapshot(
        definitions=(_workflow("wf1"), _workflow("wf1")),
        common_registry=before.common_registry,
    )
    with pytest.raises(WorkflowRegistryError):
        registry.restore_state(duplicate)

    after = registry.snapshot_state()
    assert after.definitions == before.definitions
    assert after.common_registry == before.common_registry


def test_nested_common_registry_snapshot_invalid_rejected():
    """A well-typed snapshot with an invalid nested common registry is rejected without mutation.

    Neither the domain registry snapshot nor the nested common registry snapshot may change.
    """
    registry = _registry()
    registry.register(_workflow("wf1"))
    before = registry.snapshot_state()

    # Invalid nested common registry snapshot: duplicate (workflow_id, version) keys
    wf1_common = _workflow("wf1").to_common()
    invalid_common = WorkflowRegistrySnapshot(
        definitions=(wf1_common, wf1_common),
    )
    invalid = DomainWorkflowRegistrySnapshot(
        definitions=(_workflow("wf1"),),
        common_registry=invalid_common,
    )
    with pytest.raises(WorkflowRegistryError):
        registry.restore_state(invalid)

    after = registry.snapshot_state()
    assert after.definitions == before.definitions
    after = registry.snapshot_state()
    assert after.definitions == before.definitions
    assert after.common_registry.definitions == before.common_registry.definitions


# ── Audit v2 P1 — Domain↔Common workflow snapshot correspondence ──────────────
# Each negative snapshot below is internally valid on both layers but the common
# registry does not EXACTLY match DomainWorkflowDefinition.to_common().  The
# domain restore must reject these BEFORE touching the nested common registry.


def test_missing_common_workflow_rejected_without_mutation():
    """A domain definition with no common workflow counterpart is rejected."""
    registry = _registry()
    wf1 = _workflow("wf1")
    registry.register(wf1)
    before_domain = registry.snapshot_state()
    before_common = registry.common_registry.snapshot_state()

    # Internally valid empty common snapshot.
    empty_common = WorkflowRegistrySnapshot(definitions=())
    snapshot = DomainWorkflowRegistrySnapshot(
        definitions=(wf1,),
        common_registry=empty_common,
    )
    with pytest.raises(DomainWorkflowRegistryError):
        registry.restore_state(snapshot)

    after_domain = registry.snapshot_state()
    assert after_domain.definitions == before_domain.definitions
    assert (
        registry.common_registry.snapshot_state().definitions
        == before_common.definitions
    )


def test_common_workflow_mismatch_rejected_without_mutation():
    """A common workflow that differs from to_common() is rejected."""
    registry = _registry()
    wf1 = _workflow("wf1")
    registry.register(wf1)
    before_domain = registry.snapshot_state()
    before_common = registry.common_registry.snapshot_state()

    # Same key, but the common definition is not exactly wf1.to_common().
    mismatched = replace(wf1.to_common(), enabled=False)
    common = WorkflowRegistrySnapshot(definitions=(mismatched,))
    snapshot = DomainWorkflowRegistrySnapshot(
        definitions=(wf1,),
        common_registry=common,
    )
    with pytest.raises(DomainWorkflowRegistryError):
        registry.restore_state(snapshot)

    after_domain = registry.snapshot_state()
    assert after_domain.definitions == before_domain.definitions
    assert (
        registry.common_registry.snapshot_state().definitions
        == before_common.definitions
    )


def test_extra_common_workflow_rejected_without_mutation():
    """A common registry with an extra workflow is rejected (exact match required)."""
    registry = _registry()
    wf1 = _workflow("wf1")
    registry.register(wf1)
    before_domain = registry.snapshot_state()
    before_common = registry.common_registry.snapshot_state()

    wf2_common = _workflow("wf2").to_common()
    common = WorkflowRegistrySnapshot(
        definitions=(wf1.to_common(), wf2_common),
    )
    snapshot = DomainWorkflowRegistrySnapshot(
        definitions=(wf1,),
        common_registry=common,
    )
    with pytest.raises(DomainWorkflowRegistryError):
        registry.restore_state(snapshot)

    after_domain = registry.snapshot_state()
    assert after_domain.definitions == before_domain.definitions
    assert (
        registry.common_registry.snapshot_state().definitions
        == before_common.definitions
    )


def test_exact_common_workflow_snapshot_restores_successfully():
    """An exactly corresponding Domain↔Common snapshot restores cleanly."""
    registry = _registry()
    wf1 = _workflow("wf1")
    wf2 = _workflow("wf2")
    common = WorkflowRegistrySnapshot(
        definitions=(wf1.to_common(), wf2.to_common()),
    )
    snapshot = DomainWorkflowRegistrySnapshot(
        definitions=(wf1, wf2),
        common_registry=common,
    )
    registry.restore_state(snapshot)

    assert registry.get("wf1", "1.0.0") == wf1
    assert registry.get("wf2", "1.0.0") == wf2
    assert registry.resolve_active("wf1") == wf1
    assert registry.resolve_active("wf2") == wf2
    common_definitions = registry.common_registry.list_definitions()
    assert (wf1.workflow_id, wf1.version) in {
        (d.workflow_id, d.version) for d in common_definitions
    }
    assert (wf2.workflow_id, wf2.version) in {
        (d.workflow_id, d.version) for d in common_definitions
    }