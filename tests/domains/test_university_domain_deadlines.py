"""Phase 10.22 — B3: Academic Deadlines (grounding and temporal validity).

The audit found the previous implementation merely checked that a date string
existed.  A deadline's epistemic state must be grounded: a recalled deadline is
not confirmed, a caller marking ``confirmed`` without grounding is not
authoritative, stale official sources are stale, and conflicting authoritative
deadlines stay conflicting.  Verification needs arise for missing, stale,
conflicting or decision-critical under-grounded deadlines.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.university import build_university_rules
from cmm.domains.university.rules import classify_deadline_grounding

T = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _deadline(
    *,
    value="2026-09-15",
    source_class="official_publication",
    provenance="grounded",
    temporal="valid",
    source_reference="official-deadline-notice",
    retrieval_date="2026-08-01",
    effective_date="2026-09-15",
    scope=None,
    conflicting=False,
    critical=False,
):
    d = {
        "value": value,
        "source_class": source_class,
        "provenance": provenance,
        "temporal": temporal,
        "source_reference": source_reference,
        "retrieval_date": retrieval_date,
        "effective_date": effective_date,
    }
    if scope is not None:
        d["scope"] = scope
    if conflicting:
        d["conflicting"] = True
    if critical:
        d["critical"] = True
    return d


def _canonical_result(deadline):
    rule = {
        rule.definition.id: rule
        for rule in build_university_rules()
    }["university.academic_deadline"]
    context = ReasoningRuleContext(
        reasoning_id="deadline-production",
        timestamp=T,
        active_domains=("domain:university",),
        primary_domain="domain:university",
        metadata={"deadline": deadline},
    )
    return rule.evaluate(context)


def test_remembered_deadline_is_not_confirmed():
    result = classify_deadline_grounding(
        deadline=_deadline(source_class="personal_note", provenance="remembered")
    )
    assert result["confirmed"] is False
    assert result["state"] == "remembered"


def test_caller_marks_confirmed_but_no_grounding():
    """Caller marking ``confirmed`` without authorized grounding is not confirmed."""
    result = classify_deadline_grounding(
        deadline=_deadline(
            provenance="caller_claimed",
            source_class="unknown",
        )
    )
    assert result["confirmed"] is False


def test_official_specific_current_source_may_confirm():
    result = classify_deadline_grounding(
        deadline=_deadline(
            source_class="official_publication",
            provenance="grounded",
            temporal="valid",
            effective_date="2026-09-15",
        )
    )
    assert result["confirmed"] is True
    assert result["state"] == "confirmed_official"


def test_stale_official_source_is_stale_not_current_confirmation():
    result = classify_deadline_grounding(
        deadline=_deadline(source_class="official_publication", temporal="expired")
    )
    assert result["confirmed"] is False
    assert result["state"] == "stale"


def test_conflicting_current_authoritative_deadlines_is_conflicting():
    result = classify_deadline_grounding(
        deadline=_deadline(conflicting=True)
    )
    assert result["state"] == "conflicting"
    assert result["confirmed"] is False


def test_unknown_ordering_stays_unknown():
    result = classify_deadline_grounding(
        deadline=_deadline(source_class="unknown", provenance="none")
    )
    assert result["state"] == "unknown"
    assert result["confirmed"] is False


def test_retrieval_date_is_not_effective_date():
    """A deadline retrieved early is not current merely because it was retrieved
    recently; currency depends on effective/temporal validity."""
    result = classify_deadline_grounding(
        deadline=_deadline(
            retrieval_date="2026-08-01",
            effective_date="2027-01-01",
            temporal="future",
        )
    )
    assert result["confirmed"] is False
    assert result["state"] in ("future", "unknown")


def test_missing_critical_deadline_triggers_verification_need():
    result = classify_deadline_grounding(deadline=None, critical=True)
    assert result["verification_needed"] is True


def test_stale_deadline_triggers_verification_need():
    result = classify_deadline_grounding(
        deadline=_deadline(temporal="expired", critical=True)
    )
    assert result["verification_needed"] is True


def test_conflicting_deadline_triggers_verification_need():
    result = classify_deadline_grounding(
        deadline=_deadline(conflicting=True, critical=True)
    )
    assert result["verification_needed"] is True


def test_decision_critical_undergrounded_triggers_verification_need():
    result = classify_deadline_grounding(
        deadline=_deadline(provenance="remembered", critical=True)
    )
    assert result["verification_needed"] is True


def test_complete_grounded_current_noncritical_no_verification_need():
    result = classify_deadline_grounding(
        deadline=_deadline(
            source_class="official_publication",
            provenance="grounded",
            temporal="valid",
            critical=False,
        )
    )
    assert result["verification_needed"] is False


@pytest.mark.parametrize("source_reference", (None, ""))
def test_canonical_rule_unreferenced_official_critical_deadline_requires_verification(
    source_reference,
):
    result = _canonical_result(
        _deadline(critical=True, source_reference=source_reference)
    )
    finding = result.findings[0]
    assert finding.code == "DEADLINE_VERIFICATION_NEEDED"
    assert finding.metadata["confirmed"] is False
    assert finding.metadata["verification_needed"] is True


def test_canonical_rule_referenced_official_deadline_remains_confirmed():
    result = _canonical_result(_deadline(critical=True))
    finding = result.findings[0]
    assert finding.metadata["state"] == "confirmed_official"
    assert finding.metadata["confirmed"] is True
    assert finding.metadata["verification_needed"] is False
