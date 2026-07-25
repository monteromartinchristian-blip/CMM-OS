"""Phase 8.13 – Resolution Memory & Cognitive Decision History Tests.

Validates resolution memory contracts, query engines, in-memory store implementation,
deterministic ID generation, cognitive safety invariants, and full pipeline integration.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.cognitive.contracts import Confidence, utc_now
from cmm.cognitive.contradiction_detection import KnowledgeContradictionDetector
from cmm.cognitive.contradiction_resolution import (
    KnowledgeContradictionResolver,
)
from cmm.cognitive.enums import (
    ContradictionSeverity,
    ContradictionStatus,
    KnowledgeKind,
    KnowledgeStatus,
)
from cmm.cognitive.errors import (
    InvalidResolutionMemoryEntryError,
    ResolutionMemoryConflictError,
)
from cmm.cognitive.knowledge import Contradiction, KnowledgeItem
from cmm.cognitive.resolution_contracts import (
    ResolutionDecision,
)
from cmm.cognitive.resolution_executor import (
    ContradictionResolutionExecutor,
)
from cmm.cognitive.resolution_executor_contracts import (
    ExecutionStatus,
)
from cmm.cognitive.resolution_memory import (
    InMemoryResolutionMemoryStore,
    memory_from_execution_result,
)
from cmm.cognitive.resolution_memory_contracts import (
    ResolutionMemoryEntry,
    ResolutionMemoryQuery,
    generate_resolution_memory_id,
)
from cmm.cognitive.resolution_policy import (
    ContradictionResolutionPolicyEngine,
)
from cmm.cognitive.resolution_policy_contracts import (
    PolicyDecision,
)
from cmm.cognitive.store_memory import InMemoryKnowledgeStore


def _make_valid_entry(
    entry_id: str = "res-mem-001",
    contradiction_id: str = "con-001",
    item_a_id: str = "item-a",
    item_b_id: str = "item-b",
    proposal_id: str | None = "prop-001",
    decision: ResolutionDecision = ResolutionDecision.PREFER_ITEM_A,
    policy_decision: PolicyDecision = PolicyDecision.AUTO_APPROVED,
    execution_status: ExecutionStatus = ExecutionStatus.COMPLETED,
    confidence: float = 0.85,
    actor_id: str | None = "actor-system",
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> ResolutionMemoryEntry:
    now = utc_now()
    return ResolutionMemoryEntry(
        id=entry_id,
        contradiction_id=contradiction_id,
        item_a_id=item_a_id,
        item_b_id=item_b_id,
        proposal_id=proposal_id,
        decision=decision,
        policy_decision=policy_decision,
        execution_status=execution_status,
        confidence=confidence,
        actor_id=actor_id,
        created_at=created_at or now,
        updated_at=updated_at or now,
        rationale=("Higher confidence item preferred",),
        evidence_ids=("ev-01",),
        metadata={"source": "test"},
    )


# ── Contract Validation Tests ──────────────────────────────────────────────────


class TestResolutionMemoryContracts:
    """Test resolution memory dataclasses, immutability, and validation."""

    def test_valid_entry_instantiation(self) -> None:
        entry = _make_valid_entry()
        assert entry.id == "res-mem-001"
        assert entry.contradiction_id == "con-001"
        assert entry.item_a_id == "item-a"
        assert entry.item_b_id == "item-b"
        assert entry.proposal_id == "prop-001"
        assert entry.decision == ResolutionDecision.PREFER_ITEM_A
        assert entry.policy_decision == PolicyDecision.AUTO_APPROVED
        assert entry.execution_status == ExecutionStatus.COMPLETED
        assert entry.confidence == 0.85
        assert entry.actor_id == "actor-system"
        assert entry.rationale == ("Higher confidence item preferred",)
        assert entry.evidence_ids == ("ev-01",)

    @pytest.mark.parametrize(
        ("field_name", "invalid_value"),
        [
            ("id", ""),
            ("id", "   "),
            ("contradiction_id", ""),
            ("contradiction_id", "   "),
            ("item_a_id", ""),
            ("item_a_id", "   "),
            ("item_b_id", ""),
            ("item_b_id", "   "),
        ],
    )
    def test_empty_string_ids_rejected(
        self, field_name: str, invalid_value: str
    ) -> None:
        kwargs = {
            "id": "mem-1",
            "contradiction_id": "c-1",
            "item_a_id": "a-1",
            "item_b_id": "b-1",
            "proposal_id": "p-1",
            "decision": ResolutionDecision.PREFER_ITEM_A,
            "policy_decision": PolicyDecision.AUTO_APPROVED,
            "execution_status": ExecutionStatus.COMPLETED,
            "confidence": 0.5,
            "actor_id": None,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        kwargs[field_name] = invalid_value
        with pytest.raises(InvalidResolutionMemoryEntryError):
            ResolutionMemoryEntry(**kwargs)

    @pytest.mark.parametrize("invalid_conf", [-0.1, 1.1, "high", True])
    def test_invalid_confidence_rejected(self, invalid_conf: object) -> None:
        with pytest.raises(InvalidResolutionMemoryEntryError):
            _make_valid_entry(confidence=invalid_conf)  # type: ignore[arg-type]

    def test_naive_datetime_rejected(self) -> None:
        naive_dt = datetime.now()  # noqa: DTZ005
        with pytest.raises(InvalidResolutionMemoryEntryError):
            _make_valid_entry(created_at=naive_dt)

        with pytest.raises(InvalidResolutionMemoryEntryError):
            _make_valid_entry(updated_at=naive_dt)

    def test_metadata_immutability(self) -> None:
        entry = _make_valid_entry()
        with pytest.raises(TypeError):
            entry.metadata["new_key"] = "forbidden"  # type: ignore[index]

    def test_roundtrip_serialization(self) -> None:
        original = _make_valid_entry()
        serialized = original.serialize()

        assert serialized["id"] == original.id
        assert serialized["decision"] == "prefer_item_a"
        assert serialized["policy_decision"] == "auto_approved"
        assert serialized["execution_status"] == "completed"

        deserialized = ResolutionMemoryEntry.from_mapping(serialized)
        assert deserialized == original
        assert deserialized.to_dict() == original.to_dict()


# ── Deterministic ID Tests ─────────────────────────────────────────────────────


class TestDeterministicIdGeneration:
    """Test resolution memory ID generation determinism."""

    def test_same_input_same_id(self) -> None:
        now = utc_now()
        id1 = generate_resolution_memory_id(
            contradiction_id="con-123",
            proposal_id="prop-456",
            decision=ResolutionDecision.PREFER_ITEM_A,
            execution_status=ExecutionStatus.COMPLETED,
            created_at=now,
        )
        id2 = generate_resolution_memory_id(
            contradiction_id="con-123",
            proposal_id="prop-456",
            decision=ResolutionDecision.PREFER_ITEM_A,
            execution_status=ExecutionStatus.COMPLETED,
            created_at=now,
        )
        assert id1 == id2
        assert id1.startswith("resolution-memory:")

    def test_different_inputs_different_ids(self) -> None:
        id_a = generate_resolution_memory_id(
            contradiction_id="con-123",
            proposal_id="prop-456",
            decision=ResolutionDecision.PREFER_ITEM_A,
            execution_status=ExecutionStatus.COMPLETED,
        )
        id_b = generate_resolution_memory_id(
            contradiction_id="con-123",
            proposal_id="prop-456",
            decision=ResolutionDecision.PREFER_ITEM_B,  # different decision
            execution_status=ExecutionStatus.COMPLETED,
        )
        assert id_a != id_b

    def test_invalid_id_args_raise(self) -> None:
        with pytest.raises(InvalidResolutionMemoryEntryError):
            generate_resolution_memory_id("", "prop", "prefer_item_a", "completed")


# ── Store Operations Tests ─────────────────────────────────────────────────────


class TestInMemoryResolutionMemoryStore:
    """Test InMemoryResolutionMemoryStore CRUD operations."""

    def test_save_get_contains_delete(self) -> None:
        store = InMemoryResolutionMemoryStore()
        entry = _make_valid_entry(entry_id="mem-100")

        assert not store.contains("mem-100")
        assert store.count() == 0

        saved = store.save(entry)
        assert saved == entry
        assert store.contains("mem-100")
        assert store.count() == 1

        retrieved = store.get("mem-100")
        assert retrieved == entry

        store.delete("mem-100")
        assert not store.contains("mem-100")
        assert store.count() == 0

    def test_get_nonexistent_raises(self) -> None:
        store = InMemoryResolutionMemoryStore()
        with pytest.raises(ResolutionMemoryConflictError):
            store.get("nonexistent-id")

    def test_save_duplicate_same_content_ok(self) -> None:
        store = InMemoryResolutionMemoryStore()
        entry = _make_valid_entry("mem-dup")
        store.save(entry)
        # Re-saving identical entry succeeds
        res = store.save(entry)
        assert res == entry

    def test_save_duplicate_conflicting_content_raises(self) -> None:
        store = InMemoryResolutionMemoryStore()
        entry1 = _make_valid_entry("mem-conflict", confidence=0.8)
        entry2 = _make_valid_entry(
            "mem-conflict", confidence=0.9
        )  # differing confidence
        store.save(entry1)

        with pytest.raises(ResolutionMemoryConflictError):
            store.save(entry2)


# ── Query Filtering Tests ──────────────────────────────────────────────────────


class TestResolutionMemoryQueries:
    """Test query engine filters over stored resolution memory entries."""

    @pytest.fixture
    def populated_store(self) -> InMemoryResolutionMemoryStore:
        store = InMemoryResolutionMemoryStore()
        base_time = datetime(2026, 7, 25, 10, 0, 0, tzinfo=timezone.utc)

        # Entry 1: Item A vs B, PREFER_ITEM_A, Completed, High confidence
        store.save(
            _make_valid_entry(
                entry_id="m-1",
                contradiction_id="c-1",
                item_a_id="item-1",
                item_b_id="item-2",
                decision=ResolutionDecision.PREFER_ITEM_A,
                execution_status=ExecutionStatus.COMPLETED,
                confidence=0.9,
                actor_id="admin",
                created_at=base_time,
            )
        )
        # Entry 2: Item B vs C, KEEP_BOTH, Completed, Medium confidence
        store.save(
            _make_valid_entry(
                entry_id="m-2",
                contradiction_id="c-2",
                item_a_id="item-2",
                item_b_id="item-3",
                decision=ResolutionDecision.KEEP_BOTH,
                execution_status=ExecutionStatus.COMPLETED,
                confidence=0.7,
                actor_id="system",
                created_at=datetime(2026, 7, 25, 11, 0, 0, tzinfo=timezone.utc),
            )
        )
        # Entry 3: Item A vs C, PREFER_ITEM_B, Failed, Low confidence
        store.save(
            _make_valid_entry(
                entry_id="m-3",
                contradiction_id="c-1",
                item_a_id="item-1",
                item_b_id="item-3",
                decision=ResolutionDecision.PREFER_ITEM_B,
                execution_status=ExecutionStatus.FAILED,
                confidence=0.4,
                actor_id="admin",
                created_at=datetime(2026, 7, 25, 12, 0, 0, tzinfo=timezone.utc),
            )
        )
        return store

    def test_filter_by_contradiction_id(
        self, populated_store: InMemoryResolutionMemoryStore
    ) -> None:
        query = ResolutionMemoryQuery(contradiction_id="c-1")
        res = populated_store.list(query)
        assert res.total_count == 2
        assert {e.id for e in res.entries} == {"m-1", "m-3"}

    def test_filter_by_item_id(
        self, populated_store: InMemoryResolutionMemoryStore
    ) -> None:
        query = ResolutionMemoryQuery(item_id="item-2")
        res = populated_store.list(query)
        assert res.total_count == 2
        assert {e.id for e in res.entries} == {"m-1", "m-2"}

    def test_filter_by_decision(
        self, populated_store: InMemoryResolutionMemoryStore
    ) -> None:
        query = ResolutionMemoryQuery(decision=ResolutionDecision.KEEP_BOTH)
        res = populated_store.list(query)
        assert res.total_count == 1
        assert res.entries[0].id == "m-2"

    def test_filter_by_execution_status(
        self, populated_store: InMemoryResolutionMemoryStore
    ) -> None:
        query = ResolutionMemoryQuery(execution_status=ExecutionStatus.FAILED)
        res = populated_store.list(query)
        assert res.total_count == 1
        assert res.entries[0].id == "m-3"

    def test_filter_by_minimum_confidence(
        self, populated_store: InMemoryResolutionMemoryStore
    ) -> None:
        query = ResolutionMemoryQuery(minimum_confidence=0.8)
        res = populated_store.list(query)
        assert res.total_count == 1
        assert res.entries[0].id == "m-1"

    def test_filter_by_date_range(
        self, populated_store: InMemoryResolutionMemoryStore
    ) -> None:
        after = datetime(2026, 7, 25, 10, 30, 0, tzinfo=timezone.utc)
        before = datetime(2026, 7, 25, 11, 30, 0, tzinfo=timezone.utc)
        query = ResolutionMemoryQuery(created_after=after, created_before=before)
        res = populated_store.list(query)
        assert res.total_count == 1
        assert res.entries[0].id == "m-2"

    def test_query_pagination(
        self, populated_store: InMemoryResolutionMemoryStore
    ) -> None:
        query = ResolutionMemoryQuery(limit=1, offset=1)
        res = populated_store.list(query)
        assert res.total_count == 3  # total matching before limit
        assert len(res.entries) == 1
        assert res.entries[0].id == "m-2"


# ── Cognitive Safety & Evolution Tests ──────────────────────────────────────────


class TestCognitiveSafetyAndEvolution:
    """Verify memory observability guarantees (does not alter knowledge or past history)."""

    def test_historical_coexistence_does_not_overwrite(
        self,
    ) -> None:
        store = InMemoryResolutionMemoryStore()
        c_id = "con-evolution-001"
        t1 = datetime(2026, 7, 25, 8, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 7, 25, 9, 0, 0, tzinfo=timezone.utc)

        entry_v1 = _make_valid_entry(
            entry_id="mem-v1",
            contradiction_id=c_id,
            decision=ResolutionDecision.PREFER_ITEM_A,
            confidence=0.75,
            created_at=t1,
        )
        entry_v2 = _make_valid_entry(
            entry_id="mem-v2",
            contradiction_id=c_id,
            decision=ResolutionDecision.KEEP_BOTH,
            confidence=0.95,
            created_at=t2,
        )

        store.save(entry_v1)
        store.save(entry_v2)

        history = store.list(ResolutionMemoryQuery(contradiction_id=c_id))
        assert history.total_count == 2
        assert history.entries[0].decision == ResolutionDecision.PREFER_ITEM_A
        assert history.entries[1].decision == ResolutionDecision.KEEP_BOTH
        # Evolution coexists; neither destroyed
        assert store.get("mem-v1").confidence == 0.75

    def test_memory_does_not_mutate_knowledge_items(self) -> None:
        kstore = InMemoryKnowledgeStore()
        item = KnowledgeItem(
            id="item-orig",
            kind=KnowledgeKind.FACT,
            statement="Original statement",
            status=KnowledgeStatus.ACTIVE,
            confidence=Confidence(value=0.9, source="test"),
        )
        kstore.save_item(item)

        mem_store = InMemoryResolutionMemoryStore()
        entry = _make_valid_entry(item_a_id="item-orig")
        mem_store.save(entry)

        # Knowledge item in store remains completely unchanged
        stored_item = kstore.get_item("item-orig")
        assert stored_item.statement == "Original statement"
        assert stored_item.status == KnowledgeStatus.ACTIVE


# ── Integration Pipeline Tests ─────────────────────────────────────────────────


class TestFullPipelineIntegration:
    """Test full cognitive resolution flow from Contradiction -> Proposal -> Policy -> Execution -> Memory."""

    def test_full_pipeline_to_memory(self) -> None:
        # 1. Setup KnowledgeStore with contradictory items
        kstore = InMemoryKnowledgeStore()
        item_a = KnowledgeItem(
            id="item-a-1",
            kind=KnowledgeKind.FACT,
            statement="Server port is 8080",
            status=KnowledgeStatus.ACTIVE,
            confidence=Confidence(value=0.9, source="test"),
            resource_id="res-a",
        )
        item_b = KnowledgeItem(
            id="item-b-2",
            kind=KnowledgeKind.FACT,
            statement="Server port is 9090",
            status=KnowledgeStatus.ACTIVE,
            confidence=Confidence(value=0.6, source="test"),
            resource_id="res-b",
        )
        kstore.save_item(item_a)
        kstore.save_item(item_b)

        contradiction = Contradiction(
            id="contradiction-100",
            item_a_id="item-a-1",
            item_b_id="item-b-2",
            severity=ContradictionSeverity.MEDIUM,
            status=ContradictionStatus.UNRESOLVED,
            explanation="Conflicting server port configuration",
        )
        kstore.save_contradiction(contradiction)

        # 2. Contradiction Detection Signal
        detector = KnowledgeContradictionDetector(kstore)
        det_result = detector.compare(item_a, item_b)
        assert det_result.item_a_id == "item-a-1"

        # 3. Resolution Proposal Generation
        resolver = KnowledgeContradictionResolver(kstore)
        proposals = resolver.propose_resolutions(contradiction, item_a, item_b)
        proposal = next(
            p for p in proposals if p.decision == ResolutionDecision.KEEP_BOTH
        )
        assert proposal.contradiction_id == "contradiction-100"

        # 4. Policy Evaluation
        policy_engine = ContradictionResolutionPolicyEngine(allow_auto_resolution=True)
        evaluation = policy_engine.evaluate(proposal)
        assert evaluation.allowed is True
        assert evaluation.decision == PolicyDecision.AUTO_APPROVED

        # 5. Execution
        executor = ContradictionResolutionExecutor(kstore)
        exec_result = executor.execute(proposal, evaluation)
        assert exec_result.status == ExecutionStatus.COMPLETED

        # 6. Memory Recording
        mem_entry = memory_from_execution_result(
            execution_result=exec_result,
            proposal=proposal,
            policy_evaluation=evaluation,
        )
        assert mem_entry.contradiction_id == "contradiction-100"
        assert mem_entry.proposal_id == proposal.id
        assert mem_entry.decision == ResolutionDecision.KEEP_BOTH
        assert mem_entry.policy_decision == PolicyDecision.AUTO_APPROVED
        assert mem_entry.execution_status == ExecutionStatus.COMPLETED

        mem_store = InMemoryResolutionMemoryStore()
        saved_entry = mem_store.save(mem_entry)

        # 7. Traceability verification
        retrieved_entry = mem_store.get(saved_entry.id)
        assert retrieved_entry.id == saved_entry.id
        assert retrieved_entry.contradiction_id == "contradiction-100"
        assert retrieved_entry.item_a_id == "item-a-1"
        assert retrieved_entry.item_b_id == "item-b-2"
        assert retrieved_entry.confidence == proposal.confidence
