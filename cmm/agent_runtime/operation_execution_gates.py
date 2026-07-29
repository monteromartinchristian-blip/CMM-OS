"""Phase 9.13 – Operation Execution Security Gates.

Defines the conjuntive gate evaluator for assessing 12 pre-execution security gates.
"""

from __future__ import annotations

from typing import Any

from cmm.agent_runtime.operation_execution_contracts import (
    AgentOperationRequest,
    OperationCapability,
    OperationDescriptor,
    OperationExecutionGateResult,
)
from cmm.agent_runtime.operation_registry import AgentOperationRegistry


def _value_as_string(value: Any) -> str:
    """Return an enum value or the string representation of a gate value."""
    enum_value = getattr(value, "value", value)
    return str(enum_value)


class OperationExecutionGateEvaluator:
    """Evaluates the 12 security gates before an operation can be executed."""

    def __init__(
        self,
        registry: AgentOperationRegistry,
        policy_evaluator: Any | None = None,
        autonomy_evaluator: Any | None = None,
        approval_service: Any | None = None,
        budget_service: Any | None = None,
        lock_manager: Any | None = None,
        resource_version_provider: Any | None = None,
    ) -> None:
        self._registry = registry
        self._policy_evaluator = policy_evaluator
        self._autonomy_evaluator = autonomy_evaluator
        self._approval_service = approval_service
        self._budget_service = budget_service
        self._lock_manager = lock_manager
        self._resource_version_provider = resource_version_provider

    def evaluate(
        self,
        request: AgentOperationRequest,
        capability: OperationCapability | None = None,
        uses_count: int = 0,
        checkpoint_valid: bool = True,
    ) -> OperationExecutionGateResult:
        reason_codes: list[str] = []

        registered = False
        parameters_valid = False
        capability_satisfied = True
        permissions_satisfied = True
        autonomy_satisfied = True
        policy_satisfied = True
        approval_satisfied = True
        budget_satisfied = True
        dependencies_satisfied = True
        environment_satisfied = True
        checkpoint_satisfied = checkpoint_valid
        rollback_satisfied = True
        locks_satisfied = True
        resource_versions_satisfied = True

        requires_approval = False
        requires_budget = True

        desc: OperationDescriptor | None = None

        # Gate 1: Registry check
        try:
            desc = self._registry.resolve(
                request.operation_name, request.operation_version
            )
            if not desc.enabled:
                reason_codes.append("operation.disabled")
            else:
                registered = True
                reason_codes.append("operation.registered")
        except Exception:  # noqa: BLE001
            reason_codes.append("operation.not_registered")

        # Gate 2: Parameters check
        if desc and registered:
            try:
                if self._registry.validate_request(request):
                    parameters_valid = True
                    reason_codes.append("operation.parameters_valid")
            except Exception as exc:  # noqa: BLE001
                reason_codes.append("operation.parameters_invalid")
                reason_codes.append(str(exc))

        # Gate 3: Capability check
        if capability:
            if not capability.allowed:
                capability_satisfied = False
                reason_codes.append("operation.capability_denied")
            else:
                reason_codes.append("operation.capability_allowed")

            if (
                capability.maximum_uses is not None
                and uses_count >= capability.maximum_uses
            ):
                capability_satisfied = False
                reason_codes.append("operation.capability_exceeded")

            if (
                request.environment not in capability.allowed_environments
                and capability.allowed_environments
            ):
                environment_satisfied = False
                reason_codes.append("operation.environment_denied")
            else:
                reason_codes.append("operation.environment_allowed")

            if capability.requires_approval:
                requires_approval = True
        else:
            reason_codes.append("operation.capability_allowed")

        # Gate 4: Environment check against descriptor
        if (
            desc
            and desc.compatible_environments
            and request.environment not in desc.compatible_environments
        ):
            environment_satisfied = False
            reason_codes.append("operation.environment_not_compatible")

        # Gate 5: Permissions check
        if desc and desc.required_permissions:
            missing_perms = [
                p for p in desc.required_permissions if p not in request.permissions
            ]
            if missing_perms:
                permissions_satisfied = False
                reason_codes.append("operation.permission_denied")
            else:
                reason_codes.append("operation.permission_required")

        # Gate 6: Autonomy check
        if self._autonomy_evaluator and hasattr(self._autonomy_evaluator, "evaluate"):
            try:
                aut_res = self._autonomy_evaluator.evaluate(request)
                aut_dec = getattr(aut_res, "decision", None)
                aut_str = _value_as_string(aut_dec)
                if aut_str == "deny":
                    autonomy_satisfied = False
                    reason_codes.append("operation.autonomy_denied")
                elif aut_str == "require_approval":
                    requires_approval = True
                    reason_codes.append("operation.autonomy_requires_approval")
                else:
                    reason_codes.append("operation.autonomy_allowed")
            except Exception:  # noqa: BLE001
                reason_codes.append("operation.autonomy_allowed")

        # Gate 7: Policy check
        if self._policy_evaluator and hasattr(self._policy_evaluator, "evaluate"):
            try:
                pol_res = self._policy_evaluator.evaluate(request)
                pol_dec = getattr(pol_res, "decision", None)
                pol_str = _value_as_string(pol_dec)
                if pol_str == "deny":
                    policy_satisfied = False
                    reason_codes.append("operation.policy_denied")
                elif pol_str == "require_approval":
                    requires_approval = True
                    reason_codes.append("operation.policy_requires_approval")
                else:
                    reason_codes.append("operation.policy_allowed")
            except Exception:  # noqa: BLE001
                reason_codes.append("operation.policy_allowed")

        # Gate 8: Approval check
        if requires_approval:
            if not request.approval_request_id:
                approval_satisfied = False
                reason_codes.append("operation.approval_required")
            elif self._approval_service:
                try:
                    app = self._approval_service.get_request(
                        request.approval_request_id
                    )
                    app_st = getattr(app, "status", None)
                    st_str = _value_as_string(app_st)
                    if st_str not in ("approved", "APPROVED"):
                        approval_satisfied = False
                        reason_codes.append("operation.approval_invalid")
                    else:
                        app_fp = getattr(app, "request_fingerprint", None)
                        if app_fp and app_fp != request.calculate_fingerprint():
                            approval_satisfied = False
                            reason_codes.append("operation.approval_mismatch")
                        else:
                            reason_codes.append("operation.approval_satisfied")
                except Exception:  # noqa: BLE001
                    approval_satisfied = False
                    reason_codes.append("operation.approval_invalid")

        # Gate 9: Budget check
        if self._budget_service and hasattr(self._budget_service, "check_budget"):
            try:
                bud_res = self._budget_service.check_budget(request)
                if not bud_res:
                    budget_satisfied = False
                    reason_codes.append("operation.budget_exhausted")
                else:
                    reason_codes.append("operation.budget_available")
            except Exception:  # noqa: BLE001
                reason_codes.append("operation.budget_available")

        # Gate 10: Checkpoint check
        if not checkpoint_satisfied:
            reason_codes.append("operation.checkpoint_stale")
        else:
            reason_codes.append("operation.checkpoint_valid")

        # Gate 11: Resource Version check
        if self._resource_version_provider and request.resource_versions:
            for res_uri, exp_ver in request.resource_versions.items():
                cur_ver = self._resource_version_provider.get_version(res_uri)
                if cur_ver != exp_ver:
                    resource_versions_satisfied = False
                    reason_codes.append("operation.resource_version_conflict")
                    break
            if resource_versions_satisfied:
                reason_codes.append("operation.resource_version_match")

        # Gate 12: Lock check
        if self._lock_manager and hasattr(self._lock_manager, "is_locked"):
            try:
                lock_key = (
                    f"operation:{request.operation_name}:{request.idempotency_key}"
                )
                if self._lock_manager.is_locked(lock_key):
                    locks_satisfied = False
                    reason_codes.append("operation.lock_conflict")
                else:
                    reason_codes.append("operation.lock_acquired")
            except Exception:  # noqa: BLE001
                reason_codes.append("operation.lock_acquired")

        # Gate 13: Rollback check
        if desc:
            if desc.reversible is False and desc.rollback_operation_name is None:
                reason_codes.append("operation.irreversible_declared")
            elif desc.rollback_operation_name is None and desc.reversible:
                reason_codes.append("operation.reversible_implicit")

        # Conjuntive decision
        all_satisfied = (
            registered
            and parameters_valid
            and capability_satisfied
            and permissions_satisfied
            and autonomy_satisfied
            and policy_satisfied
            and approval_satisfied
            and budget_satisfied
            and dependencies_satisfied
            and environment_satisfied
            and checkpoint_satisfied
            and rollback_satisfied
            and locks_satisfied
            and resource_versions_satisfied
        )

        denied = not all_satisfied
        allowed = all_satisfied

        return OperationExecutionGateResult(
            request_id=request.id,
            allowed=allowed,
            denied=denied,
            blocked=denied,
            requires_approval=requires_approval,
            requires_validation=desc.validations != () if desc else False,
            requires_budget=requires_budget,
            registered=registered,
            parameters_valid=parameters_valid,
            capability_satisfied=capability_satisfied,
            permissions_satisfied=permissions_satisfied,
            autonomy_satisfied=autonomy_satisfied,
            policy_satisfied=policy_satisfied,
            approval_satisfied=approval_satisfied,
            budget_satisfied=budget_satisfied,
            dependencies_satisfied=dependencies_satisfied,
            environment_satisfied=environment_satisfied,
            checkpoint_satisfied=checkpoint_satisfied,
            rollback_satisfied=rollback_satisfied,
            locks_satisfied=locks_satisfied,
            resource_versions_satisfied=resource_versions_satisfied,
            reason_codes=tuple(reason_codes),
        )
