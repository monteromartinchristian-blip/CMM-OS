"""Phase 10.24 — DP-024 acceptance matrix tests (AT-DP-024 evidence).

Direct executable evidence for the four DP-024 dimensions: open-ended analysis,
prudent hypotheses, interest mapping grounded in sources, and confirmed
persistence (spec §44, §28, §17).  These tests establish implementation-side
candidate evidence only; independent audit closure is a separate lifecycle
event and is never claimed here.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.reflection.operations import (
    generate_hypotheses_result,
    structure_reflection_result,
)
from cmm.domains.reflection.rules import (
    MultipleHypothesesRule,
    classify_persistence,
    evaluate_ambivalence,
    evaluate_hypotheses,
    evaluate_open_questions,
    map_interests,
    no_forced_conclusion_policy,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _context(metadata):
    return ReasoningRuleContext(
        reasoning_id=f"rr-dp024-{len(str(metadata)) % 10000}",
        timestamp=NOW,
        active_domains=("domain:reflection",),
        primary_domain="domain:reflection",
        metadata=metadata,
    )


# ── A. Open-ended analysis ────────────────────────────────────────────────────

def test_open_ended_analysis_succeeds_unresolved():
    structured = structure_reflection_result(
        material=(
            {"level": "observation", "content": "they cancelled twice", "source": "s1"},
            {"level": "belief", "content": "I believe they are withdrawing", "source": "s2"},
            {"level": "emotion", "content": "sad and relieved", "source": "s3"},
        )
    )
    policy = no_forced_conclusion_policy(structured)
    assert policy["valid_unresolved_completion"] is True
    assert policy["forced_conclusion"] is False
    assert structured["persisted"] is False


def test_open_ended_analysis_retains_multiple_hypotheses():
    hypotheses = evaluate_hypotheses(
        hypotheses=(
            {"identity": "h1", "statement": "work pressure explains it", "supporting_ids": ("s1",)},
            {"identity": "h2", "statement": "relationship strains explain it", "supporting_ids": ("s2",)},
            {"identity": "h3", "statement": "health explains it", "supporting_ids": ("s3",)},
        )
    )
    assert len(hypotheses["hypotheses"]) == 3
    assert hypotheses["winner_selected"] is False
    assert hypotheses["forced_conclusion"] is False
    assert hypotheses["unresolved"] is False  # multiple grounded supports; no forced winner


def test_open_ended_analysis_preserves_ambivalence():
    ambivalence = evaluate_ambivalence(
        records=(
            {"identity": "p1", "statement": "relieved", "kind": "emotion", "polarity": 1, "context": "same", "temporal": "2026-08-01"},
            {"identity": "p2", "statement": "sad", "kind": "emotion", "polarity": -1, "context": "same", "temporal": "2026-08-01"},
        )
    )
    assert ambivalence["ambivalence_present"] is True
    assert ambivalence["forced_resolution"] is False


def test_open_ended_analysis_retains_open_questions():
    questions = evaluate_open_questions(
        questions=(
            {"identity": "q1", "question": "why did it happen?", "evidence": None},
            {"identity": "q2", "question": "what do I want?", "evidence": "conflicting"},
        )
    )
    assert questions["unresolved_count"] == 2
    assert questions["invented_answers"] == ()
    assert all(q["status"] == "open" for q in questions["questions"])


# ── B. Prudent hypotheses ─────────────────────────────────────────────────────

def test_prudent_hypotheses_never_become_facts():
    result = generate_hypotheses_result(
        hypotheses=(
            {
                "identity": "h1",
                "statement": "the pattern may come from work stress",
                "supporting_ids": ("s1", "s2"),
                "counterevidence_ids": ("s3",),
                "uncertainty": 0.7,
                "scope": "work-context",
                "temporal": "2026-01..2026-06",
            },
            {
                "identity": "h2",
                "statement": "the pattern may come from relational insecurity",
                "supporting_ids": ("s4",),
                "counterevidence_ids": (),
                "uncertainty": 0.9,
            },
        )
    )
    for hypothesis in result["hypotheses"]:
        assert hypothesis["status"] == "hypothesis"
        assert hypothesis["fact"] is False
        assert hypothesis["statement"].startswith("the pattern may")  # tentative framing
    assert result["winner_selected"] is False
    assert result["no_diagnosis"] is True


def test_psychological_hypothesis_is_never_a_diagnosis():
    hypotheses = evaluate_hypotheses(
        hypotheses=(
            {"identity": "h1", "statement": "possible avoidance tendency", "supporting_ids": ("s1",)},
        )
    )
    output = json.dumps(hypotheses, allow_nan=False)
    assert "diagnos" not in output.lower()  # no diagnostic wording
    for hypothesis in hypotheses["hypotheses"]:
        assert hypothesis.get("diagnosis") is not True


def test_identity_hypothesis_remains_hypothetical():
    """A hypothesis around identity never becomes a stable identity fact."""
    hypothesis = evaluate_hypotheses(
        hypotheses=(
            {
                "identity": "id-h1",
                "statement": "the user may identify strongly with their work",
                "supporting_ids": ("s1", "s2", "s3"),
                "counterevidence_ids": ("s4",),
            },
        )
    )
    h = hypothesis["hypotheses"][0]
    assert h["status"] == "hypothesis"
    assert h["fact"] is False
    assert hypothesis["winner_selected"] is False


# ── C. Interest mapping grounded in sources ───────────────────────────────────

def test_interest_candidate_requires_source_basis():
    result = map_interests(
        records=(
            {"interest": "photography", "source": "msg:1", "explicit": True, "mention": True, "observed_at": "2026-05-01"},
        )
    )
    candidate = result["interest_candidates"][0]
    assert candidate["sources"] == ("msg:1",)
    assert candidate["persistent_confirmed"] is False
    assert candidate["uncertainty"] is True  # one mention is not enough
    assert result["persistent_confirmed"] is False


def test_duplicate_source_does_not_inflate_interest_evidence():
    result = map_interests(
        records=(
            {"interest": "photography", "source": "same", "explicit": True, "observed_at": "2026-05-01"},
            {"interest": "photography", "source": "same", "explicit": True, "observed_at": "2026-05-01"},
        )
    )
    candidate = result["interest_candidates"][0]
    assert candidate["grounded_evidence_count"] == 1
    assert result["duplicates_ignored"] == ("same",)


def test_model_inference_is_not_independent_corroboration():
    result = map_interests(
        records=(
            {"interest": "photography", "source": "msg:1", "explicit": True, "observed_at": "2026-05-01"},
            {"interest": "photography", "source": "summary:1", "source_kind": "model_summary", "observed_at": "2026-06-01"},
            {"interest": "photography", "source": "mem:1", "source_kind": "memory_summary", "observed_at": "2026-07-01"},
        )
    )
    candidate = result["interest_candidates"][0]
    assert candidate["independent_grounded_count"] == 1
    assert candidate["model_source_count"] == 2
    assert result["model_inference_not_source"] is True


def test_contradictory_interest_evidence_keeps_uncertainty():
    result = map_interests(
        records=(
            {"interest": "photography", "source": "msg:1", "explicit": True, "observed_at": "2026-05-01"},
            {"interest": "photography", "source": "msg:2", "contradictory": True, "observed_at": "2026-06-01"},
        )
    )
    candidate = result["interest_candidates"][0]
    assert candidate["uncertainty"] is True
    assert candidate["counterevidence"] == ("msg:2",)
    assert result["contradictions"] == ("photography",)


# ── D. Confirmed persistence ──────────────────────────────────────────────────

def test_candidate_pattern_is_not_confirmed_persistence():
    record = classify_persistence(
        {"pattern": "avoids intimacy", "sources": ("msg:1", "msg:2", "msg:3")},
        confirmation=None,
    )
    assert record["confirmed"] is False
    assert record["persistence_state"] == "candidate"


def test_memory_proposal_is_not_memory_mutation():
    from cmm.domains.reflection import build_reflection_memory_proposal

    proposal = build_reflection_memory_proposal(proposal_id="dp024-mp")
    assert proposal.requires_confirmation is True
    # proposal exists; nothing is written
    assert proposal.proposal_id == "dp024-mp"


def test_only_valid_confirmation_authorizes_persistence_proposal():
    record = classify_persistence(
        {"pattern": "avoids intimacy", "sources": ("msg:1", "msg:2")},
        confirmation=True,  # literal True, valid authorization
    )
    assert record["authorization_accepted"] is True
    assert record["confirmed"] is True
    assert record["persistence_state"] == "confirmed"

    for raw in ("true", "TRUE", 1, 1.0, [], {}, "yes"):
        bad = classify_persistence(
            {"pattern": "avoids intimacy", "sources": ("msg:1", "msg:2")},
            confirmation=raw,  # nonliteral -> fails closed
        )
        assert bad["confirmed"] is False
        assert bad["authorization_accepted"] is False
        assert bad["authorization_malformed"] is True


def test_rule_findings_are_strict_json_safe():
    context = _context(
        {
            "hypotheses": (
                {"identity": "h1", "statement": "a", "supporting_ids": ("s1",)},
                {"identity": "h2", "statement": "b", "supporting_ids": ("s2",)},
            )
        }
    )
    rule = MultipleHypothesesRule(definition=_nfc_definition())
    result = rule.evaluate(context)
    assert result.status is ReasoningRuleResultStatus.APPLIED
    json.dumps(result.to_dict(), allow_nan=False)
    json.dumps(result.findings[0].to_dict(), allow_nan=False)


def _nfc_definition():
    from cmm.cognitive.enums import (
        ReasoningRiskLevel,
        ReasoningRuleCategory,
        ReasoningRuleScope,
        ReasoningRuleStatus,
    )
    from cmm.domains.rule_contracts import DomainReasoningRuleDefinition

    return DomainReasoningRuleDefinition(
        id="reflection.multiple_hypotheses",
        name="MultipleHypothesesRule",
        version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id="domain:reflection",
        category=ReasoningRuleCategory.INFERENCE.value,
        status=ReasoningRuleStatus.ENABLED,
        priority=710,
        risk_level=ReasoningRiskLevel.LOW,
        deterministic=True,
        description="Multiple hypotheses rule.",
        metadata={"phase": "10.24"},
    )