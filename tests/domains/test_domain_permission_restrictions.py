"""Phase 10.15 declarative restriction and effect-separation tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cmm.agent_runtime.agent_security_enums import SensitivityLevel
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionApprovalRequirement,
    PermissionCapability,
    PermissionLayerEvaluation,
    PermissionOutcome,
)
from cmm.agent_runtime.errors import InvalidPermissionRestrictionError
from cmm.agent_runtime.permission_restriction_contracts import (
    ExportContentKind,
    ExportPolicy,
    ExportRequest,
    ExternalProviderEgressPolicy,
    ExternalProviderEgressRequest,
    ExternalSourceClass,
    ExternalSourceRequirement,
    ExternalSourceUse,
    PostVerificationKind,
    PostVerificationRequirement,
    ProviderLocation,
)
from cmm.domains.permission_contracts import (
    DomainPermissionPolicy,
    DomainPermissionRequest,
)
from cmm.domains.permission_evaluator import evaluate_domain_policy


def _policy(action: PermissionCapability, **changes: object) -> DomainPermissionPolicy:
    values: dict[str, object] = {
        "policy_id": "policy:restrictions",
        "domain_id": "domain:project",
        "version": "1.0.0",
        "allowed_capabilities": (action,),
        "allowed_sensitivity_levels": tuple(SensitivityLevel),
    }
    values.update(changes)
    return DomainPermissionPolicy(**values)  # type: ignore[arg-type]


def _request(action: PermissionCapability, **changes: object) -> DomainPermissionRequest:
    values: dict[str, object] = {
        "request_id": "request:1",
        "action": action,
        "domain_id": "domain:project",
        "actor_id": "actor:1",
        "session_id": "session:1",
        "sensitivity_level": SensitivityLevel.INTERNAL,
        "purpose": "deliverable",
    }
    values.update(changes)
    return DomainPermissionRequest(**values)  # type: ignore[arg-type]


def test_official_only_rejects_general_web() -> None:
    policy = _policy(
        PermissionCapability.SEARCH_EXTERNAL,
        source_requirement=ExternalSourceRequirement(
            minimum_source_class=ExternalSourceClass.OFFICIAL_ONLY
        ),
    )
    request = _request(
        PermissionCapability.SEARCH_EXTERNAL,
        source_use=ExternalSourceUse(
            source_class=ExternalSourceClass.GENERAL_WEB,
            domain="example.test",
        ),
    )
    result = evaluate_domain_policy(policy, request)
    assert result.effect is PermissionOutcome.DENY
    assert result.reasons == ("source_class_below_minimum",)


def test_unknown_source_class_fails_closed() -> None:
    with pytest.raises(InvalidPermissionRestrictionError):
        ExternalSourceUse(source_class="unknown", domain="example.test")


def test_external_model_permission_does_not_authorize_sensitive_egress() -> None:
    result = evaluate_domain_policy(
        _policy(PermissionCapability.MODEL_EXTERNAL),
        _request(PermissionCapability.MODEL_EXTERNAL, sensitivity_level=SensitivityLevel.SECRET),
    )
    assert result.effect is PermissionOutcome.DENY
    assert result.reasons == ("egress_policy_missing",)


def test_remote_provider_respects_maximum_sensitivity() -> None:
    policy = _policy(
        PermissionCapability.MODEL_EXTERNAL,
        egress_policy=_egress_policy(maximum_sensitivity=SensitivityLevel.INTERNAL),
    )
    request = _request(
        PermissionCapability.MODEL_EXTERNAL,
        sensitivity_level=SensitivityLevel.CONFIDENTIAL,
        egress_request=_egress_request(sensitivity=SensitivityLevel.CONFIDENTIAL),
    )
    assert evaluate_domain_policy(policy, request).reasons == ("egress_sensitivity_exceeded",)


def test_local_provider_does_not_inherit_remote_policy() -> None:
    policy = _policy(PermissionCapability.MODEL_EXTERNAL, egress_policy=_egress_policy())
    request = _request(
        PermissionCapability.MODEL_EXTERNAL,
        egress_request=_egress_request(provider_location=ProviderLocation.LOCAL),
    )
    assert evaluate_domain_policy(policy, request).reasons == ("egress_provider_location_mismatch",)


def test_egress_purpose_and_provider_must_match() -> None:
    policy = _policy(PermissionCapability.MODEL_EXTERNAL, egress_policy=_egress_policy())
    wrong_provider = _request(
        PermissionCapability.MODEL_EXTERNAL,
        egress_request=_egress_request(provider_id="provider:other"),
    )
    wrong_purpose = _request(
        PermissionCapability.MODEL_EXTERNAL,
        egress_request=_egress_request(purpose="profiling"),
    )
    assert evaluate_domain_policy(policy, wrong_provider).effect is PermissionOutcome.DENY
    assert evaluate_domain_policy(policy, wrong_purpose).effect is PermissionOutcome.DENY


def _egress_policy(**changes: object) -> ExternalProviderEgressPolicy:
    values: dict[str, object] = {
        "provider_id": "provider:remote",
        "provider_location": ProviderLocation.REMOTE,
        "allowed_source_domains": ("domain:project",),
        "maximum_sensitivity": SensitivityLevel.CONFIDENTIAL,
        "allowed_data_categories": ("project_notes",),
        "allowed_purposes": ("deliverable",),
        "allowed_resource_ids": ("resource:brief",),
        "allowed_claims": ("summarize",),
        "require_redaction": True,
        "allow_retention": False,
    }
    values.update(changes)
    return ExternalProviderEgressPolicy(**values)  # type: ignore[arg-type]


def _egress_request(**changes: object) -> ExternalProviderEgressRequest:
    values: dict[str, object] = {
        "provider_id": "provider:remote",
        "provider_location": ProviderLocation.REMOTE,
        "source_domains": ("domain:project",),
        "sensitivity": SensitivityLevel.INTERNAL,
        "data_categories": ("project_notes",),
        "purpose": "deliverable",
        "resource_ids": ("resource:brief",),
        "claims": ("summarize",),
        "redaction_applied": True,
        "retention_requested": False,
    }
    values.update(changes)
    return ExternalProviderEgressRequest(**values)  # type: ignore[arg-type]


def _export_policy(**changes: object) -> ExportPolicy:
    values: dict[str, object] = {
        "allowed_recipients": ("recipient:client",),
        "allowed_recipient_classes": ("client",),
        "allowed_purposes": ("deliverable",),
        "allowed_formats": ("pdf",),
        "allowed_data_categories": ("summary",),
        "allowed_identifiers": ("project_id",),
        "prohibited_identifiers": ("personal_id",),
        "maximum_sensitivity": SensitivityLevel.CONFIDENTIAL,
        "allow_original_evidence": False,
        "require_redaction": True,
        "one_time": True,
    }
    values.update(changes)
    return ExportPolicy(**values)  # type: ignore[arg-type]


def _export_request(**changes: object) -> ExportRequest:
    values: dict[str, object] = {
        "recipient_id": "recipient:client",
        "recipient_class": "client",
        "purpose": "deliverable",
        "format": "pdf",
        "data_categories": ("summary",),
        "identifiers": ("project_id",),
        "content_kind": ExportContentKind.SUMMARY,
        "sensitivity": SensitivityLevel.INTERNAL,
        "redaction_applied": True,
        "tokenization_applied": False,
    }
    values.update(changes)
    return ExportRequest(**values)  # type: ignore[arg-type]


def test_export_does_not_include_unauthorized_identifiers() -> None:
    result = evaluate_domain_policy(
        _policy(PermissionCapability.EXPORT, export_policy=_export_policy()),
        _request(PermissionCapability.EXPORT, export_request=_export_request(identifiers=("personal_id",))),
    )
    assert result.effect is PermissionOutcome.DENY
    assert result.reasons == ("export_identifier_prohibited",)


def test_summary_export_does_not_authorize_original_evidence() -> None:
    result = evaluate_domain_policy(
        _policy(PermissionCapability.EXPORT, export_policy=_export_policy()),
        _request(PermissionCapability.EXPORT, export_request=_export_request(content_kind=ExportContentKind.ORIGINAL_EVIDENCE)),
    )
    assert result.effect is PermissionOutcome.DENY
    assert result.reasons == ("export_original_evidence_not_allowed",)


def test_read_permission_does_not_authorize_export() -> None:
    request = _request(PermissionCapability.EXPORT, export_request=_export_request())
    result = evaluate_domain_policy(_policy(PermissionCapability.RESOURCE_READ), request)
    assert result.effect is PermissionOutcome.DENY


def test_inference_permission_does_not_authorize_persistence_or_egress() -> None:
    policy = _policy(PermissionCapability.SENSITIVE_INFERENCE)
    persistence = evaluate_domain_policy(policy, _request(PermissionCapability.SENSITIVE_INFERENCE_PERSIST))
    egress = evaluate_domain_policy(policy, _request(PermissionCapability.MODEL_EXTERNAL))
    assert persistence.effect is PermissionOutcome.DENY
    assert egress.effect is PermissionOutcome.DENY


def test_external_mutation_returns_post_verification_requirement() -> None:
    requirement = PostVerificationRequirement(
        kinds=(PostVerificationKind.REFETCH, PostVerificationKind.COMPARISON),
        resource_ids=("resource:brief",),
    )
    result = evaluate_domain_policy(
        _policy(PermissionCapability.FILE_MODIFY, post_verification=requirement),
        _request(PermissionCapability.FILE_MODIFY),
    )
    assert result.to_dict()["constraints"]["post_verification"] == requirement.to_dict()


def test_post_verification_requirement_round_trip() -> None:
    requirement = PostVerificationRequirement(
        kinds=(PostVerificationKind.DISPATCH_CONFIRMATION, PostVerificationKind.RESULT_EVIDENCE),
        resource_ids=("resource:brief",),
        comparison_fields=("status",),
    )
    assert PostVerificationRequirement.from_dict(requirement.to_dict()) == requirement


def test_post_verification_effective_constraint_round_trip() -> None:
    requirement = PostVerificationRequirement(
        kinds=(PostVerificationKind.MANUAL_VERIFICATION,),
        resource_ids=("resource:brief",),
    )
    evaluation = evaluate_domain_policy(
        _policy(PermissionCapability.FILE_MODIFY, post_verification=requirement),
        _request(PermissionCapability.FILE_MODIFY),
    )
    assert PermissionLayerEvaluation.from_dict(evaluation.to_dict()) == evaluation


def test_restriction_contracts_round_trip_and_policy_backward_compatibility() -> None:
    source = ExternalSourceRequirement(
        minimum_source_class=ExternalSourceClass.PRIMARY_SOURCES,
        allowed_domains=("official.test",),
        require_additional_verification=True,
    )
    egress = _egress_policy()
    export = _export_policy()
    for value in (source, egress, export, _egress_request(), _export_request()):
        assert type(value).from_dict(value.to_dict()) == value
    policy = _policy(
        PermissionCapability.EXPORT,
        source_requirement=source,
        egress_policy=egress,
        export_policy=export,
        post_verification=PostVerificationRequirement(
            kinds=(PostVerificationKind.RESULT_EVIDENCE,)
        ),
    )
    assert DomainPermissionPolicy.from_dict(policy.to_dict()) == policy
    request = _request(PermissionCapability.EXPORT, export_request=_export_request())
    assert DomainPermissionRequest.from_dict(request.to_dict()) == request
    legacy = DomainPermissionPolicy.from_dict({
        "policy_id": "legacy", "domain_id": "domain:project", "version": "1.0.0"
    })
    assert legacy.source_requirement is None
    assert legacy.egress_policy is None
    assert legacy.export_policy is None


def test_restriction_contracts_are_public_agent_runtime_api() -> None:
    import cmm.agent_runtime as runtime

    for name in (
        "ExternalSourceClass", "ExternalSourceRequirement", "ExternalSourceUse",
        "ProviderLocation", "ExternalProviderEgressPolicy", "ExternalProviderEgressRequest",
        "ExportContentKind", "ExportPolicy", "ExportRequest",
        "PostVerificationKind", "PostVerificationRequirement",
    ):
        assert name in runtime.__all__
        assert hasattr(runtime, name)


def test_export_expiration_fails_closed() -> None:
    expired = datetime.now(timezone.utc) - timedelta(seconds=1)
    result = evaluate_domain_policy(
        _policy(PermissionCapability.EXPORT, export_policy=_export_policy(expires_at=expired)),
        _request(PermissionCapability.EXPORT, export_request=_export_request()),
        now=datetime.now(timezone.utc),
    )
    assert result.reasons == ("export_policy_expired",)


def test_approval_binds_exact_egress_purpose_provider_and_resources() -> None:
    policy = _policy(
        PermissionCapability.MODEL_EXTERNAL,
        egress_policy=_egress_policy(require_approval=True),
    )
    request = _request(PermissionCapability.MODEL_EXTERNAL, egress_request=_egress_request())
    result = evaluate_domain_policy(policy, request)
    assert result.effect is PermissionOutcome.APPROVAL_REQUIRED
    requirement = result.approval_requirements[0]
    assert requirement.to_dict()["constraints"]["bound_egress"] == request.egress_request.to_dict()
    assert PermissionApprovalRequirement.from_dict(requirement.to_dict()) == requirement


def test_consent_is_an_approval_obligation_not_a_caller_grant() -> None:
    policy = _policy(
        PermissionCapability.MODEL_EXTERNAL,
        egress_policy=_egress_policy(require_consent=True),
    )
    request = _request(PermissionCapability.MODEL_EXTERNAL, egress_request=_egress_request())
    assert evaluate_domain_policy(policy, request).effect is PermissionOutcome.APPROVAL_REQUIRED


def test_export_approval_preserves_expiration_and_reuse_policy() -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    policy = _policy(
        PermissionCapability.EXPORT,
        export_policy=_export_policy(
            expires_at=expires_at,
            one_time=False,
            require_approval=True,
        ),
    )
    result = evaluate_domain_policy(
        policy,
        _request(PermissionCapability.EXPORT, export_request=_export_request()),
        now=datetime.now(timezone.utc),
    )
    requirement = result.approval_requirements[0]
    assert requirement.expires_at == expires_at.isoformat()
    assert requirement.one_time is False
    assert requirement.reusable is True


def test_effect_capabilities_do_not_imply_distinct_effects() -> None:
    read_policy = _policy(PermissionCapability.RESOURCE_READ)
    mutate_policy = _policy(PermissionCapability.FILE_MODIFY)
    persist_policy = _policy(PermissionCapability.SENSITIVE_INFERENCE_PERSIST)
    internal_policy = _policy(PermissionCapability.OPERATION_EXECUTE)
    assert evaluate_domain_policy(read_policy, _request(PermissionCapability.FILE_MODIFY)).effect is PermissionOutcome.DENY
    assert evaluate_domain_policy(mutate_policy, _request(PermissionCapability.EXPORT)).effect is PermissionOutcome.DENY
    assert evaluate_domain_policy(persist_policy, _request(PermissionCapability.MODEL_EXTERNAL)).effect is PermissionOutcome.DENY
    assert evaluate_domain_policy(internal_policy, _request(PermissionCapability.COMMUNICATION_EXTERNAL)).effect is PermissionOutcome.DENY
