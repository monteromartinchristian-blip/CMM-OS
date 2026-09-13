"""Phase 10.53 — Neurodivergence permission declaration tests.

Neurodivergence is fail-closed: inference/reasoning is allowed, persisting it
is not.  Reading is not transferring, provider availability is never
permission, and a technical transfer object is never authority.

The policy is a declaration only — never a permission engine, resolver or
grant of cross-domain authority.  The canonical ``DomainPermissionResolver``
remains the only source of an effective decision.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from cmm.agent_runtime.agent_security_enums import (
    SensitivityLevel as AgentSensitivityLevel,
)
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionCapability,
    PermissionOutcome,
)
from cmm.domains.neurodivergence.permissions import (
    NEURODIVERGENCE_CAPABILITY_SEPARATION,
    NEURODIVERGENCE_PERMISSION_POLICY_ID,
    NEURODIVERGENCE_PROHIBITED_CAPABILITIES,
    build_neurodivergence_permission_policy,
    permission_authorization_allows,
)
from cmm.domains.permission_contracts import DomainPermissionRequest
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver

DOMAIN_ID = "domain:neurodivergence"


def _registry(*policies) -> DomainPermissionRegistry:
    registry = DomainPermissionRegistry()
    for policy in policies:
        registry.register(policy)
    return registry


_READ_CAPABILITIES = frozenset(
    {
        PermissionCapability.RESOURCE_READ,
        PermissionCapability.KNOWLEDGE_READ,
        PermissionCapability.ENTITY_READ,
    }
)

#: A Neurodivergence-owned resource kind (the policy's read allowlist).
_OWN_RESOURCE_KIND = "developmental_history"


def _request(capability, *, domain_id=DOMAIN_ID, **overrides):
    values = {
        "request_id": "req-1",
        "action": capability,
        "domain_id": domain_id,
        "actor_id": "user-1",
        "session_id": "session-1",
        "sensitivity_level": AgentSensitivityLevel.RESTRICTED,
    }
    # The canonical contract and evaluator require the structural fields each
    # capability actually operates on.
    if capability in _READ_CAPABILITIES:
        values["resource_kind"] = _OWN_RESOURCE_KIND
    if capability is PermissionCapability.DOMAIN_CROSS_ACCESS:
        values["source_domain"] = "domain:health"
        values["target_domain"] = DOMAIN_ID
    values.update(overrides)
    return DomainPermissionRequest(**values)


def _policy():
    return build_neurodivergence_permission_policy()


def test_policy_identity_is_canonical():
    policy = _policy()

    assert policy.policy_id == NEURODIVERGENCE_PERMISSION_POLICY_ID
    assert NEURODIVERGENCE_PERMISSION_POLICY_ID == (
        "domain-permission:neurodivergence:1.0.0"
    )
    assert str(policy.domain_id) == DOMAIN_ID
    assert policy.version == "1.0.0"
    assert policy.enabled is True


def test_read_and_reason_are_allowed_but_write_is_not_automatic():
    policy = _policy()

    for capability in (
        PermissionCapability.RESOURCE_READ,
        PermissionCapability.KNOWLEDGE_READ,
        PermissionCapability.MEMORY_READ,
        PermissionCapability.OPERATION_EXECUTE,
        PermissionCapability.WORKFLOW_EXECUTE,
        PermissionCapability.SENSITIVE_INFERENCE,
    ):
        assert capability in policy.allowed_capabilities, capability

    assert policy.allow_memory_read is True
    assert policy.allow_memory_write is False
    assert policy.allow_external_communication is False
    assert policy.allow_export is False
    assert policy.allow_cross_domain_access is False


def test_no_sensitive_path_is_automatic_and_every_one_requires_approval():
    policy = _policy()

    for capability in (
        PermissionCapability.MEMORY_WRITE,
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
        PermissionCapability.EXPORT,
        PermissionCapability.COMMUNICATION_EXTERNAL,
        PermissionCapability.DOMAIN_CROSS_ACCESS,
    ):
        assert capability in policy.prohibited_capabilities, capability
        assert capability in policy.approval_capabilities, capability
        assert capability not in policy.allowed_capabilities, capability

    for requirement in (
        "memory.persist",
        "sensitive.inference.persist",
        "export",
        "communication.external",
        "domain.cross_access",
    ):
        assert requirement in policy.approval_requirements, requirement


def test_medical_and_irreversible_authority_is_denied_by_default():
    policy = _policy()

    for capability in (
        PermissionCapability.MEDICAL_DECISION,
        PermissionCapability.MEDICAL_ACTION,
        PermissionCapability.PERMISSION_MODIFY,
        PermissionCapability.IRREVERSIBLE_CHANGE,
        PermissionCapability.EXTERNAL_DOMAIN_ACTIVATE,
        PermissionCapability.DOMAIN_CROSS_ACCESS,
        PermissionCapability.EXPORT,
        PermissionCapability.COMMUNICATION_EXTERNAL,
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
        PermissionCapability.MEMORY_WRITE,
        PermissionCapability.FILE_MODIFY,
        PermissionCapability.KNOWLEDGE_DELETE,
        PermissionCapability.PUBLICATION,
    ):
        assert capability in policy.prohibited_capabilities, capability


def test_inference_is_allowed_without_granting_persistence():
    policy = _policy()

    assert PermissionCapability.SENSITIVE_INFERENCE in policy.allowed_capabilities
    assert (
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST
        in policy.prohibited_capabilities
    )


def test_capability_separation_is_explicit_and_distinct():
    """read != infer != propose != persist != transfer/export/communicate != mutate."""
    for stage in (
        "read",
        "infer",
        "propose_persistence",
        "persist",
        "transfer",
        "export",
        "communicate",
        "external_mutation",
    ):
        assert stage in NEURODIVERGENCE_CAPABILITY_SEPARATION, stage

    separation = NEURODIVERGENCE_CAPABILITY_SEPARATION
    assert separation["persist"] != separation["read"]
    assert separation["transfer"] != separation["read"]
    assert separation["export"] != separation["infer"]
    assert separation["communicate"] != separation["read"]
    # A local reading of a source domain is not a cross-domain transfer.
    assert (
        PermissionCapability.RESOURCE_READ in separation["read"]
        and PermissionCapability.DOMAIN_CROSS_ACCESS not in separation["read"]
    )


def test_capability_separation_is_surfaced_in_policy_metadata():
    policy = _policy()
    serialized = policy.metadata["capability_separation"]

    assert set(serialized) == set(NEURODIVERGENCE_CAPABILITY_SEPARATION)
    assert tuple(serialized["persist"]) == (
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST.value,
    )
    # Reading is not transferring: no cross-domain authority hides in "read".
    assert PermissionCapability.DOMAIN_CROSS_ACCESS.value not in serialized["read"]


def test_authorization_requires_literal_true():
    assert permission_authorization_allows(True) is True
    for value in (False, 1, 0, "true", "True", [], {}, None, object()):
        assert permission_authorization_allows(value) is False


def test_autonomy_is_zero_and_irreversible_action_is_not_allowed():
    limits = _policy().autonomy_limits

    assert limits.maximum_autonomy_level == 0
    assert limits.allow_reversible_changes is False
    assert limits.allow_irreversible_changes is False


# ── Canonical resolver behavior ──────────────────────────────────────────────


def test_memory_write_resolves_denied_through_canonical_resolver():
    resolver = DomainPermissionResolver(_registry(_policy()))

    resolution = resolver.resolve(_request(PermissionCapability.MEMORY_WRITE))

    assert resolution.effective_permissions.decision is PermissionOutcome.DENY


@pytest.mark.parametrize(
    "capability",
    (
        "EXPORT",
        "COMMUNICATION_EXTERNAL",
        "SENSITIVE_INFERENCE_PERSIST",
        "MEDICAL_DECISION",
        "MEDICAL_ACTION",
        "DOMAIN_CROSS_ACCESS",
        "IRREVERSIBLE_CHANGE",
        "PERMISSION_MODIFY",
    ),
)
def test_sensitive_capabilities_resolve_denied(capability):
    resolver = DomainPermissionResolver(_registry(_policy()))

    resolution = resolver.resolve(_request(getattr(PermissionCapability, capability)))

    assert resolution.effective_permissions.decision is PermissionOutcome.DENY


@pytest.mark.parametrize(
    "capability",
    ("RESOURCE_READ", "KNOWLEDGE_READ", "MEMORY_READ", "SENSITIVE_INFERENCE"),
)
def test_read_and_reason_resolve_allowed(capability):
    resolver = DomainPermissionResolver(_registry(_policy()))

    resolution = resolver.resolve(_request(getattr(PermissionCapability, capability)))

    assert resolution.effective_permissions.decision is PermissionOutcome.ALLOW


def test_unregistered_domain_fails_closed():
    """A domain with no registered policy is never granted authority.

    No policy for the requested domain means the canonical evaluator cannot
    produce an ALLOW.  This pack depends only on the fail-closed property.
    """
    resolver = DomainPermissionResolver(_registry(_policy()))

    with pytest.raises(ValueError):
        resolver.resolve(
            _request(PermissionCapability.MEMORY_READ, domain_id="domain:unknown")
        )


def test_a_foreign_domain_resource_kind_is_not_readable():
    """Reading is scoped to Neurodivergence-owned resource kinds."""
    resolver = DomainPermissionResolver(_registry(_policy()))

    resolution = resolver.resolve(
        _request(
            PermissionCapability.RESOURCE_READ, resource_kind="therapy_session_note"
        )
    )

    assert resolution.effective_permissions.decision is PermissionOutcome.DENY


def test_authority_downgrade_is_revalidated_and_fails_closed():
    """A stale ALLOW is never reused after the effective authority tightens."""
    registry = _registry(_policy())
    resolver = DomainPermissionResolver(registry)

    before = resolver.resolve(_request(PermissionCapability.SENSITIVE_INFERENCE))
    assert before.effective_permissions.decision is PermissionOutcome.ALLOW

    # Authority becomes more restrictive after the initial resolution: the
    # revised policy removes inference authority entirely.
    downgraded = dataclasses.replace(
        _policy(),
        policy_id="domain-permission:neurodivergence:1.1.0",
        version="1.1.0",
        allowed_capabilities=(
            PermissionCapability.RESOURCE_READ,
            PermissionCapability.KNOWLEDGE_READ,
            PermissionCapability.MEMORY_READ,
        ),
        prohibited_capabilities=(
            *_policy().prohibited_capabilities,
            PermissionCapability.SENSITIVE_INFERENCE,
        ),
    )
    registry.register(downgraded)

    after = resolver.resolve(_request(PermissionCapability.SENSITIVE_INFERENCE))
    assert after.effective_permissions.decision is PermissionOutcome.DENY
    assert any(str(policy.version) == "1.1.0" for policy in after.domain_policies)
    assert all(str(policy.version) != "1.0.0" for policy in after.domain_policies)


def test_provider_availability_is_not_permission():
    """A remote/model route existing never authorizes remote sensitive work."""
    policy = _policy()

    assert PermissionCapability.MODEL_EXTERNAL in policy.prohibited_capabilities
    assert PermissionCapability.SEARCH_EXTERNAL in policy.prohibited_capabilities
    assert policy.allow_external_models is False
    assert policy.allow_external_search is False


# ═══════════════════════════════════════════════════════════════════════════════
# Connected cross-domain authority (Task 9)
#
# A structurally valid ``CrossDomainContextTransfer`` is not permission
# authority.  Admission is bound to the *current* canonical resolver/gate
# decision, and to a consumed canonical approval where one is required.
# ═══════════════════════════════════════════════════════════════════════════════

HEALTH = "domain:health"
MENTAL_HEALTH = "domain:mental-health"
CROSS_DOMAIN_PURPOSE = "differential_context"
CROSS_DOMAIN_SOURCE_KIND = "differential_overlap_context"
NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _canonical_transfer(
    identifier,
    *,
    source_domain=HEALTH,
    target_domain=DOMAIN_ID,
    reason=CROSS_DOMAIN_PURPOSE,
    provenance=("finding:health:7",),
    transferable=True,
    private=False,
):
    """Return the JSON-safe canonical ``CrossDomainContextTransfer`` mapping."""
    from cmm.domains.cross_domain_contracts import CrossDomainContextTransfer

    return CrossDomainContextTransfer(
        source_domain=source_domain,
        target_domain=target_domain,
        kind="finding",
        identifier=identifier,
        value=True,
        reason=reason,
        provenance=provenance,
        transferable=transferable,
        private=private,
    ).to_dict()


def _cross_domain_request(
    request_id,
    resource_id,
    *,
    source_domain=HEALTH,
    target_domain=DOMAIN_ID,
    actor_id="user-1",
    session_id="session-1",
    reason=CROSS_DOMAIN_PURPOSE,
):
    """Real canonical cross-domain request bound to one projected resource."""
    from cmm.domains.permission_contracts import CrossDomainPermissionRequest

    return CrossDomainPermissionRequest(
        request_id,
        source_domain=source_domain,
        target_domain=target_domain,
        resource_ids=(resource_id,),
        resource_kinds=(CROSS_DOMAIN_SOURCE_KIND,),
        reason=reason,
        actor_id=actor_id,
        session_id=session_id,
        sensitivity_level=AgentSensitivityLevel.RESTRICTED,
        capability=PermissionCapability.RESOURCE_READ,
    )


def _connected_permission_stack(resolver):
    """Real canonical gate + approval stack over an already-built resolver."""
    from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
    from cmm.agent_runtime.approval_service import ApprovalService
    from cmm.domains.permission_gate import DomainPermissionGate

    approval_service = ApprovalService(InMemoryApprovalRepository())
    gate = DomainPermissionGate(resolver, approval_service, clock=lambda: NOW)
    return approval_service, gate


def _authorized_cross_domain_resolver():
    """Real Health/Neurodivergence policies composed into an authorized path."""
    from cmm.domains.health.permissions import build_health_permission_policy

    source = build_health_permission_policy()
    target = _policy()
    store = DomainPermissionRegistry()
    store.register(
        dataclasses.replace(
            source,
            allowed_capabilities=source.allowed_capabilities
            + (PermissionCapability.DOMAIN_CROSS_ACCESS,),
            allowed_target_domains=(DOMAIN_ID,),
            allowed_resource_kinds=tuple(source.allowed_resource_kinds)
            + (CROSS_DOMAIN_SOURCE_KIND,),
        )
    )
    store.register(
        dataclasses.replace(
            target,
            policy_id="domain-permission:neurodivergence:1.0.0-authorized-projection",
            version="1.0.0-authorized-projection",
            prohibited_capabilities=tuple(
                capability
                for capability in NEURODIVERGENCE_PROHIBITED_CAPABILITIES
                if capability is not PermissionCapability.DOMAIN_CROSS_ACCESS
            ),
            allowed_source_domains=(HEALTH,),
        )
    )
    return DomainPermissionResolver(store)


def _grant_canonical_cross_domain_approval(approval_service, gate, request):
    """Drive the canonical approval lifecycle for ``request`` to consumption."""
    from cmm.agent_runtime.domain_permission_contracts import (
        PermissionApprovalRequirement,
    )
    from cmm.domains.approval_bridge import to_approval_requirement
    from cmm.domains.permission_gate import PermissionGateOutcome

    pending = gate.evaluate_cross_domain(request)
    assert pending.outcome is PermissionGateOutcome.APPROVAL_REQUIRED
    requirement = PermissionApprovalRequirement.from_dict(
        pending.approval_requirements[0]
    )
    approval_request = approval_service.create_request_from_requirement(
        to_approval_requirement(requirement, agent_run_id="run-at-dp-053"),
        requested_by="user",
    )
    approval_service.approve(approval_request.id, "user")
    return approval_request.id


def _admit_cross_domain_transfers(
    *,
    request,
    candidates,
    resolver,
    gate,
    approval_request_id=None,
    now=NOW,
):
    """Admit only transfers backed by effective *current* permission authority.

    The canonical resolver decides the effective authority, the canonical gate
    composes it with approval consumption, and only then is the exact matching
    transfer admitted.  A structurally valid matching transfer on its own
    admits nothing.
    """
    decision = resolver.resolve_cross_domain(request, now=now)
    gate_result = gate.evaluate_cross_domain(
        request, approval_request_id=approval_request_id
    )
    admitted = ()
    if gate_result.allowed:
        admitted = tuple(
            candidate
            for candidate in candidates
            if candidate["identifier"] in request.resource_ids
            and candidate["source_domain"] == request.source_domain
            and candidate["target_domain"] == request.target_domain
            and candidate["reason"] == request.reason
        )
    return decision, gate_result, admitted


def _evaluate_minimization(projection, transfers):
    from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
    from cmm.domains.neurodivergence.rules import build_neurodivergence_rules

    rules = {rule.definition.id: rule for rule in build_neurodivergence_rules()}
    context = ReasoningRuleContext(
        reasoning_id="rid",
        timestamp=NOW,
        active_domains=(DOMAIN_ID,),
        primary_domain=DOMAIN_ID,
        metadata={"projection": projection, "transfers": transfers},
    )
    return rules["neurodivergence.purpose_minimized_cross_domain"].evaluate(context)


def _minimization_projection(**fields):
    return {
        "purpose": CROSS_DOMAIN_PURPOSE,
        "fields": {name: {"relevant": True} for name in fields},
    }


def test_current_permission_deny_blocks_a_matching_transfer():
    """DENY + a genuinely matching structural transfer is still not authority."""
    real_resolver = DomainPermissionResolver(_registry(_policy()))
    _approval_service, gate = _connected_permission_stack(real_resolver)
    denied_request = _cross_domain_request("req-nd-deny", "denied_field")
    candidate = _canonical_transfer("denied_field", provenance=("prov:denied",))

    # The real current canonical authority denies the path.
    decision = real_resolver.resolve_cross_domain(denied_request, now=NOW)
    assert decision.decision is PermissionOutcome.DENY
    assert decision.granted_resources == ()

    # The withheld evidence is a genuinely matching canonical transfer for
    # exactly the denied resource — not an omitted one.
    assert candidate["identifier"] in denied_request.resource_ids
    assert candidate["source_domain"] == denied_request.source_domain
    assert candidate["target_domain"] == denied_request.target_domain
    assert candidate["reason"] == denied_request.reason
    assert candidate["transferable"] is True
    assert candidate["private"] is False
    assert candidate["provenance"] == ["prov:denied"]

    # Minimization alone would structurally accept the field: the boundary
    # under test is the connected permission path, not a missing transfer.
    ungated = _evaluate_minimization(
        _minimization_projection(denied_field=True), (candidate,)
    )
    assert ungated.metadata["included_fields"] == ("denied_field",)

    # DENIED_TRANSFER_ADMITTED=NO / DENIED_FIELD_INCLUDED=NO.
    decision, gate_result, admitted = _admit_cross_domain_transfers(
        request=denied_request,
        candidates=(candidate,),
        resolver=real_resolver,
        gate=gate,
    )
    assert decision.decision is PermissionOutcome.DENY
    assert gate_result.allowed is False
    assert admitted == ()
    gated = _evaluate_minimization(
        _minimization_projection(denied_field=True), admitted
    )
    assert gated.status.value == "blocked"
    assert gated.metadata["included_fields"] == ()
    assert gated.metadata["provenance_preserved"] is False
    assert gated.metadata["source_domains"] == ()

    # A supplied approval reference never repairs a canonical DENY.
    repaired = gate.evaluate_cross_domain(
        denied_request, approval_request_id="approval-req-supplied"
    )
    assert repaired.allowed is False


def test_approval_required_without_consumption_is_not_authority():
    """APPROVAL_REQUIRED admits nothing until the approval is consumed."""
    from cmm.domains.permission_gate import PermissionGateOutcome

    authorized_resolver = _authorized_cross_domain_resolver()
    _approval_service, gate = _connected_permission_stack(authorized_resolver)
    request = _cross_domain_request("req-nd-pending", "emotional_context")
    candidate = _canonical_transfer(
        "emotional_context", source_domain=HEALTH, provenance=("finding:health:7",)
    )
    decision, gate_result, admitted = _admit_cross_domain_transfers(
        request=request,
        candidates=(candidate,),
        resolver=authorized_resolver,
        gate=gate,
    )

    assert decision.decision is PermissionOutcome.APPROVAL_REQUIRED
    assert decision.granted_resources == ()
    assert decision.approval_requirements
    assert decision.approval_requirements[0].requirement_id == (
        "cross-domain:req-nd-pending"
    )
    assert gate_result.outcome is PermissionGateOutcome.APPROVAL_REQUIRED
    assert gate_result.allowed is False
    assert admitted == ()

    result = _evaluate_minimization(
        _minimization_projection(emotional_context=True), admitted
    )
    assert result.status.value == "blocked"
    assert result.metadata["included_fields"] == ()
    assert result.metadata["provenance_preserved"] is False


def test_consumed_canonical_approval_admits_the_exact_matching_transfer():
    from cmm.domains.permission_gate import PermissionGateOutcome

    authorized_resolver = _authorized_cross_domain_resolver()
    approval_service, gate = _connected_permission_stack(authorized_resolver)
    request = _cross_domain_request("req-nd-approved", "emotional_context")
    candidates = (_canonical_transfer("emotional_context"),)

    decision, pending, admitted = _admit_cross_domain_transfers(
        request=request,
        candidates=candidates,
        resolver=authorized_resolver,
        gate=gate,
    )
    assert decision.decision is PermissionOutcome.APPROVAL_REQUIRED
    assert pending.outcome is PermissionGateOutcome.APPROVAL_REQUIRED
    assert admitted == ()

    # The approval request is created from the canonical requirement exposed by
    # the real gate and granted through the real canonical ApprovalService.
    approval_request_id = _grant_canonical_cross_domain_approval(
        approval_service, gate, request
    )
    assert approval_service.repository.get_request(approval_request_id) is not None

    decision, consumed, admitted = _admit_cross_domain_transfers(
        request=request,
        candidates=candidates,
        resolver=authorized_resolver,
        gate=gate,
        approval_request_id=approval_request_id,
    )
    assert consumed.outcome is PermissionGateOutcome.APPROVAL_CONSUMED
    assert consumed.allowed is True
    evidence = consumed.approval_evidence
    assert evidence["granted"] is True
    assert evidence["consumed"] is True
    assert evidence["requirement_id"] == f"cross-domain:{request.request_id}"
    assert evidence["domain_id"] == request.source_domain
    assert evidence["target_domain"] == request.target_domain
    assert evidence["actor_id"] == request.actor_id
    assert evidence["session_id"] == request.session_id

    assert admitted == candidates

    # Approval for one resource still authorizes only the field whose own
    # transfer was admitted.
    result = _evaluate_minimization(
        _minimization_projection(emotional_context=True, unbound_field=True),
        admitted,
    )
    assert result.status.value == "applied"
    assert result.metadata["included_fields"] == ("emotional_context",)
    assert "unbound_field" in result.metadata["excluded_fields"]
    assert result.metadata["unbound_fields"] == ("unbound_field",)
    assert result.metadata["provenance_references"] == ("finding:health:7",)


def test_authority_tuple_binding_rejects_a_mismatched_resource():
    from cmm.domains.permission_gate import PermissionGateOutcome

    authorized_resolver = _authorized_cross_domain_resolver()
    approval_service, gate = _connected_permission_stack(authorized_resolver)
    field_a = _cross_domain_request("req-nd-bind", "field_a")
    field_b = _cross_domain_request("req-nd-bind", "field_b")

    approval_request_id = _grant_canonical_cross_domain_approval(
        approval_service, gate, field_a
    )
    _decision, gate_a, admitted_a = _admit_cross_domain_transfers(
        request=field_a,
        candidates=(_canonical_transfer("field_a"),),
        resolver=authorized_resolver,
        gate=gate,
        approval_request_id=approval_request_id,
    )
    assert gate_a.outcome is PermissionGateOutcome.APPROVAL_CONSUMED
    assert admitted_a == (_canonical_transfer("field_a"),)

    # The same consumed approval cannot authorize a different resource, even
    # though its transfer is structurally valid and matching.
    _decision, gate_b, admitted_b = _admit_cross_domain_transfers(
        request=field_b,
        candidates=(_canonical_transfer("field_b"),),
        resolver=authorized_resolver,
        gate=gate,
        approval_request_id=approval_request_id,
    )
    assert gate_b.allowed is False
    assert admitted_b == ()
    blocked = _evaluate_minimization(_minimization_projection(field_b=True), admitted_b)
    assert blocked.metadata["included_fields"] == ()


def test_authority_tuple_binding_rejects_a_mismatched_actor():
    from cmm.domains.permission_gate import PermissionGateOutcome

    authorized_resolver = _authorized_cross_domain_resolver()
    approval_service, gate = _connected_permission_stack(authorized_resolver)
    field_a = _cross_domain_request("req-nd-actor", "field_a")

    approval_request_id = _grant_canonical_cross_domain_approval(
        approval_service, gate, field_a
    )
    _decision, gate_a, _admitted = _admit_cross_domain_transfers(
        request=field_a,
        candidates=(_canonical_transfer("field_a"),),
        resolver=authorized_resolver,
        gate=gate,
        approval_request_id=approval_request_id,
    )
    assert gate_a.outcome is PermissionGateOutcome.APPROVAL_CONSUMED

    other_actor = _cross_domain_request("req-nd-actor", "field_a", actor_id="user-2")
    assert other_actor.actor_id != field_a.actor_id
    _decision, gate_actor, admitted_actor = _admit_cross_domain_transfers(
        request=other_actor,
        candidates=(_canonical_transfer("field_a"),),
        resolver=authorized_resolver,
        gate=gate,
        approval_request_id=approval_request_id,
    )
    assert gate_actor.allowed is False
    assert admitted_actor == ()


def test_authority_tuple_binding_rejects_a_mismatched_session():
    authorized_resolver = _authorized_cross_domain_resolver()
    approval_service, gate = _connected_permission_stack(authorized_resolver)
    field_a = _cross_domain_request("req-nd-session", "field_a")

    approval_request_id = _grant_canonical_cross_domain_approval(
        approval_service, gate, field_a
    )
    other_session = _cross_domain_request(
        "req-nd-session", "field_a", session_id="session-2"
    )
    assert other_session.session_id != field_a.session_id

    _decision, gate_session, admitted_session = _admit_cross_domain_transfers(
        request=other_session,
        candidates=(_canonical_transfer("field_a"),),
        resolver=authorized_resolver,
        gate=gate,
        approval_request_id=approval_request_id,
    )
    assert gate_session.allowed is False
    assert admitted_session == ()


def test_authority_tuple_binding_rejects_a_mismatched_purpose():
    """A transfer for another purpose is never admitted for this request."""
    authorized_resolver = _authorized_cross_domain_resolver()
    approval_service, gate = _connected_permission_stack(authorized_resolver)
    request = _cross_domain_request("req-nd-purpose", "emotional_context")

    approval_request_id = _grant_canonical_cross_domain_approval(
        approval_service, gate, request
    )
    misfiled = _canonical_transfer("emotional_context", reason="assessment_summary")
    assert misfiled["reason"] != request.reason

    _decision, gate_result, admitted = _admit_cross_domain_transfers(
        request=request,
        candidates=(misfiled,),
        resolver=authorized_resolver,
        gate=gate,
        approval_request_id=approval_request_id,
    )
    assert gate_result.allowed is True
    # The authority was consumed, yet the mismatched-purpose transfer is still
    # never admitted: admission binds to purpose, not to approval alone.
    assert admitted == ()
    result = _evaluate_minimization(
        _minimization_projection(emotional_context=True), admitted
    )
    assert result.metadata["included_fields"] == ()
