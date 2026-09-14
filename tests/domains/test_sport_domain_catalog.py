"""Tests for Phase 10.28 Sport Domain Catalog and Definition."""

from __future__ import annotations

from cmm.domains.sport.catalog import (
    CANONICAL_SPORT_ENTITY_TYPES,
    CANONICAL_SPORT_RULE_NAMES,
    SPORT_ENTITY_IDS,
    SPORT_OPERATION_IDS,
    SPORT_RESOURCE_IDS,
    SPORT_RULE_IDS,
    SPORT_WORKFLOW_IDS,
)
from cmm.domains.sport.definition import (
    build_sport_domain_definition,
)


def test_sport_catalog_exact_counts() -> None:
    assert len(SPORT_ENTITY_IDS) == 11
    assert len(SPORT_RESOURCE_IDS) == 9
    assert len(SPORT_RULE_IDS) == 6
    assert len(SPORT_OPERATION_IDS) == 8
    assert len(SPORT_WORKFLOW_IDS) == 5

    assert len(CANONICAL_SPORT_ENTITY_TYPES) == 11
    assert len(CANONICAL_SPORT_RULE_NAMES) == 6


def test_sport_catalog_exact_ids() -> None:
    assert SPORT_ENTITY_IDS == (
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
    assert SPORT_RESOURCE_IDS == (
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
    assert SPORT_RULE_IDS == (
        "sport.rule.training_load",
        "sport.rule.progressive_overload",
        "sport.rule.recovery",
        "sport.rule.injury_signal",
        "sport.rule.health_constraint",
        "sport.rule.measurement_trend",
    )
    assert SPORT_OPERATION_IDS == (
        "sport.create_training_plan",
        "sport.review_progress",
        "sport.adjust_training_load",
        "sport.generate_workout",
        "sport.track_measurements",
        "sport.review_recovery",
        "sport.identify_risks",
        "sport.schedule_sessions",
    )
    assert SPORT_WORKFLOW_IDS == (
        "sport.training_plan_setup",
        "sport.weekly_training_review",
        "sport.recovery_review",
        "sport.progress_review",
        "sport.return_to_training_with_health_constraints",
    )


def test_sport_domain_identity_contract() -> None:
    definition = build_sport_domain_definition()
    assert str(definition.id) == "domain:sport"
    assert definition.name == "sport"
    assert definition.display_name == "Sport"
    assert definition.version == "1.0.0"
    assert definition.reasoning_profile == "SportProfile"
    assert definition.manifest_id == "manifest:sport:1.0.0"
    assert definition.permissions == ("domain-permission:sport:1.0.0",)
    assert definition.metadata.metadata["phase"] == "10.28"
    assert build_sport_domain_definition().to_dict() == definition.to_dict()
