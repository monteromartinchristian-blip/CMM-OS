"""Phase 10.30 — Project Domain Workflows Tests."""

from __future__ import annotations

from cmm.domains.project.catalog import CANONICAL_PROJECT_WORKFLOW_IDS
from cmm.domains.project.workflows import (
    GENERIC_PROJECT_WORKFLOW_IDS,
    PROJECT_WORKFLOW_IDS,
    SOFTWARE_PROJECT_WORKFLOW_IDS,
    build_project_workflow_definitions,
)


def test_project_workflow_definitions_inventory_and_partition() -> None:
    wfs = build_project_workflow_definitions()
    assert len(wfs) == 12
    assert tuple(w.workflow_id for w in wfs) == CANONICAL_PROJECT_WORKFLOW_IDS
    assert tuple(w.workflow_id for w in wfs) == PROJECT_WORKFLOW_IDS
    assert all(w.domain_id == "domain:project" for w in wfs)

    generic_ids = tuple(w.workflow_id for w in wfs if w.workflow_id in GENERIC_PROJECT_WORKFLOW_IDS)
    assert len(generic_ids) == 4

    software_ids = tuple(w.workflow_id for w in wfs if w.workflow_id in SOFTWARE_PROJECT_WORKFLOW_IDS)
    assert len(software_ids) == 8


def test_project_workflow_nodes_safety_order() -> None:
    for wf in build_project_workflow_definitions():
        node_ids = [n.node_id for n in wf.nodes]
        # Safety prefix: load -> profile -> reason
        assert node_ids[:3] == ["load", "profile", "reason"]
        # Safety suffix: validate -> complete
        assert node_ids[-2:] == ["validate", "complete"]
        # Terminal complete node must depend on validate
        complete_node = wf.nodes[-1]
        assert "validate" in complete_node.dependencies


def test_feature_implementation_has_approval_gate() -> None:
    wfs = {w.workflow_id: w for w in build_project_workflow_definitions()}
    impl_wf = wfs["project.feature_implementation"]
    modify_nodes = [n for n in impl_wf.nodes if n.operation_id == "project.modify_code"]
    assert len(modify_nodes) == 1
    assert modify_nodes[0].approval_gate is not None


def test_self_development_workflow_chain() -> None:
    wfs = {w.workflow_id: w for w in build_project_workflow_definitions()}
    self_dev_wf = wfs["project.self_development"]
    op_ids = [n.operation_id for n in self_dev_wf.nodes if n.operation_id is not None]
    assert "project.analyse_architecture" in op_ids
    assert "project.run_validation" in op_ids
    assert "project.prepare_commit" in op_ids
