"""Phase 10.24 — Reflection presentation tests.

Presentation preserves every epistemic and decision-relevant state: hypotheses
stay hypotheses, uncertainty is never amplified, ambivalence and open
questions remain visible, and identity/persistence/decision statuses are not
silently upgraded (spec §36, §46).
"""

from __future__ import annotations

import json

from cmm.domains.reflection import (
    build_reflection_presentation_policy,
    present_reflection_result,
)
from cmm.domains.reflection.presentation import (
    PRESENTATION_STATE_CONFIRMED,
    PRESENTATION_STATE_CONFLICTING,
    PRESENTATION_STATE_HYPOTHETICAL,
    PRESENTATION_STATE_INFERRED,
    PRESENTATION_STATE_OBSERVED,
    PRESENTATION_STATE_PENDING_CONFIRMATION,
    PRESENTATION_STATE_UNKNOWN,
    PRESENTATION_STATE_USER_STATED,
    present_state,
)


def test_presentation_policy_is_profile_owned():
    from cmm.domains.reflection import build_reflection_profile

    policy = build_reflection_presentation_policy()
    profile_policy = build_reflection_profile().presentation_policy
    assert policy.detail_level == profile_policy.detail_level
    assert policy.include_uncertainty is True
    assert policy.include_provenance is True
    assert policy.allow_speculation is False
    assert policy.require_disclaimers is True


def test_presentation_states_closed():
    assert PRESENTATION_STATE_OBSERVED == "observed"
    assert PRESENTATION_STATE_USER_STATED == "user-stated"
    assert PRESENTATION_STATE_INFERRED == "inferred"
    assert PRESENTATION_STATE_HYPOTHETICAL == "hypothetical"
    assert PRESENTATION_STATE_UNKNOWN == "unknown"
    assert PRESENTATION_STATE_CONFLICTING == "conflicting"
    assert PRESENTATION_STATE_CONFIRMED == "confirmed"
    assert PRESENTATION_STATE_PENDING_CONFIRMATION == "pending-confirmation"


def test_present_state_mapping():
    assert present_state("observation") == PRESENTATION_STATE_OBSERVED
    assert present_state("user-stated") == PRESENTATION_STATE_USER_STATED
    assert present_state("inferred") == PRESENTATION_STATE_INFERRED
    assert present_state("hypothesis") == PRESENTATION_STATE_HYPOTHETICAL
    assert present_state("unknown") == PRESENTATION_STATE_UNKNOWN
    assert present_state("conflicting") == PRESENTATION_STATE_CONFLICTING
    assert present_state("confirmed") == PRESENTATION_STATE_CONFIRMED
    assert (
        present_state("pending_confirmation") == PRESENTATION_STATE_PENDING_CONFIRMATION
    )
    # malformed/unknown states never widen certainty
    assert present_state(None) == PRESENTATION_STATE_UNKNOWN
    assert present_state(7) == PRESENTATION_STATE_UNKNOWN
    assert present_state({}) == PRESENTATION_STATE_UNKNOWN


def test_presentation_preserves_open_ended_result():
    result = {
        "unresolved": True,
        "hypotheses": [
            {"identity": "h1", "status": "hypothesis"},
            {"identity": "h2", "status": "hypothesis"},
        ],
        "counterevidence": ("s3",),
        "ambivalence_present": True,
        "open_questions": ("why?",),
        "interest_candidates": [
            {"interest": "photography", "persistent_confirmed": False}
        ],
        "persistent_confirmed": False,
        "decision_adopted": False,
        "chronology_state": "unknown",
    }
    presented = present_reflection_result(result)
    assert presented["unresolved"] is True
    assert presented["hypothesis_count"] == 2
    assert presented["open_questions"] == ("why?",)
    assert presented["ambivalence_present"] is True
    assert presented["persistent_confirmed"] is False
    assert presented["decision_adopted"] is False
    assert presented["temporally_ambiguous"] is True
    assert presented["certainty_amplified"] is False
    json.dumps(presented, allow_nan=False)


def test_presentation_does_not_increase_certainty():
    result = {"unresolved": True, "hypotheses": [], "open_questions": []}
    presented = present_reflection_result(result)
    assert presented["unresolved"] is True
    assert presented["conclusion_presented"] is False
    # a hypothesis cannot be worded/presented as fact or diagnosis
    assert any(
        h["presentation_state"] == PRESENTATION_STATE_HYPOTHETICAL
        for h in present_reflection_result(
            {
                "unresolved": True,
                "hypotheses": [{"identity": "h1", "status": "hypothesis"}],
                "open_questions": [],
            }
        )["hypotheses"]
    )
    json.dumps(presented, allow_nan=False)


def test_presentation_preserves_interest_provenance_and_persistence():
    result = {
        "unresolved": False,
        "interest_candidates": [
            {
                "interest": "photography",
                "sources": ("msg:1", "msg:2"),
                "grounded_evidence_count": 2,
                "persistent_confirmed": False,
            }
        ],
        "persistent_confirmed": False,
    }
    presented = present_reflection_result(result)
    candidate = presented["interest_candidates"][0]
    assert candidate["persistent_confirmed"] is False
    assert candidate["sources"] == ("msg:1", "msg:2")
    assert presented["persistence_state"] == PRESENTATION_STATE_PENDING_CONFIRMATION


def test_presentation_preserves_decision_status():
    result = {"unresolved": False, "decision_adopted": False, "reviewed": True}
    presented = present_reflection_result(result)
    assert presented["decision_adopted"] is False
    assert presented["decision_state"] == "not-adopted"
