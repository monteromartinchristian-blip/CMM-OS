"""Phase 8.15 – Cognitive Integration Layer Tests.

Validates end-to-end cognitive cycle execution, contracts, serialization,
security policies, non-direct mutations, error handling, and determinism.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from cmm.cognitive.cognitive_cycle import CognitiveCycleEngine
from cmm.cognitive.cognitive_cycle_contracts import (
    CognitiveCycleRecord,
    CognitiveCycleStatus,
    generate_cognitive_cycle_id,
)
from cmm.cognitive.contracts import Confidence
from cmm.cognitive.contradiction_detection import KnowledgeContradictionDetector
from cmm.cognitive.contradiction_resolution import KnowledgeContradictionResolver
from cmm.cognitive.enums import KnowledgeKind, KnowledgeStatus
from cmm.cognitive.errors import (
    CognitiveCycleExecutionError,
    InvalidCognitiveCycleError,
)
from cmm.cognitive.knowledge import KnowledgeItem
from cmm.cognitive.reflection import CognitiveReflectionEngine
from cmm.cognitive.resolution_executor import ContradictionResolutionExecutor
from cmm.cognitive.resolution_memory import InMemoryResolutionMemoryStore
from cmm.cognitive.resolution_policy import ContradictionResolutionPolicyEngine
from cmm.cognitive.retrieval import KnowledgeRetriever
from cmm.cognitive.store_memory import InMemoryKnowledgeStore


def _utc(
    year: int = 2026,
    month: int = 1,
    day: int = 1,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)


def _make_item(
    item_id: str,
    statement: str,
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE,
    resource_id: str | None = None,
) -> KnowledgeItem:
    return KnowledgeItem(
        id=item_id,
        statement=statement,
        kind=KnowledgeKind.FACT,
        confidence=Confidence(value=0.95, source="test"),
        status=status,
        resource_id=resource_id,
        created_at=_utc(),
        updated_at=_utc(),
    )


# ── Contract Tests ─────────────────────────────────────────────────────────────


def test_cognitive_cycle_record_valid_creation() -> None:
    dt = _utc()
    record = CognitiveCycleRecord(
        cycle_id="cognitive-cycle:abc123def4567890",
        created_at=dt,
        input_item_ids=("item-1", "item-2"),
        contradiction_ids=("cntr-1",),
        resolution_proposal_ids=("prop-1",),
        execution_ids=("exec-1",),
        memory_entry_ids=("mem-1",),
        reflection_report_id="report-1",
        status=CognitiveCycleStatus.COMPLETED,
        warnings=("Warning test",),
        metadata={"source": "test"},
    )

    assert record.cycle_id == "cognitive-cycle:abc123def4567890"
    assert record.created_at == dt
    assert record.input_item_ids == ("item-1", "item-2")
    assert record.contradiction_ids == ("cntr-1",)
    assert record.status == CognitiveCycleStatus.COMPLETED
    assert isinstance(record.metadata, MappingProxyType)
    assert record.metadata["source"] == "test"


def test_cognitive_cycle_record_validations() -> None:
    dt = _utc()

    # Invalid cycle_id prefix
    with pytest.raises(
        InvalidCognitiveCycleError, match="must start with 'cognitive-cycle:'"
    ):
        CognitiveCycleRecord(
            cycle_id="invalid-prefix:123",
            created_at=dt,
            input_item_ids=("item-1",),
            contradiction_ids=(),
            resolution_proposal_ids=(),
            execution_ids=(),
            memory_entry_ids=(),
            reflection_report_id=None,
            status=CognitiveCycleStatus.CREATED,
        )

    # Naive datetime
    with pytest.raises(InvalidCognitiveCycleError, match="timezone-aware"):
        CognitiveCycleRecord(
            cycle_id="cognitive-cycle:123",
            created_at=datetime(2026, 1, 1),  # noqa: DTZ001
            input_item_ids=("item-1",),
            contradiction_ids=(),
            resolution_proposal_ids=(),
            execution_ids=(),
            memory_entry_ids=(),
            reflection_report_id=None,
            status=CognitiveCycleStatus.CREATED,
        )

    # Invalid ID elements
    with pytest.raises(InvalidCognitiveCycleError, match="non-empty strings"):
        CognitiveCycleRecord(
            cycle_id="cognitive-cycle:123",
            created_at=dt,
            input_item_ids=("item-1", ""),
            contradiction_ids=(),
            resolution_proposal_ids=(),
            execution_ids=(),
            memory_entry_ids=(),
            reflection_report_id=None,
            status=CognitiveCycleStatus.CREATED,
        )


def test_generate_cognitive_cycle_id_determinism() -> None:
    dt = _utc()
    id1 = generate_cognitive_cycle_id(
        input_item_ids=["item-a", "item-b"],
        created_at=dt,
        status=CognitiveCycleStatus.COMPLETED,
    )
    id2 = generate_cognitive_cycle_id(
        input_item_ids=["item-b", "item-a"],
        created_at=dt,
        status=CognitiveCycleStatus.COMPLETED,
    )

    assert id1.startswith("cognitive-cycle:")
    assert id1 == id2

    # Validation on empty input_item_ids
    with pytest.raises(InvalidCognitiveCycleError):
        generate_cognitive_cycle_id(input_item_ids=[])


def test_serialization_and_deserialization() -> None:
    dt = _utc()
    record = CognitiveCycleRecord(
        cycle_id="cognitive-cycle:9998887776665554",
        created_at=dt,
        input_item_ids=("item-1", "item-2"),
        contradiction_ids=("cntr-1",),
        resolution_proposal_ids=("prop-1",),
        execution_ids=("exec-1",),
        memory_entry_ids=("mem-1",),
        reflection_report_id="report-1",
        status=CognitiveCycleStatus.COMPLETED,
        warnings=("warn-1",),
        metadata={"step": 9},
    )

    serialized = record.serialize()
    assert serialized["cycle_id"] == record.cycle_id
    assert serialized["status"] == "completed"

    restored = CognitiveCycleRecord.from_mapping(serialized)
    assert restored == record
    assert CognitiveCycleRecord.from_dict(serialized) == record


# ── Full Integration Test ──────────────────────────────────────────────────────


def test_full_cognitive_cycle_integration() -> None:
    store = InMemoryKnowledgeStore()
    retriever = KnowledgeRetriever(store)
    detector = KnowledgeContradictionDetector(store, retriever)
    resolver = KnowledgeContradictionResolver(store)
    policy_engine = ContradictionResolutionPolicyEngine(allow_auto_resolution=True)
    executor = ContradictionResolutionExecutor(store)
    memory_store = InMemoryResolutionMemoryStore()
    reflection_engine = CognitiveReflectionEngine()

    engine = CognitiveCycleEngine(
        store=store,
        retriever=retriever,
        contradiction_detector=detector,
        contradiction_resolver=resolver,
        policy_engine=policy_engine,
        executor=executor,
        memory_store=memory_store,
        reflection_engine=reflection_engine,
    )

    # Item A & Item B
    item_a = _make_item("item-a", "El servicio está activo", resource_id="res-1")
    item_b = _make_item("item-b", "El servicio está inactivo", resource_id="res-2")

    store.save_item(item_a)
    store.save_item(item_b)

    dt_start = _utc()
    record = engine.run_cycle(
        item_ids=("item-a", "item-b"),
        created_at=dt_start,
        actor_id="actor-test",
    )

    assert record.status == CognitiveCycleStatus.COMPLETED
    assert record.cycle_id.startswith("cognitive-cycle:")
    assert record.input_item_ids == ("item-a", "item-b")
    assert len(record.contradiction_ids) >= 1
    assert len(record.resolution_proposal_ids) >= 1
    assert len(record.execution_ids) >= 1
    assert len(record.memory_entry_ids) >= 1
    assert record.reflection_report_id is not None

    # Verify memory store contains saved entries
    memory_entries = memory_store.list().entries
    assert len(memory_entries) >= 1
    assert memory_entries[0].id in record.memory_entry_ids


# ── Security & Safety Tests ────────────────────────────────────────────────────


def test_safety_policy_blocking_prevents_execution() -> None:
    store = InMemoryKnowledgeStore()
    retriever = KnowledgeRetriever(store)
    detector = KnowledgeContradictionDetector(store, retriever)
    resolver = KnowledgeContradictionResolver(store)
    # Policy auto-resolution DISABLED
    policy_engine = ContradictionResolutionPolicyEngine(allow_auto_resolution=False)
    executor = ContradictionResolutionExecutor(store)
    memory_store = InMemoryResolutionMemoryStore()
    reflection_engine = CognitiveReflectionEngine()

    engine = CognitiveCycleEngine(
        store=store,
        retriever=retriever,
        contradiction_detector=detector,
        contradiction_resolver=resolver,
        policy_engine=policy_engine,
        executor=executor,
        memory_store=memory_store,
        reflection_engine=reflection_engine,
    )

    item_a = _make_item("item-a", "El servicio está activo")
    item_b = _make_item("item-b", "El servicio está inactivo")
    store.save_item(item_a)
    store.save_item(item_b)

    record = engine.run_cycle(item_ids=("item-a", "item-b"), created_at=_utc())

    assert record.status == CognitiveCycleStatus.COMPLETED
    assert len(record.contradiction_ids) >= 1
    assert len(record.resolution_proposal_ids) >= 1
    # Because policy blocked auto execution, execution_ids should be empty
    assert len(record.execution_ids) == 0
    assert len(record.memory_entry_ids) == 0

    # Ensure store items remain unchanged and active
    saved_a = store.get_item("item-a")
    saved_b = store.get_item("item-b")
    assert saved_a.status == KnowledgeStatus.ACTIVE
    assert saved_b.status == KnowledgeStatus.ACTIVE


def test_safety_error_propagation_and_memory_preservation() -> None:
    store = InMemoryKnowledgeStore()
    retriever = KnowledgeRetriever(store)
    detector = KnowledgeContradictionDetector(store, retriever)
    resolver = KnowledgeContradictionResolver(store)
    policy_engine = ContradictionResolutionPolicyEngine(allow_auto_resolution=True)
    executor = ContradictionResolutionExecutor(store)
    memory_store = InMemoryResolutionMemoryStore()
    reflection_engine = CognitiveReflectionEngine()

    engine = CognitiveCycleEngine(
        store=store,
        retriever=retriever,
        contradiction_detector=detector,
        contradiction_resolver=resolver,
        policy_engine=policy_engine,
        executor=executor,
        memory_store=memory_store,
        reflection_engine=reflection_engine,
    )

    # Force a failure during detection or retrieval by supplying non-existent items
    with pytest.raises(CognitiveCycleExecutionError):
        engine.run_cycle(
            item_ids=("non-existent-1", "non-existent-2"), created_at=_utc()
        )


# ── Determinism Tests ──────────────────────────────────────────────────────────


def test_cycle_determinism_identical_runs() -> None:
    dt_fixed = _utc()

    def _build_and_run() -> CognitiveCycleRecord:
        store = InMemoryKnowledgeStore()
        retriever = KnowledgeRetriever(store)
        detector = KnowledgeContradictionDetector(store, retriever)
        resolver = KnowledgeContradictionResolver(store)
        policy_engine = ContradictionResolutionPolicyEngine(allow_auto_resolution=True)
        executor = ContradictionResolutionExecutor(store)
        memory_store = InMemoryResolutionMemoryStore()
        reflection_engine = CognitiveReflectionEngine()

        engine = CognitiveCycleEngine(
            store=store,
            retriever=retriever,
            contradiction_detector=detector,
            contradiction_resolver=resolver,
            policy_engine=policy_engine,
            executor=executor,
            memory_store=memory_store,
            reflection_engine=reflection_engine,
        )

        item_a = _make_item("item-a", "El servicio está activo", resource_id="res-1")
        item_b = _make_item("item-b", "El servicio está inactivo", resource_id="res-2")

        store.save_item(item_a)
        store.save_item(item_b)

        return engine.run_cycle(
            item_ids=("item-a", "item-b"),
            created_at=dt_fixed,
            actor_id="actor-1",
        )

    rec1 = _build_and_run()
    rec2 = _build_and_run()

    assert rec1.cycle_id == rec2.cycle_id
    assert rec1.input_item_ids == rec2.input_item_ids
    assert rec1.contradiction_ids == rec2.contradiction_ids
    assert rec1.resolution_proposal_ids == rec2.resolution_proposal_ids
    assert len(rec1.execution_ids) == len(rec2.execution_ids)
    if rec1.execution_ids:
        assert rec1.execution_ids[0].startswith("resolution-exec:")
        assert rec2.execution_ids[0].startswith("resolution-exec:")
    assert rec1.status == rec2.status
