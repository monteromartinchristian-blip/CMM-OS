"""Phase 10.22 — M3: Conditional Verification Trigger (helper/result, not op/rule).

The audit found that conditional official verification risked being added as a
12th operation or an 11th rule.  It must instead be a deterministic helper that
returns a structured result: verification is READ-ONLY and OFFICIAL_ONLY, and
it triggers only when an academic fact is missing, stale, conflicting, or
decision-critical and insufficiently grounded (spec §32).  The helper never
performs I/O, never authorizes an action, and never adds to the canonical
operation/rule counts.
"""

from __future__ import annotations

from cmm.domains.university.rules import conditional_verification_trigger


def test_no_trigger_when_fact_is_grounded():
    """A grounded, current, official fact does not warrant verification."""
    result = conditional_verification_trigger(
        fact_state="confirmed_official",
        decision_critical=False,
    )
    assert result["verification_triggered"] is False
    assert result["read_only"] is True
    assert result["source_class"] == "official_only"


def test_missing_fact_triggers_verification():
    result = conditional_verification_trigger(
        fact_state="unknown",
        decision_critical=False,
    )
    assert result["verification_triggered"] is True
    assert result["reason"] == "missing"


def test_stale_fact_triggers_verification():
    result = conditional_verification_trigger(
        fact_state="stale",
        decision_critical=False,
    )
    assert result["verification_triggered"] is True
    assert result["reason"] == "stale"


def test_conflicting_fact_triggers_verification():
    result = conditional_verification_trigger(
        fact_state="conflicting",
        decision_critical=False,
    )
    assert result["verification_triggered"] is True
    assert result["reason"] == "conflicting"


def test_decision_critical_insufficiently_grounded_triggers():
    """A decision-critical fact that is not confirmed triggers verification."""
    result = conditional_verification_trigger(
        fact_state="reported",
        decision_critical=True,
    )
    assert result["verification_triggered"] is True
    assert result["reason"] == "decision_critical_insufficiently_grounded"


def test_decision_critical_but_confirmed_does_not_trigger():
    result = conditional_verification_trigger(
        fact_state="confirmed_official",
        decision_critical=True,
    )
    assert result["verification_triggered"] is False


def test_verification_is_read_only_and_official_only():
    """Verification is always read-only and OFFICIAL_ONLY when triggered."""
    result = conditional_verification_trigger(
        fact_state="stale",
        decision_critical=False,
    )
    assert result["read_only"] is True
    assert result["source_class"] == "official_only"
    assert result["authorizes_action"] is False


def test_never_authorizes_action():
    """The helper produces a signal, never permission to act."""
    result = conditional_verification_trigger(
        fact_state="missing",
        decision_critical=True,
    )
    assert result["authorizes_action"] is False