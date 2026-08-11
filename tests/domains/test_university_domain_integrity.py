"""Phase 10.22 — B7: Academic Integrity Mode C (permissive by default, grounded).

The audit found the previous implementation only preserved a stated mode string
and never reasoned about assistance restrictions.  Integrity Mode C must be
permissive by default: assistance is allowed when no applicable restriction is
grounded.  A caller cannot fabricate a prohibition by setting a bare boolean
without grounding.  A remembered prohibition is not automatically equivalent to
a current official one.  When an explicit, sufficiently grounded restriction
exists, the domain respects its concrete scope and preserves source and
temporal validity.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.university import build_university_rules
from cmm.domains.university.rules import evaluate_academic_integrity

T = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _canonical_result(integrity):
    rule = {
        r.definition.id: r
        for r in build_university_rules()
    }["university.academic_integrity"]
    context = ReasoningRuleContext(
        reasoning_id="integrity-production",
        timestamp=T,
        active_domains=("domain:university",),
        primary_domain="domain:university",
        metadata={"integrity": integrity},
    )
    return rule.evaluate(context)


def _restriction(**overrides):
    return {
        "status": "prohibited",
        "grounded": True,
        "source_class": "official_regulation",
        "temporal": "current",
        "source_reference": "integrity-regulation-1",
        "course": "course-x",
        "assessment": "assignment-a",
        "prohibited_actions": ("draft_final_answer",),
        **overrides,
    }


def test_mode_c_permissive_by_default_when_no_restriction():
    """No applicable restriction grounded -> assistance allowed by default."""
    result = evaluate_academic_integrity(mode="mode_c")
    assert result["mode"] == "mode_c"
    assert result["assistance_permitted"] is True
    assert result["restriction"] is None
    assert result["restriction_grounded"] is False


def test_mode_c_defaults_to_permissive_when_mode_omitted():
    result = evaluate_academic_integrity()
    assert result["mode"] == "mode_c"
    assert result["assistance_permitted"] is True


def test_ai_forbidden_without_grounding_cannot_fabricate_prohibition():
    """A caller setting ``ai_forbidden=True`` with no grounding cannot create a
    prohibition; Mode C remains permissive."""
    result = evaluate_academic_integrity(
        mode="mode_c",
        caller_restriction={"ai_forbidden": True},
    )
    assert result["assistance_permitted"] is True
    assert result["restriction_grounded"] is False
    assert result["caller_forbidden_ignored"] is True


def test_grounded_restriction_respected_within_scope():
    """An explicit, sufficiently grounded restriction is respected; assistance
    remains permitted within the allowed scope."""
    result = evaluate_academic_integrity(
        mode="mode_c",
        grounded_restriction={
            "status": "prohibited",
            "grounded": True,
            "scope": ("final_exam_essay",),
            "source_class": "official_regulation",
            "temporal": "current",
            "source_reference": "integrity-regulation-1",
        },
    )
    assert result["assistance_permitted"] is False
    assert result["restriction_grounded"] is True
    assert result["restriction_scope"] == ("final_exam_essay",)


def test_remembered_restriction_not_current_official():
    """A remembered prohibition is not automatically equivalent to a current
    official one; it does not restrict assistance."""
    result = evaluate_academic_integrity(
        mode="mode_c",
        grounded_restriction={
            "status": "prohibited",
            "grounded": True,
            "source_class": "remembered",
            "temporal": "past",
        },
        remembered_restriction=True,
    )
    assert result["assistance_permitted"] is True
    assert result["restriction_grounded"] is False
    assert result["remembered_not_official"] is True


def test_ungrounded_restriction_does_not_restrict():
    """A restriction with no grounding does not restrict assistance."""
    result = evaluate_academic_integrity(
        mode="mode_c",
        grounded_restriction={
            "status": "prohibited",
            "grounded": False,
        },
    )
    assert result["assistance_permitted"] is True
    assert result["restriction_grounded"] is False


def test_unknown_mode_not_permissive():
    """An unknown integrity mode is rejected, not silently treated as Mode C."""
    result = evaluate_academic_integrity(mode="mode_x")
    assert result["mode_valid"] is False
    assert result["assistance_permitted"] is False


def test_canonical_rule_scoped_restriction_denies_only_prohibited_action():
    result = _canonical_result(
        {
            "mode": "mode_c",
            "course": "course-x",
            "assessment": "assignment-a",
            "requested_action": "draft_final_answer",
            "grounded_restriction": _restriction(),
        }
    )
    finding = result.findings[0]
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert finding.code == "INTEGRITY_RESTRICTION_APPLIED"
    assert finding.metadata["assistance_permitted"] is False
    assert finding.metadata["restriction_applies"] is True


def test_canonical_rule_same_restriction_allows_explanation():
    result = _canonical_result(
        {
            "mode": "mode_c",
            "course": "course-x",
            "assessment": "assignment-a",
            "requested_action": "explain_concept",
            "grounded_restriction": _restriction(),
        }
    )
    assert result.findings[0].metadata["assistance_permitted"] is True


def test_canonical_rule_wrong_course_does_not_apply_restriction():
    result = _canonical_result(
        {
            "mode": "mode_c",
            "course": "course-y",
            "assessment": "assignment-a",
            "requested_action": "draft_final_answer",
            "grounded_restriction": _restriction(),
        }
    )
    assert result.findings[0].metadata["assistance_permitted"] is True
    assert result.findings[0].metadata["restriction_applies"] is False


def test_canonical_rule_stale_restriction_does_not_prohibit():
    result = _canonical_result(
        {
            "mode": "mode_c",
            "course": "course-x",
            "assessment": "assignment-a",
            "requested_action": "draft_final_answer",
            "grounded_restriction": _restriction(temporal="expired"),
        }
    )
    assert result.findings[0].metadata["assistance_permitted"] is True


def test_canonical_rule_superseded_restriction_does_not_prohibit():
    result = _canonical_result(
        {
            "mode": "mode_c",
            "course": "course-x",
            "assessment": "assignment-a",
            "requested_action": "draft_final_answer",
            "grounded_restriction": _restriction(superseded=True),
        }
    )
    assert result.findings[0].metadata["assistance_permitted"] is True


def test_canonical_rule_ambiguous_limitation_is_not_a_prohibition():
    result = _canonical_result(
        {
            "mode": "mode_c",
            "course": "course-x",
            "assessment": "assignment-a",
            "requested_action": "draft_final_answer",
            "grounded_restriction": _restriction(
                prohibited_actions=(),
                ambiguous=True,
                text="AI use should be limited",
            ),
        }
    )
    assert result.findings[0].metadata["assistance_permitted"] is True


def test_canonical_rule_caller_boolean_without_restriction_allows():
    result = _canonical_result(
        {
            "mode": "mode_c",
            "course": "course-x",
            "assessment": "assignment-a",
            "requested_action": "draft_final_answer",
            "caller_restriction": {"ai_forbidden": True},
        }
    )
    assert result.findings[0].metadata["assistance_permitted"] is True


@pytest.mark.parametrize("source_reference", (None, ""))
def test_canonical_rule_unreferenced_official_restriction_cannot_prohibit(
    source_reference,
):
    result = _canonical_result(
        {
            "mode": "mode_c",
            "course": "course-x",
            "assessment": "assignment-a",
            "requested_action": "draft_final_answer",
            "grounded_restriction": _restriction(
                source_reference=source_reference
            ),
        }
    )
    finding = result.findings[0]
    assert finding.code == "INTEGRITY_MODE_PRESERVED"
    assert finding.metadata["restriction_grounded"] is False
    assert finding.metadata["restriction_applies"] is False
    assert finding.metadata["assistance_permitted"] is True


# ── V7-B2: exact-scope fail-closed ───────────────────────────────────────────
# A scoped restriction applies only when its required scope is actually
# established.  Unknown current scope is NOT a matching scope.


def test_course_scoped_restriction_does_not_apply_when_course_unknown():
    """A course-scoped restriction with an unknown current course must not
    prohibit (applicability is unresolved, not matching)."""
    result = _canonical_result(
        {
            "mode": "mode_c",
            "requested_action": "draft_final_answer",
            "grounded_restriction": _restriction(),
        }
    )
    finding = result.findings[0]
    assert finding.metadata["assistance_permitted"] is True
    assert finding.metadata["restriction_applies"] is False
    assert finding.metadata["restriction_grounded"] is True


def test_assessment_scoped_restriction_does_not_apply_when_assessment_unknown():
    result = _canonical_result(
        {
            "mode": "mode_c",
            "course": "course-x",
            "requested_action": "draft_final_answer",
            "grounded_restriction": _restriction(),
        }
    )
    finding = result.findings[0]
    assert finding.metadata["assistance_permitted"] is True
    assert finding.metadata["restriction_applies"] is False


def test_course_and_assessment_scoped_restriction_needs_both_scopes():
    result = _canonical_result(
        {
            "mode": "mode_c",
            "requested_action": "draft_final_answer",
            "grounded_restriction": _restriction(),
        }
    )
    finding = result.findings[0]
    assert finding.metadata["restriction_applies"] is False
    assert finding.metadata["assistance_permitted"] is True


def test_exact_scope_match_still_applies():
    result = _canonical_result(
        {
            "mode": "mode_c",
            "course": "course-x",
            "assessment": "assignment-a",
            "requested_action": "draft_final_answer",
            "grounded_restriction": _restriction(),
        }
    )
    finding = result.findings[0]
    assert finding.metadata["restriction_applies"] is True
    assert finding.metadata["assistance_permitted"] is False


def test_mismatched_scope_remains_non_applicable():
    result = _canonical_result(
        {
            "mode": "mode_c",
            "course": "course-y",
            "assessment": "assignment-a",
            "requested_action": "draft_final_answer",
            "grounded_restriction": _restriction(),
        }
    )
    finding = result.findings[0]
    assert finding.metadata["restriction_applies"] is False
    assert finding.metadata["assistance_permitted"] is True


def test_unscoped_general_restriction_may_apply_without_current_course():
    """A genuinely global restriction (no course/assessment scope) may apply
    even when no current course is supplied."""
    result = _canonical_result(
        {
            "mode": "mode_c",
            "requested_action": "draft_final_answer",
            "grounded_restriction": _restriction(
                course=None,
                assessment=None,
            ),
        }
    )
    finding = result.findings[0]
    assert finding.metadata["restriction_grounded"] is True
    assert finding.metadata["restriction_applies"] is True
    assert finding.metadata["assistance_permitted"] is False


# ── Optional V7 cleanup: restrictor source/temporal evidence is preserved in ──
# ── the finding so the epistemic basis of the restriction is not lost. ────────


def test_finding_preserves_restriction_source_and_temporal_evidence():
    """The integrity finding carries the grounded restriction's source_class,
    temporal and source_reference so the epistemic basis is auditable."""
    result = _canonical_result(
        {
            "mode": "mode_c",
            "course": "course-x",
            "assessment": "assignment-a",
            "requested_action": "draft_final_answer",
            "grounded_restriction": _restriction(),
        }
    )
    finding = result.findings[0]
    assert finding.code == "INTEGRITY_RESTRICTION_APPLIED"
    assert finding.metadata["restriction_source_class"] == "official_regulation"
    assert finding.metadata["restriction_temporal"] == "current"
    assert (
        finding.metadata["restriction_source_reference"]
        == "integrity-regulation-1"
    )
    assert "integrity-regulation-1" in finding.references


@pytest.mark.parametrize(
    "integrity",
    (
        {
            "mode": "mode_c",
            "requested_action": "draft_final_answer",
            "grounded_restriction": _restriction(),
        },
        {
            "mode": "mode_c",
            "course": "course-y",
            "assessment": "assignment-a",
            "requested_action": "draft_final_answer",
            "grounded_restriction": _restriction(),
        },
        {
            "mode": "mode_c",
            "course": "course-x",
            "requested_action": "draft_final_answer",
            "grounded_restriction": _restriction(),
        },
    ),
)
def test_finding_code_does_not_claim_restriction_when_not_applied(integrity):
    """``INTEGRITY_RESTRICTION_APPLIED`` is emitted only when the grounded
    restriction actually applies."""
    result = _canonical_result(integrity)
    finding = result.findings[0]
    assert finding.metadata["restriction_grounded"] is True
    assert finding.metadata["restriction_applies"] is False
    assert finding.code != "INTEGRITY_RESTRICTION_APPLIED"
    assert finding.code == "INTEGRITY_MODE_PRESERVED"
# ── V9-B3.4: strict Integrity restriction grounding.  Truthy != grounded. ─────


def test_canonical_rule_ungrounded_restriction_never_applies():
    """A restriction with ``grounded="false"`` must never become
    ``restriction_grounded=True`` — it fails closed as not grounded."""
    result = _canonical_result(
        {
            "mode": "mode_c",
            "course": "course-x",
            "assessment": "assignment-a",
            "requested_action": "draft_final_answer",
            "grounded_restriction": _restriction(grounded="false"),
        }
    )
    finding = result.findings[0]
    assert finding.metadata["restriction_grounded"] is False
    assert finding.metadata["restriction_applies"] is False
    assert finding.metadata["assistance_permitted"] is True


def test_canonical_rule_truthy_grounded_string_does_not_ground():
    """``grounded="true"`` is not the literal ``True`` and must not ground."""
    result = _canonical_result(
        {
            "mode": "mode_c",
            "course": "course-x",
            "assessment": "assignment-a",
            "requested_action": "draft_final_answer",
            "grounded_restriction": _restriction(grounded="true"),
        }
    )
    finding = result.findings[0]
    assert finding.metadata["restriction_grounded"] is False
    assert finding.metadata["restriction_applies"] is False
    assert finding.metadata["assistance_permitted"] is True


def test_canonical_rule_grounded_one_does_not_ground():
    """``grounded=1`` is not the literal ``True`` and must not ground."""
    result = _canonical_result(
        {
            "mode": "mode_c",
            "course": "course-x",
            "assessment": "assignment-a",
            "requested_action": "draft_final_answer",
            "grounded_restriction": _restriction(grounded=1),
        }
    )
    finding = result.findings[0]
    assert finding.metadata["restriction_grounded"] is False
    assert finding.metadata["restriction_applies"] is False
    assert finding.metadata["assistance_permitted"] is True


def test_canonical_rule_strict_grounded_true_restriction_still_applies():
    """The positive regression: literal ``grounded=True`` still grounds a
    restriction when all other conditions match, and the restriction is
    enforced within its scope."""
    result = _canonical_result(
        {
            "mode": "mode_c",
            "course": "course-x",
            "assessment": "assignment-a",
            "requested_action": "draft_final_answer",
            "grounded_restriction": _restriction(),
        }
    )
    finding = result.findings[0]
    assert finding.metadata["restriction_grounded"] is True
    assert finding.metadata["restriction_applies"] is True
    assert finding.metadata["assistance_permitted"] is False
    assert finding.code == "INTEGRITY_RESTRICTION_APPLIED"


# ═══════════════════════════════════════════════════════════════════════════════
# V11-B2: strict boolean semantics on public Integrity paths
#
# Integrity boolean-bearing metadata (ai_forbidden, ambiguous, superseded) is
# strict.  Malformed truthy/falsy runtime values (strings, 1, 0) must NOT be a
# true restriction/scope state.  Mode C stays conservative: no restriction is
# applied without sufficiently grounded exact boolean evidence.
# ═══════════════════════════════════════════════════════════════════════════════


def test_v11_b2_integrity_caller_ai_forbidden_string_false_ignored():
    """caller_restriction.ai_forbidden='false' must not be read as a real
    forbidden state."""
    result = evaluate_academic_integrity(
        mode="mode_c",
        caller_restriction={"ai_forbidden": "false"},
    )
    assert result["caller_forbidden_ignored"] is False


def test_v11_b2_integrity_ambiguous_zero_malformed_not_applied():
    """A malformed ambiguous flag (0) is not confidently clear; conservative
    Mode C must not apply a restriction from it."""
    result = evaluate_academic_integrity(
        mode="mode_c",
        current_course="course-x",
        current_assessment="assignment-a",
        requested_action="draft_final_answer",
        grounded_restriction=_restriction(ambiguous=0),
    )
    assert result["assistance_permitted"] is True
    assert result["restriction_applies"] is False


def test_v11_b2_integrity_superseded_zero_malformed_not_applied():
    """A malformed superseded flag (0) is not confidently non-superseded;
    conservative Mode C must not apply a restriction from it."""
    result = evaluate_academic_integrity(
        mode="mode_c",
        current_course="course-x",
        current_assessment="assignment-a",
        requested_action="draft_final_answer",
        grounded_restriction=_restriction(superseded=0),
    )
    assert result["assistance_permitted"] is True
    assert result["restriction_applies"] is False


def test_v11_b2_integrity_exact_booleans_still_work_positive():
    """Real boolean flags retain the existing grounded-restriction semantics."""
    result = evaluate_academic_integrity(
        mode="mode_c",
        current_course="course-x",
        current_assessment="assignment-a",
        requested_action="draft_final_answer",
        grounded_restriction=_restriction(ambiguous=False),
    )
    assert result["assistance_permitted"] is False
    assert result["restriction_applies"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# V12-B1: strict boolean composition at the canonical Integrity wrapper
#
# The wrapper must NOT pre-coerce remembered_restriction with ``bool(...)``
# before delegating to the strict helper.  remembered_restriction="false" /
# "true" / 1 / 0 must never be normalized to True.
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("value", ["false", "true", 1, 0])
def test_v12_b1_integrity_remembered_restriction_malformed_not_true(value):
    result = _canonical_result({"mode": "mode_c", "remembered_restriction": value})
    finding = result.findings[0]
    assert finding.metadata["remembered_not_official"] is False


def test_v12_b1_integrity_remembered_restriction_literal_true_remembered():
    result = _canonical_result(
        {"mode": "mode_c", "remembered_restriction": True}
    )
    finding = result.findings[0]
    assert finding.metadata["remembered_not_official"] is True


def test_v12_b1_integrity_remembered_restriction_literal_false_not_remembered():
    result = _canonical_result(
        {"mode": "mode_c", "remembered_restriction": False}
    )
    finding = result.findings[0]
    assert finding.metadata["remembered_not_official"] is False
