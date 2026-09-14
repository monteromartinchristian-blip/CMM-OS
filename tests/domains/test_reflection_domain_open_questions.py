"""Phase 10.24 — Reflection open-question retention tests.

``evaluate_open_questions`` and ``OpenQuestionRule`` keep questions open when
the available basis cannot resolve them; a plausible hypothesis alone never
closes a question, and no answer is ever invented (spec §11, §41).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.reflection.rules import (
    OpenQuestionRule,
    evaluate_open_questions,
)

NOW = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _question(
    identity,
    question,
    *,
    evidence=None,
    plausible_hypothesis=False,
    future_behavior=False,
    motive_stated=None,
    timeline_complete=None,
    source_grounded=None,
    answer=None,
):
    return {
        "identity": identity,
        "question": question,
        "evidence": evidence,
        "plausible_hypothesis": plausible_hypothesis,
        "future_behavior": future_behavior,
        "motive_stated": motive_stated,
        "timeline_complete": timeline_complete,
        "source_grounded": source_grounded,
        "answer": answer,
    }


def test_question_open_when_evidence_missing():
    result = evaluate_open_questions(
        questions=(_question("q1", "Why did they stop calling?", evidence=None),)
    )
    assert result["questions"][0]["status"] == "open"
    assert "evidence_missing" in result["questions"][0]["reasons"]
    assert result["unresolved_count"] == 1


def test_question_open_when_evidence_conflicting():
    result = evaluate_open_questions(
        questions=(_question("q1", "Are they interested?", evidence="conflicting"),)
    )
    assert result["questions"][0]["status"] == "open"
    assert "evidence_conflicting" in result["questions"][0]["reasons"]


def test_plausible_hypothesis_alone_does_not_close_question():
    result = evaluate_open_questions(
        questions=(
            _question(
                "q1",
                "Why am I avoiding this?",
                evidence=None,
                plausible_hypothesis=True,
            ),
        )
    )
    assert result["questions"][0]["status"] == "open"
    assert result["questions"][0]["plausible_hypothesis"] is True
    assert "plausible_hypothesis_only" in result["questions"][0]["reasons"]


def test_future_behavior_unknowable():
    result = evaluate_open_questions(
        questions=(
            _question(
                "q1", "Will I still feel this way in a year?", future_behavior=True
            ),
        )
    )
    assert result["questions"][0]["status"] == "open"
    assert "future_behavior_unknowable" in result["questions"][0]["reasons"]


def test_motive_not_stated():
    result = evaluate_open_questions(
        questions=(_question("q1", "Why did I react that way?", motive_stated=False),)
    )
    assert result["questions"][0]["status"] == "open"
    assert "motive_not_stated" in result["questions"][0]["reasons"]


def test_incomplete_timeline_keeps_question_open():
    result = evaluate_open_questions(
        questions=(_question("q1", "When did this start?", timeline_complete=False),)
    )
    assert result["questions"][0]["status"] == "open"
    assert "timeline_incomplete" in result["questions"][0]["reasons"]


def test_ungrounded_source_basis():
    result = evaluate_open_questions(
        questions=(_question("q1", "Is this a pattern?", source_grounded=False),)
    )
    assert result["questions"][0]["status"] == "open"
    assert "source_basis_ungrounded" in result["questions"][0]["reasons"]


def test_no_invented_answer():
    result = evaluate_open_questions(
        questions=(
            _question("q1", "Why do I feel this way?", evidence=None),
            _question(
                "q2",
                "What do I actually want?",
                evidence="grounded",
                answer="user-said: distance",
            ),
        )
    )
    assert result["invented_answers"] == ()
    assert result["questions"][0]["status"] == "open"
    # only an explicitly supplied answer closes the question
    assert result["questions"][1]["status"] == "answered"


def test_input_permutation_identical():
    questions = (
        _question("q1", "Why ai?", evidence=None),
        _question("q2", "Why b?", evidence="conflicting"),
    )
    a = evaluate_open_questions(questions=questions)
    b = evaluate_open_questions(questions=(questions[1], questions[0]))
    assert (a["unresolved_count"], a["answered_count"]) == (
        b["unresolved_count"],
        b["answered_count"],
    )
    assert {q["identity"] for q in a["questions"]} == {
        q["identity"] for q in b["questions"]
    }


def test_open_question_rule_applied():
    context = ReasoningRuleContext(
        reasoning_id="rr-oq-1",
        timestamp=NOW,
        active_domains=("domain:reflection",),
        primary_domain="domain:reflection",
        metadata={
            "questions": (
                _question("q1", "Why ai?", evidence=None),
                _question("q2", "When did it start?", timeline_complete=False),
            )
        },
    )
    rule = OpenQuestionRule(definition=_definition())
    result = rule.evaluate(context)
    assert result.status is ReasoningRuleResultStatus.APPLIED
    finding = result.findings[0]
    assert finding.metadata["unresolved_count"] == 2
    assert finding.metadata["open_question"] is True
    json.dumps(finding.to_dict(), allow_nan=False)


def test_open_question_rule_not_applicable():
    context = ReasoningRuleContext(
        reasoning_id="rr-oq-2",
        timestamp=NOW,
        active_domains=("domain:reflection",),
        primary_domain="domain:reflection",
        metadata={},
    )
    rule = OpenQuestionRule(definition=_definition())
    result = rule.evaluate(context)
    assert result.status is ReasoningRuleResultStatus.NOT_APPLICABLE


def _definition():
    from cmm.cognitive.enums import (
        ReasoningRiskLevel,
        ReasoningRuleCategory,
        ReasoningRuleScope,
        ReasoningRuleStatus,
    )
    from cmm.domains.rule_contracts import DomainReasoningRuleDefinition

    return DomainReasoningRuleDefinition(
        id="reflection.open_question",
        name="OpenQuestionRule",
        version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id="domain:reflection",
        category=ReasoningRuleCategory.EPISTEMIC.value,
        status=ReasoningRuleStatus.ENABLED,
        priority=740,
        risk_level=ReasoningRiskLevel.LOW,
        deterministic=True,
        description="Open question rule.",
        metadata={"phase": "10.24"},
    )
