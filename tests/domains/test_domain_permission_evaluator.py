import pytest

from cmm.agent_runtime.domain_permission_contracts import (
    PermissionCapability,
    PermissionLayer,
    PermissionOutcome,
)
from cmm.domains.permission_contracts import (
    DomainPermissionPolicy,
    DomainPermissionRequest,
)
from cmm.domains.permission_evaluator import evaluate_domain_policy


def request(action, **kwargs):
    return DomainPermissionRequest("r", action, "domain:health", "actor", "session", **kwargs)


def test_policy_allows_internal_read_but_denies_explicit_prohibition():
    policy = DomainPermissionPolicy("p", "domain:health", "1.0.0", allowed_capabilities=(PermissionCapability.RESOURCE_READ,), allowed_resource_kinds=("clinical",), prohibited_resource_kinds=("secret",), allowed_sensitivity_levels=("internal",))
    allowed = evaluate_domain_policy(policy, request(PermissionCapability.RESOURCE_READ, resource_kind="clinical", sensitivity_level="internal"))
    denied = evaluate_domain_policy(policy, request(PermissionCapability.RESOURCE_READ, resource_kind="secret", sensitivity_level="internal"))
    assert allowed.effect is PermissionOutcome.ALLOW
    assert denied.effect is PermissionOutcome.DENY
    assert denied.source is PermissionLayer.DOMAIN


def test_sensitive_capability_requires_policy_approval_and_disabled_denies():
    policy = DomainPermissionPolicy("p", "domain:health", "1.0.0", allowed_capabilities=(PermissionCapability.MEDICAL_DECISION,), approval_capabilities=(PermissionCapability.MEDICAL_DECISION,), approval_requirements=("medical-approval",))
    result = evaluate_domain_policy(policy, request(PermissionCapability.MEDICAL_DECISION))
    assert result.effect is PermissionOutcome.APPROVAL_REQUIRED
    disabled = DomainPermissionPolicy("p2", "domain:health", "1.0.0", enabled=False)
    assert evaluate_domain_policy(disabled, request(PermissionCapability.MEMORY_READ)).effect is PermissionOutcome.DENY


def test_medical_approval_only_applies_after_explicit_base_capability_allow():
    denied_policy = DomainPermissionPolicy("denied", "domain:health", "1.0.0")
    denied = evaluate_domain_policy(
        denied_policy, request(PermissionCapability.MEDICAL_DECISION)
    )
    assert denied.effect is PermissionOutcome.DENY

    allowed_policy = DomainPermissionPolicy(
        "allowed",
        "domain:health",
        "1.0.0",
        allowed_capabilities=(PermissionCapability.MEDICAL_DECISION,),
        approval_capabilities=(PermissionCapability.MEDICAL_DECISION,),
    )
    pending = evaluate_domain_policy(
        allowed_policy, request(PermissionCapability.MEDICAL_DECISION)
    )
    assert pending.effect is PermissionOutcome.APPROVAL_REQUIRED
    requirement = pending.approval_requirements[0]
    assert requirement.action is PermissionCapability.MEDICAL_DECISION
    assert requirement.actor_id == "actor"
    assert requirement.session_id == "session"
    assert requirement.domain_id == "domain:health"


@pytest.mark.parametrize(
    ("action", "kwargs"),
    [
        (PermissionCapability.RESOURCE_READ, {"resource_kind": "clinical"}),
        (PermissionCapability.MEMORY_READ, {}),
        (PermissionCapability.EXPORT, {}),
        (PermissionCapability.MODEL_EXTERNAL, {}),
        (PermissionCapability.SENSITIVE_INFERENCE, {}),
    ],
)
def test_unknown_sensitivity_is_not_implicitly_allowed_for_sensitive_actions(action, kwargs):
    policy = DomainPermissionPolicy(
        "sensitive", "domain:health", "1.0.0",
        allowed_capabilities=(action,),
        allowed_resource_kinds=("clinical",),
    )
    result = evaluate_domain_policy(policy, request(action, **kwargs))
    assert result.effect is PermissionOutcome.DENY


@pytest.mark.parametrize(
    "action",
    [
        PermissionCapability.COMMUNICATION_EXTERNAL,
        PermissionCapability.PUBLICATION,
        PermissionCapability.SCHEDULE_MODIFY,
        PermissionCapability.FILE_MODIFY,
        PermissionCapability.IRREVERSIBLE_CHANGE,
        PermissionCapability.KNOWLEDGE_DELETE,
        PermissionCapability.MEDICAL_DECISION,
        PermissionCapability.MEDICAL_ACTION,
        PermissionCapability.LEGAL_DECISION,
        PermissionCapability.LEGAL_ACTION,
        PermissionCapability.FINANCIAL_DECISION,
        PermissionCapability.FINANCIAL_ACTION,
        PermissionCapability.FINANCIAL_SPEND,
        PermissionCapability.PERMISSION_MODIFY,
    ],
)
def test_roadmap_high_impact_capabilities_require_approval_even_if_policy_omits_it(action):
    policy = DomainPermissionPolicy(
        "p", "domain:health", "1.0.0", allowed_capabilities=(action,)
    )

    result = evaluate_domain_policy(policy, request(action))

    assert result.effect is PermissionOutcome.APPROVAL_REQUIRED
    assert result.approval_requirements[0].action is action


def test_sensitive_cross_domain_and_sensitive_inference_persistence_require_approval():
    policy = DomainPermissionPolicy(
        "p", "domain:health", "1.0.0",
        allowed_capabilities=(
            PermissionCapability.DOMAIN_CROSS_ACCESS,
            PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
        ),
        allow_cross_domain_access=True,
        allowed_target_domains=("domain:project",),
        allowed_sensitivity_levels=("confidential",),
    )
    cross = request(
        PermissionCapability.DOMAIN_CROSS_ACCESS,
        source_domain="domain:health", target_domain="domain:project",
        sensitivity_level="confidential",
    )
    persistence = request(
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
        sensitivity_level="confidential",
    )

    assert evaluate_domain_policy(policy, cross).effect is PermissionOutcome.APPROVAL_REQUIRED
    assert evaluate_domain_policy(policy, persistence).effect is PermissionOutcome.APPROVAL_REQUIRED


def test_caller_cannot_self_declare_external_domain_trust():
    policy = DomainPermissionPolicy(
        "p", "domain:health", "1.0.0",
        allowed_capabilities=(PermissionCapability.EXTERNAL_DOMAIN_ACTIVATE,),
    )

    untrusted = evaluate_domain_policy(
        policy, request(PermissionCapability.EXTERNAL_DOMAIN_ACTIVATE)
    )
    trusted = evaluate_domain_policy(
        policy,
        request(
            PermissionCapability.EXTERNAL_DOMAIN_ACTIVATE,
            external_domain_trusted=True,
        ),
    )

    assert untrusted.effect is PermissionOutcome.APPROVAL_REQUIRED
    assert trusted.effect is PermissionOutcome.APPROVAL_REQUIRED
    assert trusted.metadata["legacy_external_domain_trusted_ignored"] is True
    assert "legacy_external_domain_trusted_ignored" in trusted.reasons
