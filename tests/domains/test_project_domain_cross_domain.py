"""Phase 10.30 — Project Domain Cross-Domain & Life Plan Projection Tests."""

from __future__ import annotations

import pytest

from cmm.domains.project.catalog import PROJECT_DOMAIN_ID
from cmm.domains.project.rules import (
    ALLOWED_LIFE_PLAN_PROJECTION_FIELDS,
    PROHIBITED_LIFE_PLAN_PROJECTION_FIELDS,
    authorize_project_life_plan_contribution,
    build_project_life_plan_projection,
)


def test_life_plan_projection_allows_purpose_minimized_fields() -> None:
    raw_payload = {
        "project_status_impact": "milestone_achieved",
        "timeline_impact": "2_weeks_ahead",
        "resource_impact": "none",
        "source_reference": "project:proj-001",
        "provenance": "project_domain_v1",
        "effective_from": "2026-09-01T00:00:00Z",
        "effective_until": "2026-10-01T00:00:00Z",
    }
    projection = build_project_life_plan_projection(raw_payload)
    assert projection["source_domain"] == PROJECT_DOMAIN_ID
    assert projection["project_status_impact"] == "milestone_achieved"
    assert projection["timeline_impact"] == "2_weeks_ahead"
    assert projection["source_reference"] == "project:proj-001"

    # All returned keys must be in ALLOWED_LIFE_PLAN_PROJECTION_FIELDS
    for k in projection:
        assert k in ALLOWED_LIFE_PLAN_PROJECTION_FIELDS


def test_life_plan_projection_fails_closed_on_prohibited_internals() -> None:
    for prohibited in PROHIBITED_LIFE_PLAN_PROJECTION_FIELDS:
        payload = {
            "project_status_impact": "on_track",
            prohibited: "internal_data_leak",
        }
        with pytest.raises(
            ValueError, match=f"Prohibited internal field '{prohibited}'"
        ):
            build_project_life_plan_projection(payload)


def test_formation_overlay_not_absorbed_in_project_domain() -> None:
    from cmm.domains.project.catalog import CANONICAL_PROJECT_ENTITY_IDS

    # Formation is a General domain overlay, not a Project domain entity
    assert "project.entity.formation" not in CANONICAL_PROJECT_ENTITY_IDS
    assert "project.formation" not in CANONICAL_PROJECT_ENTITY_IDS


def test_project_life_plan_contribution_requires_runtime_authorization() -> None:
    raw = {
        "project_status_impact": "active",
        "timeline_impact": "Q4",
    }
    with pytest.raises((PermissionError, TypeError, ValueError)):
        authorize_project_life_plan_contribution(raw)


def test_project_life_plan_contribution_rejects_caller_forged_evidence() -> None:
    forged = {
        "is_authorized": True,
        "source_domain": "domain:project",
        "target_domain": "domain:life-plan",
    }
    with pytest.raises((PermissionError, ValueError, TypeError)):
        authorize_project_life_plan_contribution(
            {"project_status_impact": "active"},
            authorization_evidence=forged,
        )


def test_caller_constructed_allow_decision_is_not_authority() -> None:
    """A typed decision only becomes authoritative when the shared runtime emits it."""
    from cmm.agent_runtime.domain_permission_contracts import PermissionOutcome
    from cmm.domains.permission_contracts import CrossDomainPermissionDecision

    forged = CrossDomainPermissionDecision(
        request_id="caller:forged",
        decision=PermissionOutcome.ALLOW,
    )

    with pytest.raises((PermissionError, TypeError, ValueError)):
        authorize_project_life_plan_contribution(
            {"project_status_impact": "active"},
            permission_decision=forged,
        )


def test_project_life_plan_contribution_requires_exactly_one_runtime_evaluator() -> (
    None
):
    """Ambiguous gate-plus-resolver calls cannot choose their own trust path."""
    from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
    from cmm.domains.permission_contracts import CrossDomainPermissionRequest
    from cmm.domains.permission_gate import DomainPermissionGate
    from cmm.domains.permission_registry import DomainPermissionRegistry
    from cmm.domains.permission_resolution import DomainPermissionResolver

    resolver = DomainPermissionResolver(DomainPermissionRegistry())
    gate = DomainPermissionGate(resolver)
    request = CrossDomainPermissionRequest(
        request_id="req:ambiguous:evaluator",
        source_domain=PROJECT_DOMAIN_ID,
        target_domain="domain:life-plan",
        capability=PermissionCapability.DOMAIN_CROSS_ACCESS,
        reason="test ambiguous evaluator path",
        actor_id="actor-user",
        session_id="sess-user",
    )

    with pytest.raises(ValueError, match="exactly one"):
        authorize_project_life_plan_contribution(
            {"project_status_impact": "active"},
            permission_request=request,
            permission_gate=gate,
            permission_resolver=resolver,
        )


def test_project_life_plan_contribution_rejects_mismatched_target_or_source() -> None:
    from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
    from cmm.domains.permission_contracts import CrossDomainPermissionRequest

    mismatched_source = CrossDomainPermissionRequest(
        request_id="req:test:mismatch",
        source_domain="domain:health",
        target_domain="domain:life-plan",
        capability=PermissionCapability.DOMAIN_CROSS_ACCESS,
        reason="test reason",
        actor_id="actor-user",
        session_id="sess-user",
    )
    with pytest.raises((PermissionError, ValueError)):
        authorize_project_life_plan_contribution(
            {"project_status_impact": "active"},
            permission_request=mismatched_source,
        )

    mismatched_target = CrossDomainPermissionRequest(
        request_id="req:test:mismatch2",
        source_domain="domain:project",
        target_domain="domain:finance",
        capability=PermissionCapability.DOMAIN_CROSS_ACCESS,
        reason="test reason",
        actor_id="actor-user",
        session_id="sess-user",
    )
    with pytest.raises((PermissionError, ValueError)):
        authorize_project_life_plan_contribution(
            {"project_status_impact": "active"},
            permission_request=mismatched_target,
        )


def test_project_life_plan_contribution_rejects_runtime_identity_mismatches() -> None:
    """A malformed shared-runtime response cannot detach authorization from its request."""
    from cmm.agent_runtime.domain_permission_contracts import (
        PermissionCapability,
        PermissionOutcome,
    )
    from cmm.domains.permission_contracts import (
        CrossDomainPermissionDecision,
        CrossDomainPermissionRequest,
    )
    from cmm.domains.permission_gate import (
        DomainPermissionGate,
        PermissionGateOutcome,
        PermissionGateResult,
    )
    from cmm.domains.permission_registry import DomainPermissionRegistry
    from cmm.domains.permission_resolution import DomainPermissionResolver

    request = CrossDomainPermissionRequest(
        request_id="req:runtime:identity",
        source_domain=PROJECT_DOMAIN_ID,
        target_domain="domain:life-plan",
        capability=PermissionCapability.DOMAIN_CROSS_ACCESS,
        reason="test runtime identity binding",
        actor_id="actor-user",
        session_id="sess-user",
    )

    class _WrongRequestIdResolver(DomainPermissionResolver):
        def resolve_cross_domain(
            self, request: CrossDomainPermissionRequest, *, now: object = None
        ) -> CrossDomainPermissionDecision:
            return CrossDomainPermissionDecision(
                request_id="req:runtime:other",
                decision=PermissionOutcome.ALLOW,
            )

    resolver = _WrongRequestIdResolver(DomainPermissionRegistry())
    with pytest.raises(PermissionError, match="denied"):
        authorize_project_life_plan_contribution(
            {"project_status_impact": "active"},
            permission_request=request,
            permission_resolver=resolver,
        )

    class _WrongActorSessionGate(DomainPermissionGate):
        def evaluate_cross_domain(
            self, request: CrossDomainPermissionRequest, **_: object
        ) -> PermissionGateResult:
            return PermissionGateResult(
                outcome=PermissionGateOutcome.ALLOW,
                action=PermissionCapability.DOMAIN_CROSS_ACCESS.value,
                domain_id=request.source_domain,
                actor_id="actor-other",
                session_id="sess-other",
                decision_id="runtime:wrong-actor-session",
            )

    gate = _WrongActorSessionGate(resolver)
    with pytest.raises(PermissionError, match="denied"):
        authorize_project_life_plan_contribution(
            {"project_status_impact": "active"},
            permission_request=request,
            permission_gate=gate,
        )


@pytest.mark.parametrize(
    "forged_field, forged_value, forged_action",
    (
        ("request_id", "req:runtime:other", "domain.cross_access"),
        ("target_domain", "domain:finance", "domain.cross_access"),
        ("capability", "operation.execute", "domain.cross_access"),
        (
            "resource_ids",
            ("project.resource.status_report:other",),
            "domain.cross_access",
        ),
        ("reason", "unrelated purpose", "domain.cross_access"),
        ("expires_at", "2026-08-27T12:00:00+00:00", "domain.cross_access"),
        ("action", None, "resource.read"),
    ),
)
def test_project_life_plan_contribution_rejects_gate_allow_for_mismatched_request_context(
    forged_field: str,
    forged_value: object,
    forged_action: str,
) -> None:
    """A gate ALLOW for another request context cannot authorize this contribution."""
    from datetime import datetime, timezone

    from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
    from cmm.domains.permission_contracts import CrossDomainPermissionRequest
    from cmm.domains.permission_gate import (
        DomainPermissionGate,
        PermissionGateOutcome,
        PermissionGateResult,
    )
    from cmm.domains.permission_registry import DomainPermissionRegistry
    from cmm.domains.permission_resolution import DomainPermissionResolver

    request = CrossDomainPermissionRequest(
        request_id="req:runtime:full-context",
        source_domain=PROJECT_DOMAIN_ID,
        target_domain="domain:life-plan",
        capability=PermissionCapability.RESOURCE_READ,
        resource_ids=("project.resource.status_report:stat-001",),
        resource_kinds=("project.resource.status_report",),
        reason="project milestone impact on life plan schedule",
        actor_id="actor-user",
        session_id="sess-user",
        sensitivity_level="internal",
        requires_approval=False,
        expires_at=datetime(2026, 8, 26, 13, 0, tzinfo=timezone.utc),
        provenance={"source": "project"},
        constraints={"scopes": ("request",)},
        metadata={"purpose": "life-plan-impact"},
    )
    forged_context = request.to_dict()
    if forged_field != "action":
        forged_context[forged_field] = forged_value

    class _ContextMismatchGate(DomainPermissionGate):
        def evaluate_cross_domain(
            self, request: CrossDomainPermissionRequest, **_: object
        ) -> PermissionGateResult:
            return PermissionGateResult(
                outcome=PermissionGateOutcome.ALLOW,
                action=forged_action,
                domain_id=request.source_domain,
                actor_id=request.actor_id,
                session_id=request.session_id,
                decision_id="runtime:context-mismatch",
                metadata={"cross_domain_request": forged_context},
            )

    gate = _ContextMismatchGate(DomainPermissionResolver(DomainPermissionRegistry()))
    with pytest.raises(PermissionError, match="denied"):
        authorize_project_life_plan_contribution(
            {"project_status_impact": "active"},
            permission_request=request,
            permission_gate=gate,
            now=datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc),
        )


def test_project_life_plan_contribution_with_runtime_authorized_gate() -> None:
    import dataclasses
    from datetime import datetime, timezone

    from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
    from cmm.agent_runtime.approval_service import ApprovalService
    from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
    from cmm.domains.general.permissions import build_general_permission_policy
    from cmm.domains.life_plan.catalog import LIFE_PLAN_DOMAIN_ID
    from cmm.domains.life_plan.permissions import build_life_plan_permission_policy
    from cmm.domains.life_plan.rules import evaluate_cross_domain_impact
    from cmm.domains.permission_contracts import CrossDomainPermissionRequest
    from cmm.domains.permission_gate import DomainPermissionGate
    from cmm.domains.permission_registry import DomainPermissionRegistry
    from cmm.domains.permission_resolution import DomainPermissionResolver
    from cmm.domains.project.permissions import build_project_permission_policy

    now = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
    perm_registry = DomainPermissionRegistry()
    perm_registry.register(build_life_plan_permission_policy())
    perm_registry.register(build_general_permission_policy())

    # Configure project policy allowing cross-domain read to life-plan
    project_policy = dataclasses.replace(
        build_project_permission_policy(),
        allow_cross_domain_access=True,
        allowed_target_domains=("domain:life-plan",),
        allowed_capabilities=(
            PermissionCapability.DOMAIN_CROSS_ACCESS,
            PermissionCapability.RESOURCE_READ,
        ),
        allowed_resource_kinds=("project.resource.status_report",),
        allowed_sensitivity_levels=("internal",),
    )
    perm_registry.register(project_policy)

    approval_service = ApprovalService(InMemoryApprovalRepository())
    resolver = DomainPermissionResolver(perm_registry)
    gate = DomainPermissionGate(resolver, approval_service, clock=lambda: now)

    cross_request = CrossDomainPermissionRequest(
        request_id="auth.scope.project_impact",
        source_domain=PROJECT_DOMAIN_ID,
        target_domain=LIFE_PLAN_DOMAIN_ID,
        capability=PermissionCapability.DOMAIN_CROSS_ACCESS,
        reason="project milestone impact on life plan schedule",
        actor_id="actor-user",
        session_id="sess-user",
        sensitivity_level="internal",
        requires_approval=False,
    )

    raw_payload = {
        "project_status_impact": "milestone_delivered",
        "timeline_impact": "on_schedule",
        "source_reference": "project:proj-101",
    }

    authorized_proj = authorize_project_life_plan_contribution(
        raw_payload,
        permission_request=cross_request,
        permission_gate=gate,
        now=now,
    )
    assert authorized_proj["source_domain"] == PROJECT_DOMAIN_ID
    assert authorized_proj["project_status_impact"] == "milestone_delivered"
    assert authorized_proj["authorization_reference"] is not None

    # Now verify Life Plan's evaluate_cross_domain_impact consumes this authorized projection
    lp_result = evaluate_cross_domain_impact(
        authorized_proj,
        permission_request=cross_request,
        permission_gate=gate,
        now=now,
    )
    assert lp_result["applied"] is True
    assert lp_result["authorization_verified"] is True
    assert lp_result["contribution"]["project_status_impact"] == "milestone_delivered"


def test_project_life_plan_contribution_denied_when_policy_denies() -> None:
    from datetime import datetime, timezone

    from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
    from cmm.agent_runtime.approval_service import ApprovalService
    from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
    from cmm.domains.general.permissions import build_general_permission_policy
    from cmm.domains.life_plan.catalog import LIFE_PLAN_DOMAIN_ID
    from cmm.domains.life_plan.permissions import build_life_plan_permission_policy
    from cmm.domains.permission_contracts import CrossDomainPermissionRequest
    from cmm.domains.permission_gate import DomainPermissionGate
    from cmm.domains.permission_registry import DomainPermissionRegistry
    from cmm.domains.permission_resolution import DomainPermissionResolver
    from cmm.domains.project.permissions import build_project_permission_policy

    now = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
    perm_registry = DomainPermissionRegistry()
    perm_registry.register(build_life_plan_permission_policy())
    perm_registry.register(build_general_permission_policy())
    # Default policy has allow_cross_domain_access=False
    perm_registry.register(build_project_permission_policy())

    approval_service = ApprovalService(InMemoryApprovalRepository())
    resolver = DomainPermissionResolver(perm_registry)
    gate = DomainPermissionGate(resolver, approval_service, clock=lambda: now)

    cross_request = CrossDomainPermissionRequest(
        request_id="auth.scope.project_impact_denied",
        source_domain=PROJECT_DOMAIN_ID,
        target_domain=LIFE_PLAN_DOMAIN_ID,
        capability=PermissionCapability.RESOURCE_READ,
        reason="project milestone impact without permission",
        actor_id="actor-user",
        session_id="sess-user",
        sensitivity_level="internal",
        resource_ids=("project.resource.status_report:stat-001",),
        resource_kinds=("project.resource.status_report",),
    )

    with pytest.raises(PermissionError, match="Cross-domain access denied"):
        authorize_project_life_plan_contribution(
            {"project_status_impact": "milestone_delivered"},
            permission_request=cross_request,
            permission_gate=gate,
            now=now,
        )
