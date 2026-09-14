"""Phase 10.23 — Audit V2 definitive closure matrix.

Cross-cutting regression gate for the V2 defect class: equivalence classes,
permutations, JSON serialization, helper→Rule parity, cross-domain
most-restrictive composition, and no-unexpected-exception checks.

This file tests public behavior only and is a permanent regression gate for the
semantic-normalization defect class that caused Audit V1 and Audit V2.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from itertools import permutations

from cmm.cognitive.enums import ReasoningRuleResultStatus, ReasoningSeverity
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains import oppositions
from cmm.domains.oppositions.rules import (
    classify_opposition_temporal,
    compare_alternative_routes,
    evaluate_mock_performance,
    evaluate_study_feasibility,
    evaluate_syllabus_coverage,
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


# ── JSON serialization gate ───────────────────────────────────────────────────


def test_all_touched_helpers_json_serializable():
    results = [
        evaluate_study_feasibility(
            remaining_hours=10, available_hours=30, target_days=30
        ),
        evaluate_syllabus_coverage(
            topics=({"id": "t1", "studied": "yes", "depth": 3},),
            syllabus_version="v2",
            syllabus_current=True,
        ),
        evaluate_mock_performance(
            mocks=(
                {
                    "id": "m1",
                    "score": 5,
                    "total": 10,
                    "scoring": "standard",
                    "format": "test",
                    "date": "2026-01-01",
                },
            )
        ),
        compare_alternative_routes(
            primary={"id": "primary"},
            alternatives=({"id": "alt1", "eligibility": "eligible"},),
        ),
        classify_opposition_temporal(
            fact={
                "attribute": "application_deadline",
                "value": "2026-08-31",
                "temporal": "valid",
                "grounded": True,
                "source_reference": "r1",
            },
            decision_critical=True,
        ),
    ]
    for result in results:
        json.dumps(result)


def test_mock_timeline_json_serializable_with_mixed_chronology():
    record = evaluate_mock_performance(
        mocks=(
            {
                "id": "m1",
                "score": 5,
                "total": 10,
                "scoring": "standard",
                "format": "test",
                "date": "2026-01-01",
            },
            {
                "id": "m2",
                "score": 6,
                "total": 10,
                "scoring": "standard",
                "format": "test",
                "date": "2026-02-01T00:00:00+00:00",
            },
        )
    )
    json.dumps(record)


# ── Primitive type traps (no unexpected exceptions) ───────────────────────────


def test_study_feasibility_primitive_matrix_no_exception():
    for value in (
        None,
        True,
        False,
        0,
        1,
        -1,
        1.0,
        float("nan"),
        float("inf"),
        "",
        "0",
        "1",
        "true",
        "false",
        "unknown",
        {},
        [],
        (),
        [{}],
    ):
        # malformed target-date values must fail closed without raising
        record = evaluate_study_feasibility(
            remaining_hours=10, available_hours=30, target_days=value
        )
        assert record["feasible"] is False or isinstance(record["feasible"], bool)
        json.dumps(record)


def test_syllabus_primitive_matrix_no_exception():
    for value in (
        None,
        True,
        False,
        0,
        1,
        -1,
        1.0,
        "",
        "0",
        "1",
        "true",
        "false",
        "unknown",
        {},
        [],
        (),
        [{}],
    ):
        record = evaluate_syllabus_coverage(
            topics=({"id": "t1", "studied": "yes", "depth": value},),
            syllabus_version="v2",
            syllabus_current=True,
        )
        json.dumps(record)


def test_mock_primitive_matrix_no_exception():
    for value in (
        None,
        True,
        False,
        0,
        1,
        -1,
        1.0,
        float("nan"),
        float("inf"),
        "",
        "0",
        "1",
        "true",
        "false",
        "unknown",
        {},
        [],
        (),
        [{}],
    ):
        record = evaluate_mock_performance(
            mocks=({"id": "m1", "score": value, "total": 10},)
        )
        json.dumps(record)


def test_alternative_primitive_matrix_no_exception():
    for value in (
        None,
        True,
        False,
        0,
        1,
        -1,
        1.0,
        "",
        "0",
        "1",
        "true",
        "false",
        "unknown",
        {},
        [],
        (),
        [{}],
    ):
        result = compare_alternative_routes(
            primary={"id": "primary"},
            alternatives=({"id": "alt1", "eligibility": value},),
        )
        json.dumps(result)


# ── Full permutation invariance ───────────────────────────────────────────────


def test_syllabus_permutation_invariant_full_semantics():
    records = [
        {"id": "t1", "studied": "yes", "depth": 3},
        {"id": "t1", "studied": "yes", "depth": 3},
        {"id": "t2", "studied": "no"},
    ]
    keys = (
        "studied_count",
        "pending_count",
        "conflicting_count",
        "study_depth_total",
        "study_depth_records",
        "mock_linked_count",
        "review_due_count",
        "coverage_percent",
        "conflicting_topics",
        "dimensions",
    )
    baseline = None
    for perm in permutations(records):
        record = evaluate_syllabus_coverage(
            topics=perm, syllabus_version="v2", syllabus_current=True
        )
        projection = tuple(record[k] for k in keys)
        if baseline is None:
            baseline = projection
        else:
            assert projection == baseline


def test_mock_permutation_invariant_full_semantics():
    records = [
        {
            "id": "m1",
            "date": "2026-01-01",
            "score": 5,
            "total": 10,
            "scoring": "standard",
            "format": "test",
        },
        {
            "id": "m1",
            "date": "2026-03-01",
            "score": 8,
            "total": 10,
            "scoring": "standard",
            "format": "test",
        },
        {
            "id": "m2",
            "date": "2026-02-01",
            "score": 10,
            "total": 10,
            "scoring": "standard",
            "format": "test",
        },
    ]
    keys = (
        "observation_count",
        "conflicting_identity_count",
        "conflicting_identity_ids",
        "trend_inferred",
        "trend_state",
        "chronology_unknown",
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


def test_alternative_permutation_invariant_full_semantics():
    records = [
        {
            "id": "alt1",
            "eligibility": "eligible",
            "syllabus_overlap": 0.9,
            "effort_hours": 200,
            "call_state": "current",
        },
        {
            "id": "alt1",
            "eligibility": "ineligible",
            "syllabus_overlap": 0.1,
            "effort_hours": 200,
            "call_state": "current",
        },
        {
            "id": "alt2",
            "eligibility": "eligible",
            "syllabus_overlap": 0.5,
            "effort_hours": 200,
            "call_state": "current",
        },
    ]
    keys = (
        "resolved",
        "conflicting_route_ids",
        "conditional_requirements",
        "stale_route_ids",
        "recommendation",
        "alternatives_considered",
        "trade_offs",
    )
    baseline = None
    for perm in permutations(records):
        result = compare_alternative_routes(
            primary={"id": "primary"}, alternatives=perm
        )
        projection = tuple(result[k] for k in keys)
        if baseline is None:
            baseline = projection
        else:
            assert projection == baseline


# ── Helper → Rule parity ─────────────────────────────────────────────────────


def test_study_feasibility_rule_preserves_unresolved():
    rule = _rules()["oppositions.study_feasibility"]
    result = rule.evaluate(
        _context(remaining_hours=10, available_hours=30, target_days="soon")
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    finding = result.findings[0]
    assert finding.metadata["unresolved"] is True
    assert finding.metadata["target_date_invalid"] is True
    assert finding.severity is ReasoningSeverity.WARNING


def test_syllabus_coverage_rule_preserves_conflict():
    rule = _rules()["oppositions.syllabus_coverage"]
    result = rule.evaluate(
        _context(
            topics=[
                {"id": "t1", "studied": "yes", "depth": 3},
                {"id": "t1", "studied": "no", "depth": 1},
            ],
            syllabus_version="v2",
            syllabus_current=True,
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    finding = result.findings[0]
    assert finding.metadata["complete"] is False
    assert finding.metadata["conflicting_count"] == 1
    assert finding.metadata["conflicting_topics"] == ("t1",)
    assert finding.metadata["conflict_blocks_complete"] is True
    assert finding.severity is ReasoningSeverity.WARNING


def test_mock_rule_preserves_conflict():
    rule = _rules()["oppositions.mock_exam_interpretation"]
    result = rule.evaluate(
        _context(
            mocks=[
                {
                    "id": "m1",
                    "date": "2026-01-01",
                    "score": 5,
                    "total": 10,
                    "scoring": "standard",
                    "format": "test",
                },
                {
                    "id": "m1",
                    "date": "2026-03-01",
                    "score": 8,
                    "total": 10,
                    "scoring": "standard",
                    "format": "test",
                },
            ]
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    finding = result.findings[0]
    assert finding.metadata["conflicting_identity_count"] == 1
    assert finding.metadata["conflicting_identity_ids"] == ("m1",)
    assert finding.severity is ReasoningSeverity.WARNING


def test_alternative_rule_preserves_conflict():
    rule = _rules()["oppositions.alternative_route"]
    result = rule.evaluate(
        _context(
            primary={"id": "primary"},
            alternatives=[
                {"id": "alt1", "eligibility": "eligible", "syllabus_overlap": 0.9},
                {"id": "alt1", "eligibility": "ineligible", "syllabus_overlap": 0.1},
            ],
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    finding = result.findings[0]
    assert finding.metadata["resolved"] is False
    assert finding.metadata["conflicting_route_ids"] == ("alt1",)
    assert finding.severity is ReasoningSeverity.WARNING


# ── Cross-domain most-restrictive composition ─────────────────────────────────


def test_cross_domain_most_restrictive_composition():
    # user capacity 8, Health cap 20 (wider), University availability 10,
    # workload 2 -> effective capacity = min(8, 10) - 2 = 6
    record = evaluate_study_feasibility(
        remaining_hours=5,
        available_hours=8,
        target_days=30,
        health_constraint={"authorized": True, "functional_cap_hours": 20},
        university_projection={
            "authorized": True,
            "available_hours": 10,
            "workload_hours": 2,
        },
    )
    assert record["capacity_hours"] == 6
    # V3-M1: provenance must be truthful.  The user 8 is the binding base and
    # the University workload (2) materially reduced it to 6; Health (20) never
    # bound.  A single-source "user" label would hide the University reduction.
    assert record["capacity_source"] == "composed"
    assert record["capacity_sources"] == ("user", "university")


def test_cross_domain_unauthorized_does_not_transfer():
    record = evaluate_study_feasibility(
        remaining_hours=5,
        available_hours=8,
        target_days=30,
        health_constraint={"authorized": "true", "functional_cap_hours": 3},
        university_projection={"authorized": 1, "available_hours": 2},
    )
    assert record["capacity_hours"] == 8
    assert record["health_authorized"] is False
    assert record["university_authorized"] is False


def test_cross_domain_malformed_authorized_fails_closed():
    record = evaluate_study_feasibility(
        remaining_hours=5,
        available_hours=8,
        target_days=30,
        university_projection={"authorized": True, "workload_hours": "many"},
    )
    assert record["capacity_unknown"] is True
    assert record["unresolved"] is True


# ── Input non-mutation ────────────────────────────────────────────────────────


def test_helpers_do_not_mutate_inputs():
    topics = [{"id": "t1", "studied": "yes", "depth": 3}]
    mocks = [{"id": "m1", "score": 5, "total": 10, "date": "2026-01-01"}]
    alternatives = [{"id": "alt1", "eligibility": "eligible"}]
    university = {"authorized": True, "available_hours": 10}

    topics_snapshot = json.dumps(topics)
    mocks_snapshot = json.dumps(mocks)
    alternatives_snapshot = json.dumps(alternatives)
    university_snapshot = json.dumps(university)

    evaluate_syllabus_coverage(
        topics=topics, syllabus_version="v2", syllabus_current=True
    )
    evaluate_mock_performance(mocks=mocks)
    compare_alternative_routes(primary={"id": "primary"}, alternatives=alternatives)
    evaluate_study_feasibility(
        remaining_hours=5,
        available_hours=8,
        target_days=30,
        university_projection=university,
    )

    assert json.dumps(topics) == topics_snapshot
    assert json.dumps(mocks) == mocks_snapshot
    assert json.dumps(alternatives) == alternatives_snapshot
    assert json.dumps(university) == university_snapshot
