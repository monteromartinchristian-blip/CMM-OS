"""Phase 10.29 — Life Plan Domain Operations.

Ten declarative life plan operations built on the shared ``DomainOperationDefinition`` contract:
- life_plan.build_timeline
- life_plan.compare_scenarios
- life_plan.review_goals
- life_plan.detect_dependencies
- life_plan.identify_risks
- life_plan.update_plan
- life_plan.create_milestones
- life_plan.generate_periodic_review
- life_plan.evaluate_feasibility
- life_plan.track_decisions

All operations produce proposals or analytical results. No operation directly mutates external
calendars, writes directly to long-term memory without proposal/binding chains, makes payments,
or autonomously converts scenarios or preferences into commitments.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.domains.enums import DomainOperationType
from cmm.domains.life_plan.catalog import (
    CANONICAL_LIFE_PLAN_OPERATION_IDS,
)
from cmm.domains.life_plan.rules import (
    evaluate_decision_status,
    evaluate_goal_dependencies,
    evaluate_long_term_temporal,
    evaluate_resource_constraints,
    evaluate_scenario_consistency,
)
from cmm.domains.operation_contracts import DomainOperationDefinition

_OPERATION_TYPES: dict[str, DomainOperationType] = {
    "life_plan.build_timeline": DomainOperationType.PLANNING,
    "life_plan.compare_scenarios": DomainOperationType.ANALYSIS,
    "life_plan.review_goals": DomainOperationType.ANALYSIS,
    "life_plan.detect_dependencies": DomainOperationType.ANALYSIS,
    "life_plan.identify_risks": DomainOperationType.ANALYSIS,
    "life_plan.update_plan": DomainOperationType.PLANNING,
    "life_plan.create_milestones": DomainOperationType.PLANNING,
    "life_plan.generate_periodic_review": DomainOperationType.ANALYSIS,
    "life_plan.evaluate_feasibility": DomainOperationType.ANALYSIS,
    "life_plan.track_decisions": DomainOperationType.ANALYSIS,
}

_REQUIRED_RESOURCES: dict[str, tuple[str, ...]] = {
    "life_plan.build_timeline": ("life_plan.resource.life_plan", "life_plan.resource.calendar_event"),
    "life_plan.compare_scenarios": ("life_plan.resource.life_plan", "life_plan.resource.decision"),
    "life_plan.review_goals": ("life_plan.resource.goal", "life_plan.resource.life_plan"),
    "life_plan.detect_dependencies": ("life_plan.resource.goal", "life_plan.resource.life_plan"),
    "life_plan.identify_risks": ("life_plan.resource.life_plan", "life_plan.resource.financial_plan"),
    "life_plan.update_plan": ("life_plan.resource.life_plan", "life_plan.resource.goal"),
    "life_plan.create_milestones": ("life_plan.resource.life_plan", "life_plan.resource.goal"),
    "life_plan.generate_periodic_review": ("life_plan.resource.life_plan", "life_plan.resource.decision"),
    "life_plan.evaluate_feasibility": ("life_plan.resource.financial_plan", "life_plan.resource.life_plan"),
    "life_plan.track_decisions": ("life_plan.resource.decision", "life_plan.resource.life_plan"),
}

_INPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    op_id: {
        "type": "object",
        "properties": {
            "parameters": {"type": "object"},
        },
    }
    for op_id in CANONICAL_LIFE_PLAN_OPERATION_IDS
}

_OUTPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    op_id: {
        "type": "object",
        "properties": {
            "status": {"type": "string"},
            "is_proposal": {"type": "boolean"},
            "timestamp": {"type": "string"},
        },
        "required": ["status", "is_proposal"],
    }
    for op_id in CANONICAL_LIFE_PLAN_OPERATION_IDS
}


def build_life_plan_operation_definitions() -> tuple[DomainOperationDefinition, ...]:
    """Build all ten canonical Life Plan Domain operation definitions deterministically."""
    result = []
    for op_id in CANONICAL_LIFE_PLAN_OPERATION_IDS:
        op_name = op_id.split(".", 1)[1].replace("_", " ").title()
        result.append(
            DomainOperationDefinition(
                operation_id=op_id,
                domain_id="domain:life-plan",
                version="1.0.0",
                name=op_name,
                description=f"Life Plan reasoning operation for {op_id}.",
                operation_type=_OPERATION_TYPES[op_id],
                risk_level=PolicyRiskLevel.LOW,
                required_resources=_REQUIRED_RESOURCES[op_id],
                input_schema=_INPUT_SCHEMAS[op_id],
                output_schema=_OUTPUT_SCHEMAS[op_id],
                metadata={
                    "phase": "10.29",
                    "proposal_only": True,
                    "no_external_mutation": True,
                },
            )
        )
    return tuple(result)


# ── Operational Result Helpers ────────────────────────────────────────────────


def build_timeline_result(
    *,
    milestones: list[dict[str, Any]] | None = None,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build timeline proposal preserving temporal uncertainties and order."""
    ms = list(milestones or [])
    ev = list(events or [])
    temp_res = evaluate_long_term_temporal(milestones=ms, timeline_events=ev)

    return {
        "status": "completed",
        "is_proposal": True,
        "timeline": {
            "milestones": ms,
            "events": ev,
            "uncertain_milestones": temp_res.get("uncertain_milestones", []),
            "ordering_valid": temp_res.get("ordering_valid", True),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def compare_scenarios_result(
    *,
    scenarios: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compare scenarios across viability and assumptions without picking or committing."""
    scen_list = list(scenarios or [])
    evaluations: list[dict[str, Any]] = []

    for sc in scen_list:
        sid = sc.get("id", "unnamed")
        assump = sc.get("assumptions")
        milestones = sc.get("milestones")
        contra = sc.get("contradictions")
        c_res = evaluate_scenario_consistency(
            scenario_id=sid,
            assumptions=assump,
            milestones=milestones,
            contradictions=contra,
        )
        evaluations.append({
            "scenario_id": sid,
            "consistent": c_res["consistent"],
            "status": c_res["status"],
            "conflicts": c_res["conflicts"],
            "uncertainties": c_res["uncertainties"],
        })

    return {
        "status": "completed",
        "is_proposal": True,
        "is_decision": False,
        "is_commitment": False,
        "scenarios_evaluated": evaluations,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def review_goals_result(
    *,
    goals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Review current goals catalog and statuses."""
    g_list = list(goals or [])
    return {
        "status": "completed",
        "is_proposal": True,
        "goals_count": len(g_list),
        "goals": g_list,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def detect_dependencies_result(
    *,
    dependencies: dict[str, list[str]] | None = None,
    soft_dependencies: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Detect and validate dependencies between goals and milestones."""
    res = evaluate_goal_dependencies(
        dependencies=dependencies,
        soft_dependencies=soft_dependencies,
    )
    return {
        "status": "completed",
        "is_proposal": True,
        "valid": res["valid"],
        "has_cycles": res["has_cycles"],
        "cycles": res["cycles"],
        "prerequisites": res["prerequisites"],
        "soft_dependencies": res["soft_dependencies"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def identify_risks_result(
    *,
    risks: list[dict[str, Any]] | None = None,
    constraints: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Identify long-term planning risks and constraints."""
    r_list = list(risks or [])
    c_list = list(constraints or [])
    return {
        "status": "completed",
        "is_proposal": True,
        "risks": r_list,
        "constraints": c_list,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def update_plan_result(
    *,
    plan_id: str = "main_plan",
    updates: dict[str, Any] | None = None,
    confirmation_evidence: Any = None,
) -> dict[str, Any]:
    """Propose plan updates without silent persistence or unconfirmed promotions."""
    upd = dict(updates or {})
    curr = upd.get("current_status")
    prop = upd.get("proposed_status")

    if curr and prop:
        dec_eval = evaluate_decision_status(
            curr,
            prop,
            confirmation_evidence=confirmation_evidence,
            is_closed=upd.get("is_closed", False),
            has_new_evidence=bool(confirmation_evidence),
            new_evidence=confirmation_evidence,
        )
        if not dec_eval["allowed"]:
            return {
                "status": "update_pending_confirmation",
                "is_proposal": True,
                "plan_id": plan_id,
                "reason": dec_eval["reason"],
                "updates": upd,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    return {
        "status": "proposed_update",
        "is_proposal": True,
        "plan_id": plan_id,
        "updates": upd,
        "confirmation_evidence": confirmation_evidence,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def create_milestones_result(
    *,
    milestones: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create milestone definitions proposal."""
    ms = list(milestones or [])
    temp_res = evaluate_long_term_temporal(milestones=ms)
    return {
        "status": "created",
        "is_proposal": True,
        "milestones": ms,
        "ordering_valid": temp_res.get("ordering_valid", True),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def generate_periodic_review_result(
    *,
    period: str = "quarterly",
    goals: list[dict[str, Any]] | None = None,
    plan_drift: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate periodic review proposal for goals and milestones."""
    return {
        "status": "completed",
        "is_proposal": True,
        "period": period,
        "goals_reviewed": len(goals or []),
        "plan_drift": plan_drift or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def evaluate_feasibility_result(
    *,
    time: dict[str, Any] | None = None,
    money: dict[str, Any] | None = None,
    energy: dict[str, Any] | None = None,
    available_capacity: dict[str, Any] | None = None,
    cross_domain_impact: Any = None,
) -> dict[str, Any]:
    """Evaluate plan feasibility against resources and authorized cross-domain impacts."""
    res_eval = evaluate_resource_constraints(
        time=time,
        money=money,
        energy=energy,
        available_capacity=available_capacity,
    )
    return {
        "status": "evaluated",
        "is_proposal": True,
        "feasibility": res_eval["status"],
        "resource_evaluation": res_eval,
        "cross_domain_impact_considered": cross_domain_impact is not None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def track_decisions_result(
    *,
    decision_id: str,
    current_status: str,
    proposed_status: str,
    confirmation_evidence: Any = None,
    is_closed: bool = False,
    has_new_evidence: bool = False,
    new_evidence: Any = None,
) -> dict[str, Any]:
    """Track decision state transition under explicit lattice rules."""
    dec_eval = evaluate_decision_status(
        current_status=current_status,
        proposed_status=proposed_status,
        confirmation_evidence=confirmation_evidence,
        is_closed=is_closed,
        has_new_evidence=has_new_evidence,
        new_evidence=new_evidence,
    )
    return {
        "status": "tracked" if dec_eval["allowed"] else "transition_denied",
        "is_proposal": True,
        "decision_id": decision_id,
        "evaluation": dec_eval,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


__all__ = [
    "build_life_plan_operation_definitions",
    "build_timeline_result",
    "compare_scenarios_result",
    "create_milestones_result",
    "detect_dependencies_result",
    "evaluate_feasibility_result",
    "generate_periodic_review_result",
    "identify_risks_result",
    "review_goals_result",
    "track_decisions_result",
    "update_plan_result",
]
