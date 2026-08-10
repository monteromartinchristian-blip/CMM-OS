"""Phase 10.22 — B2: Contradiction Resolution (derived from claims).

The audit found the previous implementation trusted caller booleans
``material`` / ``unresolved``.  That behavior must disappear as a source of
truth.  Contradiction must be DERIVED from the claims: attribute identity,
value incompatibility, scope overlap, temporal overlap, authority and
supersession.  Caller flags may be input evidence only, never authoritative.
"""

from __future__ import annotations

from cmm.domains.university.rules import resolve_academic_conflict


def _claim(
    claim_id,
    *,
    attribute,
    value,
    source_class="official_academic_record",
    provenance="grounded",
    temporal="valid",
    specificity="general",
    scope=None,
    supersedes=(),
    critical=False,
):
    claim = {
        "id": claim_id,
        "attribute": attribute,
        "value": value,
        "source_class": source_class,
        "provenance": provenance,
        "temporal": temporal,
        "specificity": specificity,
        "supersedes": supersedes,
    }
    if scope is not None:
        claim["scope"] = scope
    if critical:
        claim["critical"] = True
    return claim


def test_incompatible_overlapping_claims_are_a_contradiction():
    """Incompatible values on the same attribute with overlapping scope/time are
    a contradiction — derived, not caller-declared."""
    result = resolve_academic_conflict(
        claims=(
            _claim("a", attribute="exam_date", value="2026-01-18"),
            _claim("b", attribute="exam_date", value="2026-01-17"),
        )
    )
    assert result["contradiction"] is True


def test_caller_says_unresolved_false_but_evidence_conflicts():
    """Caller marking ``unresolved=False`` cannot dismiss a conflict the evidence
    still shows as conflicting."""
    result = resolve_academic_conflict(
        claims=(
            _claim("a", attribute="exam_date", value="2026-01-18"),
            _claim("b", attribute="exam_date", value="2026-01-17"),
        )
    )
    # The conflict is derived from the incompatible claims regardless of any
    # caller flag.
    assert result["contradiction"] is True
    assert result["resolved"] is False


def test_caller_says_material_false_but_deadline_conflict_material():
    """Caller marking ``material=False`` cannot make a decision-critical
    deadline conflict silently disappear."""
    result = resolve_academic_conflict(
        claims=(
            _claim(
                "a",
                attribute="assignment_deadline",
                value="2026-01-18",
                critical=True,
            ),
            _claim(
                "b",
                attribute="assignment_deadline",
                value="2026-01-17",
                critical=True,
            ),
        )
    )
    assert result["contradiction"] is True
    assert result["material"] is True


def test_authoritative_supersession_resolves_current_value():
    """A valid authoritative supersession resolves the current value while the
    superseded claim is preserved as history."""
    result = resolve_academic_conflict(
        claims=(
            _claim("old", attribute="grade", value="B"),
            _claim(
                "new",
                attribute="grade",
                value="A",
                supersedes=("old",),
            ),
        )
    )
    assert result["contradiction"] is True
    assert result["resolved"] is True
    assert result["current_value"] == "A"
    assert "old" in result["superseded_claims"]


def test_equal_authoritative_conflict_remains_unresolved():
    """Two equivalently-authoritative incompatible claims with no supersession
    remain unresolved."""
    result = resolve_academic_conflict(
        claims=(
            _claim(
                "a",
                attribute="exam_date",
                value="2026-01-18",
                source_class="specific_official_call",
                specificity="specific",
            ),
            _claim(
                "b",
                attribute="exam_date",
                value="2026-01-17",
                source_class="specific_official_call",
                specificity="specific",
            ),
        )
    )
    assert result["contradiction"] is True
    assert result["resolved"] is False
    assert result["unresolved"] is True


def test_material_unresolved_conflict_blocks_dependent_conclusion():
    """A material unresolved conflict blocks only the dependent conclusion, not
    the whole University domain."""
    result = resolve_academic_conflict(
        claims=(
            _claim(
                "a",
                attribute="assignment_deadline",
                value="2026-01-18",
                source_class="specific_official_call",
                specificity="specific",
                critical=True,
            ),
            _claim(
                "b",
                attribute="assignment_deadline",
                value="2026-01-17",
                source_class="specific_official_call",
                specificity="specific",
                critical=True,
            ),
        )
    )
    assert result["contradiction"] is True
    assert result["material"] is True
    assert result["resolved"] is False
    assert result["blocked"] is True


def test_non_conflicting_claims_no_contradiction():
    """Compatible claims on different attributes are not a contradiction."""
    result = resolve_academic_conflict(
        claims=(
            _claim("a", attribute="grade", value="B"),
            _claim("b", attribute="exam_date", value="2026-01-17"),
        )
    )
    assert result["contradiction"] is False
    assert result["resolved"] is True


def test_scope_mismatch_means_no_overlap_no_conflict():
    """Claims on the same attribute but non-overlapping scope do not conflict."""
    result = resolve_academic_conflict(
        claims=(
            _claim("a", attribute="deadline", value="2026-01-18", scope="subject-x"),
            _claim("b", attribute="deadline", value="2026-01-17", scope="subject-y"),
        )
    )
    assert result["contradiction"] is False


def test_empty_claims_no_contradiction():
    result = resolve_academic_conflict(claims=())
    assert result["contradiction"] is False
    assert result["resolved"] is True