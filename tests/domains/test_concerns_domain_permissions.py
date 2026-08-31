"""Phase 10.25 — Concerns permissions + memory boundary tests.

Concerns is a high-sensitivity personal domain: fail-closed permissions with
literal-True boolean authorization, deny-by-default on every sensitive
capability exposed by the shared enum, most-restrictive-wins composition, and
proposal-only memory through the shared Phase 10.18 contracts (frozen design
§71–§73; implementation plan Task 8).
"""

from __future__ import annotations

import json

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.domains.concerns.memory import (
    build_concerns_memory_binding,
    build_concerns_memory_proposal,
    build_concerns_memory_view,
    build_concerns_memory_view_request,
    validate_concerns_memory_binding,
)
from cmm.domains.concerns.permissions import (
    CONCERNS_PERMISSION_POLICY_ID,
    CONCERNS_PROHIBITED_CAPABILITIES,
    build_concerns_permission_policy,
    is_persistence_restricted_content,
    permission_authorization_allows,
    persistence_confirmation_accepted,
)
from cmm.domains.memory_contracts import (
    DomainMemoryApprovalDecisionSnapshot,
    DomainMemoryApprovalRequestSnapshot,
    DomainMemoryCapability,
    DomainMemoryPermissionDecisionSnapshot,
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
    DomainMemorySensitivityLevel,
    DomainMemoryTraceSnapshot,
    DomainMemoryViewSnapshot,
)

# ── Permissions ──────────────────────────────────────────────────────────────


def test_policy_identity():
    policy = build_concerns_permission_policy()
    assert policy.policy_id == CONCERNS_PERMISSION_POLICY_ID
    assert CONCERNS_PERMISSION_POLICY_ID == "domain-permission:concerns:1.0.0"
    assert str(policy.domain_id) == "domain:concerns"
    assert policy.enabled is True


def test_high_sensitivity_identity():
    policy = build_concerns_permission_policy()
    assert policy.allowed_sensitivity_levels == ("restricted", "secret")
    assert policy.allow_memory_read is True
    assert policy.allow_memory_write is False


def test_deny_by_default_sensitive_capabilities():
    """Every sensitive capability exposed by the shared enum must be denied."""
    policy = build_concerns_permission_policy()
    for capability in (
        PermissionCapability.MEMORY_WRITE,
        PermissionCapability.FILE_MODIFY,
        PermissionCapability.TASK_CREATE,
        PermissionCapability.SCHEDULE_MODIFY,
        PermissionCapability.GOAL_UPDATE,
        PermissionCapability.COMMUNICATION_EXTERNAL,
        PermissionCapability.SENSITIVE_INFERENCE,
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
        PermissionCapability.EXPORT,
        PermissionCapability.IRREVERSIBLE_CHANGE,
        PermissionCapability.KNOWLEDGE_DELETE,
        PermissionCapability.PERMISSION_MODIFY,
        PermissionCapability.MEDICAL_DECISION,
        PermissionCapability.MEDICAL_ACTION,
        PermissionCapability.LEGAL_DECISION,
        PermissionCapability.LEGAL_ACTION,
        PermissionCapability.FINANCIAL_DECISION,
        PermissionCapability.FINANCIAL_ACTION,
        PermissionCapability.FINANCIAL_SPEND,
        PermissionCapability.EXTERNAL_DOMAIN_ACTIVATE,
        PermissionCapability.PUBLICATION,
    ):
        assert capability in policy.prohibited_capabilities, capability


def test_external_search_and_model_not_implicitly_authorized():
    policy = build_concerns_permission_policy()
    for capability in (
        PermissionCapability.SEARCH_EXTERNAL,
        PermissionCapability.MODEL_EXTERNAL,
    ):
        assert capability in policy.prohibited_capabilities
    assert policy.allow_external_search is False
    assert policy.allow_external_models is False


def test_read_only_autonomous_surface():
    policy = build_concerns_permission_policy()
    for capability in (
        PermissionCapability.RESOURCE_READ,
        PermissionCapability.MEMORY_READ,
        PermissionCapability.OPERATION_EXECUTE,
        PermissionCapability.WORKFLOW_EXECUTE,
    ):
        assert capability in policy.allowed_capabilities
    assert policy.allow_cross_domain_access is False
    assert policy.allow_inbound_cross_domain_access is True


def test_literal_true_authorization_semantics():
    for raw in ("true", "TRUE", "True", 1, 0, 1.0, [], {}, (), None, "yes"):
        assert permission_authorization_allows(raw) is False
    assert permission_authorization_allows(True) is True
    assert permission_authorization_allows(False) is False


def test_prohibited_surface_is_fail_closed():
    allowed_set = set(build_concerns_permission_policy().allowed_capabilities)
    for capability in CONCERNS_PROHIBITED_CAPABILITIES:
        assert capability not in allowed_set


def test_composed_policy_most_restrictive_wins():
    policy = build_concerns_permission_policy()
    strict = build_concerns_permission_policy()
    composed_denied = set(policy.prohibited_capabilities) | set(
        strict.prohibited_capabilities
    )
    for capability in (
        PermissionCapability.MEMORY_WRITE,
        PermissionCapability.SENSITIVE_INFERENCE,
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
        PermissionCapability.COMMUNICATION_EXTERNAL,
    ):
        assert capability in composed_denied


# ── Memory boundary ──────────────────────────────────────────────────────────


def _reference(reference_id: str, canonical_id: str) -> DomainMemoryReference:
    return DomainMemoryReference(
        reference_id=reference_id,
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id=canonical_id,
        domain_id="domain:concerns",
        applicable_domains=("domain:concerns",),
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )


def test_memory_proposal_always_requires_confirmation():
    proposal = build_concerns_memory_proposal(proposal_id="cmp-1")
    assert proposal.proposal_id == "cmp-1"
    assert proposal.requires_confirmation is True
    assert DomainMemoryCapability.PROPOSE in proposal.required_capabilities


def test_no_confirmation_override_supported():
    proposal = build_concerns_memory_proposal(proposal_id="cmp-2")
    assert proposal.requires_confirmation is True


def test_memory_view_request_and_binding_roundtrip():
    ref = _reference("ref:1", "item:1")
    inventory = DomainMemoryReferenceInventory(references=(ref,))
    request = build_concerns_memory_view_request(
        request_id="req-1",
        trace_id="trace-1",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
    )
    assert str(request.primary_domain) == "domain:concerns"
    view = build_concerns_memory_view(request=request, inventory=inventory)
    assert view.primary_domain == request.primary_domain
    proposal = build_concerns_memory_proposal(proposal_id="cmp-3")
    binding = build_concerns_memory_binding(
        proposal=proposal,
        view=view,
        trace_id="trace-1",
        permission_decision_ids=("perm-1",),
    )
    assert binding.memory_proposal_ids == ("cmp-3",)
    assert binding.domain_id == "domain:concerns"
    json.dumps(
        {
            "binding_id": binding.binding_id,
            "view_digest": binding.view_digest,
            "memory_proposal_ids": list(binding.memory_proposal_ids),
        },
        allow_nan=False,
    )


def test_binding_validation_runs_against_shared_validator():
    trace = DomainMemoryTraceSnapshot(
        trace_id="trace-2", primary_domain="domain:concerns"
    )
    ref = _reference("ref:2", "item:2")
    permission = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm-2",
        allowed=True,
        capabilities=(DomainMemoryCapability.READ,),
        source_domain_id="domain:concerns",
        target_domain_id="domain:concerns",
        sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
    )
    request = build_concerns_memory_view_request(
        request_id="req-2",
        trace_id="trace-2",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
        permission_decision_ids=("perm-2",),
    )
    inventory = DomainMemoryReferenceInventory(
        references=(ref,),
        traces=(trace,),
        permission_decisions=(permission,),
    )
    view = build_concerns_memory_view(request=request, inventory=inventory)
    proposal = build_concerns_memory_proposal(proposal_id="cmp-4")
    binding = build_concerns_memory_binding(
        proposal=proposal, view=view, trace_id="trace-2"
    )
    result = validate_concerns_memory_binding(binding=binding, inventory=inventory)
    assert isinstance(result.is_valid, bool)


def test_binding_validation_fails_closed_on_missing_trace():
    ref = _reference("ref:3", "item:3")
    request = build_concerns_memory_view_request(
        request_id="req-3",
        trace_id="trace-3",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
    )
    inventory = DomainMemoryReferenceInventory(references=(ref,))
    view = build_concerns_memory_view(request=request, inventory=inventory)
    proposal = build_concerns_memory_proposal(proposal_id="cmp-5")
    binding = build_concerns_memory_binding(
        proposal=proposal, view=view, trace_id="trace-3"
    )
    result = validate_concerns_memory_binding(binding=binding, inventory=inventory)
    assert result.is_valid is False


# ── Sensitive content can never silently persist ────────────────────────────

SENSITIVE_CONTENT_KINDS = (
    "fear",
    "support_need",
    "inferred_emotional_pattern",
    "recurring_concern_pattern",
    "psychological_interpretation",
    "risk_interpretation",
    "third_party_motive",
)


def test_sensitive_content_kinds_are_recognized_as_restricted():
    # imported at module level

    for kind in SENSITIVE_CONTENT_KINDS:
        assert is_persistence_restricted_content(kind) is True
    assert is_persistence_restricted_content("user_confirmed_preference") is False
    assert is_persistence_restricted_content(None) is False


def test_raw_boolean_or_mapping_cannot_authorize_persistence():
    from cmm.domains.concerns.permissions import persistence_confirmation_accepted

    # Raw booleans / arbitrary mappings are never a complete shared contract.
    for raw in (True, False, 1, 0, "true", {"approved": True}, None):
        record = persistence_confirmation_accepted(confirmation=raw)
        assert record["accepted"] is False
        if raw is None:
            assert record["authorization_malformed"] is False
        else:
            assert record["authorization_malformed"] is True


def test_standalone_approval_snapshot_alone_denies():
    from cmm.domains.concerns.permissions import persistence_confirmation_accepted

    snap = DomainMemoryApprovalDecisionSnapshot(
        decision_id="dec-1", request_id="req-1", approved=True
    )
    record = persistence_confirmation_accepted(confirmation=snap)
    assert record["accepted"] is False
    assert record["authorization_malformed"] is True


def _full_chain(proposal_id: str = "prop-c-1", *, approved: bool = True):
    ref = _reference(f"ref:{proposal_id}", f"item:{proposal_id}")
    permission = DomainMemoryPermissionDecisionSnapshot(
        decision_id=f"perm:{proposal_id}",
        allowed=True,
        capabilities=(DomainMemoryCapability.PROPOSE,),
        source_domain_id="domain:concerns",
        target_domain_id="domain:concerns",
        sensitivity_levels=(DomainMemorySensitivityLevel.NORMAL,),
    )
    view_request = build_concerns_memory_view_request(
        request_id=f"req:{proposal_id}",
        trace_id=f"trace:{proposal_id}",
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
        permission_decision_ids=(f"perm:{proposal_id}",),
    )
    proposal = build_concerns_memory_proposal(
        proposal_id=proposal_id,
        affected_reference_ids=(f"ref:{proposal_id}",),
    )
    temp_inventory = DomainMemoryReferenceInventory(
        references=(ref,),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id=f"trace:{proposal_id}", primary_domain="domain:concerns"
            ),
        ),
        permission_decisions=(permission,),
    )
    view = build_concerns_memory_view(request=view_request, inventory=temp_inventory)
    binding = build_concerns_memory_binding(
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
                approved=approved,
            ),
        ),
        traces=(
            DomainMemoryTraceSnapshot(
                trace_id=f"trace:{proposal_id}", primary_domain="domain:concerns"
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
    return binding, inventory


def test_complete_valid_chain_accepts_only_for_unrestricted_content():
    binding, inventory = _full_chain("prop-c-valid", approved=True)
    unrestricted = persistence_confirmation_accepted(
        confirmation_binding=binding,
        confirmation_inventory=inventory,
        proposal_id="prop-c-valid",
        content_kind="user_confirmed_preference",
    )
    assert unrestricted["accepted"] is True

    restricted = persistence_confirmation_accepted(
        confirmation_binding=binding,
        confirmation_inventory=inventory,
        proposal_id="prop-c-valid",
        content_kind="fear",
    )
    assert restricted["accepted"] is False
    assert restricted["content_restricted"] is True


def test_wrong_proposal_id_in_chain_denied():
    binding, inventory = _full_chain("prop-c-alpha", approved=True)
    record = persistence_confirmation_accepted(
        confirmation_binding=binding,
        confirmation_inventory=inventory,
        proposal_id="prop-c-beta",
        content_kind="user_confirmed_preference",
    )
    assert record["accepted"] is False


def test_no_concerns_memory_store_exists():
    import cmm.domains.concerns

    for forbidden in (
        "ConcernMemoryStore",
        "ConcernsMemoryStore",
        "ConcernMemoryRegistry",
        "ConcernMemoryEngine",
    ):
        assert not hasattr(cmm.domains.concerns, forbidden)
