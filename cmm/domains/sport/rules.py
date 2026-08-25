"""Phase 10.28 — Sport Domain Rules and deterministic evaluators.

Declarative domain rules + pure deterministic training/recovery reasoning helpers.
All helper functions and rule evaluators are state-free: no IO, no model calls,
no registry mutation, no internal clock. They receive context explicitly and
return deterministic JSON-safe structures.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
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
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition, DomainRuleResult
from cmm.domains.sport.catalog import (
    CANONICAL_SPORT_RULE_IDS,
    CANONICAL_SPORT_RULE_NAMES,
)

SPORT_RULE_IDS: tuple[str, ...] = CANONICAL_SPORT_RULE_IDS
SPORT_RULE_NAMES: tuple[str, ...] = CANONICAL_SPORT_RULE_NAMES


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
        domain_id="domain:sport",
        category=category,
        status=ReasoningRuleStatus.ENABLED,
        priority=priority,
        risk_level=risk_level,
        deterministic=True,
        description=f"Sport domain reasoning rule for {rule_id}.",
        metadata={"phase": "10.28"},
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


def evaluate_training_load(
    volume: Any = None,
    intensity: Any = None,
    frequency: Any = None,
) -> dict[str, Any]:
    """Evaluate training load while keeping volume, intensity, frequency distinct."""
    if volume is None or intensity is None or frequency is None:
        return {
            "status": "unknown",
            "load_value": None,
            "components": {
                "volume": volume,
                "intensity": intensity,
                "frequency": frequency,
            },
        }

    # Reject boolean as number
    if (
        isinstance(volume, bool)
        or isinstance(intensity, bool)
        or isinstance(frequency, bool)
    ):
        return {
            "status": "invalid_evidence",
            "load_value": None,
            "components": {"volume": None, "intensity": None, "frequency": None},
        }

    try:
        vol = float(volume)
        inte = float(intensity)
        freq = float(frequency)
    except (ValueError, TypeError):
        return {
            "status": "invalid_evidence",
            "load_value": None,
            "components": {"volume": None, "intensity": None, "frequency": None},
        }

    if (
        math.isnan(vol)
        or math.isinf(vol)
        or math.isnan(inte)
        or math.isinf(inte)
        or math.isnan(freq)
        or math.isinf(freq)
    ):
        return {
            "status": "invalid_evidence",
            "load_value": None,
            "components": {"volume": None, "intensity": None, "frequency": None},
        }

    if vol < 0 or inte < 0 or freq < 0:
        return {
            "status": "invalid_evidence",
            "load_value": None,
            "components": {"volume": None, "intensity": None, "frequency": None},
        }

    load_val = vol * inte * freq
    return {
        "status": "evaluated",
        "load_value": load_val,
        "components": {"volume": vol, "intensity": inte, "frequency": freq},
    }


def evaluate_progressive_overload(
    baseline_load: Any = None,
    proposed_load: Any = None,
    threshold_percentage: Any = None,
) -> dict[str, Any]:
    """Compare baseline and proposed load without inventing universal 10% rule."""
    if baseline_load is None or proposed_load is None:
        return {
            "status": "unknown",
            "certainty": False,
            "rationale": "Missing load baseline or proposal",
        }

    if isinstance(baseline_load, bool) or isinstance(proposed_load, bool):
        return {
            "status": "invalid_evidence",
            "certainty": False,
            "rationale": "Invalid load data types",
        }

    try:
        base = float(baseline_load)
        prop = float(proposed_load)
    except (ValueError, TypeError):
        return {
            "status": "invalid_evidence",
            "certainty": False,
            "rationale": "Invalid load numbers",
        }

    if not math.isfinite(base) or not math.isfinite(prop):
        return {
            "status": "invalid_evidence",
            "certainty": False,
            "rationale": "Non-finite load numbers",
        }

    if base <= 0:
        return {
            "status": "unknown",
            "certainty": False,
            "rationale": "Non-positive baseline load",
        }

    inc_pct = ((prop - base) / base) * 100.0

    if threshold_percentage is None:
        return {
            "status": "proposal",
            "certainty": False,
            "baseline_load": base,
            "proposed_load": prop,
            "increase_percentage": inc_pct,
            "rationale": "No explicit overload threshold configured",
        }

    if isinstance(threshold_percentage, bool):
        return {
            "status": "invalid_evidence",
            "certainty": False,
            "rationale": "Invalid threshold data type",
        }

    try:
        thresh = float(threshold_percentage)
    except (ValueError, TypeError):
        return {
            "status": "invalid_evidence",
            "certainty": False,
            "rationale": "Invalid threshold configuration",
        }

    if not math.isfinite(thresh) or thresh < 0:
        return {
            "status": "invalid_evidence",
            "certainty": False,
            "rationale": "Invalid non-finite or negative threshold",
        }

    if inc_pct > thresh:
        return {
            "status": "exceeds_threshold",
            "certainty": True,
            "baseline_load": base,
            "proposed_load": prop,
            "increase_percentage": inc_pct,
            "threshold_percentage": thresh,
            "rationale": f"Proposed increase of {inc_pct:.1f}% exceeds threshold of {thresh:.1f}%",
        }

    return {
        "status": "accepted",
        "certainty": True,
        "baseline_load": base,
        "proposed_load": prop,
        "increase_percentage": inc_pct,
        "threshold_percentage": thresh,
        "rationale": f"Proposed increase of {inc_pct:.1f}% is within threshold of {thresh:.1f}%",
    }


def evaluate_recovery(
    rest_hours: Any = None,
    fatigue_score: Any = None,
    pain_score: Any = None,
    workload_score: Any = None,
) -> dict[str, Any]:
    """Relate rest, fatigue, pain, workload to time-bound readiness."""
    if rest_hours is None or fatigue_score is None:
        return {
            "readiness_state": "unknown",
            "is_mutable": True,
            "scores": {
                "rest_hours": rest_hours,
                "fatigue_score": fatigue_score,
                "pain_score": pain_score,
                "workload_score": workload_score,
            },
        }

    try:
        rest = float(rest_hours)
        fatigue = int(fatigue_score)
        pain = int(pain_score) if pain_score is not None else 0
        workload = int(workload_score) if workload_score is not None else 5
    except (ValueError, TypeError):
        return {
            "readiness_state": "unknown",
            "is_mutable": True,
            "scores": {},
        }

    if pain >= 7 or fatigue >= 8 or rest < 5.0:
        state = "hold"
    elif pain >= 4 or fatigue >= 6 or rest < 6.5:
        state = "limited"
    else:
        state = "ready"

    return {
        "readiness_state": state,
        "is_mutable": True,
        "scores": {
            "rest_hours": rest,
            "fatigue_score": fatigue,
            "pain_score": pain,
            "workload_score": workload,
        },
    }


def evaluate_injury_signal(
    pain_score: int = 0,
    pain_location: str | None = None,
    performance_drop: float = 0.0,
    wearable_anomaly: bool = False,
    load_spike: bool = False,
    fatigue_score: int = 0,
) -> dict[str, Any]:
    """Identify athletic risk signals without diagnosing an injury."""
    if pain_score >= 7 or fatigue_score >= 8 or (pain_score >= 5 and load_spike):
        action = "stop_and_check"
    elif (
        pain_score >= 4
        or performance_drop >= 0.2
        or wearable_anomaly
        or load_spike
        or fatigue_score >= 6
    ):
        action = "reduce_load"
    else:
        action = "continue"

    return {
        "action": action,
        "is_diagnosis": False,
        "signal_details": {
            "pain_score": pain_score,
            "pain_location": pain_location,
            "performance_drop": performance_drop,
            "wearable_anomaly": wearable_anomaly,
            "load_spike": load_spike,
            "fatigue_score": fatigue_score,
        },
    }


def evaluate_health_constraint(
    projection: Any = None,
    is_authorized: bool = False,
    is_current: bool = True,
) -> dict[str, Any]:
    """Incorporate authorized Health functional constraint into Sport reasoning."""
    if not is_authorized or not is_current:
        return {
            "applied": False,
            "reason": "unauthorized_or_expired",
            "constraint": None,
        }

    if not isinstance(projection, dict):
        return {
            "applied": False,
            "reason": "invalid_projection",
            "constraint": None,
        }

    # Reject clinical dossier or raw health memory
    if (
        "full_clinical_history" in projection
        or "medication_list" in projection
        or "raw_health_memory" in projection
    ):
        return {
            "applied": False,
            "reason": "rejected_unauthorized_dossier",
            "constraint": None,
        }

    allowed_fields = (
        "constraint_id",
        "status",
        "effective_from",
        "effective_until",
        "activity_limits",
        "load_limits",
        "movement_limits",
        "return_to_activity_conditions",
        "source_reference",
        "provenance",
        "authorization_reference",
    )

    minimized_constraint = {k: projection[k] for k in allowed_fields if k in projection}

    return {
        "applied": True,
        "constraint": minimized_constraint,
        "applied_fields": tuple(minimized_constraint.keys()),
        "treatment_modification_allowed": False,
        "provenance": {
            "authorization_reference": minimized_constraint.get(
                "authorization_reference"
            ),
            "source_reference": minimized_constraint.get("source_reference"),
        },
    }


def evaluate_measurement_trend(
    observations: Any = None,
    metric: str = "metric",
) -> dict[str, Any]:
    """Inferred trend from comparable ordered body/performance measurements."""
    if not isinstance(observations, (Sequence, list, tuple)) or len(observations) < 2:
        return {
            "status": "insufficient_data",
            "metric": metric,
            "observations_count": len(observations)
            if isinstance(observations, (Sequence, list, tuple))
            else 0,
        }

    parsed_obs: list[tuple[datetime, dict[str, Any]]] = []
    units: set[str] = set()
    methods: set[str] = set()

    for obs in observations:
        if not isinstance(obs, dict):
            return {"status": "invalid_evidence", "metric": metric}

        obs_metric = obs.get("metric")
        if obs_metric is not None and obs_metric != metric:
            return {"status": "invalid_evidence", "metric": metric}

        ts_val = obs.get("timestamp")
        if not ts_val or not isinstance(ts_val, str):
            return {"status": "invalid_evidence", "metric": metric}

        try:
            ts_str = ts_val.replace("Z", "+00:00") if ts_val.endswith("Z") else ts_val
            dt = datetime.fromisoformat(ts_str)
        except (ValueError, TypeError):
            return {"status": "invalid_evidence", "metric": metric}

        val = obs.get("value")
        if isinstance(val, bool) or val is None:
            return {"status": "invalid_evidence", "metric": metric}
        try:
            val_f = float(val)
            if not math.isfinite(val_f):
                return {"status": "invalid_evidence", "metric": metric}
        except (ValueError, TypeError):
            return {"status": "invalid_evidence", "metric": metric}

        if "unit" in obs:
            units.add(obs["unit"])
        if "method" in obs:
            methods.add(obs["method"])

        parsed_obs.append((dt, obs))

    if len(units) > 1 or len(methods) > 1:
        return {
            "status": "incomparable_units",
            "metric": metric,
            "units": tuple(units),
            "methods": tuple(methods),
        }

    if len(parsed_obs) < 2:
        return {"status": "insufficient_data", "metric": metric}

    # Deterministically sort observations chronologically by timestamp
    parsed_obs.sort(key=lambda item: item[0])
    sorted_obs = [item[1] for item in parsed_obs]

    # Detect punctual outliers (> 10% deviation from mean)
    values = [float(o["value"]) for o in sorted_obs]
    mean_val = sum(values) / len(values)
    outliers = [
        o for o in sorted_obs if abs(float(o["value"]) - mean_val) > mean_val * 0.10
    ]

    # Calculate trend direction based on chronologically sorted observations
    first_val = values[0]
    last_val = values[-1]
    diff = last_val - first_val
    if abs(diff) < 0.01 * first_val if first_val != 0 else abs(diff) < 1e-6:
        direction = "stable"
    elif diff > 0:
        direction = "increasing"
    else:
        direction = "decreasing"

    return {
        "status": "evaluated",
        "metric": metric,
        "direction": direction,
        "observations_count": len(sorted_obs),
        "outliers": outliers,
    }


# ── Declarative Rule Classes ──────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class TrainingLoadRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "sport.rule.training_load",
            "TrainingLoadRule",
            ReasoningRuleCategory.INFERENCE.value,
            800,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        vol = context.metadata.get("volume")
        inte = context.metadata.get("intensity")
        freq = context.metadata.get("frequency")
        res = evaluate_training_load(volume=vol, intensity=inte, frequency=freq)

        findings = [
            ReasoningFinding(
                code="TRAINING_LOAD_EVALUATED",
                message=f"Training load evaluated: status={res['status']}, load_value={res.get('load_value')}",
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
            code="TRAINING_LOAD_EVALUATED",
            message="Evaluated training load rule.",
        )


@dataclass(frozen=True, slots=True)
class ProgressiveOverloadRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "sport.rule.progressive_overload",
            "ProgressiveOverloadRule",
            ReasoningRuleCategory.SAFETY.value,
            810,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        base = context.metadata.get("baseline_load")
        prop = context.metadata.get("proposed_load")
        thresh = context.metadata.get("threshold_percentage")
        res = evaluate_progressive_overload(
            baseline_load=base, proposed_load=prop, threshold_percentage=thresh
        )

        findings = [
            ReasoningFinding(
                code="PROGRESSIVE_OVERLOAD_EVALUATED",
                message=f"Progressive overload status={res['status']}: {res.get('rationale')}",
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
            code="PROGRESSIVE_OVERLOAD_EVALUATED",
            message="Evaluated progressive overload rule.",
        )


@dataclass(frozen=True, slots=True)
class RecoveryRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "sport.rule.recovery",
            "RecoveryRule",
            ReasoningRuleCategory.INFERENCE.value,
            820,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        rest = context.metadata.get("rest_hours")
        fatigue = context.metadata.get("fatigue_score")
        pain = context.metadata.get("pain_score")
        workload = context.metadata.get("workload_score")
        res = evaluate_recovery(
            rest_hours=rest,
            fatigue_score=fatigue,
            pain_score=pain,
            workload_score=workload,
        )

        findings = [
            ReasoningFinding(
                code="RECOVERY_EVALUATED",
                message=f"Recovery readiness_state={res['readiness_state']}",
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
            code="RECOVERY_EVALUATED",
            message="Evaluated recovery rule.",
        )


@dataclass(frozen=True, slots=True)
class InjurySignalRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "sport.rule.injury_signal",
            "InjurySignalRule",
            ReasoningRuleCategory.SAFETY.value,
            830,
            risk_level=ReasoningRiskLevel.HIGH,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        pain = context.metadata.get("pain_score", 0)
        loc = context.metadata.get("pain_location")
        drop = context.metadata.get("performance_drop", 0.0)
        anomaly = context.metadata.get("wearable_anomaly", False)
        spike = context.metadata.get("load_spike", False)
        fatigue = context.metadata.get("fatigue_score", 0)

        res = evaluate_injury_signal(
            pain_score=pain,
            pain_location=loc,
            performance_drop=drop,
            wearable_anomaly=anomaly,
            load_spike=spike,
            fatigue_score=fatigue,
        )

        findings = [
            ReasoningFinding(
                code="INJURY_SIGNAL_DETECTED",
                message=f"Injury signal evaluated action={res['action']}, is_diagnosis={res['is_diagnosis']}",
                severity=ReasoningSeverity.WARNING
                if res["action"] != "continue"
                else ReasoningSeverity.INFO,
                rule_id=self.definition.id,
                domain_id=self.definition.domain_id,
            )
        ]
        return _result(
            self.definition,
            context,
            ReasoningRuleResultStatus.APPLIED,
            findings=tuple(findings),
            code="INJURY_SIGNAL_EVALUATED",
            message="Evaluated injury signal rule.",
        )


@dataclass(frozen=True, slots=True)
class HealthConstraintRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "sport.rule.health_constraint",
            "HealthConstraintRule",
            ReasoningRuleCategory.SAFETY.value,
            840,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        proj = context.metadata.get("health_constraint")
        auth = context.metadata.get("is_authorized", False)
        curr = context.metadata.get("is_current", True)

        res = evaluate_health_constraint(
            projection=proj, is_authorized=auth, is_current=curr
        )

        findings = [
            ReasoningFinding(
                code="HEALTH_CONSTRAINT_EVALUATED",
                message=f"Health constraint applied={res['applied']}",
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
            code="HEALTH_CONSTRAINT_EVALUATED",
            message="Evaluated health constraint rule.",
        )


@dataclass(frozen=True, slots=True)
class MeasurementTrendRule:
    definition: DomainReasoningRuleDefinition = field(
        default_factory=lambda: _definition(
            "sport.rule.measurement_trend",
            "MeasurementTrendRule",
            ReasoningRuleCategory.INFERENCE.value,
            850,
        )
    )

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult:
        obs = context.metadata.get("observations")
        metric = context.metadata.get("metric", "metric")

        res = evaluate_measurement_trend(observations=obs, metric=metric)

        findings = [
            ReasoningFinding(
                code="MEASUREMENT_TREND_EVALUATED",
                message=f"Measurement trend status={res['status']}",
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
            code="MEASUREMENT_TREND_EVALUATED",
            message="Evaluated measurement trend rule.",
        )


# ── Build Function ────────────────────────────────────────────────────────────


def build_sport_rules() -> tuple[Any, ...]:
    """Build the six Sport Domain rules deterministically in canonical order."""
    by_id = {
        "sport.rule.training_load": TrainingLoadRule(),
        "sport.rule.progressive_overload": ProgressiveOverloadRule(),
        "sport.rule.recovery": RecoveryRule(),
        "sport.rule.injury_signal": InjurySignalRule(),
        "sport.rule.health_constraint": HealthConstraintRule(),
        "sport.rule.measurement_trend": MeasurementTrendRule(),
    }
    return tuple(by_id[rule_id] for rule_id in CANONICAL_SPORT_RULE_IDS)


__all__ = [
    "SPORT_RULE_IDS",
    "SPORT_RULE_NAMES",
    "HealthConstraintRule",
    "InjurySignalRule",
    "MeasurementTrendRule",
    "ProgressiveOverloadRule",
    "RecoveryRule",
    "TrainingLoadRule",
    "build_sport_rules",
    "evaluate_health_constraint",
    "evaluate_injury_signal",
    "evaluate_measurement_trend",
    "evaluate_progressive_overload",
    "evaluate_recovery",
    "evaluate_training_load",
]
