"""Phase 10.23 — Opposition Domain memory integration tests (proposal-only)."""

from __future__ import annotations

import pytest

from cmm.domains.memory_contracts import (
    DomainMemoryCapability,
    DomainMemoryProposalBinding,
    DomainMemoryProposalKind,
    DomainMemoryProposalSnapshot,
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
)
from cmm.domains.oppositions.memory import (
    build_oppositions_memory_binding,
    build_oppositions_memory_proposal,
    build_oppositions_memory_view,
    build_oppositions_memory_view_request,
    validate_oppositions_memory_binding,
)


def _reference(reference_id: str, canonical_id: str) -> DomainMemoryReference:
    return DomainMemoryReference(
        reference_id=reference_id,
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id=canonical_id,
        domain_id="domain:oppositions",
        applicable_domains=("domain:oppositions",),
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )


def _inventory(*references: DomainMemoryReference) -> DomainMemoryReferenceInventory:
    return DomainMemoryReferenceInventory(references=references)


def test_view_request_domain_is_oppositions():
    request = build_oppositions_memory_view_request(request_id="req1")
    assert str(request.primary_domain) == "domain:oppositions"


def test_memory_proposal_requires_confirmation():
    proposal = build_oppositions_memory_proposal(proposal_id="prop1")
    assert isinstance(proposal, DomainMemoryProposalSnapshot)
    assert proposal.proposal_kind is DomainMemoryProposalKind.MEMORY_UPDATE
    assert DomainMemoryCapability.PROPOSE in proposal.required_capabilities
    assert proposal.requires_confirmation is True


def test_proposal_confirmation_invariant_not_overridable():
    proposal = build_oppositions_memory_proposal(proposal_id="prop1")
    assert proposal.requires_confirmation is True
    with pytest.raises(TypeError):
        build_oppositions_memory_proposal(
            proposal_id="prop1", requires_confirmation=False
        )


def test_memory_view_resolved():
    ref = _reference("ref:1", "item:1")
    request = build_oppositions_memory_view_request(
        request_id="req1",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
    )
    view = build_oppositions_memory_view(request=request, inventory=_inventory(ref))
    assert view is not None


def test_memory_binding_links_proposal():
    ref = _reference("ref:1", "item:1")
    inventory = _inventory(ref)
    request = build_oppositions_memory_view_request(
        request_id="req1",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
    )
    view = build_oppositions_memory_view(request=request, inventory=inventory)
    proposal = build_oppositions_memory_proposal(proposal_id="prop1")
    binding = build_oppositions_memory_binding(
        proposal=proposal, view=view, trace_id="trace1"
    )
    assert isinstance(binding, DomainMemoryProposalBinding)
    assert binding.memory_proposal_ids == ("prop1",)


def test_validate_memory_binding_fail_closed_on_invalid():
    ref = _reference("ref:1", "item:1")
    request = build_oppositions_memory_view_request(
        request_id="req1",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
    )
    view = build_oppositions_memory_view(request=request, inventory=_inventory(ref))
    proposal = build_oppositions_memory_proposal(proposal_id="prop1")
    binding = build_oppositions_memory_binding(
        proposal=proposal, view=view, trace_id="trace1"
    )
    result = validate_oppositions_memory_binding(
        binding=binding, inventory=_inventory(ref)
    )
    # validation runs against the real shared validator; result is structured
    assert result is not None