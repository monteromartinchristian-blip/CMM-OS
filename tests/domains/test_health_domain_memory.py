"""Tests for Phase 10.20 Health Domain memory integration (proposal-only)."""

from __future__ import annotations

import pytest

from cmm.domains.health.memory import (
    build_health_memory_view,
    build_health_memory_view_request,
    build_health_symptom_binding,
    build_health_symptom_proposal,
    validate_health_memory_binding,
)
from cmm.domains.memory_contracts import (
    DomainMemoryCapability,
    DomainMemoryProposalBinding,
    DomainMemoryProposalKind,
    DomainMemoryProposalSnapshot,
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
)


def _reference(reference_id: str, canonical_id: str) -> DomainMemoryReference:
    return DomainMemoryReference(
        reference_id=reference_id,
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id=canonical_id,
        domain_id="domain:health",
        applicable_domains=("domain:health",),
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )


def _inventory(*references: DomainMemoryReference) -> DomainMemoryReferenceInventory:
    return DomainMemoryReferenceInventory(references=references)


def test_view_request_domain_is_health():
    request = build_health_memory_view_request(request_id="req1")
    assert str(request.primary_domain) == "domain:health"


def test_symptom_proposal_requires_confirmation():
    proposal = build_health_symptom_proposal(proposal_id="prop1")
    assert isinstance(proposal, DomainMemoryProposalSnapshot)
    assert proposal.proposal_kind is DomainMemoryProposalKind.MEMORY_UPDATE
    assert DomainMemoryCapability.PROPOSE in proposal.required_capabilities
    assert proposal.requires_confirmation is True


def test_symptom_proposal_confirmation_invariant_not_overridable():
    """Sensitive Health memory must always require confirmation.

    A caller must not be able to opt out of confirmation for a symptom
    proposal (see the profile's unconfirmed_sensitive_memory_persistence
    prohibition).  The builder exposes no override: passing
    ``requires_confirmation`` is rejected.
    """
    proposal = build_health_symptom_proposal(proposal_id="prop1")
    assert proposal.requires_confirmation is True
    with pytest.raises(TypeError):
        build_health_symptom_proposal(
            proposal_id="prop1", requires_confirmation=False
        )


def test_proposal_is_reference_only_and_never_applied():
    proposal = build_health_symptom_proposal(proposal_id="prop1")
    assert not hasattr(proposal, "payload")
    assert not hasattr(proposal, "apply")


def test_memory_view_resolved():
    ref = _reference("ref:1", "item:1")
    request = build_health_memory_view_request(
        request_id="req1",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
    )
    view = build_health_memory_view(request=request, inventory=_inventory(ref))
    assert view.primary_domain.slug == "health"


def test_symptom_binding_built():
    ref = _reference("ref:1", "item:1")
    request = build_health_memory_view_request(
        request_id="req1",
        trace_id="trace1",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
    )
    view = build_health_memory_view(request=request, inventory=_inventory(ref))
    proposal = build_health_symptom_proposal(
        proposal_id="prop1", affected_reference_ids=("ref:1",)
    )
    binding = build_health_symptom_binding(
        proposal=proposal, view=view, trace_id="trace1"
    )
    assert isinstance(binding, DomainMemoryProposalBinding)
    assert binding.domain_id.slug == "health"
    assert binding.memory_proposal_ids == ("prop1",)
    assert binding.view_digest == view.content_digest


def test_binding_serialization_round_trip():
    ref = _reference("ref:1", "item:1")
    request = build_health_memory_view_request(
        request_id="req1",
        trace_id="trace1",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
    )
    view = build_health_memory_view(request=request, inventory=_inventory(ref))
    proposal = build_health_symptom_proposal(
        proposal_id="prop1", affected_reference_ids=("ref:1",)
    )
    binding = build_health_symptom_binding(
        proposal=proposal, view=view, trace_id="trace1"
    )
    restored = DomainMemoryProposalBinding.from_dict(binding.to_dict())
    assert restored == binding


def test_binding_validates_against_inventory():
    ref = _reference("ref:1", "item:1")
    request = build_health_memory_view_request(
        request_id="req1",
        trace_id="trace1",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
    )
    view = build_health_memory_view(request=request, inventory=_inventory(ref))
    proposal = build_health_symptom_proposal(
        proposal_id="prop1", affected_reference_ids=("ref:1",)
    )
    binding = build_health_symptom_binding(
        proposal=proposal,
        view=view,
        trace_id="trace1",
        permission_decision_ids=("perm:1",),
        approval_request_ids=("appr:1",),
        approval_decision_ids=("appd:1",),
    )
    from cmm.domains.memory_contracts import (
        DomainMemoryApprovalDecisionSnapshot,
        DomainMemoryApprovalRequestSnapshot,
        DomainMemoryPermissionDecisionSnapshot,
        DomainMemoryTraceSnapshot,
        DomainMemoryViewSnapshot,
    )

    inventory = DomainMemoryReferenceInventory(
        references=(ref,),
        proposals=(proposal,),
        permission_decisions=(
            DomainMemoryPermissionDecisionSnapshot(
                decision_id="perm:1",
                allowed=True,
                capabilities=(DomainMemoryCapability.PROPOSE,),
                source_domain_id="domain:health",
                target_domain_id="domain:health",
            ),
        ),
        approval_requests=(
            DomainMemoryApprovalRequestSnapshot(
                request_id="appr:1", proposal_id="prop1"
            ),
        ),
        approval_decisions=(
            DomainMemoryApprovalDecisionSnapshot(
                decision_id="appd:1", request_id="appr:1", approved=True
            ),
        ),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id="trace1", primary_domain="domain:health"
            ),
        ),
        views=(
            DomainMemoryViewSnapshot(
                view_id=view.view_id,
                request_id=view.request_id,
                primary_domain=view.primary_domain,
                trace_id=view.trace_id,
                view_digest=view.content_digest,
            ),
        ),
    )
    result = validate_health_memory_binding(binding=binding, inventory=inventory)
    assert result.is_valid is True
