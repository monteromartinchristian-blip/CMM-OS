"""Tests for Phase 10.29 Life Plan Domain Memory Integration."""

from __future__ import annotations

from typing import Any

import pytest

from cmm.domains.life_plan.memory import (
    CANDIDATE_LIFE_PLAN_LONGITUDINAL_KINDS,
    build_life_plan_memory_binding,
    build_life_plan_memory_proposal,
    build_life_plan_memory_view,
    build_life_plan_memory_view_request,
    validate_life_plan_memory_binding,
    validate_life_plan_memory_proposal_content,
)
from cmm.domains.memory_contracts import (
    DomainMemoryCapability,
    DomainMemoryProposalKind,
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
)


def test_life_plan_memory_proposal_is_proposal_only() -> None:
    prop = build_life_plan_memory_proposal(proposal_id="prop-lp-001")
    assert prop.proposal_id == "prop-lp-001"
    assert prop.proposal_kind == DomainMemoryProposalKind.MEMORY_UPDATE
    assert prop.requires_confirmation is True
    assert prop.required_capabilities == (DomainMemoryCapability.PROPOSE,)


def test_life_plan_memory_candidate_kinds() -> None:
    assert "life_goal" in CANDIDATE_LIFE_PLAN_LONGITUDINAL_KINDS
    assert "milestone" in CANDIDATE_LIFE_PLAN_LONGITUDINAL_KINDS
    assert "scenario" in CANDIDATE_LIFE_PLAN_LONGITUDINAL_KINDS
    assert "decision" in CANDIDATE_LIFE_PLAN_LONGITUDINAL_KINDS


def test_validate_life_plan_memory_proposal_content_valid() -> None:
    content = {
        "kind": "life_goal",
        "goal_id": "g-101",
        "title": "Learn Japanese",
        "status": "active",
        "is_confirmed": True,
    }
    res = validate_life_plan_memory_proposal_content(content)
    assert res["is_valid"] is True


def test_validate_life_plan_memory_proposal_content_rejects_unconfirmed_promotion() -> (
    None
):
    content = {
        "kind": "decision",
        "status": "decision",
        "original_status": "preference",
        "is_confirmed": False,
    }
    res = validate_life_plan_memory_proposal_content(content)
    assert res["is_valid"] is False
    assert (
        "unconfirmed" in res["reason"].lower()
        or "confirmation" in res["reason"].lower()
    )


def test_validate_life_plan_memory_proposal_content_rejects_truthy_string_coercion() -> (
    None
):
    # Exact V1 reproduction: string "false" is truthy in Python
    content = {
        "kind": "decision",
        "status": "decision",
        "original_status": "preference",
        "is_confirmed": "false",
    }
    res = validate_life_plan_memory_proposal_content(content)
    assert res["is_valid"] is False


def test_validate_life_plan_memory_proposal_content_coercion_matrix_fails_closed() -> (
    None
):
    non_booleans = ("false", "true", 0, 1, [], {}, None, "1", "0")
    for val in non_booleans:
        content = {
            "kind": "decision",
            "status": "decision",
            "original_status": "preference",
            "is_confirmed": val,
        }
        res = validate_life_plan_memory_proposal_content(content)
        assert res["is_valid"] is False, (
            f"Value {val!r} unexpectedly authorized confirmation"
        )


def test_validate_life_plan_memory_proposal_content_rejects_prohibited_clinical_data() -> (
    None
):
    content = {
        "kind": "health_constraint",
        "full_clinical_history": ["surgery_2024"],
    }
    res = validate_life_plan_memory_proposal_content(content)
    assert res["is_valid"] is False


def test_life_plan_memory_view_request() -> None:
    req = build_life_plan_memory_view_request(
        request_id="req-view-01", trace_id="tr-view-01"
    )
    assert req.request_id == "req-view-01"
    assert str(req.primary_domain) == "domain:life-plan"


def test_life_plan_memory_validation_fails_closed_on_validator_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cmm.domains.memory_contracts import DomainMemoryValidationResult
    from cmm.domains.memory_validation import DefaultDomainMemoryIntegrationValidator

    def _raise_error(*args: Any, **kwargs: Any) -> DomainMemoryValidationResult:
        raise RuntimeError("Injected memory validator fault")

    monkeypatch.setattr(
        DefaultDomainMemoryIntegrationValidator, "validate_binding", _raise_error
    )

    with pytest.raises(RuntimeError, match="Injected memory validator fault"):
        validate_life_plan_memory_binding(binding=None, inventory=None)


def test_life_plan_memory_validation_fails_on_malformed_inventory() -> None:
    reference = DomainMemoryReference(
        reference_id="ref-lp-1",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="canon-1",
        domain_id="domain:life-plan",
        applicable_domains=("domain:life-plan",),
    )
    request = build_life_plan_memory_view_request(
        request_id="req-1",
        trace_id="tr-1",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(reference,),
    )
    base_inventory = DomainMemoryReferenceInventory(
        references=(reference,),
    )
    view = build_life_plan_memory_view(request=request, inventory=base_inventory)
    proposal = build_life_plan_memory_proposal(
        proposal_id="p-1",
        affected_reference_ids=("ref-missing",),
    )
    binding = build_life_plan_memory_binding(
        proposal=proposal,
        view=view,
        trace_id="tr-1",
    )
    inventory = DomainMemoryReferenceInventory()
    val_res = validate_life_plan_memory_binding(binding=binding, inventory=inventory)
    assert val_res.is_valid is False
