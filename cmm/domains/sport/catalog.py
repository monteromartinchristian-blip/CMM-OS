"""Phase 10.28 — Canonical Sport Domain Catalog.

Single source of truth for the structural IDs of the Sport Domain.

Counts:
11 entities, 9 resources, 6 rules, 8 operations, 5 workflows.
"""

from __future__ import annotations

CANONICAL_SPORT_ENTITY_TYPES: tuple[str, ...] = (
    "exercise",
    "workout",
    "training_plan",
    "metric",
    "body_measurement",
    "injury",
    "recovery",
    "sport_goal",
    "equipment",
    "session",
    "performance_record",
)

CANONICAL_SPORT_ENTITY_IDS: tuple[str, ...] = (
    "sport.entity.exercise",
    "sport.entity.workout",
    "sport.entity.training_plan",
    "sport.entity.metric",
    "sport.entity.body_measurement",
    "sport.entity.injury",
    "sport.entity.recovery",
    "sport.entity.sport_goal",
    "sport.entity.equipment",
    "sport.entity.session",
    "sport.entity.performance_record",
)

SPORT_ENTITY_IDS: tuple[str, ...] = CANONICAL_SPORT_ENTITY_IDS

CANONICAL_SPORT_RESOURCE_IDS: tuple[str, ...] = (
    "sport.resource.workout_log",
    "sport.resource.health_resource",
    "sport.resource.body_measurement",
    "sport.resource.training_plan",
    "sport.resource.calendar_event",
    "sport.resource.user_message",
    "sport.resource.note",
    "sport.resource.wearable_data",
    "sport.resource.memory_entry",
)

SPORT_RESOURCE_IDS: tuple[str, ...] = CANONICAL_SPORT_RESOURCE_IDS

SPORT_RESOURCE_KINDS: tuple[str, ...] = tuple(
    resource_id.split(".", 1)[1] for resource_id in CANONICAL_SPORT_RESOURCE_IDS
)

CANONICAL_SPORT_RULE_IDS: tuple[str, ...] = (
    "sport.rule.training_load",
    "sport.rule.progressive_overload",
    "sport.rule.recovery",
    "sport.rule.injury_signal",
    "sport.rule.health_constraint",
    "sport.rule.measurement_trend",
)

SPORT_RULE_IDS: tuple[str, ...] = CANONICAL_SPORT_RULE_IDS

CANONICAL_SPORT_RULE_NAMES: tuple[str, ...] = (
    "TrainingLoadRule",
    "ProgressiveOverloadRule",
    "RecoveryRule",
    "InjurySignalRule",
    "HealthConstraintRule",
    "MeasurementTrendRule",
)

CANONICAL_SPORT_OPERATION_IDS: tuple[str, ...] = (
    "sport.create_training_plan",
    "sport.review_progress",
    "sport.adjust_training_load",
    "sport.generate_workout",
    "sport.track_measurements",
    "sport.review_recovery",
    "sport.identify_risks",
    "sport.schedule_sessions",
)

SPORT_OPERATION_IDS: tuple[str, ...] = CANONICAL_SPORT_OPERATION_IDS

CANONICAL_SPORT_WORKFLOW_IDS: tuple[str, ...] = (
    "sport.training_plan_setup",
    "sport.weekly_training_review",
    "sport.recovery_review",
    "sport.progress_review",
    "sport.return_to_training_with_health_constraints",
)

SPORT_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_SPORT_WORKFLOW_IDS

__all__ = [
    "CANONICAL_SPORT_ENTITY_IDS",
    "CANONICAL_SPORT_ENTITY_TYPES",
    "CANONICAL_SPORT_OPERATION_IDS",
    "CANONICAL_SPORT_RESOURCE_IDS",
    "CANONICAL_SPORT_RULE_IDS",
    "CANONICAL_SPORT_RULE_NAMES",
    "CANONICAL_SPORT_WORKFLOW_IDS",
    "SPORT_ENTITY_IDS",
    "SPORT_OPERATION_IDS",
    "SPORT_RESOURCE_IDS",
    "SPORT_RESOURCE_KINDS",
    "SPORT_RULE_IDS",
    "SPORT_WORKFLOW_IDS",
]
