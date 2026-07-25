"""Tests for Cognitive Layer public API surface.

Verifies that __all__ is complete, has no duplicates, all names resolve,
and compatibility aliases remain functional.
"""

from __future__ import annotations

from cmm import cognitive


class TestPublicApiExports:
    """Ensure the public API surface is coherent and complete."""

    def test_all_names_exist(self) -> None:
        for name in cognitive.__all__:
            assert hasattr(cognitive, name), (
                f"__all__ contains '{name}' but it is missing"
            )

    def test_no_duplicates(self) -> None:
        exports = cognitive.__all__
        seen: set[str] = set()
        duplicates: list[str] = []
        for name in exports:
            if name in seen:
                duplicates.append(name)
            seen.add(name)
        assert duplicates == [], f"Duplicate exports: {duplicates}"

    def test_all_is_sorted(self) -> None:
        exports = list(cognitive.__all__)
        assert exports == sorted(exports), "__all__ is not sorted"

    def test_minimum_export_count(self) -> None:
        assert len(cognitive.__all__) >= 170, (
            f"Expected at least 170 exports, got {len(cognitive.__all__)}"
        )


from typing import ClassVar


class TestCoreContractsImportable:
    """Verify key contracts can be imported from the top-level package."""

    EXPECTED_CONTRACTS: ClassVar[list[str]] = [
        "Confidence",
        "CognitiveActor",
        "CognitiveFinding",
        "CognitiveResult",
        "CognitiveIdentifier",
        "Resource",
        "Evidence",
        "KnowledgeItem",
        "KnowledgeRelation",
        "KnowledgeBundle",
        "Contradiction",
        "TemporalScope",
        "KnowledgeQuery",
        "KnowledgeQueryResult",
        "ConsolidationCandidate",
        "ConsolidationPlan",
        "ConsolidationResult",
        "ContradictionDetection",
        "ContradictionDetectionResult",
        "ContradictionResolutionProposal",
        "ContradictionResolutionResult",
        "ResolutionPolicyEvaluation",
        "ResolutionExecutionResult",
        "ResolutionAuditRecord",
        "ResolutionMemoryEntry",
        "ResolutionMemoryQuery",
        "ResolutionMemoryResult",
        "ReflectionFinding",
        "ReflectionQuery",
        "CognitiveReflectionReport",
        "CognitiveCycleRecord",
    ]

    def test_contracts_importable(self) -> None:
        for name in self.EXPECTED_CONTRACTS:
            obj = getattr(cognitive, name, None)
            assert obj is not None, (
                f"Contract '{name}' not importable from cmm.cognitive"
            )

    EXPECTED_ENUMS: ClassVar[list[str]] = [
        "CognitiveStatus",
        "CognitiveSeverity",
        "KnowledgeKind",
        "KnowledgeStatus",
        "ContradictionStatus",
        "ContradictionSeverity",
        "ResolutionDecision",
        "ResolutionStatus",
        "ExecutionStatus",
        "PolicyDecision",
        "CognitiveCycleStatus",
    ]

    def test_enums_importable(self) -> None:
        for name in self.EXPECTED_ENUMS:
            obj = getattr(cognitive, name, None)
            assert obj is not None, f"Enum '{name}' not importable from cmm.cognitive"

    EXPECTED_ENGINES: ClassVar[list[str]] = [
        "KnowledgeConsolidator",
        "KnowledgeContradictionDetector",
        "ContradictionResolutionEngine",
        "KnowledgeContradictionResolver",
        "ContradictionResolutionPolicyEngine",
        "ContradictionResolutionExecutor",
        "CognitiveReflectionEngine",
        "CognitiveCycleEngine",
        "KnowledgeRetriever",
    ]

    def test_engines_importable(self) -> None:
        for name in self.EXPECTED_ENGINES:
            obj = getattr(cognitive, name, None)
            assert obj is not None, f"Engine '{name}' not importable from cmm.cognitive"

    EXPECTED_STORES: ClassVar[list[str]] = [
        "InMemoryKnowledgeStore",
        "SQLiteKnowledgeStore",
        "LocalKnowledgeStore",
        "KnowledgeStoreProtocol",
        "InMemoryResolutionMemoryStore",
        "ResolutionMemoryStore",
    ]

    def test_stores_importable(self) -> None:
        for name in self.EXPECTED_STORES:
            obj = getattr(cognitive, name, None)
            assert obj is not None, f"Store '{name}' not importable from cmm.cognitive"


class TestCompatibilityAliases:
    """Verify serialize/to_dict and from_mapping/from_dict aliases."""

    def test_temporal_scope_aliases(self) -> None:
        ts = cognitive.TemporalScope()
        assert ts.serialize() == ts.to_dict()
        d = ts.serialize()
        d["kind"] = "unknown"
        assert cognitive.TemporalScope.from_mapping(
            d
        ) == cognitive.TemporalScope.from_dict(d)

    def test_evidence_aliases(self) -> None:
        ev = cognitive.Evidence(
            resource_id="r-1",
            fragment="test fragment",
            confidence=cognitive.Confidence(value=0.9),
        )
        assert ev.serialize() == ev.to_dict()
        d = ev.serialize()
        reconstructed_a = cognitive.Evidence.from_mapping(d)
        reconstructed_b = cognitive.Evidence.from_dict(d)
        assert reconstructed_a.id == reconstructed_b.id

    def test_knowledge_item_aliases(self) -> None:
        item = cognitive.KnowledgeItem(
            statement="Test statement",
            kind=cognitive.KnowledgeKind.FACT,
            confidence=cognitive.Confidence(value=0.8),
        )
        assert item.serialize() == item.to_dict()
        d = item.serialize()
        r1 = cognitive.KnowledgeItem.from_mapping(d)
        r2 = cognitive.KnowledgeItem.from_dict(d)
        assert r1.id == r2.id

    def test_contradiction_aliases(self) -> None:
        c = cognitive.Contradiction(item_a_id="a", item_b_id="b")
        assert c.serialize() == c.to_dict()
        d = c.serialize()
        assert (
            cognitive.Contradiction.from_mapping(d).id
            == cognitive.Contradiction.from_dict(d).id
        )

    def test_knowledge_bundle_aliases(self) -> None:
        b = cognitive.KnowledgeBundle()
        assert b.serialize() == b.to_dict()
        d = b.serialize()
        assert (
            cognitive.KnowledgeBundle.from_mapping(d).id
            == cognitive.KnowledgeBundle.from_dict(d).id
        )

    def test_knowledge_relation_aliases(self) -> None:
        r = cognitive.KnowledgeRelation(
            source_id="s",
            target_id="t",
            kind=cognitive.KnowledgeRelationKind.SUPPORTS,
            confidence=cognitive.Confidence(value=0.7),
        )
        assert r.serialize() == r.to_dict()
        d = r.serialize()
        assert (
            cognitive.KnowledgeRelation.from_mapping(d).id
            == cognitive.KnowledgeRelation.from_dict(d).id
        )

    def test_cognitive_cycle_record_aliases(self) -> None:
        from datetime import datetime, timezone

        rec = cognitive.CognitiveCycleRecord(
            cycle_id="cognitive-cycle:abc123",
            created_at=datetime.now(timezone.utc),
            input_item_ids=("i-1",),
            contradiction_ids=(),
            resolution_proposal_ids=(),
            execution_ids=(),
            memory_entry_ids=(),
            reflection_report_id=None,
            status=cognitive.CognitiveCycleStatus.CREATED,
        )
        assert rec.serialize() == rec.to_dict()
        d = rec.serialize()
        r1 = cognitive.CognitiveCycleRecord.from_mapping(d)
        r2 = cognitive.CognitiveCycleRecord.from_dict(d)
        assert r1.cycle_id == r2.cycle_id
