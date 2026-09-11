"""Phase 10.50 – Phase 10.15 permission authority over Domain privacy.

Privacy may restrict; it may never grant cross-domain authority. These tests use
the real Phase 10.15 registry, resolver, gate and policy evaluator together with
the real canonical Phase 8 privacy evaluator. No authority component is replaced
by a caller boolean.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.agent_runtime.agent_security_enums import (
    SensitivityLevel as PermissionSensitivity,
)
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionCapability,
    PermissionOutcome,
)
from cmm.cognitive.enums import SensitivityLevel
from cmm.cognitive.privacy import (
    PrivacyDecisionStatus,
    PrivacyMetadata,
    PrivacyOperation,
    PrivacyOperationContext,
    PrivacyPolicy,
    ProcessingLocation,
    evaluate_privacy_operation,
    resolve_effective_privacy_metadata,
)
from cmm.domains.errors import DomainPrivacyPolicySerializationError
from cmm.domains.identifiers import DomainId
from cmm.domains.permission_contracts import (
    CrossDomainPermissionRequest,
    DomainPermissionPolicy,
    DomainPermissionRequest,
)
from cmm.domains.permission_evaluator import evaluate_domain_policy
from cmm.domains.permission_gate import DomainPermissionGate
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.privacy_policy_contracts import (
    DomainPrivacyPolicy,
    project_domain_privacy_metadata,
)

NOW = datetime(2026, 9, 11, 10, 0, tzinfo=timezone.utc)

SOURCE_DOMAIN = "domain:university"
TARGET_DOMAIN = "domain:health"


def _policy(
    policy_id: str,
    domain_id: str,
    **overrides: object,
) -> DomainPermissionPolicy:
    values: dict[str, object] = {
        "policy_id": policy_id,
        "domain_id": domain_id,
        "version": "1.0.0",
        "allowed_sensitivity_levels": (
            PermissionSensitivity.PUBLIC,
            PermissionSensitivity.INTERNAL,
        ),
    }
    values.update(overrides)
    return DomainPermissionPolicy(**values)  # type: ignore[arg-type]


def _gate(*policies: DomainPermissionPolicy) -> DomainPermissionGate:
    registry = DomainPermissionRegistry()
    for policy in policies:
        registry.register(policy)
    return DomainPermissionGate(DomainPermissionResolver(registry), clock=lambda: NOW)


def _cross_domain_request() -> CrossDomainPermissionRequest:
    return CrossDomainPermissionRequest(
        request_id="cross-domain-request-1",
        source_domain=SOURCE_DOMAIN,
        target_domain=TARGET_DOMAIN,
        reason="transfer approved health summary",
        actor_id="actor-1",
        session_id="session-1",
        sensitivity_level=SensitivityLevel.INTERNAL,
        requires_approval=False,
    )


def _remote_allowed_privacy() -> PrivacyMetadata:
    return project_domain_privacy_metadata(
        DomainPrivacyPolicy(
            schema_version="1",
            domain_id=DomainId(slug="university"),
            default_privacy=PrivacyMetadata(
                policy=PrivacyPolicy.REMOTE_ALLOWED,
                sensitivity=SensitivityLevel.INTERNAL,
                allowed_processing_locations=(
                    ProcessingLocation.LOCAL,
                    ProcessingLocation.REMOTE,
                ),
                allow_remote=True,
                allow_cache=True,
                allow_export=False,
            ),
        ),
        processing_location=ProcessingLocation.REMOTE,
    )


def _local_only_privacy() -> PrivacyMetadata:
    return PrivacyMetadata(
        policy=PrivacyPolicy.LOCAL_ONLY,
        sensitivity=SensitivityLevel.SENSITIVE,
        allowed_processing_locations=(ProcessingLocation.LOCAL,),
        allow_remote=False,
        allow_cache=True,
        allow_export=False,
    )


def test_privacy_allow_does_not_authorize_cross_domain_permission_denial() -> None:
    gate = _gate(
        _policy(
            "perm-policy-university-1",
            SOURCE_DOMAIN,
            allow_cross_domain_access=False,
        ),
        _policy(
            "perm-policy-health-1",
            TARGET_DOMAIN,
            allow_inbound_cross_domain_access=True,
            allowed_source_domains=(SOURCE_DOMAIN,),
        ),
    )

    result = gate.evaluate_cross_domain(_cross_domain_request())
    assert result.denied

    effective = resolve_effective_privacy_metadata(_remote_allowed_privacy()).effective
    privacy_decision = evaluate_privacy_operation(
        effective,
        PrivacyOperation.PROCESS_REMOTE,
        PrivacyOperationContext(
            processing_location=ProcessingLocation.REMOTE,
            actor_id="actor-1",
            domain=SOURCE_DOMAIN,
            at=NOW,
        ),
    )
    assert privacy_decision.allowed is True

    assert privacy_decision.allowed and not result.allowed


def test_cross_domain_permission_allow_can_still_be_blocked_by_privacy() -> None:
    gate = _gate(
        _policy(
            "perm-policy-university-1",
            SOURCE_DOMAIN,
            allow_cross_domain_access=True,
            allowed_target_domains=(TARGET_DOMAIN,),
        ),
        _policy(
            "perm-policy-health-1",
            TARGET_DOMAIN,
            allow_inbound_cross_domain_access=True,
            allowed_source_domains=(SOURCE_DOMAIN,),
        ),
    )

    result = gate.evaluate_cross_domain(_cross_domain_request())
    assert result.allowed

    effective = resolve_effective_privacy_metadata(_local_only_privacy()).effective
    privacy_decision = evaluate_privacy_operation(
        effective,
        PrivacyOperation.PROCESS_REMOTE,
        PrivacyOperationContext(
            processing_location=ProcessingLocation.REMOTE,
            actor_id="actor-1",
            domain=TARGET_DOMAIN,
            at=NOW,
        ),
    )

    assert privacy_decision.allowed is False
    assert privacy_decision.status is PrivacyDecisionStatus.DENIED
    assert privacy_decision.reason_code == "remote_blocked_local_only"
    assert result.allowed and not privacy_decision.allowed


def test_permission_denial_blocks_even_when_privacy_is_permissive() -> None:
    gate = _gate(
        _policy(
            "perm-policy-university-1",
            SOURCE_DOMAIN,
            allow_cross_domain_access=True,
            allowed_target_domains=(TARGET_DOMAIN,),
        ),
        _policy(
            "perm-policy-health-1",
            TARGET_DOMAIN,
            allow_inbound_cross_domain_access=False,
        ),
    )

    assert gate.evaluate_cross_domain(_cross_domain_request()).denied


def test_remote_privacy_allow_does_not_authorize_external_model_permission() -> None:
    policy = _policy(
        "perm-policy-university-1", SOURCE_DOMAIN, allow_external_models=False
    )
    request = DomainPermissionRequest(
        request_id="external-model-request-1",
        action=PermissionCapability.MODEL_EXTERNAL,
        domain_id=SOURCE_DOMAIN,
        actor_id="actor-1",
        session_id="session-1",
    )

    evaluation = evaluate_domain_policy(policy, request, now=NOW)
    assert evaluation.effect is PermissionOutcome.DENY

    effective = resolve_effective_privacy_metadata(_remote_allowed_privacy()).effective
    privacy_decision = evaluate_privacy_operation(
        effective,
        PrivacyOperation.TRANSMIT_TO_PROVIDER,
        PrivacyOperationContext(
            processing_location=ProcessingLocation.REMOTE,
            provider_id="provider:alpha",
            at=NOW,
        ),
    )
    assert privacy_decision.allowed is True

    assert privacy_decision.allowed and evaluation.effect is PermissionOutcome.DENY


def test_privacy_policy_has_no_allow_cross_domain_field() -> None:
    policy = DomainPrivacyPolicy(
        schema_version="1",
        domain_id=DomainId(slug="university"),
        default_privacy=_remote_allowed_privacy(),
    )

    assert "allow_cross_domain" not in policy.to_dict()
    assert "allow_cross_domain" not in DomainPrivacyPolicy.__slots__
    assert not hasattr(policy, "allow_cross_domain")

    payload = policy.to_dict()
    payload["allow_cross_domain"] = True
    with pytest.raises(DomainPrivacyPolicySerializationError):
        DomainPrivacyPolicy.from_dict(payload)
