"""Pure resolution of domain permission policies and cross-domain requests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from cmm.agent_runtime.domain_permission_contracts import (
    EffectivePermissionResult,
    PermissionApprovalGrant,
    PermissionApprovalRequirement,
    PermissionCapability,
    PermissionLayer,
    PermissionLayerEvaluation,
    PermissionOutcome,
    intersect_permission_layers,
)
from cmm.domains.permission_contracts import (
    CrossDomainDuration,
    CrossDomainPermissionDecision,
    CrossDomainPermissionRequest,
    DomainPermissionConflict,
    DomainPermissionPolicy,
    DomainPermissionRequest,
)
from cmm.domains.permission_evaluator import evaluate_domain_policy
from cmm.domains.permission_registry import DomainPermissionRegistry


@dataclass(frozen=True, slots=True)
class DomainPermissionResolution:
    domain_policies: tuple[DomainPermissionPolicy, ...]
    effective_permissions: EffectivePermissionResult
    conflicts: tuple[DomainPermissionConflict, ...] = ()
    approval_requirements: tuple[PermissionApprovalRequirement, ...] = ()
    cross_domain_requirements: tuple[PermissionApprovalRequirement, ...] = ()
    trace_entries: tuple[Mapping[str, Any], ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


class DomainPermissionResolver:
    def __init__(self, registry: DomainPermissionRegistry) -> None:
        self._registry = registry

    def resolve(
        self,
        request: DomainPermissionRequest,
        *,
        supporting_domains: tuple[str, ...] = (),
        layer_evaluations: tuple[PermissionLayerEvaluation, ...] = (),
        approval_grants: tuple[PermissionApprovalGrant, ...] = (),
        now: datetime | None = None,
    ) -> DomainPermissionResolution:
        domains = (request.domain_id, *tuple(sorted(set(supporting_domains))))
        policies = tuple(policy for domain in domains if (policy := self._registry.active_for_domain(domain, now=now)) is not None)
        evaluations = list(layer_evaluations)
        evaluations.extend(
            evaluate_domain_policy(
                policy,
                request,
                domain_role="primary" if policy.domain_id == request.domain_id else "supporting",
                now=now,
            )
            for policy in policies
        )
        if request.autonomy_level is not None:
            limits = tuple(
                policy.autonomy_limits.maximum_autonomy_level
                for policy in policies
                if policy.autonomy_limits.maximum_autonomy_level is not None
            )
            if limits and request.autonomy_level > min(limits):
                evaluations.append(
                    PermissionLayerEvaluation(
                        PermissionLayer.AUTONOMY,
                        PermissionOutcome.DENY,
                        source_id=f"autonomy:{request.domain_id}",
                        reasons=("autonomy_limit_exceeded",),
                        constraints={"maximum_autonomy_level": min(limits)},
                    )
                )
        effective = intersect_permission_layers(tuple(evaluations), request_id=request.request_id, action=request.action.value)
        allowing = tuple(item.source_id for item in effective.layer_evaluations if item.effect is PermissionOutcome.ALLOW)
        denying = tuple(item.source_id for item in effective.layer_evaluations if item.effect is PermissionOutcome.DENY)
        approving = tuple(item.source_id for item in effective.layer_evaluations if item.effect is PermissionOutcome.APPROVAL_REQUIRED)
        conflicts_list: list[DomainPermissionConflict] = []
        if allowing and denying:
            conflicts_list.append(DomainPermissionConflict(request.action, allowing, denying, approving, PermissionOutcome.DENY, "allow_deny_conflict"))
        if approving and denying:
            conflicts_list.append(DomainPermissionConflict(request.action, allowing, denying, approving, PermissionOutcome.DENY, "approval_deny_conflict"))
        return DomainPermissionResolution(
            domain_policies=policies,
            effective_permissions=effective,
            conflicts=tuple(conflicts_list),
            approval_requirements=effective.approval_requirements,
            trace_entries=tuple({"source": item.source.value, "effect": item.effect.value, "matched_rules": list(item.matched_rules), "reasons": list(item.reasons)} for item in effective.layer_evaluations),
            metadata={
                "primary_domain": request.domain_id,
                "legacy_approval_grants_ignored": len(approval_grants),
            },
        )

    def resolve_cross_domain(
        self, request: CrossDomainPermissionRequest, *, now: datetime | None = None
    ) -> CrossDomainPermissionDecision:
        source_policies = self._registry.for_domain(request.source_domain)
        target_policies = self._registry.for_domain(request.target_domain)
        if now is None and any(
            policy.enabled and policy.expires_at is not None
            for policy in (*source_policies, *target_policies)
        ):
            raise ValueError("now must be injected for temporal cross-domain policies")
        source = self._registry.active_for_domain(request.source_domain, now=now)
        target = self._registry.active_for_domain(request.target_domain, now=now)
        reasons: list[str] = []
        if source is None or target is None:
            return CrossDomainPermissionDecision(request.request_id, PermissionOutcome.DENY, reasons=("unknown_domain_policy",))
        if request.expires_at is not None:
            if now is None:
                raise ValueError("now must be injected for expiring cross-domain requests")
            if now.tzinfo is None:
                raise ValueError("now must be timezone-aware")
            if now >= request.expires_at:
                return CrossDomainPermissionDecision(request.request_id, PermissionOutcome.DENY, reasons=("cross_domain_request_expired",))
        source_request = DomainPermissionRequest(
            request.request_id,
            PermissionCapability.DOMAIN_CROSS_ACCESS,
            request.source_domain,
            request.actor_id,
            request.session_id,
            sensitivity_level=request.sensitivity_level,
            source_domain=request.source_domain,
            target_domain=request.target_domain,
        )
        source_evaluation = evaluate_domain_policy(source, source_request, now=now)
        if source_evaluation.effect is PermissionOutcome.DENY:
            reasons.extend(source_evaluation.reasons)
            reasons.append("source_cross_domain_denied")
        if request.capability is not PermissionCapability.DOMAIN_CROSS_ACCESS:
            capability_context: dict[str, str] = {}
            if request.capability is PermissionCapability.RESOURCE_READ:
                if request.resource_ids:
                    capability_context["resource_id"] = request.resource_ids[0]
                if request.resource_kinds:
                    capability_context["resource_kind"] = request.resource_kinds[0]
            elif request.capability is PermissionCapability.OPERATION_EXECUTE and request.requested_operations:
                capability_context["operation_id"] = request.requested_operations[0]
            elif request.capability is PermissionCapability.WORKFLOW_EXECUTE and request.requested_workflows:
                capability_context["workflow_id"] = request.requested_workflows[0]
            capability_request = DomainPermissionRequest(
                f"{request.request_id}:capability",
                request.capability,
                request.source_domain,
                request.actor_id,
                request.session_id,
                sensitivity_level=request.sensitivity_level,
                source_domain=request.source_domain,
                target_domain=request.target_domain,
                **capability_context,
            )
            capability_evaluation = evaluate_domain_policy(source, capability_request, now=now)
            if capability_evaluation.effect is PermissionOutcome.DENY:
                reasons.append("source_capability_denied")
        else:
            capability_evaluation = source_evaluation
        target_request = DomainPermissionRequest(
            request.request_id,
            PermissionCapability.DOMAIN_CROSS_ACCESS,
            request.target_domain,
            request.actor_id,
            request.session_id,
            sensitivity_level=request.sensitivity_level,
            source_domain=request.source_domain,
            target_domain=request.target_domain,
        )
        target_evaluation = evaluate_domain_policy(
            target,
            target_request,
            domain_role="target",
            cross_domain_direction="inbound",
            now=now,
        )
        if target_evaluation.effect is PermissionOutcome.DENY:
            reasons.extend(target_evaluation.reasons)
            reasons.append("target_cross_domain_denied")
        if request.capability is not PermissionCapability.DOMAIN_CROSS_ACCESS:
            target_capability_evaluation = evaluate_domain_policy(
                target,
                DomainPermissionRequest(
                    f"{request.request_id}:target-capability",
                    request.capability,
                    request.target_domain,
                    request.actor_id,
                    request.session_id,
                    sensitivity_level=request.sensitivity_level,
                    source_domain=request.source_domain,
                    target_domain=request.target_domain,
                    **capability_context,
                ),
                domain_role="target-capability",
                now=now,
            )
            if target_capability_evaluation.effect is PermissionOutcome.DENY:
                reasons.append("target_capability_denied")
        else:
            target_capability_evaluation = target_evaluation
        if not target.allow_inbound_cross_domain_access:
            reasons.append("target_cross_domain_denied")
        if PermissionCapability.DOMAIN_CROSS_ACCESS in target.prohibited_capabilities:
            reasons.append("target_capability_prohibited")
        if request.capability in target.prohibited_capabilities:
            reasons.append("target_capability_prohibited")
        elif (
            request.capability is not PermissionCapability.DOMAIN_CROSS_ACCESS
            and target.allowed_capabilities
            and request.capability not in target.allowed_capabilities
        ):
            reasons.append("target_capability_not_allowed")
        if request.source_domain in target.prohibited_source_domains or (target.allowed_source_domains is not None and request.source_domain not in target.allowed_source_domains):
            reasons.append("source_not_allowed_by_target")
        if request.sensitivity_level is None:
            reasons.append("unknown_sensitivity")
        elif request.sensitivity_level in target.prohibited_sensitivity_levels or (target.allowed_sensitivity_levels is not None and request.sensitivity_level not in target.allowed_sensitivity_levels):
            reasons.append("target_sensitivity_denied")
        requested_kinds = set(request.resource_kinds)
        requested_resources = set(request.resource_ids)
        for role, policy in (("source", source), ("target", target)):
            if requested_resources & set(policy.prohibited_resources):
                reasons.append(f"{role}_resource_prohibited")
            if (
                requested_resources
                and policy.allowed_resources is not None
                and not requested_resources.issubset(policy.allowed_resources)
            ):
                reasons.append(f"{role}_resource_denied")
            if request.resource_ids and not request.resource_kinds and (
                policy.allowed_resource_kinds is not None
                or policy.prohibited_resource_kinds
            ):
                reasons.append(f"{role}_resource_scope_unverifiable")
            if requested_kinds & set(policy.prohibited_resource_kinds):
                reasons.append(f"{role}_resource_kind_prohibited")
            if (
                requested_kinds
                and policy.allowed_resource_kinds is not None
                and not requested_kinds.issubset(policy.allowed_resource_kinds)
            ):
                reasons.append(f"{role}_resource_kind_denied")
            requested_operations = set(request.requested_operations)
            if requested_operations & set(policy.prohibited_operations):
                reasons.append(f"{role}_operation_prohibited")
            if (
                requested_operations
                and policy.allowed_operations is not None
                and not requested_operations.issubset(policy.allowed_operations)
            ):
                reasons.append(f"{role}_operation_denied")
            requested_workflows = set(request.requested_workflows)
            if requested_workflows & set(policy.prohibited_workflows):
                reasons.append(f"{role}_workflow_prohibited")
            if (
                requested_workflows
                and policy.allowed_workflows is not None
                and not requested_workflows.issubset(policy.allowed_workflows)
            ):
                reasons.append(f"{role}_workflow_denied")
        constraints = request.constraints
        supported_constraint_keys = {
            "allowed_resources", "prohibited_resources",
            "allowed_resource_kinds", "prohibited_resource_kinds",
            "allowed_operations", "prohibited_operations",
            "allowed_workflows", "prohibited_workflows",
            "allowed_target_domains", "prohibited_target_domains",
            "allowed_sensitivity_levels", "prohibited_sensitivity_levels",
            "scopes", "maximum_operations", "maximum_workflows", "expires_at",
        }
        if set(constraints) - supported_constraint_keys:
            reasons.append("unsupported_cross_domain_constraint")
        constrained_sets = (
            ("resources", request.resource_ids),
            ("resource_kinds", request.resource_kinds),
            ("operations", request.requested_operations),
            ("workflows", request.requested_workflows),
        )
        for suffix, requested in constrained_sets:
            requested_set = set(requested)
            allowed_values = constraints.get(f"allowed_{suffix}")
            prohibited_values = constraints.get(f"prohibited_{suffix}")
            if allowed_values is not None and not requested_set.issubset(allowed_values):
                reasons.append(f"{suffix}_not_allowed_by_constraints")
            if prohibited_values is not None and requested_set & set(prohibited_values):
                reasons.append(f"{suffix}_prohibited_by_constraints")
        allowed_sensitivity = constraints.get("allowed_sensitivity_levels")
        if (
            allowed_sensitivity is not None
            and request.sensitivity_level is not None
            and request.sensitivity_level.value not in allowed_sensitivity
        ):
            reasons.append("sensitivity_not_allowed_by_constraints")
        prohibited_sensitivity = constraints.get("prohibited_sensitivity_levels")
        if (
            prohibited_sensitivity is not None
            and request.sensitivity_level is not None
            and request.sensitivity_level.value in prohibited_sensitivity
        ):
            reasons.append("sensitivity_prohibited_by_constraints")
        allowed_targets = constraints.get("allowed_target_domains")
        prohibited_targets = constraints.get("prohibited_target_domains")
        if allowed_targets is not None and request.target_domain not in allowed_targets:
            reasons.append("target_not_allowed_by_constraints")
        if prohibited_targets is not None and request.target_domain in prohibited_targets:
            reasons.append("target_prohibited_by_constraints")
        maximum_operations = constraints.get("maximum_operations")
        if maximum_operations is not None and len(request.requested_operations) > maximum_operations:
            reasons.append("maximum_operations_exceeded")
        maximum_workflows = constraints.get("maximum_workflows")
        if maximum_workflows is not None and len(request.requested_workflows) > maximum_workflows:
            reasons.append("maximum_workflows_exceeded")
        scopes = constraints.get("scopes")
        if scopes is not None and request.duration.value not in scopes:
            reasons.append("duration_not_allowed_by_constraints")
        constraint_expiry = constraints.get("expires_at")
        if constraint_expiry is not None:
            if now is None:
                raise ValueError("now must be injected for temporal cross-domain constraints")
            if now.tzinfo is None:
                raise ValueError("now must be timezone-aware")
            if now >= datetime.fromisoformat(constraint_expiry):
                reasons.append("cross_domain_constraints_expired")
        if reasons:
            return CrossDomainPermissionDecision(
                request.request_id,
                PermissionOutcome.DENY,
                constraints=request.constraints,
                reasons=tuple(sorted(set(reasons))),
            )
        requirements = tuple({
            item.requirement_id: item
            for item in (
                *source_evaluation.approval_requirements,
                *capability_evaluation.approval_requirements,
                *target_evaluation.approval_requirements,
                *target_capability_evaluation.approval_requirements,
            )
        }.values())
        if request.requires_approval:
            requirement = PermissionApprovalRequirement(
                requirement_id=f"cross-domain:{request.request_id}",
                action=PermissionCapability.DOMAIN_CROSS_ACCESS,
                actor_id=request.actor_id,
                session_id=request.session_id,
                domain_id=request.source_domain,
                source_domain=request.source_domain,
                target_domain=request.target_domain,
                resource_id=request.resource_ids[0] if len(request.resource_ids) == 1 else None,
                resource_kind=request.resource_kinds[0] if len(request.resource_kinds) == 1 else None,
                operation_id=request.requested_operations[0]
                if len(request.requested_operations) == 1
                else None,
                workflow_id=request.requested_workflows[0]
                if len(request.requested_workflows) == 1
                else None,
                purpose=request.reason,
                sensitivity=request.sensitivity_level,
                fingerprint=f"{request.request_id}:{request.source_domain}:{request.target_domain}:{request.actor_id}:{request.session_id}",
                expires_at=request.expires_at.isoformat() if request.expires_at else None,
                scope=request.duration.value,
                one_time=request.duration in {
                    CrossDomainDuration.SINGLE_USE,
                    CrossDomainDuration.REQUEST,
                },
                reusable=request.duration in {
                    CrossDomainDuration.WORKFLOW_RUN,
                    CrossDomainDuration.SESSION,
                },
                constraints=request.constraints,
                reason_code="cross_domain_approval_required",
                risk="high",
            )
            requirements = tuple({item.requirement_id: item for item in (*requirements, requirement)}.values())
        if requirements:
            return CrossDomainPermissionDecision(
                request.request_id,
                PermissionOutcome.APPROVAL_REQUIRED,
                constraints=request.constraints,
                approval_requirements=requirements,
                reasons=("cross_domain_approval_required",),
            )
        return CrossDomainPermissionDecision(
            request.request_id,
            PermissionOutcome.ALLOW,
            granted_resources=request.resource_ids,
            granted_operations=request.requested_operations,
            granted_workflows=request.requested_workflows,
            constraints=request.constraints,
            reasons=("cross_domain_allowed",),
        )


__all__ = ["DomainPermissionResolution", "DomainPermissionResolver"]
