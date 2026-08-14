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
    assert a["alternatives_considered"] == b["alternatives_considered"]