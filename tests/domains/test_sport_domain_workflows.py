"""Tests for Phase 10.28 Sport Domain Workflows."""

from __future__ import annotations

from cmm.domains.sport.catalog import (
    CANONICAL_SPORT_WORKFLOW_IDS,
)
from cmm.domains.sport.workflows import (
    build_sport_workflow_definitions,
    execute_return_to_training_workflow,
)


def test_sport_workflow_definitions_canonical_parity() -> None:
    workflows = build_sport_workflow_definitions()
    assert len(workflows) == 5
    assert tuple(w.workflow_id for w in workflows) == CANONICAL_SPORT_WORKFLOW_IDS
    assert all(w.domain_id == "domain:sport" for w in workflows)


def test_sport_workflow_structure_safety_prefix() -> None:
    workflows = build_sport_workflow_definitions()
    for wf in workflows:
        node_ids = [n.node_id for n in wf.nodes]
        assert node_ids[0:3] == ["load", "profile", "reason"]
        assert node_ids[-1] == "complete"
        assert "validate" in node_ids


def test_return_to_training_with_health_constraints_workflow_execution() -> None:
    # 1. With active Health constraint requiring reduced load
    health_projection = {
        "constraint_id": "c-001",
        "status": "active",
        "activity_limits": ["no_sprinting"],
        "load_limits": {"max_intensity": 0.5},
        "authorization_reference": "auth.scope.100",
    }
    res = execute_return_to_training_workflow(
        rest_hours=7.5,
        fatigue_score=4,
        pain_score=3,
        health_constraint=health_projection,
        is_authorized=True,
        is_current=True,
    )
    assert res["status"] == "completed"
    assert res["recommendation"] in (
        "reduce_load",
        "continue",
        "hold",
        "stop_and_check",
    )
    assert res["health_constraint_applied"] is True
    assert res["is_diagnosis"] is False
    assert res["treatment_modified"] is False
    assert res["clinical_clearance_claimed"] is False


def test_return_to_training_rejects_unauthorized_health_context() -> None:
    res = execute_return_to_training_workflow(
        rest_hours=8.0,
        fatigue_score=2,
        pain_score=0,
        health_constraint={"full_clinical_history": ["diagnosis_A"]},
        is_authorized=False,
        is_current=True,
    )
    assert res["status"] == "completed"
    assert res["health_constraint_applied"] is False
