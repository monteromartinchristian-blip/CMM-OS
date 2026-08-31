"""Phase 10.23 — Adversarial input / order-invariance / no-evidence-deletion
matrix for the Opposition domain (spec §33–§35, §49)."""

from __future__ import annotations

from cmm.domains.oppositions.rules import (
    classify_opposition_source_authority,
    classify_opposition_temporal,
    evaluate_mock_performance,
    evaluate_study_feasibility,
    evaluate_syllabus_coverage,
)

# §33 adversarial values, used where they make sense per target contract.
_VALUES = [
    None,
    7,
    True,
    False,
    "",
    "abc",
    [],
    (),
    {},
    [7],
    [{}],
    ({"valid": "claim"}, 7),
    ["unexpected"],
    {"unexpected": object()},
]


def test_source_authority_malformed_collections_no_raise():
    for value in _VALUES:
        result = classify_opposition_source_authority(
            attribute="application_deadline", sources=value
        )
        assert isinstance(result, dict)
        assert "authority_unknown" in result


def test_source_authority_malformed_attribute_no_raise():
    for value in (None, 7, "", [], {}):
        result = classify_opposition_source_authority(attribute=value, sources=())
        assert result["authority_unknown"] is True
        assert result["reason"] == "malformed_requested_attribute"


def test_source_authority_string_not_sequence():
    result = classify_opposition_source_authority(
        attribute="exam_date", sources="not-a-list"
    )
    assert result["authority_unknown"] is True


def test_temporal_malformed_values_no_raise():
    for value in _VALUES:
        result = classify_opposition_temporal(fact=value)
        assert isinstance(result, dict)
        assert result["state"] in ("missing", "malformed", "unknown", "current")


def test_syllabus_malformed_inputs_no_raise():
    for value in _VALUES:
        result = evaluate_syllabus_coverage(topics=value)
        assert isinstance(result, dict)


def test_mock_malformed_inputs_no_raise():
    for value in _VALUES:
        result = evaluate_mock_performance(mocks=value)
        assert isinstance(result, dict)


def test_feasibility_malformed_numeric_no_raise():
    for value in _VALUES:
        result = evaluate_study_feasibility(remaining_hours=value, available_hours=10)
        assert isinstance(result, dict)


def test_truthy_authorization_not_true():
    result = evaluate_study_feasibility(
        remaining_hours=20,
        available_hours=30,
        health_constraint={"authorized": "true", "functional_cap_hours": 5},
    )
    assert result["health_authorized"] is False


def test_malformed_evidence_not_silently_deleted():
    """A malformed member must keep the outcome unresolved, not be filtered."""

    def _src(source_id, value, cls):
        return {
            "source_id": source_id,
            "source_class": cls,
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
            "value": value,
            "supplied_attributes": ("exam_date",),
            "scope": "body:admin",
        }

    sources = (
        _src("o1", "2026-08-01", "specific_official_call"),
        7,  # malformed member
    )
    result = classify_opposition_source_authority(
        attribute="exam_date", sources=sources, scope="body:admin"
    )
    # a confident resolution is NOT produced from the remaining valid member
    assert result["authority_resolved"] is False


def test_malformed_scope_never_global_in_resolver():
    call = {
        "source_id": "c1",
        "source_class": "specific_official_call",
        "provenance": "grounded",
        "temporal": "valid",
        "specificity": "specific",
        "value": "2026-08-01",
        "supplied_attributes": ("exam_date",),
        "scope": 7,  # malformed
    }
    result = classify_opposition_source_authority(
        attribute="exam_date", sources=(call,), scope="body:admin"
    )
    assert result["authority_unknown"] is True


def test_order_invariance_source_authority_conflict():
    a = (
        {
            "source_id": "c1",
            "source_class": "specific_official_call",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
            "value": "2026-08-01",
            "supplied_attributes": ("exam_date",),
            "scope": "body:admin",
        },
        {
            "source_id": "c2",
            "source_class": "specific_official_call",
            "provenance": "grounded",
            "temporal": "valid",
            "specificity": "specific",
            "value": "2026-09-01",
            "supplied_attributes": ("exam_date",),
            "scope": "body:admin",
        },
    )
    b = (a[1], a[0])
    r1 = classify_opposition_source_authority(
        attribute="exam_date", sources=a, scope="body:admin"
    )
    r2 = classify_opposition_source_authority(
        attribute="exam_date", sources=b, scope="body:admin"
    )
    assert r1["conflict"] is True
    assert r1["conflict"] == r2["conflict"]
    assert r1["authority_resolved"] == r2["authority_resolved"]
