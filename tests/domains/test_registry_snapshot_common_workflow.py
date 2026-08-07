"""Tests for InMemoryWorkflowRegistry snapshot/restore support."""

from __future__ import annotations

import pytest

from cmm.workflows.contracts import WorkflowDefinition, WorkflowNode
from cmm.workflows.enums import WorkflowNodeType
from cmm.workflows.errors import WorkflowRegistryError
from cmm.workflows.registry import InMemoryWorkflowRegistry


def _workflow(workflow_id: str, version: str = "1.0.0") -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id=workflow_id,
        version=version,
        name=workflow_id,
        description=f"test {workflow_id}",
        nodes=(
            WorkflowNode(
                node_id="start",
                node_type=WorkflowNodeType.COMPLETE,
                name="Start",
            ),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        metadata={},
    )


def test_snapshot_state_exists():
    """RED: snapshot_state() must exist."""
    registry = InMemoryWorkflowRegistry()
    assert hasattr(registry, "snapshot_state")


def test_restore_state_exists():
    """RED: restore_state() must exist."""
    registry = InMemoryWorkflowRegistry()
    assert hasattr(registry, "restore_state")


def test_round_trip_restores_exact_state():
    """Snapshot → mutate → restore → snapshot equals initial."""
    registry = InMemoryWorkflowRegistry()
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
    registry = InMemoryWorkflowRegistry()
    registry.register(_workflow("wf1"))

    before = registry.snapshot_state()

    registry.register(_workflow("wf2"))

    registry.restore_state(before)

    assert registry.get("wf1", "1.0.0") is not None
    with pytest.raises(WorkflowRegistryError):
        registry.get("wf2", "1.0.0")


def test_empty_registry_round_trip():
    """Empty registry snapshot/restore works."""
    registry = InMemoryWorkflowRegistry()
    before = registry.snapshot_state()
    registry.restore_state(before)
    after = registry.snapshot_state()
    assert after.definitions == before.definitions
    assert after.definitions == ()


def test_multiple_versions_restored():
    """Multiple versions of the same workflow are restored."""
    registry = InMemoryWorkflowRegistry()
    registry.register(_workflow("wf1", "1.0.0"))
    registry.register(_workflow("wf1", "2.0.0"))

    before = registry.snapshot_state()
    assert len(before.definitions) == 2

    registry.register(_workflow("wf2", "1.0.0"))
    registry.restore_state(before)

    assert registry.get("wf1", "1.0.0") is not None
    assert registry.get("wf1", "2.0.0") is not None
    with pytest.raises(WorkflowRegistryError):
        registry.get("wf2", "1.0.0")


def test_deterministic_order():
    """Snapshot definitions are in deterministic order."""
    registry = InMemoryWorkflowRegistry()
    registry.register(_workflow("b"))
    registry.register(_workflow("a"))

    snap = registry.snapshot_state()
    ids = [d.workflow_id for d in snap.definitions]
    assert ids == sorted(ids)


def test_snapshot_deeply_immutable():
    """Snapshot is deeply immutable."""
    registry = InMemoryWorkflowRegistry()
    registry.register(_workflow("wf1"))
    snap = registry.snapshot_state()

    with pytest.raises(AttributeError):
        snap.definitions[0].workflow_id = "changed"  # type: ignore[misc]


def test_wrong_type_rejected():
    """restore_state rejects wrong types."""
    registry = InMemoryWorkflowRegistry()
    with pytest.raises(WorkflowRegistryError):
        registry.restore_state("not a snapshot")  # type: ignore[arg-type]


def test_invalid_snapshot_does_not_mutate():
    """Invalid snapshot does not modify the registry."""
    registry = InMemoryWorkflowRegistry()
    registry.register(_workflow("wf1"))
    before = registry.snapshot_state()

    with pytest.raises(WorkflowRegistryError):
        registry.restore_state(object())  # type: ignore[arg-type]

    after = registry.snapshot_state()
    assert after.definitions == before.definitions


def test_double_restore_idempotent():
    """Two consecutive restores are idempotent."""
    registry = InMemoryWorkflowRegistry()
    registry.register(_workflow("wf1"))
    before = registry.snapshot_state()

    registry.register(_workflow("wf2"))
    registry.restore_state(before)
    registry.restore_state(before)

    after = registry.snapshot_state()
    assert after.definitions == before.definitions


def test_duplicate_workflow_id_version_rejected():
    """A well-typed snapshot with duplicate (workflow_id, version) keys is rejected without mutation."""
    from cmm.workflows.registry import WorkflowRegistrySnapshot

    registry = InMemoryWorkflowRegistry()
    registry.register(_workflow("wf1"))
    before = registry.snapshot_state()

    duplicate = WorkflowRegistrySnapshot(
        definitions=(_workflow("wf1"), _workflow("wf1")),
    )
    with pytest.raises(WorkflowRegistryError):
        registry.restore_state(duplicate)

    after = registry.snapshot_state()
    assert after.definitions == before.definitions


def test_snapshot_rejects_invalid_workflow_version_without_mutation():
    """A well-typed definition whose version register() rejects must also be
    rejected by restore_state(), before any mutation."""
    from cmm.workflows.registry import WorkflowRegistrySnapshot

    invalid = _workflow("wf_bad", "1.0")  # not SemVer (3 parts)

    fresh_registry = InMemoryWorkflowRegistry()
    with pytest.raises(WorkflowRegistryError):
        fresh_registry.register(invalid)

    snapshot = WorkflowRegistrySnapshot(definitions=(invalid,))

    registry = InMemoryWorkflowRegistry()
    registry.register(_workflow("wf1"))
    before = registry.snapshot_state()

    with pytest.raises(WorkflowRegistryError):
        registry.restore_state(snapshot)

    after = registry.snapshot_state()
    assert after.definitions == before.definitions


def test_snapshot_rejects_invalid_workflow_graph_without_mutation():
    """A well-typed definition whose graph register() rejects must also be
    rejected by restore_state(), before any mutation."""
    from cmm.workflows.errors import WorkflowGraphError
    from cmm.workflows.registry import WorkflowRegistrySnapshot

    # Valid version, but an EXECUTE_OPERATION node without operation_id/version.
    invalid = WorkflowDefinition(
        workflow_id="wf_bad_graph",
        version="1.0.0",
        name="bad",
        description="bad graph",
        nodes=(
            WorkflowNode(
                node_id="a",
                node_type=WorkflowNodeType.EXECUTE_OPERATION,
                name="A",
            ),
        ),
        completion_criteria={"all_required_nodes_completed": True},
        metadata={},
    )

    fresh_registry = InMemoryWorkflowRegistry()
    with pytest.raises(WorkflowGraphError):
        fresh_registry.register(invalid)

    snapshot = WorkflowRegistrySnapshot(definitions=(invalid,))

    registry = InMemoryWorkflowRegistry()
    registry.register(_workflow("wf1"))
    before = registry.snapshot_state()

    with pytest.raises(WorkflowGraphError):
        registry.restore_state(snapshot)

    after = registry.snapshot_state()
    assert after.definitions == before.definitions


def test_valid_common_workflow_snapshot_still_restores():
    """A valid workflow snapshot must still restore."""
    registry = InMemoryWorkflowRegistry()
    registry.register(_workflow("wf1"))
    registry.register(_workflow("wf2", "2.0.0"))
    before = registry.snapshot_state()

    registry.restore_state(before)

    after = registry.snapshot_state()
    assert after.definitions == before.definitions