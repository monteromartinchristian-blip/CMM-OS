"""Tests for Phase 10.27 Parenthood Domain Presentation."""

from __future__ import annotations

from cmm.domains.parenthood.presentation import (
    build_parenthood_presentation_policy,
    present_parenthood_result,
)


def test_parenthood_presentation_policy() -> None:
    """Verify presentation policy has required disclaimers, uncertainty and provenance flags."""
    policy = build_parenthood_presentation_policy()
    assert policy.detail_level == "detailed"
    assert policy.include_uncertainty is True
    assert policy.include_provenance is True
    assert policy.include_alternatives is True
    assert policy.require_disclaimers is True


def test_present_journey_result() -> None:
    """Verify presenting a journey result displays Camino a la Paternidad context."""
    res = {
        "status": "completed",
        "topic": "surrogacy_pathways",
        "decisions": [{"topic": "selected_clinic", "status": "proposed"}],
        "cost_range": [70000, 110000],
    }
    projected = present_parenthood_result(res, scope="parenthood.journey")
    assert projected["scope_display_name"] == "Camino a la Paternidad"
    assert projected["domain_display_name"] == "Paternidad"
    assert projected["uncertainty_preserved"] is True
    assert projected["proposals_distinguished"] is True


def test_present_child_result_uses_display_name_preserving_internal_id() -> None:
    """Verify presenting a child result uses child display name without losing stable ID."""
    res = {
        "status": "completed",
        "child_id": "child:001",
        "developmental_stage": "toddler",
        "observations": ["shy around strangers"],
    }
    projected = present_parenthood_result(
        res,
        scope="parenthood.child:child:001",
        child_display_name="Sofía",
    )
    assert projected["domain_display_name"] == "Paternidad"
    assert projected["scope_display_name"] == "Sofía"
    assert projected["child_id"] == "child:001"
    assert projected["non_diagnostic_badge"] == "Normal developmental variation"
