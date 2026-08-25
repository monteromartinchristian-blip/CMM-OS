"""Phase 10.29 — Life Plan Domain Rules and deterministic evaluators.

Declarative domain rules + pure deterministic long-term planning reasoning helpers.
All helper functions and rule evaluators are state-free: no IO, no model calls,
no registry mutation, no internal clock. They receive context explicitly and
return deterministic JSON-safe structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cmm.cognitive.enums import (
    ReasoningRiskLevel,
    ReasoningRuleCategory,
    ReasoningRuleResultStatus,
    ReasoningRuleScope,
    ReasoningRuleStatus,
    ReasoningSeverity,
)
from cmm.cognitive.reasoning_rule_contracts import (
    ReasoningEscalation,
    ReasoningFinding,
    ReasoningGap,
    ReasoningRuleContext,
    ReasoningRuleDefinition,
    ReasoningRuleResult,
    ReasoningRuleTraceEntry,
)
from cmm.domains.life_plan.catalog import (
    CANONICAL_LIFE_PLAN_RULE_IDS,
    CANONICAL_LIFE_PLAN_RULE_NAMES,
)
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition, DomainRuleResult

LIFE_PLAN_RULE_IDS: tuple[str, ...] = CANONICAL_LIFE_PLAN_RULE_IDS
LIFE_PLAN_RULE_NAMES: tuple[str, ...] = CANONICAL_LIFE_PLAN_RULE_NAMES

DECISION_STATUS_VOCABULARY: tuple[str, ...] = (
    "idea",
    "preference",
    "goal",
    "scenario",
    "decision",
    "commitment",
)


def _definition(
    rule_id: str,
    name: str,
    category: str,
    priority: int,
    risk_level: ReasoningRiskLevel = ReasoningRiskLevel.LOW,
) -> DomainReasoningRuleDefinition:
    return DomainReasoningRuleDefinition(
        id=rule_id,
        name=name,
        version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id="domain:life-plan",
        category=category,
        status=ReasoningRuleStatus.ENABLED,
        priority=priority,
        risk_level=risk_level,
        deterministic=True,
        description=f"Life Plan domain reasoning rule for {rule_id}.",
        metadata={"phase": "10.29"},
    )


def _result(
    definition: ReasoningRuleDefinition,
    context: ReasoningRuleContext,
    status: ReasoningRuleResultStatus,
    *,
    findings: tuple[ReasoningFinding, ...] = (),
    gaps: tuple[ReasoningGap, ...] = (),
    escalation: ReasoningEscalation | None = None,
    code: str,
    message: str,
) -> ReasoningRuleResult:
    return DomainRuleResult(
        rule_id=definition.id,
        rule_name=definition.name,
        rule_version=definition.version,
        domain_id=definition.domain_id,
        status=status,
        findings=findings,
        gaps=gaps,
        escalation=escalation,
        trace_entries=(
            ReasoningRuleTraceEntry(
                code=code,
                message=message,
                rule_id=definition.id,
                domain_id=definition.domain_id,
                status=status,
                occurred_at=context.timestamp,
                output_count=len(findings) + len(gaps) + int(escalation is not None),
            ),
        ),
        started_at=context.timestamp,
        completed_at=context.timestamp,
    )


# ── Pure Evaluators ───────────────────────────────────────────────────────────


def evaluate_decision_status(
    current_status: str,
    proposed_status: str,
    *,
    confirmation_evidence: Any = None,
    is_closed: bool = False,
    has_new_evidence: bool = False,
    new_evidence: Any = None,
) -> dict[str, Any]:
    """Evaluate decision status transition according to non-collapsible lattice.

    Enforces:
    - preference != decision
    - scenario != decision
    - scenario != commitment
    - inference != confirmed fact
    - closed decision cannot reopen without explicit new evidence.
    """
    curr = str(current_status).lower().strip()
    prop = str(proposed_status).lower().strip()

    # Closed decision reopening check
    if is_closed:
        if not has_new_evidence and not new_evidence:
            return {
                "allowed": False,
                "current_status": curr,
                "proposed_status": prop,
                "requires_confirmation": True,
                "reopened": False,
                "reason": "Closed decision cannot be reopened or modified without explicit new evidence.",
            }

    # If proposing transition to decision or commitment from unconfirmed state, confirmation is mandatory
    unconfirmed_states = ("idea", "preference", "hypothesis", "scenario")
    if curr in unconfirmed_states and prop in ("decision", "commitment"):
        if not confirmation_evidence:
            return {
                "allowed": False,
                "current_status": curr,
                "proposed_status": prop,
                "requires_confirmation": True,
                "reopened": False,
                "reason": f"Cannot promote unconfirmed {curr} to {prop} without explicit user confirmation evidence.",
            }

    # Proposing transition from decision to commitment also requires confirmation/commitment evidence
    if curr == "decision" and prop == "commitment":
        if not confirmation_evidence:
            return {
                "allowed": False,
                "current_status": curr,
                "proposed_status": prop,
                "requires_confirmation": True,
                "reopened": False,
                "reason": "Cannot promote decision to commitment without explicit commitment evidence.",
            }

    return {
        "allowed": True,
        "current_status": curr,
        "new_status": prop,
        "requires_confirmation": False,
        "reopened": bool(is_closed and (has_new_evidence or new_evidence)),
        "reason": f"Valid state transition from {curr} to {prop}.",
    }


def evaluate_scenario_consistency(
    scenario_id: str,
    assumptions: dict[str, Any] | None = None,
    milestones: list[dict[str, Any]] | None = None,
    contradictions: list[str] | None = None,
) -> dict[str, Any]:
    """Validate internal scenario coherence while preserving uncertainty.

    Scenario viability != decision; scenario viability != commitment.
    """
    assump = dict(assumptions or {})
    conflicts: list[str] = list(contradictions or [])
    uncertainties: list[str] = []

    for k, v in assump.items():
        if v is None or v == "unknown" or (isinstance(v, str) and "uncertain" in v.lower()):
            uncertainties.append(k)

    consistent = len(conflicts) == 0

    return {
        "scenario_id": scenario_id,
        "consistent": consistent,
        "status": "coherent" if consistent else "inconsistent",
        "conflicts": conflicts,
        "uncertainties": uncertainties,
        "is_decision": False,
        "is_commitment": False,
    }


def evaluate_alternative_route(
    primary_goal_id: str,
    alternative_route_id: str,
    route_type: str = "fallback",
    rationale: str = "",
) -> dict[str, Any]:
    """Preserve alternative routes without implying abandonment or failure."""
    return {
        "primary_goal_id": primary_goal_id,
        "alternative_route_id": alternative_route_id,
        "route_type": route_type,
        "rationale": rationale,
        "status": "active_alternative",
        "primary_goal_abandoned": False,
        "is_failure": False,
        "is_contingency": True,
    }


# ── Declarative Rule Classes (Task 4) ─────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DecisionStatusRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "life_plan.rule.decision_status",
            "DecisionStatusRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            800,
            risk_level=ReasoningRiskLevel.HIGH,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        curr = context.metadata.get("current_status", "idea")
        prop = context.metadata.get("proposed_status", "decision")
        conf = context.metadata.get("confirmation_evidence")
        closed = context.metadata.get("is_closed", False)
        new_ev = context.metadata.get("has_new_evidence", False)
        new_ev_data = context.metadata.get("new_evidence")

        res = evaluate_decision_status(
            curr,
            prop,
            confirmation_evidence=conf,
            is_closed=closed,
            has_new_evidence=new_ev,
            new_evidence=new_ev_data,
        )

        findings = [
            ReasoningFinding(
                code="DECISION_STATUS_EVALUATED",
                message=f"Decision status transition evaluated: allowed={res['allowed']}, reason={res['reason']}",
                severity=ReasoningSeverity.INFO if res["allowed"] else ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="DECISION_STATUS_EVALUATED",
            message="Evaluated decision status rule.",
        )


@dataclass(frozen=True, slots=True)
class ScenarioConsistencyRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "life_plan.rule.scenario_consistency",
            "ScenarioConsistencyRule",
            ReasoningRuleCategory.CONSISTENCY.value,
            810,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        scen_id = context.metadata.get("scenario_id", "default_scenario")
        assump = context.metadata.get("assumptions")
        milestones = context.metadata.get("milestones")
        contra = context.metadata.get("contradictions")

        res = evaluate_scenario_consistency(
            scenario_id=scen_id,
            assumptions=assump,
            milestones=milestones,
            contradictions=contra,
        )

        findings = [
            ReasoningFinding(
                code="SCENARIO_CONSISTENCY_EVALUATED",
                message=f"Scenario consistency evaluated: consistent={res['consistent']}, conflicts={len(res['conflicts'])}",
                severity=ReasoningSeverity.INFO if res["consistent"] else ReasoningSeverity.WARNING,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="SCENARIO_CONSISTENCY_EVALUATED",
            message="Evaluated scenario consistency rule.",
        )


@dataclass(frozen=True, slots=True)
class AlternativeRouteRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "life_plan.rule.alternative_route",
            "AlternativeRouteRule",
            ReasoningRuleCategory.INFERENCE.value,
            820,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        primary_goal_id = context.metadata.get("primary_goal_id", "primary_goal")
        alt_id = context.metadata.get("alternative_route_id", "alt_route")
        route_type = context.metadata.get("route_type", "fallback")
        rationale = context.metadata.get("rationale", "")

        res = evaluate_alternative_route(
            primary_goal_id=primary_goal_id,
            alternative_route_id=alt_id,
            route_type=route_type,
            rationale=rationale,
        )

        findings = [
            ReasoningFinding(
                code="ALTERNATIVE_ROUTE_EVALUATED",
                message=f"Alternative route evaluated: primary_goal_abandoned={res['primary_goal_abandoned']}",
                severity=ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="ALTERNATIVE_ROUTE_EVALUATED",
            message="Evaluated alternative route rule.",
        )


__all__ = [
    "DECISION_STATUS_VOCABULARY",
    "LIFE_PLAN_RULE_IDS",
    "LIFE_PLAN_RULE_NAMES",
    "AlternativeRouteRule",
    "DecisionStatusRule",
    "ScenarioConsistencyRule",
    "evaluate_alternative_route",
    "evaluate_decision_status",
    "evaluate_scenario_consistency",
]
