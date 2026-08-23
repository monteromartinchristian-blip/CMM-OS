"""Tests for Phase 10.26 Languages Domain Memory Integration."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionApprovalRequirement,
    PermissionCapability,
)
from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.domains.approval_bridge import to_approval_requirement
from cmm.domains.enums import DomainOperationType
from cmm.domains.languages.definition import LANGUAGES_DOMAIN_ID
from cmm.domains.languages.memory import (
    build_languages_memory_binding,
    build_languages_memory_proposal,
    build_languages_memory_view,
    build_languages_memory_view_request,
    validate_languages_memory_binding,
)
from cmm.domains.languages.permissions import build_languages_permission_policy
from cmm.domains.memory_contracts import (
    DomainMemoryApprovalDecisionSnapshot,
    DomainMemoryApprovalRequestSnapshot,
    DomainMemoryCapability,
    DomainMemoryPermissionDecisionSnapshot,
    DomainMemoryProposalBinding,
    DomainMemoryProposalKind,
    DomainMemoryProposalSnapshot,
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
    DomainMemorySensitivityLevel,
    DomainMemoryTraceSnapshot,
    DomainMemoryViewSnapshot,
)
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.permission_gate import DomainPermissionGate, PermissionGateOutcome
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


def _reference(reference_id: str, canonical_id: str) -> DomainMemoryReference:
    return DomainMemoryReference(
        reference_id=reference_id,
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id=canonical_id,
        domain_id=LANGUAGES_DOMAIN_ID,
        applicable_domains=(LANGUAGES_DOMAIN_ID,),
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )


def test_build_languages_memory_view_request() -> None:
    """Verify standard view request builder for Languages."""
    ref = _reference("ref:1", "item:1")
    req = build_languages_memory_view_request(
        request_id="req-1",
        trace_id="tr-1",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
    )
    assert str(req.primary_domain) == LANGUAGES_DOMAIN_ID
    assert req.request_id == "req-1"
    assert req.trace_id == "tr-1"


def test_build_languages_memory_proposal_requires_confirmation() -> None:
    """Verify proposal-only memory creation: requires_confirmation is strictly True."""
    prop = build_languages_memory_proposal(
        proposal_id="prop-1",
        affected_reference_ids=("ref-1",),
    )
    assert isinstance(prop, DomainMemoryProposalSnapshot)
    assert prop.proposal_id == "prop-1"
    assert prop.proposal_kind is DomainMemoryProposalKind.MEMORY_UPDATE
    assert prop.requires_confirmation is True
    assert prop.required_capabilities == (DomainMemoryCapability.PROPOSE,)


def test_build_languages_memory_binding_structure() -> None:
    """Verify binding construction with digests."""
    ref = _reference("ref:1", "item:1")
    inventory = DomainMemoryReferenceInventory(references=(ref,))
    request = build_languages_memory_view_request(
        request_id="req-1",
        trace_id="trace-1",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
    )
    view = build_languages_memory_view(request=request, inventory=inventory)
    prop = build_languages_memory_proposal(proposal_id="prop-1")
    binding = build_languages_memory_binding(
        proposal=prop,
        view=view,
        trace_id="trace-1",
        permission_decision_ids=("p-1",),
    )
    assert isinstance(binding, DomainMemoryProposalBinding)
    assert str(binding.domain_id) == LANGUAGES_DOMAIN_ID
    assert binding.memory_proposal_ids == ("prop-1",)
    assert binding.view_id == view.view_id
    json.dumps(
        {
            "binding_id": binding.binding_id,
            "view_digest": binding.view_digest,
            "memory_proposal_ids": list(binding.memory_proposal_ids),
        },
        allow_nan=False,
    )


def test_full_chain_validation_and_no_private_memory_store() -> None:
    """Verify full approval chain validation and absence of private domain store."""
    proposal_id = "prop-lang-1"
    ref = _reference(f"ref:{proposal_id}", f"item:{proposal_id}")
    permission = DomainMemoryPermissionDecisionSnapshot(
        decision_id=f"perm:{proposal_id}",
        allowed=True,
        capabilities=(DomainMemoryCapability.PROPOSE,),
        source_domain_id=LANGUAGES_DOMAIN_ID,
        target_domain_id=LANGUAGES_DOMAIN_ID,
        sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
    )
    view_request = build_languages_memory_view_request(
        request_id=f"req:{proposal_id}",
        trace_id=f"trace:{proposal_id}",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
        permission_decision_ids=(f"perm:{proposal_id}",),
    )
    proposal = build_languages_memory_proposal(
        proposal_id=proposal_id,
        affected_reference_ids=(f"ref:{proposal_id}",),
    )
    temp_inventory = DomainMemoryReferenceInventory(
        references=(ref,),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id=f"trace:{proposal_id}", primary_domain=LANGUAGES_DOMAIN_ID
            ),
        ),
        permission_decisions=(permission,),
    )
    view = build_languages_memory_view(request=view_request, inventory=temp_inventory)
    binding = build_languages_memory_binding(
        proposal=proposal,
        view=view,
        trace_id=f"trace:{proposal_id}",
        permission_decision_ids=(f"perm:{proposal_id}",),
        approval_request_ids=(f"appr-req:{proposal_id}",),
        approval_decision_ids=(f"appr-dec:{proposal_id}",),
    )
    inventory = DomainMemoryReferenceInventory(
        references=(ref,),
        proposals=(proposal,),
        permission_decisions=(permission,),
        approval_requests=(
            DomainMemoryApprovalRequestSnapshot(
                request_id=f"appr-req:{proposal_id}", proposal_id=proposal_id
            ),
        ),
        approval_decisions=(
            DomainMemoryApprovalDecisionSnapshot(
                decision_id=f"appr-dec:{proposal_id}",
                request_id=f"appr-req:{proposal_id}",
                approved=True,
            ),
        ),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id=f"trace:{proposal_id}", primary_domain=LANGUAGES_DOMAIN_ID
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

    val_res = validate_languages_memory_binding(binding=binding, inventory=inventory)
    assert val_res.is_valid is True

    # Confirm no private memory store in domain package
    import cmm.domains.languages
    for forbidden in (
        "LanguageMemoryStore",
        "LanguagesMemoryStore",
        "LanguageMemoryRegistry",
        "LanguageMemoryEngine",
    ):
        assert not hasattr(cmm.domains.languages, forbidden)


def test_proposal_and_binding_do_not_consume_real_memory_write_approval() -> None:
    registry = DomainPermissionRegistry()
    registry.register(build_languages_permission_policy())
    service = ApprovalService(InMemoryApprovalRepository())
    gate = DomainPermissionGate(
        DomainPermissionResolver(registry), service, clock=lambda: NOW
    )
    operation = DomainOperationDefinition(
        operation_id="languages.test_memory_proposal_apply_boundary",
        domain_id=LANGUAGES_DOMAIN_ID,
        version="1.0.0",
        name="Test memory proposal apply boundary",
        description="Test-only operation for proposal/apply permission separation.",
        operation_type=DomainOperationType.ANALYSIS,
        required_permissions=(PermissionCapability.MEMORY_WRITE.value,),
        risk_level=PolicyRiskLevel.LOW,
        reversible=True,
    )
    pending = gate.evaluate_operation_definition(
        operation,
        request_id="languages-memory-proposal-1",
        actor_id="actor-1",
        session_id="session-1",
    )
    assert pending.outcome is PermissionGateOutcome.APPROVAL_REQUIRED
    requirement = PermissionApprovalRequirement.from_dict(
        pending.approval_requirements[0]
    )
    approval = service.create_request_from_requirement(
        to_approval_requirement(requirement, agent_run_id="run-languages-memory"),
        requested_by="agent-runtime",
    )
    service.approve(approval.id, "human-approver")

    proposal_id = "proposal-real-approval-1"
    reference = _reference(f"ref:{proposal_id}", f"item:{proposal_id}")
    trace_id = f"trace:{proposal_id}"
    memory_permission_id = f"permission:{proposal_id}"
    memory_permission = DomainMemoryPermissionDecisionSnapshot(
        decision_id=memory_permission_id,
        allowed=True,
        capabilities=(DomainMemoryCapability.PROPOSE,),
        source_domain_id=LANGUAGES_DOMAIN_ID,
        target_domain_id=LANGUAGES_DOMAIN_ID,
        sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
    )
    request = build_languages_memory_view_request(
        request_id=f"request:{proposal_id}",
        trace_id=trace_id,
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(reference,),
        permission_decision_ids=(memory_permission_id,),
    )
    base_inventory = DomainMemoryReferenceInventory(
        references=(reference,),
        traces=(DomainMemoryTraceSnapshot(trace_id=trace_id, primary_domain=LANGUAGES_DOMAIN_ID),),
        permission_decisions=(memory_permission,),
    )
    view = build_languages_memory_view(request=request, inventory=base_inventory)
    proposal = build_languages_memory_proposal(
        proposal_id=proposal_id, affected_reference_ids=(reference.reference_id,)
    )
    decision_id = service.repository.list_decisions(approval.id)[0].id
    binding = build_languages_memory_binding(
        proposal=proposal,
        view=view,
        trace_id=trace_id,
        permission_decision_ids=(memory_permission_id,),
        approval_request_ids=(approval.id,),
        approval_decision_ids=(decision_id,),
    )
    inventory = DomainMemoryReferenceInventory(
        references=(reference,),
        proposals=(proposal,),
        permission_decisions=(memory_permission,),
        approval_requests=(
            DomainMemoryApprovalRequestSnapshot(
                request_id=approval.id, proposal_id=proposal_id
            ),
        ),
        approval_decisions=(
            DomainMemoryApprovalDecisionSnapshot(
                decision_id=decision_id, request_id=approval.id, approved=True
            ),
        ),
        traces=(DomainMemoryTraceSnapshot(trace_id=trace_id, primary_domain=LANGUAGES_DOMAIN_ID),),
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

    assert proposal.requires_confirmation is True
    assert validate_languages_memory_binding(binding=binding, inventory=inventory).is_valid
    assert service.repository.is_consumed(approval.id) is False

    applied = gate.evaluate_operation_definition(
        operation,
        request_id="languages-memory-proposal-1",
        actor_id="actor-1",
        session_id="session-1",
        approval_request_id=approval.id,
    )
    assert applied.outcome is PermissionGateOutcome.APPROVAL_CONSUMED
    assert applied.allowed
    assert service.repository.is_consumed(approval.id) is True
