"""Pure deterministic decision engine for model fallback and escalation."""

from __future__ import annotations

from collections.abc import Callable

from cmm.agent_runtime.model_fallback_contracts import (
    ModelFallbackAction,
    ModelFallbackContext,
    ModelFallbackDecision,
    ModelFallbackTrigger,
)
from cmm.agent_runtime.model_requirements_contracts import model_requirements_to_dict
from kernel.llm.model_router import (
    ModelRouter,
    RoutingCandidate,
    RoutingDecision,
)

FallbackProvider = Callable[[RoutingDecision], tuple[RoutingCandidate, ...]]


class ModelFallbackDecisionEngine:
    """Apply fail-closed precedence to a model attempt and its policy."""

    def __init__(self, fallback_provider: FallbackProvider | None = None) -> None:
        # ModelRouter.fallback_candidates is the canonical candidate ordering.
        self._fallback_provider = fallback_provider or (
            lambda decision: ModelRouter.fallback_candidates(None, decision)
        )

    def decide(self, context: ModelFallbackContext) -> ModelFallbackDecision:
        result = context.latest_result
        policy = context.policy
        attempts = context.history.attempts_including_latest(result)
        reasons: list[str] = []

        if context.privacy.get("compatible") is False or result.trigger is ModelFallbackTrigger.PRIVACY_INCOMPATIBLE:
            return self._restricted(context, "privacy_conflict")
        if context.policy_context.get("allowed", True) is False:
            return self._restricted(context, "policy_denied")
        if not context.budget.get("available", True) or result.trigger is ModelFallbackTrigger.BUDGET_EXHAUSTED:
            return self._restricted(context, "budget_exhausted")

        if context.policy_context.get("premium_required", False):
            if not policy.allow_premium_with_approval:
                return self._decision(context, ModelFallbackAction.FAIL_TERMINAL, ("premium_not_allowed",))
            if not context.approval.get("approved", False):
                return self._decision(context, ModelFallbackAction.REQUEST_APPROVAL, ("approval_required",), requires_approval=True, pause=True)

        if len(attempts) >= policy.maximum_attempts:
            return self._decision(context, ModelFallbackAction.FAIL_TERMINAL, ("maximum_attempts_exhausted",))

        model_count = sum(a.model_id == result.model_id for a in attempts)
        provider_count = sum(a.provider_id == result.provider_id for a in attempts)
        if model_count >= policy.maximum_attempts_per_model:
            reasons.append(f"model_attempt_limit:{result.model_id}")
        if provider_count >= policy.maximum_attempts_per_provider:
            reasons.append(f"provider_attempt_limit:{result.provider_id}")

        if result.trigger in policy.escalation_triggers:
            return self._escalate_or_fail(
                context, (*reasons, result.trigger.value, "escalation_trigger")
            )

        if result.trigger in {
            ModelFallbackTrigger.VALIDATION_FAILED,
            ModelFallbackTrigger.STRUCTURED_OUTPUT_INVALID,
            ModelFallbackTrigger.PARSING_FAILED,
        } and ModelFallbackAction.REVALIDATE in policy.actions:
            return self._decision(context, ModelFallbackAction.REVALIDATE, (*reasons, "revalidation_required"))

        requested_action = context.policy_context.get("requested_action")
        if requested_action is not None:
            try:
                requested = ModelFallbackAction(requested_action)
            except ValueError:
                requested = None
            if requested in {
                ModelFallbackAction.REOBSERVE,
                ModelFallbackAction.REPLAN,
                ModelFallbackAction.PAUSE,
            } and requested in policy.actions:
                return self._decision(
                    context, requested, (*reasons, f"requested_action:{requested.value}"),
                    pause=requested is ModelFallbackAction.PAUSE,
                )

        if result.trigger is ModelFallbackTrigger.CONTEXT_INSUFFICIENT and ModelFallbackAction.RETRY_MODIFIED_PARAMETERS in policy.actions:
            return self._decision(context, ModelFallbackAction.RETRY_MODIFIED_PARAMETERS, (*reasons, "context_reduction_allowed"))

        if result.trigger in policy.retryable_triggers and not reasons and ModelFallbackAction.RETRY_SAME_MODEL in policy.actions:
            return self._decision(context, ModelFallbackAction.RETRY_SAME_MODEL, tuple(reasons))

        selection_actions = {
            ModelFallbackAction.NEXT_ROUTING_CANDIDATE,
            ModelFallbackAction.SELECT_EQUIVALENT_MODEL,
            ModelFallbackAction.SELECT_LOWER_COST_MODEL,
            ModelFallbackAction.SELECT_HIGHER_QUALITY_MODEL,
        }
        if selection_actions.intersection(policy.actions) and context.routing_decision:
            used_models = {attempt.model_id for attempt in attempts}
            skipped: list[str] = []
            excluded: set[str] = set()
            if policy.exclude_failed_model:
                excluded.add(result.model_id)
            if policy.exclude_failed_provider:
                excluded.update(
                    candidate.qualified_model_id
                    for candidate in context.routing_decision.candidates
                    if candidate.provider_id == result.provider_id
                )
                reasons.append(f"provider_excluded:{result.provider_id}")
            candidates = self._fallback_provider(context.routing_decision)
            for candidate in candidates:
                valid, reason = self._candidate_is_valid(context, candidate, used_models, excluded)
                if not valid:
                    skipped.append(candidate.qualified_model_id)
                    reasons.append(reason)
                    continue
                transition = "same_provider" if candidate.provider_id == result.provider_id else "provider_changed"
                selected_action = ModelFallbackAction.NEXT_ROUTING_CANDIDATE
                if ModelFallbackAction.SELECT_HIGHER_QUALITY_MODEL in policy.actions and (
                    result.trigger is ModelFallbackTrigger.QUALITY_INSUFFICIENT
                    or ModelFallbackAction.NEXT_ROUTING_CANDIDATE not in policy.actions
                ):
                    selected_action = ModelFallbackAction.SELECT_HIGHER_QUALITY_MODEL
                elif ModelFallbackAction.SELECT_LOWER_COST_MODEL in policy.actions:
                    selected_action = ModelFallbackAction.SELECT_LOWER_COST_MODEL
                elif ModelFallbackAction.SELECT_EQUIVALENT_MODEL in policy.actions:
                    selected_action = ModelFallbackAction.SELECT_EQUIVALENT_MODEL
                return self._decision(
                    context, selected_action,
                    (*reasons, "next_routing_candidate", transition), candidate.model_id,
                    candidate.provider_id, tuple(skipped),
                )
            reasons.append("routing_candidates_exhausted")

        if policy.allow_rerouting and ModelFallbackAction.REROUTE in policy.actions:
            return self._decision(context, ModelFallbackAction.REROUTE, (*reasons, "reroute_required"))
        if ModelFallbackAction.PAUSE in policy.actions:
            return self._decision(context, ModelFallbackAction.PAUSE, (*reasons, "pause_required"), pause=True)
        return self._decision(context, ModelFallbackAction.FAIL_TERMINAL, (*reasons, "no_safe_fallback"))

    def _candidate_is_valid(
        self,
        context: ModelFallbackContext,
        candidate: RoutingCandidate,
        used_models: set[str],
        excluded: set[str],
    ) -> tuple[bool, str]:
        requirements = context.effective_requirements
        if candidate.model_id in used_models:
            return False, f"model_already_used:{candidate.qualified_model_id}"
        if candidate.qualified_model_id in excluded:
            return False, f"provider_excluded:{candidate.provider_id}"
        if candidate.context_window is None or candidate.context_window < requirements.minimum_context_window:
            return False, f"candidate_context_insufficient:{candidate.qualified_model_id}"
        if requirements.allowed_providers and candidate.provider_id not in requirements.allowed_providers:
            return False, f"candidate_provider_not_allowed:{candidate.provider_id}"
        if candidate.provider_id in requirements.excluded_providers:
            return False, f"provider_excluded:{candidate.provider_id}"
        if requirements.maximum_input_cost_per_million is not None and (
            candidate.input_cost_per_million is None or candidate.input_cost_per_million > requirements.maximum_input_cost_per_million
        ):
            return False, f"candidate_cost_exceeded:{candidate.qualified_model_id}"
        if requirements.maximum_output_cost_per_million is not None and (
            candidate.output_cost_per_million is None or candidate.output_cost_per_million > requirements.maximum_output_cost_per_million
        ):
            return False, f"candidate_cost_exceeded:{candidate.qualified_model_id}"
        provider_types = context.privacy.get("provider_types", {})
        provider_type = provider_types.get(candidate.provider_id)
        if requirements.privacy in {"LOCAL_ONLY", "SENSITIVE"} and provider_type != "local":
            return False, f"candidate_privacy_conflict:{candidate.provider_id}"
        if not context.budget.get("available", True):
            return False, "budget_exhausted"
        return True, ""

    def _restricted(self, context: ModelFallbackContext, reason: str) -> ModelFallbackDecision:
        return self._escalate_or_fail(context, (reason,))

    def _escalate_or_fail(self, context: ModelFallbackContext, reasons: tuple[str, ...]) -> ModelFallbackDecision:
        if ModelFallbackAction.ESCALATE in context.policy.actions:
            return self._decision(context, ModelFallbackAction.ESCALATE, reasons, pause=context.policy.pause_on_escalation)
        return self._decision(context, ModelFallbackAction.FAIL_TERMINAL, reasons)

    @staticmethod
    def _decision(
        context: ModelFallbackContext,
        action: ModelFallbackAction,
        reasons: tuple[str, ...],
        selected_model_id: str | None = None,
        selected_provider_id: str | None = None,
        skipped: tuple[str, ...] = (),
        *,
        requires_approval: bool = False,
        pause: bool = False,
    ) -> ModelFallbackDecision:
        strategy = {
            ModelFallbackAction.RETRY_SAME_MODEL: "retry",
            ModelFallbackAction.RETRY_MODIFIED_PARAMETERS: "retry_with_modified_parameters",
            ModelFallbackAction.NEXT_ROUTING_CANDIDATE: "retry",
            ModelFallbackAction.SELECT_EQUIVALENT_MODEL: "retry",
            ModelFallbackAction.SELECT_LOWER_COST_MODEL: "retry",
            ModelFallbackAction.SELECT_HIGHER_QUALITY_MODEL: "retry",
            ModelFallbackAction.REROUTE: "replan",
            ModelFallbackAction.REOBSERVE: "reobserve",
            ModelFallbackAction.REVALIDATE: "rerun_validation",
            ModelFallbackAction.REPLAN: "replan",
            ModelFallbackAction.REQUEST_APPROVAL: "request_approval",
            ModelFallbackAction.ESCALATE: "escalate",
            ModelFallbackAction.PAUSE: "pause",
            ModelFallbackAction.FAIL_TERMINAL: "fail",
        }.get(action)
        return ModelFallbackDecision(
            operation_id=context.operation_id,
            attempt_index=context.latest_result.attempt_index,
            action=action,
            trigger=context.latest_result.trigger,
            selected_model_id=selected_model_id,
            selected_provider_id=selected_provider_id,
            skipped_candidates=skipped,
            reason_codes=tuple(dict.fromkeys(reasons)),
            effective_requirements=context.effective_requirements,
            requires_approval=requires_approval,
            pause=pause,
            recovery_strategy=strategy,
            metadata={
                "workflow_id": context.workflow_id,
                "history_size": len(context.history.attempts),
                "policy_id": context.policy.id,
                "policy_version": context.policy.version,
                "routing_decision_id": context.routing_decision.id if context.routing_decision else None,
                "effective_requirements": model_requirements_to_dict(context.effective_requirements),
                "history": context.history.to_dict(),
                "approval": context.approval,
                "budget": context.budget,
                "policy_context": context.policy_context,
            },
        )
