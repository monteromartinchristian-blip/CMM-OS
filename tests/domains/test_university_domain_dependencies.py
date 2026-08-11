"""Phase 10.22 — B6: Academic Dependencies (grounded, caller not authoritative).

The audit found the previous implementation trusted a caller `passed` boolean
as authoritative.  Dependency satisfaction must be grounded: only grounded
evidence of passing satisfies a prerequisite; a caller-claimed `passed` with no
grounding is not authoritative; credit/TFG sequencing still blocks; and an
unknown prerequisite status remains unresolved (never silently treated as
satisfied).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.university import build_university_rules
from cmm.domains.university.rules import evaluate_academic_dependency

T = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _dep(
    dep_id,
    *,
    grounded_passed=False,
    caller_passed=False,
    status="unknown",
    kind="subject",
):
    return {
        "id": dep_id,
        "grounded_passed": grounded_passed,
        "caller_passed": caller_passed,
        "status": status,
        "kind": kind,
    }


def _academic_record(subject_id, status, *, ects=0, source="record-1", grounded=True):
    return {
        "subject_id": subject_id,
        "status": status,
        "ects": ects,
        "grounded": grounded,
        "source_reference": source,
        "temporal": "valid",
    }


def _canonical_result(dependency):
    rule = {
        r.definition.id: r
        for r in build_university_rules()
    }["university.academic_dependency"]
    context = ReasoningRuleContext(
        reasoning_id="dependency-production",
        timestamp=T,
        active_domains=("domain:university",),
        primary_domain="domain:university",
        metadata={"dependency": dependency},
    )
    return rule.evaluate(context)


def test_grounded_passed_prerequisite_satisfies():
    result = evaluate_academic_dependency(
        subject_id="subj-2",
        dependencies=(_dep("subj-1", grounded_passed=True, status="passed"),),
    )
    assert result["dependency_blocked"] is False
    assert result["satisfied_prerequisites"] == ("subj-1",)


def test_ungrounded_caller_passed_is_not_authoritative():
    """A caller claiming ``passed=True`` without grounding does not satisfy the
    prerequisite."""
    result = evaluate_academic_dependency(
        subject_id="subj-2",
        dependencies=(_dep("subj-1", caller_passed=True),),
    )
    assert result["dependency_blocked"] is True
    assert result["caller_passed_ignored"] == ("subj-1",)
    assert "subj-1" not in result["satisfied_prerequisites"]


def test_failed_prerequisite_blocks():
    result = evaluate_academic_dependency(
        subject_id="subj-2",
        dependencies=(_dep("subj-1", status="failed"),),
    )
    assert result["dependency_blocked"] is True
    assert "subj-1" in result["open_prerequisites"]


def test_unknown_prerequisite_remains_unresolved():
    """An unknown prerequisite status stays unresolved and is never treated as
    satisfied."""
    result = evaluate_academic_dependency(
        subject_id="subj-2",
        dependencies=(_dep("subj-1"),),
    )
    assert result["dependency_blocked"] is True
    assert "subj-1" in result["unknown_prerequisites"]
    assert "subj-1" not in result["satisfied_prerequisites"]


def test_mixed_prerequisites_only_grounded_pass_counts():
    result = evaluate_academic_dependency(
        subject_id="subj-2",
        dependencies=(
            _dep("subj-1", grounded_passed=True, status="passed"),
            _dep("subj-3", caller_passed=True),
        ),
    )
    assert result["satisfied_prerequisites"] == ("subj-1",)
    assert result["dependency_blocked"] is True


def test_tfg_prerequisite_blocks_like_subject():
    """TFG/credit sequencing operates like any prerequisite: an unsatisfied
    TFG blocks."""
    result = evaluate_academic_dependency(
        subject_id="degree",
        dependencies=(_dep("tfg", kind="tfg", status="pending"),),
    )
    assert result["dependency_blocked"] is True
    assert "tfg" in result["open_prerequisites"]


def test_grounded_tfg_passed_satisfies():
    result = evaluate_academic_dependency(
        subject_id="degree",
        dependencies=(_dep("tfg", kind="tfg", grounded_passed=True, status="passed"),),
    )
    assert result["dependency_blocked"] is False
    assert "tfg" in result["satisfied_prerequisites"]


def test_no_dependencies_is_blocked_false():
    result = evaluate_academic_dependency(subject_id="subj-2", dependencies=())
    assert result["dependency_blocked"] is False
    assert result["satisfied_prerequisites"] == ()


def test_canonical_rule_caller_fabricated_pass_does_not_establish_prerequisite():
    result = _canonical_result(
        {
            "subject_id": "subj-2",
            "prerequisites": (
                {
                    "id": "subj-1",
                    "passed": True,
                    "grounded_passed": True,
                },
            ),
        }
    )
    finding = result.findings[0]
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert finding.code == "DEPENDENCY_BLOCKED"
    assert "subj-1" in finding.metadata["unknown_prerequisites"]


# ── V10-B1/B3: direct helper malformed containers and strict booleans ────────


def test_direct_helper_malformed_dependencies_container_no_exception():
    """dependencies=7 must not raise and must block the dependency."""
    result = evaluate_academic_dependency(subject_id="target", dependencies=7)
    assert result["dependency_blocked"] is True
    assert result["satisfied_prerequisites"] == ()


def test_direct_helper_malformed_academic_records_container_no_exception():
    """academic_records=7 must not raise and must leave credit evidence unknown."""
    result = evaluate_academic_dependency(
        subject_id="target",
        dependencies=(),
        academic_records=7,
        derive_from_academic_state=True,
    )
    assert result["credit_evidence_unknown"] is True
    assert result["dependency_blocked"] is False


def test_direct_helper_grounded_passed_string_false_never_satisfies():
    """grounded_passed='false' must not satisfy a prerequisite."""
    result = evaluate_academic_dependency(
        subject_id="target",
        dependencies=({"id": "prereq", "grounded_passed": "false"},),
    )
    assert result["satisfied_prerequisites"] == ()
    assert result["dependency_blocked"] is True


def test_direct_helper_grounded_passed_string_true_never_satisfies():
    """grounded_passed='true' must not satisfy a prerequisite."""
    result = evaluate_academic_dependency(
        subject_id="target",
        dependencies=({"id": "prereq", "grounded_passed": "true"},),
    )
    assert result["satisfied_prerequisites"] == ()
    assert result["dependency_blocked"] is True


def test_direct_helper_grounded_passed_one_never_satisfies():
    """grounded_passed=1 must not satisfy a prerequisite."""
    result = evaluate_academic_dependency(
        subject_id="target",
        dependencies=({"id": "prereq", "grounded_passed": 1},),
    )
    assert result["satisfied_prerequisites"] == ()
    assert result["dependency_blocked"] is True


def test_direct_helper_grounded_passed_zero_never_satisfies():
    """grounded_passed=0 must not satisfy a prerequisite."""
    result = evaluate_academic_dependency(
        subject_id="target",
        dependencies=({"id": "prereq", "grounded_passed": 0},),
    )
    assert result["satisfied_prerequisites"] == ()
    assert result["dependency_blocked"] is True


def test_direct_helper_credit_threshold_numeric_string_does_not_satisfy():
    """ects='6' / required_credits='6' must not satisfy a credit threshold."""
    result = evaluate_academic_dependency(
        subject_id="target",
        dependencies=(
            {"id": "threshold", "kind": "credit_threshold", "required_credits": "6"},
        ),
        academic_records=(
            {
                "subject_id": "subject-1",
                "status": "completed",
                "ects": "6",
                "grounded": True,
                "source_reference": "rec-1",
                "temporal": "valid",
            },
        ),
        derive_from_academic_state=True,
    )
    assert result["satisfied_prerequisites"] == ()
    assert result["dependency_blocked"] is True



def test_canonical_rule_grounded_subject_state_satisfies_prerequisite():
    result = _canonical_result(
        {
            "subject_id": "subj-2",
            "prerequisites": ({"id": "subj-1", "kind": "subject"},),
            "academic_records": (
                _academic_record("subj-1", "passed", source="record-pass"),
            ),
        }
    )
    finding = result.findings[0]
    assert finding.code == "DEPENDENCY_SATISFIED"
    assert finding.metadata["satisfied_prerequisites"] == ("subj-1",)


def test_canonical_rule_credit_threshold_uses_grounded_completed_records():
    result = _canonical_result(
        {
            "subject_id": "tfg",
            "prerequisites": (
                {"id": "degree-credits", "kind": "credit_threshold", "required_credits": 180},
            ),
            "academic_records": tuple(
                _academic_record(f"subject-{i}", "completed", ects=29)
                for i in range(6)
            ),
        }
    )
    finding = result.findings[0]
    assert finding.code == "DEPENDENCY_BLOCKED"
    assert finding.metadata["credit_thresholds"]["degree-credits"]["completed"] == 174


def test_canonical_rule_pending_recognition_is_conditional_not_currently_satisfied():
    result = _canonical_result(
        {
            "subject_id": "tfg",
            "prerequisites": (
                {"id": "degree-credits", "kind": "tfg_eligibility", "required_credits": 180},
            ),
            "academic_records": (
                _academic_record("completed", "completed", ects=174),
                _academic_record("pending", "pending_recognition", ects=6),
            ),
        }
    )
    finding = result.findings[0]
    threshold = finding.metadata["credit_thresholds"]["degree-credits"]
    assert finding.code == "DEPENDENCY_BLOCKED"
    assert threshold["status"] == "conditional"
    assert threshold["scenario_if_recognized"] is True


def test_canonical_rule_conditional_prerequisite_is_in_blocked_ids():
    result = _canonical_result(
        {
            "subject_id": "tfg",
            "prerequisites": (
                {"id": "degree-credits", "kind": "credit_threshold", "required_credits": 180},
            ),
            "academic_records": (
                _academic_record("completed", "completed", ects=174),
                _academic_record("pending", "pending_recognition", ects=6),
            ),
        }
    )
    finding = result.findings[0]
    assert finding.metadata["conditional_prerequisites"] == ("degree-credits",)
    assert "degree-credits" in finding.references


def test_canonical_rule_unknown_dependency_remains_unresolved():
    result = _canonical_result(
        {
            "subject_id": "subj-2",
            "prerequisites": ({"id": "subj-1", "kind": "subject"},),
            "academic_records": (),
        }
    )
    finding = result.findings[0]
    assert finding.code == "DEPENDENCY_BLOCKED"
    assert finding.metadata["unknown_prerequisites"] == ("subj-1",)


def test_canonical_rule_dependency_without_id_remains_blocking_unknown():
    result = _canonical_result(
        {
            "subject_id": "subj-2",
            "prerequisites": ({"kind": "subject", "status": "unknown"},),
        }
    )
    finding = result.findings[0]
    assert finding.code == "DEPENDENCY_BLOCKED"
    assert finding.metadata["dependency_blocked"] is True
    assert finding.metadata["anonymous_prerequisite_count"] == 1
    assert finding.metadata["satisfied_prerequisites"] == ()


@pytest.mark.parametrize("required_credits", (-1, 0, 1.5, True, "abc"))
def test_canonical_rule_invalid_credit_threshold_cannot_be_satisfied(
    required_credits,
):
    result = _canonical_result(
        {
            "subject_id": "tfg",
            "prerequisites": (
                {
                    "id": "degree-credits",
                    "kind": "credit_threshold",
                    "required_credits": required_credits,
                },
            ),
            "academic_records": tuple(
                _academic_record(f"subject-{index}", "completed", ects=30)
                for index in range(6)
            ),
        }
    )
    finding = result.findings[0]
    assert finding.code == "DEPENDENCY_BLOCKED"
    assert finding.metadata["unknown_prerequisites"] == ("degree-credits",)
    assert finding.metadata["satisfied_prerequisites"] == ()


def test_canonical_rule_identityless_credits_cannot_satisfy_threshold():
    result = _canonical_result(
        {
            "subject_id": "tfg",
            "prerequisites": (
                {
                    "id": "degree-credits",
                    "kind": "credit_threshold",
                    "required_credits": 180,
                },
            ),
            "academic_records": (
                {
                    "status": "completed",
                    "ects": 180,
                    "grounded": True,
                    "source_reference": "official-credit-record",
                    "temporal": "valid",
                },
            ),
        }
    )
    finding = result.findings[0]
    assert finding.code == "DEPENDENCY_BLOCKED"
    assert finding.metadata["credit_thresholds"]["degree-credits"]["status"] == "unknown"
    assert finding.metadata["satisfied_prerequisites"] == ()


def test_canonical_rule_unknown_credit_state_cannot_satisfy_threshold():
    result = _canonical_result(
        {
            "subject_id": "tfg",
            "prerequisites": (
                {
                    "id": "degree-credits",
                    "kind": "credit_threshold",
                    "required_credits": 180,
                },
            ),
            "academic_records": (_academic_record("record-1", "unknown", ects=180),),
        }
    )
    finding = result.findings[0]
    assert finding.code == "DEPENDENCY_BLOCKED"
    assert finding.metadata["credit_thresholds"]["degree-credits"]["status"] == "unknown"


def test_canonical_rule_valid_identified_credits_satisfy_valid_threshold():
    result = _canonical_result(
        {
            "subject_id": "tfg",
            "prerequisites": (
                {
                    "id": "degree-credits",
                    "kind": "credit_threshold",
                    "required_credits": 180,
                },
            ),
            "academic_records": tuple(
                _academic_record(f"subject-{index}", "completed", ects=30)
                for index in range(6)
            ),
        }
    )
    finding = result.findings[0]
    assert finding.code == "DEPENDENCY_SATISFIED"
    assert finding.metadata["satisfied_prerequisites"] == ("degree-credits",)


# ── V7-B3: dependency credit evidence must be deduplicated by canonical ─────
# ── identity; contradictory same-identity evidence must not establish ──────
# ── a definitive credit threshold. ──────────────────────────────────────────


def test_duplicate_same_identity_credit_counts_once():
    """Two compatible completed records for the same credit identity count the
    identity once, never twice."""
    result = _canonical_result(
        {
            "subject_id": "tfg",
            "prerequisites": (
                {
                    "id": "degree-credits",
                    "kind": "credit_threshold",
                    "required_credits": 180,
                },
            ),
            "academic_records": (
                _academic_record("credit-x", "completed", ects=90),
                _academic_record("credit-x", "completed", ects=90),
            ),
        }
    )
    finding = result.findings[0]
    assert finding.code == "DEPENDENCY_BLOCKED"
    threshold = finding.metadata["credit_thresholds"]["degree-credits"]
    assert threshold["completed"] == 90
    assert threshold["status"] == "open"
    assert finding.metadata["satisfied_prerequisites"] == ()


def test_contradictory_same_identity_credit_blocks_threshold():
    """A contradictory same-identity credit (completed + failed) must not
    establish a definitive threshold; evidence is unknown."""
    result = _canonical_result(
        {
            "subject_id": "tfg",
            "prerequisites": (
                {
                    "id": "degree-credits",
                    "kind": "credit_threshold",
                    "required_credits": 180,
                },
            ),
            "academic_records": (
                _academic_record("credit-x", "completed", ects=180),
                _academic_record("credit-x", "failed", ects=180),
            ),
        }
    )
    finding = result.findings[0]
    assert finding.code == "DEPENDENCY_BLOCKED"
    assert finding.metadata["credit_evidence_unknown"] is True
    threshold = finding.metadata["credit_thresholds"]["degree-credits"]
    assert threshold["status"] == "unknown"
    assert finding.metadata["satisfied_prerequisites"] == ()


def test_same_identity_conflicting_credit_amount_fails_closed():
    """Two compatible completed records for the same identity with different
    credit amounts cannot be summed or arbitrarily chosen."""
    result = _canonical_result(
        {
            "subject_id": "tfg",
            "prerequisites": (
                {
                    "id": "degree-credits",
                    "kind": "credit_threshold",
                    "required_credits": 180,
                },
            ),
            "academic_records": (
                _academic_record("credit-x", "completed", ects=90),
                _academic_record("credit-x", "completed", ects=120),
            ),
        }
    )
    finding = result.findings[0]
    assert finding.code == "DEPENDENCY_BLOCKED"
    assert finding.metadata["credit_evidence_unknown"] is True
    threshold = finding.metadata["credit_thresholds"]["degree-credits"]
    assert threshold["status"] == "unknown"


def test_distinct_identities_still_sum():
    """Two distinct earned credit identities still sum toward the threshold."""
    result = _canonical_result(
        {
            "subject_id": "tfg",
            "prerequisites": (
                {
                    "id": "degree-credits",
                    "kind": "credit_threshold",
                    "required_credits": 180,
                },
            ),
            "academic_records": (
                _academic_record("credit-a", "completed", ects=90),
                _academic_record("credit-b", "completed", ects=90),
            ),
        }
    )
    finding = result.findings[0]
    assert finding.code == "DEPENDENCY_SATISFIED"
    threshold = finding.metadata["credit_thresholds"]["degree-credits"]
    assert threshold["completed"] == 180
    assert finding.metadata["satisfied_prerequisites"] == ("degree-credits",)


def test_six_distinct_30_ects_remains_satisfied():
    """Positive regression: six distinct subjects × 30 ECTS still satisfies a
    180 threshold."""
    result = _canonical_result(
        {
            "subject_id": "tfg",
            "prerequisites": (
                {
                    "id": "degree-credits",
                    "kind": "credit_threshold",
                    "required_credits": 180,
                },
            ),
            "academic_records": tuple(
                _academic_record(f"subject-{index}", "completed", ects=30)
                for index in range(6)
            ),
        }
    )
    finding = result.findings[0]
    assert finding.code == "DEPENDENCY_SATISFIED"
    assert finding.metadata["satisfied_prerequisites"] == ("degree-credits",)


def test_identityless_credits_still_cannot_satisfy():
    """Positive regression: identityless credit records still cannot establish
    a satisfied threshold."""
    result = _canonical_result(
        {
            "subject_id": "tfg",
            "prerequisites": (
                {
                    "id": "degree-credits",
                    "kind": "credit_threshold",
                    "required_credits": 180,
                },
            ),
            "academic_records": (
                {
                    "status": "completed",
                    "ects": 180,
                    "grounded": True,
                    "source_reference": "official-credit-record",
                    "temporal": "valid",
                },
            ),
        }
    )
    finding = result.findings[0]
    assert finding.code == "DEPENDENCY_BLOCKED"
    assert finding.metadata["satisfied_prerequisites"] == ()


# ── V7-B4: malformed collection-shaped metadata must not leak TypeError; ─────
# ── the rule must degrade to a conservative blocked/unknown result. ───────────


def test_canonical_rule_scalar_prerequisites_collection_does_not_crash():
    """A scalar ``prerequisites`` value must not raise TypeError and must not
    fabricate a satisfied dependency."""
    result = _canonical_result(
        {
            "subject_id": "subj-2",
            "prerequisites": 7,
        }
    )
    assert result.status is not None
    assert result.findings


def test_canonical_rule_scalar_academic_records_collection_does_not_crash():
    """A scalar ``academic_records`` value must not raise TypeError."""
    result = _canonical_result(
        {
            "subject_id": "subj-2",
            "prerequisites": ({"id": "subj-1", "kind": "subject"},),
            "academic_records": 7,
        }
    )
    finding = result.findings[0]
    assert finding.code == "DEPENDENCY_BLOCKED"


# ── V8-B1: malformed collection evidence is never silently coerced into an ──
# ── empty collection, because malformed prerequisites are not equivalent to ──
# ── no prerequisites. ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "malformed",
    (7, "bad", {"unexpected": "mapping"}),
)
def test_canonical_rule_malformed_prerequisites_block_not_satisfy(malformed):
    """Malformed ``prerequisites`` must be blocking and never satisfied."""
    result = _canonical_result(
        {
            "subject_id": "subj-2",
            "prerequisites": malformed,
        }
    )
    finding = result.findings[0]
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert finding.code != "DEPENDENCY_SATISFIED"
    assert finding.code == "DEPENDENCY_BLOCKED"
    assert finding.metadata["prerequisites_malformed"] is True
    assert finding.metadata["dependency_blocked"] is True


def test_canonical_rule_empty_prerequisites_remain_legitimate():
    """A valid empty prerequisites collection keeps legitimate empty
    semantics instead of being treated as malformed."""
    result = _canonical_result(
        {
            "subject_id": "subj-2",
            "prerequisites": [],
        }
    )
    finding = result.findings[0]
    assert finding.code == "DEPENDENCY_SATISFIED"
    assert finding.metadata["prerequisites_malformed"] is False
    assert finding.metadata["dependency_blocked"] is False


@pytest.mark.parametrize(
    "malformed",
    (7, "bad", {"unexpected": "mapping"}),
)
def test_canonical_rule_malformed_academic_records_cannot_confirm_credit(malformed):
    """Malformed academic records cannot establish a credit prerequisite."""
    result = _canonical_result(
        {
            "subject_id": "tfg",
            "prerequisites": (
                {
                    "id": "degree-credits",
                    "kind": "credit_threshold",
                    "required_credits": 180,
                },
            ),
            "academic_records": malformed,
        }
    )
    finding = result.findings[0]
    assert finding.code == "DEPENDENCY_BLOCKED"
    assert finding.code != "DEPENDENCY_SATISFIED"
    assert finding.metadata["academic_records_malformed"] is True
    assert finding.metadata["credit_evidence_unknown"] is True
    assert finding.metadata["satisfied_prerequisites"] == ()
# ── V9-B3.3: strict Dependency credit grounding.  Truthy != grounded. ────────


def test_canonical_rule_ungrounded_credit_record_cannot_satisfy_threshold():
    """A credit record with ``grounded="false"`` is not grounded credit evidence
    and cannot satisfy a ``required_credits`` threshold."""
    result = _canonical_result(
        {
            "subject_id": "tfg",
            "prerequisites": (
                {
                    "id": "degree-credits",
                    "kind": "credit_threshold",
                    "required_credits": 180,
                },
            ),
            "academic_records": (
                _academic_record("degree-credits", "completed", ects=180, grounded="false"),
            ),
        }
    )
    finding = result.findings[0]
    assert finding.code == "DEPENDENCY_BLOCKED"
    assert finding.code != "DEPENDENCY_SATISFIED"
    assert finding.metadata["credit_evidence_unknown"] is True
    assert finding.metadata["dependency_blocked"] is True


def test_canonical_rule_strict_grounded_true_credit_satisfies_threshold():
    """The positive regression: literal ``grounded=True`` credit evidence works."""
    result = _canonical_result(
        {
            "subject_id": "tfg",
            "prerequisites": (
                {
                    "id": "degree-credits",
                    "kind": "credit_threshold",
                    "required_credits": 180,
                },
            ),
            "academic_records": (
                _academic_record("degree-credits", "completed", ects=180, grounded=True),
            ),
        }
    )
    finding = result.findings[0]
    assert finding.code == "DEPENDENCY_SATISFIED"
    assert finding.metadata["dependency_blocked"] is False
