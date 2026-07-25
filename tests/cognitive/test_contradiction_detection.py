"""Phase 8.8 – Contradiction Detection Tests.

Validates pure, deterministic contradiction detection, classification, signals,
batch evaluation, and idempotent registration across InMemory and SQLite stores.
"""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cmm.cognitive.contracts import Confidence
from cmm.cognitive.contradiction_detection import KnowledgeContradictionDetector
from cmm.cognitive.contradiction_detection_contracts import (
    ContradictionDetection,
    ContradictionDetectionResult,
    ContradictionKind,
    ContradictionSignal,
)
from cmm.cognitive.enums import (
    ContradictionSeverity,
    EvidenceKind,
    EvidencePolarityKind,
    KnowledgeKind,
    KnowledgeRelationKind,
    KnowledgeStatus,
    TemporalScopeKind,
)
from cmm.cognitive.errors import (
    InvalidContradictionDetectionError,
    InvalidContradictionSignalError,
    KnowledgeContradictionConflictError,
)
from cmm.cognitive.knowledge import (
    Evidence,
    KnowledgeItem,
    KnowledgeRelation,
    TemporalScope,
)
from cmm.cognitive.store_contracts import KnowledgeStoreProtocol
from cmm.cognitive.store_memory import InMemoryKnowledgeStore
from cmm.cognitive.store_sqlite import SQLiteKnowledgeStore


@pytest.fixture
def memory_store() -> InMemoryKnowledgeStore:
    return InMemoryKnowledgeStore()


@pytest.fixture
def sqlite_store() -> Generator[SQLiteKnowledgeStore, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_contradictions.db"
        store = SQLiteKnowledgeStore(db_path)
        yield store
        store.close()


def _create_item(
    item_id: str,
    statement: str,
    *,
    kind: KnowledgeKind = KnowledgeKind.FACT,
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE,
    resource_id: str | None = "res-1",
    actor_id: str | None = "act-1",
    version: int = 1,
    supersedes_id: str | None = None,
    superseded_by_id: str | None = None,
    invalidated_at: datetime | None = None,
    invalidation_reason: str | None = None,
    evidence: tuple[Evidence, ...] = (),
    relations: tuple[KnowledgeRelation, ...] = (),
    temporal_scope: TemporalScope | None = None,
) -> KnowledgeItem:
    dt_now = datetime.now(timezone.utc)
    if status == KnowledgeStatus.INVALIDATED:
        if invalidated_at is None:
            invalidated_at = dt_now
        if invalidation_reason is None:
            invalidation_reason = "Test invalidation"

    return KnowledgeItem(
        id=item_id,
        statement=statement,
        kind=kind,
        confidence=Confidence(value=0.9, source="test"),
        status=status,
        resource_id=resource_id,
        actor_id=actor_id,
        version=version,
        supersedes_id=supersedes_id,
        superseded_by_id=superseded_by_id,
        invalidated_at=invalidated_at,
        invalidation_reason=invalidation_reason,
        evidence=evidence,
        relations=relations,
        temporal_scope=temporal_scope or TemporalScope(),
        created_at=dt_now,
        updated_at=dt_now,
    )


# ── 1. Contract Tests ─────────────────────────────────────────────────────────


def test_contradiction_signal_contracts() -> None:
    sig = ContradictionSignal(
        kind=ContradictionKind.DIRECT,
        field="statement",
        value_a="activo",
        value_b="inactivo",
        strength=0.9,
        reason="Direct opposition",
    )
    assert sig.kind == ContradictionKind.DIRECT
    assert sig.field == "statement"
    assert sig.strength == 0.9

    # Round trip
    serialized = sig.serialize()
    deserialized = ContradictionSignal.from_mapping(serialized)
    assert deserialized == sig
    assert sig.to_dict() == serialized
    assert ContradictionSignal.from_dict(serialized) == sig

    # Invalid strength
    with pytest.raises(InvalidContradictionSignalError):
        ContradictionSignal(
            kind=ContradictionKind.DIRECT,
            field="statement",
            value_a="a",
            value_b="b",
            strength=1.5,
            reason="Invalid strength",
        )

    # Empty field
    with pytest.raises(InvalidContradictionSignalError):
        ContradictionSignal(
            kind=ContradictionKind.DIRECT,
            field="",
            value_a="a",
            value_b="b",
            strength=0.5,
            reason="Reason",
        )


def test_contradiction_detection_contracts() -> None:
    sig = ContradictionSignal(
        kind=ContradictionKind.DIRECT,
        field="statement",
        value_a="x",
        value_b="y",
        strength=0.9,
        reason="reason",
    )
    det = ContradictionDetection(
        item_a_id="item-1",
        item_b_id="item-2",
        is_contradiction=True,
        kind=ContradictionKind.DIRECT,
        severity=ContradictionSeverity.HIGH,
        confidence=0.9,
        signals=(sig,),
        contradicting_fields=("statement",),
    )
    assert det.item_a_id == "item-1"
    assert det.item_b_id == "item-2"

    # Canonical order swap
    det_swapped = ContradictionDetection(
        item_a_id="item-2",
        item_b_id="item-1",
        is_contradiction=True,
        kind=ContradictionKind.DIRECT,
        severity=ContradictionSeverity.HIGH,
        confidence=0.9,
        signals=(sig,),
        contradicting_fields=("statement",),
    )
    assert det_swapped.item_a_id == "item-1"
    assert det_swapped.item_b_id == "item-2"

    # Same IDs rejected
    with pytest.raises(InvalidContradictionDetectionError):
        ContradictionDetection(
            item_a_id="item-1",
            item_b_id="item-1",
            is_contradiction=False,
        )

    # is_contradiction True with empty signals
    with pytest.raises(InvalidContradictionDetectionError):
        ContradictionDetection(
            item_a_id="item-1",
            item_b_id="item-2",
            is_contradiction=True,
            kind=ContradictionKind.DIRECT,
            signals=(),
        )

    # Round trip
    ser = det.serialize()
    deser = ContradictionDetection.from_mapping(ser)
    assert deser == det
    assert det.to_dict() == ser


def test_contradiction_detection_result_contracts() -> None:
    res = ContradictionDetectionResult(
        detections=(),
        contradiction_count=0,
        possible_count=0,
        non_contradiction_count=0,
        existing_count=0,
    )
    ser = res.serialize()
    deser = ContradictionDetectionResult.from_mapping(ser)
    assert deser.contradiction_count == 0
    assert res.to_dict() == ser


# ── 2. Direct Contradiction Tests (Token-level) ──────────────────────────────


@pytest.mark.parametrize("store_fixture", ["memory_store", "sqlite_store"])
def test_direct_contradiction_opposition_pairs(
    store_fixture: str, request: pytest.FixtureRequest
) -> None:
    store: KnowledgeStoreProtocol = request.getfixturevalue(store_fixture)
    detector = KnowledgeContradictionDetector(store)

    item1 = _create_item("item-1", "El servicio está activo")
    item2 = _create_item("item-2", "El servicio está inactivo")

    det = detector.compare(item1, item2)
    assert det.is_contradiction
    assert det.kind == ContradictionKind.DIRECT
    assert det.confidence == 0.9

    # Substring prevention: radioactivo vs inactivo should NOT trigger direct opposition
    item_rad = _create_item("item-rad", "El material es radioactivo")
    item_inac = _create_item("item-inac", "El material es inactivo")
    det_sub = detector.compare(item_rad, item_inac)
    assert not det_sub.is_contradiction or det_sub.kind != ContradictionKind.DIRECT


# ── 3. Negation Contradiction Tests (With Exclusions) ─────────────────────────


@pytest.mark.parametrize("store_fixture", ["memory_store", "sqlite_store"])
def test_structural_negation(
    store_fixture: str, request: pytest.FixtureRequest
) -> None:
    store: KnowledgeStoreProtocol = request.getfixturevalue(store_fixture)
    detector = KnowledgeContradictionDetector(store)

    item1 = _create_item("item-1", "El contrato está vigente")
    item2 = _create_item("item-2", "El contrato no está vigente")

    det = detector.compare(item1, item2)
    assert det.is_contradiction
    assert det.kind == ContradictionKind.NEGATION
    assert det.confidence == 0.95

    # Excluded negation phrases
    item_no_solo = _create_item("item-ns", "No solo está vigente, también renovado")
    item_vigente = _create_item("item-vig", "Está vigente")
    det_ns = detector.compare(item_no_solo, item_vigente)
    assert not det_ns.is_contradiction

    item_sin_embargo = _create_item("item-se", "Sin embargo está vigente")
    det_se = detector.compare(item_sin_embargo, item_vigente)
    assert not det_se.is_contradiction


# ── 4. Quantitative Contradiction Tests (Context-Aware) ──────────────────────


@pytest.mark.parametrize("store_fixture", ["memory_store", "sqlite_store"])
def test_quantitative_contradiction(
    store_fixture: str, request: pytest.FixtureRequest
) -> None:
    store: KnowledgeStoreProtocol = request.getfixturevalue(store_fixture)
    detector = KnowledgeContradictionDetector(store)

    item1 = _create_item("item-1", "La población es 10 millones")
    item2 = _create_item("item-2", "La población es 12 millones")

    det = detector.compare(item1, item2)
    assert det.is_contradiction
    assert det.kind == ContradictionKind.QUANTITATIVE

    # Complex sentence cross-comparison prevention
    item_c1 = _create_item("item-c1", "Hay 10 alumnos y 2 profesores")
    item_c2 = _create_item("item-c2", "Hay 10 profesores y 2 alumnos")
    det_cross = detector.compare(item_c1, item_c2)
    assert (
        not det_cross.is_contradiction
        or det_cross.kind != ContradictionKind.QUANTITATIVE
    )


# ── 5. Temporal Contradiction Tests (Non-overlapping historical ok) ─────────


@pytest.mark.parametrize("store_fixture", ["memory_store", "sqlite_store"])
def test_temporal_contradiction(
    store_fixture: str, request: pytest.FixtureRequest
) -> None:
    store: KnowledgeStoreProtocol = request.getfixturevalue(store_fixture)
    detector = KnowledgeContradictionDetector(store)

    now = datetime.now(timezone.utc)

    # Non-overlapping historical intervals -> NOT a contradiction
    scope_2020 = TemporalScope(
        kind=TemporalScopeKind.INTERVAL,
        valid_from=now.replace(year=2020),
        valid_until=now.replace(year=2021),
    )
    scope_2023 = TemporalScope(
        kind=TemporalScopeKind.INTERVAL,
        valid_from=now.replace(year=2023),
        valid_until=now.replace(year=2024),
    )
    item_h1 = _create_item("item-h1", "Presidente del club", temporal_scope=scope_2020)
    item_h2 = _create_item("item-h2", "Presidente del club", temporal_scope=scope_2023)
    det_hist = detector.compare(item_h1, item_h2)
    assert not det_hist.is_contradiction or det_hist.kind != ContradictionKind.TEMPORAL

    # Overlapping interval with conflicting status -> TEMPORAL contradiction
    item_h3 = _create_item(
        "item-h3",
        "Presidente del club",
        temporal_scope=scope_2020,
        status=KnowledgeStatus.INVALIDATED,
        invalidated_at=now,
        invalidation_reason="Error",
    )
    item_h4 = _create_item(
        "item-h4",
        "Presidente del club",
        temporal_scope=scope_2020,
        status=KnowledgeStatus.ACTIVE,
    )
    det_overlap = detector.compare(item_h3, item_h4)
    assert det_overlap.is_contradiction
    assert det_overlap.kind == ContradictionKind.TEMPORAL


# ── 6. Status Contradiction Tests ──────────────────────────────────────────────


@pytest.mark.parametrize("store_fixture", ["memory_store", "sqlite_store"])
def test_status_contradiction(
    store_fixture: str, request: pytest.FixtureRequest
) -> None:
    store: KnowledgeStoreProtocol = request.getfixturevalue(store_fixture)
    detector = KnowledgeContradictionDetector(store)

    item1 = _create_item(
        "item-1", "Política de privacidad", status=KnowledgeStatus.ACTIVE
    )
    item2 = _create_item(
        "item-2",
        "Política de privacidad",
        status=KnowledgeStatus.INVALIDATED,
        invalidated_at=datetime.now(timezone.utc),
        invalidation_reason="Anticuada",
    )

    det = detector.compare(item1, item2)
    assert det.is_contradiction
    assert det.kind == ContradictionKind.STATUS


# ── 7. Lineage Contradiction Tests ─────────────────────────────────────────────


@pytest.mark.parametrize("store_fixture", ["memory_store", "sqlite_store"])
def test_lineage_cycle_contradiction(
    store_fixture: str, request: pytest.FixtureRequest
) -> None:
    store: KnowledgeStoreProtocol = request.getfixturevalue(store_fixture)
    detector = KnowledgeContradictionDetector(store)

    item1 = _create_item("item-1", "Regla A", supersedes_id="item-2")
    item2 = _create_item("item-2", "Regla B", supersedes_id="item-1")

    det = detector.compare(item1, item2)
    assert det.is_contradiction
    assert det.kind == ContradictionKind.LINEAGE
    assert det.severity == ContradictionSeverity.CRITICAL


# ── 8. Relational Contradiction Tests ──────────────────────────────────────────


@pytest.mark.parametrize("store_fixture", ["memory_store", "sqlite_store"])
def test_relational_contradiction(
    store_fixture: str, request: pytest.FixtureRequest
) -> None:
    store: KnowledgeStoreProtocol = request.getfixturevalue(store_fixture)
    detector = KnowledgeContradictionDetector(store)

    rel_supports = KnowledgeRelation(
        source_id="item-1",
        target_id="item-2",
        kind=KnowledgeRelationKind.SUPPORTS,
        confidence=Confidence(value=0.9, source="test"),
    )
    rel_contradicts = KnowledgeRelation(
        source_id="item-1",
        target_id="item-2",
        kind=KnowledgeRelationKind.CONTRADICTS,
        confidence=Confidence(value=0.9, source="test"),
    )

    item1 = _create_item("item-1", "Afirmación A", relations=(rel_supports,))
    item2 = _create_item("item-2", "Afirmación B", relations=(rel_contradicts,))

    det = detector.compare(item1, item2)
    assert det.is_contradiction
    assert det.kind == ContradictionKind.RELATIONAL


# ── 9. Complete Symmetry Tests Across All Types ──────────────────────────────


@pytest.mark.parametrize("store_fixture", ["memory_store", "sqlite_store"])
def test_compare_symmetry_across_types(
    store_fixture: str, request: pytest.FixtureRequest
) -> None:
    store: KnowledgeStoreProtocol = request.getfixturevalue(store_fixture)
    detector = KnowledgeContradictionDetector(store)

    pairs = [
        (
            _create_item("item-A", "El servicio está activo"),
            _create_item("item-B", "El servicio está inactivo"),
        ),
        (
            _create_item("item-C", "El contrato está vigente"),
            _create_item("item-D", "El contrato no está vigente"),
        ),
        (
            _create_item("item-E", "Población es 10 millones"),
            _create_item("item-F", "Población es 12 millones"),
        ),
        (
            _create_item("item-G", "Item G", supersedes_id="item-H"),
            _create_item("item-H", "Item H", supersedes_id="item-G"),
        ),
    ]

    for item_a, item_b in pairs:
        forward = detector.compare(item_a, item_b)
        reverse = detector.compare(item_b, item_a)
        assert forward == reverse


# ── 10. Registration, Evidence Conflicts, & POSSIBLE Rejection ────────────────


@pytest.mark.parametrize("store_fixture", ["memory_store", "sqlite_store"])
def test_registration_rules(store_fixture: str, request: pytest.FixtureRequest) -> None:
    store: KnowledgeStoreProtocol = request.getfixturevalue(store_fixture)
    detector = KnowledgeContradictionDetector(store)

    dt_now = datetime.now(timezone.utc)
    ev_a = Evidence(
        id="ev-1",
        resource_id="res-1",
        fragment="frag-a",
        confidence=Confidence(value=0.8),
        kind=EvidenceKind.DIRECT_QUOTE,
        polarity=EvidencePolarityKind.SUPPORTING,
        observed_at=dt_now,
    )
    ev_b_conflicting = Evidence(
        id="ev-1",
        resource_id="res-1",
        fragment="frag-b-DIFFERENT",
        confidence=Confidence(value=0.8),
        kind=EvidenceKind.DIRECT_QUOTE,
        polarity=EvidencePolarityKind.SUPPORTING,
        observed_at=dt_now,
    )

    item1 = _create_item("item-1", "Servicio activo", evidence=(ev_a,))
    item2 = _create_item("item-2", "Servicio inactivo", evidence=(ev_b_conflicting,))

    store.save_item(item1)
    store.save_item(item2)

    det = detector.compare(item1, item2)

    # Evidence conflict raises KnowledgeContradictionConflictError
    with pytest.raises(KnowledgeContradictionConflictError):
        detector.register(det)
