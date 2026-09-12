"""Tests for Phase 10.52 Mental Health Domain operations and workflows.

Task 3: exactly eight declarative operations with frozen semantics and eight
workflows over the shared Workflow Engine contract.  Declaration never means
availability, and no workflow defines its own executor or runtime.
"""

from __future__ import annotations

from cmm.domains.mental_health.catalog import (
    MENTAL_HEALTH_OPERATION_IDS,
    MENTAL_HEALTH_WORKFLOW_IDS,
)
from cmm.domains.mental_health.operations import (
    build_mental_health_operation_definitions,
)
from cmm.domains.mental_health.workflows import (
    build_mental_health_workflow_definitions,
)
from cmm.workflows.enums import WorkflowNodeType

EXPECTED_OPERATION_TYPES = {
    "mental_health.review_emotional_context": "ANALYSIS",
    "mental_health.prepare_therapy_session": "PREPARATION",
    "mental_health.review_therapy_session": "ANALYSIS",
    "mental_health.analyze_therapy_transcript": "SENSITIVE",
    "mental_health.compare_emotional_periods": "ANALYSIS",
    "mental_health.map_fact_interpretation_uncertainty": "ANALYSIS",
    "mental_health.review_emotional_decision": "ANALYSIS",
    "mental_health.propose_memory_update": "MEMORY",
}


def _operations_by_id():
    return {
        operation.operation_id: operation
        for operation in build_mental_health_operation_definitions()
    }


def test_eight_operations_exist_with_canonical_domain():
    definitions = build_mental_health_operation_definitions()
    assert tuple(d.operation_id for d in definitions) == MENTAL_HEALTH_OPERATION_IDS
    assert len(definitions) == 8
    for operation in definitions:
        assert operation.domain_id == "domain:mental-health"
        assert operation.operation_id in MENTAL_HEALTH_OPERATION_IDS


def test_operation_semantics_are_classified_exactly():
    by_id = _operations_by_id()
    for operation_id, expected_type in EXPECTED_OPERATION_TYPES.items():
        assert by_id[operation_id].operation_type.name == expected_type


def test_no_operation_performs_an_external_or_destructive_effect():
    for operation in build_mental_health_operation_definitions():
        assert operation.operation_type.name not in {"EXTERNAL", "DESTRUCTIVE"}
        assert operation.metadata.get("direct_memory_write") is False


def test_propose_memory_update_is_proposal_only_and_approved():
    proposal = _operations_by_id()["mental_health.propose_memory_update"]
    assert proposal.requires_approval is True
    assert proposal.metadata["proposal_only"] is True
    assert proposal.metadata.get("direct_memory_write") is not True
    # A proposal can never directly persist: output is proposal + binding.
    assert set(proposal.output_schema["required"]) == {"proposal", "binding"}


def test_transcript_analysis_requires_speaker_provenance_inputs():
    transcript = _operations_by_id()["mental_health.analyze_therapy_transcript"]
    assert set(transcript.input_schema["required"]) == {
        "transcript_ref",
        "speaker_turns",
    }
    turn_schema = transcript.input_schema["properties"]["speaker_turns"]["items"]
    assert set(turn_schema["required"]) == {"turn_id", "speaker"}
    assert transcript.required_resources == ("mental_health.therapy_transcript",)


def test_operations_declare_only_structurally_consumed_resources():
    for operation in build_mental_health_operation_definitions():
        for resource_id in operation.required_resources:
            assert resource_id.startswith("mental_health.")


def test_eight_workflows_exist_and_are_ordered():
    workflows = build_mental_health_workflow_definitions()
    assert tuple(w.workflow_id for w in workflows) == MENTAL_HEALTH_WORKFLOW_IDS
    assert len(workflows) == 8
    for workflow in workflows:
        assert workflow.domain_id == "domain:mental-health"
        assert workflow.version == "1.0.0"


def test_workflows_reference_registered_operations_only():
    for workflow in build_mental_health_workflow_definitions():
        for node in workflow.nodes:
            if node.operation_id is not None:
                assert node.operation_id in MENTAL_HEALTH_OPERATION_IDS


def test_workflows_use_existing_node_types_only():
    allowed = {node_type.value for node_type in WorkflowNodeType}
    for workflow in build_mental_health_workflow_definitions():
        for node in workflow.nodes:
            assert node.node_type.value in allowed


def test_workflows_have_strict_load_profile_reason_prefix():
    for workflow in build_mental_health_workflow_definitions():
        by_id = {node.node_id: node for node in workflow.nodes}
        assert by_id["load"].node_type is WorkflowNodeType.LOAD_RESOURCE
        assert by_id["profile"].dependencies == ("load",)
        assert by_id["reason"].dependencies == ("profile",)
        assert by_id["profile"].node_type is WorkflowNodeType.APPLY_PROFILE


def test_complete_never_bypasses_validation():
    for workflow in build_mental_health_workflow_definitions():
        by_id = {node.node_id: node for node in workflow.nodes}
        complete = next(
            node
            for node in workflow.nodes
            if node.node_type is WorkflowNodeType.COMPLETE
        )
        # Walk dependencies backwards; a VALIDATE node must be reachable.
        seen: set[str] = set()
        stack = list(complete.dependencies)
        reachable_validate = False
        while stack:
            node_id = stack.pop()
            if node_id in seen:
                continue
            seen.add(node_id)
            node = by_id[node_id]
            if node.node_type is WorkflowNodeType.VALIDATE:
                reachable_validate = True
            stack.extend(node.dependencies)
        assert reachable_validate, workflow.workflow_id


def test_sensitive_memory_workflow_stops_at_proposal_and_approval():
    workflow = next(
        w
        for w in build_mental_health_workflow_definitions()
        if w.workflow_id == "mental_health.sensitive_memory_proposal_review"
    )
    by_id = {node.node_id: node for node in workflow.nodes}
    assert by_id["approval"].node_type is WorkflowNodeType.REQUEST_APPROVAL
    assert by_id["propose"].node_type is WorkflowNodeType.PROPOSE_MEMORY
    assert by_id["propose"].dependencies == ("approval",)
    assert by_id["complete"].dependencies == ("propose",)
    # No node in this workflow can mutate memory directly.
    assert all(
        node.node_type is not WorkflowNodeType.UPDATE_SESSION for node in workflow.nodes
    )


def test_safety_workflow_is_coordination_only():
    workflow = next(
        w
        for w in build_mental_health_workflow_definitions()
        if w.workflow_id == "mental_health.safety_escalation_review"
    )
    assert workflow.metadata["own_crisis_engine"] is False
    assert workflow.metadata["emotion_triggered_escalation"] is False
    escalate = next(
        node for node in workflow.nodes if node.node_type is WorkflowNodeType.ESCALATE
    )
    # Coordination routes to the existing mechanism; it invents no protocol.
    assert escalate.operation_id is None


def test_no_workflow_defines_its_own_executor_or_runtime():
    for workflow in build_mental_health_workflow_definitions():
        assert not hasattr(workflow, "executor")
        assert "executor" not in workflow.metadata
        assert "runtime" not in workflow.metadata
