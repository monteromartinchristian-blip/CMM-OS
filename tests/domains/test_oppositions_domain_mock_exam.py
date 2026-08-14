"""Phase 10.23 — MockExamInterpretationRule tests (frozen spec §40)."""

from __future__ import annotations

from cmm.domains.oppositions.rules import evaluate_mock_performance


def _mock(mock_id, score, total, scoring="standard", *, date=None, **overrides):
    mock = {
        "id": mock_id,
        "score": score,
        "total": total,
        "scoring": scoring,
        "date": date or f"2026-01-0{(int(mock_id[-1]) % 9) + 1}",
        "format": "test",
    }
    mock.update(overrides)
    return mock


def test_one_mock_is_observation_not_trend():
    record = evaluate_mock_performance(mocks=(_mock("m1", 30, 50),))
    assert record["trend_state"] == "no_trend"
    assert record["trend_inferred"] is False
    assert record["one_mock_is_trend"] is False


def test_multiple_comparable_mocks_can_establish_trend():
    record = evaluate_mock_performance(
        mocks=(
            _mock("m1", 20, 50, date="2026-01-01"),
            _mock("m2", 30, 50, date="2026-02-01"),
            _mock("m3", 40, 50, date="2026-03-01"),
        )
    )
    assert record["trend_state"] == "trend"
    assert record["trend_inferred"] is True
    assert record["trend_slope"] == 20


def test_incompatible_scoring_regimes_prevent_naive_trend():
    record = evaluate_mock_performance(
        mocks=(
            _mock("m1", 20, 40, scoring="penalty", date="2026-01-01"),
            _mock("m2", 30, 50, scoring="standard", date="2026-02-01"),
        )
    )
    # two different scoring regimes -> only the regime with 2 comparable
    # records forms a trend; here neither regime has 2 -> no trend
    assert record["trend_inferred"] is False


def test_missing_denominator_prevents_invalid_normalization():
    record = evaluate_mock_performance(mocks=(_mock("m1", 30, None),))
    assert record["comparable_count"] == 0
    assert record["trend_inferred"] is False


def test_malformed_score_does_not_promote_certainty():
    record = evaluate_mock_performance(
        mocks=({"id": "m1", "score": "abc", "total": 50},)
    )
    assert record["has_scores"] is False
    assert record["trend_inferred"] is False


def test_unknown_chronology_prevents_temporal_trend():
    record = evaluate_mock_performance(
        mocks=(
            {"id": "m1", "score": 20, "total": 50, "scoring": "standard", "format": "test"},
            {"id": "m2", "score": 30, "total": 50, "scoring": "standard", "format": "test"},
        )
    )
    assert record["chronology_unknown"] is True
    assert record["trend_inferred"] is False


def test_duplicate_mock_identity_not_double_counted():
    record = evaluate_mock_performance(
        mocks=(_mock("m1", 20, 50), _mock("m1", 30, 50))
    )
    assert record["duplicates_ignored"] == 1
    assert record["observation_count"] == 1


def test_order_invariance():
    a = evaluate_mock_performance(
        mocks=(_mock("m2", 30, 50), _mock("m1", 20, 50))
    )
    b = evaluate_mock_performance(
        mocks=(_mock("m1", 20, 50), _mock("m2", 30, 50))
    )
    # normalized semantic meaning, not just a weak boolean
    assert (
        a["trend_inferred"],
        a["trend_slope"],
        a["observation_count"],
        a["comparable_count"],
        a["duplicates_ignored"],
        a["conflicting_identity_count"],
    ) == (
        b["trend_inferred"],
        b["trend_slope"],
        b["observation_count"],
        b["comparable_count"],
        b["duplicates_ignored"],
        b["conflicting_identity_count"],
    )


def test_speed_separate_from_knowledge():
    record = evaluate_mock_performance(
        mocks=(_mock("m1", 30, 50, speed_score=10),)
    )
    assert record["speed_dimension_present"] is True
    assert record["has_scores"] is True
    assert record["speed_knowledge_separated"] is True


def test_format_errors_separate_from_knowledge_errors():
    record = evaluate_mock_performance(
        mocks=(_mock("m1", 30, 50, process_errors=5, knowledge_errors=2),)
    )
    assert record["process_error_dimension_present"] is True


def test_no_intelligence_or_capacity_inference():
    record = evaluate_mock_performance(mocks=(_mock("m1", 49, 50),))
    assert record["intelligence_inferred"] is False
    assert record["capacity_inferred"] is False
    assert record["pass_guaranteed"] is False


def test_different_denominators_prevent_raw_score_trend():
    """Same format/scoring but different scoring bases must not be combined: a
    raw-score rise of 40 -> 50 hides a normalized fall 80% -> 50%."""
    record = evaluate_mock_performance(
        mocks=(
            _mock("m1", 40, 50, date="2026-01-01"),
            _mock("m2", 50, 100, date="2026-02-01"),
        )
    )
    assert record["trend_inferred"] is False


def test_malformed_chronology_blocks_trend():
    """Non-parseable chronology must not be treated as temporal ordering."""
    record = evaluate_mock_performance(
        mocks=(
            _mock("m1", 20, 50, date="zzz"),
            _mock("m2", 30, 50, date="2026-02-01"),
        )
    )
    assert record["chronology_unknown"] is True
    assert record["trend_inferred"] is False


def test_conflicting_duplicate_mock_order_invariance():
    """Conflicting duplicate mock identities must produce the same normalized
    semantics regardless of input order and must not drive a trend."""
    a1 = {"id": "m1", "date": "2026-01-01", "score": 5, "total": 10,
          "scoring": "standard", "format": "test"}
    a2 = {"id": "m1", "date": "2026-03-01", "score": 5, "total": 10,
          "scoring": "standard", "format": "test"}
    b = {"id": "m2", "date": "2026-02-01", "score": 10, "total": 10,
         "scoring": "standard", "format": "test"}
    forward = evaluate_mock_performance(mocks=(a1, a2, b))
    reverse = evaluate_mock_performance(mocks=(a2, a1, b))
    # the conflicting duplicate m1 is unresolved, and no trend is inferred from
    # whichever duplicate happened to appear first.
    assert forward["trend_inferred"] is False
    assert forward["conflicting_identity_count"] == 1
    assert (
        forward["trend_inferred"],
        forward["trend_slope"],
        forward["conflicting_identity_count"],
    ) == (
        reverse["trend_inferred"],
        reverse["trend_slope"],
        reverse["conflicting_identity_count"],
    )


import json


def test_mixed_naive_aware_chronology_never_raises():
    record = evaluate_mock_performance(
        mocks=(
            {"id": "m1", "score": 5, "total": 10, "scoring": "standard",
             "format": "test", "date": "2026-01-01"},
            {"id": "m2", "score": 6, "total": 10, "scoring": "standard",
             "format": "test", "date": "2026-02-01T00:00:00+00:00"},
        )
    )
    assert record["trend_state"] == "trend"
    assert record["trend_inferred"] is True


def test_z_and_explicit_offset_chronology_never_raises():
    record = evaluate_mock_performance(
        mocks=(
            {"id": "m1", "score": 5, "total": 10, "scoring": "standard",
             "format": "test", "date": "2026-01-01T12:00:00Z"},
            {"id": "m2", "score": 6, "total": 10, "scoring": "standard",
             "format": "test", "date": "2026-01-02T12:00:00+02:00"},
        )
    )
    assert record["trend_state"] == "trend"
    assert record["trend_inferred"] is True


def test_mock_helper_result_json_serializable():
    record = evaluate_mock_performance(
        mocks=(
            {"id": "m1", "score": 5, "total": 10, "scoring": "standard",
             "format": "test", "date": "2026-01-01"},
        )
    )
    json.dumps(record)


def test_conflicting_mock_public_result_permutation_invariant():
    a1 = {"id": "m1", "date": "2026-01-01", "score": 5, "total": 10,
          "scoring": "standard", "format": "test"}
    a2 = {"id": "m1", "date": "2026-03-01", "score": 8, "total": 10,
          "scoring": "standard", "format": "test"}
    b = {"id": "m2", "date": "2026-02-01", "score": 10, "total": 10,
         "scoring": "standard", "format": "test"}
    forward = evaluate_mock_performance(mocks=(a1, a2, b))
    reverse = evaluate_mock_performance(mocks=(a2, a1, b))
    # conflicting identity must not expose a first-wins representative
    assert forward["conflicting_identity_count"] == 1
    assert forward["conflicting_identity_ids"] == ("m1",)
    assert forward["timeline"] == reverse["timeline"]
    for key in (
        "observation_count",
        "conflicting_identity_count",
        "conflicting_identity_ids",
        "trend_inferred",
        "trend_state",
        "chronology_unknown",
    ):
        assert forward[key] == reverse[key], key
