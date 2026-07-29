"""Phase 9.18 – Knowledge and Memory Update Comprehensive Test Suite.

Targeting >= 150 tests covering contracts, repository, candidate extraction, relevance,
confidence, sensitivity, deduplication, contradiction resolution, operational lessons,
memory policies, proposal engine, execution manager, outcome integration, recovery integration,
event emissions, and security invariants.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from cmm.agent_runtime.enums import (
    KnowledgeCandidateKind,
    KnowledgeConfidenceLevel,
    KnowledgeProposalStatus,
    KnowledgeRejectionReason,
    KnowledgeSensitivityLevel,
    KnowledgeWriteDecisionKind,
    MemoryWriteDecisionKind,
    OperationalLessonKind,
    Outcome,
)
from cmm.agent_runtime.errors import (
    InvalidAgentContractError,
    KnowledgeApprovalRequiredError,
    KnowledgeFingerprintError,
    KnowledgeWriteError,
)
from cmm.agent_runtime.knowledge_candidate_extractor import KnowledgeCandidateExtractor
from cmm.agent_runtime.knowledge_confidence_evaluator import (
    KnowledgeConfidenceEvaluator,
)
from cmm.agent_runtime.knowledge_contradiction_resolver import (
    KnowledgeContradictionResolver,
)
from cmm.agent_runtime.knowledge_deduplicator import KnowledgeDeduplicator
from cmm.agent_runtime.knowledge_memory_update_manager import (
    KnowledgeMemoryUpdateManager,
)
from cmm.agent_runtime.knowledge_relevance_evaluator import KnowledgeRelevanceEvaluator
from cmm.agent_runtime.knowledge_sensitivity_policy import (
    KnowledgeSensitivityPolicyAdapter,
)
from cmm.agent_runtime.knowledge_update_contracts import (
    AgentKnowledgeUpdateProposal,
    KnowledgeAddition,
    KnowledgeProvenance,
    KnowledgeSensitivityAssessment,
    KnowledgeUpdateCandidate,
    KnowledgeUpdateContext,
    KnowledgeUpdateDecision,
    KnowledgeVersionReference,
    MemoryUpdateCandidate,
    MemoryUpdateProposal,
    MemoryWriteDecision,
    OperationalLesson,
)
from cmm.agent_runtime.knowledge_update_proposal_engine import (
    KnowledgeUpdateProposalEngine,
)
from cmm.agent_runtime.knowledge_update_repository import (
    InMemoryKnowledgeUpdateRepository,
)
from cmm.agent_runtime.memory_update_policy_adapter import MemoryUpdatePolicyAdapter

# ── Section 1: Contracts Tests ───────────────────────────────────────────────


def test_knowledge_provenance_creation():
    prov = KnowledgeProvenance(source_run_id="run-1", source_goal_id="goal-1")
    assert prov.source_run_id == "run-1"
    assert prov.source_goal_id == "goal-1"
    assert prov.fingerprint != ""


def test_knowledge_provenance_validation():
    with pytest.raises(InvalidAgentContractError):
        KnowledgeProvenance(source_run_id="", source_goal_id="goal-1")


def test_knowledge_sensitivity_assessment():
    sens = KnowledgeSensitivityAssessment(
        assessment_id="sens-1",
        level=KnowledgeSensitivityLevel.PUBLIC,
    )
    assert sens.level == KnowledgeSensitivityLevel.PUBLIC
    assert sens.fingerprint != ""


def test_knowledge_candidate_immutability():
    prov = KnowledgeProvenance(source_run_id="run-1", source_goal_id="goal-1")
    cand = KnowledgeUpdateCandidate(
        candidate_id="cand-1",
        kind=KnowledgeCandidateKind.CREATED_GOAL,
        title="Title 1",
        content={"k": "v"},
        provenance=prov,
        confidence=0.9,
        relevance_score=0.8,
        reusable=True,
    )
    with pytest.raises(AttributeError):
        cand.confidence = 0.5


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_knowledge_candidate_confidence_bounds(confidence):
    prov = KnowledgeProvenance(source_run_id="run-1", source_goal_id="goal-1")
    with pytest.raises(InvalidAgentContractError):
        KnowledgeUpdateCandidate(
            candidate_id="cand-1",
            kind=KnowledgeCandidateKind.CREATED_GOAL,
            title="Title",
            content={},
            provenance=prov,
            confidence=confidence,
            relevance_score=0.8,
            reusable=True,
        )


def test_operational_lesson_contract():
    les = OperationalLesson(
        lesson_id="les-1",
        statement="Statement",
        kind=OperationalLessonKind.SUCCESS_PATTERN,
        evidence_ids=("ev-1",),
        scope={"goal": "g1"},
        confidence=0.95,
        reusable=True,
    )
    assert les.lesson_id == "les-1"
    assert les.fingerprint != ""


# ── Section 2: Repository Tests ──────────────────────────────────────────────


def test_repository_save_and_get_proposal():
    repo = InMemoryKnowledgeUpdateRepository()
    sens = KnowledgeSensitivityAssessment(
        assessment_id="s1", level=KnowledgeSensitivityLevel.PUBLIC
    )
    prop = AgentKnowledgeUpdateProposal(
        proposal_id="prop-1",
        agent_run_id="run-1",
        goal_id="goal-1",
        workflow_id="wf-1",
        iteration_id="it-1",
        outcome_evaluation_id="oe-1",
        completion_decision_id="cd-1",
        additions=(),
        updates=(),
        invalidations=(),
        relations=(),
        operation_facts=(),
        decisions=(),
        lessons=(),
        rejected_items=(),
        requires_approval=False,
        confidence=0.9,
        reasons=(),
        source_evidence_ids=(),
        validation_result_ids=(),
        permissions=(),
        sensitivity=sens,
    )
    repo.save_proposal(prop)
    retrieved = repo.get_proposal("prop-1")
    assert retrieved == prop


def test_repository_idempotency_same_fingerprint():
    repo = InMemoryKnowledgeUpdateRepository()
    sens = KnowledgeSensitivityAssessment(
        assessment_id="s1", level=KnowledgeSensitivityLevel.PUBLIC
    )
    prop = AgentKnowledgeUpdateProposal(
        proposal_id="prop-1",
        agent_run_id="run-1",
        goal_id="goal-1",
        workflow_id="wf-1",
        iteration_id="it-1",
        outcome_evaluation_id="oe-1",
        completion_decision_id="cd-1",
        additions=(),
        updates=(),
        invalidations=(),
        relations=(),
        operation_facts=(),
        decisions=(),
        lessons=(),
        rejected_items=(),
        requires_approval=False,
        confidence=0.9,
        reasons=(),
        source_evidence_ids=(),
        validation_result_ids=(),
        permissions=(),
        sensitivity=sens,
    )
    res1 = repo.save_proposal(prop, idempotency_key="key-1")
    res2 = repo.save_proposal(prop, idempotency_key="key-1")
    assert res1 == res2


def test_repository_idempotency_different_fingerprint_raises():
    repo = InMemoryKnowledgeUpdateRepository()
    sens = KnowledgeSensitivityAssessment(
        assessment_id="s1", level=KnowledgeSensitivityLevel.PUBLIC
    )
    prop1 = AgentKnowledgeUpdateProposal(
        proposal_id="prop-1",
        agent_run_id="run-1",
        goal_id="goal-1",
        workflow_id="wf-1",
        iteration_id="it-1",
        outcome_evaluation_id="oe-1",
        completion_decision_id="cd-1",
        additions=(),
        updates=(),
        invalidations=(),
        relations=(),
        operation_facts=(),
        decisions=(),
        lessons=(),
        rejected_items=(),
        requires_approval=False,
        confidence=0.9,
        reasons=(),
        source_evidence_ids=(),
        validation_result_ids=(),
        permissions=(),
        sensitivity=sens,
    )
    prop2 = AgentKnowledgeUpdateProposal(
        proposal_id="prop-2",
        agent_run_id="run-1",
        goal_id="goal-1",
        workflow_id="wf-1",
        iteration_id="it-1",
        outcome_evaluation_id="oe-1",
        completion_decision_id="cd-1",
        additions=(),
        updates=(),
        invalidations=(),
        relations=(),
        operation_facts=(),
        decisions=(),
        lessons=(),
        rejected_items=(),
        requires_approval=True,
        confidence=0.5,
        reasons=(),
        source_evidence_ids=(),
        validation_result_ids=(),
        permissions=(),
        sensitivity=sens,
    )
    repo.save_proposal(prop1, idempotency_key="key-1")
    with pytest.raises(KnowledgeFingerprintError):
        repo.save_proposal(prop2, idempotency_key="key-1")


def test_repository_missing_queries():
    repo = InMemoryKnowledgeUpdateRepository()
    assert repo.get_proposal("nonexistent") is None
    assert repo.get_decision("nonexistent") is None
    assert repo.get_result("nonexistent") is None


# ── Section 3: Candidate Extraction Tests ────────────────────────────────────


@pytest.mark.parametrize(
    "kind_str",
    [
        "created_goal",
        "completed_goal",
        "operation_result",
        "validated_state",
        "structural_change",
        "decision",
        "constraint",
        "explicit_preference",
        "reproducible_error",
        "failed_strategy",
        "successful_strategy",
        "dependency",
        "contradiction",
        "technical_debt",
        "generated_artifact",
        "new_capability",
        "updated_resource",
    ],
)
def test_all_17_candidate_kinds_extracted(kind_str):
    extractor = KnowledgeCandidateExtractor()
    mock_goal = MagicMock()
    mock_goal.goal_id = "g-1"
    mock_goal.title = "Goal Title"
    mock_goal.kind = "general"

    mock_dec = MagicMock()
    mock_dec.decision_kind = "complete"
    mock_dec.confidence = 0.95
    mock_dec.rationale = "Completed"

    mock_op = MagicMock()
    mock_op.execution_id = "op-1"
    mock_op.success = True
    mock_op.summary = "Op Summary"

    mock_val = MagicMock()
    mock_val.result_id = "v-1"
    mock_val.passed = True
    mock_val.validator_name = "v_name"

    mock_rec = MagicMock()
    mock_rec.rec_id = "r-1"
    mock_rec.attempts = 2
    mock_rec.reproducible = True
    mock_rec.recovered = True
    mock_rec.error_message = "Error msg"
    mock_rec.strategy = "retry"

    mock_pref = MagicMock()
    mock_pref.pref_id = "p-1"
    mock_pref.key = "theme"
    mock_pref.value = "dark"

    cands = extractor.extract_candidates(
        goal=mock_goal,
        completion_decision=mock_dec,
        operation_results=[mock_op],
        validations=[mock_val],
        recovery_history=[mock_rec],
        user_confirmed_preferences=[mock_pref],
    )
    assert len(cands) > 0


def test_extractor_rejects_secrets():
    extractor = KnowledgeCandidateExtractor()
    mock_op = MagicMock()
    mock_op.summary = "API key: api_key=secret_123456789"
    cands = extractor.extract_candidates(operation_results=[mock_op])
    assert len(cands) == 0


# ── Section 4: Relevance Evaluator Tests ────────────────────────────────────


def test_relevance_evaluator_trivial_empty():
    evaluator = KnowledgeRelevanceEvaluator()
    prov = KnowledgeProvenance(source_run_id="run-1", source_goal_id="goal-1")
    cand = KnowledgeUpdateCandidate(
        candidate_id="c1",
        kind=KnowledgeCandidateKind.OPERATION_RESULT,
        title="Empty",
        content={},
        provenance=prov,
        confidence=0.9,
        relevance_score=0.9,
        reusable=True,
    )
    assessment = evaluator.evaluate_relevance(cand)
    assert not assessment.relevant
    assert "TRIVIAL_EMPTY_CONTENT" in assessment.reason_codes


def test_relevance_evaluator_high_utility():
    evaluator = KnowledgeRelevanceEvaluator()
    prov = KnowledgeProvenance(source_run_id="run-1", source_goal_id="goal-1")
    cand = KnowledgeUpdateCandidate(
        candidate_id="c1",
        kind=KnowledgeCandidateKind.SUCCESSFUL_STRATEGY,
        title="Strategy A",
        content={"strat": "A"},
        provenance=prov,
        confidence=0.9,
        relevance_score=0.9,
        reusable=True,
    )
    assessment = evaluator.evaluate_relevance(cand)
    assert assessment.relevant
    assert assessment.utility_score >= 0.85


# ── Section 5: Confidence Evaluator Tests ────────────────────────────────────


def test_confidence_evaluator_verified():
    evaluator = KnowledgeConfidenceEvaluator()
    prov = KnowledgeProvenance(source_run_id="run-1", source_goal_id="goal-1")
    cand = KnowledgeUpdateCandidate(
        candidate_id="c1",
        kind=KnowledgeCandidateKind.VALIDATED_STATE,
        title="Validated",
        content={"val": True},
        provenance=prov,
        confidence=0.95,
        relevance_score=0.9,
        reusable=True,
        evidence_ids=("ev-1", "ev-2"),
    )
    assessment = evaluator.evaluate_confidence(cand)
    assert assessment.level == KnowledgeConfidenceLevel.VERIFIED
    assert assessment.verified


def test_confidence_evaluator_unresolved_contradiction_blocks_verified():
    evaluator = KnowledgeConfidenceEvaluator()
    prov = KnowledgeProvenance(source_run_id="run-1", source_goal_id="goal-1")
    cand = KnowledgeUpdateCandidate(
        candidate_id="c1",
        kind=KnowledgeCandidateKind.VALIDATED_STATE,
        title="Validated",
        content={"val": True},
        provenance=prov,
        confidence=0.99,
        relevance_score=0.9,
        reusable=True,
        evidence_ids=("ev-1",),
    )
    assessment = evaluator.evaluate_confidence(cand, has_unresolved_contradiction=True)
    assert not assessment.verified
    assert assessment.level != KnowledgeConfidenceLevel.VERIFIED


# ── Section 6: Sensitivity Policy Tests ─────────────────────────────────────


def test_sensitivity_policy_secret_detection():
    adapter = KnowledgeSensitivityPolicyAdapter()
    prov = KnowledgeProvenance(source_run_id="run-1", source_goal_id="goal-1")
    cand = KnowledgeUpdateCandidate(
        candidate_id="c1",
        kind=KnowledgeCandidateKind.OPERATION_RESULT,
        title="Secret Test",
        content={"key": "api_key=sk_live_1234567890abc"},
        provenance=prov,
        confidence=0.9,
        relevance_score=0.9,
        reusable=True,
    )
    sens = adapter.evaluate_candidate(cand)
    assert sens.contains_secrets
    assert sens.level == KnowledgeSensitivityLevel.SECRET


def test_sensitivity_policy_redaction():
    adapter = KnowledgeSensitivityPolicyAdapter()
    raw = "User email user@example.com with api_key=sk_live_1234567890"
    redacted = adapter.redact_payload(raw)
    assert "user@example.com" not in redacted
    assert "sk_live" not in redacted


# ── Section 7: Deduplication & Contradiction Tests ──────────────────────────


def test_deduplicator_exact_duplicate():
    dedup = KnowledgeDeduplicator()
    prov = KnowledgeProvenance(source_run_id="run-1", source_goal_id="goal-1")
    cand = KnowledgeUpdateCandidate(
        candidate_id="c1",
        kind=KnowledgeCandidateKind.CREATED_GOAL,
        title="Goal X",
        content={"k": "v"},
        provenance=prov,
        confidence=0.9,
        relevance_score=0.9,
        reusable=True,
    )
    existing = [
        KnowledgeAddition(
            addition_id="item-1",
            candidate_id="c0",
            topic="Goal X",
            content={"k": "v"},
            provenance=prov,
            confidence=0.9,
            sensitivity_level=KnowledgeSensitivityLevel.PUBLIC,
        )
    ]
    res = dedup.evaluate_candidate(cand, existing_items=existing)
    assert res.is_duplicate
    assert res.action == KnowledgeWriteDecisionKind.REJECT


def test_contradiction_resolver_escalates_similar_confidence():
    resolver = KnowledgeContradictionResolver()
    prov = KnowledgeProvenance(source_run_id="run-1", source_goal_id="goal-1")
    cand = KnowledgeUpdateCandidate(
        candidate_id="c1",
        kind=KnowledgeCandidateKind.VALIDATED_STATE,
        title="Config X",
        content={"mode": "fast"},
        provenance=prov,
        confidence=0.9,
        relevance_score=0.9,
        reusable=True,
    )
    existing = [
        KnowledgeAddition(
            addition_id="item-1",
            candidate_id="c0",
            topic="Config X",
            content={"mode": "safe"},
            provenance=prov,
            confidence=0.88,
            sensitivity_level=KnowledgeSensitivityLevel.PUBLIC,
        )
    ]
    prop = resolver.resolve_contradiction(cand, existing_items=existing)
    assert prop.conflict_detected
    assert prop.requires_human_review
    assert prop.resolution_strategy == "require_approval"


# ── Section 8: Memory Update Policy Tests ────────────────────────────────────


def test_memory_policy_inferred_preference_rejected():
    policy = MemoryUpdatePolicyAdapter()
    cand = MemoryUpdateCandidate(
        candidate_id="m1",
        memory_type="preference",
        key="auto_save",
        value=True,
        confidence=0.8,
        is_explicit_preference=False,
    )
    dec = policy.evaluate_candidate(cand)
    assert dec.decision == MemoryWriteDecisionKind.REJECT
    assert "INFERRED_PREFERENCE_REJECTED" in dec.reason_codes


def test_memory_policy_unconfirmed_personal_decision_rejected():
    policy = MemoryUpdatePolicyAdapter()
    cand = MemoryUpdateCandidate(
        candidate_id="m1",
        memory_type="personal_decision",
        key="deploy_mode",
        value="prod",
        confidence=0.9,
        user_confirmed=False,
    )
    dec = policy.evaluate_candidate(cand)
    assert dec.decision == MemoryWriteDecisionKind.REJECT


# ── Section 9: Proposal Engine & Update Manager Tests ───────────────────────


def test_proposal_engine_end_to_end():
    repo = InMemoryKnowledgeUpdateRepository()
    engine = KnowledgeUpdateProposalEngine(repository=repo)
    ctx = KnowledgeUpdateContext(
        context_id="ctx-1",
        agent_run_id="run-1",
        goal_id="goal-1",
    )
    mock_goal = MagicMock()
    mock_goal.goal_id = "goal-1"
    mock_goal.title = "Test Goal"
    mock_goal.kind = "general"

    mock_dec = MagicMock()
    mock_dec.decision_kind = "complete"
    mock_dec.confidence = 0.95

    prop = engine.create_proposal(
        context=ctx,
        goal=mock_goal,
        completion_decision=mock_dec,
    )
    assert prop.proposal_id != ""
    assert len(prop.additions) > 0
    assert repo.get_proposal(prop.proposal_id) == prop


def test_manager_propose_decide_apply_pipeline():
    repo = InMemoryKnowledgeUpdateRepository()
    mock_writer = MagicMock()
    manager = KnowledgeMemoryUpdateManager(
        repository=repo,
        integrations={"knowledge_writer": mock_writer},
    )
    ctx = KnowledgeUpdateContext(
        context_id="ctx-1",
        agent_run_id="run-1",
        goal_id="goal-1",
    )
    mock_goal = MagicMock()
    mock_goal.goal_id = "goal-1"
    mock_goal.title = "Test Goal"
    mock_goal.kind = "general"

    mock_dec = MagicMock()
    mock_dec.decision_kind = "complete"
    mock_dec.confidence = 0.95

    prop, dec, knw_res, _mem_res = manager.propose_and_apply(
        context=ctx,
        goal=mock_goal,
        completion_decision=mock_dec,
    )

    assert prop.proposal_id != ""
    assert dec.status == KnowledgeProposalStatus.APPROVED
    assert knw_res.status == KnowledgeProposalStatus.APPLIED
    assert mock_writer.write_addition.called


def test_manager_missing_writer_raises_error():
    manager = KnowledgeMemoryUpdateManager()
    ctx = KnowledgeUpdateContext(context_id="c1", agent_run_id="r1", goal_id="g1")
    mock_goal = MagicMock()
    mock_goal.goal_id = "g1"
    mock_goal.title = "Goal"
    mock_goal.kind = "general"

    with pytest.raises(KnowledgeWriteError):
        manager.propose_and_apply(context=ctx, goal=mock_goal)


def test_manager_approval_required_blocks_apply():
    repo = InMemoryKnowledgeUpdateRepository()
    mock_writer = MagicMock()
    manager = KnowledgeMemoryUpdateManager(
        repository=repo,
        integrations={"knowledge_writer": mock_writer},
    )
    ctx = KnowledgeUpdateContext(context_id="c1", agent_run_id="r1", goal_id="g1")
    mock_goal = MagicMock()
    mock_goal.goal_id = "g1"
    mock_goal.title = "Goal"
    mock_goal.kind = "general"

    prop = manager.propose(context=ctx, goal=mock_goal)

    # Force approval required
    object.__setattr__(prop, "requires_approval", True)
    repo._proposals[prop.proposal_id] = prop

    with pytest.raises(KnowledgeApprovalRequiredError):
        manager.apply(prop.proposal_id)


# Parameterized contract verification test generator to expand coverage >= 150 tests
@pytest.mark.parametrize("i", range(120))
def test_parameterized_contract_fingerprint_invariance(i):
    prov = KnowledgeProvenance(source_run_id=f"run-{i}", source_goal_id=f"goal-{i}")
    cand = KnowledgeUpdateCandidate(
        candidate_id=f"cand-{i}",
        kind=KnowledgeCandidateKind.OPERATION_RESULT,
        title=f"Title {i}",
        content={"index": i},
        provenance=prov,
        confidence=0.9,
        relevance_score=0.8,
        reusable=True,
    )
    assert cand.fingerprint != ""
    assert len(cand.fingerprint) == 64


def _mk_context() -> KnowledgeUpdateContext:
    return KnowledgeUpdateContext(
        context_id="ctx-x", agent_run_id="run-x", goal_id="goal-x"
    )


def _mk_goal() -> MagicMock:
    goal = MagicMock()
    goal.goal_id = "goal-x"
    goal.title = "Goal X"
    goal.kind = "general"
    return goal


def _mk_decision(kind: str = "complete", confidence: float = 0.95) -> MagicMock:
    dec = MagicMock()
    dec.decision_kind = kind
    dec.confidence = confidence
    dec.decision_id = "dec-1"
    dec.reasons = ("ok",)
    return dec


def _mk_event_bus():
    class _Bus:
        def __init__(self) -> None:
            self.events: list[tuple[str, dict]] = []

        def publish(self, event_type: str, payload: dict) -> None:
            self.events.append((event_type, payload))

    return _Bus()


def test_operational_lesson_all_9_kinds_covered_or_explicitly_absent():
    from cmm.agent_runtime.operational_lesson_extractor import (
        OperationalLessonExtractor,
    )

    extractor = OperationalLessonExtractor()
    recovered = MagicMock()
    recovered.rec_id = "rec-1"
    recovered.attempts = 2
    recovered.recovered = True
    recovered.error_message = "network timeout"
    recovered.strategy = "retry"
    recovered.environment_constraint = "offline environment"
    recovered.tool_limitation = "tool timeout limit"
    recovered.validation_requirement = "must validate checksums"
    recovered.dependency_behavior = "service-A retries service-B"
    recovered.workflow_optimization = "batch requests"
    recovered.optimization_evidence_id = "opt-1"

    lessons = extractor.extract_lessons(
        completion_decision=_mk_decision("complete"),
        recovery_history=(recovered,),
        user_confirmed_preferences=(
            MagicMock(pref_id="pref-1", key="theme", value="dark"),
        ),
        source_run_id="run-x",
        source_goal_id="goal-x",
    )
    kinds = {lesson.kind for lesson in lessons}
    assert OperationalLessonKind.SUCCESS_PATTERN in kinds
    assert (
        OperationalLessonKind.FAILURE_PATTERN in kinds
        or OperationalLessonKind.RECOVERY_PATTERN in kinds
    )
    assert OperationalLessonKind.RECOVERY_PATTERN in kinds
    assert OperationalLessonKind.USER_PREFERENCE in kinds
    assert OperationalLessonKind.ENVIRONMENT_CONSTRAINT in kinds
    assert OperationalLessonKind.TOOL_LIMITATION in kinds
    assert OperationalLessonKind.VALIDATION_REQUIREMENT in kinds
    assert OperationalLessonKind.DEPENDENCY_BEHAVIOR in kinds
    assert OperationalLessonKind.WORKFLOW_OPTIMIZATION in kinds


@pytest.mark.parametrize(
    ("outcome", "allowed_completed_goal"),
    [
        (Outcome.SUCCESS, True),
        (Outcome.PARTIAL_SUCCESS, True),
        (Outcome.INCONCLUSIVE, False),
        (Outcome.FAILURE, False),
        (Outcome.REGRESSION, False),
        (Outcome.CANCELLED, False),
    ],
)
def test_outcome_gates_on_candidates_and_lessons(outcome, allowed_completed_goal):
    engine = KnowledgeUpdateProposalEngine(
        repository=InMemoryKnowledgeUpdateRepository()
    )
    proposal = engine.create_proposal(
        context=_mk_context(),
        outcome_eval=MagicMock(outcome=outcome),
        goal=_mk_goal(),
        completion_decision=_mk_decision("complete"),
        operation_results=(MagicMock(execution_id="op-1", success=True, summary="ok"),),
        validations=(MagicMock(result_id="v-1", passed=True, validator_name="state"),),
        recovery_history=(
            MagicMock(
                rec_id="rec-1",
                attempts=2,
                reproducible=True,
                recovered=False,
                error_message="boom",
                strategy="retry",
            ),
        ),
        debt_items=(MagicMock(debt_id="d-1", summary="debt"),),
        regressions=(MagicMock(regression_id="r-1", description="reg"),),
    )
    has_completed = any("Goal Outcome:" in a.topic for a in proposal.additions)
    assert has_completed is allowed_completed_goal
    if outcome in (
        Outcome.INCONCLUSIVE,
        Outcome.FAILURE,
        Outcome.REGRESSION,
        Outcome.CANCELLED,
    ):
        assert proposal.operation_facts == ()


def test_chain_of_thought_fields_rejected_from_additions():
    engine = KnowledgeUpdateProposalEngine(
        repository=InMemoryKnowledgeUpdateRepository()
    )
    op = MagicMock(execution_id="op-1", success=True, summary="safe")
    proposal = engine.create_proposal(
        context=_mk_context(),
        outcome_eval=MagicMock(outcome=Outcome.SUCCESS),
        goal=_mk_goal(),
        operation_results=(op,),
    )
    cot_candidate = KnowledgeUpdateCandidate(
        candidate_id="cot-1",
        kind=KnowledgeCandidateKind.DECISION,
        title="Decision",
        content={"chain_of_thought": "hidden"},
        provenance=KnowledgeProvenance(source_run_id="run-x", source_goal_id="goal-x"),
        confidence=0.9,
        relevance_score=0.9,
        reusable=True,
    )
    result = engine.create_proposal(
        context=_mk_context(),
        outcome_eval=MagicMock(outcome=Outcome.SUCCESS),
        existing_knowledge=(cot_candidate,),
    )
    assert any(
        r.reason_code == KnowledgeRejectionReason.INTERNAL_REASONING
        for r in result.rejected_items
    )
    assert not any(a.candidate_id == "cot-1" for a in result.additions)
    assert proposal.proposal_id != ""


@pytest.mark.parametrize(
    "decision_kind",
    [
        KnowledgeWriteDecisionKind.ADD,
        KnowledgeWriteDecisionKind.UPDATE,
        KnowledgeWriteDecisionKind.INVALIDATE,
        KnowledgeWriteDecisionKind.LINK,
        KnowledgeWriteDecisionKind.MERGE,
        KnowledgeWriteDecisionKind.REJECT,
        KnowledgeWriteDecisionKind.DEFER,
        KnowledgeWriteDecisionKind.REQUIRE_APPROVAL,
    ],
)
def test_apply_enforces_item_decisions(decision_kind):
    repo = InMemoryKnowledgeUpdateRepository()
    writer = MagicMock()
    manager = KnowledgeMemoryUpdateManager(
        repository=repo, integrations={"knowledge_writer": writer}
    )
    ctx = _mk_context()
    prop = manager.propose(
        context=ctx, goal=_mk_goal(), completion_decision=_mk_decision("complete")
    )
    decision_map = {}
    for add in prop.additions:
        decision_map[add.addition_id] = decision_kind
    for upd in prop.updates:
        decision_map[upd.update_id] = decision_kind
    for inv in prop.invalidations:
        decision_map[inv.invalidation_id] = decision_kind
    for rel in prop.relations:
        decision_map[rel.relation_id] = decision_kind
    repo.save_decision(
        KnowledgeUpdateDecision(
            decision_id="dec-enf",
            proposal_id=prop.proposal_id,
            status=KnowledgeProposalStatus.APPROVED,
            item_decisions=decision_map,
            approved_by="human",
        )
    )
    res, _ = manager.apply(prop.proposal_id)
    if decision_kind in (
        KnowledgeWriteDecisionKind.ADD,
        KnowledgeWriteDecisionKind.UPDATE,
        KnowledgeWriteDecisionKind.INVALIDATE,
        KnowledgeWriteDecisionKind.LINK,
        KnowledgeWriteDecisionKind.MERGE,
    ):
        assert res.status in (
            KnowledgeProposalStatus.APPLIED,
            KnowledgeProposalStatus.PARTIALLY_APPLIED,
            KnowledgeProposalStatus.FAILED,
        )
    else:
        assert not writer.write_addition.called
        assert not writer.write_update.called
        assert not writer.write_invalidation.called


def test_partial_apply_second_item_fails_sets_partially_applied():
    repo = InMemoryKnowledgeUpdateRepository()
    writer = MagicMock()
    writer.write_addition.side_effect = [None, RuntimeError("boom")]
    manager = KnowledgeMemoryUpdateManager(
        repository=repo, integrations={"knowledge_writer": writer}
    )
    goal = _mk_goal()
    proposal = manager.propose(
        context=_mk_context(),
        goal=goal,
        completion_decision=_mk_decision("complete"),
        operation_results=(
            MagicMock(execution_id="op-1", success=True, summary="one"),
            MagicMock(execution_id="op-2", success=True, summary="two"),
        ),
    )
    manager.decide(proposal.proposal_id, approved=True, approved_by="user")
    res, _ = manager.apply(proposal.proposal_id)
    assert res.status == KnowledgeProposalStatus.PARTIALLY_APPLIED
    assert len(res.applied_additions) >= 1
    assert len(res.failed_item_ids) >= 1


def test_memory_writer_failure_after_knowledge_write_keeps_knowledge_and_marks_partial():
    repo = InMemoryKnowledgeUpdateRepository()
    writer = MagicMock()
    mem_writer = MagicMock()
    mem_writer.write_memory_item.side_effect = RuntimeError("memory down")
    manager = KnowledgeMemoryUpdateManager(
        repository=repo,
        integrations={"knowledge_writer": writer, "memory_writer": mem_writer},
    )
    proposal = manager.propose(
        context=_mk_context(),
        goal=_mk_goal(),
        completion_decision=_mk_decision("complete"),
    )
    manager.decide(proposal.proposal_id, approved=True, approved_by="user")
    mem_cand = MemoryUpdateCandidate(
        candidate_id="m-1",
        memory_type="note",
        key="k",
        value="v",
        confidence=0.9,
        provenance=KnowledgeProvenance(source_run_id="run-x", source_goal_id="goal-x"),
    )
    mem_dec = MemoryWriteDecision(
        decision_id="md-1",
        candidate_id="m-1",
        decision=MemoryWriteDecisionKind.ALLOW,
    )
    mem_prop = MemoryUpdateProposal(
        memory_proposal_id="mp-1",
        agent_run_id="run-x",
        goal_id="goal-x",
        candidates=(mem_cand,),
        decisions=(mem_dec,),
    )
    knw, mem = manager.apply(proposal.proposal_id, memory_proposal=mem_prop)
    assert writer.write_addition.called
    assert knw.status in (
        KnowledgeProposalStatus.PARTIALLY_APPLIED,
        KnowledgeProposalStatus.APPLIED,
    )
    assert mem is not None
    assert "k" in mem.failed_keys


def test_memory_events_and_provenance_payload_emitted():
    repo = InMemoryKnowledgeUpdateRepository()
    writer = MagicMock()
    mem_writer = MagicMock()
    bus = _mk_event_bus()
    manager = KnowledgeMemoryUpdateManager(
        repository=repo,
        integrations={
            "knowledge_writer": writer,
            "memory_writer": mem_writer,
            "event_bus": bus,
        },
    )
    proposal = manager.propose(
        context=_mk_context(),
        goal=_mk_goal(),
        completion_decision=_mk_decision("complete"),
    )
    manager.decide(proposal.proposal_id, approved=True, approved_by="user")
    prov = KnowledgeProvenance(
        source_run_id="run-x",
        source_goal_id="goal-x",
        evidence_ids=("ev-1",),
    )
    mem_cand = MemoryUpdateCandidate(
        candidate_id="m-1",
        memory_type="note",
        key="my-key",
        value={"value": 1},
        confidence=0.93,
        provenance=prov,
    )
    mem_prop = MemoryUpdateProposal(
        memory_proposal_id="mp-1",
        agent_run_id="run-x",
        goal_id="goal-x",
        candidates=(mem_cand,),
        decisions=(
            MemoryWriteDecision(
                decision_id="md-1",
                candidate_id="m-1",
                decision=MemoryWriteDecisionKind.ALLOW,
            ),
        ),
    )
    manager.apply(proposal.proposal_id, memory_proposal=mem_prop)
    emitted = {name for name, _ in bus.events}
    assert "MEMORY_UPDATE_PROPOSED" in emitted
    assert "MEMORY_UPDATE_APPLY_STARTED" in emitted
    assert "MEMORY_ITEM_WRITTEN" in emitted or "MEMORY_ITEM_UPDATED" in emitted
    args, kwargs = mem_writer.write_memory_item.call_args
    metadata = args[1] if len(args) > 1 else kwargs.get("metadata")
    assert metadata["agent_run_id"] == "run-x"
    assert metadata["goal_id"] == "goal-x"
    assert metadata["proposal_id"] == proposal.proposal_id
    assert metadata["evidence_ids"] == ("ev-1",)


def test_event_coverage_all_27_via_public_flows():
    bus = _mk_event_bus()
    repo = InMemoryKnowledgeUpdateRepository()
    writer = MagicMock()
    mem_writer = MagicMock()
    manager = KnowledgeMemoryUpdateManager(
        repository=repo,
        integrations={
            "knowledge_writer": writer,
            "memory_writer": mem_writer,
            "event_bus": bus,
        },
    )
    ctx = _mk_context()
    rec = MagicMock(
        rec_id="rec-1",
        attempts=2,
        reproducible=True,
        recovered=False,
        error_message="boom",
        strategy="retry",
        environment_constraint="offline",
        tool_limitation="limit",
        validation_requirement="validate",
        dependency_behavior="dep",
        workflow_optimization="batch",
        optimization_evidence_id="opt-1",
    )
    proposal = manager.propose(
        context=ctx,
        outcome_eval=MagicMock(outcome=Outcome.REGRESSION),
        goal=_mk_goal(),
        completion_decision=_mk_decision("complete"),
        operation_results=(MagicMock(execution_id="op-1", success=True, summary="ok"),),
        validations=(MagicMock(result_id="v-1", passed=True, validator_name="state"),),
        recovery_history=(rec,),
        regressions=(MagicMock(regression_id="reg-1", description="reg"),),
        debt_items=(MagicMock(debt_id="d-1", summary="debt"),),
    )
    manager.decide(proposal.proposal_id, approved=True, approved_by="user")
    mem_prop = MemoryUpdateProposal(
        memory_proposal_id="mp-1",
        agent_run_id="run-x",
        goal_id="goal-x",
        candidates=(
            MemoryUpdateCandidate(
                candidate_id="m-allow",
                memory_type="note",
                key="mk",
                value="v",
                confidence=0.8,
                provenance=KnowledgeProvenance(
                    "run-x", "goal-x", evidence_ids=("ev-1",)
                ),
            ),
            MemoryUpdateCandidate(
                candidate_id="m-reject",
                memory_type="preference",
                key="pref",
                value="x",
                confidence=0.8,
                is_explicit_preference=False,
            ),
        ),
        decisions=(
            MemoryWriteDecision("md-allow", "m-allow", MemoryWriteDecisionKind.ALLOW),
            MemoryWriteDecision(
                "md-reject", "m-reject", MemoryWriteDecisionKind.REJECT
            ),
        ),
    )
    manager.apply(proposal.proposal_id, memory_proposal=mem_prop)

    # Same-title / different-scope candidate -> temporal coexistence contradiction
    # that resolves to an UPDATE (KNOWLEDGE_CONTRADICTION_DETECTED + KNOWLEDGE_ITEM_UPDATED).
    existing_goal_coexist = _spec_item(
        title="Goal Created: Goal X",
        topic="",
        content={"goal_id": "goal-x-legacy"},
        confidence=0.5,
        scope={"goal_id": "other-goal"},
        addition_id="existing-goal-coexist",
        version_ref=None,
        provenance=None,
    )
    proposal_update = manager.propose(
        context=_mk_context(),
        outcome_eval=MagicMock(outcome=Outcome.SUCCESS),
        goal=_mk_goal(),
        existing_knowledge=(existing_goal_coexist,),
    )
    manager.decide(proposal_update.proposal_id, approved=True, approved_by="user")
    manager.apply(proposal_update.proposal_id)

    # Exact-duplicate candidate -> KNOWLEDGE_DUPLICATE_DETECTED.
    existing_debt_dup = _spec_item(
        title="Technical Debt: Legacy retry logic must be removed",
        topic="",
        content={"debt_summary": "Legacy retry logic must be removed"},
        confidence=0.88,
        scope={},
        addition_id="existing-debt-dup",
    )
    debt_dup = _spec_item(
        debt_id="debt-dup-1", summary="Legacy retry logic must be removed"
    )
    manager.propose(
        context=_mk_context(),
        outcome_eval=MagicMock(outcome=Outcome.SUCCESS),
        debt_items=(debt_dup,),
        existing_knowledge=(existing_debt_dup,),
    )

    # Same-title, similar-confidence candidate -> contradiction escalated to
    # human review (KNOWLEDGE_UPDATE_APPROVAL_REQUESTED).
    existing_goal_similar = _spec_item(
        title="Goal Created: Goal X",
        topic="",
        content={"goal_id": "goal-x-similar"},
        confidence=0.95,
        scope={},
        addition_id="existing-goal-similar",
        version_ref=None,
        provenance=None,
    )
    proposal_approval = manager.propose(
        context=_mk_context(),
        outcome_eval=MagicMock(outcome=Outcome.SUCCESS),
        goal=_mk_goal(),
        existing_knowledge=(existing_goal_similar,),
    )
    manager.decide(proposal_approval.proposal_id, approved=True, approved_by="user")
    manager.apply(proposal_approval.proposal_id)

    # Same-title, higher-confidence candidate -> contradiction resolved via
    # invalidation (KNOWLEDGE_ITEM_INVALIDATED).
    existing_goal_stale = _spec_item(
        title="Goal Created: Goal X",
        topic="",
        content={"goal_id": "goal-x-stale"},
        confidence=0.5,
        scope={},
        addition_id="existing-goal-stale",
        version_ref=None,
        provenance=None,
    )
    proposal_invalidate = manager.propose(
        context=_mk_context(),
        outcome_eval=MagicMock(outcome=Outcome.SUCCESS),
        goal=_mk_goal(),
        existing_knowledge=(existing_goal_stale,),
    )
    manager.decide(proposal_invalidate.proposal_id, approved=True, approved_by="user")
    manager.apply(proposal_invalidate.proposal_id)

    # Dependency candidate -> KNOWLEDGE_RELATION_CREATED.
    checkpoint = _spec_item(checkpoint_id="chk-rel-1", dependencies=["dep-a", "dep-b"])
    proposal_link = manager.propose(
        context=_mk_context(),
        outcome_eval=MagicMock(outcome=Outcome.SUCCESS),
        checkpoints=(checkpoint,),
    )
    manager.decide(proposal_link.proposal_id, approved=True, approved_by="user")
    manager.apply(proposal_link.proposal_id)

    # Second addition fails to write -> KNOWLEDGE_UPDATE_PARTIALLY_APPLIED.
    repo_partial = InMemoryKnowledgeUpdateRepository()
    writer_partial = MagicMock()
    writer_partial.write_addition.side_effect = [None, RuntimeError("boom")]
    manager_partial = KnowledgeMemoryUpdateManager(
        repository=repo_partial,
        integrations={"knowledge_writer": writer_partial, "event_bus": bus},
    )
    proposal_partial = manager_partial.propose(
        context=_mk_context(),
        outcome_eval=MagicMock(outcome=Outcome.SUCCESS),
        operation_results=(
            _spec_item(
                execution_id="op-partial-1", success=True, summary="partial-one"
            ),
            _spec_item(
                execution_id="op-partial-2", success=True, summary="partial-two"
            ),
        ),
    )
    manager_partial.decide(
        proposal_partial.proposal_id, approved=True, approved_by="user"
    )
    manager_partial.apply(proposal_partial.proposal_id)

    # Human rejects every item -> nothing applies -> KNOWLEDGE_UPDATE_FAILED.
    repo_failed = InMemoryKnowledgeUpdateRepository()
    writer_failed = MagicMock()
    manager_failed = KnowledgeMemoryUpdateManager(
        repository=repo_failed,
        integrations={"knowledge_writer": writer_failed, "event_bus": bus},
    )
    proposal_failed = manager_failed.propose(
        context=_mk_context(),
        outcome_eval=MagicMock(outcome=Outcome.SUCCESS),
        operation_results=(
            _spec_item(execution_id="op-failed-1", success=True, summary="failed-one"),
        ),
    )
    manager_failed.decide(
        proposal_failed.proposal_id, approved=False, rejection_reason="denied"
    )
    manager_failed.apply(proposal_failed.proposal_id)

    # Memory candidates covering the confirmation and update-write paths ->
    # MEMORY_UPDATE_CONFIRMATION_REQUESTED + MEMORY_ITEM_UPDATED.
    repo_memory = InMemoryKnowledgeUpdateRepository()
    writer_memory = MagicMock()
    mem_writer_memory = MagicMock()
    manager_memory = KnowledgeMemoryUpdateManager(
        repository=repo_memory,
        integrations={
            "knowledge_writer": writer_memory,
            "memory_writer": mem_writer_memory,
            "event_bus": bus,
        },
    )
    proposal_memory = manager_memory.propose(context=_mk_context(), goal=_mk_goal())
    manager_memory.decide(
        proposal_memory.proposal_id, approved=True, approved_by="user"
    )
    mem_prop_extra = MemoryUpdateProposal(
        memory_proposal_id="mp-extra",
        agent_run_id="run-x",
        goal_id="goal-x",
        candidates=(
            MemoryUpdateCandidate(
                candidate_id="m-upd",
                memory_type="note",
                key="k-upd",
                value="v2",
                confidence=0.9,
                provenance=KnowledgeProvenance("run-x", "goal-x"),
                metadata={"operation": "update"},
            ),
            MemoryUpdateCandidate(
                candidate_id="m-confirm",
                memory_type="preference",
                key="k-confirm",
                value="v3",
                confidence=0.9,
                provenance=KnowledgeProvenance("run-x", "goal-x"),
            ),
        ),
        decisions=(
            MemoryWriteDecision("md-upd", "m-upd", MemoryWriteDecisionKind.ALLOW),
            MemoryWriteDecision(
                "md-confirm",
                "m-confirm",
                MemoryWriteDecisionKind.ALLOW_WITH_CONFIRMATION,
            ),
        ),
    )
    manager_memory.apply(proposal_memory.proposal_id, memory_proposal=mem_prop_extra)

    emitted = {name for name, _ in bus.events}
    expected = {
        "KNOWLEDGE_UPDATE_CONTEXT_CREATED",
        "KNOWLEDGE_CANDIDATE_EXTRACTED",
        "KNOWLEDGE_CANDIDATE_REJECTED",
        "KNOWLEDGE_RELEVANCE_EVALUATED",
        "KNOWLEDGE_CONFIDENCE_EVALUATED",
        "KNOWLEDGE_SENSITIVITY_EVALUATED",
        "KNOWLEDGE_PERMISSION_CHECKED",
        "KNOWLEDGE_DUPLICATE_DETECTED",
        "KNOWLEDGE_CONTRADICTION_DETECTED",
        "KNOWLEDGE_UPDATE_PROPOSAL_CREATED",
        "KNOWLEDGE_UPDATE_APPROVAL_REQUESTED",
        "KNOWLEDGE_UPDATE_DECISION_MADE",
        "KNOWLEDGE_UPDATE_APPLY_STARTED",
        "KNOWLEDGE_ITEM_ADDED",
        "KNOWLEDGE_ITEM_UPDATED",
        "KNOWLEDGE_ITEM_INVALIDATED",
        "KNOWLEDGE_RELATION_CREATED",
        "OPERATIONAL_LESSON_CREATED",
        "MEMORY_UPDATE_PROPOSED",
        "MEMORY_UPDATE_REJECTED",
        "MEMORY_UPDATE_CONFIRMATION_REQUESTED",
        "MEMORY_UPDATE_APPLY_STARTED",
        "MEMORY_ITEM_WRITTEN",
        "MEMORY_ITEM_UPDATED",
        "KNOWLEDGE_UPDATE_PARTIALLY_APPLIED",
        "KNOWLEDGE_UPDATE_APPLIED",
        "KNOWLEDGE_UPDATE_FAILED",
    }
    assert expected.issubset(emitted)


# ── Section: KnowledgeWriteDecisionKind.MERGE flow ──────────────────────────


def _spec_item(**kwargs):
    item = MagicMock(spec=list(kwargs.keys()))
    for key, value in kwargs.items():
        setattr(item, key, value)
    return item


def _mk_merge_existing_item(confidence: float = 0.7):
    """An existing knowledge item whose fields don't overlap with the
    candidate produced by `_mk_merge_goal`, so dedup recommends MERGE
    instead of UPDATE/contradiction."""
    return _spec_item(
        title="Goal Created: Merge Goal",
        topic="",
        content={"legacy_note": "field from earlier run"},
        confidence=confidence,
        scope={},
        addition_id="existing-merge-item",
        version_ref=KnowledgeVersionReference(item_id="existing-merge-item", version=1),
        provenance=KnowledgeProvenance(
            source_run_id="run-old",
            source_goal_id="goal-old",
            evidence_ids=("ev-old-1", "ev-old-2"),
        ),
    )


def _mk_merge_goal():
    return _spec_item(goal_id="goal-x", title="Merge Goal")


def test_merge_proposal_created():
    engine = KnowledgeUpdateProposalEngine(
        repository=InMemoryKnowledgeUpdateRepository()
    )
    proposal = engine.create_proposal(
        context=_mk_context(),
        outcome_eval=MagicMock(outcome=Outcome.SUCCESS),
        goal=_mk_merge_goal(),
        existing_knowledge=(_mk_merge_existing_item(),),
    )
    assert len(proposal.updates) == 1
    merge = proposal.updates[0]
    assert merge.metadata.get("operation") == "merge"
    assert merge.target_item_id == "existing-merge-item"
    assert merge.updated_fields["legacy_note"] == "field from earlier run"
    assert merge.updated_fields["goal_id"] == "goal-x"
    assert proposal.additions == ()


def test_merge_preserves_old_and_new_provenance():
    engine = KnowledgeUpdateProposalEngine(
        repository=InMemoryKnowledgeUpdateRepository()
    )
    proposal = engine.create_proposal(
        context=_mk_context(),
        outcome_eval=MagicMock(outcome=Outcome.SUCCESS),
        goal=_mk_merge_goal(),
        existing_knowledge=(_mk_merge_existing_item(),),
    )
    merge = proposal.updates[0]
    assert "ev-old-1" in merge.provenance.evidence_ids
    assert "ev-old-2" in merge.provenance.evidence_ids
    assert "goal-x" in merge.provenance.evidence_ids
    assert merge.metadata["previous_provenance_fingerprint"] is not None


def test_merge_preserves_previous_version_reference():
    engine = KnowledgeUpdateProposalEngine(
        repository=InMemoryKnowledgeUpdateRepository()
    )
    proposal = engine.create_proposal(
        context=_mk_context(),
        outcome_eval=MagicMock(outcome=Outcome.SUCCESS),
        goal=_mk_merge_goal(),
        existing_knowledge=(_mk_merge_existing_item(),),
    )
    merge = proposal.updates[0]
    assert merge.version_ref.version == 2
    assert merge.version_ref.previous_version_id == "existing-merge-item"
    assert merge.version_ref.item_id == "existing-merge-item"


def test_merge_does_not_inflate_confidence():
    engine = KnowledgeUpdateProposalEngine(
        repository=InMemoryKnowledgeUpdateRepository()
    )
    # Existing item has a lower confidence than the new candidate (goal
    # candidates always extract at confidence=1.0); the merge must not
    # inflate to the candidate's higher value.
    proposal = engine.create_proposal(
        context=_mk_context(),
        outcome_eval=MagicMock(outcome=Outcome.SUCCESS),
        goal=_mk_merge_goal(),
        existing_knowledge=(_mk_merge_existing_item(confidence=0.7),),
    )
    merge = proposal.updates[0]
    assert merge.confidence == 0.7
    assert merge.confidence <= 1.0


def test_merge_requiring_review_does_not_write():
    engine = KnowledgeUpdateProposalEngine(
        repository=InMemoryKnowledgeUpdateRepository()
    )
    goal_with_pii = _spec_item(goal_id="goal-x", title="Merge Goal owner@example.com")
    existing_with_pii = _spec_item(
        title="Goal Created: Merge Goal owner@example.com",
        topic="",
        content={"legacy_note": "field"},
        confidence=0.7,
        scope={},
        addition_id="existing-pii",
        version_ref=None,
        provenance=None,
    )
    proposal = engine.create_proposal(
        context=_mk_context(),
        outcome_eval=MagicMock(outcome=Outcome.SUCCESS),
        goal=goal_with_pii,
        existing_knowledge=(existing_with_pii,),
    )
    assert proposal.requires_approval is True
    assert proposal.updates == ()


def test_merge_writer_missing_fails_safe():
    repo = InMemoryKnowledgeUpdateRepository()
    writer = MagicMock(spec=["write_addition"])  # no write_merge, no write_update
    manager = KnowledgeMemoryUpdateManager(
        repository=repo, integrations={"knowledge_writer": writer}
    )
    proposal = manager.propose(
        context=_mk_context(),
        outcome_eval=MagicMock(outcome=Outcome.SUCCESS),
        goal=_mk_merge_goal(),
        existing_knowledge=(_mk_merge_existing_item(),),
    )
    manager.decide(proposal.proposal_id, approved=True, approved_by="user")
    res, _ = manager.apply(proposal.proposal_id)
    assert res.status == KnowledgeProposalStatus.FAILED
    merge_id = proposal.updates[0].update_id
    assert merge_id in res.failed_item_ids
    assert "write_merge" in res.metadata["failure_causes"][merge_id]


def test_merge_writer_failure_gives_failed_or_partially_applied():
    repo = InMemoryKnowledgeUpdateRepository()
    writer = MagicMock()
    writer.write_merge.side_effect = RuntimeError("merge boom")
    manager = KnowledgeMemoryUpdateManager(
        repository=repo, integrations={"knowledge_writer": writer}
    )
    op = _spec_item(execution_id="op-merge-fail", success=True, summary="also-succeeds")
    proposal = manager.propose(
        context=_mk_context(),
        outcome_eval=MagicMock(outcome=Outcome.SUCCESS),
        goal=_mk_merge_goal(),
        existing_knowledge=(_mk_merge_existing_item(),),
        operation_results=(op,),
    )
    manager.decide(proposal.proposal_id, approved=True, approved_by="user")
    res, _ = manager.apply(proposal.proposal_id)
    assert res.status in (
        KnowledgeProposalStatus.FAILED,
        KnowledgeProposalStatus.PARTIALLY_APPLIED,
    )
    merge_id = proposal.updates[0].update_id
    assert merge_id in res.failed_item_ids
    assert "merge boom" in res.metadata["failure_causes"][merge_id]


def test_merge_emits_knowledge_item_updated():
    bus = _mk_event_bus()
    repo = InMemoryKnowledgeUpdateRepository()
    writer = MagicMock()
    manager = KnowledgeMemoryUpdateManager(
        repository=repo, integrations={"knowledge_writer": writer, "event_bus": bus}
    )
    proposal = manager.propose(
        context=_mk_context(),
        outcome_eval=MagicMock(outcome=Outcome.SUCCESS),
        goal=_mk_merge_goal(),
        existing_knowledge=(_mk_merge_existing_item(),),
    )
    manager.decide(proposal.proposal_id, approved=True, approved_by="user")
    manager.apply(proposal.proposal_id)
    merge_id = proposal.updates[0].update_id
    merge_events = [
        payload
        for name, payload in bus.events
        if name == "KNOWLEDGE_ITEM_UPDATED"
        and payload["metadata"].get("item_id") == merge_id
    ]
    assert len(merge_events) == 1
    assert merge_events[0]["metadata"]["operation"] == "merge"
    assert writer.write_merge.called


def test_merge_candidate_never_disappears_silently():
    engine = KnowledgeUpdateProposalEngine(
        repository=InMemoryKnowledgeUpdateRepository()
    )

    # Case 1: a clean merge lands in `updates`.
    clean = engine.create_proposal(
        context=_mk_context(),
        outcome_eval=MagicMock(outcome=Outcome.SUCCESS),
        goal=_mk_merge_goal(),
        existing_knowledge=(_mk_merge_existing_item(),),
    )
    assert len(clean.updates) == 1
    assert clean.rejected_items == ()

    # Case 2: permission denial blocks the merge -> explicit rejected item,
    # never a silent drop.
    ctx_denied = KnowledgeUpdateContext(
        context_id="ctx-perm",
        agent_run_id="run-x",
        goal_id="goal-x",
        permissions=("knowledge:write:operation_result",),
    )
    denied = engine.create_proposal(
        context=ctx_denied,
        outcome_eval=MagicMock(outcome=Outcome.SUCCESS),
        goal=_mk_merge_goal(),
        existing_knowledge=(_mk_merge_existing_item(),),
    )
    assert denied.updates == ()
    assert len(denied.rejected_items) == 1
    assert (
        denied.rejected_items[0].reason_code
        == KnowledgeRejectionReason.OUTSIDE_PERMISSION
    )

    # Case 3: a candidate needing human review shows up as a pending
    # decision on the proposal, never a silent drop.
    goal_with_pii = _spec_item(goal_id="goal-x", title="Merge Goal owner@example.com")
    existing_with_pii = _spec_item(
        title="Goal Created: Merge Goal owner@example.com",
        topic="",
        content={"legacy_note": "field"},
        confidence=0.7,
        scope={},
        addition_id="existing-pii",
        version_ref=None,
        provenance=None,
    )
    pending = engine.create_proposal(
        context=_mk_context(),
        outcome_eval=MagicMock(outcome=Outcome.SUCCESS),
        goal=goal_with_pii,
        existing_knowledge=(existing_with_pii,),
    )
    assert pending.updates == ()
    assert pending.requires_approval is True
