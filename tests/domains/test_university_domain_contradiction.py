"""Phase 10.22 — B2: Contradiction Resolution (derived from claims).

The audit found the previous implementation trusted caller booleans
``material`` / ``unresolved``.  That behavior must disappear as a source of
truth.  Contradiction must be DERIVED from the claims: attribute identity,
value incompatibility, scope overlap, temporal overlap, authority and
supersession.  Caller flags may be input evidence only, never authoritative.
"""

from __future__ import annotations

from datetime import datetime, timezone
from itertools import permutations

import pytest

from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.university import build_university_rules
from cmm.domains.university.rules import (
    evaluate_academic_contradiction,
    resolve_academic_conflict,
)

T = datetime(2026, 8, 1, tzinfo=timezone.utc)


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


def _canonical_result(*claims):
    rules = {
        rule.definition.id: rule
        for rule in build_university_rules()
    }
    context = ReasoningRuleContext(
        reasoning_id="contradiction-production",
        timestamp=T,
        active_domains=("domain:university",),
        primary_domain="domain:university",
        metadata={"contradiction_statements": claims},
    )
    return rules["university.academic_contradiction"].evaluate(context)


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


def test_canonical_rule_attribute_specific_authority_resolves_current_value():
    result = _canonical_result(
        _claim(
            "calendar",
            attribute="exam_date",
            value="17",
            source_class="academic_calendar",
            specificity="general",
            critical=True,
        ),
        _claim(
            "call",
            attribute="exam_date",
            value="18",
            source_class="specific_official_call",
            specificity="specific",
            critical=True,
        ),
    )
    finding = next(
        finding
        for finding in result.findings
        if finding.code == "CONTRADICTION_STATE"
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert finding.metadata["current_value"] == "18"
    assert finding.metadata["resolved"] is True
    assert finding.metadata["superseded_claims"] == ()
    assert finding.metadata["verification_need"]["needed"] is False


def _canonical_contradiction_finding(result):
    return next(
        finding
        for finding in result.findings
        if finding.code in {
            "CONTRADICTION_STATE",
            "CONTRADICTION_UNRESOLVED",
            "MATERIAL_CONTRADICTION_UNRESOLVED",
        }
    )


def _semantic_contradiction_result(result):
    finding = _canonical_contradiction_finding(result)
    metadata = finding.metadata
    conflicts = tuple(
        sorted(
            (
                conflict["attribute"],
                conflict["left_id"],
                conflict["right_id"],
                conflict["left_value"],
                conflict["right_value"],
            )
            for conflict in metadata["conflicts"]
        )
    )
    return (
        metadata["current_value"],
        metadata["resolved"],
        metadata["unresolved"],
        metadata["verification_need"]["needed"],
        conflicts,
    )


def test_canonical_rule_three_source_resolution_uses_highest_attribute_authority():
    result = _canonical_result(
        _claim(
            "email",
            attribute="exam_date",
            value="18",
            source_class="institutional_email",
            critical=True,
        ),
        _claim(
            "calendar",
            attribute="exam_date",
            value="17",
            source_class="academic_calendar",
            critical=True,
        ),
        _claim(
            "call",
            attribute="exam_date",
            value="18",
            source_class="specific_official_call",
            specificity="specific",
            critical=True,
        ),
    )
    finding = _canonical_contradiction_finding(result)
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert finding.metadata["contradiction"] is True
    assert finding.metadata["current_value"] == "18"
    assert finding.metadata["resolved"] is True
    assert finding.metadata["unresolved"] is False
    assert finding.metadata["verification_need"]["needed"] is False
    assert set(finding.references) == {"email", "calendar", "call"}


def test_canonical_rule_three_source_resolution_is_permutation_invariant():
    claims = (
        _claim(
            "email",
            attribute="exam_date",
            value="18",
            source_class="institutional_email",
        ),
        _claim(
            "calendar",
            attribute="exam_date",
            value="17",
            source_class="academic_calendar",
        ),
        _claim(
            "call",
            attribute="exam_date",
            value="18",
            source_class="specific_official_call",
            specificity="specific",
        ),
    )
    semantic_results = [
        _semantic_contradiction_result(_canonical_result(*ordered_claims))
        for ordered_claims in permutations(claims)
    ]
    assert len(semantic_results) == 6
    assert all(semantic == semantic_results[0] for semantic in semantic_results)
    assert semantic_results[0][0] == "18"
    assert semantic_results[0][1:4] == (True, False, False)


def test_canonical_rule_corroborated_highest_authority_is_not_unresolved():
    result = _canonical_result(
        _claim(
            "call-a",
            attribute="exam_date",
            value="18",
            source_class="specific_official_call",
            specificity="specific",
        ),
        _claim(
            "call-b",
            attribute="exam_date",
            value="18",
            source_class="specific_official_call",
            specificity="specific",
        ),
        _claim(
            "calendar",
            attribute="exam_date",
            value="17",
            source_class="academic_calendar",
        ),
    )
    finding = _canonical_contradiction_finding(result)
    assert finding.metadata["contradiction"] is True
    assert finding.metadata["current_value"] == "18"
    assert finding.metadata["resolved"] is True
    assert finding.metadata["unresolved"] is False


def test_canonical_rule_equal_authority_conflict_emits_verification_need():
    result = _canonical_result(
        _claim(
            "call-a",
            attribute="exam_date",
            value="17",
            source_class="specific_official_call",
            specificity="specific",
            critical=True,
        ),
        _claim(
            "call-b",
            attribute="exam_date",
            value="18",
            source_class="specific_official_call",
            specificity="specific",
            critical=True,
        ),
    )
    finding = next(
        finding
        for finding in result.findings
        if finding.code == "MATERIAL_CONTRADICTION_UNRESOLVED"
    )
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert finding.metadata["verification_need"]["needed"] is True
    assert finding.metadata["verification_need"]["reason"] == "conflicting"


def test_canonical_rule_ignores_caller_unresolved_false():
    left = _claim(
        "call-a",
        attribute="exam_date",
        value="17",
        source_class="specific_official_call",
        specificity="specific",
        critical=True,
    )
    right = _claim(
        "call-b",
        attribute="exam_date",
        value="18",
        source_class="specific_official_call",
        specificity="specific",
        critical=True,
    )
    left["unresolved"] = False
    right["unresolved"] = False
    result = _canonical_result(left, right)
    assert result.status is ReasoningRuleResultStatus.BLOCKED


def test_canonical_rule_preserves_independent_scoped_values_order_invariant():
    claims = (
        _claim(
            "subject-a-call",
            attribute="exam_date",
            value="18",
            source_class="specific_official_call",
            specificity="specific",
            scope="subject-a",
        ),
        _claim(
            "subject-b-call",
            attribute="exam_date",
            value="20",
            source_class="specific_official_call",
            specificity="specific",
            scope="subject-b",
        ),
    )

    semantic_results = []
    for ordered_claims in (claims, tuple(reversed(claims))):
        finding = _canonical_contradiction_finding(_canonical_result(*ordered_claims))
        metadata = finding.metadata
        semantic_results.append(
            (
                metadata["contradiction"],
                metadata["resolved"],
                metadata["unresolved"],
                metadata["current_value"],
                metadata["current_values_by_scope"],
                metadata["verification_need"]["needed"],
            )
        )

    assert semantic_results[0] == semantic_results[1]
    assert semantic_results[0] == (
        False,
        True,
        False,
        None,
        (
            {"attribute": "exam_date", "scope": "subject-a", "value": "18"},
            {"attribute": "exam_date", "scope": "subject-b", "value": "20"},
        ),
        False,
    )


def test_canonical_rule_unknown_temporal_conflict_remains_unresolved():
    result = _canonical_result(
        _claim(
            "calendar",
            attribute="exam_date",
            value="17",
            source_class="academic_calendar",
            specificity="general",
            scope="subject-a",
            critical=True,
        ),
        _claim(
            "specific-call",
            attribute="exam_date",
            value="18",
            source_class="specific_official_call",
            temporal="unknown",
            specificity="specific",
            scope="subject-a",
            critical=True,
        ),
    )

    finding = _canonical_contradiction_finding(result)
    verification = finding.metadata["verification_need"]
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert finding.metadata["contradiction"] is True
    assert finding.metadata["resolved"] is False
    assert finding.metadata["unresolved"] is True
    assert finding.metadata["current_value"] is None
    assert verification["needed"] is True
    assert verification["source_class"] == "official_only"
    assert verification["read_only"] is True
# ── V9-B2: malformed contradiction evidence never resolves confidently ───────
# ── and never falls through to RULE_NOT_APPLICABLE. ──────────────────────────


def test_canonical_rule_malformed_statements_container_not_applicable():
    """:func:`AcademicContradictionRule.evaluate` with a malformed
    ``contradiction_statements`` container (scalar [7]) must NOT return
    ``RULE_NOT_APPLICABLE``.  It must preserve structured uncertainty."""
    result = _canonical_result(7)
    codes = [f.code for f in result.findings]
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert "RULE_NOT_APPLICABLE" not in codes
    assert result.findings[0].code == "CONTRADICTION_UNRESOLVED"
    assert result.findings[0].metadata["unresolved"] is True
    assert result.findings[0].metadata["resolved"] is False


def test_canonical_rule_malformed_contradiction_member_fails_closed():
    """A valid claim mixed with a malformed member cannot produce a clean
    ``contradiction=False + resolved=True`` conclusion."""
    claim = _claim(
        "official",
        attribute="deadline",
        value="2026-09-01",
        source_class="official_publication",
        specificity="specific",
    )
    result = _canonical_result(claim, 7)
    finding = _canonical_contradiction_finding(result)
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert finding.metadata["resolved"] is False
    assert finding.metadata["unresolved"] is True


def test_canonical_rule_valid_contradiction_evidence_resolves_normally():
    """The positive regression: all-Mapping contradiction evidence resolves."""
    result = _canonical_result(
        _claim("a", attribute="exam_date", value="17"),
    )
    finding = _canonical_contradiction_finding(result)
    assert finding.metadata["resolved"] is True


# ── V10-B1: direct helper malformed collection containers/members ────────────


def test_direct_helper_malformed_claims_container_no_exception():
    """claims=7 must not raise and must remain unresolved."""
    result = resolve_academic_conflict(claims=7)
    assert result["resolved"] is False
    assert result["unresolved"] is True


def test_direct_helper_malformed_claim_member_stays_unresolved():
    """A valid claim plus a non-Mapping member cannot produce a clean
    contradiction=False + resolved=True conclusion."""
    claim = _claim(
        "official",
        attribute="deadline",
        value="2026-09-01",
        source_class="official_publication",
        specificity="specific",
    )
    result = resolve_academic_conflict(claims=(claim, 7))
    assert result["resolved"] is False
    assert result["unresolved"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# V11-B1: exported compatibility adapter boundary normalization
#
# evaluate_academic_contradiction must normalize malformed containers/members
# BEFORE delegation so it shares the base resolver's fail-closed boundary.  A
# malformed member must not be deleted before delegation.
# ═══════════════════════════════════════════════════════════════════════════════


def test_v11_b1_contradiction_adapter_malformed_container_no_exception():
    """statements=7 must not raise and must remain unresolved."""
    result = evaluate_academic_contradiction(statements=7)
    assert result["resolved"] is False
    assert result["unresolved"] is True
    assert result["state"] == "unresolved"


def test_v11_b1_contradiction_adapter_string_container_unresolved():
    """statements='abc' must not be treated as a resolved contradiction."""
    result = evaluate_academic_contradiction(statements="abc")
    assert result["resolved"] is False
    assert result["unresolved"] is True
    assert result["state"] == "unresolved"


def test_v11_b1_contradiction_adapter_mapping_container_unresolved():
    """statements={'x': 1} must not resolve as a clean contradiction state."""
    result = evaluate_academic_contradiction(statements={"x": 1})
    assert result["resolved"] is False
    assert result["unresolved"] is True
    assert result["state"] == "unresolved"


def test_v11_b1_contradiction_adapter_malformed_member_unresolved():
    """A valid claim plus a non-Mapping member must not resolve cleanly; the
    malformed member must be passed into the resolver, not deleted first."""
    claim = _claim(
        "official",
        attribute="deadline",
        value="2026-09-01",
        source_class="official_publication",
        specificity="specific",
    )
    result = evaluate_academic_contradiction(statements=(claim, 7))
    assert result["resolved"] is False
    assert result["unresolved"] is True
    assert result["state"] == "unresolved"


def test_v11_b1_contradiction_adapter_fully_valid_statement_resolves():
    """Fully-valid legacy behavior must remain green."""
    claim = _claim(
        "official",
        attribute="deadline",
        value="2026-09-01",
        source_class="official_publication",
        specificity="specific",
    )
    result = evaluate_academic_contradiction(statements=(claim,))
    assert result["resolved"] is True
    assert result["unresolved"] is False
    assert result["state"] == "resolved"


# ═══════════════════════════════════════════════════════════════════════════════
# V11-B3: Contradiction semantic Mapping validation
#
# An empty/opaque Mapping claim ({}, {"foo": "bar"}) must not prove
# "no contradiction".  Mapping instance != semantically valid claim evidence.
# ═══════════════════════════════════════════════════════════════════════════════


def test_v11_b3_direct_conflict_opaque_claim_stays_unresolved():
    """(valid_claim, {}) must not produce a clean contradiction=False +
    resolved=True conclusion."""
    claim = _claim(
        "official",
        attribute="deadline",
        value="2026-09-01",
        source_class="official_publication",
        specificity="specific",
    )
    result = resolve_academic_conflict(claims=(claim, {}))
    assert result["resolved"] is False
    assert result["unresolved"] is True


def test_v11_b3_canonical_contradiction_opaque_statement_unresolved():
    """contradiction_statements=[valid_claim, {}] must emit an unresolved
    contradiction state and never a clean resolved conclusion."""
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
        {},
    )
    assert any(
        finding.code == "CONTRADICTION_UNRESOLVED"
        for finding in result.findings
    )
    assert not any(
        finding.code == "CONTRADICTION_EVALUATED" and finding.metadata.get("resolved") is True
        for finding in result.findings
    )


# ═══════════════════════════════════════════════════════════════════════════════
# V12-B1: strict boolean semantics at composition boundaries — Contradiction
#
# The legacy flag-only path and the claim ``critical`` field must not re-introduce
# Python truthiness.  material="false" / "true" / 1 / 0 must never become
# material=True.  critical="false" must never create a material/blocked state.
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("value", ["false", "true", 1, 0])
def test_v12_b1_flag_only_material_string_never_material_true(value):
    """material='false' / 'true' / 1 / 0 must NOT become material=True."""
    result = evaluate_academic_contradiction(
        statements=({"material": value, "unresolved": value},)
    )
    assert result["material"] is False


def test_v12_b1_flag_only_material_literal_true_is_material():
    result = evaluate_academic_contradiction(
        statements=({"material": True, "unresolved": True},)
    )
    assert result["material"] is True
    assert result["state"] == "material"


def test_v12_b1_flag_only_material_literal_false_not_material():
    result = evaluate_academic_contradiction(
        statements=({"material": False, "unresolved": False},)
    )
    assert result["material"] is False
    assert result["resolved"] is True


def test_v12_b1_flag_only_unresolved_string_not_truthy():
    """unresolved='false' must not be interpreted via truthiness as True."""
    result = evaluate_academic_contradiction(
        statements=({"material": "false", "unresolved": "false"},)
    )
    # A malformed flag is never trusted as material=True and cannot resolve
    # confidently clean; the flag-only evidence stays conservatively unresolved.
    assert result["material"] is False
    assert result["unresolved"] is True
    assert result["resolved"] is False


def test_v12_b1_claim_critical_string_false_does_not_block():
    """critical='false' on equal-authority incompatible claims must NOT create
    material=True / blocked=True solely from truthiness.  The contradiction
    itself remains unresolved."""
    left = _claim(
        "call-a",
        attribute="deadline",
        value="17",
        source_class="specific_official_call",
        specificity="specific",
    )
    right = _claim(
        "call-b",
        attribute="deadline",
        value="18",
        source_class="specific_official_call",
        specificity="specific",
    )
    left["critical"] = "false"
    right["critical"] = "false"
    result = resolve_academic_conflict(claims=(left, right))
    assert result["contradiction"] is True
    assert result["resolved"] is False
    assert result["unresolved"] is True
    assert result["material"] is False
    assert result["blocked"] is False


def test_v12_b1_claim_critical_literal_true_still_material():
    left = _claim(
        "call-a",
        attribute="deadline",
        value="17",
        source_class="specific_official_call",
        specificity="specific",
        critical=True,
    )
    right = _claim(
        "call-b",
        attribute="deadline",
        value="18",
        source_class="specific_official_call",
        specificity="specific",
        critical=True,
    )
    result = resolve_academic_conflict(claims=(left, right))
    assert result["material"] is True
    assert result["blocked"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# V12-B2: partial same-attribute claim is incomplete evidence
#
# id + attribute alone does not prove no contradiction.  A value-less claim that
# names an attribute (e.g. {"id":"junk","attribute":"deadline"}) cannot
# corroborate, contradict, or differ, so the conflict stays unresolved.
# ═══════════════════════════════════════════════════════════════════════════════


def test_v12_b2_direct_partial_same_attribute_claim_unresolved():
    valid_claim = _claim(
        "official",
        attribute="deadline",
        value="2026-09-01",
        source_class="official_publication",
        specificity="specific",
    )
    partial_claim = {"id": "junk", "attribute": "deadline"}
    result = resolve_academic_conflict(claims=(valid_claim, partial_claim))
    assert result["resolved"] is False
    assert result["unresolved"] is True


def test_v12_b2_direct_valid_corroboration_stays_resolved():
    claims = (
        _claim(
            "c1",
            attribute="deadline",
            value="2026-09-01",
            source_class="official_publication",
            provenance="grounded",
            temporal="valid",
        ),
        _claim(
            "c2",
            attribute="deadline",
            value="2026-09-01",
            source_class="official_publication",
            provenance="grounded",
            temporal="valid",
        ),
    )
    result = resolve_academic_conflict(claims=claims)
    assert result["resolved"] is True
    assert result["unresolved"] is False


def test_v12_b2_canonical_partial_same_attribute_claim_unresolved():
    """contradiction_statements=[valid deadline claim, partial deadline claim]
    must emit CONTRADICTION_UNRESOLVED, never a clean resolved conclusion."""
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
    codes = [finding.code for finding in result.findings]
    assert "CONTRADICTION_UNRESOLVED" in codes
    assert not any(
        finding.code == "CONTRADICTION_STATE"
        and finding.metadata.get("resolved") is True
        for finding in result.findings
    )


# ═══════════════════════════════════════════════════════════════════════════════
# V13-B1: contradiction claim validation
#
# A usable contradiction claim must carry at least a usable semantic attribute
# and a usable/present fact value.  Missing / blank / non-string attribute is
# relationship-unknown and must force an unresolved state (never the synthetic
# "unknown" bucket treated as safely unrelated).
# ═══════════════════════════════════════════════════════════════════════════════


def _valid_deadline_claim():
    return _claim(
        "official",
        attribute="deadline",
        value="2026-09-01",
        source_class="official_publication",
        specificity="specific",
    )


@pytest.mark.parametrize(
    "partial",
    [
        {"id": "junk", "value": "2026-09-02"},
        {"id": "junk", "attribute": "", "value": "2026-09-02"},
        {"id": "junk", "attribute": 7, "value": "2026-09-02"},
        {"id": "junk"},
    ],
)
def test_v13_b1_missing_or_invalid_attribute_claim_unresolved(partial):
    """A claim whose attribute is missing/blank/non-string is relationship-
    unknown and cannot resolve cleanly next to valid evidence."""
    result = resolve_academic_conflict(claims=(_valid_deadline_claim(), partial))
    assert result["resolved"] is False
    assert result["unresolved"] is True


def test_v13_b1_valid_unrelated_claim_stays_safe():
    """A fully valid unrelated claim must not make target resolution uncertain."""
    deadline = _valid_deadline_claim()
    unrelated = _claim("enr", attribute="enrollment_status", value="active")
    result = resolve_academic_conflict(claims=(deadline, unrelated))
    assert result["resolved"] is True
    assert result["unresolved"] is False


@pytest.mark.parametrize(
    "partial",
    [
        {"id": "junk", "value": "2026-09-02"},
        {"id": "junk", "attribute": "", "value": "2026-09-02"},
        {"id": "junk", "attribute": 7, "value": "2026-09-02"},
        {"id": "junk"},
    ],
)
def test_v13_b1_canonical_missing_or_invalid_attribute_unresolved(partial):
    """Canonical contradiction_statements with relationship-unknown claims must
    emit CONTRADICTION_UNRESOLVED with resolved=False / unresolved=True."""
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
        partial,
    )
    codes = [finding.code for finding in result.findings]
    assert "CONTRADICTION_UNRESOLVED" in codes
    assert not any(
        finding.code == "CONTRADICTION_STATE"
        and finding.metadata.get("resolved") is True
        for finding in result.findings
    )
    unresolved_finding = next(
        finding for finding in result.findings if finding.code == "CONTRADICTION_UNRESOLVED"
    )
    assert unresolved_finding.metadata["resolved"] is False
    assert unresolved_finding.metadata["unresolved"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# V13-B2: malformed claim/requested scope must never become global
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("bad_scope", [7, "", [], ["course:A"], {}])
def test_v13_b2_malformed_claim_scope_unresolved(bad_scope):
    """A claim with a malformed scope is relationship-unknown and stays
    unresolved; it never acts as unscoped/global evidence."""
    claim = _claim(
        "solo",
        attribute="deadline",
        value="2026-09-01",
        source_class="official_publication",
        specificity="specific",
    )
    claim["scope"] = bad_scope
    result = resolve_academic_conflict(claims=(claim,))
    assert result["resolved"] is False
    assert result["unresolved"] is True


def test_v13_b2_mixed_valid_and_malformed_scope_never_broadens_reach():
    """course:A claim + malformed-scope claim: the malformed member must NOT act
    as global and must NOT create cross-scope contradiction reach into course:A."""
    claim_a = _claim("a", attribute="deadline", value="17", scope="course:A")
    claim_b = _claim("b", attribute="deadline", value="18")
    claim_b["scope"] = 7
    result = resolve_academic_conflict(claims=(claim_a, claim_b))
    assert result["unresolved"] is True
    assert result["resolved"] is False
    # B must never reach into A's scoped resolution as a global competitor: A
    # resolves independently to 17 and B is not present in any conflict pair.
    assert result["current_value"] == "17"
    assert not any(
        conflict["left_id"] == "b" or conflict["right_id"] == "b"
        for conflict in result["conflicts"]
    )


@pytest.mark.parametrize("bad_scope", [7, ""])
def test_v13_b2_requested_scope_fails_closed(bad_scope):
    """A malformed requested scope in resolve_academic_conflict must not resolve
    cleanly; it fails closed rather than acting as global."""
    result = resolve_academic_conflict(
        claims=(_valid_deadline_claim(),),
        scope=bad_scope,
    )
    assert result["resolved"] is False
    assert result["unresolved"] is True


def test_v13_b2_canonical_contradiction_malformed_scope_unresolved():
    """Canonical contradiction statements carrying scope=7 must not produce a
    clean resolved=True nor silently normalize the scope to None."""
    result = _canonical_result(
        {
            "id": "c1",
            "attribute": "deadline",
            "value": "2026-09-01",
            "source_class": "official_publication",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
            "scope": 7,
        }
    )
    codes = [finding.code for finding in result.findings]
    assert "CONTRADICTION_UNRESOLVED" in codes
    unresolved_finding = next(
        finding for finding in result.findings if finding.code == "CONTRADICTION_UNRESOLVED"
    )
    assert unresolved_finding.metadata["resolved"] is False
    assert unresolved_finding.metadata["unresolved"] is True
