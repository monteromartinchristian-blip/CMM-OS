"""Bridge between Phase 10.15 PermissionApprovalRequirement and Phase 9 ApprovalRequirement.

This module provides deterministic, pure translation functions
between the two contract types without creating a parallel lifecycle.
The bridge is one-way: 10.15 produces PermissionApprovalRequirement,
and the bridge converts it into a canonical ApprovalRequirement
consumable by ApprovalService.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from cmm.agent_runtime.approval_contracts import (
    ApprovalRequirement,
)
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionApprovalRequirement,
)
from cmm.agent_runtime.enums import (
    ApprovalRequirementSource,
    PolicyRiskLevel,
)

_RISK_MAP: Mapping[str, PolicyRiskLevel] = {
    "low": PolicyRiskLevel.LOW,
    "medium": PolicyRiskLevel.MEDIUM,
    "high": PolicyRiskLevel.HIGH,
    "critical": PolicyRiskLevel.CRITICAL,
}


def to_approval_requirement(
    par: PermissionApprovalRequirement,
    *,
    agent_run_id: str | None = None,
    goal_id: str | None = None,
) -> ApprovalRequirement:
    """Convert a PermissionApprovalRequirement into an ApprovalRequirement.

    The complete security binding is preserved as the typed
    ``permission_requirement`` field.  Operation/workflow identity, scope,
    expiration and risk are also projected into the canonical approval fields;
    metadata contains provenance only and is never authorization evidence.
    """
    risk = _RISK_MAP.get(par.risk, PolicyRiskLevel.MEDIUM)
    action_label = par.action.value if hasattr(par.action, "value") else str(par.action)

    metadata: dict[str, Any] = {"source": "domain_permission"}

    return ApprovalRequirement(
        id=par.requirement_id,
        source=ApprovalRequirementSource.SECURITY,
        title=f"Permission approval required: {action_label}",
        description=(
            f"Domain permission resolution requires approval for "
            f"{action_label} in domain {par.domain_id} "
            f"(reason: {par.reason_code})"
        ),
        reason_codes=(par.reason_code, "domain_permission"),
        risk_level=risk,
        scope=par.scope,
        agent_run_id=agent_run_id,
        goal_id=goal_id,
        workflow_id=par.workflow_id,
        operation_id=par.operation_id,
        permission_requirement=par,
        expires_at=par.expires_at,
        metadata=metadata,
    )


def to_approval_requirements(
    requirements: tuple[PermissionApprovalRequirement, ...],
    *,
    agent_run_id: str | None = None,
    goal_id: str | None = None,
) -> tuple[ApprovalRequirement, ...]:
    """Convert a tuple of PermissionApprovalRequirements."""
    return tuple(
        to_approval_requirement(r, agent_run_id=agent_run_id, goal_id=goal_id)
        for r in requirements
    )


__all__ = ["to_approval_requirement", "to_approval_requirements"]
