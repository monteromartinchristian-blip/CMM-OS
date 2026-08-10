"""Phase 10.22 — B3: Academic Deadlines (grounding and temporal validity).

The audit found the previous implementation merely checked that a date string
existed.  A deadline's epistemic state must be grounded: a recalled deadline is
not confirmed, a caller marking ``confirmed`` without grounding is not
authoritative, stale official sources are stale, and conflicting authoritative
deadlines stay conflicting.  Verification needs arise for missing, stale,
conflicting or decision-critical under-grounded deadlines.
"""

from __future__ import annotations

from cmm.domains.university.rules import classify_deadline_grounding


def _deadline(
    *,
    value="2026-09-15",
    source_class="official_publication",
    provenance="grounded",
    temporal="valid",
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