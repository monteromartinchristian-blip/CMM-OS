"""Phase 10.23 — SyllabusCoverageRule tests (frozen spec §38)."""

from __future__ import annotations

from cmm.domains.oppositions.rules import evaluate_syllabus_coverage


def _topic(topic_id, studied="yes", **overrides):
    topic = {"id": topic_id, "studied": studied}
    topic.update(overrides)
    return topic


def test_complete_structured_coverage():
    record = evaluate_syllabus_coverage(
        topics=(
            _topic("t1", depth=3, revision="done"),
            _topic("t2", depth=2, revision="done"),
        ),
        syllabus_version="v2",
        syllabus_current=True,
    )
    assert record["complete"] is True
    assert record["studied_count"] == 2
    assert record["pending_count"] == 0


def test_pending_topics_block_completion():
    record = evaluate_syllabus_coverage(
        topics=(
            _topic("t1", studied="yes"),
            _topic("t2", studied="no"),
        ),
        syllabus_version="v2",
        syllabus_current=True,
    )
    assert record["complete"] is False
    assert record["pending_count"] == 1


def test_duplicate_topic_ids_not_double_counted():
    record = evaluate_syllabus_coverage(
        topics=(
            _topic("t1"),
            _topic("t1"),
            _topic("t2"),
        ),
        syllabus_version="v2",
        syllabus_current=True,
    )
    # only 2 distinct topics studied
    assert record["studied_count"] == 2


def test_identityless_topic_cannot_establish_complete_coverage():
    record = evaluate_syllabus_coverage(
        topics=({"studied": "yes"}, {"studied": "yes"}),
        syllabus_version="v2",
        syllabus_current=True,
    )
    assert record["complete"] is False
    assert record["studied_count"] == 0


def test_malformed_topic_collection():
    record = evaluate_syllabus_coverage(topics=7)
    assert record["malformed"] is True
    assert record["complete"] is False


def test_valid_empty_distinct_from_absent_and_malformed():
    empty = evaluate_syllabus_coverage(topics=())
    assert empty["valid_empty"] is True
    assert empty["malformed"] is False
    absent = evaluate_syllabus_coverage(topics=None)
    assert absent["container_present"] is False
    malformed = evaluate_syllabus_coverage(topics=7)
    assert malformed["malformed"] is True


def test_unknown_topic_state():
    record = evaluate_syllabus_coverage(
        topics=(_topic("t1", studied="unknown"),),
        syllabus_version="v2",
        syllabus_current=True,
    )
    assert record["complete"] is False
    assert record["unknown_count"] >= 1


def test_stale_unknown_syllabus_blocks_current_complete():
    record = evaluate_syllabus_coverage(
        topics=(_topic("t1"),),
        syllabus_version=None,
        syllabus_current=False,
    )
    assert record["complete"] is False
    assert record["syllabus_version_unknown"] is True


def test_review_due_does_not_equal_forgotten():
    record = evaluate_syllabus_coverage(
        topics=(_topic("t1", review_due=True),),
        syllabus_version="v2",
        syllabus_current=True,
    )
    assert record["review_cue"] is True
    assert record["forgetting_proven"] is False
    assert record["retention_risk"] is True


def test_elapsed_time_alone_does_not_prove_forgetting():
    record = evaluate_syllabus_coverage(
        topics=(_topic("t1"),),
        past_minutes=10000,
        syllabus_version="v2",
        syllabus_current=True,
    )
    assert record["elapsed_time_cue"] is True
    assert record["forgetting_proven"] is False


def test_mock_without_topic_mapping_does_not_prove_mastery():
    record = evaluate_syllabus_coverage(
        topics=(_topic("t1"), _topic("t2")),
        syllabus_version="v2",
        syllabus_current=True,
    )
    # no mock-linked evidence, but completeness of *coverage* refers to studying
    # not mastery; mock linkage count stays 0.
    assert record["mock_linked_count"] == 0


def test_malformed_member_preserved():
    record = evaluate_syllabus_coverage(topics=[{"id": "t1"}, 7])
    assert record["malformed"] is True
    assert record["complete"] is False


def test_order_invariance():
    a = evaluate_syllabus_coverage(
        topics=(_topic("t2"), _topic("t1")), syllabus_version="v2", syllabus_current=True
    )
    b = evaluate_syllabus_coverage(
        topics=(_topic("t1"), _topic("t2")), syllabus_version="v2", syllabus_current=True
    )
    assert (a["studied_count"], a["complete"]) == (b["studied_count"], b["complete"])