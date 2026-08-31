"""Phase 10.23 — Versioned strategy / DP-023 tests (frozen spec §42)."""

from __future__ import annotations

from cmm.domains.oppositions.rules import create_strategy_proposal


def test_current_strategy_has_explicit_version():
    proposal = create_strategy_proposal(
        current_version="3",
        proposed_change="shift target",
        reason="better call",
        evidence=("ev-1",),
        actor="user",
        target_id="body:primary",
    )
    assert proposal["strategy_proposal"] is True
    assert proposal["previous_version"] == "3"
    assert proposal["preserves_previous_version"] is True


def test_proposed_update_preserves_prior_strategy():
    proposal = create_strategy_proposal(
        current_version="2",
        proposed_change="increase revision hours",
        reason="feasibility",
        evidence=(),
        actor="user",
        target_id="body:primary",
    )
    assert proposal["previous_version"] == "2"
    assert proposal["proposed_change"] == "increase revision hours"


def test_proposal_does_not_equal_adoption():
    proposal = create_strategy_proposal(
        current_version="1",
        proposed_change="change plan",
        reason="x",
        evidence=(),
        actor="user",
        target_id="body:primary",
    )
    assert proposal["adopted"] is False
    assert proposal["decision_pending"] is True
    assert proposal["adoption_time"] is None


def test_explicit_adoption_requires_fields():
    proposal = create_strategy_proposal(
        current_version="1",
        proposed_change=None,
        reason=None,
        evidence=None,
        actor=None,
        target_id=None,
    )
    # no proposed change -> no pending strategy decision
    assert proposal["decision_pending"] is False


def test_alternative_recommendation_does_not_mutate_target():
    proposal = create_strategy_proposal(
        current_version="1",
        proposed_change="consider alt",
        reason="comparison",
        evidence=(),
        actor="system",
        target_id="body:primary",
    )
    # the primary target is preserved; only a proposal is produced.
    assert proposal["target_id"] == "body:primary"
    assert proposal["adopted"] is False


def test_changed_official_facts_create_review_need():
    proposal = create_strategy_proposal(
        current_version="2",
        proposed_change=None,
        reason="official deadlines changed",
        evidence=("official-2027",),
        actor="system",
        target_id="body:primary",
    )
    # official state never silently rewrites strategy; it stays a proposal.
    assert proposal["official_state_overridden"] is False
    assert proposal["strategy_state_overridden"] is False


def test_material_change_preserves_reason_and_actor():
    proposal = create_strategy_proposal(
        current_version="5",
        proposed_change="switch focus",
        reason="new official call",
        evidence=("ev-9",),
        actor="user",
        target_id="body:primary",
    )
    assert proposal["reason"] == "new official call"
    assert proposal["actor"] == "user"
    assert proposal["relation_to_goal"] == "body:primary"
