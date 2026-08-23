"""Tests for Languages Domain Error Patterns, Correction Priority, and Adaptation."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.cognitive.enums import (
    ReasoningRiskLevel,
    ReasoningRuleCategory,
    ReasoningRuleResultStatus,
    ReasoningRuleScope,
    ReasoningRuleStatus,
)
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.languages.rules import (
    AdaptiveDifficultyRule,
    CorrectionPriorityRule,
    ErrorPatternEvidenceRule,
    adapt_difficulty,
    evaluate_error_pattern,
    prioritize_corrections,
)
from cmm.domains.rule_contracts import DomainReasoningRuleDefinition

NOW = datetime.now(timezone.utc)


def test_evaluate_error_pattern_single_error_insufficient() -> None:
    """A single isolated error is not a recurrent error pattern."""
    result = evaluate_error_pattern(
        observations=(
            {"id": "err-1", "error_type": "subject_verb_agreement", "context_id": "c1", "sentence": "He go home."},
        )
    )
    assert result["pattern_state"] == "insufficient_evidence"
    assert result["eligible"] is False
    assert result["independent_occurrences"] == 1


def test_evaluate_error_pattern_repeated_same_sentence_not_independent() -> None:
    """Repeated identical tokens in copied context do not count as independent."""
    result = evaluate_error_pattern(
        observations=(
            {"id": "err-1", "error_type": "subject_verb_agreement", "context_id": "c1", "sentence": "He go home."},
            {"id": "err-2", "error_type": "subject_verb_agreement", "context_id": "c1", "sentence": "He go home."},
        )
    )
    assert result["pattern_state"] == "insufficient_evidence"
    assert result["eligible"] is False
    assert result["independent_occurrences"] == 1


def test_evaluate_error_pattern_independent_comparable_samples() -> None:
    """Same systematic error across independent contexts confirms pattern."""
    result = evaluate_error_pattern(
        observations=(
            {"id": "err-1", "error_type": "subject_verb_agreement", "context_id": "c1", "sentence": "He go to school.", "comparable": True, "comparison_key": "free-writing"},
            {"id": "err-2", "error_type": "subject_verb_agreement", "context_id": "c2", "sentence": "She have a dog.", "comparable": True, "comparison_key": "free-writing"},
        )
    )
    assert result["pattern_state"] in ("candidate", "evidenced")
    assert result["eligible"] is True
    assert result["independent_occurrences"] >= 2


def test_same_error_same_provenance_different_ids_is_not_recurrent_pattern() -> None:
    """Caller aliases cannot manufacture independent recurrence."""
    observations = (
        {
            "id": "caller-a",
            "provenance_id": "sample-1",
            "sentence": "No sooner I had...",
            "error_type": "inversion",
            "comparable": True,
            "comparison_key": "free-writing",
        },
        {
            "id": "caller-b",
            "provenance_id": "sample-1",
            "sentence": "No sooner I had...",
            "error_type": "inversion",
            "comparable": True,
            "comparison_key": "free-writing",
        },
    )

    result = evaluate_error_pattern(observations=observations)

    assert result["eligible"] is False
    assert result["independent_occurrences"] == 1


def test_different_non_comparable_occurrences_do_not_form_pattern() -> None:
    """Distinct occurrences still require explicit semantic comparability."""
    observations = (
        {"provenance_id": "sample-1", "error_type": "inversion", "comparable": False},
        {"provenance_id": "sample-2", "error_type": "inversion", "comparable": False},
    )

    result = evaluate_error_pattern(observations=observations)

    assert result["eligible"] is False
    assert result["pattern_state"] == "insufficient_evidence"


def test_evaluate_error_pattern_valid_variety_excluded() -> None:
    """Valid variety differences must not be counted as error pattern evidence."""
    result = evaluate_error_pattern(
        observations=(
            {"id": "var-1", "error_type": "spelling", "is_valid_alternative": True, "context_id": "c1"},
            {"id": "err-1", "error_type": "spelling", "is_valid_alternative": False, "context_id": "c2"},
        )
    )
    assert result["pattern_state"] == "insufficient_evidence"
    assert result["eligible"] is False
    assert result["independent_occurrences"] == 1


def test_evaluate_error_pattern_resolved_with_isolated_slip() -> None:
    """A resolved pattern with one isolated slip shows lapse_possible without full regression."""
    result = evaluate_error_pattern(
        observations=(
            {"id": "err-1", "error_type": "past_tense", "context_id": "c1", "resolved": True, "comparable": True, "comparison_key": "free-writing"},
            {"id": "err-2", "error_type": "past_tense", "context_id": "c2", "resolved": True, "comparable": True, "comparison_key": "free-writing"},
            {"id": "slip-1", "error_type": "past_tense", "context_id": "c3", "resolved": False, "comparable": True, "comparison_key": "free-writing"},
        )
    )
    assert result["lapse_possible"] is True
    assert result["pattern_state"] in ("improving", "resolved", "candidate")


def test_evaluate_error_pattern_order_invariance() -> None:
    """Permuting evidence does not alter pattern outcome."""
    obs1 = (
        {"id": "err-1", "error_type": "preposition", "context_id": "c1", "sentence": "I arrived at."},
        {"id": "err-2", "error_type": "preposition", "context_id": "c2", "sentence": "She listened on him."},
    )
    obs2 = (obs1[1], obs1[0])
    res1 = evaluate_error_pattern(observations=obs1)
    res2 = evaluate_error_pattern(observations=obs2)
    assert res1["pattern_state"] == res2["pattern_state"]
    assert res1["eligible"] == res2["eligible"]


def test_prioritize_corrections_hierarchy() -> None:
    """Comprehension-blocking errors have priority over minor style."""
    errors = (
        {"id": "e1", "category": "minor_style", "blocking": False},
        {"id": "e2", "category": "comprehension_blocking", "blocking": True},
        {"id": "e3", "category": "recurrent", "blocking": False},
    )
    prioritized = prioritize_corrections(errors=errors, mode="practice")
    assert prioritized["prioritized_errors"][0]["id"] == "e2"
    assert prioritized["prioritized_errors"][1]["id"] == "e3"


def test_prioritize_corrections_modes() -> None:
    """In practice mode, minor style errors are selective; in assess mode, feedback is deferred."""
    errors = (
        {"id": "e1", "category": "minor_style", "blocking": False},
    )
    practice_res = prioritize_corrections(errors=errors, mode="practice")
    assert practice_res["immediate_correction_count"] == 0 or practice_res["selective_density"] is True

    assess_res = prioritize_corrections(errors=errors, mode="assess")
    assert assess_res["defer_feedback"] is True


def test_adapt_difficulty_increase_scaffold_maintain() -> None:
    """Verify adaptive difficulty responses to performance evidence."""
    # High score across comparable sessions -> increase
    perf_high = (
        {"session_id": "s1", "score": 0.95, "comparable": True},
        {"session_id": "s2", "score": 0.92, "comparable": True},
    )
    res_inc = adapt_difficulty(current_difficulty=3, performance=perf_high)
    assert res_inc["action"] == "increase"
    assert res_inc["target_difficulty"] == 4

    # Low score -> scaffold_reduce
    perf_low = (
        {"session_id": "s1", "score": 0.35, "comparable": True},
        {"session_id": "s2", "score": 0.40, "comparable": True},
    )
    res_red = adapt_difficulty(current_difficulty=3, performance=perf_low)
    assert res_red["action"] == "scaffold_reduce"
    assert res_red["target_difficulty"] == 2

    # Adequate score -> maintain_and_advance
    perf_mid = (
        {"session_id": "s1", "score": 0.75, "comparable": True},
        {"session_id": "s2", "score": 0.78, "comparable": True},
    )
    res_adv = adapt_difficulty(current_difficulty=3, performance=perf_mid)
    assert res_adv["action"] == "maintain_and_advance"
    assert res_adv["target_difficulty"] == 3


def test_adapt_difficulty_one_bad_session_no_stable_regression() -> None:
    """One single bad session does not alter stable proficiency."""
    perf_single_bad = (
        {"session_id": "s1", "score": 0.20, "comparable": True},
    )
    res = adapt_difficulty(current_difficulty=4, performance=perf_single_bad, stable_proficiency="B2")
    assert res["stable_proficiency_changed"] is False
    assert res["action"] in ("scaffold_reduce", "insufficient_evidence", "maintain_and_advance")


def test_error_rules_evaluation() -> None:
    """Verify rule evaluations for ErrorPatternEvidenceRule, CorrectionPriorityRule, AdaptiveDifficultyRule."""
    ep_def = DomainReasoningRuleDefinition(
        id="languages.error_pattern_evidence",
        name="ErrorPatternEvidenceRule",
        version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id="domain:languages",
        category=ReasoningRuleCategory.EPISTEMIC,
        status=ReasoningRuleStatus.ENABLED,
        priority=740,
        risk_level=ReasoningRiskLevel.LOW,
    )
    rule_ep = ErrorPatternEvidenceRule(definition=ep_def)
    ctx_ep = ReasoningRuleContext(
        reasoning_id="r-ep",
        timestamp=NOW,
        metadata={"material": {"observations": [{"id": "e1", "context_id": "c1", "error_type": "t"}]}},
    )
    res_ep = rule_ep.evaluate(ctx_ep)
    assert res_ep.status == ReasoningRuleResultStatus.APPLIED

    cp_def = DomainReasoningRuleDefinition(
        id="languages.correction_priority",
        name="CorrectionPriorityRule",
        version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id="domain:languages",
        category=ReasoningRuleCategory.INFERENCE,
        status=ReasoningRuleStatus.ENABLED,
        priority=750,
        risk_level=ReasoningRiskLevel.LOW,
    )
    rule_cp = CorrectionPriorityRule(definition=cp_def)
    ctx_cp = ReasoningRuleContext(
        reasoning_id="r-cp",
        timestamp=NOW,
        metadata={"material": {"errors": [{"id": "e1", "category": "comprehension_blocking"}]}},
    )
    res_cp = rule_cp.evaluate(ctx_cp)
    assert res_cp.status == ReasoningRuleResultStatus.APPLIED

    ad_def = DomainReasoningRuleDefinition(
        id="languages.adaptive_difficulty",
        name="AdaptiveDifficultyRule",
        version="1.0.0",
        scope=ReasoningRuleScope.DOMAIN,
        domain_id="domain:languages",
        category=ReasoningRuleCategory.INFERENCE,
        status=ReasoningRuleStatus.ENABLED,
        priority=760,
        risk_level=ReasoningRiskLevel.LOW,
    )
    rule_ad = AdaptiveDifficultyRule(definition=ad_def)
    ctx_ad = ReasoningRuleContext(
        reasoning_id="r-ad",
        timestamp=NOW,
        metadata={"material": {"current_difficulty": 2, "performance": [{"score": 0.9, "comparable": True}, {"score": 0.9, "comparable": True}]}},
    )
    res_ad = rule_ad.evaluate(ctx_ad)
    assert res_ad.status == ReasoningRuleResultStatus.APPLIED
