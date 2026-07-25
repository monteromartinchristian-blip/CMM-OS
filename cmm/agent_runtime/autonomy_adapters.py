"""Phase 9.9 – Autonomy ↔ Policy Engine adapters.

Bridges Phase 9.8 policy evaluation results with Phase 9.9 autonomy
evaluation requests.

Autonomy is an additional binding constraint. Effective authorization
requires all relevant layers to permit the action:

autonomy AND policy AND permissions AND validation AND approval.

This module never reconstructs unavailable policy request data and never
infers security-sensitive operation characteristics from operation names.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .autonomy_contracts import (
    AutonomyCapability,
    AutonomyEvaluationRequest,
    coerce_autonomy_level,
    generate_autonomy_request_id,
)
from .contracts import AgentRun
from .errors import AutonomyPolicyIntegrationError
from .policy_contracts import PolicyEvaluationResult

_POLICY_DENY_VALUES: frozenset[str] = frozenset({"deny"})
_POLICY_REQUIRE_APPROVAL_VALUES: frozenset[str] = frozenset(
    {"require_approval", "require_approval_for"}
)
_POLICY_REQUIRE_VALIDATION_VALUES: frozenset[str] = frozenset({"require_validation"})
_POLICY_PAUSE_VALUES: frozenset[str] = frozenset({"pause"})


def _policy_decision_to_string(result: PolicyEvaluationResult) -> str:
    """Normalize a policy result into an autonomy-compatible decision."""
    if result.denied:
        return "deny"

    decision = str(result.decision.value).strip().lower()

    if decision in _POLICY_DENY_VALUES:
        return "deny"

    if result.requires_approval or decision in _POLICY_REQUIRE_APPROVAL_VALUES:
        return "require_approval"

    if result.requires_validation or decision in _POLICY_REQUIRE_VALIDATION_VALUES:
        return "require_validation"

    if result.paused or decision in _POLICY_PAUSE_VALUES:
        return "pause"

    if result.allowed:
        return "allow"

    return decision or "indeterminate"


def create_autonomy_request_from_policy_result(
    *,
    agent_run: AgentRun,
    capability: AutonomyCapability | str,
    policy_result: PolicyEvaluationResult,
    operation_name: str | None = None,
    is_mutation: bool = False,
    is_reversible: bool = True,
    is_destructive: bool = False,
    is_external: bool = False,
    is_sensitive: bool = False,
    requires_spend: bool = False,
    changes_permissions: bool = False,
    changes_policy: bool = False,
    approval_present: bool = False,
    validation_passed: bool = False,
    rollback_available: bool = False,
    metadata: Mapping[str, Any] | None = None,
) -> AutonomyEvaluationRequest:
    """Build an autonomy request from an explicit policy result.

    Security-relevant operation characteristics must be provided by the
    caller. They are never inferred from operation names or rule metadata,
    because ``PolicyEvaluationResult`` does not preserve the original
    request contract.

    Safe defaults describe a read-only, reversible, non-sensitive action.
    Callers evaluating mutations or higher-impact operations must pass the
    corresponding flags explicitly.
    """
    if not isinstance(agent_run, AgentRun):
        raise AutonomyPolicyIntegrationError(
            "create_autonomy_request_from_policy_result requires an AgentRun"
        )

    if not isinstance(policy_result, PolicyEvaluationResult):
        raise AutonomyPolicyIntegrationError(
            "create_autonomy_request_from_policy_result requires a "
            "PolicyEvaluationResult"
        )

    return AutonomyEvaluationRequest(
        id=generate_autonomy_request_id(),
        agent_run_id=agent_run.id,
        autonomy_level=coerce_autonomy_level(agent_run.autonomy_level),
        capability=capability,
        operation_name=operation_name,
        is_mutation=is_mutation,
        is_reversible=is_reversible,
        is_destructive=is_destructive,
        is_external=is_external,
        is_sensitive=is_sensitive,
        requires_spend=requires_spend,
        changes_permissions=changes_permissions,
        changes_policy=changes_policy,
        policy_decision=_policy_decision_to_string(policy_result),
        approval_present=approval_present,
        validation_passed=validation_passed,
        rollback_available=rollback_available,
        metadata=metadata or {},
    )


__all__ = [
    "create_autonomy_request_from_policy_result",
]
