"""Phase 8.4 – Knowledge Model tests.

Covers: TemporalScope, Evidence, KnowledgeRelation, KnowledgeItem,
Contradiction, KnowledgeBundle, materializer, public API, deep immutability,
canonical serialize/from_mapping round-trips, and compatibility with Phase 8.3.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cmm.cognitive import (
    Confidence,
    Contradiction,
    ContradictionSeverity,
    ContradictionStatus,
    Evidence,
    EvidenceKind,
    EvidencePolarityKind,
    ExtractionCandidate,
    ExtractionEvidence,
    InvalidContradictionError,
    InvalidEvidenceError,
    InvalidKnowledgeBundleError,
    InvalidKnowledgeItemError,
    InvalidKnowledgeModelError,
    InvalidKnowledgeRelationError,
    InvalidTemporalValidityError,
    KnowledgeBundle,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeRelation,
    KnowledgeRelationKind,
    KnowledgeStatus,
    SensitivityLevel,
    TemporalScope,
    TemporalScopeKind,
    TemporalValidityStatus,
    materialise_candidate,
    materialise_evidence,
    materialise_result,
)
from cmm.cognitive.enums import CandidateKind, ExtractionStatus
from cmm.cognitive.extraction import KnowledgeExtractionResult


NOW = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
FUTURE = NOW + timedelta(days=30)
PAST = NOW - timedelta(days=30)


# ── helpers ───────────────────────────────────────────────────────────────────


def confidence(value: float = 0.8) -> Confidence:
    return Confidence(value=value, source="test")


def make_evidence(
    resource_id: str = "resource:test:doc",
    fragment: str = "The project is active.",
    *,
    ev_id: str = "evidence:knowledge:test-ev",
) -> Evidence:
    return Evidence(
        id=ev_id,
        resource_id=resource_id,
        fragment=fragment,
        confidence=confidence(0.9),
        observed_at=NOW,
    )


def make_item(
    statement: str = "The project has a Cognitive Layer.",
    *,
    kind: KnowledgeKind = KnowledgeKind.OBSERVATION,
    item_id: str | None = None,
) -> KnowledgeItem:
    kwargs: dict = dict(
        statement=statement,
        kind=kind,
        confidence=confidence(),
        created_at=NOW,
        updated_at=NOW,
    )
    if item_id is not None:
        kwargs["id"] = item_id
    return KnowledgeItem(**kwargs)


def make_extraction_evidence(
    resource_id: str = "resource:test:doc",
) -> ExtractionEvidence:
    return ExtractionEvidence(
        resource_id=resource_id,
        fragment="The system was deployed.",
        start=0,
        end=25,
        section="intro",
    )


def make_candidate(
    *,
    kind: CandidateKind = CandidateKind.STATEMENT,
    value: str = "The system is operational.",
    resource_id: str = "resource:test:doc",
) -> ExtractionCandidate:
    return ExtractionCandidate(
        kind=kind,
        value=value,
        confidence=confidence(0.75),
        resource_id=resource_id,
        extractor_name="plain-text-extractor",
        evidence=make_extraction_evidence(resource_id),
    )


# ── TemporalScope ─────────────────────────────────────────────────────────────


def test_temporal_scope_defaults_to_unknown() -> None:
    scope = TemporalScope()
    assert scope.kind is TemporalScopeKind.UNKNOWN


def test_temporal_scope_timeless_valid_at_any_moment() -> None:
    scope = TemporalScope(kind=TemporalScopeKind.TIMELESS)
    assert scope.is_valid_at(NOW) is True
    assert scope.is_valid_at(FUTURE) is True


def test_temporal_scope_unknown_invalid_at_any_moment() -> None:
    scope = TemporalScope(kind=TemporalScopeKind.UNKNOWN)
    assert scope.is_valid_at(NOW) is False


def test_temporal_scope_interval_contains_matching_moment() -> None:
    scope = TemporalScope(
        kind=TemporalScopeKind.INTERVAL,
        valid_from=NOW,
        valid_until=FUTURE,
    )
    assert scope.is_valid_at(NOW + timedelta(days=1)) is True
    assert scope.is_valid_at(PAST) is False


def test_temporal_scope_contains_alias_works() -> None:
    scope = TemporalScope(kind=TemporalScopeKind.TIMELESS)
    assert scope.contains(NOW) is True


def test_temporal_scope_point_in_time_exact_match() -> None:
    scope = TemporalScope(kind=TemporalScopeKind.POINT_IN_TIME, observed_at=NOW)
    assert scope.is_valid_at(NOW) is True
    assert scope.is_valid_at(FUTURE) is False


def test_temporal_scope_interval_requires_both_bounds() -> None:
    with pytest.raises(InvalidTemporalValidityError):
        TemporalScope(kind=TemporalScopeKind.INTERVAL, valid_from=NOW)


def test_temporal_scope_point_in_time_requires_observed_at() -> None:
    with pytest.raises(InvalidTemporalValidityError):
        TemporalScope(kind=TemporalScopeKind.POINT_IN_TIME)


def test_temporal_scope_rejects_reversed_interval() -> None:
    with pytest.raises(InvalidTemporalValidityError):
        TemporalScope(
            kind=TemporalScopeKind.INTERVAL,
            valid_from=FUTURE,
            valid_until=NOW,
        )


def test_temporal_scope_rejects_naive_datetimes() -> None:
    with pytest.raises(InvalidTemporalValidityError):
        TemporalScope(
            kind=TemporalScopeKind.POINT_IN_TIME,
            observed_at=datetime(2026, 7, 25, 12, 0),
        )


def test_temporal_scope_serialization_round_trip() -> None:
    scope = TemporalScope(
        kind=TemporalScopeKind.INTERVAL,
        valid_from=NOW,
        valid_until=FUTURE,
        metadata={"source": "test"},
    )
    payload = scope.serialize()
    assert payload["kind"] == "interval"
    assert payload["valid_from"] == NOW.isoformat()
    assert payload["valid_until"] == FUTURE.isoformat()
    assert payload["metadata"] == {"source": "test"}

    restored = TemporalScope.from_mapping(payload)
    assert restored == scope


def test_temporal_scope_from_dict_and_from_mapping_alias() -> None:
    scope = TemporalScope(
        kind=TemporalScopeKind.INTERVAL,
        valid_from=NOW,
        valid_until=FUTURE,
    )
    payload = scope.to_dict()
    restored_from_dict = TemporalScope.from_dict(payload)
    restored_from_mapping = TemporalScope.from_mapping(payload)
    assert restored_from_dict == scope
    assert restored_from_mapping == scope


def test_temporal_scope_validity_status_enum() -> None:
    timeless = TemporalScope(kind=TemporalScopeKind.TIMELESS)
    assert timeless.validity_status is TemporalValidityStatus.TIMELESS

    expired = TemporalScope(
        kind=TemporalScopeKind.INTERVAL,
        valid_from=PAST - timedelta(days=10),
        valid_until=PAST,
    )
    assert expired.validity_status is TemporalValidityStatus.EXPIRED


def test_temporal_scope_immutable() -> None:
    scope = TemporalScope(kind=TemporalScopeKind.TIMELESS)
    with pytest.raises(Exception):
        scope.kind = TemporalScopeKind.UNKNOWN  # type: ignore[misc]


# ── Evidence ──────────────────────────────────────────────────────────────────


def test_evidence_valid_construction() -> None:
    ev = make_evidence()
    assert ev.resource_id == "resource:test:doc"
    assert ev.confidence.value == 0.9


def test_evidence_serializes_all_traceability_fields() -> None:
    ev = Evidence(
        id="evidence:knowledge:e1",
        resource_id="resource:test:doc",
        fragment="The result was positive.",
        confidence=confidence(0.85),
        kind=EvidenceKind.DIRECT_QUOTE,
        polarity=EvidencePolarityKind.SUPPORTING,
        locator="para:1",
        section="results",
        page=3,
        char_start=10,
        char_end=40,
        actor_id="agent:test",
        extraction_candidate_id="extraction-candidate:general:xyz",
        resource_provenance_id="resource:prov:abc",
        observed_at=NOW,
        metadata={"tag": "verified"},
    )
    payload = ev.serialize()
    assert payload["id"] == "evidence:knowledge:e1"
    assert payload["kind"] == "direct_quote"
    assert payload["polarity"] == "supporting"
    assert payload["section"] == "results"
    assert payload["page"] == 3
    assert payload["char_start"] == 10
    assert payload["char_end"] == 40
    assert payload["actor_id"] == "agent:test"
    assert payload["extraction_candidate_id"] == "extraction-candidate:general:xyz"
    assert payload["resource_provenance_id"] == "resource:prov:abc"
    assert payload["observed_at"] == NOW.isoformat()

    restored = Evidence.from_mapping(payload)
    assert restored == ev


def test_evidence_from_dict_and_from_mapping_alias() -> None:
    ev = Evidence(
        id="evidence:knowledge:e2",
        resource_id="resource:test:doc",
        fragment="test fragment",
        confidence=confidence(0.7),
        observed_at=NOW,
    )
    restored = Evidence.from_mapping(ev.serialize())
    assert restored == ev
    assert Evidence.from_dict(ev.to_dict()) == ev


def test_evidence_rejects_empty_resource_id() -> None:
    with pytest.raises(InvalidEvidenceError):
        Evidence(
            resource_id="", fragment="content", confidence=confidence(), observed_at=NOW
        )


def test_evidence_rejects_empty_fragment() -> None:
    with pytest.raises(InvalidEvidenceError):
        Evidence(
            resource_id="res:test:x",
            fragment="   ",
            confidence=confidence(),
            observed_at=NOW,
        )


def test_evidence_rejects_blank_locator() -> None:
    with pytest.raises(InvalidEvidenceError):
        Evidence(
            resource_id="res:test:x",
            fragment="content",
            confidence=confidence(),
            locator="   ",
            observed_at=NOW,
        )


def test_evidence_rejects_negative_char_start() -> None:
    with pytest.raises(InvalidEvidenceError):
        Evidence(
            resource_id="res:test:x",
            fragment="content",
            confidence=confidence(),
            char_start=-1,
            observed_at=NOW,
        )


def test_evidence_rejects_char_end_before_char_start() -> None:
    with pytest.raises(InvalidEvidenceError):
        Evidence(
            resource_id="res:test:x",
            fragment="content",
            confidence=confidence(),
            char_start=10,
            char_end=5,
            observed_at=NOW,
        )


def test_evidence_rejects_naive_observed_at() -> None:
    with pytest.raises(InvalidTemporalValidityError):
        Evidence(
            resource_id="res:test:x",
            fragment="content",
            confidence=confidence(),
            observed_at=datetime(2026, 7, 25, 12, 0),
        )


def test_evidence_immutable() -> None:
    ev = make_evidence()
    with pytest.raises(Exception):
        ev.fragment = "mutated"  # type: ignore[misc]


# ── KnowledgeRelation ─────────────────────────────────────────────────────────


def test_relation_valid_construction() -> None:
    rel = KnowledgeRelation(
        source_id="knowledge-item:knowledge:a",
        target_id="knowledge-item:knowledge:b",
        kind=KnowledgeRelationKind.SUPPORTS,
        confidence=confidence(),
        created_at=NOW,
    )
    assert rel.kind is KnowledgeRelationKind.SUPPORTS


def test_relation_rejects_self_reference() -> None:
    with pytest.raises(InvalidKnowledgeRelationError):
        KnowledgeRelation(
            source_id="knowledge-item:knowledge:same",
            target_id="knowledge-item:knowledge:same",
            kind=KnowledgeRelationKind.RELATED_TO,
            confidence=confidence(),
            created_at=NOW,
        )


def test_relation_rejects_empty_source_id() -> None:
    with pytest.raises(InvalidKnowledgeRelationError):
        KnowledgeRelation(
            source_id="",
            target_id="knowledge-item:knowledge:b",
            kind=KnowledgeRelationKind.RELATED_TO,
            confidence=confidence(),
            created_at=NOW,
        )


def test_relation_serialization_preserves_semantics() -> None:
    rel = KnowledgeRelation(
        id="knowledge-relation:knowledge:test",
        source_id="knowledge-item:knowledge:a",
        target_id="knowledge-item:knowledge:b",
        kind=KnowledgeRelationKind.CONTRADICTS,
        confidence=confidence(0.75),
        actor_id="agent:test",
        provenance="extraction-run-42",
        created_at=NOW,
    )
    payload = rel.serialize()
    assert payload["kind"] == "contradicts"
    assert payload["actor_id"] == "agent:test"
    assert payload["provenance"] == "extraction-run-42"

    restored = KnowledgeRelation.from_mapping(payload)
    assert restored == rel


def test_relation_from_dict_and_from_mapping_alias() -> None:
    rel = KnowledgeRelation(
        id="knowledge-relation:knowledge:r1",
        source_id="knowledge-item:knowledge:a",
        target_id="knowledge-item:knowledge:b",
        kind=KnowledgeRelationKind.DERIVED_FROM,
        confidence=confidence(),
        created_at=NOW,
    )
    restored = KnowledgeRelation.from_mapping(rel.serialize())
    assert restored == rel
    assert KnowledgeRelation.from_dict(rel.to_dict()) == rel


def test_relation_all_kinds_constructible() -> None:
    for kind in KnowledgeRelationKind:
        rel = KnowledgeRelation(
            source_id="knowledge-item:knowledge:a",
            target_id="knowledge-item:knowledge:b",
            kind=kind,
            confidence=confidence(),
            created_at=NOW,
        )
        assert rel.kind is kind


# ── KnowledgeItem ─────────────────────────────────────────────────────────────


def test_knowledge_item_defaults_to_active_first_version() -> None:
    item = make_item()
    assert item.status is KnowledgeStatus.ACTIVE
    assert item.version == 1
    assert item.is_active is True


def test_knowledge_item_all_kinds_constructible() -> None:
    for kind in KnowledgeKind:
        item = KnowledgeItem(
            statement="A statement.",
            kind=kind,
            confidence=confidence(),
            created_at=NOW,
            updated_at=NOW,
        )
        assert item.kind is kind


def test_knowledge_item_supports_actor_and_resource() -> None:
    item = KnowledgeItem(
        statement="The agent created this.",
        kind=KnowledgeKind.OBSERVATION,
        confidence=confidence(),
        actor_id="agent:cmm:main",
        resource_id="resource:test:doc",
        created_at=NOW,
        updated_at=NOW,
    )
    assert item.actor_id == "agent:cmm:main"
    assert item.resource_id == "resource:test:doc"


def test_knowledge_item_sensitivity_level() -> None:
    item = KnowledgeItem(
        statement="Sensitive information.",
        kind=KnowledgeKind.OBSERVATION,
        confidence=confidence(),
        sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
        created_at=NOW,
        updated_at=NOW,
    )
    assert item.sensitivity is SensitivityLevel.HIGHLY_SENSITIVE
    payload = item.serialize()
    assert payload["sensitivity"] == "highly_sensitive"

    restored = KnowledgeItem.from_mapping(payload)
    assert restored == item


def test_knowledge_item_serialization_and_round_trip() -> None:
    item = KnowledgeItem(
        id="knowledge-item:knowledge:serialized",
        statement="Serializable knowledge.",
        kind=KnowledgeKind.INFERENCE,
        confidence=confidence(0.7),
        evidence=(make_evidence(),),
        temporal_scope=TemporalScope(
            kind=TemporalScopeKind.CURRENT,
            valid_from=NOW,
        ),
        sensitivity=SensitivityLevel.SENSITIVE,
        actor_id="agent:test",
        resource_id="resource:test:doc",
        created_at=NOW,
        updated_at=NOW,
        metadata={"domain": "testing"},
    )
    payload = item.serialize()
    assert payload["id"] == "knowledge-item:knowledge:serialized"
    assert payload["kind"] == "inference"
    assert payload["status"] == "active"
    assert payload["version"] == 1
    assert payload["is_active"] is True
    assert payload["sensitivity"] == "sensitive"
    assert payload["actor_id"] == "agent:test"
    assert payload["resource_id"] == "resource:test:doc"
    assert payload["evidence"][0]["resource_id"] == "resource:test:doc"
    assert payload["metadata"] == {"domain": "testing"}

    restored = KnowledgeItem.from_mapping(payload)
    assert restored == item
    assert KnowledgeItem.from_dict(item.to_dict()) == item


def test_knowledge_item_rejects_empty_statement() -> None:
    with pytest.raises(InvalidKnowledgeItemError):
        KnowledgeItem(
            statement="   ",
            kind=KnowledgeKind.OBSERVATION,
            confidence=confidence(),
            created_at=NOW,
            updated_at=NOW,
        )


def test_knowledge_item_rejects_version_zero() -> None:
    with pytest.raises(InvalidKnowledgeItemError):
        KnowledgeItem(
            statement="A statement.",
            kind=KnowledgeKind.OBSERVATION,
            confidence=confidence(),
            version=0,
            created_at=NOW,
            updated_at=NOW,
        )


def test_knowledge_item_rejects_updated_at_before_created_at() -> None:
    with pytest.raises(InvalidKnowledgeItemError):
        KnowledgeItem(
            statement="Timestamp issue.",
            kind=KnowledgeKind.OBSERVATION,
            confidence=confidence(),
            created_at=NOW,
            updated_at=NOW - timedelta(seconds=1),
        )


def test_knowledge_item_rejects_duplicate_evidence() -> None:
    ev = make_evidence()
    with pytest.raises(InvalidKnowledgeItemError):
        KnowledgeItem(
            statement="Duplicated.",
            kind=KnowledgeKind.OBSERVATION,
            confidence=confidence(),
            evidence=(ev, ev),
            created_at=NOW,
            updated_at=NOW,
        )


def test_knowledge_item_rejects_duplicate_relations() -> None:
    rel = KnowledgeRelation(
        id="knowledge-relation:knowledge:dup",
        source_id="knowledge-item:knowledge:a",
        target_id="knowledge-item:knowledge:b",
        kind=KnowledgeRelationKind.RELATED_TO,
        confidence=confidence(),
        created_at=NOW,
    )
    with pytest.raises(InvalidKnowledgeItemError):
        KnowledgeItem(
            statement="Duplicated rel.",
            kind=KnowledgeKind.OBSERVATION,
            confidence=confidence(),
            relations=(rel, rel),
            created_at=NOW,
            updated_at=NOW,
        )


def test_knowledge_item_invalidated_requires_audit_fields() -> None:
    with pytest.raises(InvalidKnowledgeItemError):
        KnowledgeItem(
            statement="Missing audit.",
            kind=KnowledgeKind.OBSERVATION,
            confidence=confidence(),
            status=KnowledgeStatus.INVALIDATED,
            created_at=NOW,
            updated_at=NOW,
        )


def test_knowledge_item_active_rejects_invalidation_fields() -> None:
    with pytest.raises(InvalidKnowledgeItemError):
        KnowledgeItem(
            statement="Inconsistent.",
            kind=KnowledgeKind.OBSERVATION,
            confidence=confidence(),
            invalidated_at=NOW,
            invalidation_reason="Unexpected.",
            created_at=NOW,
            updated_at=NOW,
        )


def test_knowledge_item_superseded_requires_successor() -> None:
    with pytest.raises(InvalidKnowledgeItemError):
        KnowledgeItem(
            statement="Superseded without successor.",
            kind=KnowledgeKind.OBSERVATION,
            confidence=confidence(),
            status=KnowledgeStatus.SUPERSEDED,
            created_at=NOW,
            updated_at=NOW,
        )


def test_invalidate_returns_new_immutable_state() -> None:
    item = make_item()
    ts = NOW + timedelta(hours=1)
    invalidated = item.invalidate("Source withdrawn.", invalidated_at=ts)

    assert item.status is KnowledgeStatus.ACTIVE
    assert invalidated.status is KnowledgeStatus.INVALIDATED
    assert invalidated.invalidated_at == ts
    assert invalidated.invalidation_reason == "Source withdrawn."
    assert invalidated.is_active is False


def test_invalidate_requires_non_empty_reason() -> None:
    with pytest.raises(InvalidKnowledgeItemError):
        make_item().invalidate("")


def test_create_revision_increments_version_and_links_predecessor() -> None:
    item = KnowledgeItem(
        id="knowledge-item:knowledge:original",
        statement="Original.",
        kind=KnowledgeKind.HYPOTHESIS,
        confidence=confidence(0.4),
        version=3,
        created_at=NOW,
        updated_at=NOW,
    )
    ts = NOW + timedelta(hours=2)
    revision = item.create_revision(
        statement="Revised.",
        confidence=confidence(0.85),
        created_at=ts,
    )

    assert revision.id != item.id
    assert revision.version == 4
    assert revision.supersedes_id == item.id
    assert revision.statement == "Revised."
    assert revision.status is KnowledgeStatus.ACTIVE
    assert revision.created_at == ts


def test_mark_superseded_preserves_original() -> None:
    item = make_item()
    superseded = item.mark_superseded(
        "knowledge-item:knowledge:new",
        superseded_at=NOW + timedelta(hours=1),
    )
    assert item.status is KnowledgeStatus.ACTIVE
    assert superseded.status is KnowledgeStatus.SUPERSEDED
    assert superseded.superseded_by_id == "knowledge-item:knowledge:new"
    assert superseded.is_active is False


def test_knowledge_item_immutable() -> None:
    item = make_item()
    with pytest.raises(Exception):
        item.statement = "mutated"  # type: ignore[misc]


# ── Contradiction ─────────────────────────────────────────────────────────────


def test_contradiction_valid_unresolved() -> None:
    c = Contradiction(
        item_a_id="knowledge-item:knowledge:a",
        item_b_id="knowledge-item:knowledge:b",
        created_at=NOW,
    )
    assert c.status is ContradictionStatus.UNRESOLVED
    assert c.severity is ContradictionSeverity.MEDIUM


def test_contradiction_with_preferred_and_reason() -> None:
    c = Contradiction(
        item_a_id="knowledge-item:knowledge:a",
        item_b_id="knowledge-item:knowledge:b",
        preferred_id="knowledge-item:knowledge:a",
        preference_reason="More recent and verified.",
        created_at=NOW,
    )
    assert c.preferred_id == "knowledge-item:knowledge:a"


def test_contradiction_rejects_same_items() -> None:
    with pytest.raises(InvalidContradictionError):
        Contradiction(
            item_a_id="knowledge-item:knowledge:same",
            item_b_id="knowledge-item:knowledge:same",
            created_at=NOW,
        )


def test_contradiction_rejects_preferred_not_in_pair() -> None:
    with pytest.raises(InvalidContradictionError):
        Contradiction(
            item_a_id="knowledge-item:knowledge:a",
            item_b_id="knowledge-item:knowledge:b",
            preferred_id="knowledge-item:knowledge:c",
            preference_reason="Unrelated.",
            created_at=NOW,
        )


def test_contradiction_requires_preference_reason_when_preferred_set() -> None:
    with pytest.raises(InvalidContradictionError):
        Contradiction(
            item_a_id="knowledge-item:knowledge:a",
            item_b_id="knowledge-item:knowledge:b",
            preferred_id="knowledge-item:knowledge:a",
            created_at=NOW,
        )


def test_contradiction_preserves_supporting_evidence() -> None:
    ev = make_evidence()
    c = Contradiction(
        item_a_id="knowledge-item:knowledge:a",
        item_b_id="knowledge-item:knowledge:b",
        supporting_evidence=(ev,),
        explanation="Sources disagree on the date.",
        remaining_uncertainty="±2 days",
        created_at=NOW,
    )
    payload = c.serialize()
    assert len(payload["supporting_evidence"]) == 1
    assert payload["explanation"] == "Sources disagree on the date."
    assert payload["remaining_uncertainty"] == "±2 days"

    restored = Contradiction.from_mapping(payload)
    assert restored == c


def test_contradiction_does_not_auto_resolve() -> None:
    c = Contradiction(
        item_a_id="knowledge-item:knowledge:a",
        item_b_id="knowledge-item:knowledge:b",
        created_at=NOW,
    )
    assert c.status is ContradictionStatus.UNRESOLVED


def test_contradiction_serialization_and_round_trip() -> None:
    c = Contradiction(
        id="contradiction:knowledge:c1",
        item_a_id="knowledge-item:knowledge:a",
        item_b_id="knowledge-item:knowledge:b",
        severity=ContradictionSeverity.HIGH,
        created_at=NOW,
    )
    payload = c.serialize()
    assert payload["id"] == "contradiction:knowledge:c1"
    assert payload["severity"] == "high"
    assert payload["status"] == "unresolved"

    restored = Contradiction.from_mapping(payload)
    assert restored == c
    assert Contradiction.from_dict(c.to_dict()) == c


def test_contradiction_immutable() -> None:
    c = Contradiction(
        item_a_id="knowledge-item:knowledge:a",
        item_b_id="knowledge-item:knowledge:b",
        created_at=NOW,
    )
    with pytest.raises(Exception):
        c.status = ContradictionStatus.RESOLVED  # type: ignore[misc]


# ── KnowledgeBundle ───────────────────────────────────────────────────────────


def test_bundle_empty_is_valid() -> None:
    bundle = KnowledgeBundle(created_at=NOW)
    assert bundle.item_count == 0
    assert bundle.has_contradictions is False
    assert bundle.has_open_questions is False


def test_bundle_with_items_and_contradictions() -> None:
    item_a = make_item("Statement A.", item_id="knowledge-item:knowledge:a")
    item_b = make_item("Statement B.", item_id="knowledge-item:knowledge:b")
    contradiction = Contradiction(
        item_a_id=item_a.id,
        item_b_id=item_b.id,
        created_at=NOW,
    )
    bundle = KnowledgeBundle(
        items=(item_a, item_b),
        contradictions=(contradiction,),
        open_questions=("Is A still valid?",),
        findings=("Extraction was partial.",),
        actor_id="agent:test",
        created_at=NOW,
    )
    assert bundle.item_count == 2
    assert bundle.has_contradictions is True
    assert bundle.has_open_questions is True


def test_bundle_rejects_duplicate_item_ids() -> None:
    item = make_item(item_id="knowledge-item:knowledge:dup")
    with pytest.raises(InvalidKnowledgeBundleError):
        KnowledgeBundle(items=(item, item), created_at=NOW)


def test_bundle_rejects_empty_status() -> None:
    with pytest.raises(InvalidKnowledgeBundleError):
        KnowledgeBundle(status="   ", created_at=NOW)


def test_bundle_serialization_and_round_trip() -> None:
    item = make_item(item_id="knowledge-item:knowledge:s1")
    bundle = KnowledgeBundle(
        id="knowledge-bundle:knowledge:b1",
        items=(item,),
        open_questions=("Open Q1",),
        findings=("Finding 1",),
        actor_id="agent:test",
        status="partial",
        created_at=NOW,
        metadata={"run": "42"},
    )
    payload = bundle.serialize()
    assert payload["id"] == "knowledge-bundle:knowledge:b1"
    assert payload["item_count"] == 1
    assert payload["has_contradictions"] is False
    assert payload["open_questions"] == ["Open Q1"]
    assert payload["status"] == "partial"
    assert payload["metadata"] == {"run": "42"}

    restored = KnowledgeBundle.from_mapping(payload)
    assert restored == bundle
    assert KnowledgeBundle.from_dict(bundle.to_dict()) == bundle


def test_bundle_immutable() -> None:
    bundle = KnowledgeBundle(created_at=NOW)
    with pytest.raises(Exception):
        bundle.status = "mutated"  # type: ignore[misc]


# ── Metadata Deep Immutability Tests ──────────────────────────────────────────


def test_metadata_immutability_input_dict_mutation() -> None:
    input_meta = {"key": "initial"}
    item = make_item()
    scope = TemporalScope(metadata=input_meta)

    # Mutate original dictionary
    input_meta["key"] = "mutated"

    assert scope.metadata["key"] == "initial"


def test_metadata_immutability_attribute_mutation_fails() -> None:
    item = make_item()
    with pytest.raises(TypeError):
        item.metadata["new_key"] = "value"  # type: ignore[index]


def test_metadata_immutability_serialized_dict_mutation() -> None:
    item = KnowledgeItem(
        statement="A statement.",
        kind=KnowledgeKind.OBSERVATION,
        confidence=confidence(),
        metadata={"nested": {"value": 1}},
        created_at=NOW,
        updated_at=NOW,
    )
    serialized = item.serialize()
    serialized["metadata"]["nested"] = "mutated"

    assert item.metadata["nested"] == {"value": 1}


# ── Epistemological Materializer Guarantees ───────────────────────────────────


def test_no_candidate_kind_materializes_as_fact() -> None:
    for candidate_kind in CandidateKind:
        candidate = make_candidate(kind=candidate_kind)
        item = materialise_candidate(candidate, observed_at=NOW)
        assert item.kind is not KnowledgeKind.FACT, (
            f"CandidateKind.{candidate_kind.name} must never materialize as FACT"
        )


def test_candidate_kind_materialization_epistemological_mapping() -> None:
    expected_mappings = {
        CandidateKind.STATEMENT: KnowledgeKind.OBSERVATION,
        CandidateKind.ENTITY_MENTION: KnowledgeKind.OBSERVATION,
        CandidateKind.RELATIONSHIP_MENTION: KnowledgeKind.OBSERVATION,
        CandidateKind.TEMPORAL_REFERENCE: KnowledgeKind.OBSERVATION,
        CandidateKind.QUANTITY: KnowledgeKind.OBSERVATION,
        CandidateKind.KEYWORD: KnowledgeKind.OBSERVATION,
        CandidateKind.QUESTION: KnowledgeKind.QUESTION,
        CandidateKind.UNKNOWN: KnowledgeKind.HYPOTHESIS,
    }
    for candidate_kind, expected_kind in expected_mappings.items():
        candidate = make_candidate(kind=candidate_kind)
        item = materialise_candidate(candidate, observed_at=NOW)
        assert item.kind is expected_kind


def test_materialise_evidence_preserves_all_provenance_fields() -> None:
    ext_ev = ExtractionEvidence(
        resource_id="resource:test:doc",
        fragment="The result was 42.",
        start=10,
        end=28,
        section="results",
        page=5,
        selector="para:3",
    )
    ev = materialise_evidence(
        ext_ev,
        confidence=confidence(0.8),
        actor_id="agent:extractor",
        extraction_candidate_id="extraction-candidate:general:x",
        resource_provenance_id="resource:prov:p1",
        observed_at=NOW,
    )
    assert ev.resource_id == "resource:test:doc"
    assert ev.fragment == "The result was 42."
    assert ev.char_start == 10
    assert ev.char_end == 28
    assert ev.section == "results"
    assert ev.page == 5
    assert ev.locator == "para:3"
    assert ev.actor_id == "agent:extractor"
    assert ev.extraction_candidate_id == "extraction-candidate:general:x"
    assert ev.resource_provenance_id == "resource:prov:p1"
    assert ev.kind is EvidenceKind.EXTRACTION_CANDIDATE
    assert ev.polarity is EvidencePolarityKind.SUPPORTING


def test_materialise_candidate_produces_unverified_item() -> None:
    candidate = make_candidate()
    item = materialise_candidate(candidate, actor_id="agent:test", observed_at=NOW)

    assert item.status is KnowledgeStatus.UNVERIFIED
    assert item.statement == "The system is operational."
    assert item.kind is KnowledgeKind.OBSERVATION
    assert item.actor_id == "agent:test"
    assert item.resource_id == "resource:test:doc"
    assert len(item.evidence) == 1
    assert item.evidence[0].extraction_candidate_id == candidate.id


def test_materialise_candidate_question_kind_preserved() -> None:
    candidate = make_candidate(
        kind=CandidateKind.QUESTION, value="Is the system stable?"
    )
    item = materialise_candidate(candidate, observed_at=NOW)
    assert item.kind is KnowledgeKind.QUESTION


def test_materialise_candidate_preserves_confidence() -> None:
    candidate = make_candidate()
    item = materialise_candidate(candidate, observed_at=NOW)
    assert item.confidence.value == candidate.confidence.value


def test_materialise_candidate_does_not_invent_facts() -> None:
    candidate = make_candidate(kind=CandidateKind.UNKNOWN, value="Unclear signal.")
    item = materialise_candidate(candidate, observed_at=NOW)
    assert item.kind is KnowledgeKind.HYPOTHESIS


def test_materialise_candidate_preserves_resource_id() -> None:
    candidate = make_candidate(resource_id="resource:test:special-doc")
    item = materialise_candidate(candidate, observed_at=NOW)
    assert item.resource_id == "resource:test:special-doc"
    assert item.evidence[0].resource_id == "resource:test:special-doc"


def test_materialise_result_produces_bundle_with_items() -> None:
    result = KnowledgeExtractionResult(
        resource_id="resource:test:doc",
        extractor_name="plain-text-extractor",
        extractor_version="1.0",
        status=ExtractionStatus.COMPLETED,
        candidates=(make_candidate(), make_candidate(value="Second candidate.")),
        created_at=NOW,
    )
    bundle = materialise_result(result, actor_id="agent:test")

    assert bundle.item_count == 2
    assert bundle.actor_id == "agent:test"
    assert bundle.status == "completed"
    assert bundle.metadata["resource_id"] == "resource:test:doc"
    assert bundle.metadata["extractor_name"] == "plain-text-extractor"


def test_materialise_result_open_questions_from_question_candidates() -> None:
    q_candidate = make_candidate(
        kind=CandidateKind.QUESTION, value="Is the API stable?"
    )
    result = KnowledgeExtractionResult(
        resource_id="resource:test:doc",
        extractor_name="test-extractor",
        extractor_version="1.0",
        status=ExtractionStatus.COMPLETED,
        candidates=(q_candidate,),
        created_at=NOW,
    )
    bundle = materialise_result(result)
    assert "Is the API stable?" in bundle.open_questions


def test_materialise_result_warnings_become_findings() -> None:
    result = KnowledgeExtractionResult(
        resource_id="resource:test:doc",
        extractor_name="test-extractor",
        extractor_version="1.0",
        status=ExtractionStatus.PARTIAL,
        candidates=(),
        warnings=("Content truncated.",),
        errors=("Parser timeout.",),
        created_at=NOW,
    )
    bundle = materialise_result(result)
    assert "Content truncated." in bundle.findings
    assert any("Parser timeout." in f for f in bundle.findings)
    assert bundle.status == "partial"


def test_materialise_result_preserves_provenance_in_evidence() -> None:
    candidate = make_candidate()
    result = KnowledgeExtractionResult(
        resource_id="resource:test:doc",
        extractor_name="plain-text-extractor",
        extractor_version="1.0",
        status=ExtractionStatus.COMPLETED,
        candidates=(candidate,),
        created_at=NOW,
    )
    bundle = materialise_result(result, actor_id="agent:test")
    ev = bundle.items[0].evidence[0]
    assert ev.extraction_candidate_id == candidate.id
    assert ev.actor_id == "agent:test"


def test_materialise_result_no_contradictions_introduced() -> None:
    c1 = make_candidate(value="A is true.")
    c2 = make_candidate(value="A is false.")
    result = KnowledgeExtractionResult(
        resource_id="resource:test:doc",
        extractor_name="test-extractor",
        extractor_version="1.0",
        status=ExtractionStatus.COMPLETED,
        candidates=(c1, c2),
        created_at=NOW,
    )
    bundle = materialise_result(result)
    assert bundle.has_contradictions is False


# ── Deserialization Error Handling Tests ──────────────────────────────────────


def test_deserialization_unknown_enum_raises_error() -> None:
    item_payload = make_item().serialize()
    item_payload["kind"] = "invalid_kind_value"
    with pytest.raises(InvalidKnowledgeItemError):
        KnowledgeItem.from_mapping(item_payload)

    with pytest.raises(InvalidKnowledgeItemError):
        item_payload2 = make_item().serialize()
        item_payload2["sensitivity"] = "invalid_sensitivity"
        KnowledgeItem.from_mapping(item_payload2)


def test_deserialization_invalid_timestamp_raises_error() -> None:
    item_payload = make_item().serialize()
    item_payload["created_at"] = "not-a-timestamp"
    with pytest.raises(InvalidKnowledgeItemError):
        KnowledgeItem.from_mapping(item_payload)


# ── Public API ────────────────────────────────────────────────────────────────


def test_public_api_exports_knowledge_model_symbols() -> None:
    import cmm.cognitive as cog

    assert hasattr(cog, "KnowledgeItem")
    assert hasattr(cog, "Evidence")
    assert hasattr(cog, "KnowledgeRelation")
    assert hasattr(cog, "TemporalScope")
    assert hasattr(cog, "Contradiction")
    assert hasattr(cog, "KnowledgeBundle")
    assert hasattr(cog, "materialise_candidate")
    assert hasattr(cog, "materialise_evidence")
    assert hasattr(cog, "materialise_result")


def test_public_api_exports_8_4_enums() -> None:
    import cmm.cognitive as cog

    assert hasattr(cog, "KnowledgeKind")
    assert hasattr(cog, "KnowledgeStatus")
    assert hasattr(cog, "KnowledgeRelationKind")
    assert hasattr(cog, "TemporalScopeKind")
    assert hasattr(cog, "EvidenceKind")
    assert hasattr(cog, "EvidencePolarityKind")
    assert hasattr(cog, "ContradictionSeverity")
    assert hasattr(cog, "ContradictionStatus")
    assert hasattr(cog, "TemporalValidityStatus")


def test_public_api_exports_8_4_errors() -> None:
    import cmm.cognitive as cog

    assert hasattr(cog, "InvalidKnowledgeItemError")
    assert hasattr(cog, "InvalidEvidenceError")
    assert hasattr(cog, "InvalidTemporalValidityError")
    assert hasattr(cog, "InvalidKnowledgeRelationError")
    assert hasattr(cog, "InvalidContradictionError")
    assert hasattr(cog, "InvalidKnowledgeBundleError")
    # backward compat alias
    assert hasattr(cog, "InvalidKnowledgeModelError")
    assert cog.InvalidKnowledgeModelError is cog.InvalidKnowledgeItemError


def test_8_1_8_2_8_3_exports_still_present() -> None:
    """Regression guard: 8.4 must not break previous public exports."""
    import cmm.cognitive as cog

    # 8.1
    assert hasattr(cog, "Confidence")
    assert hasattr(cog, "CognitiveActor")
    # 8.2
    assert hasattr(cog, "Resource")
    assert hasattr(cog, "ResourceProvenance")
    # 8.3
    assert hasattr(cog, "ExtractionCandidate")
    assert hasattr(cog, "KnowledgeExtractionResult")
    assert hasattr(cog, "ResourceExtractionService")
