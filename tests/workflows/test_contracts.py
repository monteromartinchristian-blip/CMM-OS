from datetime import datetime, timezone

import pytest

from cmm.workflows.contracts import WorkflowDefinition, WorkflowNode, WorkflowRun
from cmm.workflows.enums import WorkflowAvailabilityStatus, WorkflowRunStatus
from cmm.workflows.errors import WorkflowContractError


def node(node_id="start", node_type="complete", *, dependencies=()):
    return WorkflowNode(
        node_id=node_id,
        node_type=node_type,
        name=node_id,
        dependencies=dependencies,
    )


def test_definition_and_run_statuses_are_separate():
    assert WorkflowAvailabilityStatus.AVAILABLE.value == "available"
    assert WorkflowRunStatus.PENDING.value == "pending"
    with pytest.raises(ValueError):
        WorkflowRunStatus("available")


def test_definition_round_trip_is_deeply_immutable():
    definition = WorkflowDefinition(
        workflow_id="example.workflow",
        version="1.0.0",
        name="Example",
        nodes=(node(),),
        metadata={"nested": {"value": 1}},
    )
    restored = WorkflowDefinition.from_dict(definition.to_dict())
    assert restored.to_dict() == definition.to_dict()
    with pytest.raises(TypeError):
        definition.metadata["nested"]["value"] = 2


def test_unknown_fields_and_non_finite_metadata_are_rejected():
    with pytest.raises(WorkflowContractError):
        WorkflowDefinition.from_dict(
            {"workflow_id": "x", "version": "1.0.0", "name": "X", "nodes": [], "extra": 1}
        )
    with pytest.raises(WorkflowContractError):
        WorkflowDefinition(
            workflow_id="x", version="1.0.0", name="X", nodes=(node(),), metadata={"n": float("nan")}
        )


def test_run_requires_aware_ordered_timestamps_and_valid_status_invariants():
    started = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(WorkflowContractError):
        WorkflowRun(
            run_id="run-1", workflow_id="x", workflow_version="1.0.0",
            status=WorkflowRunStatus.COMPLETED, started_at=started,
            completed_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
    with pytest.raises(WorkflowContractError):
        WorkflowRun(
            run_id="run-1", workflow_id="x", workflow_version="1.0.0",
            status=WorkflowRunStatus.PAUSED,
        )
