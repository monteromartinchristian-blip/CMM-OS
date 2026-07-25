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
    ContradictionStatus,
    KnowledgeKind,
    KnowledgeRelationKind,
    KnowledgeStatus,
    TemporalScopeKind,
)
from cmm.cognitive.errors import (
    InvalidContradictionDetectionError,
    InvalidContradictionSignalError,
)
from cmm.cognitive.knowledge import (
    Contradiction,
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


# ── 2. Direct Contradiction Tests ──────────────────────────────────────────────


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
    assert det.severity in (ContradictionSeverity.HIGH, ContradictionSeverity.MEDIUM)
    assert det.confidence == 0.9


# ── 3. Negation Contradiction Tests ────────────────────────────────────────────


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

    # False positive test
    item3 = _create_item("item-3", "No solo está vigente, también renovado")
    det_fp = detector.compare(item1, item3)
    assert not det_fp.is_contradiction or det_fp.kind == ContradictionKind.POSSIBLE


# ── 4. Quantitative Contradiction Tests ────────────────────────────────────────


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
    assert "statement" in det.contradicting_fields

    # Decimal comma test
    item3 = _create_item("item-3", "El porcentaje es 20,5 %")
    item4 = _create_item("item-4", "El porcentaje es 35,0 %")
    det_dec = detector.compare(item3, item4)
    assert det_dec.is_contradiction
    assert det_dec.kind == ContradictionKind.QUANTITATIVE


# ── 5. Temporal Contradiction Tests ────────────────────────────────────────────


@pytest.mark.parametrize("store_fixture", ["memory_store", "sqlite_store"])
def test_temporal_contradiction(
    store_fixture: str, request: pytest.FixtureRequest
) -> None:
    store: KnowledgeStoreProtocol = request.getfixturevalue(store_fixture)
    detector = KnowledgeContradictionDetector(store)

    now = datetime.now(timezone.utc)
    scope_valid = TemporalScope(
        kind=TemporalScopeKind.CURRENT,
    )
    scope_expired = TemporalScope(
        kind=TemporalScopeKind.INTERVAL,
        valid_from=now.replace(year=2020),
        valid_until=now.replace(year=2021),
    )

    item1 = _create_item("item-1", "Servicio operativo", temporal_scope=scope_valid)
    item2 = _create_item("item-2", "Servicio operativo", temporal_scope=scope_expired)

    det = detector.compare(item1, item2)
    assert det.is_contradiction
    assert det.kind == ContradictionKind.TEMPORAL
    assert "temporal_scope" in det.contradicting_fields


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
    assert "status" in det.contradicting_fields


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
    assert det.confidence == 1.0


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


# ── 9. Symmetry & Determinism Tests ────────────────────────────────────────────


@pytest.mark.parametrize("store_fixture", ["memory_store", "sqlite_store"])
def test_compare_symmetry_and_determinism(
    store_fixture: str, request: pytest.FixtureRequest
) -> None:
    store: KnowledgeStoreProtocol = request.getfixturevalue(store_fixture)
    detector = KnowledgeContradictionDetector(store)

    item_a = _create_item("item-A", "El sistema está activo")
    item_b = _create_item("item-B", "El sistema está inactivo")

    det_ab = detector.compare(item_a, item_b)
    det_ba = detector.compare(item_b, item_a)

    assert det_ab == det_ba
    assert det_ab.item_a_id == "item-A"
    assert det_ab.item_b_id == "item-B"


# ── 10. Batch Detection Tests ─────────────────────────────────────────────────


@pytest.mark.parametrize("store_fixture", ["memory_store", "sqlite_store"])
def test_batch_detection(store_fixture: str, request: pytest.FixtureRequest) -> None:
    store: KnowledgeStoreProtocol = request.getfixturevalue(store_fixture)
    detector = KnowledgeContradictionDetector(store)

    item1 = _create_item("item-1", "Servidor activo")
    item2 = _create_item("item-2", "Servidor inactivo")
    item3 = _create_item("item-3", "Servidor inactivo")

    store.save_item(item1)
    store.save_item(item2)
    store.save_item(item3)

    result = detector.detect()
    assert len(result.detections) == 3
    assert result.contradiction_count >= 2


# ── 11. Registration & Idempotency Tests ───────────────────────────────────────


@pytest.mark.parametrize("store_fixture", ["memory_store", "sqlite_store"])
def test_registration_and_idempotency(
    store_fixture: str, request: pytest.FixtureRequest
) -> None:
    store: KnowledgeStoreProtocol = request.getfixturevalue(store_fixture)
    detector = KnowledgeContradictionDetector(store)

    item1 = _create_item("item-1", "Documento aprobado")
    item2 = _create_item("item-2", "Documento no aprobado")

    store.save_item(item1)
    store.save_item(item2)

    det = detector.compare(item1, item2)
    c1 = detector.register(det)

    assert isinstance(c1, Contradiction)
    assert c1.item_a_id == "item-1"
    assert c1.item_b_id == "item-2"
    assert c1.status == ContradictionStatus.UNRESOLVED
    assert c1.preferred_id is None

    # Idempotency
    c2 = detector.register(det)
    assert c1.id == c2.id
    assert len(store.list_contradictions(item_id="item-1")) == 1


# ── 12. Detect and Register Tests ──────────────────────────────────────────────


@pytest.mark.parametrize("store_fixture", ["memory_store", "sqlite_store"])
def test_detect_and_register(
    store_fixture: str, request: pytest.FixtureRequest
) -> None:
    store: KnowledgeStoreProtocol = request.getfixturevalue(store_fixture)
    detector = KnowledgeContradictionDetector(store)

    item1 = _create_item("item-1", "Proceso activo")
    item2 = _create_item("item-2", "Proceso inactivo")

    store.save_item(item1)
    store.save_item(item2)

    registered = detector.detect_and_register()
    assert len(registered) == 1
    assert registered[0].status == ContradictionStatus.UNRESOLVED
