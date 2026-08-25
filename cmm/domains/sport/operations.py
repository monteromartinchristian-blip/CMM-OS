"""Phase 10.28 — Sport Domain Operations.

Eight declarative sport operations built on the shared ``DomainOperationDefinition`` contract:
- sport.create_training_plan
- sport.review_progress
- sport.adjust_training_load
- sport.generate_workout
- sport.track_measurements
- sport.review_recovery
- sport.identify_risks
- sport.schedule_sessions

All operations produce proposals or analytical results. No operation directly mutates external
calendars, writes directly to long-term memory without proposal/binding chains, or provides
medical diagnoses/prescriptions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cmm.agent_runtime.enums import PolicyRiskLevel
from cmm.domains.enums import DomainOperationType
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.sport.catalog import (
    CANONICAL_SPORT_OPERATION_IDS,
)
from cmm.domains.sport.rules import (
    evaluate_injury_signal,
    evaluate_recovery,
)

_OPERATION_TYPES: dict[str, DomainOperationType] = {
    "sport.create_training_plan": DomainOperationType.PLANNING,
    "sport.review_progress": DomainOperationType.ANALYSIS,
    "sport.adjust_training_load": DomainOperationType.PLANNING,
    "sport.generate_workout": DomainOperationType.PREPARATION,
    "sport.track_measurements": DomainOperationType.PREPARATION,
    "sport.review_recovery": DomainOperationType.ANALYSIS,
    "sport.identify_risks": DomainOperationType.ANALYSIS,
    "sport.schedule_sessions": DomainOperationType.PLANNING,
}

_REQUIRED_RESOURCES: dict[str, tuple[str, ...]] = {
    "sport.create_training_plan": ("sport.resource.training_plan",),
    "sport.review_progress": (
        "sport.resource.workout_log",
        "sport.resource.wearable_data",
    ),
    "sport.adjust_training_load": (
        "sport.resource.training_plan",
        "sport.resource.wearable_data",
    ),
    "sport.generate_workout": ("sport.resource.training_plan",),
    "sport.track_measurements": ("sport.resource.body_measurement",),
    "sport.review_recovery": ("sport.resource.wearable_data", "sport.resource.note"),
    "sport.identify_risks": (
        "sport.resource.workout_log",
        "sport.resource.wearable_data",
    ),
    "sport.schedule_sessions": (
        "sport.resource.calendar_event",
        "sport.resource.training_plan",
    ),
}

_INPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    op_id: {
        "type": "object",
        "properties": {
            "parameters": {"type": "object"},
        },
    }
    for op_id in CANONICAL_SPORT_OPERATION_IDS
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
    for op_id in CANONICAL_SPORT_OPERATION_IDS
}


def build_sport_operation_definitions() -> tuple[DomainOperationDefinition, ...]:
    """Build all eight canonical Sport Domain operation definitions deterministically."""
    result = []
    for op_id in CANONICAL_SPORT_OPERATION_IDS:
        op_name = op_id.split(".", 1)[1].replace("_", " ").title()
        result.append(
            DomainOperationDefinition(
                operation_id=op_id,
                domain_id="domain:sport",
                version="1.0.0",
                name=op_name,
                description=f"Sport reasoning operation for {op_id}.",
                operation_type=_OPERATION_TYPES[op_id],
                risk_level=PolicyRiskLevel.LOW,
                required_resources=_REQUIRED_RESOURCES[op_id],
                input_schema=_INPUT_SCHEMAS[op_id],
                output_schema=_OUTPUT_SCHEMAS[op_id],
                metadata={
                    "phase": "10.28",
                    "proposal_only": True,
                    "no_external_mutation": True,
                },
            )
        )
    return tuple(result)


# ── Operational Result Helpers ────────────────────────────────────────────────


def create_training_plan_result(
    *,
    goal: str = "general_fitness",
    weeks: int = 4,
    level: str = "intermediate",
) -> dict[str, Any]:
    """Create a training plan proposal (not a medical prescription)."""
    week_plans = [
        {"week": i + 1, "focus": f"Week {i + 1} progression", "sessions_count": 3}
        for i in range(weeks)
    ]
    return {
        "status": "completed",
        "is_proposal": True,
        "is_medical_prescription": False,
        "plan": {
            "goal": goal,
            "weeks": week_plans,
            "level": level,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def review_progress_result(
    *,
    completed_workouts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Review progress using comparable evidence, preserving insufficient evidence state."""
    if not completed_workouts:
        return {
            "status": "insufficient_data",
            "is_proposal": True,
            "summary": "Insufficient workout evidence to evaluate progress.",
            "completed_count": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return {
        "status": "completed",
        "is_proposal": True,
        "summary": f"Evaluated progress across {len(completed_workouts)} workout records.",
        "completed_count": len(completed_workouts),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _extract_authorized_health_constraint(
    health_constraint: Any,
) -> dict[str, Any] | None:
    """Extract and validate that a health constraint has current authorization evidence."""
    if not isinstance(health_constraint, dict):
        return None
    if health_constraint.get("applied") is True and isinstance(
        health_constraint.get("constraint"), dict
    ):
        hc = health_constraint["constraint"]
    else:
        hc = health_constraint

    if not isinstance(hc, dict):
        return None

    if hc.get("status") != "active":
        return None
    if not hc.get("authorization_reference"):
        return None

    prohibited = (
        "diagnosis",
        "treatment_plan",
        "clinical_notes",
        "full_clinical_history",
        "medication_list",
        "raw_health_memory",
    )
    if any(k in hc for k in prohibited):
        return None

    return hc


def adjust_training_load_result(
    *,
    current_load: float = 100.0,
    readiness_state: str = "ready",
    health_constraint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Adjust training load taking readiness and Health constraints into account."""
    adjusted = current_load
    constraint_applied = False

    hc = _extract_authorized_health_constraint(health_constraint)
    if hc is not None:
        load_limits = hc.get("load_limits", {})
        if isinstance(load_limits, dict):
            if "reduction_pct" in load_limits:
                red_pct = load_limits["reduction_pct"]
                if not isinstance(red_pct, bool):
                    try:
                        red_f = float(red_pct)
                        if (
                            red_f == red_f
                            and not float("inf") == abs(red_f)
                            and 0.0 <= red_f <= 100.0
                        ):
                            adjusted = current_load * (1.0 - (red_f / 100.0))
                            constraint_applied = True
                    except (ValueError, TypeError):
                        pass
            elif "max_load" in load_limits:
                max_l = load_limits["max_load"]
                if not isinstance(max_l, bool):
                    try:
                        max_f = float(max_l)
                        if (
                            max_f == max_f
                            and not float("inf") == abs(max_f)
                            and max_f >= 0.0
                        ):
                            adjusted = min(adjusted, max_f)
                            constraint_applied = True
                    except (ValueError, TypeError):
                        pass
            elif "max_intensity" in load_limits:
                constraint_applied = True

    if readiness_state in ("limited", "hold") and not constraint_applied:
        adjusted = current_load * 0.8

    status = "load_reduced" if adjusted < current_load else "load_maintained"

    return {
        "status": status,
        "is_proposal": True,
        "original_load": current_load,
        "adjusted_load": adjusted,
        "readiness_state": readiness_state,
        "constraint_applied": constraint_applied,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def generate_workout_result(
    *,
    requested_type: str = "general_workout",
    health_constraint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate a workout proposal without bypassing active blocking constraints."""
    hc = _extract_authorized_health_constraint(health_constraint)
    if hc is not None:
        activity_limits = hc.get("activity_limits", [])
        if "no_high_impact" in activity_limits and "high_intensity" in requested_type:
            return {
                "status": "blocked_by_constraint",
                "is_proposal": True,
                "workout": None,
                "reason": "Requested workout type violates active Health activity limits.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    return {
        "status": "generated",
        "is_proposal": True,
        "workout": {
            "type": requested_type,
            "duration_minutes": 45,
            "exercises": ["Warm-up", "Main Set", "Cool-down"],
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def track_measurements_result(
    *,
    metric: str,
    value: float,
    unit: str,
    timestamp: str,
    source: str = "manual",
) -> dict[str, Any]:
    """Track a body/performance measurement preserving timestamp, unit, and provenance."""
    return {
        "status": "tracked",
        "is_proposal": True,
        "measurement": {
            "metric": metric,
            "value": value,
            "unit": unit,
            "timestamp": timestamp,
            "source": source,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def review_recovery_result(
    *,
    rest_hours: float = 8.0,
    fatigue_score: int = 2,
    pain_score: int = 0,
) -> dict[str, Any]:
    """Review current recovery evidence without freezing prior readiness as identity."""
    res = evaluate_recovery(
        rest_hours=rest_hours,
        fatigue_score=fatigue_score,
        pain_score=pain_score,
    )
    return {
        "status": "completed",
        "is_proposal": True,
        "readiness_state": res["readiness_state"],
        "is_mutable": True,
        "scores": res["scores"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def identify_risks_result(
    *,
    pain_score: int = 0,
    performance_drop: float = 0.0,
    load_spike: bool = False,
) -> dict[str, Any]:
    """Identify athletic risk signals without emitting clinical diagnoses."""
    res = evaluate_injury_signal(
        pain_score=pain_score,
        performance_drop=performance_drop,
        load_spike=load_spike,
    )
    return {
        "status": "completed",
        "is_proposal": True,
        "risk_signal": res["action"],
        "is_diagnosis": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def schedule_sessions_result(
    *,
    sessions: list[dict[str, Any]],
    approval_request_id: str | None = None,
    approval_decision_id: str | None = None,
    approval_decision: Any = None,
    has_approval: bool = False,
) -> dict[str, Any]:
    """Propose session schedules; direct external calendar mutation requires scoped approval evidence."""
    req_id = approval_request_id
    dec_id = approval_decision_id
    is_approved = False

    if approval_decision is not None:
        status_val = (
            approval_decision.status.value
            if hasattr(approval_decision.status, "value")
            else str(approval_decision.status)
        )
        if status_val.lower() == "approved":
            is_approved = True
            req_id = req_id or getattr(approval_decision, "request_id", None)
            dec_id = dec_id or getattr(approval_decision, "id", None)
    elif approval_request_id and approval_decision_id:
        is_approved = True

    if not is_approved or not req_id or not dec_id:
        return {
            "status": "proposal_pending_approval",
            "is_proposal": True,
            "sessions": sessions,
            "external_calendar_mutated": False,
            "approval_required": True,
            "approval_request_id": req_id,
            "approval_decision_id": dec_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return {
        "status": "ready_for_external_execution",
        "is_proposal": True,
        "sessions": sessions,
        "external_calendar_mutated": False,
        "approval_granted": True,
        "approval_request_id": req_id,
        "approval_decision_id": dec_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


__all__ = [
    "adjust_training_load_result",
    "build_sport_operation_definitions",
    "create_training_plan_result",
    "generate_workout_result",
    "identify_risks_result",
    "review_progress_result",
    "review_recovery_result",
    "schedule_sessions_result",
    "track_measurements_result",
]
