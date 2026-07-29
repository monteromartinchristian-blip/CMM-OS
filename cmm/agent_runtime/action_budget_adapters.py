"""Phase 9.11 – Action Budget Adapters.

Provides clean, pure adapters integrating Action Budget with Policy Engine,
Autonomy Levels, and Human Approval System.

Invariants:
* budget_available != policy_allows (Policy DENY overrides available budget).
* level 4 autonomy cannot ignore budget exhaustion.
* budget increases require external approval resolutions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import MappingProxyType

from .action_budget_contracts import (
    ActionBudget,
    BudgetEvaluationResult,
)
from .approval_contracts import ApprovalRequirement, ApprovalResolution
from .autonomy_contracts import AutonomyEvaluationResult
from .enums import (
    ApprovalRequestStatus,
    ApprovalRequirementSource,
    AutonomyDecision,
    BudgetResourceType,
    PolicyDecision,
)
from .errors import (
    BudgetApprovalIntegrationError,
    BudgetPolicyIntegrationError,
)
from .policy_contracts import PolicyEvaluationResult


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class ActionBudgetPolicyAdapter:
    """Adapts Policy Engine evaluation results into Action Budget constraints."""

    @staticmethod
    def apply_policy_to_budget_evaluation(
        budget_evaluation: BudgetEvaluationResult,
        policy_result: PolicyEvaluationResult | None,
    ) -> BudgetEvaluationResult:
        """Combine Policy Engine decision with Action Budget evaluation.

        If policy decision is DENY, budget reservation MUST be denied regardless of availability.
        """
        if policy_result is None:
            return budget_evaluation

        if not isinstance(policy_result, PolicyEvaluationResult):
            raise BudgetPolicyIntegrationError(
                f"policy_result must be PolicyEvaluationResult, got {type(policy_result).__name__}"
            )

        if policy_result.decision == PolicyDecision.DENY:
            reasons = list(budget_evaluation.reason_codes)
            if "budget.policy_denied" not in reasons:
                reasons.append("budget.policy_denied")

            return BudgetEvaluationResult(
                budget_id=budget_evaluation.budget_id,
                allowed=False,
                denied=True,
                warning=budget_evaluation.warning,
                exhausted=budget_evaluation.exhausted,
                status=budget_evaluation.status,
                requested_allocations=budget_evaluation.requested_allocations,
                available=budget_evaluation.available,
                reason_codes=tuple(reasons),
                evaluated_at=budget_evaluation.evaluated_at,
                metadata={
                    "policy_decision": policy_result.decision.value,
                    "policy_reason_codes": list(policy_result.reason_codes),
                },
            )

        return budget_evaluation


class ActionBudgetAutonomyAdapter:
    """Ensures Autonomy Level decisions respect Action Budget limits and exhaustion."""

    @staticmethod
    def apply_autonomy_to_budget_evaluation(
        budget_evaluation: BudgetEvaluationResult,
        autonomy_result: AutonomyEvaluationResult | None,
    ) -> BudgetEvaluationResult:
        """Combine Autonomy Evaluator decision with Action Budget evaluation."""
        if autonomy_result is None:
            return budget_evaluation

        if not isinstance(autonomy_result, AutonomyEvaluationResult):
            raise BudgetPolicyIntegrationError(
                f"autonomy_result must be AutonomyEvaluationResult, got {type(autonomy_result).__name__}"
            )

        if autonomy_result.decision == AutonomyDecision.DENY:
            reasons = list(budget_evaluation.reason_codes)
            if "budget.autonomy_denied" not in reasons:
                reasons.append("budget.autonomy_denied")

            return BudgetEvaluationResult(
                budget_id=budget_evaluation.budget_id,
                allowed=False,
                denied=True,
                warning=budget_evaluation.warning,
                exhausted=budget_evaluation.exhausted,
                status=budget_evaluation.status,
                requested_allocations=budget_evaluation.requested_allocations,
                available=budget_evaluation.available,
                reason_codes=tuple(reasons),
                evaluated_at=budget_evaluation.evaluated_at,
                metadata={
                    "autonomy_decision": autonomy_result.decision.value,
                    "autonomy_level": autonomy_result.level.value
                    if hasattr(autonomy_result.level, "value")
                    else autonomy_result.level,
                },
            )

        return budget_evaluation


class ActionBudgetApprovalAdapter:
    """Adapts Human Approval System contracts to Action Budget limit increase workflows."""

    @staticmethod
    def create_increase_requirement(
        budget: ActionBudget,
        resource_type: BudgetResourceType | str,
        requested_limit: int | Decimal | None = None,
        requested_delta: int | Decimal | None = None,
        reason: str = "Action budget increase requested",
    ) -> ApprovalRequirement:
        """Construct an ApprovalRequirement for requesting a budget limit increase."""
        res_t = (
            BudgetResourceType(resource_type)
            if isinstance(resource_type, str)
            else resource_type
        )
        curr_lim = budget.limit_for(res_t)

        meta = {
            "budget_id": budget.id,
            "agent_run_id": budget.agent_run_id,
            "resource_type": res_t.value,
            "current_limit": str(curr_lim)
            if isinstance(curr_lim, Decimal)
            else curr_lim,
            "requested_limit": str(requested_limit)
            if isinstance(requested_limit, Decimal)
            else requested_limit,
            "requested_delta": str(requested_delta)
            if isinstance(requested_delta, Decimal)
            else requested_delta,
        }

        return ApprovalRequirement(
            id=f"req-budget-increase-{budget.id}-{res_t.value}",
            source=ApprovalRequirementSource.BUDGET,
            title=f"Action budget limit increase for {res_t.value}",
            description=reason,
            required_approvers=("role:supervisor", "role:admin"),
            scope=f"budget.increase.{res_t.value}",
            metadata=MappingProxyType(dict(meta)),
        )

    @staticmethod
    def validate_approval_for_increase(
        resolution: ApprovalResolution,
        budget_id: str,
        resource_type: BudgetResourceType | str,
        now: datetime | None = None,
    ) -> bool:
        """Validate that an ApprovalResolution is valid and permits increasing budget_id."""
        ref_now = now if now is not None else _now_utc()

        if not isinstance(resolution, ApprovalResolution):
            raise BudgetApprovalIntegrationError(
                "resolution must be an instance of ApprovalResolution"
            )

        if resolution.status not in (
            ApprovalRequestStatus.APPROVED,
            ApprovalRequestStatus.APPROVED_WITH_CHANGES,
        ):
            return False

        if not resolution.may_execute:
            return False

        if hasattr(resolution, "is_expired") and resolution.is_expired(ref_now):
            return False

        # Validate budget_id matching in metadata if present
        meta = resolution.metadata
        return not (meta and "budget_id" in meta and meta["budget_id"] != budget_id)
