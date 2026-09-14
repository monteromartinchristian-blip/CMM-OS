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

from datetime import datetime, timezone

import pytest

from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.university import build_university_rules
from cmm.domains.university.rules import conditional_verification_trigger

T = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _deadline_result(deadline, **extra):
    rule = {r.definition.id: r for r in build_university_rules()}[
        "university.academic_deadline"
    ]
    context = ReasoningRuleContext(
        reasoning_id="verification-production",
        timestamp=T,
        active_domains=("domain:university",),
        primary_domain="domain:university",
        metadata={"deadline": deadline, **extra},
    )
    return rule.evaluate(context)


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


def test_deadline_rule_missing_critical_value_emits_shared_verification_need():
    result = _deadline_result({"critical": True})
    finding = result.findings[0]
    need = finding.metadata["verification_need"]
    assert finding.code == "DEADLINE_VERIFICATION_NEEDED"
    assert need["needed"] is True
    assert need["reason"] == "missing"
    assert need["attribute"] == "deadline"
    assert need["source_class"] == "official_only"
    assert need["read_only"] is True
    assert need["action_authorized"] is False


def test_deadline_rule_missing_critical_fact_emits_shared_verification_need():
    result = _deadline_result(None, deadline_required=True)
    finding = result.findings[0]
    assert finding.code == "DEADLINE_VERIFICATION_NEEDED"
    assert finding.metadata["verification_need"]["needed"] is True


def test_deadline_rule_stale_value_emits_shared_verification_need():
    result = _deadline_result(
        {
            "value": "2026-07-01",
            "source_class": "official_publication",
            "provenance": "grounded",
            "temporal": "expired",
            "critical": True,
        }
    )
    need = result.findings[0].metadata["verification_need"]
    assert need["needed"] is True
    assert need["reason"] == "stale"


def test_deadline_rule_confirmed_value_has_no_verification_need():
    result = _deadline_result(
        {
            "value": "2026-09-15",
            "source_class": "official_publication",
            "provenance": "grounded",
            "temporal": "valid",
        }
    )
    need = result.findings[0].metadata["verification_need"]
    assert need["needed"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# V11-B2: strict boolean semantics on public Verification paths
#
# ``decision_critical`` is a strict runtime boolean.  Truthy strings ("false")
# must NOT be treated as decision-critical.  Only literal True counts;
# literal False does not; anything else is malformed/unknown.
# ═══════════════════════════════════════════════════════════════════════════════


def test_v11_b2_verification_decision_critical_string_false_not_critical():
    """decision_critical='false' must not be interpreted as decision-critical."""
    result = conditional_verification_trigger(
        fact_state="reported",
        decision_critical="false",
    )
    assert result["verification_triggered"] is False
    assert result["needed"] is False


def test_v11_b2_verification_decision_critical_true_triggers():
    """decision_critical=True on reported state triggers verification."""
    result = conditional_verification_trigger(
        fact_state="reported",
        decision_critical=True,
    )
    assert result["verification_triggered"] is True
    assert result["reason"] == "decision_critical_insufficiently_grounded"


class _V18StringLike:
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value


def test_v18_closure_verification_fact_state_is_not_string_coerced():
    result = conditional_verification_trigger(
        fact_state=_V18StringLike("confirmed_official"),
    )
    assert result["fact_state"] == "unknown"
    assert result["verification_triggered"] is True
    assert result["needed"] is True


@pytest.mark.parametrize("field", ("attribute", "scope"))
def test_v18_closure_verification_semantic_identity_is_strict(field):
    kwargs = {"fact_state": "missing", field: ["course:A"]}
    result = conditional_verification_trigger(**kwargs)
    assert result[field] is None
    assert result["verification_triggered"] is True
