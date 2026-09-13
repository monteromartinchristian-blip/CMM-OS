"""Phase 10.53 — Neurodivergence memory, trace and presentation boundary tests.

A working hypothesis may be discussed and organized freely inside the current
reasoning context; it is never persisted silently.  Proposals are
confirmation-gated through the shared Phase 10.18 contracts, a malformed or
unauthorized affected-reference inventory fails closed, no Neurodivergence
memory store exists, and the Domain trace stays reference-only (no raw prompt
text, no hidden chain of thought, no raw sensitive source bodies).

READ != PROPOSE != APPROVE != APPLY.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
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
from cmm.domains.neurodivergence.memory import (
    NeurodivergenceMemoryPolicyError,
    build_neurodivergence_memory_binding,
    build_neurodivergence_memory_proposal,
    build_neurodivergence_memory_view,
    build_neurodivergence_memory_view_request,
    validate_neurodivergence_memory_binding,
)
from cmm.domains.neurodivergence.presentation import (
    build_neurodivergence_presentation_policy,
)
from cmm.domains.neurodivergence.trace import (
    assemble_neurodivergence_trace,
    build_neurodivergence_trace_contribution,
    build_neurodivergence_trace_reference,
    validate_neurodivergence_trace,
)
from cmm.domains.trace_contracts import (
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
)

NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)
DOMAIN = "domain:neurodivergence"


# ═══════════════════════════════════════════════════════════════════════════════
# Presentation
# ═══════════════════════════════════════════════════════════════════════════════


def test_presentation_is_exploration_friendly_not_disclaimer_first():
    policy = build_neurodivergence_presentation_policy()

    assert policy.include_uncertainty is True
    assert policy.include_provenance is True
    assert policy.include_alternatives is True
    assert policy.warning_position != "before_content"
    # No mandatory disclaimer block and no required clinical section.
    assert policy.require_disclaimers is False
    assert policy.required_sections == ()


def test_presentation_offers_useful_exploratory_structure():
    policy = build_neurodivergence_presentation_policy()
    offered = set(policy.optional_sections)

    for section in (
        "what_may_fit",
        "why_it_may_fit",
        "what_remains_unclear",
        "what_may_not_fit",
        "alternative_or_overlapping_explanations",
        "evidence_that_would_clarify",
        "current_certainty",
    ):
        assert section in offered, section


def test_presentation_protects_certainty_and_source_terms():
    policy = build_neurodivergence_presentation_policy()

    for term in (
        "confirmed",
        "in_evaluation",
        "hypothesis",
        "not_confirmed",
        "ruled_out",
        "insufficiently_supported",
        "screening",
        "self_report",
        "third_party_report",
        "model_interpretation",
        "provenance",
        "working_hypothesis",
    ):
        assert term in policy.protected_terms, term
    # Each protected term carries a gloss so certainty stays understandable.
    for term in policy.protected_terms:
        assert policy.term_glosses[term], term


def test_presentation_does_not_force_a_clinical_tone():
    policy = build_neurodivergence_presentation_policy()
    joined = " ".join(policy.optional_sections + policy.preferred_section_order)

    assert "diagnosis" not in joined
    assert policy.preferred_views == ("conversational", "structured")


# ═══════════════════════════════════════════════════════════════════════════════
# Memory
# ═══════════════════════════════════════════════════════════════════════════════


def _reference(reference_id: str, canonical_id: str) -> DomainMemoryReference:
    return DomainMemoryReference(
        reference_id=reference_id,
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id=canonical_id,
        domain_id=DOMAIN,
        applicable_domains=(DOMAIN,),
        evidence_ids=("ev:nd:1",),
        resource_ids=("neurodivergence.developmental_history",),
    )


def test_proposal_is_memory_update_and_confirmation_gated():
    proposal = build_neurodivergence_memory_proposal(proposal_id="mp-nd-1")

    assert proposal.proposal_kind is DomainMemoryProposalKind.MEMORY_UPDATE
    assert proposal.requires_confirmation is True
    assert proposal.required_capabilities == (DomainMemoryCapability.PROPOSE,)


def test_never_persistable_clinical_content_is_not_proposable():
    """A diagnosis artifact can never be persisted by this pack at all."""
    for content_kind in (
        "confirmed_diagnosis",
        "diagnosis_assertion",
        "clinical_status",
        "psychiatric_label",
        "medication_change",
        "treatment_change",
        "source_authority_rewrite",
    ):
        with pytest.raises(NeurodivergenceMemoryPolicyError):
            build_neurodivergence_memory_proposal(
                proposal_id="mp-nd-x", content_kind=content_kind
            )


def test_a_working_hypothesis_is_proposable_but_never_applied():
    """A hypothesis may be proposed; the proposal is not a mutation."""
    proposal = build_neurodivergence_memory_proposal(
        proposal_id="mp-nd-hypothesis", content_kind="working_hypothesis"
    )

    assert proposal.requires_confirmation is True
    assert proposal.required_capabilities == (DomainMemoryCapability.PROPOSE,)
    assert DomainMemoryCapability.APPLY not in proposal.required_capabilities
    assert DomainMemoryCapability.DELETE not in proposal.required_capabilities


def test_view_request_is_domain_scoped():
    ref = _reference("ref:nd:1", "item:nd:1")
    request = build_neurodivergence_memory_view_request(
        request_id="req-nd-1",
        trace_id="trace-nd-1",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
    )

    assert str(request.primary_domain) == DOMAIN
    inventory = DomainMemoryReferenceInventory(references=(ref,))
    view = build_neurodivergence_memory_view(request=request, inventory=inventory)
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
    view_request = build_neurodivergence_memory_view_request(
        request_id=f"req:{proposal_id}",
        trace_id=trace_id,
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
        permission_decision_ids=(f"perm:{proposal_id}",),
    )
    proposal = build_neurodivergence_memory_proposal(
        proposal_id=proposal_id,
        content_kind="working_hypothesis",
        affected_reference_ids=(f"ref:{proposal_id}",),
    )
    temp_inventory = DomainMemoryReferenceInventory(
        references=(ref,),
        traces=(DomainMemoryTraceSnapshot(trace_id=trace_id, primary_domain=DOMAIN),),
        permission_decisions=(permission,),
    )
    view = build_neurodivergence_memory_view(
        request=view_request, inventory=temp_inventory
    )
    binding = build_neurodivergence_memory_binding(
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
    binding, inventory, view, proposal = _full_chain("mp-nd-2")

    result = validate_neurodivergence_memory_binding(
        binding=binding, inventory=inventory
    )
    assert result.is_valid is True

    assert proposal.requires_confirmation is True
    assert proposal.required_capabilities == (DomainMemoryCapability.PROPOSE,)
    assert DomainMemoryCapability.APPLY not in proposal.required_capabilities
    assert DomainMemoryCapability.DELETE not in proposal.required_capabilities
    assert binding.memory_proposal_ids == ("mp-nd-2",)
    assert binding.view_id == view.view_id
    assert binding.approval_request_ids == ("appr-req:mp-nd-2",)
    assert binding.approval_decision_ids == ("appr-dec:mp-nd-2",)


def test_malformed_or_unauthorized_inventory_fails_closed():
    binding, inventory, _view, _proposal = _full_chain("mp-nd-3")
    malformed = DomainMemoryReferenceInventory(
        references=inventory.references,
        proposals=inventory.proposals,
        permission_decisions=inventory.permission_decisions,
        approval_requests=inventory.approval_requests,
        approval_decisions=inventory.approval_decisions,
        traces=inventory.traces,
    )

    result = validate_neurodivergence_memory_binding(
        binding=binding, inventory=malformed
    )

    assert result.is_valid is False


def test_a_proposal_without_approval_coverage_fails_closed():
    binding, inventory, _view, _proposal = _full_chain("mp-nd-4")
    without_approval = DomainMemoryReferenceInventory(
        references=inventory.references,
        proposals=inventory.proposals,
        permission_decisions=inventory.permission_decisions,
        traces=inventory.traces,
        views=inventory.views,
    )

    result = validate_neurodivergence_memory_binding(
        binding=binding, inventory=without_approval
    )

    assert result.is_valid is False


def test_revoked_permission_invalidates_a_stale_binding():
    """Permission revocation makes the proposal chain invalid, not applied."""
    import dataclasses

    binding, inventory, _view, _proposal = _full_chain("mp-nd-5")
    assert (
        validate_neurodivergence_memory_binding(
            binding=binding, inventory=inventory
        ).is_valid
        is True
    )

    revoked = dataclasses.replace(inventory.permission_decisions[0], allowed=False)
    revoked_inventory = DomainMemoryReferenceInventory(
        references=inventory.references,
        proposals=inventory.proposals,
        permission_decisions=(revoked,),
        approval_requests=inventory.approval_requests,
        approval_decisions=inventory.approval_decisions,
        traces=inventory.traces,
        views=inventory.views,
    )

    result = validate_neurodivergence_memory_binding(
        binding=binding, inventory=revoked_inventory
    )

    assert result.is_valid is False


def test_binding_contract_rejects_tampered_content_digest():
    from cmm.domains.errors import DomainMemoryContractError

    binding, _inventory, _view, _proposal = _full_chain("mp-nd-6")

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


def test_discussing_a_working_hypothesis_performs_no_mutation():
    """Talking about a hypothesis is not authorization to persist it."""
    from cmm.domains.neurodivergence.rules import (
        build_neurodivergence_rules,
        is_persistence_restricted_content,
    )

    assert is_persistence_restricted_content("confirmed_diagnosis") is True
    assert is_persistence_restricted_content("working_hypothesis") is False

    rules = {rule.definition.id: rule for rule in build_neurodivergence_rules()}
    rule = rules["neurodivergence.sensitive_label_persistence"]
    context = ReasoningRuleContext(
        reasoning_id="rid",
        timestamp=NOW,
        active_domains=(DOMAIN,),
        primary_domain=DOMAIN,
        metadata={
            "persistence_request": {
                "content_kind": "working_hypothesis",
                "certainty_state": "hypothesis",
                "authorization": None,
                "discussion_only": True,
            }
        },
    )

    result = rule.evaluate(context)

    assert result.status.value == "blocked"
    assert result.metadata["direct_write_performed"] is False
    assert result.metadata["proposal_required"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# Trace
# ═══════════════════════════════════════════════════════════════════════════════


def test_trace_is_reference_only_and_domain_scoped():
    ref = build_neurodivergence_trace_reference(
        ref_id="neurodivergence.trace.ref:1",
        kind=DomainTraceReferenceKind.DOMAIN_RESULT,
    )

    assert ref.ref_id == "neurodivergence.trace.ref:1"
    assert str(ref.domain_id) == DOMAIN

    contribution = build_neurodivergence_trace_contribution(
        domain_result_id="result:nd:1"
    )
    assert str(contribution.domain_id) == DOMAIN

    serialized = json.dumps(contribution.to_dict(), sort_keys=True)
    for forbidden in (
        "chain_of_thought",
        "prompt",
        "source_body",
        "transcript",
        "assessment_report_text",
    ):
        assert forbidden not in serialized, forbidden


def test_assembled_trace_exposes_resolution_and_result_pairings():
    trace = assemble_neurodivergence_trace(
        request_id="trace-req:1",
        resolution_context_id="ctx:1",
        resolution_result_id="resolution:1",
        composition_id="composition:1",
        domain_result_id="result:nd:1",
        started_at=NOW,
        completed_at=NOW,
    )

    assert str(trace.primary_domain) == DOMAIN
    assert trace.references.resolution_context_id == "ctx:1"
    assert trace.references.composition_id == "composition:1"
    assert any(
        str(reference.result_id) == "result:nd:1" for reference in trace.domain_results
    )
    serialized = json.dumps(trace.to_dict(), sort_keys=True)
    assert "chain_of_thought" not in serialized
    assert "prompt" not in serialized


def test_trace_supports_permission_approval_and_memory_proposal_references():
    contribution = build_neurodivergence_trace_contribution(
        domain_result_id="result:nd:2",
        references=(
            build_neurodivergence_trace_reference(
                ref_id="profile:neurodivergence.profile",
                kind=DomainTraceReferenceKind.PROFILE,
            ),
            build_neurodivergence_trace_reference(
                ref_id="rule-result:neurodivergence.certainty_state_preservation",
                kind=DomainTraceReferenceKind.RULE_RESULT,
            ),
            build_neurodivergence_trace_reference(
                ref_id="evidence:neurodivergence.developmental_history",
                kind=DomainTraceReferenceKind.EVIDENCE,
            ),
            build_neurodivergence_trace_reference(
                ref_id="permission:cross-domain:1",
                kind=DomainTraceReferenceKind.PERMISSION_DECISION,
            ),
            build_neurodivergence_trace_reference(
                ref_id="approval-decision:cross-domain:1",
                kind=DomainTraceReferenceKind.APPROVAL_DECISION,
            ),
            build_neurodivergence_trace_reference(
                ref_id="privacy-decision:1",
                kind=DomainTraceReferenceKind.PRIVACY_DECISION,
            ),
            build_neurodivergence_trace_reference(
                ref_id="memory-proposal:1",
                kind=DomainTraceReferenceKind.MEMORY_PROPOSAL,
            ),
            build_neurodivergence_trace_reference(
                ref_id="workflow-result:development_history_review",
                kind=DomainTraceReferenceKind.WORKFLOW_RESULT,
            ),
        ),
    )

    kinds = {reference.kind for reference in contribution.references}
    for kind in (
        DomainTraceReferenceKind.PROFILE,
        DomainTraceReferenceKind.RULE_RESULT,
        DomainTraceReferenceKind.EVIDENCE,
        DomainTraceReferenceKind.PERMISSION_DECISION,
        DomainTraceReferenceKind.APPROVAL_DECISION,
        DomainTraceReferenceKind.PRIVACY_DECISION,
        DomainTraceReferenceKind.MEMORY_PROPOSAL,
        DomainTraceReferenceKind.WORKFLOW_RESULT,
    ):
        assert kind in kinds, kind
    # Every domain contribution reference belongs to this domain.
    for reference in contribution.references:
        assert str(reference.domain_id) == DOMAIN
    # Reference-only: no reference carries a raw sensitive source body.
    serialized = json.dumps(contribution.to_dict(), sort_keys=True)
    for forbidden in ("source_body", "chain_of_thought", "prompt"):
        assert forbidden not in serialized, forbidden


def test_a_global_trace_reference_cannot_be_relabelled_as_domain_owned():
    """Canonical contract: global kinds omit domain_id, domain kinds include it."""
    from cmm.domains.errors import DomainTraceContractError

    # A Knowledge Package reference is a canonical global kind and is created
    # without a domain owner.
    global_ref = build_neurodivergence_trace_reference(
        ref_id="knowledge-package:1",
        kind=DomainTraceReferenceKind.KNOWLEDGE_PACKAGE,
        domain_id=None,
    )
    assert global_ref.domain_id is None

    with pytest.raises(DomainTraceContractError):
        build_neurodivergence_trace_reference(
            ref_id="knowledge-package:2",
            kind=DomainTraceReferenceKind.KNOWLEDGE_PACKAGE,
        )

    # A global reference may not be smuggled into a domain-owned contribution.
    with pytest.raises(DomainTraceContractError):
        build_neurodivergence_trace_contribution(
            domain_result_id="result:nd:global",
            references=(global_ref,),
        )


def test_trace_validation_uses_canonical_validator():
    from cmm.domains.trace_contracts import DomainTraceDomainSelection

    trace = assemble_neurodivergence_trace(
        request_id="trace-req:2",
        resolution_context_id="ctx:2",
        resolution_result_id="resolution:2",
        composition_id="composition:2",
        domain_result_id="result:nd:2",
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

    result = validate_neurodivergence_trace(trace=trace, inventory=inventory)

    assert result.valid is True
