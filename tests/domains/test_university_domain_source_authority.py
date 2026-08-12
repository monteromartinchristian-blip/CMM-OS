"""Phase 10.22 — B1: Academic Source Authority (grounded, attribute-specific).

The audit found the previous implementation ranked by a caller-supplied
``source_type`` plus ``supplied_attributes``.  That is insufficient: authority
must derive from attribute + source class + provenance + temporal validity +
specificity + scope, and a caller cannot fabricate ``official`` by setting a
field.  These tests pin the grounded semantics.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.university import build_university_rules
from cmm.domains.university.rules import (
    classify_academic_source_authority,
    resolve_source_authority_by_attribute,
)

T = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _grounded(
    source_id,
    *,
    source_class="official_academic_record",
    supplied=("grade",),
    provenance="grounded",
    temporal="valid",
    specificity="general",
    scope=None,
    supersedes=(),
):
    source = {
        "source_id": source_id,
        "source_class": source_class,
        "supplied_attributes": supplied,
        "provenance": provenance,
        "temporal": temporal,
        "specificity": specificity,
        "supersedes": supersedes,
    }
    if scope is not None:
        source["scope"] = scope
    return source


def _canonical_rule():
    return {
        rule.definition.id: rule
        for rule in build_university_rules()
    }["university.academic_source_authority"]


def _canonical_result(*claims):
    context = ReasoningRuleContext(
        reasoning_id="source-authority-production",
        timestamp=T,
        active_domains=("domain:university",),
        primary_domain="domain:university",
        metadata={"academic_claims": claims},
    )
    return _canonical_rule().evaluate(context)


def _authority_finding(result, attribute):
    return next(
        finding
        for finding in result.findings
        if finding.metadata.get("attribute") == attribute
    )


def test_official_academic_record_beats_personal_note_for_grade():
    """For an official grade attribute, a grounded official academic record wins
    over a personal note."""
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(
            _grounded("rec", source_class="official_academic_record"),
            _grounded("note", source_class="personal_note"),
        ),
    )
    assert result["authority_resolved"] is True
    assert result["authoritative_source_id"] == "rec"
    assert result["authority_class"] == "official_academic_record"


def test_specific_official_exam_notice_may_win_over_general_record_for_exam_date():
    """For an exact exam date, a specific official examination notice may beat a
    general academic record (specificity + scope)."""
    rec = _grounded(
        "rec",
        source_class="general_academic_record",
        supplied=("exam_date",),
        specificity="general",
    )
    notice = _grounded(
        "notice",
        source_class="specific_official_call",
        supplied=("exam_date",),
        specificity="specific",
    )
    result = classify_academic_source_authority(
        attribute="exam_date",
        sources=(rec, notice),
    )
    assert result["authority_resolved"] is True
    assert result["authoritative_source_id"] == "notice"


def test_recency_alone_never_wins():
    """A newer source with insufficient authority/scope does not win over an
    older authoritative regulation."""
    older_authoritative = _grounded(
        "reg",
        source_class="regulation",
        supplied=("requirement",),
        temporal="valid",
    )
    newer_informal = _grounded(
        "new",
        source_class="personal_note",
        supplied=("requirement",),
        temporal="valid",
    )
    result = classify_academic_source_authority(
        attribute="requirement",
        sources=(older_authoritative, newer_informal),
    )
    assert result["authoritative_source_id"] == "reg"


def test_caller_cannot_fabricate_official_without_grounding():
    """A caller claiming ``source_type=official`` without grounded provenance or
    source classification must NOT become authoritative."""
    fabricated = {
        "source_id": "fake",
        "source_type": "official",
        "source_class": "unknown",
        "supplied_attributes": ("grade",),
        "provenance": "caller_claimed",
        "temporal": "valid",
    }
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(fabricated,),
    )
    assert result["authority_resolved"] is False
    assert result["authoritative_source_id"] is None


def test_provenance_is_not_truth():
    """A source having provenance does not automatically make its claim correct;
    authority is resolved but the claim value is not blessed as true."""
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(_grounded("rec", source_class="official_academic_record"),),
    )
    assert result["authority_resolved"] is True
    assert result["authoritative_source_id"] == "rec"
    # Provenance alone does not elevate a non-authoritative source.
    unver = _grounded("u", source_class="personal_note", provenance="grounded")
    result2 = classify_academic_source_authority(
        attribute="grade",
        sources=(_grounded("rec", source_class="official_academic_record"), unver),
    )
    assert result2["authoritative_source_id"] == "rec"


def test_equal_authority_incompatible_claims_unresolved():
    """Two equally-authoritative incompatible claims without valid supersession
    remain unresolved (no arbitrary choice)."""
    result = classify_academic_source_authority(
        attribute="exam_date",
        sources=(
            _grounded(
                "a",
                source_class="specific_official_call",
                supplied=("exam_date",),
                specificity="specific",
            ),
            _grounded(
                "b",
                source_class="specific_official_call",
                supplied=("exam_date",),
                specificity="specific",
            ),
        ),
    )
    assert result["authority_resolved"] is False
    assert result["authority_unknown"] is True
    assert result["conflict"] is True


def test_valid_supersession_resolves_current_while_preserving_history():
    """A valid authoritative supersession resolves the current value while the
    superseded source remains preserved as history."""
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(
            _grounded("old", source_class="official_academic_record"),
            _grounded(
                "new",
                source_class="official_academic_record",
                supersedes=("old",),
            ),
        ),
    )
    assert result["authority_resolved"] is True
    assert result["authoritative_source_id"] == "new"
    assert "old" in result["superseded_sources"]


def test_scope_exclusion_removes_candidate():
    """A source outside the relevant scope does not compete for the attribute."""
    result = classify_academic_source_authority(
        attribute="deadline",
        sources=(
            _grounded(
                "other",
                source_class="official_publication",
                supplied=("deadline",),
                scope="another_subject",
            ),
            _grounded(
                "mine",
                source_class="subject_guide",
                supplied=("deadline",),
                scope="current_subject",
            ),
        ),
        scope="current_subject",
    )
    assert result["authoritative_source_id"] == "mine"


def test_canonical_rule_specific_notice_beats_general_calendar_for_exact_date():
    result = _canonical_result(
        {
            "id": "calendar",
            "attribute": "exam_date",
            "value": "17",
            "source_class": "academic_calendar",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "general",
        },
        {
            "id": "notice",
            "attribute": "exam_date",
            "value": "18",
            "source_class": "specific_official_call",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
        },
    )
    finding = _authority_finding(result, "exam_date")
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert finding.metadata["authoritative_source_id"] == "notice"
    assert finding.metadata["authoritative_value"] == "18"
    assert finding.metadata["historical_source_ids"] == ()


def test_canonical_rule_newer_personal_note_does_not_beat_older_valid_official():
    result = _canonical_result(
        {
            "id": "official",
            "attribute": "exam_date",
            "value": "18",
            "source_class": "specific_official_call",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
            "observed_at": "2026-07-01",
        },
        {
            "id": "note",
            "attribute": "exam_date",
            "value": "19",
            "source_type": "official",
            "source_class": "personal_note",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
            "observed_at": "2026-07-31",
        },
    )
    finding = _authority_finding(result, "exam_date")
    assert finding.metadata["authoritative_source_id"] == "official"
    assert finding.metadata["authoritative_value"] == "18"


def test_canonical_rule_caller_official_metadata_without_grounding_is_unknown():
    result = _canonical_result(
        {
            "id": "fabricated",
            "attribute": "exam_date",
            "value": "18",
            "source_type": "official",
            "source_class": "unknown",
            "provenance": "caller_claimed",
            "temporal": "valid",
        }
    )
    finding = _authority_finding(result, "exam_date")
    assert finding.metadata["authority_resolved"] is False
    assert finding.metadata["authoritative_source_id"] is None


def test_canonical_rule_equal_current_authority_remains_unresolved():
    result = _canonical_result(
        {
            "id": "call-a",
            "attribute": "exam_date",
            "value": "18",
            "source_class": "specific_official_call",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
        },
        {
            "id": "call-b",
            "attribute": "exam_date",
            "value": "19",
            "source_class": "specific_official_call",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
        },
    )
    finding = _authority_finding(result, "exam_date")
    assert finding.metadata["authority_resolved"] is False
    assert finding.metadata["authority_conflict"] is True


def test_canonical_rule_equal_authority_same_value_is_corroborated():
    result = _canonical_result(
        {
            "id": "call-a",
            "attribute": "exam_date",
            "value": "18",
            "source_class": "specific_official_call",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
        },
        {
            "id": "call-b",
            "attribute": "exam_date",
            "value": "18",
            "source_class": "specific_official_call",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
        },
    )
    finding = _authority_finding(result, "exam_date")
    assert finding.metadata["authority_resolved"] is True
    assert finding.metadata["authority_conflict"] is False
    assert finding.metadata["authoritative_source_id"] is None
    assert finding.metadata["authoritative_value"] == "18"
    assert finding.metadata["supporting_source_ids"] == ("call-a", "call-b")
    assert finding.metadata["verification_need"]["needed"] is False


def test_canonical_rule_supersession_selects_new_value_and_preserves_old():
    result = _canonical_result(
        {
            "id": "old-call",
            "attribute": "exam_date",
            "value": "17",
            "source_class": "specific_official_call",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
        },
        {
            "id": "revised-call",
            "attribute": "exam_date",
            "value": "18",
            "source_class": "specific_official_call",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
            "supersedes": ("old-call",),
        },
    )
    finding = _authority_finding(result, "exam_date")
    assert finding.metadata["authoritative_source_id"] == "revised-call"
    assert finding.metadata["authoritative_value"] == "18"
    assert finding.metadata["historical_source_ids"] == ("old-call",)


def test_unknown_authority_ordering_remains_unknown():
    """When authority cannot be ordered, the result stays unknown; never silently
    choosing a side."""
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(
            _grounded("a", source_class="unknown"),
            _grounded("b", source_class="unknown"),
        ),
    )
    assert result["authority_resolved"] is False
    assert result["authoritative_source_id"] is None


def test_canonical_rule_preserves_independent_scoped_current_values_order_invariant():
    claims = (
        {
            "id": "subject-a-call",
            "attribute": "exam_date",
            "value": "18",
            "source_class": "specific_official_call",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
            "scope": "subject-a",
        },
        {
            "id": "subject-b-call",
            "attribute": "exam_date",
            "value": "20",
            "source_class": "specific_official_call",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
            "scope": "subject-b",
        },
    )

    semantic_results = []
    for ordered_claims in (claims, tuple(reversed(claims))):
        result = _canonical_result(*ordered_claims)
        findings = [
            finding
            for finding in result.findings
            if finding.metadata.get("attribute") == "exam_date"
        ]
        semantic_results.append(
            tuple(
                sorted(
                    (
                        finding.metadata["scope"],
                        finding.metadata["authoritative_source_id"],
                        finding.metadata["authoritative_value"],
                        finding.metadata["authority_conflict"],
                        finding.metadata["historical_source_ids"],
                    )
                    for finding in findings
                )
            )
        )

    assert semantic_results[0] == semantic_results[1]
    assert semantic_results[0] == (
        ("subject-a", "subject-a-call", "18", False, ()),
        ("subject-b", "subject-b-call", "20", False, ()),
    )


def test_canonical_rule_weak_source_cannot_fabricate_supersession():
    result = _canonical_result(
        {
            "id": "official-record",
            "attribute": "grade",
            "value": "A",
            "source_class": "official_academic_record",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "general",
        },
        {
            "id": "personal-note",
            "attribute": "grade",
            "value": "B",
            "source_class": "personal_note",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "general",
            "supersedes": ("official-record",),
        },
    )

    finding = _authority_finding(result, "grade")
    assert finding.metadata["authoritative_source_id"] == "official-record"
    assert finding.metadata["authoritative_value"] == "A"
    assert finding.metadata["superseded_source_ids"] == ()


def test_canonical_rule_honors_valid_superseded_by_relation():
    result = _canonical_result(
        {
            "id": "old-call",
            "attribute": "exam_date",
            "value": "17",
            "source_class": "specific_official_call",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
            "scope": "subject-a",
            "superseded_by": ("revised-call",),
        },
        {
            "id": "revised-call",
            "attribute": "exam_date",
            "value": "18",
            "source_class": "specific_official_call",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
            "scope": "subject-a",
        },
    )

    finding = _authority_finding(result, "exam_date")
    assert finding.metadata["authoritative_source_id"] == "revised-call"
    assert finding.metadata["authoritative_value"] == "18"
    assert finding.metadata["historical_source_ids"] == ("old-call",)


def test_canonical_rule_less_specific_peer_cannot_fabricate_supersession():
    result = _canonical_result(
        {
            "id": "specific-call",
            "attribute": "exam_date",
            "value": "18",
            "source_class": "specific_official_call",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
            "scope": "subject-a",
        },
        {
            "id": "general-call",
            "attribute": "exam_date",
            "value": "17",
            "source_class": "specific_official_call",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "general",
            "scope": "subject-a",
            "supersedes": ("specific-call",),
        },
    )

    finding = _authority_finding(result, "exam_date")
    assert finding.metadata["authoritative_source_id"] == "specific-call"
    assert finding.metadata["superseded_source_ids"] == ()


def test_canonical_rule_valid_scoped_official_supersession_preserves_history():
    result = _canonical_result(
        {
            "id": "calendar",
            "attribute": "exam_date",
            "value": "17",
            "source_class": "academic_calendar",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "general",
            "scope": "subject-a",
        },
        {
            "id": "specific-call",
            "attribute": "exam_date",
            "value": "18",
            "source_class": "specific_official_call",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
            "scope": "subject-a",
            "supersedes": ("calendar",),
        },
    )

    finding = _authority_finding(result, "exam_date")
    assert finding.metadata["authoritative_source_id"] == "specific-call"
    assert finding.metadata["authoritative_value"] == "18"
    assert finding.metadata["historical_source_ids"] == ("calendar",)


def test_canonical_rule_unknown_temporal_stronger_evidence_blocks_resolution():
    result = _canonical_result(
        {
            "id": "calendar",
            "attribute": "exam_date",
            "value": "17",
            "source_class": "academic_calendar",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "general",
            "scope": "subject-a",
            "critical": True,
        },
        {
            "id": "specific-call",
            "attribute": "exam_date",
            "value": "18",
            "source_class": "specific_official_call",
            "provenance": "grounded",
            "temporal": "unknown",
            "specificity": "specific",
            "scope": "subject-a",
            "critical": True,
        },
    )

    finding = _authority_finding(result, "exam_date")
    verification = finding.metadata["verification_need"]
    assert finding.metadata["authority_resolved"] is False
    assert finding.metadata["authority_conflict"] is True
    assert finding.metadata["authoritative_value"] is None
    assert verification["needed"] is True
    assert verification["source_class"] == "official_only"
    assert verification["read_only"] is True


def test_canonical_rule_expired_stronger_evidence_does_not_block_valid_current_value():
    result = _canonical_result(
        {
            "id": "calendar",
            "attribute": "exam_date",
            "value": "17",
            "source_class": "academic_calendar",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "general",
            "scope": "subject-a",
        },
        {
            "id": "expired-call",
            "attribute": "exam_date",
            "value": "18",
            "source_class": "specific_official_call",
            "provenance": "grounded",
            "temporal": "expired",
            "specificity": "specific",
            "scope": "subject-a",
        },
    )

    finding = _authority_finding(result, "exam_date")
    assert finding.metadata["authority_resolved"] is True
    assert finding.metadata["authoritative_source_id"] == "calendar"
    assert finding.metadata["authoritative_value"] == "17"


def test_canonical_rule_authoritative_missing_values_stay_unconfirmed():
    for value in (None, "   "):
        result = _canonical_result(
            {
                "id": "official-call",
                "attribute": "exam_date",
                "value": value,
                "source_class": "specific_official_call",
                "provenance": "grounded",
                "temporal": "valid",
                "specificity": "specific",
                "scope": "subject-a",
                "critical": True,
            }
        )

        finding = _authority_finding(result, "exam_date")
        verification = finding.metadata["verification_need"]
        assert finding.metadata["authority_resolved"] is True
        assert finding.metadata["fact_value_known"] is False
        assert finding.metadata["fact_resolved"] is False
        assert finding.metadata["authoritative_value"] == value
        assert verification["needed"] is True
        assert verification["reason"] == "missing"


def test_canonical_rule_falsey_authoritative_values_remain_known():
    for value in (0, False):
        result = _canonical_result(
            {
                "id": "official-record",
                "attribute": "grade",
                "value": value,
                "source_class": "official_academic_record",
                "provenance": "grounded",
                "temporal": "valid",
                "specificity": "specific",
                "scope": "subject-a",
                "critical": True,
            }
        )

        finding = _authority_finding(result, "grade")
        assert finding.metadata["authority_resolved"] is True
        assert finding.metadata["fact_value_known"] is True
        assert finding.metadata["fact_resolved"] is True
        assert finding.metadata["authoritative_value"] == value
        assert finding.metadata["verification_need"]["needed"] is False


def test_canonical_rule_unreferenced_grounded_source_cannot_establish_fact():
    for source_id in (None, "", "   "):
        claim = {
            "attribute": "grade",
            "value": "A",
            "source_class": "official_academic_record",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
            "critical": True,
        }
        if source_id is not None:
            claim["id"] = source_id

        finding = _authority_finding(_canonical_result(claim), "grade")
        verification = finding.metadata["verification_need"]
        assert finding.metadata["authority_resolved"] is False
        assert finding.metadata["fact_resolved"] is False
        assert finding.metadata["authoritative_source_id"] is None
        assert finding.metadata["authoritative_value"] is None
        assert verification["needed"] is True
        assert verification["source_class"] == "official_only"
        assert verification["read_only"] is True


def test_canonical_rule_referenced_grounded_source_remains_authoritative():
    finding = _authority_finding(
        _canonical_result(
            {
                "id": "official-grade-record",
                "attribute": "grade",
                "value": "A",
                "source_class": "official_academic_record",
                "provenance": "grounded",
                "temporal": "valid",
                "specificity": "specific",
                "critical": True,
            }
        ),
        "grade",
    )

    assert finding.metadata["authority_resolved"] is True
    assert finding.metadata["fact_resolved"] is True
    assert finding.metadata["authoritative_source_id"] == "official-grade-record"
    assert finding.metadata["authoritative_value"] == "A"
# ── V9-B2: malformed source authority evidence never resolves confidently ─────
# ── and never falls through to RULE_NOT_APPLICABLE. ──────────────────────────


def test_canonical_rule_malformed_claims_container_not_applicable():
    """:func:`AcademicSourceAuthorityRule.evaluate` with a malformed
    ``academic_claims`` container (scalar [7]) must NOT return
    ``RULE_NOT_APPLICABLE``.  It must produce a structured unknown result."""
    result = _canonical_result(7)
    codes = [f.code for f in result.findings]
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert "RULE_NOT_APPLICABLE" not in codes
    assert result.findings[0].metadata["authority_resolved"] is False
    assert result.findings[0].metadata["fact_resolved"] is False


def test_canonical_rule_malformed_claim_member_inside_valid_container():
    """A valid claims container that holds a non-Mapping member prevents a
    confident authority resolution, even if other claims are valid."""
    claim = {
        "id": "c1",
        "attribute": "deadline",
        "value": "2026-09-01",
        "source_class": "official_publication",
        "provenance": "grounded",
        "temporal": "valid",
        "specificity": "specific",
    }
    result = _canonical_result(claim, 7)
    for finding in result.findings:
        if finding.metadata.get("attribute") == "deadline":
            assert finding.metadata["authority_resolved"] is False
            assert finding.metadata["fact_resolved"] is False
            assert finding.metadata["authoritative_value"] is None
            return
    # If no finding matched, fail
    assert False, "Missing finding for 'deadline' attribute"


def test_canonical_rule_valid_claims_only_resolves_normally():
    """The positive regression: all-Mapping claims resolve authority."""
    finding = _authority_finding(
        _canonical_result(
            {
                "id": "official-record",
                "attribute": "deadline",
                "value": "2026-09-01",
                "source_class": "official_publication",
                "provenance": "grounded",
                "temporal": "valid",
                "specificity": "specific",
            }
        ),
        "deadline",
    )
    assert finding.metadata["authority_resolved"] is True
    assert finding.metadata["fact_resolved"] is True


# ── V10-B1: helper boundary must be fail-closed independently of canonical ──


def test_direct_helper_malformed_sources_container_no_exception():
    """sources=7 must not raise and must resolve to unknown authority."""
    result = classify_academic_source_authority(attribute="grade", sources=7)
    assert result["authority_resolved"] is False
    assert result["fact_resolved"] is False
    assert result["authority_unknown"] is True


def test_direct_helper_malformed_source_member_prevents_confident_resolution():
    """A valid grounded source plus a non-Mapping member cannot resolve as if
    the malformed member never existed."""
    valid = _grounded(
        "rec",
        source_class="official_academic_record",
        supplied=("grade",),
    )
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(valid, 7),
    )
    assert result["authority_resolved"] is False
    assert result["fact_resolved"] is False
    assert result["authority_unknown"] is True

# V10 tests


# ═══════════════════════════════════════════════════════════════════════════════
# V11-B1: exported compatibility adapter boundary normalization
#
# The exported adapter resolve_source_authority_by_attribute must normalize
# malformed containers/members BEFORE delegation so it shares the base
# helper's fail-closed boundary.  It must never filter malformed members away.
# ═══════════════════════════════════════════════════════════════════════════════


def test_v11_b1_source_authority_adapter_malformed_container_fails_closed():
    """sources=7 must not raise and must not resolve authority."""
    result = resolve_source_authority_by_attribute(attribute="grade", sources=7)
    assert result["authority_resolved"] is False
    assert result["authority_unknown"] is True


def test_v11_b1_source_authority_adapter_malformed_member_not_confidently_resolved():
    """A malformed member must not be silently filtered; overall authority
    evidence is incomplete, so the result must not resolve confidently."""
    valid = _grounded(
        "rec",
        source_class="official_academic_record",
        supplied=("grade",),
    )
    result = resolve_source_authority_by_attribute(
        attribute="grade",
        sources=(valid, 7),
    )
    assert result["authority_resolved"] is False
    assert result["authority_unknown"] is True


def test_v11_b1_source_authority_adapter_fully_valid_legacy_source_resolves():
    """Fully-valid legacy behavior must remain green."""
    result = resolve_source_authority_by_attribute(
        attribute="grade",
        sources=(
            {
                "source_id": "rec",
                "source_type": "official",
                "supplied_attributes": ("grade",),
                "value": 8.5,
            },
        ),
    )
    assert result["authority_resolved"] is True
    assert result["authority"] == "official"


# ═══════════════════════════════════════════════════════════════════════════════
# V11-B3: Source Authority semantic Mapping validation
#
# Mapping instance != semantically valid evidence.  An opaque Mapping member
# ({}, {"foo": "bar"}) has an unknown semantic relationship to any attribute
# and must fail the whole resolution closed.
# ═══════════════════════════════════════════════════════════════════════════════


def test_v11_b3_source_authority_empty_mapping_member_not_confident():
    """(valid_grounded_source, {}) must not resolve authority confidently."""
    valid = _grounded(
        "rec",
        source_class="official_academic_record",
        supplied=("grade",),
    )
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(valid, {}),
    )
    assert result["authority_resolved"] is False
    assert result["fact_resolved"] is False
    assert result["authority_unknown"] is True


def test_v11_b3_source_authority_arbitrary_mapping_member_not_confident():
    """A Mapping with no semantic identity content ({'foo': 'bar'}) is also
    opaque supplied evidence and must not resolve confidently."""
    valid = _grounded(
        "rec",
        source_class="official_academic_record",
        supplied=("grade",),
    )
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(valid, {"foo": "bar"}),
    )
    assert result["authority_resolved"] is False
    assert result["authority_unknown"] is True


def test_v11_b3_canonical_source_authority_opaque_claim_leaves_evidence_gap():
    """academic_claims=[valid_claim, {}] must not resolve globally; the opaque
    claim leaves a malformed/unknown evidence gap and no fully confident
    resolution."""
    result = _canonical_result(
        {
            "id": "rec",
            "attribute": "grade",
            "value": 8.5,
            "source_class": "official_academic_record",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "general",
        },
        {},
    )
    assert any(
        gap.code == "SOURCE_AUTHORITY_EVIDENCE_MALFORMED"
        for gap in result.gaps
    )
    grade_finding = _authority_finding(result, "grade")
    assert grade_finding.metadata["authority_resolved"] is False
    assert grade_finding.metadata["authority_unknown"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# V12-B2: partial same-attribute Source Authority evidence
#
# A source that claims the target attribute but carries neither a usable fact
# value nor any authority/grounding identity cannot corroborate, contradict, or
# be ignored.  It must force uncertain authority instead of letting a valid
# same-attribute source resolve alone.  Fully valid unrelated-attribute
# evidence must NOT poison the target attribute.
# ═══════════════════════════════════════════════════════════════════════════════


def test_v12_b2_source_partial_supplied_attributes_not_resolved():
    """(valid grade source, {"source_id":"junk","supplied_attributes":["grade"]})
    must not resolve grade confidently."""
    valid = _grounded(
        "s1",
        source_class="official_academic_record",
        supplied=("grade",),
    )
    partial = {"source_id": "junk", "supplied_attributes": ["grade"]}
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(valid, partial),
    )
    assert result["authority_resolved"] is False
    assert result["fact_resolved"] is False
    assert result["authority_unknown"] is True


def test_v12_b2_source_partial_bare_attribute_not_resolved():
    """(valid grade source, {"attribute":"grade"}) must not resolve grade
    confidently."""
    valid = _grounded(
        "s1",
        source_class="official_academic_record",
        supplied=("grade",),
    )
    partial = {"attribute": "grade"}
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(valid, partial),
    )
    assert result["authority_resolved"] is False
    assert result["authority_unknown"] is True


def test_v12_b2_source_valid_authority_only_still_resolves():
    """An authority-establishing source (class/provenance/temporal, no inline
    value) is usable and must NOT be flagged as incomplete."""
    older = _grounded(
        "reg",
        source_class="regulation",
        supplied=("requirement",),
        temporal="valid",
    )
    newer = _grounded(
        "new",
        source_class="personal_note",
        supplied=("requirement",),
        temporal="valid",
    )
    result = classify_academic_source_authority(
        attribute="requirement",
        sources=(older, newer),
    )
    assert result["authoritative_source_id"] == "reg"
    assert result["authority_resolved"] is True


def test_v12_b2_source_valid_unrelated_attribute_does_not_poison():
    """A fully valid source for a different attribute must NOT make the target
    attribute resolution uncertain."""
    grade = _grounded(
        "s1",
        source_class="official_academic_record",
        supplied=("grade",),
    )
    enrollment = _grounded(
        "s2",
        source_class="official_academic_record",
        supplied=("enrollment_status",),
    )
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(grade, enrollment),
    )
    assert result["authority_resolved"] is True
    assert result["authoritative_source_id"] == "s1"


def test_v12_b2_canonical_partial_same_attribute_evidence_unresolved():
    """academic_claims=[valid deadline claim, partial deadline claim without
    value] must keep authority/fact unresolved and emit an evidence gap."""
    result = _canonical_result(
        {
            "id": "official",
            "attribute": "deadline",
            "value": "2026-09-01",
            "source_class": "official_publication",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
        },
        {"id": "junk", "attribute": "deadline"},
    )
    finding = _authority_finding(result, "deadline")
    assert finding.metadata["authority_resolved"] is False
    assert finding.metadata["fact_resolved"] is False
    assert finding.metadata["authority_unknown"] is True
    assert any(
        gap.code == "SOURCE_AUTHORITY_EVIDENCE_MALFORMED"
        for gap in result.gaps
    )


# ═══════════════════════════════════════════════════════════════════════════════
# V13-B1: semantic evidence validation
#
# A single arbitrary authority metadata string must NOT convert incomplete
# evidence into a valid authority-only source.  Malformed supplied_attributes
# must NOT become "no relevant supplied attribute".  An identity-looking key is
# NOT semantic completeness.
# ═══════════════════════════════════════════════════════════════════════════════


def _valid_grade_source():
    return _grounded(
        "s1",
        source_class="official_academic_record",
        supplied=("grade",),
    )


def test_v13_b1_partial_arbitrary_provenance_does_not_resolve():
    """(valid grade source, partial with provenance='garbage') must NOT resolve.

    A single arbitrary non-empty metadata string is not semantic completeness."""
    valid = _valid_grade_source()
    partial = {
        "source_id": "junk",
        "supplied_attributes": ["grade"],
        "provenance": "garbage",
    }
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(valid, partial),
    )
    assert result["authority_resolved"] is False
    assert result["fact_resolved"] is False
    assert result["authority_unknown"] is True


def test_v13_b1_partial_source_class_only_does_not_resolve():
    """A value-less same-attribute source with only a recognized source_class
    does not carry the coherent authority-only identity."""
    valid = _valid_grade_source()
    partial = {
        "source_id": "junk",
        "supplied_attributes": ["grade"],
        "source_class": "official_academic_record",
    }
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(valid, partial),
    )
    assert result["authority_resolved"] is False
    assert result["authority_unknown"] is True


def test_v13_b1_partial_temporal_only_does_not_resolve():
    valid = _valid_grade_source()
    partial = {
        "source_id": "junk",
        "supplied_attributes": ["grade"],
        "temporal": "valid",
    }
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(valid, partial),
    )
    assert result["authority_resolved"] is False
    assert result["authority_unknown"] is True


def test_v13_b1_partial_specificity_only_does_not_resolve():
    valid = _valid_grade_source()
    partial = {
        "source_id": "junk",
        "supplied_attributes": ["grade"],
        "specificity": "general",
    }
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(valid, partial),
    )
    assert result["authority_resolved"] is False
    assert result["authority_unknown"] is True


def test_v13_b1_coherent_authority_only_source_remains_supported():
    """A value-less source carrying the full coherent recognized authority
    identity (source_class + provenance + temporal + specificity) stays usable
    and must NOT be flagged incomplete."""
    older = _grounded(
        "reg",
        source_class="regulation",
        supplied=("requirement",),
        provenance="grounded",
        temporal="valid",
        specificity="general",
    )
    newer = _grounded(
        "new",
        source_class="personal_note",
        supplied=("requirement",),
        temporal="valid",
    )
    result = classify_academic_source_authority(
        attribute="requirement",
        sources=(older, newer),
    )
    assert result["authority_resolved"] is True
    assert result["authoritative_source_id"] == "reg"


@pytest.mark.parametrize(
    "malformed",
    [
        ({"source_id": "junk", "supplied_attributes": "grade"}),
        ({"source_id": "junk", "supplied_attributes": 7}),
        ({"source_id": "junk", "supplied_attributes": {}}),
        ({"source_id": "junk", "supplied_attributes": [7]}),
        ({"source_id": "junk", "supplied_attributes": [""]}),
        ({"source_id": "junk", "supplied_attributes": ["grade", 7]}),
    ],
)
def test_v13_b1_malformed_supplied_attributes_fails_closed(malformed):
    """A malformed attribute carrier must NOT become 'no relevant supplied
    attribute'.  It is relationship-unknown and fails the resolution closed."""
    valid = _valid_grade_source()
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(valid, malformed),
    )
    assert result["authority_resolved"] is False
    assert result["fact_resolved"] is False
    assert result["authority_unknown"] is True


def test_v13_b1_canonicical_partial_arbitrary_provenance_unresolved():
    """academic_claims=[valid deadline claim, junk provenance='garbage' claim]
    must not resolve deadline confidently and must emit an evidence gap."""
    result = _canonical_result(
        {
            "id": "official",
            "attribute": "deadline",
            "value": "2026-09-01",
            "source_class": "official_publication",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
        },
        {
            "id": "junk",
            "attribute": "deadline",
            "provenance": "garbage",
        },
    )
    finding = _authority_finding(result, "deadline")
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert finding.metadata["authority_resolved"] is False
    assert finding.metadata["fact_resolved"] is False
    assert finding.metadata["authority_unknown"] is True
    assert any(
        gap.code == "SOURCE_AUTHORITY_EVIDENCE_MALFORMED"
        for gap in result.gaps
    )


def test_v13_b1_canonical_relation_unknown_claim_never_buckets_relevant():
    """academic_claims=[valid deadline claim, {'id':'junk','value':...}] groups
    the junk claim under no known attribute; deadline must NOT resolve
    confidently because the relationship of the junk claim is unknown."""
    result = _canonical_result(
        {
            "id": "official",
            "attribute": "deadline",
            "value": "2026-09-01",
            "source_class": "official_publication",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
        },
        {"id": "junk", "value": "2026-09-02"},
    )
    finding = _authority_finding(result, "deadline")
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert finding.metadata["authority_resolved"] is False
    assert finding.metadata["fact_resolved"] is False
    assert finding.metadata["authority_unknown"] is True
    assert any(
        gap.code == "SOURCE_AUTHORITY_EVIDENCE_MALFORMED"
        for gap in result.gaps
    )


# ═══════════════════════════════════════════════════════════════════════════════
# V13-B2: malformed scope must never become global
#
# scope absent == unscoped (existing), scope valid string == scoped (existing),
# scope present-but-malformed == fail closed (never None/unscoped/global).
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("bad_scope", [7, "", [], ["course:A"], {}, 0.0])
def test_v13_b2_malformed_source_scope_never_global(bad_scope):
    """A same-attribute source with a malformed scope must fail closed; it must
    not resolve under the unscoped/global None semantics."""
    valid = _valid_grade_source()
    scoped = _grounded(
        "bad",
        source_class="official_academic_record",
        supplied=("grade",),
    )
    scoped["scope"] = bad_scope
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(valid, scoped),
    )
    assert result["authority_resolved"] is False
    assert result["fact_resolved"] is False
    assert result["authority_unknown"] is True


def test_v13_b2_absent_scope_retains_unscoped_semantics():
    """scope key absent != malformed: unscoped resolution is preserved."""
    valid = _valid_grade_source()
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(valid,),
    )
    assert result["authority_resolved"] is True


def test_v13_b2_valid_string_scope_retains_scoped_semantics():
    """scope='course:A' == scoped resolution: relevant in-scope, excluded
    out-of-scope, exactly like the existing resolver semantics."""
    mine = _grounded(
        "mine",
        source_class="official_academic_record",
        supplied=("deadline",),
        scope="course:A",
    )
    other = _grounded(
        "other",
        source_class="subject_guide",
        supplied=("deadline",),
        scope="course:B",
    )
    result = classify_academic_source_authority(
        attribute="deadline",
        sources=(mine, other),
        scope="course:A",
    )
    assert result["authority_resolved"] is True
    assert result["authoritative_source_id"] == "mine"


@pytest.mark.parametrize("bad_scope", [7, ""])
def test_v13_b2_requested_scope_fails_closed(bad_scope):
    """A malformed public requested scope must fail closed, not act as global."""
    valid = _valid_grade_source()
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(valid,),
        scope=bad_scope,
    )
    assert result["authority_resolved"] is False
    assert result["authority_unknown"] is True


def test_v13_b2_canonical_source_authority_malformed_scope_never_global():
    """A canonical claim carrying scope=7 must not emit scope=None /
    authority_resolved=True; malformed scope evidence fails closed with a gap."""
    result = _canonical_result(
        {
            "id": "official",
            "attribute": "deadline",
            "value": "2026-09-01",
            "source_class": "official_publication",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
            "scope": 7,
        }
    )
    finding = _authority_finding(result, "deadline")
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert finding.metadata["authority_resolved"] is False
    assert finding.metadata["fact_resolved"] is False
    assert finding.metadata["authority_unknown"] is True
    assert finding.metadata["scope"] != "course:A"
    assert any(
        gap.code == "SOURCE_AUTHORITY_EVIDENCE_MALFORMED"
        for gap in result.gaps
    )


# ═══════════════════════════════════════════════════════════════════════════════
# V14-B1: singular scalar source_id must never be unwrapped from a collection
#
# _usable_reference() recursively unwraps list/tuple values.  That is valid for
# genuinely plural references but NOT valid for fields that contractually
# represent a single scalar identity.  source_id=["junk"] must NOT become
# authoritative_source_id="junk".
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("malformed_id", [["junk"], ("junk",), 7, True])
def test_v14_b1_source_id_collection_or_nonstring_never_authoritative(malformed_id):
    """A collection-shaped or non-string source_id must NOT be unwrapped
    into a scalar authority identity."""
    source = {
        "source_id": malformed_id,
        "supplied_attributes": ["grade"],
        "value": 8.5,
        "source_class": "official_academic_record",
        "provenance": "grounded",
        "temporal": "valid",
        "specificity": "general",
    }
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(source,),
    )
    assert result["authority_resolved"] is False
    assert result["fact_resolved"] is False
    assert result["authority_unknown"] is True


@pytest.mark.parametrize("malformed_id", [["junk"], ("junk",), 7, True])
def test_v14_b1_adapter_source_id_collection_never_authoritative(malformed_id):
    """The adapter must share base semantics for collection-shaped source_id."""
    source = {
        "source_id": malformed_id,
        "supplied_attributes": ["grade"],
        "value": 8.5,
        "source_class": "official_academic_record",
        "provenance": "grounded",
        "temporal": "valid",
        "specificity": "general",
    }
    result = resolve_source_authority_by_attribute(
        attribute="grade",
        sources=(source,),
    )
    assert result["authority_resolved"] is False
    assert result["authority_unknown"] is True


@pytest.mark.parametrize("malformed_id", [["junk"], ("junk",), 7, True])
def test_v14_b1_canonical_source_id_collection_never_authoritative(malformed_id):
    """Canonical AcademicSourceAuthorityRule with collection-shaped claim id
    must not resolve confidently."""
    result = _canonical_result(
        {
            "id": malformed_id,
            "attribute": "grade",
            "value": 8.5,
            "source_class": "official_academic_record",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "general",
        }
    )
    finding = _authority_finding(result, "grade")
    assert finding.metadata["authority_resolved"] is False
    assert finding.metadata["fact_resolved"] is False


def test_v14_b1_scalar_source_id_still_works():
    """Positive control: a proper scalar source_id must remain supported."""
    source = {
        "source_id": "s1",
        "supplied_attributes": ["grade"],
        "value": 8.5,
        "source_class": "official_academic_record",
        "provenance": "grounded",
        "temporal": "valid",
        "specificity": "general",
    }
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(source,),
    )
    assert result["authority_resolved"] is True
    assert result["authoritative_source_id"] == "s1"


# ═══════════════════════════════════════════════════════════════════════════════
# V14-B1: unusable identity must NOT disappear from epistemic resolution
#
# A conflicting source whose source_id is unusable (absent, blank, None, [], 7)
# cannot simply be excluded while a valid sibling wins confidently.  The
# conflicting fact cannot disappear merely because its identity is unusable.
# ═══════════════════════════════════════════════════════════════════════════════


def _valid_grade_source_with_value():
    return {
        "source_id": "s1",
        "supplied_attributes": ["grade"],
        "value": 8.5,
        "source_class": "official_academic_record",
        "provenance": "grounded",
        "temporal": "valid",
        "specificity": "general",
    }


@pytest.mark.parametrize(
    "conflicting_id",
    [
        pytest.param("ABSENT", id="absent"),
        pytest.param("", id="blank"),
        pytest.param("   ", id="whitespace"),
        pytest.param(None, id="none"),
        pytest.param([], id="empty_list"),
        pytest.param(7, id="integer"),
    ],
)
def test_v14_b1_conflicting_source_unusable_id_forces_uncertainty(conflicting_id):
    """A conflicting source with an unusable source_id must not disappear
    while a valid sibling resolves confidently."""
    valid = _valid_grade_source_with_value()
    conflicting = {
        "supplied_attributes": ["grade"],
        "value": 9.0,
        "source_class": "official_academic_record",
        "provenance": "grounded",
        "temporal": "valid",
        "specificity": "general",
    }
    if conflicting_id != "ABSENT":
        conflicting["source_id"] = conflicting_id
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(valid, conflicting),
    )
    assert result["authority_resolved"] is False
    assert result["fact_resolved"] is False
    assert result["authority_unknown"] is True


@pytest.mark.parametrize(
    "conflicting_id",
    [
        pytest.param("ABSENT", id="absent"),
        pytest.param("", id="blank"),
        pytest.param(None, id="none"),
    ],
)
def test_v14_b1_canonical_conflicting_source_unusable_id_unresolved(conflicting_id):
    """Canonical Source Authority: an unreferenced conflicting source must NOT
    let the referenced sibling resolve confidently."""
    valid_claim = {
        "id": "official",
        "attribute": "grade",
        "value": 8.5,
        "source_class": "official_academic_record",
        "provenance": "grounded",
        "temporal": "valid",
        "specificity": "general",
    }
    conflicting_claim = {
        "attribute": "grade",
        "value": 9.0,
        "source_class": "official_academic_record",
        "provenance": "grounded",
        "temporal": "valid",
        "specificity": "general",
    }
    if conflicting_id != "ABSENT":
        conflicting_claim["id"] = conflicting_id
    result = _canonical_result(valid_claim, conflicting_claim)
    finding = _authority_finding(result, "grade")
    assert finding.metadata["authority_resolved"] is False
    assert finding.metadata["fact_resolved"] is False


def test_v14_b1_valid_usable_source_id_still_resolves():
    """Positive: valid usable source_id remains green."""
    valid = _valid_grade_source_with_value()
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(valid,),
    )
    assert result["authority_resolved"] is True
    assert result["authoritative_source_id"] == "s1"


# ═══════════════════════════════════════════════════════════════════════════════
# V14-B2: relation-unknown source must NOT become safely irrelevant
#
# A source that has a fact value but no attribute carrier (no supplied_attributes
# and no attribute field) has an UNKNOWN relationship to the target attribute.
# It must NOT be silently excluded while a valid source resolves confidently.
#
# supplied_attributes=None (present-but-None) is malformed, NOT absent.
# attribute=None is malformed, NOT absent.
# ═══════════════════════════════════════════════════════════════════════════════


def test_v14_b2_source_with_value_no_carrier_is_not_safely_irrelevant():
    """A source with a fact value but no attribute carrier (no supplied_attributes
    / attribute) has an unknown relationship.  It must NOT let a valid source
    for the target attribute resolve confidently."""
    valid = _valid_grade_source_with_value()
    relation_unknown = {
        "source_id": "junk",
        "value": 9.0,
    }
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(valid, relation_unknown),
    )
    assert result["authority_resolved"] is False
    assert result["fact_resolved"] is False
    assert result["authority_unknown"] is True


def test_v14_b2_source_with_authority_no_carrier_is_not_safely_irrelevant():
    """A source with coherent authority metadata but no attribute carrier has
    an unknown relationship — it is NOT valid unrelated evidence."""
    valid = _valid_grade_source_with_value()
    relation_unknown = {
        "source_id": "junk",
        "value": 9.0,
        "source_class": "official_academic_record",
        "provenance": "grounded",
        "temporal": "valid",
        "specificity": "general",
    }
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(valid, relation_unknown),
    )
    assert result["authority_resolved"] is False
    assert result["fact_resolved"] is False
    assert result["authority_unknown"] is True


def test_v14_b2_supplied_attributes_none_is_not_absent():
    """supplied_attributes=None (present but null) is a malformed carrier,
    distinct from the field being absent.  It must fail closed."""
    valid = _valid_grade_source_with_value()
    malformed = {
        "source_id": "junk",
        "supplied_attributes": None,
        "value": 9.0,
    }
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(valid, malformed),
    )
    assert result["authority_resolved"] is False
    assert result["fact_resolved"] is False
    assert result["authority_unknown"] is True


def test_v14_b2_attribute_none_is_not_absent():
    """attribute=None (present but null) is a malformed carrier, distinct from
    the field being absent.  It must NOT be treated as safely irrelevant."""
    valid = _valid_grade_source_with_value()
    malformed = {
        "source_id": "junk",
        "attribute": None,
        "value": 9.0,
    }
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(valid, malformed),
    )
    assert result["authority_resolved"] is False
    assert result["fact_resolved"] is False
    assert result["authority_unknown"] is True


def test_v14_b2_valid_unrelated_source_remains_safely_irrelevant():
    """Positive: a source that explicitly supplies a different attribute via
    valid supplied_attributes remains safely irrelevant."""
    grade = _valid_grade_source_with_value()
    enrollment = {
        "source_id": "enrollment-source",
        "supplied_attributes": ["enrollment_status"],
        "value": "active",
        "source_class": "official_academic_record",
        "provenance": "grounded",
        "temporal": "valid",
        "specificity": "general",
    }
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(grade, enrollment),
    )
    assert result["authority_resolved"] is True
    assert result["authoritative_source_id"] == "s1"


def test_v14_b2_adapter_source_no_carrier_forces_uncertainty():
    """The adapter must not filter relation-unknown evidence away."""
    valid = {
        "source_id": "s1",
        "source_type": "official",
        "supplied_attributes": ("grade",),
        "value": 8.5,
    }
    relation_unknown = {
        "source_id": "junk",
        "value": 9.0,
    }
    result = resolve_source_authority_by_attribute(
        attribute="grade",
        sources=(valid, relation_unknown),
    )
    assert result["authority_resolved"] is False
    assert result["authority_unknown"] is True


def test_v14_b2_canonical_source_no_carrier_not_safely_irrelevant():
    """Canonical Source Authority: a claim with value but no attribute carrier
    has an unknown relationship and must not let valid claims resolve."""
    result = _canonical_result(
        {
            "id": "official",
            "attribute": "grade",
            "value": 8.5,
            "source_class": "official_academic_record",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "general",
        },
        {
            "id": "junk",
            "value": 9.0,
        },
    )
    finding = _authority_finding(result, "grade")
    assert finding.metadata["authority_resolved"] is False
    assert finding.metadata["fact_resolved"] is False


def test_v14_b2_supplied_attributes_empty_list_is_known_unrelated():
    """Positive: supplied_attributes=[] is an explicit empty carrier set.
    The source is known to supply nothing and remains safely irrelevant."""
    valid = _valid_grade_source_with_value()
    empty_carrier = {
        "source_id": "unrelated",
        "supplied_attributes": [],
        "value": 9.0,
        "source_class": "official_academic_record",
        "provenance": "grounded",
        "temporal": "valid",
        "specificity": "general",
    }
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(valid, empty_carrier),
    )
    assert result["authority_resolved"] is True
    assert result["authoritative_source_id"] == "s1"


# ── V15-B2 / V16: relation-unknown does not require an inline value ─────────


def _v16_relation_unknown_authority_only_source():
    return {
        "source_id": "junk",
        "source_class": "official_academic_record",
        "provenance": "grounded",
        "temporal": "valid",
        "specificity": "general",
    }


@pytest.mark.parametrize(
    "relation_unknown",
    (_v16_relation_unknown_authority_only_source(), {"source_id": "junk"}),
    ids=("authority-only", "identity-only"),
)
def test_v16_relation_unknown_without_value_forces_base_uncertainty(
    relation_unknown,
):
    result = classify_academic_source_authority(
        attribute="grade",
        sources=(_valid_grade_source_with_value(), relation_unknown),
    )
    assert result["authority_resolved"] is False
    assert result["fact_resolved"] is False
    assert result["authority_unknown"] is True


@pytest.mark.parametrize(
    "relation_unknown",
    (_v16_relation_unknown_authority_only_source(), {"source_id": "junk"}),
    ids=("authority-only", "identity-only"),
)
def test_v16_relation_unknown_without_value_forces_adapter_uncertainty(
    relation_unknown,
):
    result = resolve_source_authority_by_attribute(
        attribute="grade",
        sources=(_valid_grade_source_with_value(), relation_unknown),
    )
    assert result["authority_resolved"] is False
    assert result["authority_unknown"] is True


@pytest.mark.parametrize(
    "unknown_claim",
    (
        {
            "id": "junk",
            "source_class": "official_academic_record",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "general",
        },
        {"id": "junk"},
    ),
    ids=("authority-only", "identity-only"),
)
def test_v16_relation_unknown_without_value_forces_canonical_uncertainty(
    unknown_claim,
):
    result = _canonical_result(
        {
            "id": "official",
            "attribute": "grade",
            "value": 8.5,
            "source_class": "official_academic_record",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "general",
        },
        unknown_claim,
    )
    finding = _authority_finding(result, "grade")
    assert finding.metadata["authority_resolved"] is False
    assert finding.metadata["fact_resolved"] is False
    assert finding.metadata["authority_unknown"] is True


def test_v16_source_authority_wrapper_does_not_recoerce_collection_claim_id():
    result = _canonical_result(
        {
            "id": ["junk"],
            "attribute": "grade",
            "value": 8.5,
            "source_class": "official_academic_record",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "general",
        }
    )
    finding = _authority_finding(result, "grade")
    assert finding.metadata["authority_resolved"] is False
    assert finding.references == ()


# ═══════════════════════════════════════════════════════════════════════════════
# V16-B1 / V17: flat plural containers require strict scalar members
# ═══════════════════════════════════════════════════════════════════════════════


def _v17_grade_source(source_id, value):
    return {
        "source_id": source_id,
        "supplied_attributes": ["grade"],
        "value": value,
        "source_class": "official_academic_record",
        "provenance": "grounded",
        "temporal": "valid",
        "specificity": "general",
    }


def _v17_grade_claim(source_id, value):
    return {
        "id": source_id,
        "attribute": "grade",
        "value": value,
        "source_class": "official_academic_record",
        "provenance": "grounded",
        "temporal": "valid",
        "specificity": "general",
    }


@pytest.mark.parametrize("relation_field", ("supersedes", "superseded_by"))
@pytest.mark.parametrize(
    "malformed_member",
    (["old"], ("old",), "", 7, True, None, {}, [], ()),
)
def test_v17_malformed_supersession_member_preserves_unresolved_conflict(
    relation_field,
    malformed_member,
):
    old = _v17_grade_source("old", 8.5)
    new = _v17_grade_source("new", 9.0)
    target = new if relation_field == "supersedes" else old
    target[relation_field] = [malformed_member]

    result = classify_academic_source_authority(
        attribute="grade",
        sources=(old, new),
    )

    assert result["authority_resolved"] is False
    assert result["conflict"] is True
    assert result["superseded_sources"] == ()
    evaluated = next(
        source
        for source in result["matched_sources"]
        if source["source_id"] == target["source_id"]
    )
    assert evaluated[f"{relation_field}_malformed"] is True


@pytest.mark.parametrize("relation_field", ("supersedes", "superseded_by"))
@pytest.mark.parametrize("nested_type", (list, tuple))
def test_v17_canonical_malformed_supersession_cannot_resolve(
    relation_field,
    nested_type,
):
    old = _v17_grade_claim("old", 8.5)
    new = _v17_grade_claim("new", 9.0)
    target = new if relation_field == "supersedes" else old
    target[relation_field] = [nested_type(("old" if target is new else "new",))]

    finding = _authority_finding(_canonical_result(old, new), "grade")

    assert finding.metadata["authority_resolved"] is False
    assert finding.metadata["authority_conflict"] is True
    assert finding.metadata["superseded_source_ids"] == ()
    evaluated = next(
        source
        for source in finding.metadata["matched_sources"]
        if source["source_id"] == ("new" if target is new else "old")
    )
    assert evaluated[f"{relation_field}_malformed"] is True


@pytest.mark.parametrize("container_type", (list, tuple))
def test_v17_flat_supersedes_container_remains_valid(container_type):
    old = _v17_grade_source("old", 8.5)
    new = _v17_grade_source("new", 9.0)
    new["supersedes"] = container_type(("old",))

    result = classify_academic_source_authority(
        attribute="grade",
        sources=(old, new),
    )

    assert result["authority_resolved"] is True
    assert result["authoritative_source_id"] == "new"
    assert result["superseded_sources"] == ("old",)
    evaluated_new = next(
        source
        for source in result["matched_sources"]
        if source["source_id"] == "new"
    )
    assert evaluated_new["supersedes_malformed"] is False


@pytest.mark.parametrize("relation_field", ("supersedes", "superseded_by"))
def test_v17_valid_reference_cannot_hide_malformed_sibling(relation_field):
    old = _v17_grade_source("old", 8.5)
    new = _v17_grade_source("new", 9.0)
    target = new if relation_field == "supersedes" else old
    valid_reference = "old" if target is new else "new"
    target[relation_field] = [valid_reference, ["malformed-sibling"]]

    result = classify_academic_source_authority(
        attribute="grade",
        sources=(old, new),
    )

    assert result["authority_resolved"] is False
    assert result["conflict"] is True
    assert result["superseded_sources"] == ()
    evaluated = next(
        source
        for source in result["matched_sources"]
        if source["source_id"] == target["source_id"]
    )
    assert evaluated[f"{relation_field}_malformed"] is True
