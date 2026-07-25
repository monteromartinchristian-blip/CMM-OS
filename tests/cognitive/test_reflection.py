"""Phase 8.14 – Cognitive Reflection & Resolution Feedback Layer Tests.

Tests contracts, engine metrics, deterministic report ID generation, pattern discovery,
cognitive safety (zero side-effects), and full end-to-end cognitive traceability.
"""

from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from cmm.cognitive.contracts import Confidence, utc_now
from cmm.cognitive.contradiction_detection_contracts import (
    ContradictionDetection,
    ContradictionKind,
    ContradictionSignal,
)
from cmm.cognitive.errors import InvalidReflectionReportError
from cmm.cognitive.knowledge import (
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeStatus,
)
from cmm.cognitive.reflection import CognitiveReflectionEngine
from cmm.cognitive.reflection_contracts import (
    CognitiveReflectionReport,
    ReflectionFinding,
    ReflectionQuery,
    generate_reflection_report_id,
)
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
from cmm.cognitive.resolution_memory_contracts import ResolutionMemoryEntry
from cmm.cognitive.resolution_policy import ContradictionResolutionPolicyEngine
from cmm.cognitive.resolution_policy_contracts import PolicyDecision
from cmm.cognitive.store_memory import InMemoryKnowledgeStore


def _make_sample_entry(
    entry_id: str = "entry-1",
    contradiction_id: str = "contra-1",
    item_a_id: str = "item-a",
    item_b_id: str = "item-b",
    proposal_id: str = "prop-1",
    decision: ResolutionDecision = ResolutionDecision.PREFER_ITEM_A,
    policy_decision: PolicyDecision = PolicyDecision.AUTO_APPROVED,
    execution_status: ExecutionStatus = ExecutionStatus.COMPLETED,
    confidence: float = 0.9,
    created_at: datetime | None = None,
    kind: str = "direct",
) -> ResolutionMemoryEntry:
    now = created_at or utc_now()
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
        actor_id="test-actor",
        created_at=now,
        updated_at=now,
        rationale=("Sample rationale",),
        evidence_ids=("ev-1",),
        metadata={"contradiction_kind": kind},
    )


# ── Contracts Tests ─────────────────────────────────────────────────────────


def test_reflection_finding_valid_and_serialization() -> None:
    finding = ReflectionFinding(
        category="human_dependency",
        severity="warning",
        description="High dependency on human reviews",
        related_entry_ids=("entry-1", "entry-2"),
        confidence=0.85,
    )
    assert finding.category == "human_dependency"
    assert finding.severity == "warning"
    assert finding.description == "High dependency on human reviews"
    assert finding.related_entry_ids == ("entry-1", "entry-2")
    assert finding.confidence == 0.85

    data = finding.serialize()
    restored = ReflectionFinding.from_mapping(data)
    assert restored == finding
    assert restored.to_dict() == data


def test_reflection_finding_invalid_inputs() -> None:
    with pytest.raises(InvalidReflectionReportError, match="category"):
        ReflectionFinding(
            category="",
            severity="warning",
            description="desc",
        )

    with pytest.raises(InvalidReflectionReportError, match="confidence"):
        ReflectionFinding(
            category="cat",
            severity="warning",
            description="desc",
            confidence=1.5,
        )


def test_reflection_query_filtering_and_validation() -> None:
    query = ReflectionQuery(
        decision=ResolutionDecision.PREFER_ITEM_A,
        execution_status=ExecutionStatus.COMPLETED,
        minimum_confidence=0.8,
    )

    matching_entry = _make_sample_entry(
        decision=ResolutionDecision.PREFER_ITEM_A,
        execution_status=ExecutionStatus.COMPLETED,
        confidence=0.9,
    )
    non_matching_entry = _make_sample_entry(
        decision=ResolutionDecision.KEEP_BOTH,
        execution_status=ExecutionStatus.COMPLETED,
        confidence=0.9,
    )
    low_confidence_entry = _make_sample_entry(
        decision=ResolutionDecision.PREFER_ITEM_A,
        execution_status=ExecutionStatus.COMPLETED,
        confidence=0.5,
    )

    assert query.matches(matching_entry) is True
    assert query.matches(non_matching_entry) is False
    assert query.matches(low_confidence_entry) is False

    serialized = query.serialize()
    restored = ReflectionQuery.from_mapping(serialized)
    assert restored.decision == query.decision
    assert restored.minimum_confidence == query.minimum_confidence


def test_reflection_query_invalid_datetime_range() -> None:
    t1 = datetime(2026, 1, 2, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(
        InvalidReflectionReportError, match="created_before cannot be earlier"
    ):
        ReflectionQuery(created_after=t1, created_before=t2)


def test_cognitive_reflection_report_valid_and_serialization() -> None:
    now = utc_now()
    finding = ReflectionFinding(
        category="general",
        severity="info",
        description="Sample finding",
    )
    report = CognitiveReflectionReport(
        id="reflection-report:123456",
        created_at=now,
        analysed_entries=10,
        contradiction_count=8,
        resolution_count=10,
        human_review_count=2,
        auto_resolution_count=8,
        average_confidence=0.92,
        decision_distribution={"prefer_item_a": 6, "keep_both": 4},
        contradiction_distribution={"direct": 8, "temporal": 2},
        policy_distribution={"auto_approved": 8, "human_review_required": 2},
        findings=(finding,),
        warnings=("Sample warning",),
        metadata={"source": "unit-test"},
    )

    assert report.analysed_entries == 10
    assert report.average_confidence == 0.92
    assert isinstance(report.decision_distribution, MappingProxyType)
    assert isinstance(report.metadata, MappingProxyType)
    assert report.findings[0] == finding

    data = report.serialize()
    restored = CognitiveReflectionReport.from_mapping(data)
    assert restored.id == report.id
    assert restored.analysed_entries == report.analysed_entries
    assert restored.average_confidence == report.average_confidence
    assert restored.decision_distribution == report.decision_distribution
    assert restored.to_dict() == data


def test_cognitive_reflection_report_invalid_validations() -> None:
    now = utc_now()

    # Invalid ID
    with pytest.raises(
        InvalidReflectionReportError, match="id must be a non-empty string"
    ):
        CognitiveReflectionReport(
            id="   ",
            created_at=now,
            analysed_entries=1,
            contradiction_count=1,
            resolution_count=1,
            human_review_count=0,
            auto_resolution_count=1,
            average_confidence=0.8,
            decision_distribution={},
            contradiction_distribution={},
            policy_distribution={},
        )

    # Naive Datetime
    with pytest.raises(InvalidReflectionReportError, match="timezone-aware"):
        CognitiveReflectionReport(
            id="reflection-report:abc",
            created_at=datetime(2026, 1, 1),  # noqa: DTZ001
            analysed_entries=1,
            contradiction_count=1,
            resolution_count=1,
            human_review_count=0,
            auto_resolution_count=1,
            average_confidence=0.8,
            decision_distribution={},
            contradiction_distribution={},
            policy_distribution={},
        )

    # Invalid Confidence (> 1.0)
    with pytest.raises(InvalidReflectionReportError, match="average_confidence"):
        CognitiveReflectionReport(
            id="reflection-report:abc",
            created_at=now,
            analysed_entries=1,
            contradiction_count=1,
            resolution_count=1,
            human_review_count=0,
            auto_resolution_count=1,
            average_confidence=1.5,
            decision_distribution={},
            contradiction_distribution={},
            policy_distribution={},
        )


# ── Engine & Metrics Tests ──────────────────────────────────────────────────


def test_reflection_engine_metrics_calculation() -> None:
    store = InMemoryResolutionMemoryStore()
    now = utc_now()

    e1 = _make_sample_entry(
        entry_id="ref-1",
        contradiction_id="c-1",
        decision=ResolutionDecision.PREFER_ITEM_A,
        policy_decision=PolicyDecision.AUTO_APPROVED,
        execution_status=ExecutionStatus.COMPLETED,
        confidence=0.9,
        created_at=now,
        kind="direct",
    )
    e2 = _make_sample_entry(
        entry_id="ref-2",
        contradiction_id="c-2",
        decision=ResolutionDecision.REQUEST_HUMAN_REVIEW,
        policy_decision=PolicyDecision.HUMAN_REVIEW_REQUIRED,
        execution_status=ExecutionStatus.FAILED,
        confidence=0.5,
        created_at=now,
        kind="temporal",
    )
    e3 = _make_sample_entry(
        entry_id="ref-3",
        contradiction_id="c-1",
        decision=ResolutionDecision.PREFER_ITEM_A,
        policy_decision=PolicyDecision.AUTO_APPROVED,
        execution_status=ExecutionStatus.COMPLETED,
        confidence=0.8,
        created_at=now,
        kind="direct",
    )

    store.save(e1)
    store.save(e2)
    store.save(e3)

    engine = CognitiveReflectionEngine()
    report = engine.reflect(store, created_at=now)

    assert report.analysed_entries == 3
    assert report.contradiction_count == 2  # c-1 and c-2
    assert report.resolution_count == 3
    assert report.human_review_count == 1
    assert report.auto_resolution_count == 2
    assert report.average_confidence == pytest.approx(0.7333, abs=0.01)

    assert report.decision_distribution["prefer_item_a"] == 2
    assert report.decision_distribution["request_human_review"] == 1

    assert report.contradiction_distribution["direct"] == 2
    assert report.contradiction_distribution["temporal"] == 1

    assert report.policy_distribution["auto_approved"] == 2
    assert report.policy_distribution["human_review_required"] == 1


def test_reflection_engine_pattern_findings() -> None:
    engine = CognitiveReflectionEngine()
    now = utc_now()

    # Case 1: High Human Review Dependency (> 50%)
    entries_high_hr = [
        _make_sample_entry(
            entry_id=f"e-{i}",
            decision=ResolutionDecision.REQUEST_HUMAN_REVIEW,
            policy_decision=PolicyDecision.HUMAN_REVIEW_REQUIRED,
        )
        for i in range(3)
    ]
    entries_high_hr.append(
        _make_sample_entry(
            entry_id="e-3",
            decision=ResolutionDecision.PREFER_ITEM_A,
            policy_decision=PolicyDecision.AUTO_APPROVED,
        )
    )

    report_hr = engine.reflect(entries_high_hr, created_at=now)
    assert any(f.category == "human_dependency" for f in report_hr.findings)
    assert (
        "Over 50% of analyzed resolutions required human review." in report_hr.warnings
    )

    # Case 2: Low Confidence Resolutions (< 0.60 avg)
    entries_low_conf = [
        _make_sample_entry(entry_id=f"e-{i}", confidence=0.4) for i in range(3)
    ]
    report_low_conf = engine.reflect(entries_low_conf, created_at=now)
    assert any(f.category == "confidence" for f in report_low_conf.findings)
    assert any("below threshold 0.60" in w for w in report_low_conf.warnings)


# ── Determinism Tests ────────────────────────────────────────────────────────


def test_generate_reflection_report_id_determinism() -> None:
    now = datetime(2026, 7, 25, 12, 0, 0, tzinfo=timezone.utc)
    id1 = generate_reflection_report_id(
        analysed_entries=5,
        created_at=now,
        decision_distribution={"prefer_item_a": 3, "keep_both": 2},
        contradiction_distribution={"direct": 5},
        policy_distribution={"auto_approved": 5},
    )

    id2 = generate_reflection_report_id(
        analysed_entries=5,
        created_at=now,
        decision_distribution={"prefer_item_a": 3, "keep_both": 2},
        contradiction_distribution={"direct": 5},
        policy_distribution={"auto_approved": 5},
    )

    assert id1 == id2
    assert id1.startswith("reflection-report:")


def test_engine_reflect_determinism() -> None:
    store = InMemoryResolutionMemoryStore()
    now = utc_now()

    e1 = _make_sample_entry(entry_id="e1", contradiction_id="c1", created_at=now)
    e2 = _make_sample_entry(entry_id="e2", contradiction_id="c2", created_at=now)
    store.save(e1)
    store.save(e2)

    engine = CognitiveReflectionEngine()
    r1 = engine.reflect(store, created_at=now)
    r2 = engine.reflect(store, created_at=now)

    assert r1.id == r2.id
    assert r1.to_dict() == r2.to_dict()


# ── Cognitive Safety Tests ──────────────────────────────────────────────────


def test_cognitive_safety_zero_side_effects() -> None:
    store = InMemoryResolutionMemoryStore()
    now = utc_now()

    e1 = _make_sample_entry(entry_id="safe-1", created_at=now)
    store.save(e1)

    initial_memory_count = store.count()

    engine = CognitiveReflectionEngine()
    report = engine.reflect(store, created_at=now)

    # Assert memory store state was unchanged
    assert store.count() == initial_memory_count
    assert store.get("safe-1") == e1
    # Assert report was returned successfully
    assert isinstance(report, CognitiveReflectionReport)


# ── Full Cognitive Lifecycle Integration Test ───────────────────────────────


def test_full_cognitive_lifecycle_traceability() -> None:
    """Full lifecycle integration test:

    Detection -> Proposal -> Policy -> Execution -> Memory -> Reflection
    """
    now = utc_now()
    kstore = InMemoryKnowledgeStore()
    mstore = InMemoryResolutionMemoryStore()

    # 1. Knowledge Items & Contradiction Detection
    item_a = KnowledgeItem(
        id="item-alpha",
        kind=KnowledgeKind.FACT,
        statement="System status is ONLINE",
        status=KnowledgeStatus.UNVERIFIED,
        confidence=Confidence(value=0.9, source="test"),
        created_at=now,
        updated_at=now,
    )
    item_b = KnowledgeItem(
        id="item-beta",
        kind=KnowledgeKind.FACT,
        statement="System status is OFFLINE",
        status=KnowledgeStatus.UNVERIFIED,
        confidence=Confidence(value=0.8, source="test"),
        created_at=now,
        updated_at=now,
    )
    kstore.save_item(item_a)
    kstore.save_item(item_b)

    signal = ContradictionSignal(
        kind=ContradictionKind.DIRECT,
        field="statement",
        value_a="System status is ONLINE",
        value_b="System status is OFFLINE",
        strength=0.9,
        reason="Direct conflict in statement content",
    )
    detection = ContradictionDetection(
        item_a_id=item_a.id,
        item_b_id=item_b.id,
        is_contradiction=True,
        kind=ContradictionKind.DIRECT,
        confidence=0.85,
        signals=(signal,),
        existing_contradiction_id="det-alpha-beta",
    )
    assert detection.is_contradiction is True

    # 2. Proposal
    proposal = ContradictionResolutionProposal(
        id="prop-alpha-beta",
        contradiction_id="det-alpha-beta",
        item_a_id=item_a.id,
        item_b_id=item_b.id,
        decision=ResolutionDecision.KEEP_BOTH,
        status=ResolutionStatus.APPROVED,
        confidence=0.9,
        rationale=("Item A has higher confidence",),
        created_at=now,
    )

    # 3. Policy Evaluation
    policy_engine = ContradictionResolutionPolicyEngine(allow_auto_resolution=True)
    eval_result = policy_engine.evaluate(proposal)
    assert eval_result.decision == PolicyDecision.AUTO_APPROVED

    # 4. Resolution Execution
    executor = ContradictionResolutionExecutor(kstore)
    exec_result = executor.execute(proposal, eval_result)
    assert exec_result.status == ExecutionStatus.COMPLETED

    # 5. Resolution Memory
    mem_entry = memory_from_execution_result(exec_result, proposal, eval_result)
    mstore.save(mem_entry)
    assert mstore.contains(mem_entry.id) is True

    # 6. Reflection
    reflection_engine = CognitiveReflectionEngine()
    report = reflection_engine.reflect(mstore, created_at=now)

    assert report.analysed_entries == 1
    assert report.contradiction_count == 1
    assert report.auto_resolution_count == 1
    assert report.human_review_count == 0
    assert report.average_confidence == 0.9
    assert report.decision_distribution["keep_both"] == 1
    assert report.policy_distribution["auto_approved"] == 1
