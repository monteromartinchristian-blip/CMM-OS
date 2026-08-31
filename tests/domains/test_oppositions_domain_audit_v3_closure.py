"""Phase 10.23 — Audit V3 definitive closure matrix.

Permanent regression gate for the four V3 edge contracts:

- V3-I1 — syllabus conflict survives the canonical ``SyllabusCoverageRule``;
- V3-I2 — a directional trend requires strict temporal ordering (>= 2 distinct
  normalized instants), never arbitrary equality ties;
- V3-I3 — missing/unknown/conditional/malformed eligibility keeps an
  alternative comparison unresolved;
- V3-M1 — capacity provenance is truthful for University/composed composition.

This file tests public behavior only and is a permanent regression gate.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from cmm.cognitive.enums import ReasoningSeverity
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains import oppositions
from cmm.domains.oppositions.rules import (
    compare_alternative_routes,
    evaluate_mock_performance,
    evaluate_study_feasibility,
)

T = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _context(**metadata) -> ReasoningRuleContext:
    return ReasoningRuleContext(
        reasoning_id="rid",
        timestamp=T,
        active_domains=("domain:oppositions",),
        primary_domain="domain:oppositions",
        metadata=metadata,
    )


def _rules():
    return {r.definition.id: r for r in oppositions.build_oppositions_rules()}


def _mock(mock_id, score, *, date, **overrides):
    record = {
        "id": mock_id,
        "score": score,
        "total": 10,
        "scoring": "standard",
        "format": "test",
        "date": date,
    }
    record.update(overrides)
    return record


# ── V3-I1 — Syllabus conflict survives the canonical Rule ─────────────────────


def test_syllabus_rule_preserves_conflict_metadata():
    rule = _rules()["oppositions.syllabus_coverage"]
    result = rule.evaluate(
        _context(
            topics=[
                {"id": "t-conflict", "studied": "yes", "depth": 2},
                {"id": "t-conflict", "studied": "yes", "depth": 8},
            ],
            syllabus_version="v2",
            syllabus_current=True,
        )
    )
    assert result.status.value  # APPLIED
    finding = result.findings[0]
    assert finding.metadata["complete"] is False
    assert finding.metadata["conflicting_count"] == 1
    assert "t-conflict" in finding.metadata["conflicting_topics"]
    assert finding.metadata["conflict_blocks_complete"] is True
    assert finding.metadata["dimensions"]["conflicting"] == 1
    assert finding.severity is ReasoningSeverity.WARNING
    json.dumps(finding.to_dict(), allow_nan=False)


def test_syllabus_conflict_message_distinct_from_normal_pending():
    rule = _rules()["oppositions.syllabus_coverage"]
    conflict = rule.evaluate(
        _context(
            topics=[
                {"id": "t-conflict", "studied": "yes", "depth": 2},
                {"id": "t-conflict", "studied": "yes", "depth": 8},
            ],
            syllabus_version="v2",
            syllabus_current=True,
        )
    ).findings[0]
    pending = rule.evaluate(
        _context(
            topics=[{"id": "t-pending", "studied": "no"}],
            syllabus_version="v2",
            syllabus_current=True,
        )
    ).findings[0]
    assert "conflict" in conflict.message.lower()
    assert "conflict" not in pending.message.lower()


def test_syllabus_ordinary_pending_does_not_falsely_report_conflict():
    rule = _rules()["oppositions.syllabus_coverage"]
    finding = rule.evaluate(
        _context(
            topics=[{"id": "t-pending", "studied": "no"}],
            syllabus_version="v2",
            syllabus_current=True,
        )
    ).findings[0]
    assert finding.metadata["complete"] is False
    assert finding.metadata["conflicting_count"] == 0
    assert finding.metadata["conflicting_topics"] == ()
    assert finding.metadata["conflict_blocks_complete"] is False
    assert "conflict" not in finding.message.lower()


# ── V3-I2 — Strict temporal ordering for directional trend ────────────────────


def test_same_instant_offset_equivalent_mocks_do_not_create_trend():
    record = evaluate_mock_performance(
        mocks=(
            _mock("m1", 2, date="2027-04-01T00:00:00Z"),
            _mock("m2", 7, date="2027-04-01T02:00:00+02:00"),
        )
    )
    assert record["trend_inferred"] is False
    assert record["trend_state"] == "no_trend"
    assert record["trend_slope"] is None


def test_same_date_only_mocks_do_not_create_trend():
    record = evaluate_mock_performance(
        mocks=(
            _mock("m1", 5, date="2027-05-03"),
            _mock("m2", 9, date="2027-05-03"),
        )
    )
    assert record["trend_inferred"] is False
    assert record["trend_slope"] is None


def test_three_mocks_with_duplicate_timestamp_deterministic_no_trend():
    # T0 holds two materially different observations (scores 2 and 7); that
    # timestamp group is temporally ambiguous for a directional trend.
    record = evaluate_mock_performance(
        mocks=(
            _mock("m-a", 2, date="2027-06-01T08:00:00Z"),
            _mock("m-b", 7, date="2027-06-01T08:00:00Z"),
            _mock("m-c", 9, date="2027-06-02T08:00:00Z"),
        )
    )
    assert record["trend_inferred"] is False
    assert record["trend_state"] == "no_trend"
    assert record["trend_slope"] is None
    assert record["chronology_ambiguous"] is True


def test_equal_time_exact_duplicates_do_not_imply_temporal_progression():
    # Two observations at the same instant with identical semantics but
    # distinct ids corroborate; they never provide a temporal progression.
    record = evaluate_mock_performance(
        mocks=(
            _mock("m1", 6, date="2027-07-01T00:00:00Z"),
            _mock("m2", 6, date="2027-07-01T00:00:00Z"),
        )
    )
    assert record["trend_inferred"] is False
    assert record["trend_state"] == "no_trend"
    assert record["trend_slope"] is None


def test_same_time_mock_permutations_preserve_semantic_result():
    records = [
        _mock("m-a", 2, date="2027-06-01T08:00:00Z"),
        _mock("m-b", 7, date="2027-06-01T08:00:00Z"),
        _mock("m-c", 9, date="2027-06-02T08:00:00Z"),
    ]
    from itertools import permutations

    keys = (
        "trend_inferred",
        "trend_state",
        "trend_slope",
        "chronology_unknown",
        "chronology_ambiguous",
        "timeline",
    )
    baseline = None
    for perm in permutations(records):
        record = evaluate_mock_performance(mocks=perm)
        projection = tuple(record[k] for k in keys)
        if baseline is None:
            baseline = projection
        else:
            assert projection == baseline
    assert baseline[0] is False


def test_strictly_ordered_normal_case_still_infers_trend():
    record = evaluate_mock_performance(
        mocks=(
            _mock("m1", 3, date="2027-01-10"),
            _mock("m2", 5, date="2027-02-10"),
            _mock("m3", 8, date="2027-03-10"),
        )
    )
    assert record["trend_inferred"] is True
    assert record["trend_state"] == "trend"
    assert record["trend_slope"] == 5


def test_mock_rule_propagates_chronology_ambiguous():
    rule = _rules()["oppositions.mock_exam_interpretation"]
    result = rule.evaluate(
        _context(
            mocks=[
                _mock("m-a", 2, date="2027-06-01T08:00:00Z"),
                _mock("m-b", 7, date="2027-06-01T08:00:00Z"),
                _mock("m-c", 9, date="2027-06-02T08:00:00Z"),
            ]
        )
    )
    finding = result.findings[0]
    assert finding.metadata["trend_inferred"] is False
    assert finding.metadata["chronology_ambiguous"] is True
    json.dumps(finding.to_dict(), allow_nan=False)


# ── V3-I3 — Conditional/unknown eligibility keeps comparison unresolved ────────


def test_missing_eligibility_keeps_comparison_unresolved():
    result = compare_alternative_routes(
        primary={"id": "primary", "eligibility": "eligible"},
        alternatives=({"id": "alt-missing"},),
    )
    assert "alt-missing" in result["conditional_requirements"]
    assert result["resolved"] is False
    assert result["recommendation"] is None


def test_explicit_unknown_eligibility_keeps_comparison_unresolved():
    result = compare_alternative_routes(
        primary={"id": "primary", "eligibility": "eligible"},
        alternatives=({"id": "alt-unknown", "eligibility": "unknown"},),
    )
    assert "alt-unknown" in result["conditional_requirements"]
    assert result["resolved"] is False
    assert result["recommendation"] is None


def test_explicit_conditional_eligibility_keeps_comparison_unresolved():
    result = compare_alternative_routes(
        primary={"id": "primary", "eligibility": "eligible"},
        alternatives=({"id": "alt-conditional", "eligibility": "conditional"},),
    )
    assert "alt-conditional" in result["conditional_requirements"]
    assert result["resolved"] is False
    assert result["recommendation"] is None


def test_arbitrary_eligibility_string_fails_closed():
    result = compare_alternative_routes(
        primary={"id": "primary", "eligibility": "eligible"},
        alternatives=({"id": "alt-invalid", "eligibility": "banana"},),
    )
    assert "alt-invalid" in result["conditional_requirements"]
    assert result["resolved"] is False
    assert result["recommendation"] is None


def test_mixed_eligible_plus_conditional_suppresses_recommendation():
    result = compare_alternative_routes(
        primary={"id": "primary", "eligibility": "eligible"},
        alternatives=(
            {"id": "alt1", "eligibility": "eligible", "syllabus_overlap": 0.9},
            {"id": "alt2", "eligibility": "conditional", "syllabus_overlap": 0.5},
        ),
    )
    assert result["resolved"] is False
    assert "alt2" in result["conditional_requirements"]
    assert result["recommendation"] is None


def test_canonical_alternative_rule_preserves_conditional_state():
    rule = _rules()["oppositions.alternative_route"]
    result = rule.evaluate(
        _context(
            primary={"id": "primary", "eligibility": "eligible"},
            alternatives=[
                {"id": "alt1", "eligibility": "eligible", "syllabus_overlap": 0.9},
                {"id": "alt2", "eligibility": "conditional", "syllabus_overlap": 0.5},
            ],
        )
    )
    finding = result.findings[0]
    assert finding.metadata["resolved"] is False
    assert "alt2" in finding.metadata["conditional_requirements"]
    assert finding.metadata["recommendation"] is None
    assert finding.severity is ReasoningSeverity.WARNING
    json.dumps(finding.to_dict(), allow_nan=False)


def test_eligible_and_ineligible_still_normal():
    result = compare_alternative_routes(
        primary={"id": "primary", "eligibility": "eligible"},
        alternatives=(
            {"id": "alt1", "eligibility": "eligible", "syllabus_overlap": 0.9},
            {"id": "alt2", "eligibility": "ineligible", "syllabus_overlap": 0.5},
        ),
    )
    assert result["resolved"] is True
    assert result["recommendation"] == "alt1"


# ── V3-M1 — Truthful University/composed capacity provenance ──────────────────


def test_user_only_provenance_tracks_user():
    record = evaluate_study_feasibility(
        remaining_hours=4, available_hours=8, target_days=30
    )
    assert record["capacity_hours"] == 8
    assert record["capacity_sources"] == ("user",)
    assert record["capacity_source"] == "user"


def test_university_availability_bound_provenance_tracks_university():
    record = evaluate_study_feasibility(
        remaining_hours=4,
        available_hours=10,
        target_days=30,
        university_projection={
            "authorized": True,
            "available_hours": 6,
            "workload_hours": 0,
        },
    )
    assert record["capacity_hours"] == 6
    assert "university" in record["capacity_sources"]


def test_university_workload_reduction_provenance_tracks_university():
    record = evaluate_study_feasibility(
        remaining_hours=4,
        available_hours=10,
        target_days=30,
        university_projection={
            "authorized": True,
            "available_hours": 8,
            "workload_hours": 3,
        },
    )
    assert record["capacity_hours"] == 5
    assert "university" in record["capacity_sources"]


def test_health_plus_university_composed_provenance_truthful():
    record = evaluate_study_feasibility(
        remaining_hours=4,
        available_hours=11,
        target_days=30,
        health_constraint={"authorized": True, "functional_cap_hours": 8},
        university_projection={
            "authorized": True,
            "available_hours": 7,
            "workload_hours": 2,
        },
    )
    assert record["capacity_hours"] == 5
    assert record["capacity_sources"] == ("health", "university")
    assert record["capacity_source"] == "composed"


def test_capacity_provenance_is_json_safe():
    records = [
        evaluate_study_feasibility(
            remaining_hours=4, available_hours=8, target_days=30
        ),
        evaluate_study_feasibility(
            remaining_hours=4,
            available_hours=10,
            target_days=30,
            university_projection={"authorized": True, "available_hours": 6},
        ),
        evaluate_study_feasibility(
            remaining_hours=4,
            available_hours=11,
            target_days=30,
            health_constraint={"authorized": True, "functional_cap_hours": 8},
            university_projection={
                "authorized": True,
                "available_hours": 7,
                "workload_hours": 2,
            },
        ),
    ]
    for record in records:
        json.dumps(record, allow_nan=False)


def test_study_feasibility_rule_preserves_capacity_provenance():
    rule = _rules()["oppositions.study_feasibility"]
    result = rule.evaluate(
        _context(
            remaining_hours=4,
            available_hours=11,
            target_days=30,
            health_constraint={"authorized": True, "functional_cap_hours": 8},
            university_projection={
                "authorized": True,
                "available_hours": 7,
                "workload_hours": 2,
            },
        )
    )
    finding = result.findings[0]
    assert finding.metadata["capacity_hours"] == 5
    assert finding.metadata["capacity_sources"] == ("health", "university")
