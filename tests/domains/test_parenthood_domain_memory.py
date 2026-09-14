"""Tests for Phase 10.27 Parenthood Domain Memory Integration."""

from __future__ import annotations

from typing import ClassVar

from cmm.domains.memory_contracts import (
    DomainMemoryCapability,
    DomainMemoryProposalKind,
    DomainMemoryValidationCode,
)
from cmm.domains.parenthood.memory import (
    CANDIDATE_LONGITUDINAL_KINDS,
    build_parenthood_memory_proposal,
    build_parenthood_memory_view_request,
    validate_parenthood_memory_binding,
)


def test_parenthood_memory_candidate_kinds() -> None:
    """Verify candidate longitudinal memory kinds for parenthood."""
    assert "parenthood_goal" in CANDIDATE_LONGITUDINAL_KINDS
    assert "explicit_decision" in CANDIDATE_LONGITUDINAL_KINDS
    assert "developmental_milestone" in CANDIDATE_LONGITUDINAL_KINDS
    assert "authorized_journey_transfer" in CANDIDATE_LONGITUDINAL_KINDS


def test_build_parenthood_memory_proposal_is_proposal_only() -> None:
    """Verify memory proposal has requires_confirmation=True and no direct write."""
    prop = build_parenthood_memory_proposal(
        proposal_id="prop-001",
        affected_reference_ids=("ref-1", "ref-2"),
    )
    assert prop.proposal_id == "prop-001"
    assert prop.requires_confirmation is True
    assert prop.proposal_kind is DomainMemoryProposalKind.MEMORY_UPDATE
    assert DomainMemoryCapability.PROPOSE in prop.required_capabilities


def test_build_parenthood_memory_view_request() -> None:
    """Verify building view request for domain:parenthood."""
    req = build_parenthood_memory_view_request(
        request_id="req-001",
        trace_id="trace-001",
    )
    assert req.request_id == "req-001"
    assert str(req.primary_domain) == "domain:parenthood"


def test_validate_parenthood_memory_binding_child_scope_mismatch() -> None:
    """Verify memory binding validation rejects sibling child_id mismatch."""

    class MockBinding:
        domain_id = "domain:parenthood"
        memory_proposal_ids = ("prop-001",)
        trace_id = "trace-001"
        view_id = "view-001"
        metadata: ClassVar[dict[str, str]] = {"child_id": "child:001"}

    class MockInventory:
        approval_requests = ()
        approval_decisions = ()

    result = validate_parenthood_memory_binding(
        binding=MockBinding(),
        inventory=MockInventory(),
        child_id="child:002",
    )
    assert result.is_valid is False
    assert result.code is DomainMemoryValidationCode.INVALID_PERMISSION_UNSCOPED
