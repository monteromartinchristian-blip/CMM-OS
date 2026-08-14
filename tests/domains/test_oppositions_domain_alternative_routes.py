"""Phase 10.23 — AlternativeRouteRule tests (frozen spec §41)."""

from __future__ import annotations

from cmm.domains.oppositions.rules import compare_alternative_routes


def _route(route_id, *, eligibility="eligible", overlap=0.5, call_state="current"):
    return {
        "id": route_id,
        "eligibility": eligibility,
        "syllabus_overlap": overlap,
        "effort_hours": 200,
        "call_state": call_state,
    }


def test_primary_plus_one_alternative():
    result = compare_alternative_routes(
        primary=_route("primary", overlap=0.9),
        alternatives=(_route("alt1", overlap=0.7),),
    )
    assert result["resolved"] is True
    assert result["alternatives_considered"] == ("alt1",)
    assert result["target_unchanged"] is True
    assert result["primary_abandoned"] is False


def test_multiple_alternatives():
    result = compare_alternative_routes(
        primary=_route("primary"),
        alternatives=(_route("a1"), _route("a2", overlap=0.8)),
    )
    assert result["alternatives_considered"] == ("a1", "a2")


def test_missing_official_requirements_leave_comparison_conditional():
    alt = {"id": "alt1", "eligibility": None, "syllabus_overlap": 0.6}
    result = compare_alternative_routes(
        primary=_route("primary"), alternatives=(alt,)
    )
    assert "alt1" in result["conditional_requirements"]
    # a decision-relevant route with missing eligibility keeps the comparison
    # unresolved; no definitive recommendation may be emitted from the known
    # subset only.
    assert result["resolved"] is False
    assert result["recommendation"] is None


def test_route_with_stale_call_remains_stale():
    result = compare_alternative_routes(
        primary=_route("primary"),
        alternatives=(_route("alt1", call_state="stale"),),
    )
    assert "alt1" in result["stale_route_ids"]
    assert result["target_unchanged"] is True


def test_better_scenario_does_not_change_active_target():
    result = compare_alternative_routes(
        primary=_route("primary", overlap=0.4),
        alternatives=(_route("alt1", overlap=0.9),),
    )
    # alt1 is recommended, but the target is unchanged.
    assert result["recommendation"] == "alt1"
    assert result["target_unchanged"] is True
    assert result["primary_abandoned"] is False


def test_comparison_does_not_mark_primary_abandoned():
    result = compare_alternative_routes(
        primary=_route("primary"), alternatives=(_route("alt1"),)
    )
    assert result["primary_abandoned"] is False
    assert result["target_changed"] is False


def test_malformed_route_identity_does_not_merge():
    result = compare_alternative_routes(
        primary=7, alternatives=(_route("alt1"),)
    )
    assert result["resolved"] is False


def test_trade_offs_remain_visible():
    result = compare_alternative_routes(
        primary=_route("primary"), alternatives=(_route("alt1", overlap=0.8),)
    )
    assert len(result["trade_offs"]) == 1
    assert result["trade_offs"][0]["eligible"] is True


def test_hard_constraint_beats_preference():
    # alt1 ineligible (hard blocker) should not be the recommendation even with
    # the best overlap.
    result = compare_alternative_routes(
        primary=_route("primary", overlap=0.4),
        alternatives=(_route("alt1", overlap=0.9, eligibility="ineligible"),),
    )
    assert result["recommendation"] is None


def test_order_invariance():
    a = compare_alternative_routes(
        primary=_route("primary"),
        alternatives=(_route("a1"), _route("a2", overlap=0.8)),
    )
    b = compare_alternative_routes(
        primary=_route("primary"),
        alternatives=(_route("a2", overlap=0.8), _route("a1")),
    )
    # normalized semantic meaning, not just the considered-id set
    key = (
        "recommendation",
        "alternatives_considered",
        "conflicting_route_ids",
        "conditional_requirements",
        "stale_route_ids",
        "resolved",
    )
    assert tuple(a[k] for k in key) == tuple(b[k] for k in key)
    assert a["trade_offs"] == b["trade_offs"]


def test_conflicting_duplicate_route_order_invariance():
    """Conflicting duplicate route identities must be unresolved/blocked and
    must not make the recommendation depend on input order."""
    a = {
        "id": "alt1",
        "eligibility": "eligible",
        "syllabus_overlap": 0.9,
        "effort_hours": 200,
        "call_state": "current",
    }
    b = {
        "id": "alt1",
        "eligibility": "ineligible",
        "syllabus_overlap": 0.1,
        "effort_hours": 200,
        "call_state": "current",
    }
    alt2 = _route("alt2", overlap=0.5)
    forward = compare_alternative_routes(
        primary=_route("primary"), alternatives=(a, b, alt2)
    )
    reverse = compare_alternative_routes(
        primary=_route("primary"), alternatives=(b, a, alt2)
    )
    # the recommendation must not change solely because the first duplicate
    # changed.
    assert forward["recommendation"] == reverse["recommendation"]
    # the conflicting duplicate route can never be automatically recommended.
    assert forward["recommendation"] != "alt1"
    assert forward["conflicting_route_ids"] == ("alt1",)
    assert forward["alternatives_considered"] == reverse["alternatives_considered"]


def test_conflicting_alternative_sets_resolved_false():
    a = {"id": "alt1", "eligibility": "eligible", "syllabus_overlap": 0.9,
         "effort_hours": 200, "call_state": "current"}
    b = {"id": "alt1", "eligibility": "ineligible", "syllabus_overlap": 0.1,
         "effort_hours": 200, "call_state": "current"}
    result = compare_alternative_routes(primary=_route("primary"), alternatives=(a, b))
    assert result["resolved"] is False
    assert result["conflicting_route_ids"] == ("alt1",)


def test_conflicting_alternative_suppresses_recommendation():
    a = {"id": "alt1", "eligibility": "eligible", "syllabus_overlap": 0.9,
         "effort_hours": 200, "call_state": "current"}
    b = {"id": "alt1", "eligibility": "ineligible", "syllabus_overlap": 0.1,
         "effort_hours": 200, "call_state": "current"}
    alt2 = _route("alt2", overlap=0.5)
    result = compare_alternative_routes(
        primary=_route("primary"), alternatives=(a, b, alt2)
    )
    # any decision-relevant conflicting route suppresses a definitive
    # recommendation and makes the comparison unresolved.
    assert result["recommendation"] is None
    assert result["resolved"] is False
    assert result["target_unchanged"] is True
