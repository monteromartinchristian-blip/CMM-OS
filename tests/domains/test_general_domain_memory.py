"""Tests for General Domain memory integration."""

from __future__ import annotations

from cmm.domains.general import (
    build_general_goal_binding,
    build_general_goal_proposal,
    build_general_memory_view,
    build_general_memory_view_request,
    build_general_task_binding,
    build_general_task_proposal,
    validate_general_memory_binding,
)
from cmm.domains.memory_contracts import (
    DomainMemoryCapability,
    DomainMemoryProposalBinding,
    DomainMemoryProposalKind,
    DomainMemoryProposalSnapshot,
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
    DomainMemoryValidationCode,
    DomainMemoryView,
    DomainMemoryViewRequest,
)
from cmm.domains.memory_validation import DefaultDomainMemoryIntegrationValidator


def _reference(reference_id: str, canonical_id: str) -> DomainMemoryReference:
    return DomainMemoryReference(
        reference_id=reference_id,
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id=canonical_id,
        domain_id="domain:general",
        applicable_domains=("domain:general",),
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )


def _inventory(*references: DomainMemoryReference) -> DomainMemoryReferenceInventory:
    return DomainMemoryReferenceInventory(references=references)


def test_memory_view_request_built():
    request = build_general_memory_view_request(request_id="req1")
    assert isinstance(request, DomainMemoryViewRequest)
    assert request.primary_domain.slug == "general"


def test_memory_view_request_domain():
    request = build_general_memory_view_request(request_id="req1")
    assert str(request.primary_domain) == "domain:general"


def test_task_proposal_built():
    proposal = build_general_task_proposal(proposal_id="prop1")
    assert isinstance(proposal, DomainMemoryProposalSnapshot)
    assert proposal.proposal_kind is DomainMemoryProposalKind.MEMORY_UPDATE
    assert DomainMemoryCapability.PROPOSE in proposal.required_capabilities


def test_task_proposal_requires_confirmation():
    proposal = build_general_task_proposal(proposal_id="prop1")
    assert proposal.requires_confirmation is True


def test_goal_proposal_built():
    proposal = build_general_goal_proposal(proposal_id="prop2")
    assert isinstance(proposal, DomainMemoryProposalSnapshot)
    assert proposal.proposal_kind is DomainMemoryProposalKind.MEMORY_UPDATE


def test_goal_proposal_requires_confirmation():
    proposal = build_general_goal_proposal(proposal_id="prop2")
    assert proposal.requires_confirmation is True


def test_proposals_are_reference_only():
    proposal = build_general_task_proposal(proposal_id="prop1")
    # No payload, no content
    assert not hasattr(proposal, "payload")
    assert not hasattr(proposal, "content")


def test_proposals_never_applied_directly():
    # Proposals are snapshots; they don't have an apply method
    proposal = build_general_task_proposal(proposal_id="prop1")
    assert not hasattr(proposal, "apply")


def test_no_separate_memory():
    # General Domain uses the common memory contracts
    from cmm.domains.memory_contracts import DomainMemoryViewRequest

    assert DomainMemoryViewRequest is not None


def test_proposal_deterministic():
    a = build_general_task_proposal(proposal_id="prop1")
    b = build_general_task_proposal(proposal_id="prop1")
    assert a.to_dict() == b.to_dict()


def test_memory_view_resolved():
    """A memory view is resolved via the canonical resolver."""
    ref = _reference("ref:1", "item:1")
    request = build_general_memory_view_request(
        request_id="req1",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
    )
    view = build_general_memory_view(request=request, inventory=_inventory(ref))
    assert isinstance(view, DomainMemoryView)
    assert view.primary_domain.slug == "general"


def test_task_binding_built():
    """A task proposal binding uses the real DomainMemoryProposalBinding contract."""
    ref = _reference("ref:1", "item:1")
    request = build_general_memory_view_request(
        request_id="req1",
        trace_id="trace1",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
    )
    view = build_general_memory_view(request=request, inventory=_inventory(ref))
    proposal = build_general_task_proposal(
        proposal_id="prop1", affected_reference_ids=("ref:1",)
    )
    binding = build_general_task_binding(
        proposal=proposal,
        view=view,
        trace_id="trace1",
    )
    assert isinstance(binding, DomainMemoryProposalBinding)
    assert binding.domain_id.slug == "general"
    assert binding.trace_id == "trace1"
    assert binding.view_id == view.view_id
    assert binding.view_digest == view.content_digest
    assert binding.memory_proposal_ids == ("prop1",)
    assert binding.affected_reference_ids == ("ref:1",)


def test_goal_binding_built():
    """A goal proposal binding uses the real DomainMemoryProposalBinding contract."""
    ref = _reference("ref:1", "item:1")
    request = build_general_memory_view_request(
        request_id="req1",
        trace_id="trace1",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
    )
    view = build_general_memory_view(request=request, inventory=_inventory(ref))
    proposal = build_general_goal_proposal(
        proposal_id="prop2", affected_reference_ids=("ref:1",)
    )
    binding = build_general_goal_binding(
        proposal=proposal,
        view=view,
        trace_id="trace1",
    )
    assert isinstance(binding, DomainMemoryProposalBinding)
    assert binding.memory_proposal_ids == ("prop2",)


def test_binding_round_trip():
    """A binding serializes and deserializes without loss."""
    ref = _reference("ref:1", "item:1")
    request = build_general_memory_view_request(
        request_id="req1",
        trace_id="trace1",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
    )
    view = build_general_memory_view(request=request, inventory=_inventory(ref))
    proposal = build_general_task_proposal(
        proposal_id="prop1", affected_reference_ids=("ref:1",)
    )
    binding = build_general_task_binding(
        proposal=proposal,
        view=view,
        trace_id="trace1",
    )
    restored = DomainMemoryProposalBinding.from_dict(binding.to_dict())
    assert restored == binding


def test_binding_validates_with_inventory():
    """A binding validates against a canonical inventory."""
    ref = _reference("ref:1", "item:1")
    request = build_general_memory_view_request(
        request_id="req1",
        trace_id="trace1",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
    )
    view = build_general_memory_view(request=request, inventory=_inventory(ref))
    proposal = build_general_task_proposal(
        proposal_id="prop1", affected_reference_ids=("ref:1",)
    )
    binding = build_general_task_binding(
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
                source_domain_id="domain:general",
                target_domain_id="domain:general",
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
                trace_id="trace1", primary_domain="domain:general"
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
    validator = DefaultDomainMemoryIntegrationValidator()
    result = validator.validate_binding(binding, inventory)
    assert result.is_valid is True


def _full_parts():
    """Build a reference/view/proposal/binding triad for a task proposal."""
    ref = _reference("ref:1", "item:1")
    request = build_general_memory_view_request(
        request_id="req1",
        trace_id="trace1",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
    )
    view = build_general_memory_view(request=request, inventory=_inventory(ref))
    proposal = build_general_task_proposal(
        proposal_id="prop1", affected_reference_ids=("ref:1",)
    )
    binding = build_general_task_binding(
        proposal=proposal,
        view=view,
        trace_id="trace1",
        permission_decision_ids=("perm:1",),
        approval_request_ids=("appr:1",),
        approval_decision_ids=("appd:1",),
    )
    return ref, view, proposal, binding


def _canonical_inventory(
    ref: DomainMemoryReference,
    view: DomainMemoryView,
    proposal: DomainMemoryProposalSnapshot,
    *,
    include_permission: bool = True,
    include_approval: bool = True,
    include_trace: bool = True,
    include_view: bool = True,
) -> DomainMemoryReferenceInventory:
    """Build a canonical binding inventory, optionally omitting parts."""
    from cmm.domains.memory_contracts import (
        DomainMemoryApprovalDecisionSnapshot,
        DomainMemoryApprovalRequestSnapshot,
        DomainMemoryPermissionDecisionSnapshot,
        DomainMemoryTraceSnapshot,
        DomainMemoryViewSnapshot,
    )

    return DomainMemoryReferenceInventory(
        references=(ref,),
        proposals=(proposal,),
        permission_decisions=(
            (
                DomainMemoryPermissionDecisionSnapshot(
                    decision_id="perm:1",
                    allowed=True,
                    capabilities=(DomainMemoryCapability.PROPOSE,),
                    source_domain_id="domain:general",
                    target_domain_id="domain:general",
                ),
            )
            if include_permission
            else ()
        ),
        approval_requests=(
            (
                DomainMemoryApprovalRequestSnapshot(
                    request_id="appr:1", proposal_id="prop1"
                ),
            )
            if include_approval
            else ()
        ),
        approval_decisions=(
            (
                DomainMemoryApprovalDecisionSnapshot(
                    decision_id="appd:1", request_id="appr:1", approved=True
                ),
            )
            if include_approval
            else ()
        ),
        traces=(
            (
                DomainMemoryTraceSnapshot(
                    trace_id="trace1", primary_domain="domain:general"
                ),
            )
            if include_trace
            else ()
        ),
        views=(
            (
                DomainMemoryViewSnapshot(
                    view_id=view.view_id,
                    request_id=view.request_id,
                    primary_domain=view.primary_domain,
                    trace_id=view.trace_id,
                    view_digest=view.content_digest,
                ),
            )
            if include_view
            else ()
        ),
    )


def test_binding_id_ends_with_content_digest_prefix():
    """The canonical binding suffix equals content_digest[:12]."""
    _, _, _, binding = _full_parts()
    assert binding.binding_id.endswith(binding.content_digest[:12])


def test_binding_view_digest_matches_view_content():
    """view_digest is content-bound to the resolved view."""
    _, view, _, binding = _full_parts()
    assert binding.view_digest == view.content_digest


def test_binding_valid_with_full_inventory():
    """A binding with a complete canonical inventory validates as VALID."""
    ref, view, proposal, binding = _full_parts()
    inventory = _canonical_inventory(ref, view, proposal)
    result = validate_general_memory_binding(binding=binding, inventory=inventory)
    assert result.is_valid is True
    assert result.code is DomainMemoryValidationCode.VALID


def test_binding_invalid_when_permission_missing():
    """A referenced permission decision absent from the inventory is INVALID."""
    ref, view, proposal, binding = _full_parts()
    inventory = _canonical_inventory(
        ref, view, proposal, include_permission=False
    )
    result = validate_general_memory_binding(binding=binding, inventory=inventory)
    assert result.is_valid is False
    assert result.code is DomainMemoryValidationCode.INVALID_PERMISSION_DENIED


def test_binding_invalid_when_trace_missing():
    """A referenced trace absent from the inventory is INVALID."""
    ref, view, proposal, binding = _full_parts()
    inventory = _canonical_inventory(ref, view, proposal, include_trace=False)
    result = validate_general_memory_binding(binding=binding, inventory=inventory)
    assert result.is_valid is False
    assert result.code is DomainMemoryValidationCode.INVALID_TRACE_VIEW_MISMATCH


def test_binding_invalid_when_approval_chain_missing():
    """A confirmation-required proposal without an approval chain is INVALID."""
    ref, view, proposal, binding = _full_parts()
    inventory = _canonical_inventory(ref, view, proposal, include_approval=False)
    result = validate_general_memory_binding(binding=binding, inventory=inventory)
    assert result.is_valid is False
    assert result.code is DomainMemoryValidationCode.INVALID_APPROVAL_REQUIRED


def test_binding_valid_with_canonical_approval_chain():
    """A complete canonical approval chain keeps the binding VALID."""
    ref, view, proposal, binding = _full_parts()
    inventory = _canonical_inventory(ref, view, proposal)
    result = validate_general_memory_binding(binding=binding, inventory=inventory)
    assert result.is_valid is True
    assert result.code is DomainMemoryValidationCode.VALID