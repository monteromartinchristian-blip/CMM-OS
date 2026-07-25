"""Phase 8 basic performance / regression tests.

Measures wall-clock time for common cognitive operations on controlled data.
The goal is to detect obvious regressions, not to enforce strict timing.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from cmm.cognitive.cognitive_cycle import CognitiveCycleEngine
from cmm.cognitive.consolidation import KnowledgeConsolidator
from cmm.cognitive.contracts import Confidence
from cmm.cognitive.contradiction_detection import KnowledgeContradictionDetector
from cmm.cognitive.contradiction_resolution import KnowledgeContradictionResolver
from cmm.cognitive.enums import KnowledgeKind
from cmm.cognitive.knowledge import KnowledgeItem
from cmm.cognitive.reflection import CognitiveReflectionEngine
from cmm.cognitive.resolution_executor import ContradictionResolutionExecutor
from cmm.cognitive.resolution_memory import InMemoryResolutionMemoryStore
from cmm.cognitive.resolution_policy import ContradictionResolutionPolicyEngine
from cmm.cognitive.retrieval import KnowledgeRetriever
from cmm.cognitive.store_memory import InMemoryKnowledgeStore

NOW = datetime.now(timezone.utc)


def _make_item(idx: int) -> KnowledgeItem:
    return KnowledgeItem(
        id=f"perf-{idx:05d}",
        statement=f"Performance test statement number {idx}",
        kind=KnowledgeKind.FACT,
        confidence=Confidence(value=0.8),
        created_at=NOW,
        updated_at=NOW,
    )


class TestBulkItemPerformance:
    """Measure store operations at moderate scale."""

    def test_save_1000_items(self) -> None:
        store = InMemoryKnowledgeStore()
        items = [_make_item(i) for i in range(1000)]

        start = time.monotonic()
        for item in items:
            store.save_item(item)
        elapsed = time.monotonic() - start

        assert store.count_items() == 1000
        # Should complete in well under 10 seconds
        assert elapsed < 10.0, f"Saving 1000 items took {elapsed:.2f}s"

    def test_retrieve_and_filter(self) -> None:
        store = InMemoryKnowledgeStore()
        for i in range(500):
            store.save_item(_make_item(i))

        retriever = KnowledgeRetriever(store)

        start = time.monotonic()
        items = retriever.get_items([f"perf-{i:05d}" for i in range(500)])
        elapsed = time.monotonic() - start

        assert len(items) == 500
        assert elapsed < 5.0, f"Retrieving 500 items took {elapsed:.2f}s"

    def test_list_with_pagination(self) -> None:
        store = InMemoryKnowledgeStore()
        for i in range(200):
            store.save_item(_make_item(i))

        start = time.monotonic()
        all_items: list[KnowledgeItem] = []
        offset = 0
        while True:
            batch = store.list_items(limit=50, offset=offset)
            if not batch:
                break
            all_items.extend(batch)
            offset += len(batch)
        elapsed = time.monotonic() - start

        assert len(all_items) == 200
        assert elapsed < 5.0


class TestConsolidationPerformance:
    """Measure consolidation candidate detection at moderate scale."""

    def test_find_candidates_controlled_group(self) -> None:
        store = InMemoryKnowledgeStore()
        # Create 20 items, some with similar statements
        items = []
        for i in range(20):
            item = KnowledgeItem(
                id=f"consperf-{i}",
                statement=f"The temperature is {25 + (i % 3)} degrees",
                kind=KnowledgeKind.FACT,
                confidence=Confidence(value=0.8),
                created_at=NOW,
                updated_at=NOW,
            )
            store.save_item(item)
            items.append(item)

        consolidator = KnowledgeConsolidator(store)

        start = time.monotonic()
        _ = consolidator.find_candidates()
        elapsed = time.monotonic() - start

        # Just ensure it completes in reasonable time
        assert elapsed < 5.0, f"Finding candidates took {elapsed:.2f}s"


class TestSerializationPerformance:
    """Measure contract serialization round-trips."""

    def test_serialize_1000_items(self) -> None:
        items = [_make_item(i) for i in range(1000)]

        start = time.monotonic()
        payloads = [item.serialize() for item in items]
        elapsed_ser = time.monotonic() - start

        start = time.monotonic()
        restored = [KnowledgeItem.from_mapping(p) for p in payloads]
        elapsed_deser = time.monotonic() - start

        assert len(restored) == 1000
        assert elapsed_ser < 5.0, f"Serializing 1000 items took {elapsed_ser:.2f}s"
        assert elapsed_deser < 5.0, (
            f"Deserializing 1000 items took {elapsed_deser:.2f}s"
        )


class TestSmallCyclePerformance:
    """Measure a small cognitive cycle end-to-end."""

    def test_cycle_with_5_items(self) -> None:
        store = InMemoryKnowledgeStore()
        items = [
            KnowledgeItem(
                id=f"cycp-{i}",
                statement=f"Cycle performance statement {i}",
                kind=KnowledgeKind.FACT,
                confidence=Confidence(value=0.8),
                created_at=NOW,
                updated_at=NOW,
            )
            for i in range(5)
        ]
        for item in items:
            store.save_item(item)

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

        start = time.monotonic()
        record = engine.run_cycle(
            item_ids=[f"cycp-{i}" for i in range(5)], created_at=NOW
        )
        elapsed = time.monotonic() - start

        assert record.status.value in ("completed", "failed")
        assert elapsed < 10.0, f"Small cycle took {elapsed:.2f}s"
