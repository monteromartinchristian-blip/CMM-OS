"""Tests for Phase 10.28 Sport Domain Memory."""

from __future__ import annotations

from cmm.domains.sport.memory import (
    CANDIDATE_SPORT_LONGITUDINAL_KINDS,
    build_sport_memory_proposal,
    build_sport_memory_view_request,
    validate_sport_memory_proposal_content,
)


def test_sport_memory_proposal_is_proposal_only() -> None:
    proposal = build_sport_memory_proposal(proposal_id="prop-001")
    assert proposal.proposal_id == "prop-001"
    assert proposal.requires_confirmation is True


def test_sport_memory_candidate_kinds() -> None:
    assert "sport_goal" in CANDIDATE_SPORT_LONGITUDINAL_KINDS
    assert "training_plan" in CANDIDATE_SPORT_LONGITUDINAL_KINDS
    assert "body_measurement" in CANDIDATE_SPORT_LONGITUDINAL_KINDS
    assert "readiness_snapshot" in CANDIDATE_SPORT_LONGITUDINAL_KINDS


def test_sport_memory_proposal_content_validation() -> None:
    # Valid proposal
    valid_content = {
        "kind": "readiness_snapshot",
        "readiness_state": "ready",
        "timestamp": "2026-08-25T10:00:00Z",
    }
    assert validate_sport_memory_proposal_content(valid_content)["is_valid"] is True

    # Prohibited diagnosis persistence
    diagnosis_content = {
        "kind": "injury_diagnosis",
        "clinical_diagnosis": "ACL tear",
    }
    res_diag = validate_sport_memory_proposal_content(diagnosis_content)
    assert res_diag["is_valid"] is False
    assert res_diag["reason"] == "prohibited_clinical_diagnosis"

    # Prohibited treatment advice persistence
    treatment_content = {
        "kind": "treatment_instruction",
        "medication_change": "stop anti-inflammatory",
    }
    res_treat = validate_sport_memory_proposal_content(treatment_content)
    assert res_treat["is_valid"] is False
    assert res_treat["reason"] == "prohibited_treatment_advice"


def test_sport_memory_view_request() -> None:
    req = build_sport_memory_view_request(request_id="req-100", trace_id="tr-100")
    assert req.request_id == "req-100"
    assert str(req.primary_domain) == "domain:sport"
