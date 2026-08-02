"""Pure and conservative evaluation of a domain permission policy."""

from __future__ import annotations

from datetime import datetime

from cmm.agent_runtime.agent_security_enums import SensitivityLevel
from cmm.agent_runtime.domain_permission_contracts import (
    MANDATORY_APPROVAL_CAPABILITIES,
    PermissionApprovalRequirement,
    PermissionCapability,
    PermissionLayer,
    PermissionLayerEvaluation,
    PermissionOutcome,
)
from cmm.agent_runtime.permission_restriction_contracts import (
    ExportContentKind,
    ExternalSourceClass,
)
from cmm.domains.permission_contracts import (
    DomainPermissionPolicy,
    DomainPermissionRequest,
)

_RESOURCE_ACTIONS = frozenset(
    {
        PermissionCapability.RESOURCE_READ,
        PermissionCapability.KNOWLEDGE_READ,
        PermissionCapability.ENTITY_READ,
        PermissionCapability.RELATIONSHIP_READ,
    }
)
_UNKNOWN_SENSITIVITY_DENY = _RESOURCE_ACTIONS | frozenset(
    {
        PermissionCapability.MEMORY_READ,
        PermissionCapability.MEMORY_WRITE,
        PermissionCapability.EXPORT,
        PermissionCapability.MODEL_EXTERNAL,
        PermissionCapability.SENSITIVE_INFERENCE,
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
        PermissionCapability.DOMAIN_CROSS_ACCESS,
    }
)


def _effective_constraints(policy: DomainPermissionPolicy) -> dict[str, object]:
    constraints: dict[str, object] = {
        key: value
        for key, value in policy.autonomy_limits.to_dict().items()
        if key.startswith("maximum_") and value is not None
    }
    if policy.post_verification is not None:
        constraints["post_verification"] = policy.post_verification.to_dict()
    return constraints


_SOURCE_RANK = {
    ExternalSourceClass.GENERAL_WEB: 0,
    ExternalSourceClass.TRUSTED_SECONDARY: 1,
    ExternalSourceClass.PRIMARY_SOURCES: 2,
    ExternalSourceClass.OFFICIAL_ONLY: 3,
}
_SENSITIVITY_RANK = {
    SensitivityLevel.PUBLIC: 0,
    SensitivityLevel.INTERNAL: 1,
    SensitivityLevel.CONFIDENTIAL: 2,
    SensitivityLevel.RESTRICTED: 3,
    SensitivityLevel.SECRET: 4,
}


def _source_denial(policy: DomainPermissionPolicy, request: DomainPermissionRequest) -> str | None:
    requirement = policy.source_requirement
    if request.action is not PermissionCapability.SEARCH_EXTERNAL:
        return "external_source_capability_required" if request.source_use is not None else None
    if requirement is None:
        return None
    used = request.source_use
    if used is None:
        return "source_class_missing"
    if _SOURCE_RANK[used.source_class] < _SOURCE_RANK[requirement.minimum_source_class]:
        return "source_class_below_minimum"
    if used.domain in requirement.prohibited_domains:
        return "source_domain_prohibited"
    if requirement.allowed_domains and used.domain not in requirement.allowed_domains:
        return "source_domain_not_allowed"
    if requirement.require_additional_verification and not used.additional_verification:
        return "source_additional_verification_required"
    return None


def _not_subset(requested: tuple[str, ...], allowed: tuple[str, ...]) -> bool:
    return bool(set(requested) - set(allowed))


def _egress_denial(policy: DomainPermissionPolicy, request: DomainPermissionRequest) -> str | None:
    egress_actions = {
        PermissionCapability.MODEL_EXTERNAL,
        PermissionCapability.COMMUNICATION_EXTERNAL,
    }
    if request.action not in egress_actions:
        return "egress_capability_required" if request.egress_request is not None else None
    if (
        request.action is PermissionCapability.COMMUNICATION_EXTERNAL
        and request.egress_request is None
    ):
        return None
    expected = policy.egress_policy
    if expected is None:
        return "egress_policy_missing"
    actual = request.egress_request
    if actual is None:
        return "egress_request_missing"
    if actual.provider_id != expected.provider_id:
        return "egress_provider_mismatch"
    if actual.provider_location is not expected.provider_location:
        return "egress_provider_location_mismatch"
    if _not_subset(actual.source_domains, expected.allowed_source_domains):
        return "egress_source_domain_not_allowed"
    if _SENSITIVITY_RANK[actual.sensitivity] > _SENSITIVITY_RANK[expected.maximum_sensitivity]:
        return "egress_sensitivity_exceeded"
    if actual.sensitivity is not request.sensitivity_level:
        return "egress_sensitivity_binding_mismatch"
    for requested, allowed, reason in (
        (actual.data_categories, expected.allowed_data_categories, "egress_data_category_not_allowed"),
        (actual.resource_ids, expected.allowed_resource_ids, "egress_resource_not_allowed"),
        (actual.claims, expected.allowed_claims, "egress_claim_not_allowed"),
    ):
        if _not_subset(requested, allowed):
            return reason
    if actual.purpose not in expected.allowed_purposes or actual.purpose != request.purpose:
        return "egress_purpose_mismatch"
    if expected.require_redaction and not actual.redaction_applied:
        return "egress_redaction_required"
    if actual.retention_requested and not expected.allow_retention:
        return "egress_retention_not_allowed"
    return None


def _export_denial(policy: DomainPermissionPolicy, request: DomainPermissionRequest, now: datetime | None) -> str | None:
    if request.action is not PermissionCapability.EXPORT:
        return "export_capability_required" if request.export_request is not None else None
    expected = policy.export_policy
    if expected is None:
        return "export_policy_missing"
    actual = request.export_request
    if actual is None:
        return "export_request_missing"
    if expected.expires_at is not None:
        if now is None:
            return "export_time_context_missing"
        if now.tzinfo is None or now >= expected.expires_at:
            return "export_policy_expired"
    checks = (
        (actual.recipient_id, expected.allowed_recipients, "export_recipient_not_allowed"),
        (actual.recipient_class, expected.allowed_recipient_classes, "export_recipient_class_not_allowed"),
        (actual.purpose, expected.allowed_purposes, "export_purpose_not_allowed"),
        (actual.format, expected.allowed_formats, "export_format_not_allowed"),
    )
    for value, allowed, reason in checks:
        if value not in allowed:
            return reason
    if actual.purpose != request.purpose:
        return "export_purpose_binding_mismatch"
    if _not_subset(actual.data_categories, expected.allowed_data_categories):
        return "export_data_category_not_allowed"
    if set(actual.identifiers) & set(expected.prohibited_identifiers):
        return "export_identifier_prohibited"
    if _not_subset(actual.identifiers, expected.allowed_identifiers):
        return "export_identifier_not_allowed"
    if actual.content_kind is ExportContentKind.ORIGINAL_EVIDENCE and not expected.allow_original_evidence:
        return "export_original_evidence_not_allowed"
    if _SENSITIVITY_RANK[actual.sensitivity] > _SENSITIVITY_RANK[expected.maximum_sensitivity]:
        return "export_sensitivity_exceeded"
    if actual.sensitivity is not request.sensitivity_level:
        return "export_sensitivity_binding_mismatch"
    if expected.require_redaction and not actual.redaction_applied:
        return "export_redaction_required"
    if expected.require_tokenization and not actual.tokenization_applied:
        return "export_tokenization_required"
    return None


def _allowlist(value: tuple[str, ...] | None, requested: str | None) -> bool:
    return value is None or (requested is not None and bool(value) and requested in value)


def _legacy_capability(policy: DomainPermissionPolicy, action: PermissionCapability) -> bool:
    return {
        PermissionCapability.MEMORY_READ: policy.allow_memory_read,
        PermissionCapability.MEMORY_WRITE: policy.allow_memory_write,
        PermissionCapability.SENSITIVE_INFERENCE: policy.allow_sensitive_inference,
        PermissionCapability.SEARCH_EXTERNAL: policy.allow_external_search,
        PermissionCapability.MODEL_EXTERNAL: policy.allow_external_models,
        PermissionCapability.COMMUNICATION_EXTERNAL: policy.allow_external_communication,
        PermissionCapability.FILE_MODIFY: policy.allow_file_modification,
        PermissionCapability.TASK_CREATE: policy.allow_task_creation,
        PermissionCapability.SCHEDULE_MODIFY: policy.allow_schedule_modification,
        PermissionCapability.GOAL_UPDATE: policy.allow_goal_update,
        PermissionCapability.EXPORT: policy.allow_export,
        PermissionCapability.DOMAIN_CROSS_ACCESS: policy.allow_cross_domain_access,
    }.get(action, action in _RESOURCE_ACTIONS)


def _capability_allowed(
    policy: DomainPermissionPolicy,
    action: PermissionCapability,
    *,
    inbound_cross_domain: bool = False,
) -> bool:
    if action in policy.prohibited_capabilities:
        return False
    if action is PermissionCapability.DOMAIN_CROSS_ACCESS and inbound_cross_domain:
        return policy.allow_inbound_cross_domain_access
    if policy.allowed_capabilities:
        return action in policy.allowed_capabilities
    return _legacy_capability(policy, action)


def _sensitivity_allowed(policy: DomainPermissionPolicy, request: DomainPermissionRequest) -> bool:
    if request.sensitivity_level is None:
        return request.action not in _UNKNOWN_SENSITIVITY_DENY
    if request.sensitivity_level in policy.prohibited_sensitivity_levels:
        return False
    return policy.allowed_sensitivity_levels is None or request.sensitivity_level in policy.allowed_sensitivity_levels


def _approval_requirement(
    policy: DomainPermissionPolicy, request: DomainPermissionRequest
) -> PermissionApprovalRequirement:
    action = request.action
    risk = "critical" if action in {
        PermissionCapability.MEDICAL_DECISION,
        PermissionCapability.MEDICAL_ACTION,
        PermissionCapability.LEGAL_DECISION,
        PermissionCapability.LEGAL_ACTION,
        PermissionCapability.FINANCIAL_DECISION,
        PermissionCapability.FINANCIAL_ACTION,
        PermissionCapability.FINANCIAL_SPEND,
    } else "high"
    scope = (
        "operation"
        if action is PermissionCapability.OPERATION_EXECUTE
        else "workflow"
        if action is PermissionCapability.WORKFLOW_EXECUTE
        else "resource"
        if action in _RESOURCE_ACTIONS
        else "cross_domain"
        if action is PermissionCapability.DOMAIN_CROSS_ACCESS
        else "request"
    )
    constraints = _effective_constraints(policy)
    if request.source_use is not None:
        constraints["bound_source_use"] = request.source_use.to_dict()
    if request.egress_request is not None:
        constraints["bound_egress"] = request.egress_request.to_dict()
    if request.export_request is not None:
        constraints["bound_export"] = request.export_request.to_dict()
    one_time = (
        policy.export_policy.one_time
        if action is PermissionCapability.EXPORT and policy.export_policy is not None
        else True
    )
    expiration_candidates = tuple(
        value
        for value in (
            policy.expires_at,
            policy.export_policy.expires_at if policy.export_policy is not None else None,
        )
        if value is not None
    )
    expires_at = min(expiration_candidates).isoformat() if expiration_candidates else None
    return PermissionApprovalRequirement(
        requirement_id=f"{policy.policy_id}:{policy.version}:{request.request_id}:{action.value}",
        action=action,
        actor_id=request.actor_id,
        session_id=request.session_id,
        domain_id=request.domain_id,
        resource_id=request.resource_id,
        resource_kind=request.resource_kind,
        operation_id=request.operation_id,
        operation_version=request.operation_version,
        workflow_id=request.workflow_id,
        workflow_version=request.workflow_version,
        source_domain=request.source_domain,
        target_domain=request.target_domain,
        purpose=request.purpose,
        sensitivity=request.sensitivity_level,
        fingerprint=f"{request.request_id}:{action.value}:{request.actor_id}:{request.session_id}:{request.domain_id}",
        expires_at=expires_at,
        scope=scope,
        one_time=one_time,
        reusable=not one_time,
        constraints=constraints,
        reason_code=action.value if action.value in policy.approval_requirements else "approval_required",
        risk=risk,
    )


def _requires_mandatory_approval(request: DomainPermissionRequest) -> bool:
    if request.action in MANDATORY_APPROVAL_CAPABILITIES:
        return True
    if request.action is PermissionCapability.DOMAIN_CROSS_ACCESS:
        return request.sensitivity_level in {
            SensitivityLevel.CONFIDENTIAL,
            SensitivityLevel.RESTRICTED,
            SensitivityLevel.SECRET,
        }
    # The request-level legacy flag is never an authoritative trust source.
    return request.action is PermissionCapability.EXTERNAL_DOMAIN_ACTIVATE


def evaluate_domain_policy(
    policy: DomainPermissionPolicy,
    request: DomainPermissionRequest,
    *,
    domain_role: str = "primary",
    cross_domain_direction: str = "outbound",
    now: datetime | None = None,
) -> PermissionLayerEvaluation:
    if cross_domain_direction not in {"outbound", "inbound"}:
        raise ValueError("cross_domain_direction must be outbound or inbound")
    if not policy.enabled:
        return PermissionLayerEvaluation(PermissionLayer.DOMAIN, PermissionOutcome.DENY, source_id=f"{domain_role}:{policy.policy_id}:{policy.version}", policy_id=policy.policy_id, policy_version=policy.version, domain_role=domain_role, reasons=("policy_disabled",), matched_rules=(policy.policy_id,))
    if policy.expires_at is not None:
        if now is None:
            raise ValueError("now must be injected when evaluating temporal policies")
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        if now >= policy.expires_at:
            return PermissionLayerEvaluation(PermissionLayer.DOMAIN, PermissionOutcome.DENY, source_id=f"{domain_role}:{policy.policy_id}:{policy.version}", policy_id=policy.policy_id, policy_version=policy.version, domain_role=domain_role, reasons=("policy_expired",), matched_rules=(policy.policy_id,))
    action = request.action
    denied_reason: str | None = None
    if not _capability_allowed(
        policy,
        action,
        inbound_cross_domain=cross_domain_direction == "inbound",
    ):
        denied_reason = "capability_not_allowed"
    elif not _sensitivity_allowed(policy, request):
        denied_reason = "sensitivity_not_allowed"
    else:
        if action in _RESOURCE_ACTIONS:
            if request.resource_id is not None and request.resource_id in policy.prohibited_resources:
                denied_reason = "explicit_resource_prohibition"
            elif policy.allowed_resources is not None and not _allowlist(policy.allowed_resources, request.resource_id):
                denied_reason = "resource_allowlist_not_matched"
            elif request.resource_kind is not None and request.resource_kind in policy.prohibited_resource_kinds:
                denied_reason = "explicit_resource_kind_prohibition"
            elif policy.allowed_resource_kinds is not None and not _allowlist(policy.allowed_resource_kinds, request.resource_kind):
                denied_reason = "resource_kind_allowlist_not_matched"
        elif action is PermissionCapability.OPERATION_EXECUTE:
            if request.operation_id in policy.prohibited_operations:
                denied_reason = "explicit_prohibition"
            elif not _allowlist(policy.allowed_operations, request.operation_id):
                denied_reason = "allowlist_not_matched"
        elif action is PermissionCapability.WORKFLOW_EXECUTE:
            if request.workflow_id in policy.prohibited_workflows:
                denied_reason = "explicit_prohibition"
            elif not _allowlist(policy.allowed_workflows, request.workflow_id):
                denied_reason = "allowlist_not_matched"
        elif action is PermissionCapability.DOMAIN_CROSS_ACCESS:
            if cross_domain_direction == "inbound":
                if request.source_domain is not None and (
                    request.source_domain in policy.prohibited_source_domains
                    or (
                        policy.allowed_source_domains is not None
                        and request.source_domain not in policy.allowed_source_domains
                    )
                ):
                    denied_reason = "source_domain_not_allowed"
            elif request.target_domain is not None and (
                request.target_domain in policy.prohibited_target_domains
                or (
                    policy.allowed_target_domains is not None
                    and request.target_domain not in policy.allowed_target_domains
                )
            ):
                denied_reason = "target_domain_not_allowed"
    if denied_reason is None:
        denied_reason = _source_denial(policy, request)
    if denied_reason is None:
        denied_reason = _egress_denial(policy, request)
    if denied_reason is None:
        denied_reason = _export_denial(policy, request, now)
    requirement = (
        _approval_requirement(policy, request)
        if denied_reason is None
        and (
            action in policy.approval_capabilities
            or _requires_mandatory_approval(request)
            or (policy.egress_policy is not None and policy.egress_policy.require_approval)
            or (policy.egress_policy is not None and policy.egress_policy.require_consent)
            or (policy.export_policy is not None and policy.export_policy.require_approval)
        )
        else None
    )
    effect = PermissionOutcome.DENY if denied_reason else PermissionOutcome.APPROVAL_REQUIRED if requirement else PermissionOutcome.ALLOW
    reasons = (denied_reason or ("approval_required" if requirement else "policy_allow"),)
    metadata = {"policy_id": policy.policy_id, "policy_version": policy.version}
    if (
        action is PermissionCapability.EXTERNAL_DOMAIN_ACTIVATE
        and request.external_domain_trusted
    ):
        reasons = (*reasons, "legacy_external_domain_trusted_ignored")
        metadata["legacy_external_domain_trusted_ignored"] = True
    return PermissionLayerEvaluation(
        PermissionLayer.DOMAIN,
        effect,
        source_id=f"{domain_role}:{policy.policy_id}:{policy.version}",
        policy_id=policy.policy_id,
        policy_version=policy.version,
        domain_role=domain_role,
        matched_rules=(policy.policy_id,),
        reasons=reasons,
        approval_requirements=(requirement,) if requirement else (),
        constraints=_effective_constraints(policy),
        metadata=metadata,
    )


__all__ = ["evaluate_domain_policy"]
