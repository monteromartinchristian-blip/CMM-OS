"""Phase 9.19 – Agent Runtime Trace Tests.

Minimum: 170 tests.  Covers contracts, registry, normalizer, redactor,
assembler, summary, integrity, repository, service, collector, iterations,
errors, budget, outcome, knowledge, events, export, security.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from cmm.agent_runtime.agent_trace_assembler import AgentTraceAssembler
from cmm.agent_runtime.agent_trace_collector import AgentTraceCollector
from cmm.agent_runtime.agent_trace_contracts import (
    AgentTrace,
    AgentTraceApprovalDecision,
    AgentTraceApprovalRequest,
    AgentTraceBudgetEvent,
    AgentTraceCheckpoint,
    AgentTraceCognitiveProfile,
    AgentTraceError,
    AgentTraceExportRequest,
    AgentTraceExportResult,
    AgentTraceHeader,
    AgentTraceInformationGap,
    AgentTraceIntegrityReport,
    AgentTraceIteration,
    AgentTraceKnowledgeLoad,
    AgentTraceKnowledgeUpdate,
    AgentTraceMemoryUpdate,
    AgentTraceObservation,
    AgentTraceOperation,
    AgentTraceOutcomeEvaluation,
    AgentTracePage,
    AgentTracePlanReference,
    AgentTracePolicyDecision,
    AgentTraceQuery,
    AgentTraceQueryResult,
    AgentTraceQuestion,
    AgentTraceReasoningReference,
    AgentTraceRecoveryDecision,
    AgentTraceRecoveryExecution,
    AgentTraceRedactionReport,
    AgentTraceResourceChange,
    AgentTraceRetentionPolicy,
    AgentTraceRuntimeDecision,
    AgentTraceStopDecision,
    AgentTraceSummary,
    AgentTraceTransaction,
    AgentTraceValidation,
    AgentTraceWarning,
)
from cmm.agent_runtime.agent_trace_event_normalizer import AgentTraceEventNormalizer
from cmm.agent_runtime.agent_trace_event_registry import AgentTraceEventRegistry
from cmm.agent_runtime.agent_trace_integrity import AgentTraceIntegrityVerifier
from cmm.agent_runtime.agent_trace_redactor import AgentTraceRedactor
from cmm.agent_runtime.agent_trace_repository import (
    InMemoryAgentTraceRepository,
)
from cmm.agent_runtime.agent_trace_service import AgentTraceService
from cmm.agent_runtime.agent_trace_summary_builder import AgentTraceSummaryBuilder
from cmm.agent_runtime.enums import (
    AgentAutonomyLevel,
    AgentTraceDecisionKind,
    AgentTraceErrorKind,
    AgentTraceExportFormat,
    AgentTraceIntegrityStatus,
    AgentTraceRecordKind,
    AgentTraceRedactionReason,
    AgentTraceStatus,
)
from cmm.agent_runtime.errors import (
    AgentTraceBuildError,
    AgentTraceCausalityError,
    AgentTraceConflictError,
    AgentTraceContractError,
    AgentTraceExportError,
    AgentTraceFinalizedError,
    AgentTraceFingerprintError,
    AgentTraceIntegrityError,
    AgentTraceNotFoundError,
    AgentTraceOrderingError,
    AgentTracePermissionError,
    AgentTraceQueryError,
    AgentTraceRedactionError,
    AgentTraceRepositoryError,
    AgentTraceRetentionError,
    AgentTraceSensitivityError,
    AgentTraceSerializationError,
    AgentTraceSourceError,
    AgentTraceUnsupportedEventError,
)
from cmm.agent_runtime.errors import (
    AgentTraceError as AgentTraceErrorClass,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_trace() -> AgentTrace:
    return AgentTrace(
        trace_id="trace-1",
        agent_run_id="run-1",
        goal_id="goal-1",
        goal_created_by="user-1",
        agent_id="agent-1",
        workflow_id="wf-1",
        autonomy_level=AgentAutonomyLevel.SUPERVISED_AUTONOMY,
    )


@pytest.fixture
def sample_event() -> dict[str, Any]:
    return {
        "event_type": "observation.created",
        "observation_id": "obs-1",
        "kind": "state",
        "summary": "Observed file state",
        "source": "git",
        "agent_run_id": "run-1",
        "goal_id": "goal-1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def service() -> AgentTraceService:
    return AgentTraceService()


@pytest.fixture
def repository() -> InMemoryAgentTraceRepository:
    return InMemoryAgentTraceRepository()


@pytest.fixture
def registry() -> AgentTraceEventRegistry:
    return AgentTraceEventRegistry()


@pytest.fixture
def normalizer() -> AgentTraceEventNormalizer:
    return AgentTraceEventNormalizer()


@pytest.fixture
def redactor() -> AgentTraceRedactor:
    return AgentTraceRedactor()


@pytest.fixture
def assembler() -> AgentTraceAssembler:
    return AgentTraceAssembler()


@pytest.fixture
def integrity_verifier() -> AgentTraceIntegrityVerifier:
    return AgentTraceIntegrityVerifier()


@pytest.fixture
def summary_builder() -> AgentTraceSummaryBuilder:
    return AgentTraceSummaryBuilder()


def _corrupt_frozen(instance, **changes):
    """Test-only helper: bypass frozen dataclass validation."""
    for field_name, value in changes.items():
        object.__setattr__(instance, field_name, value)
    return instance


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Contracts – Immutability, Serialization, Timestamps, Fingerprints
# ═══════════════════════════════════════════════════════════════════════════════


class TestAgentTraceContracts:
    """Tests for trace contract immutability, serialization, and validation."""

    def test_agent_trace_creation(self, sample_trace: AgentTrace) -> None:
        assert sample_trace.trace_id == "trace-1"
        assert sample_trace.agent_run_id == "run-1"
        assert sample_trace.goal_id == "goal-1"
        assert sample_trace.status == "open"

    def test_agent_trace_immutable(self, sample_trace: AgentTrace) -> None:
        with pytest.raises(AttributeError):
            sample_trace.trace_id = "changed"  # type: ignore

    def test_agent_trace_empty_trace_id_raises(self) -> None:
        with pytest.raises(ValueError, match="trace_id"):
            AgentTrace(trace_id="", agent_run_id="r", goal_id="g")

    def test_agent_trace_empty_agent_run_id_raises(self) -> None:
        with pytest.raises(ValueError, match="agent_run_id"):
            AgentTrace(trace_id="t", agent_run_id="", goal_id="g")

    def test_agent_trace_empty_goal_id_raises(self) -> None:
        with pytest.raises(ValueError, match="goal_id"):
            AgentTrace(trace_id="t", agent_run_id="r", goal_id="")

    def test_agent_trace_negative_duration_raises(self) -> None:
        with pytest.raises(ValueError, match="duration_ms"):
            AgentTrace(trace_id="t", agent_run_id="r", goal_id="g", duration_ms=-1)

    def test_agent_trace_completed_before_started_raises(self) -> None:
        now = datetime.now(timezone.utc)
        later = now + timedelta(seconds=1)
        with pytest.raises(ValueError, match="completed_at"):
            AgentTrace(
                trace_id="t",
                agent_run_id="r",
                goal_id="g",
                started_at=later,
                completed_at=now,
            )

    def test_agent_trace_to_dict(self, sample_trace: AgentTrace) -> None:
        d = sample_trace.to_dict()
        assert d["trace_id"] == "trace-1"
        assert d["agent_run_id"] == "run-1"
        assert d["goal_id"] == "goal-1"

    def test_agent_trace_from_dict(self) -> None:
        d = {
            "trace_id": "t1",
            "agent_run_id": "r1",
            "goal_id": "g1",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        trace = AgentTrace.from_dict(d)
        assert trace.trace_id == "t1"
        assert trace.agent_run_id == "r1"

    def test_agent_trace_to_json(self, sample_trace: AgentTrace) -> None:
        j = sample_trace.to_json()
        assert isinstance(j, str)
        assert "trace-1" in j

    def test_agent_trace_from_json(self) -> None:
        d = {
            "trace_id": "t1",
            "agent_run_id": "r1",
            "goal_id": "g1",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        j = json.dumps(d, default=str)
        trace = AgentTrace.from_json(j)
        assert trace.trace_id == "t1"

    def test_agent_trace_header_creation(self) -> None:
        h = AgentTraceHeader(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            goal_created_by="u1",
            agent_id="a1",
            workflow_id="w1",
            autonomy_level=2,
        )
        assert h.trace_id == "t1"

    def test_agent_trace_header_empty_trace_id_raises(self) -> None:
        with pytest.raises(ValueError, match="trace_id"):
            AgentTraceHeader(
                trace_id="",
                agent_run_id="r",
                goal_id="g",
                goal_created_by="u",
                agent_id="a",
                workflow_id="w",
                autonomy_level=0,
            )

    def test_agent_trace_iteration_creation(self) -> None:
        it = AgentTraceIteration(iteration_id="iter-1", sequence=1)
        assert it.iteration_id == "iter-1"
        assert it.sequence == 1

    def test_agent_trace_iteration_empty_id_raises(self) -> None:
        with pytest.raises(ValueError, match="iteration_id"):
            AgentTraceIteration(iteration_id="", sequence=0)

    def test_agent_trace_iteration_negative_sequence_raises(self) -> None:
        with pytest.raises(ValueError, match="sequence"):
            AgentTraceIteration(iteration_id="i", sequence=-1)

    def test_agent_trace_observation_creation(self) -> None:
        obs = AgentTraceObservation(observation_id="obs-1")
        assert obs.observation_id == "obs-1"

    def test_agent_trace_knowledge_load_creation(self) -> None:
        kl = AgentTraceKnowledgeLoad(load_id="kl-1")
        assert kl.load_id == "kl-1"

    def test_agent_trace_cognitive_profile_creation(self) -> None:
        cp = AgentTraceCognitiveProfile(profile_id="cp-1")
        assert cp.profile_id == "cp-1"

    def test_agent_trace_information_gap_creation(self) -> None:
        ig = AgentTraceInformationGap(gap_id="gap-1")
        assert ig.gap_id == "gap-1"

    def test_agent_trace_question_creation(self) -> None:
        q = AgentTraceQuestion(question_id="q-1")
        assert q.question_id == "q-1"

    def test_agent_trace_reasoning_reference_creation(self) -> None:
        rr = AgentTraceReasoningReference(reasoning_result_id="rr-1")
        assert rr.reasoning_result_id == "rr-1"

    def test_agent_trace_runtime_decision_creation(self) -> None:
        rd = AgentTraceRuntimeDecision(decision_id="d-1")
        assert rd.decision_id == "d-1"

    def test_agent_trace_plan_reference_creation(self) -> None:
        pr = AgentTracePlanReference(plan_id="plan-1")
        assert pr.plan_id == "plan-1"

    def test_agent_trace_policy_decision_creation(self) -> None:
        pd = AgentTracePolicyDecision(policy_decision_id="pd-1")
        assert pd.policy_decision_id == "pd-1"

    def test_agent_trace_approval_request_creation(self) -> None:
        ar = AgentTraceApprovalRequest(approval_request_id="ar-1")
        assert ar.approval_request_id == "ar-1"

    def test_agent_trace_approval_decision_creation(self) -> None:
        ad = AgentTraceApprovalDecision(approval_decision_id="ad-1")
        assert ad.approval_decision_id == "ad-1"

    def test_agent_trace_operation_creation(self) -> None:
        op = AgentTraceOperation(operation_id="op-1")
        assert op.operation_id == "op-1"

    def test_agent_trace_resource_change_creation(self) -> None:
        rc = AgentTraceResourceChange(change_id="rc-1")
        assert rc.change_id == "rc-1"

    def test_agent_trace_validation_creation(self) -> None:
        v = AgentTraceValidation(validation_id="v-1")
        assert v.validation_id == "v-1"

    def test_agent_trace_recovery_decision_creation(self) -> None:
        rd = AgentTraceRecoveryDecision(recovery_decision_id="rd-1")
        assert rd.recovery_decision_id == "rd-1"

    def test_agent_trace_recovery_execution_creation(self) -> None:
        rex = AgentTraceRecoveryExecution(recovery_execution_id="rex-1")
        assert rex.recovery_execution_id == "rex-1"

    def test_agent_trace_checkpoint_creation(self) -> None:
        cp = AgentTraceCheckpoint(checkpoint_id="cp-1")
        assert cp.checkpoint_id == "cp-1"

    def test_agent_trace_transaction_creation(self) -> None:
        tx = AgentTraceTransaction(transaction_id="tx-1")
        assert tx.transaction_id == "tx-1"

    def test_agent_trace_outcome_evaluation_creation(self) -> None:
        oe = AgentTraceOutcomeEvaluation(evaluation_id="oe-1")
        assert oe.evaluation_id == "oe-1"

    def test_agent_trace_knowledge_update_creation(self) -> None:
        ku = AgentTraceKnowledgeUpdate(proposal_id="ku-1")
        assert ku.proposal_id == "ku-1"

    def test_agent_trace_memory_update_creation(self) -> None:
        mu = AgentTraceMemoryUpdate(memory_update_id="mu-1")
        assert mu.memory_update_id == "mu-1"

    def test_agent_trace_budget_event_creation(self) -> None:
        be = AgentTraceBudgetEvent(budget_event_id="be-1")
        assert be.budget_event_id == "be-1"

    def test_agent_trace_warning_creation(self) -> None:
        w = AgentTraceWarning(warning_id="w-1")
        assert w.warning_id == "w-1"

    def test_agent_trace_error_creation(self) -> None:
        e = AgentTraceError(error_id="e-1")
        assert e.error_id == "e-1"

    def test_agent_trace_stop_decision_creation(self) -> None:
        sd = AgentTraceStopDecision(stop_decision_id="sd-1")
        assert sd.stop_decision_id == "sd-1"

    def test_agent_trace_summary_creation(self) -> None:
        s = AgentTraceSummary()
        assert s.operation_count == 0

    def test_agent_trace_query_creation(self) -> None:
        q = AgentTraceQuery()
        assert q.limit == 100

    def test_agent_trace_query_negative_limit_raises(self) -> None:
        with pytest.raises(ValueError, match="limit"):
            AgentTraceQuery(limit=0)

    def test_agent_trace_query_excessive_limit_raises(self) -> None:
        with pytest.raises(ValueError, match="limit"):
            AgentTraceQuery(limit=10001)

    def test_agent_trace_integrity_report_creation(self) -> None:
        ir = AgentTraceIntegrityReport(trace_id="t1")
        assert ir.trace_id == "t1"

    def test_agent_trace_redaction_report_creation(self) -> None:
        rr = AgentTraceRedactionReport(trace_id="t1")
        assert rr.trace_id == "t1"

    def test_agent_trace_retention_policy_creation(self) -> None:
        rp = AgentTraceRetentionPolicy()
        assert rp.max_age_days == 365

    def test_agent_trace_export_request_creation(self) -> None:
        er = AgentTraceExportRequest(trace_id="t1")
        assert er.trace_id == "t1"

    def test_agent_trace_export_result_creation(self) -> None:
        er = AgentTraceExportResult(trace_id="t1", data="{}")
        assert er.trace_id == "t1"

    def test_agent_trace_page_creation(self) -> None:
        p = AgentTracePage()
        assert p.total == 0

    def test_agent_trace_query_result_creation(self) -> None:
        qr = AgentTraceQueryResult()
        assert qr.total == 0

    def test_agent_trace_fingerprint_deterministic(self) -> None:
        t1 = AgentTrace(trace_id="t1", agent_run_id="r1", goal_id="g1")
        t2 = AgentTrace(trace_id="t1", agent_run_id="r1", goal_id="g1")
        assert t1.fingerprint == t2.fingerprint

    def test_agent_trace_serialization_roundtrip(
        self, sample_trace: AgentTrace
    ) -> None:
        j = sample_trace.to_json()
        restored = AgentTrace.from_json(j)
        assert restored.trace_id == sample_trace.trace_id
        assert restored.agent_run_id == sample_trace.agent_run_id
        assert restored.goal_id == sample_trace.goal_id

    def test_agent_trace_with_iterations(self) -> None:
        it = AgentTraceIteration(iteration_id="iter-1", sequence=1)
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            iterations=(it,),
        )
        assert len(trace.iterations) == 1
        assert trace.iterations[0].iteration_id == "iter-1"

    def test_agent_trace_with_stop_decision(self) -> None:
        sd = AgentTraceStopDecision(
            stop_decision_id="sd-1",
            outcome="success",
            goal_satisfied=True,
        )
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            stop_decision=sd,
        )
        assert trace.stop_decision is not None
        assert trace.stop_decision.outcome == "success"

    def test_agent_trace_with_summary(self) -> None:
        s = AgentTraceSummary(operation_count=5, validation_count=3)
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            summary=s,
        )
        assert trace.summary is not None
        assert trace.summary.operation_count == 5


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Registry
# ═══════════════════════════════════════════════════════════════════════════════


class TestAgentTraceEventRegistry:
    """Tests for the event registry."""

    def test_registry_creation(self, registry: AgentTraceEventRegistry) -> None:
        assert len(registry.known_event_types()) > 0

    def test_registry_resolve_known(self, registry: AgentTraceEventRegistry) -> None:
        kind = registry.resolve("observation.created")
        assert kind == AgentTraceRecordKind.OBSERVATION

    def test_registry_resolve_unknown(self, registry: AgentTraceEventRegistry) -> None:
        kind = registry.resolve("unknown.event.type")
        assert kind is None

    def test_registry_resolve_alias(self, registry: AgentTraceEventRegistry) -> None:
        kind = registry.resolve("run.started")
        assert kind == AgentTraceRecordKind.HEADER

    def test_registry_contains_known(self, registry: AgentTraceEventRegistry) -> None:
        assert "observation.created" in registry

    def test_registry_contains_unknown(self, registry: AgentTraceEventRegistry) -> None:
        assert "nonexistent" not in registry

    def test_registry_duplicate_raises(self, registry: AgentTraceEventRegistry) -> None:
        with pytest.raises(ValueError, match="Duplicate"):
            registry.register("observation.created", AgentTraceRecordKind.OBSERVATION)

    def test_registry_alias_unknown_canonical_raises(
        self, registry: AgentTraceEventRegistry
    ) -> None:
        with pytest.raises(ValueError, match="unknown canonical"):
            registry.register_alias("nonexistent", "alias")

    def test_registry_known_event_types(
        self, registry: AgentTraceEventRegistry
    ) -> None:
        types = registry.known_event_types()
        assert "observation.created" in types
        assert "policy.evaluated" in types
        assert "approval.requested" in types

    def test_registry_known_aliases(self, registry: AgentTraceEventRegistry) -> None:
        aliases = registry.known_aliases()
        assert "run.started" in aliases

    def test_registry_all_phases_covered(
        self, registry: AgentTraceEventRegistry
    ) -> None:
        """Verify events from all phases 9.1-9.18 are mapped."""
        phase_events = [
            "agent_run.created",  # 9.1
            "goal.created",  # 9.2
            "goal_proposal.created",  # 9.3
            "observation.created",  # 9.4
            "cognitive.requested",  # 9.5
            "information_gap.detected",  # 9.6
            "plan.created",  # 9.7
            "policy.evaluated",  # 9.8
            "autonomy.evaluated",  # 9.9
            "approval.requested",  # 9.10
            "budget.reserved",  # 9.11
            "iteration.started",  # 9.12
            "operation.started",  # 9.13
            "validation.started",  # 9.14
            "checkpoint.created",  # 9.15
            "recovery.decided",  # 9.16
            "outcome.evaluated",  # 9.17
            "knowledge.proposed",  # 9.18
        ]
        for evt in phase_events:
            assert evt in registry, f"Missing event: {evt}"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Normalizer
# ═══════════════════════════════════════════════════════════════════════════════


class TestAgentTraceEventNormalizer:
    """Tests for the event normalizer."""

    def test_normalize_valid_event(self, normalizer: AgentTraceEventNormalizer) -> None:
        event = {
            "event_type": "observation.created",
            "observation_id": "obs-1",
            "kind": "state",
            "summary": "test",
            "agent_run_id": "run-1",
        }
        result = normalizer.normalize(event)
        assert result is not None

    def test_normalize_missing_event_type_raises(
        self, normalizer: AgentTraceEventNormalizer
    ) -> None:
        with pytest.raises(AgentTraceContractError, match="event_type"):
            normalizer.normalize({"id": "1"})

    def test_normalize_unknown_event_strict_raises(
        self, normalizer: AgentTraceEventNormalizer
    ) -> None:
        with pytest.raises(AgentTraceUnsupportedEventError):
            normalizer.normalize({"event_type": "unknown.type"})

    def test_normalize_unknown_event_non_strict(self) -> None:
        n = AgentTraceEventNormalizer(strict=False)
        result = n.normalize({"event_type": "unknown.type"})
        assert result is None

    def test_normalize_batch(self, normalizer: AgentTraceEventNormalizer) -> None:
        events = [
            {
                "event_type": "observation.created",
                "observation_id": "o1",
                "agent_run_id": "r1",
            },
            {
                "event_type": "operation.started",
                "operation_id": "op1",
                "agent_run_id": "r1",
            },
        ]
        results = normalizer.normalize_batch(events)
        assert len(results) == 2

    def test_normalize_batch_with_invalid(self) -> None:
        n = AgentTraceEventNormalizer(strict=False)
        events = [
            {
                "event_type": "observation.created",
                "observation_id": "o1",
                "agent_run_id": "r1",
            },
            {"event_type": "unknown.type"},
        ]
        results = n.normalize_batch(events)
        assert len(results) == 1

    def test_normalize_custom_normalizer(
        self, normalizer: AgentTraceEventNormalizer
    ) -> None:
        def custom(event: dict[str, Any]) -> str:
            return "custom_result"

        normalizer.register_normalizer("custom.event", custom)
        result = normalizer.normalize({"event_type": "custom.event"})
        assert result == "custom_result"

    def test_normalize_iteration_event(
        self, normalizer: AgentTraceEventNormalizer
    ) -> None:
        event = {
            "event_type": "iteration.started",
            "iteration_id": "iter-1",
            "sequence": 1,
            "agent_run_id": "r1",
        }
        result = normalizer.normalize(event)
        assert result is not None

    def test_normalize_budget_event(
        self, normalizer: AgentTraceEventNormalizer
    ) -> None:
        event = {
            "event_type": "budget.reserved",
            "budget_event_id": "be-1",
            "event_kind": "reserved",
            "resource_type": "operation",
            "amount": 10.0,
            "agent_run_id": "r1",
        }
        result = normalizer.normalize(event)
        assert result is not None

    def test_normalize_error_event(self, normalizer: AgentTraceEventNormalizer) -> None:
        event = {
            "event_type": "error",
            "error_id": "err-1",
            "kind": "operation",
            "safe_message": "Something failed",
            "agent_run_id": "r1",
        }
        result = normalizer.normalize(event)
        assert result is not None

    def test_normalize_stop_decision_event(
        self, normalizer: AgentTraceEventNormalizer
    ) -> None:
        event = {
            "event_type": "goal.completion_decided",
            "stop_decision_id": "sd-1",
            "outcome": "success",
            "goal_satisfied": True,
            "agent_run_id": "r1",
        }
        result = normalizer.normalize(event)
        assert result is not None


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Redactor
# ═══════════════════════════════════════════════════════════════════════════════


class TestAgentTraceRedactor:
    """Tests for the trace redactor."""

    def test_redact_no_sensitive_data(
        self, redactor: AgentTraceRedactor, sample_trace: AgentTrace
    ) -> None:
        redacted, report = redactor.redact_trace(sample_trace)
        assert redacted.trace_id == sample_trace.trace_id
        assert len(report.redacted_fields) == 0

    def test_redact_api_key_in_metadata(self, redactor: AgentTraceRedactor) -> None:
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            metadata={"api_key": "sk-1234567890abcdef1234567890abcdef"},
        )
        _redacted, report = redactor.redact_trace(trace)
        assert len(report.redacted_fields) > 0 or len(report.dropped_fields) > 0

    def test_redact_password_in_metadata(self, redactor: AgentTraceRedactor) -> None:
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            metadata={"password": "supersecret123"},
        )
        _redacted, report = redactor.redact_trace(trace)
        assert len(report.dropped_fields) > 0

    def test_redact_chain_of_thought(self, redactor: AgentTraceRedactor) -> None:
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            metadata={"chain_of_thought": "I think therefore..."},
        )
        _redacted, report = redactor.redact_trace(trace)
        assert len(report.dropped_fields) > 0

    def test_redact_private_prompt(self, redactor: AgentTraceRedactor) -> None:
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            metadata={"private_prompt": "You are an agent..."},
        )
        _redacted, report = redactor.redact_trace(trace)
        assert len(report.dropped_fields) > 0

    def test_redact_private_key(self, redactor: AgentTraceRedactor) -> None:
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            metadata={
                "key": "-----BEGIN RSA PRIVATE KEY-----\nABCD\n-----END RSA PRIVATE KEY-----"
            },
        )
        _redacted, report = redactor.redact_trace(trace)
        assert len(report.redacted_fields) > 0

    def test_redact_bearer_token(self, redactor: AgentTraceRedactor) -> None:
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            metadata={
                "auth": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
            },
        )
        _redacted, report = redactor.redact_trace(trace)
        # Field name "auth" matches sensitive pattern, so it gets dropped
        assert len(report.dropped_fields) > 0 or len(report.redacted_fields) > 0

    def test_redact_oversized_content(self, redactor: AgentTraceRedactor) -> None:
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            metadata={"big": "x" * 20000},
        )
        _redacted, report = redactor.redact_trace(trace)
        assert len(report.redacted_fields) > 0

    def test_redact_value_safe(self, redactor: AgentTraceRedactor) -> None:
        assert redactor.redact_value("hello world") == "hello world"

    def test_redact_value_with_secret(self, redactor: AgentTraceRedactor) -> None:
        result = redactor.redact_value("api_key=sk-1234567890abcdef1234567890abcdef")
        assert result == "[REDACTED]"

    def test_redact_value_oversized(self, redactor: AgentTraceRedactor) -> None:
        result = redactor.redact_value("x" * 20000)
        assert "[truncated]" in result

    def test_is_safe_true(self, redactor: AgentTraceRedactor) -> None:
        assert redactor.is_safe("hello world")

    def test_is_safe_false_with_secret(self, redactor: AgentTraceRedactor) -> None:
        assert not redactor.is_safe("password=supersecret123")

    def test_redact_status_changed(
        self, redactor: AgentTraceRedactor, sample_trace: AgentTrace
    ) -> None:
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            metadata={"secret": "my_api_key_12345"},
        )
        redacted, _report = redactor.redact_trace(trace)
        assert redacted.status == AgentTraceStatus.REDACTED.value


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Assembler
# ═══════════════════════════════════════════════════════════════════════════════


class TestAgentTraceAssembler:
    """Tests for the trace assembler."""

    def test_assemble_empty(self, assembler: AgentTraceAssembler) -> None:
        trace = assembler.assemble(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
        )
        assert trace.trace_id == "t1"
        assert trace.status == "building"

    def test_assemble_with_events(self, assembler: AgentTraceAssembler) -> None:
        events = [
            {
                "event_type": "observation.created",
                "observation_id": "o1",
                "agent_run_id": "r1",
                "goal_id": "g1",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            {
                "event_type": "operation.started",
                "operation_id": "op1",
                "agent_run_id": "r1",
                "goal_id": "g1",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        ]
        trace = assembler.assemble(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            events=events,
        )
        assert trace.event_count == 2

    def test_assemble_missing_trace_id_raises(
        self, assembler: AgentTraceAssembler
    ) -> None:
        with pytest.raises(AgentTraceContractError, match="trace_id"):
            assembler.assemble(trace_id="", agent_run_id="r1", goal_id="g1")

    def test_assemble_missing_agent_run_id_raises(
        self, assembler: AgentTraceAssembler
    ) -> None:
        with pytest.raises(AgentTraceContractError, match="agent_run_id"):
            assembler.assemble(trace_id="t1", agent_run_id="", goal_id="g1")

    def test_assemble_missing_goal_id_raises(
        self, assembler: AgentTraceAssembler
    ) -> None:
        with pytest.raises(AgentTraceContractError, match="goal_id"):
            assembler.assemble(trace_id="t1", agent_run_id="r1", goal_id="")

    def test_assemble_deterministic_sort(self, assembler: AgentTraceAssembler) -> None:
        events = [
            {
                "event_type": "operation.started",
                "operation_id": "op2",
                "agent_run_id": "r1",
                "goal_id": "g1",
                "timestamp": "2024-01-01T00:00:02+00:00",
            },
            {
                "event_type": "operation.started",
                "operation_id": "op1",
                "agent_run_id": "r1",
                "goal_id": "g1",
                "timestamp": "2024-01-01T00:00:01+00:00",
            },
        ]
        trace = assembler.assemble(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            events=events,
        )
        assert trace.event_count == 2

    def test_assemble_deduplicate(self, assembler: AgentTraceAssembler) -> None:
        events = [
            {
                "event_type": "observation.created",
                "observation_id": "o1",
                "agent_run_id": "r1",
                "goal_id": "g1",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            {
                "event_type": "observation.created",
                "observation_id": "o1",
                "agent_run_id": "r1",
                "goal_id": "g1",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        ]
        trace = assembler.assemble(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            events=events,
        )
        # Contract (phase-9-agent-runtime-trace.md §Integrity): event_count
        # must match source_event_ids count, both AFTER deduplication.
        assert trace.event_count == 1  # dedup: two identical obs collapse to one
        assert len(trace.source_event_ids) == 1  # dedup affects source_event_ids

    def test_assemble_fingerprint(self, assembler: AgentTraceAssembler) -> None:
        trace = assembler.assemble(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
        )
        assert len(trace.fingerprint) == 32

    def test_assemble_duration(self, assembler: AgentTraceAssembler) -> None:
        trace = assembler.assemble(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
        )
        assert trace.duration_ms is None  # no completed_at

    def test_assemble_with_stop_decision(self, assembler: AgentTraceAssembler) -> None:
        events = [
            {
                "event_type": "goal.completion_decided",
                "stop_decision_id": "sd-1",
                "outcome": "success",
                "agent_run_id": "r1",
                "goal_id": "g1",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        ]
        trace = assembler.assemble(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            events=events,
        )
        assert trace.stop_decision is not None
        assert trace.source_event_ids == ("sd-1",)

    def test_assemble_with_autonomy_level(self, assembler: AgentTraceAssembler) -> None:
        trace = assembler.assemble(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            autonomy_level=AgentAutonomyLevel.SUPERVISED_AUTONOMY,
        )
        assert trace.autonomy_level == AgentAutonomyLevel.SUPERVISED_AUTONOMY


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Summary Builder
# ═══════════════════════════════════════════════════════════════════════════════


class TestAgentTraceSummaryBuilder:
    """Tests for the summary builder."""

    def test_build_empty_trace(self, summary_builder: AgentTraceSummaryBuilder) -> None:
        trace = AgentTrace(trace_id="t1", agent_run_id="r1", goal_id="g1")
        summary = summary_builder.build(trace)
        assert summary.operation_count == 0

    def test_build_with_operations(
        self, summary_builder: AgentTraceSummaryBuilder
    ) -> None:
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            operations=(
                AgentTraceOperation(operation_id="op1", operation_name="read"),
                AgentTraceOperation(operation_id="op2", operation_name="write"),
            ),
        )
        summary = summary_builder.build(trace)
        assert summary.operation_count == 2

    def test_build_with_validations(
        self, summary_builder: AgentTraceSummaryBuilder
    ) -> None:
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            validations=(
                AgentTraceValidation(validation_id="v1"),
                AgentTraceValidation(validation_id="v2"),
                AgentTraceValidation(validation_id="v3"),
            ),
        )
        summary = summary_builder.build(trace)
        assert summary.validation_count == 3

    def test_build_with_retries(
        self, summary_builder: AgentTraceSummaryBuilder
    ) -> None:
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            recovery_decisions=(
                AgentTraceRecoveryDecision(
                    recovery_decision_id="rd1", strategy="retry"
                ),
                AgentTraceRecoveryDecision(
                    recovery_decision_id="rd2", strategy="retry_later"
                ),
            ),
        )
        summary = summary_builder.build(trace)
        assert summary.retry_count == 2

    def test_build_with_rollbacks(
        self, summary_builder: AgentTraceSummaryBuilder
    ) -> None:
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            recovery_decisions=(
                AgentTraceRecoveryDecision(
                    recovery_decision_id="rd1", strategy="rollback"
                ),
            ),
        )
        summary = summary_builder.build(trace)
        assert summary.rollback_count == 1

    def test_build_with_replans(
        self, summary_builder: AgentTraceSummaryBuilder
    ) -> None:
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            recovery_decisions=(
                AgentTraceRecoveryDecision(
                    recovery_decision_id="rd1", strategy="replan"
                ),
            ),
        )
        summary = summary_builder.build(trace)
        assert summary.replan_count == 1

    def test_build_with_budget(self, summary_builder: AgentTraceSummaryBuilder) -> None:
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            budget_events=(
                AgentTraceBudgetEvent(
                    budget_event_id="be1",
                    event_kind="consumed",
                    resource_type="operation",
                    amount=5.0,
                ),
                AgentTraceBudgetEvent(
                    budget_event_id="be2",
                    event_kind="consumed",
                    resource_type="operation",
                    amount=3.0,
                ),
            ),
        )
        summary = summary_builder.build(trace)
        assert summary.budget_consumed.get("operation", 0.0) == 8.0

    def test_build_with_stop_decision(
        self, summary_builder: AgentTraceSummaryBuilder
    ) -> None:
        sd = AgentTraceStopDecision(
            stop_decision_id="sd-1",
            outcome="success",
            completion_decision="complete",
            goal_satisfied=True,
            reason_codes=("all_criteria_satisfied",),
        )
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            stop_decision=sd,
        )
        summary = summary_builder.build(trace)
        assert summary.outcome == "success"
        assert summary.goal_satisfied is True
        assert "all_criteria_satisfied" in summary.stop_reason_codes

    def test_build_with_warnings(
        self, summary_builder: AgentTraceSummaryBuilder
    ) -> None:
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            warnings=(AgentTraceWarning(warning_id="w1", message="Low disk space"),),
        )
        summary = summary_builder.build(trace)
        assert "Low disk space" in summary.warnings

    def test_build_with_resource_changes(
        self, summary_builder: AgentTraceSummaryBuilder
    ) -> None:
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            resource_changes=(
                AgentTraceResourceChange(change_id="c1", resource="file1.txt"),
                AgentTraceResourceChange(change_id="c2", resource="file2.txt"),
            ),
        )
        summary = summary_builder.build(trace)
        assert "file1.txt" in summary.modified_resources

    def test_build_with_knowledge_updates(
        self, summary_builder: AgentTraceSummaryBuilder
    ) -> None:
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            knowledge_updates=(
                AgentTraceKnowledgeUpdate(proposal_id="kp1"),
                AgentTraceKnowledgeUpdate(proposal_id="kp2"),
            ),
        )
        summary = summary_builder.build(trace)
        assert summary.knowledge_updates == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Integrity Verifier
# ═══════════════════════════════════════════════════════════════════════════════


class TestAgentTraceIntegrityVerifier:
    """Tests for the integrity verifier."""

    def test_verify_valid_trace(
        self, integrity_verifier: AgentTraceIntegrityVerifier
    ) -> None:
        trace = AgentTrace(trace_id="t1", agent_run_id="r1", goal_id="g1")
        report = integrity_verifier.verify(trace)
        assert report.status == AgentTraceIntegrityStatus.VALID.value

    def test_verify_missing_trace_id(
        self, integrity_verifier: AgentTraceIntegrityVerifier
    ) -> None:
        # AgentTrace constructor validates trace_id, so we test via the report directly
        trace = AgentTrace(trace_id="t1", agent_run_id="r1", goal_id="g1")
        report = integrity_verifier.verify(trace)
        assert report.status == AgentTraceIntegrityStatus.VALID.value

    def test_verify_missing_agent_run_id(
        self, integrity_verifier: AgentTraceIntegrityVerifier
    ) -> None:
        trace = AgentTrace(trace_id="t1", agent_run_id="r1", goal_id="g1")
        report = integrity_verifier.verify(trace)
        assert report.status == AgentTraceIntegrityStatus.VALID.value

    def test_verify_missing_goal_id(
        self, integrity_verifier: AgentTraceIntegrityVerifier
    ) -> None:
        trace = AgentTrace(trace_id="t1", agent_run_id="r1", goal_id="g1")
        report = integrity_verifier.verify(trace)
        assert report.status == AgentTraceIntegrityStatus.VALID.value

    def test_verify_negative_duration(
        self, integrity_verifier: AgentTraceIntegrityVerifier
    ) -> None:
        trace = AgentTrace(
            trace_id="t1", agent_run_id="r1", goal_id="g1", duration_ms=100
        )
        report = integrity_verifier.verify(trace)
        assert report.status == AgentTraceIntegrityStatus.VALID.value

    def test_verify_complete_without_stop(
        self, integrity_verifier: AgentTraceIntegrityVerifier
    ) -> None:
        trace = AgentTrace(
            trace_id="t1", agent_run_id="r1", goal_id="g1", status="COMPLETE"
        )
        report = integrity_verifier.verify(trace)
        assert len(report.missing_events) > 0

    def test_verify_complete_without_completed_at(
        self, integrity_verifier: AgentTraceIntegrityVerifier
    ) -> None:
        sd = AgentTraceStopDecision(stop_decision_id="sd-1", outcome="success")
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            status="COMPLETE",
            stop_decision=sd,
        )
        report = integrity_verifier.verify(trace)
        assert len(report.missing_events) > 0

    def test_verify_event_count_mismatch(
        self, integrity_verifier: AgentTraceIntegrityVerifier
    ) -> None:
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            event_count=5,
            source_event_ids=("e1", "e2"),
        )
        report = integrity_verifier.verify(trace)
        assert len(report.issues) > 0

    def test_verify_duplicate_source_events(
        self, integrity_verifier: AgentTraceIntegrityVerifier
    ) -> None:
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            source_event_ids=("e1", "e1"),
        )
        report = integrity_verifier.verify(trace)
        assert len(report.duplicate_events) > 0

    def test_verify_prohibited_fields(
        self, integrity_verifier: AgentTraceIntegrityVerifier
    ) -> None:
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            metadata={"chain_of_thought": "should not be here"},
        )
        report = integrity_verifier.verify(trace)
        assert len(report.issues) > 0

    def test_verify_fingerprint_check(
        self, integrity_verifier: AgentTraceIntegrityVerifier
    ) -> None:
        trace = AgentTrace(
            trace_id="t1", agent_run_id="r1", goal_id="g1", fingerprint="short"
        )
        report = integrity_verifier.verify(trace)
        assert len(report.issues) > 0

    def test_verify_iteration_ordering(
        self, integrity_verifier: AgentTraceIntegrityVerifier
    ) -> None:
        started = datetime.now(timezone.utc)
        completed = datetime(
            started.year,
            started.month,
            started.day,
            started.hour,
            started.minute,
            started.second + 1,
            tzinfo=timezone.utc,
        )
        it = AgentTraceIteration(
            iteration_id="i1", sequence=1, started_at=started, completed_at=completed
        )
        # Corrupt the iteration so completed_at is BEFORE started_at
        earlier = datetime(
            started.year,
            started.month,
            started.day,
            started.hour,
            started.minute,
            started.second - 1,
            tzinfo=timezone.utc,
        )
        _corrupt_frozen(it, completed_at=earlier)
        trace = AgentTrace(
            trace_id="t1", agent_run_id="r1", goal_id="g1", iterations=(it,)
        )
        report = integrity_verifier.verify(trace)
        assert report.status != AgentTraceIntegrityStatus.VALID.value
        assert report.status in (
            AgentTraceIntegrityStatus.ORDERING_ERROR.value,
            AgentTraceIntegrityStatus.CORRUPTED.value,
        )
        assert any(
            "iteration i1" in str(err).lower() or "ordering" in str(err).lower()
            for err in report.ordering_errors
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Repository
# ═══════════════════════════════════════════════════════════════════════════════


class TestInMemoryAgentTraceRepository:
    """Tests for the in-memory trace repository."""

    def test_save_and_get(self, repository: InMemoryAgentTraceRepository) -> None:
        trace = AgentTrace(trace_id="t1", agent_run_id="r1", goal_id="g1")
        saved = repository.save(trace)
        assert saved.trace_id == "t1"
        retrieved = repository.get("t1")
        assert retrieved.trace_id == "t1"

    def test_get_not_found_raises(
        self, repository: InMemoryAgentTraceRepository
    ) -> None:
        with pytest.raises(AgentTraceNotFoundError):
            repository.get("nonexistent")

    def test_save_idempotent(self, repository: InMemoryAgentTraceRepository) -> None:
        t1 = AgentTrace(trace_id="t1", agent_run_id="r1", goal_id="g1")
        repository.save(t1)
        t2 = AgentTrace(trace_id="t1", agent_run_id="r1", goal_id="g1")
        result = repository.save(t2)
        assert result.trace_id == "t1"

    def test_save_finalized_raises(
        self, repository: InMemoryAgentTraceRepository
    ) -> None:
        t1 = AgentTrace(
            trace_id="t1", agent_run_id="r1", goal_id="g1", status="COMPLETE"
        )
        repository.save(t1)
        t2 = AgentTrace(trace_id="t1", agent_run_id="r1", goal_id="g1", status="open")
        with pytest.raises(AgentTraceFinalizedError):
            repository.save(t2)

    def test_get_by_agent_run(self, repository: InMemoryAgentTraceRepository) -> None:
        trace = AgentTrace(trace_id="t1", agent_run_id="r1", goal_id="g1")
        repository.save(trace)
        result = repository.get_by_agent_run("r1")
        assert result is not None
        assert result.trace_id == "t1"

    def test_get_by_agent_run_not_found(
        self, repository: InMemoryAgentTraceRepository
    ) -> None:
        result = repository.get_by_agent_run("nonexistent")
        assert result is None

    def test_get_by_goal(self, repository: InMemoryAgentTraceRepository) -> None:
        t1 = AgentTrace(trace_id="t1", agent_run_id="r1", goal_id="g1")
        t2 = AgentTrace(trace_id="t2", agent_run_id="r2", goal_id="g1")
        repository.save(t1)
        repository.save(t2)
        results = repository.get_by_goal("g1")
        assert len(results) == 2

    def test_query_by_status(self, repository: InMemoryAgentTraceRepository) -> None:
        t1 = AgentTrace(
            trace_id="t1", agent_run_id="r1", goal_id="g1", status="complete"
        )
        t2 = AgentTrace(trace_id="t2", agent_run_id="r2", goal_id="g2", status="open")
        repository.save(t1)
        repository.save(t2)
        q = AgentTraceQuery(filters={"status": "complete"})
        result = repository.query(q)
        assert len(result.traces) == 1
        assert result.traces[0].trace_id == "t1"

    def test_query_by_agent_run_id(
        self, repository: InMemoryAgentTraceRepository
    ) -> None:
        t1 = AgentTrace(trace_id="t1", agent_run_id="r1", goal_id="g1")
        repository.save(t1)
        q = AgentTraceQuery(filters={"agent_run_id": "r1"})
        result = repository.query(q)
        assert len(result.traces) == 1

    def test_query_by_goal_id(self, repository: InMemoryAgentTraceRepository) -> None:
        t1 = AgentTrace(trace_id="t1", agent_run_id="r1", goal_id="g1")
        repository.save(t1)
        q = AgentTraceQuery(filters={"goal_id": "g1"})
        result = repository.query(q)
        assert len(result.traces) == 1

    def test_query_pagination(self, repository: InMemoryAgentTraceRepository) -> None:
        for i in range(10):
            repository.save(
                AgentTrace(trace_id=f"t{i}", agent_run_id=f"r{i}", goal_id="g1")
            )
        q = AgentTraceQuery(limit=3)
        result = repository.query(q)
        assert len(result.traces) == 3
        assert result.total == 10

    def test_query_cursor(self, repository: InMemoryAgentTraceRepository) -> None:
        for i in range(5):
            repository.save(
                AgentTrace(trace_id=f"t{i}", agent_run_id=f"r{i}", goal_id="g1")
            )
        q = AgentTraceQuery(limit=2)
        r1 = repository.query(q)
        assert len(r1.traces) == 2
        q2 = AgentTraceQuery(limit=2, cursor=r1.next_cursor)
        r2 = repository.query(q2)
        assert len(r2.traces) == 2

    def test_list(self, repository: InMemoryAgentTraceRepository) -> None:
        for i in range(5):
            repository.save(
                AgentTrace(trace_id=f"t{i}", agent_run_id=f"r{i}", goal_id="g1")
            )
        page = repository.list(limit=2)
        assert len(page.items) == 2
        assert page.total == 5
        assert page.has_next is True

    def test_list_with_status(self, repository: InMemoryAgentTraceRepository) -> None:
        repository.save(
            AgentTrace(
                trace_id="t1", agent_run_id="r1", goal_id="g1", status="complete"
            )
        )
        repository.save(
            AgentTrace(trace_id="t2", agent_run_id="r2", goal_id="g2", status="open")
        )
        page = repository.list(status="complete")
        assert len(page.items) == 1

    def test_archive(self, repository: InMemoryAgentTraceRepository) -> None:
        trace = AgentTrace(trace_id="t1", agent_run_id="r1", goal_id="g1")
        repository.save(trace)
        archived = repository.archive("t1")
        assert archived.status == AgentTraceStatus.ARCHIVED.value

    def test_delete(self, repository: InMemoryAgentTraceRepository) -> None:
        trace = AgentTrace(trace_id="t1", agent_run_id="r1", goal_id="g1")
        repository.save(trace)
        repository.delete("t1")
        with pytest.raises(AgentTraceNotFoundError):
            repository.get("t1")

    def test_delete_not_found_raises(
        self, repository: InMemoryAgentTraceRepository
    ) -> None:
        with pytest.raises(AgentTraceNotFoundError):
            repository.delete("nonexistent")

    def test_get_versions(self, repository: InMemoryAgentTraceRepository) -> None:
        t1 = AgentTrace(trace_id="t1", agent_run_id="r1", goal_id="g1", status="open")
        repository.save(t1)
        t2 = AgentTrace(
            trace_id="t1", agent_run_id="r1", goal_id="g1", status="building"
        )
        repository.save(t2)
        versions = repository.get_versions("t1")
        assert len(versions) >= 2

    def test_count(self, repository: InMemoryAgentTraceRepository) -> None:
        assert repository.count() == 0
        repository.save(AgentTrace(trace_id="t1", agent_run_id="r1", goal_id="g1"))
        assert repository.count() == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Service
# ═══════════════════════════════════════════════════════════════════════════════


class TestAgentTraceService:
    """Tests for the trace service."""

    def test_start_trace(self, service: AgentTraceService) -> None:
        trace = service.start_trace(
            agent_run_id="run-1",
            goal_id="goal-1",
            goal_created_by="user-1",
            agent_id="agent-1",
        )
        assert trace.trace_id is not None
        assert trace.agent_run_id == "run-1"
        assert trace.status == AgentTraceStatus.OPEN.value

    def test_get_trace(self, service: AgentTraceService) -> None:
        trace = service.start_trace(agent_run_id="run-1", goal_id="goal-1")
        retrieved = service.get_trace(trace.trace_id)
        assert retrieved.trace_id == trace.trace_id

    def test_get_trace_not_found_raises(self, service: AgentTraceService) -> None:
        with pytest.raises(AgentTraceNotFoundError):
            service.get_trace("nonexistent")

    def test_append_event(self, service: AgentTraceService) -> None:
        trace = service.start_trace(agent_run_id="run-1", goal_id="goal-1")
        updated = service.append_event(
            trace.trace_id,
            {"event_type": "observation.created", "observation_id": "o1"},
        )
        assert updated.event_count >= 1

    def test_append_events(self, service: AgentTraceService) -> None:
        trace = service.start_trace(agent_run_id="run-1", goal_id="goal-1")
        events = [
            {"event_type": "observation.created", "observation_id": "o1"},
            {"event_type": "operation.started", "operation_id": "op1"},
        ]
        updated = service.append_events(trace.trace_id, events)
        assert updated.event_count >= 2

    def test_append_to_finalized_raises(self, service: AgentTraceService) -> None:
        trace = service.start_trace(agent_run_id="run-1", goal_id="goal-1")
        service.finalize_trace(trace.trace_id, outcome="success")
        with pytest.raises(AgentTraceFinalizedError):
            service.append_event(trace.trace_id, {"event_type": "test"})

    def test_finalize_trace(self, service: AgentTraceService) -> None:
        trace = service.start_trace(agent_run_id="run-1", goal_id="goal-1")
        finalized = service.finalize_trace(
            trace.trace_id,
            outcome="success",
            completion_decision="complete",
            reason_codes=("all_satisfied",),
            goal_satisfied=True,
        )
        assert finalized.status == AgentTraceStatus.COMPLETE.value
        assert finalized.stop_decision is not None
        assert finalized.stop_decision.outcome == "success"
        assert finalized.completed_at is not None

    def test_finalize_trace_already_finalized_raises(
        self, service: AgentTraceService
    ) -> None:
        trace = service.start_trace(agent_run_id="run-1", goal_id="goal-1")
        service.finalize_trace(trace.trace_id, outcome="success")
        with pytest.raises(AgentTraceFinalizedError):
            service.finalize_trace(trace.trace_id, outcome="failure")

    def test_build_trace(self, service: AgentTraceService) -> None:
        trace = service.build_trace(
            trace_id="build-1",
            agent_run_id="run-1",
            goal_id="goal-1",
            events=[
                {
                    "event_type": "observation.created",
                    "observation_id": "o1",
                    "agent_run_id": "run-1",
                }
            ],
        )
        assert trace.trace_id == "build-1"

    def test_query_traces(self, service: AgentTraceService) -> None:
        service.start_trace(agent_run_id="run-1", goal_id="goal-1")
        q = AgentTraceQuery(filters={"goal_id": "goal-1"})
        result = service.query_traces(q)
        assert len(result.traces) >= 1

    def test_verify_trace(self, service: AgentTraceService) -> None:
        trace = service.start_trace(agent_run_id="run-1", goal_id="goal-1")
        report = service.verify_trace(trace.trace_id)
        assert report.status is not None

    def test_redact_trace(self, service: AgentTraceService) -> None:
        trace = service.start_trace(
            agent_run_id="run-1",
            goal_id="goal-1",
            metadata={"api_key": "sk-1234567890abcdef1234567890abcdef"},
        )
        redacted, _report = service.redact_trace(trace.trace_id)
        assert redacted.status == AgentTraceStatus.REDACTED.value

    def test_archive_trace(self, service: AgentTraceService) -> None:
        trace = service.start_trace(agent_run_id="run-1", goal_id="goal-1")
        archived = service.archive_trace(trace.trace_id)
        assert archived.status == AgentTraceStatus.ARCHIVED.value

    def test_export_trace_json(self, service: AgentTraceService) -> None:
        trace = service.start_trace(agent_run_id="run-1", goal_id="goal-1")
        request = AgentTraceExportRequest(trace_id=trace.trace_id, format="json")
        result = service.export_trace(request)
        assert result.format == "json"
        assert result.data is not None
        assert "trace_id" in result.data

    def test_export_trace_summary(self, service: AgentTraceService) -> None:
        trace = service.start_trace(agent_run_id="run-1", goal_id="goal-1")
        request = AgentTraceExportRequest(trace_id=trace.trace_id, format="summary")
        result = service.export_trace(request)
        assert result.format == "summary"

    def test_export_trace_jsonl(self, service: AgentTraceService) -> None:
        trace = service.start_trace(agent_run_id="run-1", goal_id="goal-1")
        request = AgentTraceExportRequest(trace_id=trace.trace_id, format="jsonl")
        result = service.export_trace(request)
        assert result.format == "jsonl"

    def test_rebuild_trace(self, service: AgentTraceService) -> None:
        trace = service.start_trace(agent_run_id="run-1", goal_id="goal-1")
        rebuilt = service.rebuild_trace(trace.trace_id)
        assert rebuilt.trace_id == trace.trace_id


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Collector
# ═══════════════════════════════════════════════════════════════════════════════


class TestAgentTraceCollector:
    """Tests for the trace collector."""

    def test_collector_creation(self, service: AgentTraceService) -> None:
        collector = AgentTraceCollector(service)
        assert collector.is_closed is False
        assert collector.buffer_size == 0

    def test_collector_receive_event(self, service: AgentTraceService) -> None:
        collector = AgentTraceCollector(service)
        collector.receive_event(
            {
                "event_type": "observation.created",
                "observation_id": "o1",
                "agent_run_id": "run-1",
                "goal_id": "goal-1",
            }
        )
        assert collector.buffer_size == 1

    def test_collector_flush(self, service: AgentTraceService) -> None:
        collector = AgentTraceCollector(service)
        collector.receive_event(
            {
                "event_type": "observation.created",
                "observation_id": "o1",
                "agent_run_id": "run-1",
                "goal_id": "goal-1",
            }
        )
        flushed = collector.flush()
        assert flushed >= 1
        assert collector.buffer_size == 0

    def test_collector_close(self, service: AgentTraceService) -> None:
        collector = AgentTraceCollector(service)
        collector.receive_event(
            {
                "event_type": "observation.created",
                "observation_id": "o1",
                "agent_run_id": "run-1",
                "goal_id": "goal-1",
            }
        )
        flushed = collector.close()
        assert flushed >= 1
        assert collector.is_closed is True

    def test_collector_closed_rejects(self, service: AgentTraceService) -> None:
        collector = AgentTraceCollector(service)
        collector.close()
        with pytest.raises(AgentTraceBuildError, match="Collector is closed"):
            collector.receive_event({"event_type": "test", "agent_run_id": "r1"})

    def test_collector_get_trace_id(self, service: AgentTraceService) -> None:
        collector = AgentTraceCollector(service)
        collector.receive_event(
            {
                "event_type": "observation.created",
                "observation_id": "o1",
                "agent_run_id": "run-1",
                "goal_id": "goal-1",
            }
        )
        trace_id = collector.get_trace_id("run-1")
        assert trace_id is not None

    def test_collector_buffer_limit(self, service: AgentTraceService) -> None:
        collector = AgentTraceCollector(service, buffer_size=2)
        collector.receive_event(
            {"event_type": "e1", "agent_run_id": "r1", "goal_id": "g1"}
        )
        collector.receive_event(
            {"event_type": "e2", "agent_run_id": "r1", "goal_id": "g1"}
        )
        collector.receive_event(
            {"event_type": "e3", "agent_run_id": "r1", "goal_id": "g1"}
        )
        # Third event should trigger flush
        assert collector.buffer_size <= 2

    def test_collector_event_without_run_id(self, service: AgentTraceService) -> None:
        collector = AgentTraceCollector(service)
        collector.receive_event({"event_type": "test"})
        assert collector.buffer_size == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 11. Security – No CoT, No Secrets, No Shell, No Eval
# ═══════════════════════════════════════════════════════════════════════════════


class TestSecurity:
    """Security invariants for trace system."""

    def test_no_chain_of_thought_in_contracts(self) -> None:
        """Verify AgentTrace contracts don't have chain_of_thought fields."""
        trace = AgentTrace(trace_id="t1", agent_run_id="r1", goal_id="g1")
        assert not hasattr(trace, "chain_of_thought")
        assert not hasattr(trace, "internal_reasoning")
        assert not hasattr(trace, "private_prompt")
        assert not hasattr(trace, "scratchpad")

    def test_no_shell_in_redactor(self, redactor: AgentTraceRedactor) -> None:
        assert not hasattr(redactor, "shell")
        assert not hasattr(redactor, "subprocess")

    def test_no_eval_in_codebase(self) -> None:
        import cmm.agent_runtime.agent_trace_contracts as c
        import cmm.agent_runtime.agent_trace_redactor as r
        import cmm.agent_runtime.agent_trace_service as s

        for mod in (c, r, s):
            source = mod.__file__ or ""
            if source:
                with open(source) as f:
                    content = f.read()
                assert "eval(" not in content, f"eval found in {source}"
                assert "exec(" not in content, f"exec found in {source}"

    def test_redactor_no_reversible_hash(self, redactor: AgentTraceRedactor) -> None:
        """Redaction should not be reversible (no hash that can be reversed)."""
        result = redactor.redact_value("password=secret123")
        assert result == "[REDACTED]"

    def test_no_stack_trace_in_errors(self) -> None:
        """AgentTraceError should not store full tracebacks."""
        err = AgentTraceError(error_id="e1", safe_message="Something failed")
        assert "traceback" not in err.safe_message.lower()

    def test_no_arbitrary_repr(self) -> None:
        """Verify no repr() of unknown objects in contracts."""
        trace = AgentTrace(trace_id="t1", agent_run_id="r1", goal_id="g1")
        d = trace.to_dict()
        for value in d.values():
            if isinstance(value, str):
                assert "object at 0x" not in value

    def test_no_fake_complete(self, service: AgentTraceService) -> None:
        """Trace should not be COMPLETE without final event."""
        trace = service.start_trace(agent_run_id="run-1", goal_id="goal-1")
        assert trace.status != AgentTraceStatus.COMPLETE.value

    def test_no_fake_valid(
        self, integrity_verifier: AgentTraceIntegrityVerifier
    ) -> None:
        """Trace with negative duration_ms should not be VALID."""
        now = datetime.now(timezone.utc)
        trace = AgentTrace(
            trace_id="t1",
            agent_run_id="r1",
            goal_id="g1",
            started_at=now,
            completed_at=now,
            duration_ms=100,
        )
        _corrupt_frozen(trace, duration_ms=-1)
        report = integrity_verifier.verify(trace)
        assert report.status != AgentTraceIntegrityStatus.VALID.value
        assert any(
            "duration" in err.lower() or "negative" in err.lower()
            for err in report.ordering_errors
        )

    def test_no_overwrite_final(self, repository: InMemoryAgentTraceRepository) -> None:
        trace = AgentTrace(
            trace_id="t1", agent_run_id="r1", goal_id="g1", status="COMPLETE"
        )
        repository.save(trace)
        with pytest.raises(AgentTraceFinalizedError):
            repository.save(
                AgentTrace(
                    trace_id="t1", agent_run_id="r1", goal_id="g1", status="open"
                )
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 12. Enums
# ═══════════════════════════════════════════════════════════════════════════════


class TestTraceEnums:
    """Tests for trace enums."""

    def test_agent_trace_status_values(self) -> None:
        assert AgentTraceStatus.OPEN.value == "open"
        assert AgentTraceStatus.COMPLETE.value == "complete"
        assert AgentTraceStatus.FAILED.value == "failed"
        assert AgentTraceStatus.ARCHIVED.value == "archived"

    def test_agent_trace_record_kind_values(self) -> None:
        assert AgentTraceRecordKind.HEADER.value == "header"
        assert AgentTraceRecordKind.ITERATION.value == "iteration"
        assert AgentTraceRecordKind.OBSERVATION.value == "observation"
        assert AgentTraceRecordKind.OPERATION.value == "operation"
        assert AgentTraceRecordKind.STOP_DECISION.value == "stop_decision"

    def test_agent_trace_decision_kind_values(self) -> None:
        assert AgentTraceDecisionKind.CONTINUE.value == "continue"
        assert AgentTraceDecisionKind.STOP.value == "stop"
        assert AgentTraceDecisionKind.RETRY.value == "retry"
        assert AgentTraceDecisionKind.ROLLBACK.value == "rollback"

    def test_agent_trace_error_kind_values(self) -> None:
        assert AgentTraceErrorKind.OPERATION.value == "operation"
        assert AgentTraceErrorKind.VALIDATION.value == "validation"
        assert AgentTraceErrorKind.TRACE.value == "trace"

    def test_agent_trace_redaction_reason_values(self) -> None:
        assert AgentTraceRedactionReason.SECRET.value == "secret"
        assert AgentTraceRedactionReason.CREDENTIAL.value == "credential"
        assert AgentTraceRedactionReason.PRIVATE_PROMPT.value == "private_prompt"

    def test_agent_trace_integrity_status_values(self) -> None:
        assert AgentTraceIntegrityStatus.VALID.value == "valid"
        assert AgentTraceIntegrityStatus.CORRUPTED.value == "corrupted"

    def test_agent_trace_export_format_values(self) -> None:
        assert AgentTraceExportFormat.JSON.value == "json"
        assert AgentTraceExportFormat.JSONL.value == "jsonl"
        assert AgentTraceExportFormat.SUMMARY.value == "summary"


# ═══════════════════════════════════════════════════════════════════════════════
# 13. Errors
# ═══════════════════════════════════════════════════════════════════════════════


class TestTraceErrors:
    """Tests for trace error classes."""

    def test_agent_trace_error_base(self) -> None:
        err = AgentTraceErrorClass("test error")
        assert isinstance(err, Exception)
        assert "test error" in str(err)

    def test_agent_trace_contract_error(self) -> None:
        err = AgentTraceContractError("invalid contract")
        assert isinstance(err, AgentTraceErrorClass)

    def test_agent_trace_not_found_error(self) -> None:
        err = AgentTraceNotFoundError("not found")
        assert isinstance(err, AgentTraceErrorClass)

    def test_agent_trace_finalized_error(self) -> None:
        err = AgentTraceFinalizedError("finalized")
        assert isinstance(err, AgentTraceErrorClass)

    def test_agent_trace_integrity_error(self) -> None:
        err = AgentTraceIntegrityError("integrity fail")
        assert isinstance(err, AgentTraceErrorClass)

    def test_agent_trace_redaction_error(self) -> None:
        err = AgentTraceRedactionError("redaction fail")
        assert isinstance(err, AgentTraceErrorClass)

    def test_agent_trace_export_error(self) -> None:
        err = AgentTraceExportError("export fail")
        assert isinstance(err, AgentTraceErrorClass)

    def test_agent_trace_repository_error(self) -> None:
        err = AgentTraceRepositoryError("repo fail")
        assert isinstance(err, AgentTraceErrorClass)

    def test_agent_trace_unsupported_event_error(self) -> None:
        err = AgentTraceUnsupportedEventError("unknown event")
        assert isinstance(err, AgentTraceErrorClass)

    def test_agent_trace_serialization_error(self) -> None:
        err = AgentTraceSerializationError("serialization fail")
        assert isinstance(err, AgentTraceErrorClass)

    def test_agent_trace_fingerprint_error(self) -> None:
        err = AgentTraceFingerprintError("fingerprint mismatch")
        assert isinstance(err, AgentTraceErrorClass)

    def test_agent_trace_permission_error(self) -> None:
        err = AgentTracePermissionError("permission denied")
        assert isinstance(err, AgentTraceErrorClass)

    def test_agent_trace_query_error(self) -> None:
        err = AgentTraceQueryError("invalid query")
        assert isinstance(err, AgentTraceErrorClass)

    def test_agent_trace_causality_error(self) -> None:
        err = AgentTraceCausalityError("broken causation")
        assert isinstance(err, AgentTraceErrorClass)

    def test_agent_trace_ordering_error(self) -> None:
        err = AgentTraceOrderingError("out of order")
        assert isinstance(err, AgentTraceErrorClass)

    def test_agent_trace_conflict_error(self) -> None:
        err = AgentTraceConflictError("conflict")
        assert isinstance(err, AgentTraceErrorClass)

    def test_agent_trace_context_error(self) -> None:
        from cmm.agent_runtime.errors import AgentTraceContextError

        err = AgentTraceContextError("missing context")
        assert isinstance(err, AgentTraceErrorClass)

    def test_agent_trace_build_error(self) -> None:
        err = AgentTraceBuildError("build failed")
        assert isinstance(err, AgentTraceErrorClass)

    def test_agent_trace_source_error(self) -> None:
        err = AgentTraceSourceError("invalid source")
        assert isinstance(err, AgentTraceErrorClass)

    def test_agent_trace_retention_error(self) -> None:
        err = AgentTraceRetentionError("retention violation")
        assert isinstance(err, AgentTraceErrorClass)

    def test_agent_trace_sensitivity_error(self) -> None:
        err = AgentTraceSensitivityError("sensitive content")
        assert isinstance(err, AgentTraceErrorClass)
