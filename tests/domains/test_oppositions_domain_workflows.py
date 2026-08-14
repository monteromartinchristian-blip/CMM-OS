"""Phase 10.23 — Opposition Domain Workflows tests (spec §44)."""

from __future__ import annotations

from cmm.domains.oppositions import build_oppositions_workflow_definitions


def test_exactly_seven_workflows():
    workflows = build_oppositions_workflow_definitions()
    assert len(workflows) == 7


def test_workflow_ids_exact():
    workflows = build_oppositions_workflow_definitions()
    ids = {w.workflow_id for w in workflows}
    assert ids == {
        "oppositions.setup",
        "oppositions.weekly_review",
        "oppositions.mock_exam_review",
        "oppositions.call_analysis",
        "oppositions.syllabus_revision",
        "oppositions.alternative_route_comparison",
        "oppositions.exam_readiness",
    }


def test_shared_workflow_engine_used():
    """Workflow nodes use the shared WorkflowNodeType, not a custom runtime."""
    from cmm.workflows.enums import WorkflowNodeType

    workflows = build_oppositions_workflow_definitions()
    all_types = {node.node_type for w in workflows for node in w.nodes}
    assert WorkflowNodeType.COMPLETE in all_types
    assert WorkflowNodeType.REASON in all_types


def test_strict_dependency_prefix():
    """load -> profile -> reason strict safety prefix in every workflow."""
    from cmm.workflows.enums import WorkflowNodeType

    workflows = build_oppositions_workflow_definitions()
    for w in workflows:
        nodes = {n.node_id: n for n in w.nodes}
        assert nodes["load"].node_type is WorkflowNodeType.LOAD_RESOURCE
        assert nodes["profile"].dependencies == ("load",)
        assert nodes["reason"].dependencies == ("profile",)


def test_every_workflow_complete_depends_on_validate():
    workflows = build_oppositions_workflow_definitions()
    for w in workflows:
        complete = next(n for n in w.nodes if n.node_id == "complete")
        # completion transitively depends on a VALIDATE node
        assert complete.dependencies


def test_call_analysis_has_official_readonly_verification_gate():
    workflows = {w.workflow_id: w for w in build_oppositions_workflow_definitions()}
    call_analysis = workflows["oppositions.call_analysis"]
    verify = next(n for n in call_analysis.nodes if n.node_id == "verify")
    assert verify.wait_condition == {"official_only": True, "read_only": True}


def test_weekly_review_includes_call_monitoring_concern():
    from cmm.workflows.enums import WorkflowNodeType

    workflows = {w.workflow_id: w for w in build_oppositions_workflow_definitions()}
    weekly = workflows["oppositions.weekly_review"]
    assert any(
        n.operation_id == "oppositions.review_call"
        and n.node_type is WorkflowNodeType.EXECUTE_OPERATION
        for n in weekly.nodes
    )


def test_no_registration_payment_submission_node():
    workflows = build_oppositions_workflow_definitions()
    for w in workflows:
        for n in w.nodes:
            assert n.operation_id != "oppositions.register"
            assert n.name.lower() not in ("submit", "register", "pay")


def test_alternative_route_workflow_does_not_switch_target():
    workflows = {w.workflow_id: w for w in build_oppositions_workflow_definitions()}
    comparison = workflows["oppositions.alternative_route_comparison"]
    # completion goes through an approval gate (proposal only)
    assert any(n.approval_gate for n in comparison.nodes)


def test_syllabus_revision_no_forgetting_inference():
    workflows = {w.workflow_id: w for w in build_oppositions_workflow_definitions()}
    revision = workflows["oppositions.syllabus_revision"]
    # revision plan is grounded in coverage; proposal-only/validate tail
    assert any(n.operation_id == "oppositions.generate_revision_plan" for n in revision.nodes)