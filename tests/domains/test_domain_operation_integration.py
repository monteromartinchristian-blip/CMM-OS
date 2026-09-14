from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains import (
    DomainComposition,
    DomainCompositionItem,
    DomainCompositionStatus,
    DomainId,
    DomainMemoryPolicy,
    DomainOperationContext,
    DomainOperationRequest,
    DomainPresentationPolicy,
    DomainProductionPolicy,
    DomainQuestionPolicy,
    DomainReasoningDepth,
    DomainTemporalPolicy,
    PermissionComposition,
    ResolvedDomainProfile,
)


def _profile() -> ResolvedDomainProfile:
    return ResolvedDomainProfile(
        id="profile:health",
        primary_domain=DomainId("health"),
        supporting_domains=(DomainId("general"),),
        profile_names=("Health",),
        required_rules=("rule:health.safety",),
        optional_rules=("rule:general.structure",),
        prohibited_rules=(),
        allowed_resource_kinds=None,
        priority_resource_kinds=(),
        prohibited_resource_kinds=(),
        minimum_confidence=0.7,
        reasoning_depth=DomainReasoningDepth.STANDARD,
        allowed_inferences=None,
        prohibited_inferences=(),
        maximum_questions=3,
        escalation_rules=(),
        prohibited_actions=("medical_diagnosis",),
        question_policy=DomainQuestionPolicy(),
        presentation_policy=DomainPresentationPolicy(),
        memory_policy=DomainMemoryPolicy(),
        temporal_policy=DomainTemporalPolicy(),
        production_policy=DomainProductionPolicy(),
        permissions=("health.read",),
        modifications=(),
        trace_id="trace:profile",
        resolved_at=datetime.now(timezone.utc),
        metadata={"source": "resolved"},
    )


def _composition() -> DomainComposition:
    operation = DomainCompositionItem(
        category="operation",
        identifier="health.prepare_medical_appointment",
        contributing_domains=(DomainId("health"), DomainId("general")),
        primary_contributor=DomainId("health"),
        precedence=1,
        metadata={"source": "composition"},
    )
    return DomainComposition(
        id="composition:1",
        resolution_id="resolution:1",
        status=DomainCompositionStatus.COMPOSED,
        primary_domain=DomainId("health"),
        supporting_domains=(DomainId("general"),),
        operations=(operation,),
        permissions=PermissionComposition(
            required_permissions=("health.read",),
            granted_permissions=("health.read",),
            denied_permissions=("health.write",),
            provenance={"health.read": "domain:health"},
        ),
    )


def test_context_consumes_resolved_profile_and_composition_without_recomputing() -> (
    None
):
    request = DomainOperationRequest(
        request_id="request:integration",
        operation_id="health.prepare_medical_appointment",
        operation_version="1.0.0",
        inputs={},
        agent_run_id="run:1",
        task_id="task:1",
        session_id="session:1",
        primary_domain_id="domain:health",
        supporting_domain_ids=("domain:general",),
        granted_permissions=(),
        available_resources=("health.notes",),
        idempotency_key="idem:integration",
    )
    context = DomainOperationContext.from_effective(
        request,
        resolved_profile=_profile(),
        composition=_composition(),
        selected_rule_ids=("rule:health.safety",),
    )
    assert context.primary_domain_id == "domain:health"
    assert context.supporting_domain_ids == ("domain:general",)
    assert context.granted_permissions == ("health.read",)
    assert context.denied_permissions == ("health.write",)
    assert context.profile_id == "profile:health"
    assert context.composition_id == "composition:1"
    assert context.composed_operation_ids == ("health.prepare_medical_appointment",)
    assert context.selected_rule_ids == ("rule:health.safety",)
    assert context.provenance["health.read"] == "domain:health"
    assert DomainOperationContext.from_dict(context.to_dict()) == context
