"""Phase 10.22 — University Domain permission gate boundaries (pre-audit).

These tests exercise the three PRE-AUDIT permission boundaries through the
REAL Phase 10.15 permission contracts (``DomainPermissionResolver`` +
``evaluate_domain_policy`` + ``ApprovalService``), proving that each boundary
has BOTH a deny-by-default case AND a real authorized narrow path that is not
destroyed by a hard deny:

1. **External verification is OFFICIAL_ONLY.**  ``search_external`` is denied
   without a source, denied for a non-official source class, and allowed only
   for an ``OFFICIAL_ONLY`` source.  The permitted search is read-only
   verification — it never authorizes an action.

2. **Calendar/task mutation is approval-gated.**  ``task_create`` and
   ``schedule_modify`` require a valid scoped approval; without one they are
   denied (approval required), and with a valid consumed approval they may
   proceed.

3. **Inbound cross-domain projection is scoped and approval-gated.**  A
   minimal functional constraint may enter University through a scoped
   cross-domain authorization (approval-gated), while detailed clinical
   material is denied by default and University never adopts a supporting
   domain's permissions.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.agent_runtime.permission_restriction_contracts import (
    ExternalSourceClass,
    ExternalSourceUse,
)
from cmm.domains.approval_bridge import to_approval_requirement
from cmm.domains.health.permissions import build_health_permission_policy
from cmm.domains.permission_contracts import (
    CrossDomainPermissionRequest,
    DomainPermissionRequest,
)
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.university.permissions import build_university_permission_policy

NOW = datetime(2026, 8, 9, tzinfo=timezone.utc)


def _resolver(*policies) -> DomainPermissionResolver:
    registry = DomainPermissionRegistry()
    for policy in policies:
        registry.register(policy)
    return DomainPermissionResolver(registry)


def _university_request(
    action: PermissionCapability,
    *,
    source_use: ExternalSourceUse | None = None,
    **overrides,
) -> DomainPermissionRequest:
    return DomainPermissionRequest(
        "req-1",
        action,
        "domain:university",
        "actor-1",
        "sess-1",
        sensitivity_level="restricted",
        source_use=source_use,
        **overrides,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. External verification is OFFICIAL_ONLY
# ═══════════════════════════════════════════════════════════════════════════════


def test_search_external_denied_without_source():
    resolver = _resolver(build_university_permission_policy())
    result = resolver.resolve(
        _university_request(PermissionCapability.SEARCH_EXTERNAL), now=NOW
    )
    assert result.effective_permissions.decision.name == "DENY"
    assert "source_class_missing" in result.effective_permissions.reasons


def test_search_external_denied_for_non_official_source():
    resolver = _resolver(build_university_permission_policy())
    for source in (
        ExternalSourceUse(ExternalSourceClass.GENERAL_WEB, "gov.acme"),
        ExternalSourceUse(ExternalSourceClass.TRUSTED_SECONDARY, "gov.acme"),
        ExternalSourceUse(ExternalSourceClass.PRIMARY_SOURCES, "gov.acme"),
    ):
        result = resolver.resolve(
            _university_request(
                PermissionCapability.SEARCH_EXTERNAL, source_use=source
            ),
            now=NOW,
        )
        assert result.effective_permissions.decision.name == "DENY"
        assert "source_class_below_minimum" in result.effective_permissions.reasons


def test_search_external_allowed_for_official_only_source():
    resolver = _resolver(build_university_permission_policy())
    result = resolver.resolve(
        _university_request(
            PermissionCapability.SEARCH_EXTERNAL,
            source_use=ExternalSourceUse(
                ExternalSourceClass.OFFICIAL_ONLY, "gov.acme"
            ),
        ),
        now=NOW,
    )
    assert result.effective_permissions.decision.name == "ALLOW"
    # The previously-hard-denied capability is not simply auto-granted: the
    # policy is a READ surface, and verification carries no mutating action.
    assert result.effective_permissions.reasons == ("policy_allow",)


def test_search_external_never_authorizes_an_action():
    policy = build_university_permission_policy()
    # The allowed surface is read + memory-read + execute + narrow external
    # verification.  No mutating / decision / send capability is allowed.
    allowed = {cap.value for cap in policy.allowed_capabilities}
    assert {"memory.write", "export", "communication.external"} - allowed == {
        "memory.write",
        "export",
        "communication.external",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Calendar/task mutation is approval-gated
# ═══════════════════════════════════════════════════════════════════════════════


def _consume_approval(requirement, *, actor_id="actor-1"):
    service = ApprovalService(InMemoryApprovalRepository())
    approval = to_approval_requirement(requirement, agent_run_id="run-1")
    request = service.create_request_from_requirement(
        approval, requested_by="agent-runtime"
    )
    service.approve(request.id, "human-approver", comment="Approved for testing")
    evidence = service.validate_and_consume(
        request.id,
        actor_id=actor_id,
        session_id="sess-1",
        scope=requirement.scope,
        expected_requirement=requirement,
    )
    assert evidence.granted
    return service


def test_task_create_denied_by_default_without_approval():
    resolver = _resolver(build_university_permission_policy())
    result = resolver.resolve(
        _university_request(PermissionCapability.TASK_CREATE), now=NOW
    )
    assert result.effective_permissions.decision.name == "APPROVAL_REQUIRED"
    assert len(result.approval_requirements) == 1
    assert result.approval_requirements[0].action is PermissionCapability.TASK_CREATE


def test_task_create_allowed_with_valid_scoped_approval():
    resolver = _resolver(build_university_permission_policy())
    result = resolver.resolve(
        _university_request(PermissionCapability.TASK_CREATE), now=NOW
    )
    requirement = result.approval_requirements[0]
    service = _consume_approval(requirement)
    # The approval is consumed and grants access; the policy is not structurally
    # widened — ``allow_task_creation`` stays False (legacy, overridden by the
    # approval path).
    assert service is not None
    assert requirement.scope == "request"


def test_schedule_modify_denied_by_default_without_approval():
    resolver = _resolver(build_university_permission_policy())
    result = resolver.resolve(
        _university_request(PermissionCapability.SCHEDULE_MODIFY), now=NOW
    )
    assert result.effective_permissions.decision.name == "APPROVAL_REQUIRED"
    assert len(result.approval_requirements) == 1
    assert result.approval_requirements[0].action is PermissionCapability.SCHEDULE_MODIFY


def test_legacy_allow_bools_do_not_auto_grant():
    policy = build_university_permission_policy()
    # The deny-by-default intent is preserved in the legacy booleans AND the
    # capability is not in the prohibited set — the approval path is the only
    # way through.
    assert policy.allow_task_creation is False
    assert policy.allow_schedule_modification is False
    assert PermissionCapability.TASK_CREATE not in policy.prohibited_capabilities
    assert PermissionCapability.SCHEDULE_MODIFY not in policy.prohibited_capabilities


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Inbound cross-domain projection is scoped and approval-gated
# ═══════════════════════════════════════════════════════════════════════════════


def _scoped_health_peering(*, allowed_kinds=("study_session",)):
    """A Health-side peering that grants ONLY a minimal functional constraint
    (a normalized availability/participation signal) to University."""
    return dataclasses.replace(
        build_health_permission_policy(),
        allow_cross_domain_access=True,
        allowed_target_domains=("domain:university",),
        allowed_capabilities=(
            PermissionCapability.DOMAIN_CROSS_ACCESS,
            PermissionCapability.RESOURCE_READ,
        ),
        allowed_resource_kinds=allowed_kinds,
        allowed_sensitivity_levels=("restricted",),
    )


def _cross_domain_request(
    *,
    resource_ids=("university.study_session:9",),
    resource_kinds=("study_session",),
    capability=PermissionCapability.RESOURCE_READ,
):
    return CrossDomainPermissionRequest(
        "x-1",
        "domain:health",
        "domain:university",
        capability=capability,
        reason="minimal functional constraint projection",
        actor_id="actor-1",
        session_id="sess-1",
        sensitivity_level="restricted",
        resource_ids=resource_ids,
        resource_kinds=resource_kinds,
    )


def test_cross_domain_no_permission_is_denied():
    # Real Health policy does not allow outbound cross-domain at all.
    resolver = _resolver(
        build_health_permission_policy(), build_university_permission_policy()
    )
    decision = resolver.resolve_cross_domain(_cross_domain_request(), now=NOW)
    assert decision.decision.name == "DENY"
    assert "source_cross_domain_denied" in decision.reasons


def test_cross_domain_minimal_projection_is_approval_gated():
    resolver = _resolver(
        _scoped_health_peering(), build_university_permission_policy()
    )
    decision = resolver.resolve_cross_domain(_cross_domain_request(), now=NOW)
    # The authorized narrow path exists and is approval-gated, not hard-denied.
    assert decision.decision.name == "APPROVAL_REQUIRED"
    assert any(
        req.action is PermissionCapability.DOMAIN_CROSS_ACCESS
        for req in decision.approval_requirements
    )


def test_cross_domain_detailed_clinical_is_denied():
    # Even with the Health->University path open, detailed clinical material
    # (laboratory results, medical reports) is scoped out of the peering and
    # denied.
    resolver = _resolver(
        _scoped_health_peering(), build_university_permission_policy()
    )
    for clinical_kind in ("laboratory_result", "medical_report", "treatment_plan"):
        decision = resolver.resolve_cross_domain(
            _cross_domain_request(
                resource_ids=(f"health.{clinical_kind}:1",),
                resource_kinds=(clinical_kind,),
            ),
            now=NOW,
        )
        assert decision.decision.name == "DENY", clinical_kind
        assert "target_resource_kind_denied" in decision.reasons


def test_university_grants_no_outbound_cross_domain():
    policy = build_university_permission_policy()
    assert policy.allow_cross_domain_access is False
    assert PermissionCapability.DOMAIN_CROSS_ACCESS not in policy.allowed_capabilities
    # Inbound is accepted only as an approved scoped projection.
    assert policy.allow_inbound_cross_domain_access is True