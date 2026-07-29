"""Phase 9.6 – Information Acquisition Strategy Service and Resolver.

Implements the Information Acquisition Resolver, read-only search/query handlers,
and InformationAcquisitionService.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, ClassVar, Protocol, runtime_checkable

from cmm.agent_runtime.enums import (
    InformationAcquisitionDecisionType,
    InformationAcquisitionRisk,
    InformationAcquisitionSource,
    InformationAcquisitionStatus,
    InformationAcquisitionStrategy,
)
from cmm.agent_runtime.errors import (
    InformationAcquisitionHandlerError,
    InformationAcquisitionResolutionError,
    InformationAcquisitionStrategyUnavailableError,
    InvalidInformationAcquisitionContractError,
)
from cmm.agent_runtime.information_acquisition_contracts import (
    InformationAcquisitionCandidate,
    InformationAcquisitionContext,
    InformationAcquisitionCost,
    InformationAcquisitionDecision,
    InformationAcquisitionPolicy,
    InformationAcquisitionRequest,
    InformationAcquisitionResult,
    generate_acquisition_decision_id,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class AcquisitionSearchResult:
    """Structured result returned by a read-only information acquisition handler."""

    query: str
    source: InformationAcquisitionSource
    source_ids: tuple[str, ...] = ()
    provenance: str = ""
    timestamp: str = field(default_factory=_now_iso)
    temporal_validity: str = "valid"
    confidence: float = 1.0
    items: tuple[Any, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def serialize(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "source": self.source.value,
            "source_ids": list(self.source_ids),
            "provenance": self.provenance,
            "timestamp": self.timestamp,
            "temporal_validity": self.temporal_validity,
            "confidence": self.confidence,
            "items": [
                item.to_dict() if hasattr(item, "to_dict") else str(item)
                for item in self.items
            ],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()


@runtime_checkable
class InformationAcquisitionResolver(Protocol):
    """Protocol for Information Acquisition Resolvers."""

    def resolve(
        self,
        request: InformationAcquisitionRequest,
        policy: InformationAcquisitionPolicy | None = None,
    ) -> InformationAcquisitionResult:
        """Evaluate and select an information acquisition strategy for a request."""
        ...


@runtime_checkable
class InformationAcquisitionHandler(Protocol):
    """Protocol for read-only information acquisition strategy handlers."""

    def execute(
        self,
        request: InformationAcquisitionRequest,
        candidate: InformationAcquisitionCandidate,
    ) -> AcquisitionSearchResult:
        """Execute a read-only acquisition strategy."""
        ...


class DefaultInformationAcquisitionResolver:
    """Default deterministic implementation of InformationAcquisitionResolver.

    Evaluates gap, context, availability, permissions, sensitivity, and policy rules
    to select the best acquisition strategy deterministically without mutating state.
    """

    # Risk numeric weight for tie-breaking
    _RISK_WEIGHT: ClassVar[dict[InformationAcquisitionRisk, int]] = {
        InformationAcquisitionRisk.NONE: 0,
        InformationAcquisitionRisk.LOW: 1,
        InformationAcquisitionRisk.MEDIUM: 2,
        InformationAcquisitionRisk.HIGH: 3,
        InformationAcquisitionRisk.CRITICAL: 4,
    }

    # Default strategy preferences
    _DEFAULT_PREFERENCE_ORDER: tuple[InformationAcquisitionStrategy, ...] = (
        InformationAcquisitionStrategy.SEARCH_KNOWLEDGE,
        InformationAcquisitionStrategy.LOAD_INTERNAL_RESOURCE,
        InformationAcquisitionStrategy.ASK_USER,
        InformationAcquisitionStrategy.SEARCH_REPOSITORY,
        InformationAcquisitionStrategy.SEARCH_EXTERNAL_SOURCE,
        InformationAcquisitionStrategy.INFER_WITH_PERMISSION,
        InformationAcquisitionStrategy.REQUEST_HUMAN_REVIEW,
        InformationAcquisitionStrategy.ACCEPT_UNCERTAINTY,
        InformationAcquisitionStrategy.PAUSE,
        InformationAcquisitionStrategy.ABORT,
    )

    def __init__(
        self,
        default_policy: InformationAcquisitionPolicy | None = None,
        available_handlers: Mapping[
            InformationAcquisitionStrategy, InformationAcquisitionHandler
        ]
        | None = None,
    ) -> None:
        self._default_policy = default_policy or InformationAcquisitionPolicy()
        self._handlers: dict[
            InformationAcquisitionStrategy, InformationAcquisitionHandler
        ] = dict(available_handlers or {})

    def resolve(
        self,
        request: InformationAcquisitionRequest,
        policy: InformationAcquisitionPolicy | None = None,
    ) -> InformationAcquisitionResult:
        """Resolve acquisition request into a structured decision and result."""
        if not isinstance(request, InformationAcquisitionRequest):
            raise InvalidInformationAcquisitionContractError(
                "request must be an InformationAcquisitionRequest instance"
            )

        active_policy = policy or self._default_policy
        if not isinstance(active_policy, InformationAcquisitionPolicy):
            raise InvalidInformationAcquisitionContractError(
                "policy must be an InformationAcquisitionPolicy instance"
            )

        context = self._build_context(request)
        candidates = self.generate_candidates(request, context, active_policy)
        filtered_candidates = self._filter_candidates(
            candidates, request, context, active_policy
        )

        ordered_candidates = self._order_candidates(filtered_candidates, active_policy)

        if not ordered_candidates:
            # Fallback to abort or pause
            decision = self._build_fallback_decision(request, active_policy, candidates)
        else:
            top_candidate = ordered_candidates[0]
            rejected = tuple(ordered_candidates[1:])
            decision = self._build_decision_from_candidate(
                request, top_candidate, rejected, active_policy
            )

        status = (
            InformationAcquisitionStatus.SELECTED
            if decision.decision != InformationAcquisitionDecisionType.ABORT
            else InformationAcquisitionStatus.BLOCKED
        )

        return InformationAcquisitionResult(
            request=request,
            context=context,
            decision=decision,
            candidates=ordered_candidates,
            status=status,
            confidence=decision.expected_confidence_gain,
            created_at=_now_iso(),
            metadata=MappingProxyType({"policy": active_policy.to_dict()}),
        )

    def generate_candidates(
        self,
        request: InformationAcquisitionRequest,
        context: InformationAcquisitionContext,
        policy: InformationAcquisitionPolicy,
    ) -> tuple[InformationAcquisitionCandidate, ...]:
        """Generate candidate strategies based on request properties and gap analysis."""
        gap_info = self._extract_gap_info(request.gap)

        candidates: list[InformationAcquisitionCandidate] = []

        # 1. Ask User Candidate
        ask_user_cand = self._eval_ask_user_candidate(
            request, context, policy, gap_info
        )
        candidates.append(ask_user_cand)

        # 2. Load Internal Resource Candidate
        load_res_cand = self._eval_load_resource_candidate(
            request, context, policy, gap_info
        )
        candidates.append(load_res_cand)

        # 3. Search Knowledge Candidate
        search_know_cand = self._eval_search_knowledge_candidate(
            request, context, policy, gap_info
        )
        candidates.append(search_know_cand)

        # 4. Search Repository Candidate
        search_repo_cand = self._eval_search_repository_candidate(
            request, context, policy, gap_info
        )
        candidates.append(search_repo_cand)

        # 5. Search External Source Candidate
        search_ext_cand = self._eval_search_external_candidate(
            request, context, policy, gap_info
        )
        candidates.append(search_ext_cand)

        # 6. Infer with Permission Candidate
        infer_cand = self._eval_infer_candidate(request, context, policy, gap_info)
        candidates.append(infer_cand)

        # 7. Request Human Review Candidate
        human_cand = self._eval_human_review_candidate(
            request, context, policy, gap_info
        )
        candidates.append(human_cand)

        # 8. Accept Uncertainty Candidate
        accept_unc_cand = self._eval_accept_uncertainty_candidate(
            request, context, policy, gap_info
        )
        candidates.append(accept_unc_cand)

        # 9. Pause Candidate
        pause_cand = self._eval_pause_candidate(request, context, policy, gap_info)
        candidates.append(pause_cand)

        # 10. Abort Candidate
        abort_cand = self._eval_abort_candidate(request, context, policy, gap_info)
        candidates.append(abort_cand)

        return tuple(candidates)

    def _extract_gap_info(self, gap: Any) -> dict[str, Any]:
        """Extract standardized properties from a gap object (dict, dataclass, or object)."""
        req_val = (
            gap.get("required")
            if isinstance(gap, dict)
            else getattr(gap, "required", True)
        )
        block_val = (
            gap.get("is_blocking")
            if isinstance(gap, dict)
            else getattr(gap, "is_blocking", None)
        )
        if block_val is None:
            block_val = req_val

        info: dict[str, Any] = {
            "id": getattr(gap, "id", None)
            or (gap.get("id") if isinstance(gap, dict) else str(gap)),
            "question": getattr(gap, "question", None)
            or (gap.get("question") if isinstance(gap, dict) else ""),
            "topic": getattr(gap, "topic", None)
            or (gap.get("topic") if isinstance(gap, dict) else ""),
            "impact": getattr(gap, "impact", None)
            or (gap.get("impact") if isinstance(gap, dict) else "medium"),
            "required": bool(req_val),
            "is_blocking": bool(block_val),
            "resource_reference": getattr(gap, "resource_reference", None)
            or (gap.get("resource_reference") if isinstance(gap, dict) else None),
            "domain": getattr(gap, "domain", None)
            or (gap.get("domain") if isinstance(gap, dict) else ""),
            "metadata": getattr(gap, "metadata", {})
            or (gap.get("metadata", {}) if isinstance(gap, dict) else {}),
        }
        return info

    def _eval_ask_user_candidate(
        self,
        request: InformationAcquisitionRequest,
        context: InformationAcquisitionContext,
        policy: InformationAcquisitionPolicy,
        gap_info: dict[str, Any],
    ) -> InformationAcquisitionCandidate:
        blockers: list[str] = []
        reasons: list[str] = []

        if not policy.allow_questions:
            blockers.append("Policy prohibits questions")
        if request.maximum_questions_remaining <= 0:
            blockers.append("No remaining question budget")

        is_blocking = gap_info.get("is_blocking", True) or gap_info.get(
            "required", True
        )
        if is_blocking:
            reasons.append("Gap is blocking and resoluble by user")

        avail = len(blockers) == 0
        risk = InformationAcquisitionRisk.NONE
        cost = InformationAcquisitionCost(questions=1, risk=risk)

        return InformationAcquisitionCandidate(
            strategy=InformationAcquisitionStrategy.ASK_USER,
            applicability=0.95 if is_blocking else 0.5,
            availability=avail,
            estimated_cost=cost,
            estimated_duration_seconds=30.0,
            expected_confidence_gain=0.9,
            probability_of_resolution=0.95,
            risk=risk,
            required_permissions=(),
            sensitivity=request.sensitivity,
            reasons=tuple(reasons),
            blockers=tuple(blockers),
        )

    def _eval_load_resource_candidate(
        self,
        request: InformationAcquisitionRequest,
        context: InformationAcquisitionContext,
        policy: InformationAcquisitionPolicy,
        gap_info: dict[str, Any],
    ) -> InformationAcquisitionCandidate:
        blockers: list[str] = []
        reasons: list[str] = []

        has_res = bool(
            request.available_resources
            or request.available_resource_ids
            or gap_info.get("resource_reference")
        )
        if not has_res:
            blockers.append("No internal resource available for gap")
        else:
            reasons.append("Internal resource available for loading")

        if request.maximum_internal_calls_remaining <= 0:
            blockers.append("No internal call budget remaining")

        avail = len(blockers) == 0
        cost = InformationAcquisitionCost(
            internal_calls=1, risk=InformationAcquisitionRisk.NONE
        )

        return InformationAcquisitionCandidate(
            strategy=InformationAcquisitionStrategy.LOAD_INTERNAL_RESOURCE,
            applicability=0.98 if has_res else 0.2,
            availability=avail,
            estimated_cost=cost,
            estimated_duration_seconds=0.5,
            expected_confidence_gain=0.85,
            probability_of_resolution=0.9,
            risk=InformationAcquisitionRisk.NONE,
            reasons=tuple(reasons),
            blockers=tuple(blockers),
        )

    def _eval_search_knowledge_candidate(
        self,
        request: InformationAcquisitionRequest,
        context: InformationAcquisitionContext,
        policy: InformationAcquisitionPolicy,
        gap_info: dict[str, Any],
    ) -> InformationAcquisitionCandidate:
        blockers: list[str] = []
        reasons: list[str] = ["Knowledge Store available for query"]

        if not policy.allow_internal_search:
            blockers.append("Policy prohibits internal search")

        has_res = bool(
            request.available_resources
            or request.available_resource_ids
            or gap_info.get("resource_reference")
        )
        is_user_blocking = (
            gap_info.get("is_blocking", True) or gap_info.get("required", True)
        ) and getattr(request.gap, "question", None)

        applicability = 0.85
        if has_res:
            applicability = 0.6
        elif is_user_blocking:
            applicability = 0.7

        avail = len(blockers) == 0
        cost = InformationAcquisitionCost(
            internal_calls=1, risk=InformationAcquisitionRisk.NONE
        )

        return InformationAcquisitionCandidate(
            strategy=InformationAcquisitionStrategy.SEARCH_KNOWLEDGE,
            applicability=applicability,
            availability=avail,
            estimated_cost=cost,
            estimated_duration_seconds=0.2,
            expected_confidence_gain=0.8,
            probability_of_resolution=0.85,
            risk=InformationAcquisitionRisk.NONE,
            reasons=tuple(reasons),
            blockers=tuple(blockers),
        )

    def _eval_search_repository_candidate(
        self,
        request: InformationAcquisitionRequest,
        context: InformationAcquisitionContext,
        policy: InformationAcquisitionPolicy,
        gap_info: dict[str, Any],
    ) -> InformationAcquisitionCandidate:
        blockers: list[str] = []
        reasons: list[str] = []

        if not policy.allow_internal_search:
            blockers.append("Policy prohibits repository search")

        reasons.append("Repository code and structure available")
        avail = len(blockers) == 0
        cost = InformationAcquisitionCost(
            internal_calls=1, risk=InformationAcquisitionRisk.LOW
        )

        return InformationAcquisitionCandidate(
            strategy=InformationAcquisitionStrategy.SEARCH_REPOSITORY,
            applicability=0.8,
            availability=avail,
            estimated_cost=cost,
            estimated_duration_seconds=1.0,
            expected_confidence_gain=0.75,
            probability_of_resolution=0.8,
            risk=InformationAcquisitionRisk.LOW,
            reasons=tuple(reasons),
            blockers=tuple(blockers),
        )

    def _eval_search_external_candidate(
        self,
        request: InformationAcquisitionRequest,
        context: InformationAcquisitionContext,
        policy: InformationAcquisitionPolicy,
        gap_info: dict[str, Any],
    ) -> InformationAcquisitionCandidate:
        blockers: list[str] = []
        reasons: list[str] = []

        if not policy.allow_external_search:
            blockers.append("Policy prohibits external search")

        if request.sensitivity.lower() in (
            "restricted",
            "confidential",
            "secret",
            "high",
        ):
            blockers.append(
                f"Incompatible sensitivity for external search: {request.sensitivity}"
            )

        if request.maximum_external_calls_remaining <= 0:
            blockers.append("No external call budget remaining")

        handler_avail = (
            InformationAcquisitionStrategy.SEARCH_EXTERNAL_SOURCE in self._handlers
        )
        if not handler_avail:
            reasons.append("External search capability not configured locally")

        avail = len(blockers) == 0
        cost = InformationAcquisitionCost(
            external_calls=1, risk=InformationAcquisitionRisk.MEDIUM
        )

        return InformationAcquisitionCandidate(
            strategy=InformationAcquisitionStrategy.SEARCH_EXTERNAL_SOURCE,
            applicability=0.6,
            availability=avail,
            estimated_cost=cost,
            estimated_duration_seconds=5.0,
            expected_confidence_gain=0.6,
            probability_of_resolution=0.6,
            risk=InformationAcquisitionRisk.MEDIUM,
            required_permissions=("external_search",),
            sensitivity=request.sensitivity,
            reasons=tuple(reasons),
            blockers=tuple(blockers),
        )

    def _eval_infer_candidate(
        self,
        request: InformationAcquisitionRequest,
        context: InformationAcquisitionContext,
        policy: InformationAcquisitionPolicy,
        gap_info: dict[str, Any],
    ) -> InformationAcquisitionCandidate:
        blockers: list[str] = []
        reasons: list[str] = []

        if not policy.allow_inference:
            blockers.append("Policy prohibits inference")

        is_high_impact = gap_info.get("impact") in ("high", "critical")
        if is_high_impact:
            blockers.append("Inference prohibited for high impact gaps")

        reasons.append("Cognitive inference allowed with permission")
        avail = len(blockers) == 0
        cost = InformationAcquisitionCost(
            model_calls=1, risk=InformationAcquisitionRisk.MEDIUM
        )

        return InformationAcquisitionCandidate(
            strategy=InformationAcquisitionStrategy.INFER_WITH_PERMISSION,
            applicability=0.5,
            availability=avail,
            estimated_cost=cost,
            estimated_duration_seconds=2.0,
            expected_confidence_gain=0.5,
            probability_of_resolution=0.5,
            risk=InformationAcquisitionRisk.MEDIUM,
            required_permissions=("inference",),
            reasons=tuple(reasons),
            blockers=tuple(blockers),
        )

    def _eval_human_review_candidate(
        self,
        request: InformationAcquisitionRequest,
        context: InformationAcquisitionContext,
        policy: InformationAcquisitionPolicy,
        gap_info: dict[str, Any],
    ) -> InformationAcquisitionCandidate:
        blockers: list[str] = []
        reasons: list[str] = []

        if not policy.allow_human_review:
            blockers.append("Policy prohibits human review")

        is_critical = gap_info.get("impact") == "critical"
        if is_critical:
            reasons.append("Critical gap requires human review")

        avail = len(blockers) == 0
        risk = (
            InformationAcquisitionRisk.NONE
            if is_critical
            else InformationAcquisitionRisk.LOW
        )
        cost = InformationAcquisitionCost(risk=risk)

        return InformationAcquisitionCandidate(
            strategy=InformationAcquisitionStrategy.REQUEST_HUMAN_REVIEW,
            applicability=0.99 if is_critical else 0.4,
            availability=avail,
            estimated_cost=cost,
            estimated_duration_seconds=300.0,
            expected_confidence_gain=0.95,
            probability_of_resolution=0.95,
            risk=risk,
            requires_approval=True,
            reasons=tuple(reasons),
            blockers=tuple(blockers),
        )

    def _eval_accept_uncertainty_candidate(
        self,
        request: InformationAcquisitionRequest,
        context: InformationAcquisitionContext,
        policy: InformationAcquisitionPolicy,
        gap_info: dict[str, Any],
    ) -> InformationAcquisitionCandidate:
        blockers: list[str] = []
        reasons: list[str] = []

        if not policy.allow_accept_uncertainty:
            blockers.append("Policy prohibits accepting uncertainty")

        is_blocking = gap_info.get("is_blocking", True) or gap_info.get(
            "required", True
        )
        if is_blocking:
            blockers.append("Gap is blocking and cannot accept uncertainty")
        else:
            reasons.append("Gap is optional / non-blocking")

        avail = len(blockers) == 0
        cost = InformationAcquisitionCost(risk=InformationAcquisitionRisk.LOW)

        return InformationAcquisitionCandidate(
            strategy=InformationAcquisitionStrategy.ACCEPT_UNCERTAINTY,
            applicability=0.8 if not is_blocking else 0.0,
            availability=avail,
            estimated_cost=cost,
            estimated_duration_seconds=0.0,
            expected_confidence_gain=0.0,
            probability_of_resolution=0.0,
            risk=InformationAcquisitionRisk.LOW,
            reasons=tuple(reasons),
            blockers=tuple(blockers),
        )

    def _eval_pause_candidate(
        self,
        request: InformationAcquisitionRequest,
        context: InformationAcquisitionContext,
        policy: InformationAcquisitionPolicy,
        gap_info: dict[str, Any],
    ) -> InformationAcquisitionCandidate:
        cost = InformationAcquisitionCost(risk=InformationAcquisitionRisk.NONE)
        return InformationAcquisitionCandidate(
            strategy=InformationAcquisitionStrategy.PAUSE,
            applicability=0.1,
            availability=True,
            estimated_cost=cost,
            estimated_duration_seconds=0.0,
            expected_confidence_gain=0.0,
            probability_of_resolution=0.0,
            risk=InformationAcquisitionRisk.NONE,
            reasons=("System can pause and await external capability/resource",),
            blockers=(),
        )

    def _eval_abort_candidate(
        self,
        request: InformationAcquisitionRequest,
        context: InformationAcquisitionContext,
        policy: InformationAcquisitionPolicy,
        gap_info: dict[str, Any],
    ) -> InformationAcquisitionCandidate:
        cost = InformationAcquisitionCost(risk=InformationAcquisitionRisk.NONE)
        return InformationAcquisitionCandidate(
            strategy=InformationAcquisitionStrategy.ABORT,
            applicability=0.05,
            availability=True,
            estimated_cost=cost,
            estimated_duration_seconds=0.0,
            expected_confidence_gain=0.0,
            probability_of_resolution=0.0,
            risk=InformationAcquisitionRisk.NONE,
            reasons=("Abort run when resolution is unsafe or impossible",),
            blockers=(),
        )

    def _filter_candidates(
        self,
        candidates: tuple[InformationAcquisitionCandidate, ...],
        request: InformationAcquisitionRequest,
        context: InformationAcquisitionContext,
        policy: InformationAcquisitionPolicy,
    ) -> tuple[InformationAcquisitionCandidate, ...]:
        """Filter out candidates that violate permissions, policies, or prohibitions."""
        filtered: list[InformationAcquisitionCandidate] = []

        for cand in candidates:
            if not cand.availability:
                continue

            # Check prohibited strategies from request and policy
            if (
                cand.strategy in request.prohibited_strategies
                or cand.strategy in policy.prohibited_strategies
            ):
                continue

            # Check allowed strategies if specified
            if (
                request.allowed_strategies
                and cand.strategy not in request.allowed_strategies
            ):
                continue
            if (
                policy.allowed_strategies
                and cand.strategy not in policy.allowed_strategies
            ):
                continue

            # Check required permissions
            if cand.required_permissions:
                has_perms = all(
                    p in context.permissions for p in cand.required_permissions
                )
                if not has_perms:
                    continue

            # Check risk against maximum risk
            cand_risk_weight = self._RISK_WEIGHT.get(cand.risk, 0)
            max_risk_weight = self._RISK_WEIGHT.get(policy.maximum_risk, 4)
            if cand_risk_weight > max_risk_weight:
                continue

            filtered.append(cand)

        return tuple(filtered)

    def _order_candidates(
        self,
        candidates: tuple[InformationAcquisitionCandidate, ...],
        policy: InformationAcquisitionPolicy,
    ) -> tuple[InformationAcquisitionCandidate, ...]:
        """Order candidates deterministically according to tie-breaking criteria."""
        pref_order = policy.preferred_strategies or self._DEFAULT_PREFERENCE_ORDER
        pref_indices = {strat: idx for idx, strat in enumerate(pref_order)}

        def sort_key(cand: InformationAcquisitionCandidate) -> tuple[Any, ...]:
            app_val = -cand.applicability
            risk_w = self._RISK_WEIGHT.get(cand.risk, 0)
            cost_val = (
                cand.estimated_cost.monetary_cost
                + cand.estimated_cost.internal_calls
                + cand.estimated_cost.external_calls
                + cand.estimated_cost.questions
            )
            prob_res = -cand.probability_of_resolution
            conf_gain = -cand.expected_confidence_gain
            ext_calls = cand.estimated_cost.external_calls
            pref_idx = pref_indices.get(cand.strategy, 999)
            strat_name = cand.strategy.value

            return (
                app_val,
                risk_w,
                cost_val,
                prob_res,
                conf_gain,
                ext_calls,
                pref_idx,
                strat_name,
            )

        return tuple(sorted(candidates, key=sort_key))

    def _build_context(
        self, request: InformationAcquisitionRequest
    ) -> InformationAcquisitionContext:
        sources: list[InformationAcquisitionSource] = [
            InformationAcquisitionSource.KNOWLEDGE_STORE,
            InformationAcquisitionSource.REPOSITORY,
            InformationAcquisitionSource.USER,
        ]
        if InformationAcquisitionStrategy.SEARCH_EXTERNAL_SOURCE in self._handlers:
            sources.append(InformationAcquisitionSource.EXTERNAL_SOURCE)

        return InformationAcquisitionContext(
            request_id=request.id,
            agent_run_id=request.agent_run_id,
            goal_id=request.goal_id,
            gap_id=request.gap_id,
            sources_available=tuple(sources),
            permissions=request.permissions,
            sensitivity=request.sensitivity,
            current_question_count=0,
            current_internal_call_count=0,
            current_external_call_count=0,
            metadata=request.metadata,
        )

    def _build_decision_from_candidate(
        self,
        request: InformationAcquisitionRequest,
        candidate: InformationAcquisitionCandidate,
        rejected: tuple[InformationAcquisitionCandidate, ...],
        policy: InformationAcquisitionPolicy,
    ) -> InformationAcquisitionDecision:
        dec_type_map = {
            InformationAcquisitionStrategy.ASK_USER: InformationAcquisitionDecisionType.ASK_USER,
            InformationAcquisitionStrategy.LOAD_INTERNAL_RESOURCE: InformationAcquisitionDecisionType.LOAD_RESOURCE,
            InformationAcquisitionStrategy.SEARCH_KNOWLEDGE: InformationAcquisitionDecisionType.SEARCH,
            InformationAcquisitionStrategy.SEARCH_REPOSITORY: InformationAcquisitionDecisionType.SEARCH,
            InformationAcquisitionStrategy.SEARCH_EXTERNAL_SOURCE: InformationAcquisitionDecisionType.SEARCH,
            InformationAcquisitionStrategy.INFER_WITH_PERMISSION: InformationAcquisitionDecisionType.INFER,
            InformationAcquisitionStrategy.REQUEST_HUMAN_REVIEW: InformationAcquisitionDecisionType.REQUEST_HUMAN_REVIEW,
            InformationAcquisitionStrategy.ACCEPT_UNCERTAINTY: InformationAcquisitionDecisionType.ACCEPT_UNCERTAINTY,
            InformationAcquisitionStrategy.PAUSE: InformationAcquisitionDecisionType.PAUSE,
            InformationAcquisitionStrategy.ABORT: InformationAcquisitionDecisionType.ABORT,
        }

        dec_type = dec_type_map.get(
            candidate.strategy, InformationAcquisitionDecisionType.SELECT_STRATEGY
        )

        return InformationAcquisitionDecision(
            id=generate_acquisition_decision_id(),
            request_id=request.id,
            gap_id=request.gap_id,
            decision=dec_type,
            strategy=candidate.strategy,
            expected_cost=candidate.estimated_cost,
            reason_codes=candidate.reasons or ("selected_by_policy",),
            selected_candidate=candidate,
            rejected_candidates=rejected,
            expected_confidence_gain=candidate.expected_confidence_gain,
            requires_permission=bool(candidate.required_permissions),
            requires_approval=candidate.requires_approval,
            requires_user_input=(
                candidate.strategy == InformationAcquisitionStrategy.ASK_USER
            ),
            requires_resource=(
                candidate.strategy
                == InformationAcquisitionStrategy.LOAD_INTERNAL_RESOURCE
            ),
            blocked=(candidate.strategy == InformationAcquisitionStrategy.ABORT),
            created_at=_now_iso(),
        )

    def _build_fallback_decision(
        self,
        request: InformationAcquisitionRequest,
        policy: InformationAcquisitionPolicy,
        all_candidates: tuple[InformationAcquisitionCandidate, ...],
    ) -> InformationAcquisitionDecision:
        abort_cand = next(
            (
                c
                for c in all_candidates
                if c.strategy == InformationAcquisitionStrategy.ABORT
            ),
            InformationAcquisitionCandidate(
                strategy=InformationAcquisitionStrategy.ABORT,
                availability=True,
                estimated_cost=InformationAcquisitionCost(),
            ),
        )
        return InformationAcquisitionDecision(
            id=generate_acquisition_decision_id(),
            request_id=request.id,
            gap_id=request.gap_id,
            decision=InformationAcquisitionDecisionType.ABORT,
            strategy=InformationAcquisitionStrategy.ABORT,
            expected_cost=InformationAcquisitionCost(),
            reason_codes=("no_eligible_candidate", "all_strategies_filtered"),
            selected_candidate=abort_cand,
            rejected_candidates=all_candidates,
            expected_confidence_gain=0.0,
            blocked=True,
            created_at=_now_iso(),
        )


class InformationAcquisitionService:
    """Orchestration service for resolving and executing information acquisition operations."""

    def __init__(
        self,
        resolver: InformationAcquisitionResolver | None = None,
        policy: InformationAcquisitionPolicy | None = None,
    ) -> None:
        self._resolver = resolver or DefaultInformationAcquisitionResolver()
        self._default_policy = policy or InformationAcquisitionPolicy()
        self._handlers: dict[
            InformationAcquisitionStrategy, InformationAcquisitionHandler
        ] = {}

    def register_handler(
        self,
        strategy: InformationAcquisitionStrategy,
        handler: InformationAcquisitionHandler,
    ) -> None:
        """Register a read-only strategy handler."""
        if isinstance(strategy, str):
            strategy = InformationAcquisitionStrategy(strategy)
        self._handlers[strategy] = handler

    def acquire_information(
        self,
        request: InformationAcquisitionRequest,
        policy: InformationAcquisitionPolicy | None = None,
    ) -> InformationAcquisitionResult:
        """Resolve information acquisition request and produce structured decision/result."""
        active_policy = policy or self._default_policy
        return self._resolver.resolve(request, active_policy)

    def execute_selected_strategy(
        self,
        result: InformationAcquisitionResult,
    ) -> AcquisitionSearchResult:
        """Execute the read-only strategy selected in an acquisition result if a handler is registered."""
        strategy = result.decision.strategy
        if strategy not in self._handlers:
            raise InformationAcquisitionStrategyUnavailableError(
                f"No handler registered for strategy: {strategy.value}"
            )

        handler = self._handlers[strategy]
        cand = result.decision.selected_candidate
        if not cand:
            raise InformationAcquisitionResolutionError(
                "Acquisition result decision lacks selected_candidate"
            )

        try:
            return handler.execute(result.request, cand)
        except Exception as err:
            raise InformationAcquisitionHandlerError(
                f"Handler execution failed for strategy {strategy.value}: {err}"
            ) from err
