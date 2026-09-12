"""Phase 10.52 — Mental Health memory, trace and presentation boundary tests.

Sensitive inference is never persisted implicitly: proposals are
confirmation-gated through the shared Phase 10.18 contracts, a malformed or
unauthorized affected-reference inventory fails closed, no Mental Health memory
store exists, and the Domain trace stays reference-only.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from cmm.domains.memory_contracts import (
    DomainMemoryApprovalDecisionSnapshot,
    DomainMemoryApprovalRequestSnapshot,
    DomainMemoryCapability,
    DomainMemoryPermissionDecisionSnapshot,
    DomainMemoryProposalBinding,
    DomainMemoryProposalKind,
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
    DomainMemorySensitivityLevel,
    DomainMemoryTraceSnapshot,
    DomainMemoryViewSnapshot,
)
from cmm.domains.mental_health.memory import (
    MentalHealthMemoryPolicyError,
    build_mental_health_memory_binding,
    build_mental_health_memory_proposal,
    build_mental_health_memory_view,
    build_mental_health_memory_view_request,
    validate_mental_health_memory_binding,
)
from cmm.domains.mental_health.presentation import (
    build_mental_health_presentation_policy,
)
from cmm.domains.mental_health.trace import (
    assemble_mental_health_trace,
    build_mental_health_trace_contribution,
    build_mental_health_trace_reference,
    validate_mental_health_trace,
)
from cmm.domains.trace_contracts import (
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)
DOMAIN = "domain:mental-health"


def _reference(reference_id: str, canonical_id: str) -> DomainMemoryReference:
    return DomainMemoryReference(
        reference_id=reference_id,
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id=canonical_id,
        domain_id=DOMAIN,
        applicable_domains=(DOMAIN,),
        evidence_ids=("ev:mh:1",),
        resource_ids=("mental_health.conversation",),
    )


# ── Presentation ─────────────────────────────────────────────────────────────


def test_ordinary_presentation_is_non_clinical_and_uncertainty_visible():
    policy = build_mental_health_presentation_policy()
    assert policy.include_uncertainty is True
    assert policy.include_provenance is True
    assert policy.allow_speculation is False
    assert "understanding" in policy.required_sections
    assert "interpretations" in policy.required_sections
    # No clinical or diagnostic section is ever required by default.
    joined = " ".join(policy.required_sections + policy.optional_sections)
    assert "diagnosis" not in joined
    assert "clinical" not in joined


def test_presentation_protects_epistemic_and_provenance_terms():
    policy = build_mental_health_presentation_policy()
    for term in (
        "interpretation",
        "uncertainty",
        "provenance",
        "therapist_statement",
        "user_statement",
        "model_interpretation",
    ):
        assert term in policy.protected_terms


# ── Memory ───────────────────────────────────────────────────────────────────


def test_proposal_is_memory_update_and_confirmation_gated():
    proposal = build_mental_health_memory_proposal(proposal_id="mp-mh-1")
    assert proposal.proposal_kind is DomainMemoryProposalKind.MEMORY_UPDATE
    assert proposal.requires_confirmation is True
    assert proposal.required_capabilities == (DomainMemoryCapability.PROPOSE,)


def test_restricted_sensitive_content_is_never_proposable():
    for content_kind in (
        "fear",
        "intuition",
        "inferred_emotional_pattern",
        "emotional_loop",
        "psychological_interpretation",
        "third_party_motive",
    ):
        with pytest.raises(MentalHealthMemoryPolicyError):
            build_mental_health_memory_proposal(
                proposal_id="mp-mh-x", content_kind=content_kind
            )


def test_view_request_is_domain_scoped():
    ref = _reference("ref:mh:1", "item:mh:1")
    request = build_mental_health_memory_view_request(
        request_id="req-mh-1",
        trace_id="trace-mh-1",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
    )
    assert str(request.primary_domain) == DOMAIN
    inventory = DomainMemoryReferenceInventory(references=(ref,))
    view = build_mental_health_memory_view(request=request, inventory=inventory)
    assert str(view.primary_domain) == DOMAIN


def _full_chain(proposal_id: str):
    """Build a complete canonical proposal chain (binding + inventory)."""
    trace_id = f"trace:{proposal_id}"
    ref = _reference(f"ref:{proposal_id}", f"item:{proposal_id}")
    permission = DomainMemoryPermissionDecisionSnapshot(
        decision_id=f"perm:{proposal_id}",
        allowed=True,
        capabilities=(DomainMemoryCapability.PROPOSE,),
        source_domain_id=DOMAIN,
        target_domain_id=DOMAIN,
        sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
    )
    view_request = build_mental_health_memory_view_request(
        request_id=f"req:{proposal_id}",
        trace_id=trace_id,
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
        permission_decision_ids=(f"perm:{proposal_id}",),
    )
    proposal = build_mental_health_memory_proposal(
        proposal_id=proposal_id,
        affected_reference_ids=(f"ref:{proposal_id}",),
    )
    temp_inventory = DomainMemoryReferenceInventory(
        references=(ref,),
        traces=(DomainMemoryTraceSnapshot(trace_id=trace_id, primary_domain=DOMAIN),),
        permission_decisions=(permission,),
    )
    view = build_mental_health_memory_view(
        request=view_request, inventory=temp_inventory
    )
    binding = build_mental_health_memory_binding(
        proposal=proposal,
        view=view,
        trace_id=trace_id,
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
        traces=(DomainMemoryTraceSnapshot(trace_id=trace_id, primary_domain=DOMAIN),),
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
    return binding, inventory, view, proposal


def test_read_propose_approve_apply_are_distinct_and_no_direct_write():
    binding, inventory, view, proposal = _full_chain("mp-mh-2")

    # The canonical validator accepts the complete reference-only chain.
    result = validate_mental_health_memory_binding(binding=binding, inventory=inventory)
    assert result.is_valid is True

    # Reading/proposing produced a proposal only: never a direct mutation.
    assert proposal.requires_confirmation is True
    assert DomainMemoryCapability.APPLY not in proposal.required_capabilities
    assert DomainMemoryCapability.DELETE not in proposal.required_capabilities
    assert binding.memory_proposal_ids == ("mp-mh-2",)
    assert binding.view_id == view.view_id
    # READ != PROPOSE != APPLY: only the PROPOSE capability is required and the
    # binding carries references, never applied mutation state.
    assert proposal.required_capabilities == (DomainMemoryCapability.PROPOSE,)
    assert binding.approval_request_ids == ("appr-req:mp-mh-2",)
    assert binding.approval_decision_ids == ("appr-dec:mp-mh-2",)


def test_malformed_or_unauthorized_inventory_fails_closed():
    binding, inventory, _view, _proposal = _full_chain("mp-mh-3")
    # Drop the view snapshot: the binding's view cannot be verified.
    malformed = DomainMemoryReferenceInventory(
        references=inventory.references,
        proposals=inventory.proposals,
        permission_decisions=inventory.permission_decisions,
        approval_requests=inventory.approval_requests,
        approval_decisions=inventory.approval_decisions,
        traces=inventory.traces,
    )
    result = validate_mental_health_memory_binding(binding=binding, inventory=malformed)
    assert result.is_valid is False


def test_unauthorized_affected_reference_fails_closed():
    binding, inventory, _view, _proposal = _full_chain("mp-mh-4")
    # An inventory without the declared proposal coverage fails closed, so an
    # unauthorized or malformed affected-reference inventory cannot validate.
    unauthorized = DomainMemoryReferenceInventory(
        references=inventory.references,
        permission_decisions=inventory.permission_decisions,
        approval_requests=inventory.approval_requests,
        approval_decisions=inventory.approval_decisions,
        traces=inventory.traces,
        views=inventory.views,
    )
    result = validate_mental_health_memory_binding(
        binding=binding, inventory=unauthorized
    )
    assert result.is_valid is False


def test_unknown_permission_decision_fails_closed():
    binding, inventory, _view, _proposal = _full_chain("mp-mh-6")
    # Dropping the declared permission decision makes the chain unauthorized.
    unauthorized = DomainMemoryReferenceInventory(
        references=inventory.references,
        proposals=inventory.proposals,
        approval_requests=inventory.approval_requests,
        approval_decisions=inventory.approval_decisions,
        traces=inventory.traces,
        views=inventory.views,
    )
    result = validate_mental_health_memory_binding(
        binding=binding, inventory=unauthorized
    )
    assert result.is_valid is False


def test_binding_contract_rejects_tampered_content_digest():
    from cmm.domains.errors import DomainMemoryContractError

    binding, _inventory, _view, _proposal = _full_chain("mp-mh-5")
    with pytest.raises(DomainMemoryContractError):
        DomainMemoryProposalBinding(
            binding_id=binding.binding_id,
            domain_id=binding.domain_id,
            trace_id=binding.trace_id,
            view_id=binding.view_id,
            view_digest=binding.view_digest,
            memory_proposal_ids=binding.memory_proposal_ids,
            affected_reference_ids=("ref:tampered",),
            permission_decision_ids=binding.permission_decision_ids,
        )


# ── Trace ────────────────────────────────────────────────────────────────────


def test_trace_is_reference_only_and_domain_scoped():
    ref = build_mental_health_trace_reference(
        ref_id="mental_health.trace.ref:1",
        kind=DomainTraceReferenceKind.DOMAIN_RESULT,
    )
    assert ref.ref_id == "mental_health.trace.ref:1"
    contribution = build_mental_health_trace_contribution(
        domain_result_id="result:mh:1"
    )
    assert str(contribution.domain_id) == DOMAIN
    # The trace carries references; it never carries transcript content.
    serialized = json.dumps(contribution.to_dict(), sort_keys=True)
    assert "transcript" not in serialized
    assert "chain_of_thought" not in serialized


def test_assembled_trace_exposes_resolution_and_result_pairings():
    trace = assemble_mental_health_trace(
        request_id="trace-req:1",
        resolution_context_id="ctx:1",
        resolution_result_id="resolution:1",
        composition_id="composition:1",
        domain_result_id="result:mh:1",
        started_at=NOW,
        completed_at=NOW,
    )
    assert str(trace.primary_domain) == DOMAIN
    assert trace.references.resolution_context_id == "ctx:1"
    assert trace.references.composition_id == "composition:1"
    assert any(
        str(reference.result_id) == "result:mh:1" for reference in trace.domain_results
    )
    assert "transcript" not in json.dumps(trace.to_dict(), sort_keys=True)


def test_trace_validation_uses_canonical_validator():
    from cmm.domains.trace_contracts import DomainTraceDomainSelection

    trace = assemble_mental_health_trace(
        request_id="trace-req:2",
        resolution_context_id="ctx:2",
        resolution_result_id="resolution:2",
        composition_id="composition:2",
        domain_result_id="result:mh:2",
        started_at=NOW,
        completed_at=NOW,
    )
    inventory = DomainTraceReferenceInventory(
        references=trace.all_references(),
        domain_results=trace.domain_results,
        expected_primary_domain=DOMAIN,
        resolution_result_domains=DomainTraceDomainSelection(
            "resolution:2", DOMAIN, ()
        ),
        composition_domains=DomainTraceDomainSelection("composition:2", DOMAIN, ()),
    )
    result = validate_mental_health_trace(trace=trace, inventory=inventory)
    assert result.valid is True


# ── Persistence discipline (Task 9) ──────────────────────────────────────────


def test_discussing_sensitive_inference_performs_no_mutation():
    """Talking about an inference is not authorization to persist it."""
    from datetime import datetime, timezone

    from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
    from cmm.domains.mental_health.rules import (
        build_mental_health_rules,
        is_persistence_restricted_content,
        persistence_is_authorized,
    )

    assert is_persistence_restricted_content("inferred_emotional_pattern") is True
    # Repetition, intensity or certainty are never authorization.
    for authorization in (True, 1, "approved", {"approved": True}, None):
        assert persistence_is_authorized(authorization) is False

    rules = {rule.definition.id: rule for rule in build_mental_health_rules()}
    rule = rules["mental_health.sensitive_persistence_control"]
    context = ReasoningRuleContext(
        reasoning_id="rid",
        timestamp=datetime(2026, 8, 1, tzinfo=timezone.utc),
        active_domains=(DOMAIN,),
        primary_domain=DOMAIN,
        metadata={
            "persistence_request": {
                "content_kind": "inferred_emotional_pattern",
                "authorization": None,
                "repetition_count": 9,
            }
        },
    )
    result = rule.evaluate(context)
    assert result.status.value == "blocked"
    assert result.metadata["direct_write_performed"] is False
    assert result.metadata["proposal_required"] is True


def test_proposal_remains_a_proposal_until_canonical_approval():
    binding, inventory, _view, proposal = _full_chain("mp-mh-9")
    # Before approval the chain is incomplete and the proposal is not applied.
    assert proposal.requires_confirmation is True

    without_approval = DomainMemoryReferenceInventory(
        references=inventory.references,
        proposals=inventory.proposals,
        permission_decisions=inventory.permission_decisions,
        traces=inventory.traces,
        views=inventory.views,
    )
    result = validate_mental_health_memory_binding(
        binding=binding, inventory=without_approval
    )
    assert result.is_valid is False

    # With the canonical approval chain the binding validates, and it still
    # carries only references — never applied mutation state.
    approved = validate_mental_health_memory_binding(
        binding=binding, inventory=inventory
    )
    assert approved.is_valid is True
    assert binding.memory_proposal_ids == ("mp-mh-9",)
