"""Tests for Phase 10.29 Life Plan Domain Presentation."""

from __future__ import annotations

from cmm.domains.life_plan.presentation import (
    build_life_plan_presentation_policy,
    present_life_plan_result,
)


def test_build_life_plan_presentation_policy() -> None:
    policy = build_life_plan_presentation_policy()
    assert policy is not None


def test_present_life_plan_result_preserves_semantics() -> None:
    res = {
        "status": "completed",
        "is_proposal": True,
        "goals": [{"id": "g-1", "status": "idea"}],
    }
    projected = present_life_plan_result(res)
    assert projected["domain_display_name"] == "Life Plan"
    assert projected["uncertainty_preserved"] is True
    assert projected["decision_lattice_preserved"] is True
