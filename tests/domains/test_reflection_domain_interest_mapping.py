"""Phase 10.24 — Reflection source-grounded interest mapping tests.

DP-024 requires interest mapping grounded in sources: one mention is a
candidate only; duplicates never inflate evidence; model-generated summaries
are never independent corroboration; contradiction stays visible; interest
never becomes identity or commitment (spec §16, §28, §44.C).
"""

from __future__ import annotations

import json

from cmm.domains.reflection.rules import map_interests


def _mention(interest, source, *, source_kind="user_statement", explicit=False,
             activity=False, mention=True, context=None, observed_at=None,
             contradictory=False, recording=""):
    return {
        "interest": interest,
        "source": source,
        "source_kind": source_kind,
        "explicit": explicit,
        "activity": activity,
        "mention": mention,
        "context": context,
        "observed_at": observed_at,
        "contradictory": contradictory,
        "recording": recording,
    }


def test_one_explicit_mention_candidate_only():
    result = map_interests(
        records=(
            _mention("photography", "msg:1", explicit=True, context="hobby", observed_at="2026-05-01"),
        )
    )
    assert len(result["interest_candidates"]) == 1
    candidate = result["interest_candidates"][0]
    assert candidate["interest"] == "photography"
    assert candidate["persistent_confirmed"] is False
    assert candidate["mention_count"] == 1
    assert candidate["grounded_evidence_count"] == 1
    assert candidate["uncertainty"] is True


def test_repeated_grounded_activity_stronger_candidate():
    result = map_interests(
        records=(
            _mention("photography", "msg:1", activity=True, mention=True, observed_at="2026-03-01"),
            _mention("photography", "msg:2", activity=True, mention=True, observed_at="2026-06-01"),
            _mention("photography", "msg:3", activity=True, mention=True, observed_at="2026-08-01"),
        )
    )
    candidates = {c["interest"]: c for c in result["interest_candidates"]}
    candidate = candidates["photography"]
    assert candidate["grounded_evidence_count"] == 3
    assert candidate["mention_count"] == 3
    assert candidate["persistent_confirmed"] is False
    assert candidate["relative_strength"] == "stronger"
    assert result["persistent_confirmed"] is False


def test_duplicate_source_does_not_inflate_evidence():
    result = map_interests(
        records=(
            _mention("photography", "same-src", explicit=True, observed_at="2026-05-01"),
            _mention("photography", "same-src", explicit=True, observed_at="2026-05-01"),
        )
    )
    candidate = result["interest_candidates"][0]
    assert candidate["grounded_evidence_count"] == 1
    assert candidate["mention_count"] == 1
    assert len(candidate["sources"]) == 1
    assert "same-src" in result["duplicates_ignored"]


def test_model_summary_is_not_independent_corroboration():
    result = map_interests(
        records=(
            _mention("photography", "msg:1", source_kind="user_statement", explicit=True, observed_at="2026-05-01"),
            _mention("photography", "summary:1", source_kind="model_summary", observed_at="2026-06-01"),
            _mention("photography", "memory:1", source_kind="memory_summary", observed_at="2026-07-01"),
        )
    )
    candidate = result["interest_candidates"][0]
    assert candidate["grounded_evidence_count"] == 1
    assert candidate["independent_grounded_count"] == 1
    assert candidate["model_source_count"] == 2
    assert result["model_inference_not_source"] is True


def test_contradictory_evidence_keeps_uncertainty():
    result = map_interests(
        records=(
            _mention("photography", "msg:1", explicit=True, observed_at="2026-05-01"),
            _mention("photography", "msg:2", contradictory=True, observed_at="2026-06-01"),
        )
    )
    candidate = result["interest_candidates"][0]
    assert candidate["uncertainty"] is True
    assert candidate["counterevidence"] == ("msg:2",)
    assert result["contradictions"] == ("photography",)


def test_single_unrelated_mention_is_not_committed_interest():
    result = map_interests(
        records=(_mention("football", "msg:1", mention=True),)
    )
    candidate = result["interest_candidates"][0]
    assert candidate["persistent_confirmed"] is False
    assert candidate["uncertainty"] is True
    # interest is never converted into identity or commitment
    assert candidate["identity_claim"] is False
    assert candidate["commitment"] is False


def test_interest_not_identity_not_commitment():
    result = map_interests(
        records=(
            _mention("photography", "msg:1", explicit=True, observed_at="2026-05-01"),
            _mention("photography", "msg:2", explicit=True, observed_at="2026-08-01"),
        )
    )
    for candidate in result["interest_candidates"]:
        assert candidate["identity_claim"] is False
        assert candidate["commitment"] is False
        assert candidate["persistent_confirmed"] is False


def test_input_permutation_identical():
    records = (
        _mention("photography", "msg:1", explicit=True, observed_at="2026-05-01"),
        _mention("gardening", "msg:2", activity=True, observed_at="2026-06-01"),
        _mention("photography", "msg:3", activity=True, observed_at="2026-08-01"),
    )
    import itertools

    results = [map_interests(records=tuple(order)) for order in itertools.permutations(records)]
    canonical = {
        tuple(
            (c["interest"], c["grounded_evidence_count"], c["uncertainty"])
            for c in r["interest_candidates"]
        )
        for r in results
    }
    assert len(canonical) == 1


def test_json_safe_interest_result():
    result = map_interests(
        records=(_mention("photography", "msg:1", explicit=True),)
    )
    json.dumps(result, allow_nan=False)


def test_interest_mapping_requires_source_basis():
    """Interest never originates from model association without user evidence."""
    result = map_interests(records=())
    assert result["interest_candidates"] == ()
    assert result["model_inference_not_source"] is True