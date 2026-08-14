"""Phase 10.23 — Opposition Temporal Validity + call-monitoring tests."""

from __future__ import annotations

from cmm.domains.oppositions.rules import (
    classify_opposition_temporal,
    opposition_call_monitoring,
)


def _grounded_fact(**overrides):
    fact = {
        "attribute": "application_deadline",
        "value": "2026-08-31",
        "temporal": "valid",
        "grounded": True,
        "source_reference": "ref-1",
        "decision_critical": True,
    }
    fact.update(overrides)
    return fact


def test_no_call_supplied():
    record = classify_opposition_temporal(fact=None)
    assert record["state"] == "missing"
    assert record["verification_needed"] is False  # non-critical by default


def test_malformed_call_payload():
    record = classify_opposition_temporal(fact=7)
    assert record["state"] == "malformed"


def test_missing_identity():
    record = classify_opposition_temporal(fact=_grounded_fact(source_reference=None))
    assert record["state"] in ("unknown", "undergrounded", "current")


def test_current_grounded_call():
    record = classify_opposition_temporal(fact=_grounded_fact())
    assert record["state"] == "current"
    assert record["current"] is True
    assert record["calendar_not_created"] is True


def test_expired_call():
    record = classify_opposition_temporal(fact=_grounded_fact(temporal="expired"))
    assert record["state"] == "stale"
    assert record["current"] is False


def test_future_call():
    record = classify_opposition_temporal(fact=_grounded_fact(temporal="future"))
    assert record["state"] == "future"


def test_conflicting_call_state_missing_unknown():
    record = classify_opposition_temporal(fact=_grounded_fact(temporal="unknown"))
    assert record["state"] == "unknown"


def test_deadline_bare_value_only_not_confirmed():
    record = classify_opposition_temporal(
        fact={"attribute": "application_deadline", "value": "2026-08-31"}
    )
    # bare date string, not grounded -> not confirmed current deadline
    assert record["confirmed"] is False
    assert record["state"] != "current"


def test_grounded_current_deadline():
    record = classify_opposition_temporal(fact=_grounded_fact())
    assert record["confirmed"] is True


def test_future_deadline():
    record = classify_opposition_temporal(fact=_grounded_fact(temporal="future"))
    assert record["current"] is False


def test_conflicting_uses_state():
    record = classify_opposition_temporal(fact=_grounded_fact(temporal="unknown"))
    assert record["state"] == "unknown"


def test_unknown_ordering_preserved():
    record = classify_opposition_temporal(fact=_grounded_fact(temporal="unknown"))
    assert record["state"] == "unknown"


def test_current_syllabus_unresolved_triggers_verification():
    record = classify_opposition_temporal(
        fact=_grounded_fact(attribute="syllabus", temporal="unknown")
    )
    assert record["verification_needed"] is True


def test_decision_critical_missing_triggers_verification():
    record = classify_opposition_temporal(fact=None, decision_critical=True)
    assert record["verification_needed"] is True


def test_non_critical_gap_stays_explicit_without_blocking():
    record = classify_opposition_temporal(fact=None, decision_critical=False)
    assert record["verification_needed"] is False
    assert record["state"] == "missing"


def test_active_objective_stale_call_emits_monitoring():
    requirement = opposition_call_monitoring(
        objective_active=True, call_state="stale"
    )
    assert requirement["monitoring_needed"] is True
    assert requirement["kind"] == "official_verification_requirement"
    assert requirement["scheduler_started"] is False
    assert requirement["notification_sent"] is False


def test_inactive_objective_no_monitoring():
    requirement = opposition_call_monitoring(
        objective_active=False, call_state="stale"
    )
    assert requirement["monitoring_needed"] is False


def test_current_call_no_monitoring():
    requirement = opposition_call_monitoring(objective_active=True, call_state="current")
    assert requirement["monitoring_needed"] is False


def test_no_calendar_event_created():
    record = classify_opposition_temporal(fact=_grounded_fact())
    assert record["calendar_not_created"] is True


def test_strict_boolean_objective():
    # "true" is not literal True -> not active -> no monitoring
    requirement = opposition_call_monitoring(objective_active="true", call_state="stale")
    assert requirement["monitoring_needed"] is False


def test_conflicting_temporal_state_preserved():
    """A grounded, decision-critical conflicting temporal state must not collapse
    to unknown."""
    record = classify_opposition_temporal(
        fact=_grounded_fact(temporal="conflicting")
    )
    assert record["state"] == "conflicting"
    assert record["current"] is False
    assert record["confirmed"] is False
    assert record["verification_needed"] is True


def test_superseded_temporal_state_preserved():
    """A grounded superseded temporal state must be preserved as superseded, not
    collapsed to unknown, and never made current."""
    record = classify_opposition_temporal(
        fact=_grounded_fact(temporal="superseded")
    )
    assert record["state"] == "superseded"
    assert record["current"] is False
    assert record["confirmed"] is False
