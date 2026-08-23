"""Tests for Phase 10.26 Languages Domain Workflows."""

from __future__ import annotations

from cmm.domains.languages.catalog import (
    CANONICAL_LANGUAGES_WORKFLOW_IDS,
    CANONICAL_LANGUAGES_WORKFLOW_NAMES,
)
from cmm.domains.languages.operations import build_languages_operation_definitions
from cmm.domains.languages.workflows import (
    build_languages_workflow_definitions,
)
from cmm.workflows.enums import WorkflowNodeType


def test_build_languages_workflow_definitions_count_and_names() -> None:
    """Verify exact 9 workflows, canonical names, and acyclic nodes."""
    workflows = build_languages_workflow_definitions()
    assert len(workflows) == 9
    assert tuple(w.workflow_id for w in workflows) == CANONICAL_LANGUAGES_WORKFLOW_IDS
    assert tuple(w.name for w in workflows) == CANONICAL_LANGUAGES_WORKFLOW_NAMES

    for w in workflows:
        assert str(w.domain_id) == "domain:languages"
        assert w.version == "1.0.0"
        node_ids = [n.node_id for n in w.nodes]
        assert len(node_ids) == len(set(node_ids)), f"Duplicate node IDs in {w.workflow_id}"

        # First 3 nodes must be load -> profile -> reason
        assert node_ids[:3] == ["load", "profile", "reason"]
        assert w.nodes[1].dependencies == ("load",)
        assert w.nodes[2].dependencies == ("profile",)

        # Complete node must exist and depend on at least one validate node
        assert "complete" in node_ids
        complete_node = next(n for n in w.nodes if n.node_id == "complete")
        assert complete_node.node_type is WorkflowNodeType.COMPLETE


def test_workflow_validate_nodes_consume_real_producer_fields() -> None:
    """Audit every VALIDATE node: all wait_condition keys must be declared in a direct dependency's output schema."""
    workflows = build_languages_workflow_definitions()
    operations = {op.operation_id: op for op in build_languages_operation_definitions()}

    for w in workflows:
        nodes_by_id = {n.node_id: n for n in w.nodes}
        for node in w.nodes:
            if node.node_type is not WorkflowNodeType.VALIDATE:
                continue
            assert node.wait_condition, f"Validate node {node.node_id} in {w.workflow_id} has empty wait_condition"

            # Check each key in wait_condition
            for condition_key in node.wait_condition:
                found_producer = False
                for dep_id in node.dependencies:
                    dep_node = nodes_by_id.get(dep_id)
                    if dep_node and dep_node.operation_id:
                        op = operations.get(dep_node.operation_id)
                        if op and condition_key in op.output_schema.get("properties", {}):
                            found_producer = True
                            break
                assert found_producer, (
                    f"Workflow {w.workflow_id} validate node {node.node_id} condition '{condition_key}' "
                    f"is not declared in any direct dependency operation schema! (deps: {node.dependencies})"
                )


def test_onboarding_tracking_boundary_gate() -> None:
    """Verify onboarding workflow contains validate_tracking_boundary reading from create_plan."""
    workflows = {w.workflow_id: w for w in build_languages_workflow_definitions()}
    onb = workflows["languages.language_onboarding"]
    val_node = next(n for n in onb.nodes if n.node_id == "validate_tracking_boundary")
    assert "tracking_choice_resolved" in val_node.wait_condition
    assert "persistence_applied" in val_node.wait_condition
    assert val_node.dependencies == ("create_plan",)


def test_certification_preparation_gates() -> None:
    """Verify certification prep workflow contains gates reading from prepare_certification."""
    workflows = {w.workflow_id: w for w in build_languages_workflow_definitions()}
    cert_wf = workflows["languages.certification_preparation"]
    val_node = next(n for n in cert_wf.nodes if n.node_type is WorkflowNodeType.VALIDATE)
    assert "registration_performed" in val_node.wait_condition
    assert "payment_performed" in val_node.wait_condition
    assert "submission_performed" in val_node.wait_condition
    assert val_node.dependencies == ("certification",)
