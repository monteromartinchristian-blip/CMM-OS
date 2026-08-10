"""Phase 10.22 — B1: Academic Source Authority (grounded, attribute-specific).

The audit found the previous implementation ranked by a caller-supplied
``source_type`` plus ``supplied_attributes``.  That is insufficient: authority
must derive from attribute + source class + provenance + temporal validity +
specificity + scope, and a caller cannot fabricate ``official`` by setting a
field.  These tests pin the grounded semantics.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.university import build_university_rules
from cmm.domains.university.rules import classify_academic_source_authority

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
    assert "calendar" in finding.metadata["historical_source_ids"]


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
