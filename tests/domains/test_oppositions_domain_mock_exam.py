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
    assert a["trend_inferred"] == b["trend_inferred"]


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