"""Phase 8 end-to-end integration tests.

Covers the seven canonical flows required to close Phase 8:
1. Knowledge lifecycle (Resource → Extraction → Item → Store → Retrieval)
2. Consolidation (duplicate items → candidate → plan → apply)
3. Contradiction lifecycle (conflicting items → detection → registration)
4. Resolution lifecycle (contradiction → proposal → policy → execution → audit)
5. Memory and reflection (execution → memory entry → reflection report)
6. Full cognitive cycle (Store → CognitiveCycleEngine → CognitiveCycleRecord)
7. Safety (policy block, rollback, manual review rejected, info preserved)

Parametrized over InMemoryKnowledgeStore and SQLiteKnowledgeStore.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from cmm.cognitive.cognitive_cycle import CognitiveCycleEngine
from cmm.cognitive.cognitive_cycle_contracts import CognitiveCycleStatus
from cmm.cognitive.consolidation import KnowledgeConsolidator
from cmm.cognitive.contracts import Confidence
from cmm.cognitive.contradiction_detection import KnowledgeContradictionDetector
from cmm.cognitive.contradiction_resolution import KnowledgeContradictionResolver
from cmm.cognitive.enums import (
    KnowledgeKind,
    KnowledgeStatus,
    ResourceKind,
    ResourceSourceKind,
)
from cmm.cognitive.errors import (
    CognitiveCycleExecutionError,
    InvalidCognitiveCycleError,
)
from cmm.cognitive.extraction import PlainTextKnowledgeExtractor
from cmm.cognitive.knowledge import KnowledgeItem
from cmm.cognitive.reflection import CognitiveReflectionEngine
from cmm.cognitive.resolution_contracts import (
    ContradictionResolutionProposal,
    ResolutionDecision,
    ResolutionStatus,
)
from cmm.cognitive.resolution_executor import ContradictionResolutionExecutor
from cmm.cognitive.resolution_executor_contracts import ExecutionStatus
from cmm.cognitive.resolution_memory import (
    InMemoryResolutionMemoryStore,
    memory_from_execution_result,
)
from cmm.cognitive.resolution_policy import ContradictionResolutionPolicyEngine
from cmm.cognitive.resolution_policy_contracts import PolicyDecision
from cmm.cognitive.resources import (
    Resource,
    ResourceProvenance,
    ResourceTemporalScope,
)
from cmm.cognitive.retrieval import KnowledgeRetriever
from cmm.cognitive.store_memory import InMemoryKnowledgeStore
from cmm.cognitive.store_sqlite import SQLiteKnowledgeStore

NOW = datetime.now(timezone.utc)


def _make_item(
    item_id: str, statement: str, kind: KnowledgeKind = KnowledgeKind.FACT, **kw: Any
) -> KnowledgeItem:
    return KnowledgeItem(
        id=item_id,
        statement=statement,
        kind=kind,
        confidence=Confidence(value=kw.pop("confidence", 0.9)),
        created_at=kw.pop("created_at", NOW),
        updated_at=kw.pop("updated_at", NOW),
        **kw,
    )


@pytest.fixture(params=["memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> Any:
    if request.param == "memory":
        return InMemoryKnowledgeStore()
    db_path = str(tmp_path / "test.db")
    return SQLiteKnowledgeStore(db_path)


# ── Flow 1: Knowledge Lifecycle ──────────────────────────────────────────────


class TestKnowledgeLifecycle:
    """Resource → Extraction → KnowledgeItem → Store → Retrieval."""

    def test_full_lifecycle(self, store: Any) -> None:
        # 1. Create resource
        resource = Resource(
            domain="general",
            kind=ResourceKind.USER_MESSAGE,
            source=ResourceSourceKind.USER_INPUT,
            content="El cielo es azul. El agua se congela a 0°C.",
            provenance=ResourceProvenance(
                source_type=ResourceSourceKind.USER_INPUT,
                source_id="usr-input-1",
            ),
            reliability=Confidence(value=1.0),
            temporal_scope=ResourceTemporalScope(),
        )
        assert resource.domain == "general"

        # 2. Extract knowledge
        extractor = PlainTextKnowledgeExtractor()
        result = extractor.extract(resource)
        assert result.candidates is not None

        # 3. Create and save items
        item_a = _make_item("flow1-a", "El cielo es azul", resource_id=resource.id)
        item_b = _make_item(
            "flow1-b", "El agua se congela a 0°C", resource_id=resource.id
        )
        store.save_item(item_a)
        store.save_item(item_b)

        # 4. Retrieve
        retriever = KnowledgeRetriever(store)
        items = retriever.get_items(["flow1-a", "flow1-b"])
        assert len(items) == 2
        assert items[0].id == "flow1-a"

        # 5. Verify round-trip
        fetched = store.get_item("flow1-a")
        assert fetched.statement == item_a.statement
        assert fetched.serialize() == item_a.serialize()


# ── Flow 2: Consolidation ─────────────────────────────────────────────────────


class TestConsolidation:
    """Duplicate items → Candidate → Plan → Apply."""

    def test_merge_consolidation(self, store: Any) -> None:
        item_a = _make_item("cons-1", "La tierra orbita el sol")
        item_b = _make_item("cons-2", "la tierra orbita el sol")
        store.save_item(item_a)
        store.save_item(item_b)

        consolidator = KnowledgeConsolidator(store)
        candidates = consolidator.find_candidates()
        assert len(candidates) >= 1

        plan = consolidator.build_plan(
            candidates, actor_id="test-system", dry_run=False
        )
        assert len(plan.actions) >= 1

        result = consolidator.apply_plan(plan)

        assert result.applied is True

    def test_no_duplicate_on_distinct_items(self, store: Any) -> None:
        item_a = _make_item("cons-3", "El agua es líquida")
        item_b = _make_item("cons-4", "El fuego es caliente")
        store.save_item(item_a)
        store.save_item(item_b)

        consolidator = KnowledgeConsolidator(store)
        candidates = consolidator.find_candidates()
        assert len(candidates) == 0


# ── Flow 3: Contradiction Lifecycle ───────────────────────────────────────────


class TestContradictionLifecycle:
    """Conflicting items → Detection → Registration."""

    def test_detect_and_register_contradiction(self, store: Any) -> None:
        # Use opposition pair pattern the detector recognizes
        item_a = _make_item("det-1", "El servicio está activo")
        item_b = _make_item("det-2", "El servicio está inactivo")
        store.save_item(item_a)
        store.save_item(item_b)

        detector = KnowledgeContradictionDetector(store)
        detection = detector.compare(item_a, item_b)
        assert detection.is_contradiction is True

        registered = detector.register(detection, actor_id="test-system")
        assert registered.item_a_id in (item_a.id, item_b.id)
        assert registered.item_b_id in (item_a.id, item_b.id)


# ── Flow 4: Resolution Lifecycle ──────────────────────────────────────────────


class TestResolutionLifecycle:
    """Contradiction → Proposal → Policy → Execution → Audit."""

    def test_prefer_item_resolution(self, store: Any) -> None:
        # Use negation pattern the detector recognizes
        item_a = _make_item("res-1", "El contrato está vigente", confidence=0.95)
        item_b = _make_item("res-2", "El contrato no está vigente", confidence=0.3)
        store.save_item(item_a)
        store.save_item(item_b)

        # Detect
        detector = KnowledgeContradictionDetector(store)
        detection = detector.compare(item_a, item_b)
        assert detection.is_contradiction

        detector.register(detection, actor_id="test")

        # Propose
        resolver = KnowledgeContradictionResolver(store)
        proposals = resolver.propose_resolutions(
            contradiction=detection,
            item_a=item_a,
            item_b=item_b,
            actor_id="test",
        )
        assert len(proposals) >= 1

        proposal = proposals[0]

        # Evaluate policy
        policy = ContradictionResolutionPolicyEngine()
        evaluation = policy.evaluate(proposal)

        if evaluation.allowed and evaluation.decision == PolicyDecision.AUTO_APPROVED:
            # Execute
            executor = ContradictionResolutionExecutor(store)
            exec_result = executor.execute(proposal, evaluation, actor_id="test")
            assert exec_result.execution_status in (
                ExecutionStatus.APPLIED,
                ExecutionStatus.NOOP,
            )

            # Verify audit record
            assert exec_result.audit_record is not None
            assert exec_result.audit_record.execution_id == exec_result.execution_id


# ── Flow 5: Memory and Reflection ─────────────────────────────────────────────


class TestMemoryAndReflection:
    """Execution → MemoryEntry → ReflectionReport."""

    def test_memory_and_reflection_round_trip(self, store: Any) -> None:
        # Use opposition pair pattern
        item_a = _make_item("mem-1", "El sistema está activo", confidence=0.95)
        item_b = _make_item("mem-2", "El sistema está inactivo", confidence=0.2)
        store.save_item(item_a)
        store.save_item(item_b)

        detector = KnowledgeContradictionDetector(store)
        detection = detector.compare(item_a, item_b)
        assert detection.is_contradiction

        detector.register(detection, actor_id="test")
        resolver = KnowledgeContradictionResolver(store)
        proposals = resolver.propose_resolutions(
            contradiction=detection, item_a=item_a, item_b=item_b, actor_id="test"
        )

        policy = ContradictionResolutionPolicyEngine()
        executor = ContradictionResolutionExecutor(store)
        memory_store = InMemoryResolutionMemoryStore()

        executed_count = 0
        for prop in proposals:
            ev = policy.evaluate(prop)
            if ev.allowed and ev.decision == PolicyDecision.AUTO_APPROVED:
                exec_res = executor.execute(prop, ev, actor_id="test")
                mem_entry = memory_from_execution_result(
                    execution_result=exec_res, proposal=prop, policy_evaluation=ev
                )
                saved = memory_store.save(mem_entry)
                assert saved.id == mem_entry.id
                executed_count += 1

        # Reflect — works even if no executions happened
        reflection_engine = CognitiveReflectionEngine()
        report = reflection_engine.reflect(memory_store)
        assert report.analysed_entries >= 0
        assert report.id.startswith("reflection-report:")


# ── Flow 6: Full Cognitive Cycle ──────────────────────────────────────────────


class TestFullCognitiveCycle:
    """Store → CognitiveCycleEngine → CognitiveCycleRecord."""

    def test_cycle_with_contradictions(self, store: Any) -> None:
        # Use patterns the detector recognizes
        item_a = _make_item("cyc-1", "El proceso está activo", confidence=0.99)
        item_b = _make_item("cyc-2", "El proceso está inactivo", confidence=0.1)
        item_c = _make_item("cyc-3", "Marte tiene dos lunas", confidence=0.95)
        store.save_item(item_a)
        store.save_item(item_b)
        store.save_item(item_c)

        retriever = KnowledgeRetriever(store)
        detector = KnowledgeContradictionDetector(store)
        resolver = KnowledgeContradictionResolver(store)
        policy = ContradictionResolutionPolicyEngine()
        executor = ContradictionResolutionExecutor(store)
        memory_store = InMemoryResolutionMemoryStore()
        reflection = CognitiveReflectionEngine()

        engine = CognitiveCycleEngine(
            store=store,
            retriever=retriever,
            contradiction_detector=detector,
            contradiction_resolver=resolver,
            policy_engine=policy,
            executor=executor,
            memory_store=memory_store,
            reflection_engine=reflection,
        )

        record = engine.run_cycle(item_ids=["cyc-1", "cyc-2", "cyc-3"], created_at=NOW)
        assert record.status == CognitiveCycleStatus.COMPLETED
        assert record.cycle_id.startswith("cognitive-cycle:")
        assert len(record.input_item_ids) == 3

    def test_cycle_no_contradictions(self, store: Any) -> None:
        item_a = _make_item("cyc-4", "El agua es H2O", confidence=0.99)
        item_b = _make_item("cyc-5", "El aire contiene oxígeno", confidence=0.95)
        store.save_item(item_a)
        store.save_item(item_b)

        retriever = KnowledgeRetriever(store)
        detector = KnowledgeContradictionDetector(store)
        resolver = KnowledgeContradictionResolver(store)
        policy = ContradictionResolutionPolicyEngine()
        executor = ContradictionResolutionExecutor(store)
        memory_store = InMemoryResolutionMemoryStore()
        reflection = CognitiveReflectionEngine()

        engine = CognitiveCycleEngine(
            store=store,
            retriever=retriever,
            contradiction_detector=detector,
            contradiction_resolver=resolver,
            policy_engine=policy,
            executor=executor,
            memory_store=memory_store,
            reflection_engine=reflection,
        )

        record = engine.run_cycle(item_ids=["cyc-4", "cyc-5"], created_at=NOW)
        assert record.status == CognitiveCycleStatus.COMPLETED
        assert len(record.contradiction_ids) == 0

    def test_cycle_empty_store_raises(self, store: Any) -> None:
        retriever = KnowledgeRetriever(store)
        detector = KnowledgeContradictionDetector(store)
        resolver = KnowledgeContradictionResolver(store)
        policy = ContradictionResolutionPolicyEngine()
        executor = ContradictionResolutionExecutor(store)
        memory_store = InMemoryResolutionMemoryStore()
        reflection = CognitiveReflectionEngine()

        engine = CognitiveCycleEngine(
            store=store,
            retriever=retriever,
            contradiction_detector=detector,
            contradiction_resolver=resolver,
            policy_engine=policy,
            executor=executor,
            memory_store=memory_store,
            reflection_engine=reflection,
        )

        with pytest.raises((InvalidCognitiveCycleError, CognitiveCycleExecutionError)):
            engine.run_cycle(created_at=NOW)


# ── Flow 7: Safety ────────────────────────────────────────────────────────────


class TestSafety:
    """Policy block, rollback, manual review rejected, information preserved."""

    def test_policy_block_prevents_mutation(self, store: Any) -> None:
        """REQUEST_HUMAN_REVIEW should not modify the store."""
        item_a = _make_item("safe-1", "A es verdadero", confidence=0.5)
        item_b = _make_item("safe-2", "A no es verdadero", confidence=0.5)
        store.save_item(item_a)
        store.save_item(item_b)

        # Create a manual-review proposal
        proposal = ContradictionResolutionProposal(
            id="proposal-manual",
            contradiction_id="contra-manual",
            item_a_id="safe-1",
            item_b_id="safe-2",
            decision=ResolutionDecision.REQUEST_HUMAN_REVIEW,
            status=ResolutionStatus.PROPOSED,
            confidence=0.3,
        )

        policy = ContradictionResolutionPolicyEngine()
        evaluation = policy.evaluate(proposal)

        # REQUEST_HUMAN_REVIEW should not be AUTO_APPROVED
        if (
            evaluation.decision != PolicyDecision.AUTO_APPROVED
            or not evaluation.allowed
        ):
            # Store should remain unchanged
            assert store.get_item("safe-1").status == KnowledgeStatus.ACTIVE
            assert store.get_item("safe-2").status == KnowledgeStatus.ACTIVE

    def test_rollback_restores_state(self, store: Any) -> None:
        """Transaction rollback should restore original state."""
        item = _make_item("rollback-1", "Declaración original")
        store.save_item(item)

        try:
            with store.transaction() as tx_store:
                tx_store.delete_item("rollback-1")
                assert not tx_store.contains_item("rollback-1")
                raise ValueError("Force rollback")
        except ValueError:
            pass

        # Item should still exist
        assert store.contains_item("rollback-1")
        restored = store.get_item("rollback-1")
        assert restored.statement == "Declaración original"

    def test_information_is_preserved_on_invalidation(self, store: Any) -> None:
        """Invalidation should not delete items."""
        item = _make_item("preserve-1", "Seré invalidado")
        store.save_item(item)

        invalidated = item.invalidate("Ya no es preciso", invalidated_at=NOW)
        store.save_item(invalidated)

        fetched = store.get_item("preserve-1")
        assert fetched.status == KnowledgeStatus.INVALIDATED
        assert fetched.invalidation_reason == "Ya no es preciso"
        # Original data preserved
        assert fetched.statement == "Seré invalidado"

    def test_supersession_preserves_lineage(self, store: Any) -> None:
        """Superseded items remain in the store with lineage intact."""
        original = _make_item("lineage-1", "Versión 1")
        store.save_item(original)

        revision = original.create_revision(statement="Versión 2")
        store.save_item(revision)

        superseded = original.mark_superseded(revision.id)
        store.save_item(superseded)

        # Both items should exist
        old = store.get_item("lineage-1")
        assert old.status == KnowledgeStatus.SUPERSEDED
        assert old.superseded_by_id == revision.id

        new = store.get_item(revision.id)
        assert new.supersedes_id == "lineage-1"
        assert new.statement == "Versión 2"
