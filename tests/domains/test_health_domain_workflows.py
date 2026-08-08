"""Tests for Phase 10.20 Health Domain workflows."""

from __future__ import annotations

from cmm.domains import health
from cmm.domains.health.catalog import CANONICAL_HEALTH_WORKFLOW_IDS


def test_eight_workflows_and_canonical_order():
    workflows = health.build_health_workflow_definitions()
    assert len(workflows) == 8
    assert [w.workflow_id for w in workflows] == list(CANONICAL_HEALTH_WORKFLOW_IDS)


def test_all_workflows_end_in_proposal_never_write():
    from cmm.workflows.enums import WorkflowNodeType

    for workflow in health.build_health_workflow_definitions():
        node_types = {node.node_type for node in workflow.nodes}
        # Propose memory is allowed; there is no persist/write node type used.
        assert WorkflowNodeType.PROPOSE_MEMORY in node_types
        assert WorkflowNodeType.COMPLETE in node_types


def test_no_schedule_external_nodes():
    from cmm.domains.health.catalog import CANONICAL_HEALTH_OPERATION_IDS

    known_ops = set(CANONICAL_HEALTH_OPERATION_IDS)
    for workflow in health.build_health_workflow_definitions():
        for node in workflow.nodes:
            # Every operation node references a declared Health operation.
            if node.operation_id is not None:
                assert node.operation_id in known_ops


def test_medication_workflow_only_reviews():
    from cmm.domains.health.catalog import CANONICAL_HEALTH_OPERATION_IDS

    wf = next(
        w
        for w in health.build_health_workflow_definitions()
        if w.workflow_id == "health.medication_change_review"
    )
    op_ids = {node.operation_id for node in wf.nodes if node.operation_id}
    assert op_ids <= set(CANONICAL_HEALTH_OPERATION_IDS)
    assert "health.review_medication_changes" in op_ids


def test_prepare_workflow_does_not_book():
    wf = next(
        w
        for w in health.build_health_workflow_definitions()
        if w.workflow_id == "health.specialist_appointment_preparation"
    )
    op_ids = {node.operation_id for node in wf.nodes if node.operation_id}
    assert "health.prepare_medical_appointment" in op_ids
    # There is no booking operation anywhere in Health.
    assert all("book" not in op for op in op_ids)
