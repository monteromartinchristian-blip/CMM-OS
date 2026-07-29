from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from threading import Lock
from types import MappingProxyType

import pytest

from cmm.agent_runtime.agent_observability_service import AgentObservabilityService
from cmm.agent_runtime.economic_budget_contracts import ModelCostEstimate
from cmm.agent_runtime.model_execution_assembler import ModelExecutionRecordAssembler
from cmm.agent_runtime.model_execution_contracts import (
    AcceptanceStatus,
    ContentRetentionMode,
    ModelExecutionContentReference,
    ModelExecutionRecord,
    ModelExecutionStatus,
    PrivacyClassification,
    QualityEvaluation,
)
from cmm.agent_runtime.model_execution_errors import (
    InvalidModelExecutionRecordError,
    ModelExecutionIdempotencyConflictError,
    ModelExecutionNotFoundError,
)
from cmm.agent_runtime.model_execution_observability import (
    ModelExecutionObservabilityProjector,
)
from cmm.agent_runtime.model_execution_repository import (
    InMemoryModelExecutionRecordRepository,
)
from cmm.agent_runtime.model_execution_service import ModelExecutionRecordService
from cmm.agent_runtime.model_fallback_contracts import (
    ModelAttemptResult,
    ModelFallbackAction,
    ModelFallbackTrigger,
)
from cmm.agent_runtime.model_requirements_contracts import (
    model_requirements_to_dict,
)
from cmm.agent_runtime.runtime_event_bus import AgentRuntimeEventBus
from kernel.llm.model_selection import ModelRequirements

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def record(**overrides):
    values = {
        "id": "mer-1",
        "agent_run_id": "run-1",
        "provider_id": "provider-a",
        "model_id": "model-a",
        "capability": "reasoning",
        "created_at": NOW,
    }
    values.update(overrides)
    return ModelExecutionRecord(**values)


def test_record_validates_decimal_integer_datetime_and_privacy_defaults():
    value = record(
        estimated_cost=Decimal("1.20"),
        input_tokens=2,
        prompt_hash="a" * 64,
        response_hash="b" * 64,
        metadata={"team": "runtime"},
    )
    assert value.acceptance_status is AcceptanceStatus.PENDING
    assert value.content_retention is ContentRetentionMode.HASHES_ONLY
    assert value.privacy_classification is PrivacyClassification.INTERNAL
    assert isinstance(value.metadata, MappingProxyType)
    assert value.to_dict()["estimated_cost"] == "1.20"
    assert ModelExecutionRecord.from_dict(value.to_dict()) == value


@pytest.mark.parametrize(
    "field,value",
    [("input_tokens", True), ("latency_ms", True), ("estimated_cost", float("nan"))],
)
def test_record_rejects_unsafe_numeric_values(field, value):
    with pytest.raises(InvalidModelExecutionRecordError):
        record(**{field: value})


def test_record_rejects_naive_datetime_and_sensitive_metadata():
    with pytest.raises(InvalidModelExecutionRecordError):
        record(created_at=datetime.fromisoformat("2026-01-01T00:00:00"))
    with pytest.raises(InvalidModelExecutionRecordError):
        record(metadata={"api_key": "secret"})


def test_acceptance_transitions_are_strict_and_technical_failure_is_separate():
    service = ModelExecutionRecordService(InMemoryModelExecutionRecordRepository())
    created = service.create_record(record(), idempotency_key="call-1")
    completed = service.complete_record(created.id, actual_cost=Decimal("0.50"))
    assert completed.execution_status.value == "completed"
    rejected = service.update_acceptance(completed.id, AcceptanceStatus.REJECTED)
    assert rejected.acceptance_status is AcceptanceStatus.REJECTED
    with pytest.raises(InvalidModelExecutionRecordError):
        service.update_acceptance(rejected.id, AcceptanceStatus.ACCEPTED)


def test_service_idempotency_and_repository_queries():
    repo = InMemoryModelExecutionRecordRepository()
    service = ModelExecutionRecordService(repo)
    first = service.create_record(record(), idempotency_key="call-1")
    assert service.create_record(record(), idempotency_key="call-1") == first
    with pytest.raises(ModelExecutionIdempotencyConflictError):
        service.create_record(record(model_id="model-b"), idempotency_key="call-1")
    assert repo.list_by_agent_run("run-1") == (first,)
    assert service.get_record("missing") is None
    with pytest.raises(ModelExecutionNotFoundError):
        service.complete_record("missing")


def test_idempotency_survives_service_reconstruction():
    repo = InMemoryModelExecutionRecordRepository()
    value = record(id="persistent-idempotency")

    first_service = ModelExecutionRecordService(repo)
    created = first_service.create_record(value, idempotency_key="persistent-key")

    reconstructed_service = ModelExecutionRecordService(repo)
    assert (
        reconstructed_service.create_record(
            value,
            idempotency_key="persistent-key",
        )
        == created
    )

    with pytest.raises(ModelExecutionIdempotencyConflictError):
        reconstructed_service.create_record(
            record(id="different-record", model_id="model-b"),
            idempotency_key="persistent-key",
        )

    assert len(repo) == 1


def test_idempotent_replay_does_not_emit_duplicate_created_event():
    class Bus:
        def __init__(self):
            self.events = []

        def publish(self, event):
            self.events.append(event.header.event_type)

    repo = InMemoryModelExecutionRecordRepository()
    bus = Bus()

    first_service = ModelExecutionRecordService(repo, event_bus=bus)
    value = record(id="idempotent-event")
    first_service.create_record(value, idempotency_key="event-key")

    reconstructed_service = ModelExecutionRecordService(repo, event_bus=bus)
    replayed = reconstructed_service.create_record(
        value,
        idempotency_key="event-key",
    )

    assert replayed == value
    assert bus.events == ["model_execution.created"]


def test_event_payload_is_safe_and_event_types_are_published():
    class Bus:
        def __init__(self):
            self.events = []

        def publish(self, event):
            self.events.append(event)

    bus = Bus()
    service = ModelExecutionRecordService(
        InMemoryModelExecutionRecordRepository(), event_bus=bus
    )
    created = service.create_record(record(metadata={"safe": "yes"}))
    service.complete_record(created.id)
    assert [event.header.event_type for event in bus.events] == [
        "model_execution.created",
        "model_execution.completed",
    ]
    assert "metadata" not in bus.events[0].payload.data
    assert bus.events[0].payload.data["record_id"] == created.id


def test_query_normalizes_enums_strings_and_rejects_unknown_filters():
    repo = InMemoryModelExecutionRecordRepository()
    repo.add(
        record(
            provider_id="Provider-A",
            model_id="Model-A",
            execution_status=ModelExecutionStatus.COMPLETED,
            acceptance_status=AcceptanceStatus.ACCEPTED,
            trace_id="trace-1",
            correlation_id="corr-1",
        )
    )
    assert repo.query(
        provider_id="provider-a",
        model_id="model-a",
        execution_status="completed",
        acceptance_status=AcceptanceStatus.ACCEPTED,
        trace_id="trace-1",
    )
    with pytest.raises(InvalidModelExecutionRecordError):
        repo.query(not_a_filter="x")


def test_repository_update_rejects_immutable_identity_changes():
    repo = InMemoryModelExecutionRecordRepository()
    original = repo.add(record(goal_id="goal-1"))
    with pytest.raises(InvalidModelExecutionRecordError):
        repo.update(record(goal_id="goal-2"))
    assert repo.get(original.id).goal_id == "goal-1"


def _estimate(currency, total, *, tokens=1):
    return ModelCostEstimate(
        Decimal(0),
        Decimal(0),
        Decimal(total),
        Decimal(total),
        currency=currency,
        input_tokens=tokens,
        output_tokens=tokens,
        total_tokens=tokens * 2,
    )


def _attempt(**overrides):
    values = {
        "operation_id": "operation-1",
        "attempt_index": 1,
        "model_id": "model-a",
        "provider_id": "provider-a",
        "trigger": ModelFallbackTrigger.TIMEOUT,
        "success": True,
        "estimated_cost": Decimal(0),
    }
    values.update(overrides)
    return ModelAttemptResult(**values)


def test_assembler_resolves_actual_currency_and_rejects_mismatch():
    actual = _estimate("EUR", "0")
    result = ModelExecutionRecordAssembler.from_attempt(
        _attempt(),
        record_id="mer-currency",
        agent_run_id="run-1",
        estimate=None,
        actual=actual,
    )
    assert result.currency == "EUR"
    assert result.actual_cost == Decimal(0)
    with pytest.raises(InvalidModelExecutionRecordError):
        ModelExecutionRecordAssembler.from_attempt(
            _attempt(),
            record_id="mer-mismatch",
            agent_run_id="run-1",
            estimate=_estimate("USD", "1"),
            actual=actual,
        )


def test_assembler_preserves_canonical_enum_values_and_context_references():
    result = ModelExecutionRecordAssembler.from_attempt(
        _attempt(),
        record_id="mer-context",
        agent_run_id="run-1",
        fallback_action=ModelFallbackAction.REROUTE,
        fallback_from="model-old",
        budget_id="budget-1",
        reservation_id="reservation-1",
        economic_decision="allow",
        economic_reason_codes=("within_budget",),
        validation_result_ids=("validation-1",),
        validation_status="accepted",
        validation_blocking_count=0,
        validation_warning_count=1,
        quality_evaluation=QualityEvaluation(score=Decimal("0.9")),
        causation_id="cause-1",
        content_reference=ModelExecutionContentReference("trace-ref", kind="trace"),
        content_retention=ContentRetentionMode.TRACE_REFERENCE,
        exclusion_reasons=("prompt_not_retained",),
        privacy_policy_version="privacy-2",
        fallback_trigger=ModelFallbackTrigger.TIMEOUT,
    )
    payload = result.to_dict()
    assert payload["fallback_trigger"] == "timeout"
    assert payload["fallback_action"] == "reroute"
    assert payload["economic_decision"] == "allow"
    assert ModelExecutionRecord.from_dict(payload) == result


def test_retention_invariants_are_fail_closed():
    with pytest.raises(InvalidModelExecutionRecordError):
        record(
            content_retention="hashes_only",
            content_reference=ModelExecutionContentReference("trace-ref"),
        )
    with pytest.raises(InvalidModelExecutionRecordError):
        record(content_retention="none", prompt_hash="a" * 64)
    with pytest.raises(InvalidModelExecutionRecordError):
        record(content_retention="authorized_payload_reference")


def test_pending_can_be_cancelled_and_failed_does_not_change_acceptance():
    service = ModelExecutionRecordService(InMemoryModelExecutionRecordRepository())
    cancelled = service.cancel_record(service.create_record(record(id="cancel-1")).id)
    assert cancelled.execution_status is ModelExecutionStatus.CANCELLED
    failed = service.fail_record(service.create_record(record(id="fail-1")).id)
    assert failed.execution_status is ModelExecutionStatus.FAILED
    assert failed.acceptance_status is AcceptanceStatus.PENDING


@pytest.mark.parametrize(
    "actual,expected,available",
    [
        (None, Decimal(0), False),
        (Decimal(0), Decimal(0), True),
        (Decimal("2.5"), Decimal("2.5"), True),
    ],
)
def test_observability_projector_preserves_actual_cost_availability(
    actual, expected, available
):
    projected = ModelExecutionObservabilityProjector(
        AgentObservabilityService()
    ).project(record(id=f"obs-{available}-{actual}", actual_cost=actual))
    assert projected.actual_cost == expected
    assert projected.metadata["actual_cost_available"] is available
    assert (
        projected.actual_cost
        != record(estimated_cost=Decimal(9), actual_cost=None).estimated_cost
    )


def test_event_bus_closed_is_best_effort_but_factory_errors_propagate():
    bus = AgentRuntimeEventBus()
    bus.close()
    service = ModelExecutionRecordService(
        InMemoryModelExecutionRecordRepository(), event_bus=bus
    )
    assert service.create_record(record(id="closed-1")).id == "closed-1"

    class InvalidFactory:
        def create_event(self, *args, **kwargs):
            raise InvalidModelExecutionRecordError("invalid event")

    failing = ModelExecutionRecordService(
        InMemoryModelExecutionRecordRepository(),
        event_bus=bus,
        event_factory=InvalidFactory(),
    )
    with pytest.raises(InvalidModelExecutionRecordError):
        failing.create_record(record(id="factory-1"))


class _CountingRepository(InMemoryModelExecutionRecordRepository):
    def __init__(self, *, fail_first_add=False):
        super().__init__()
        self.add_count = 0
        self._count_lock = Lock()
        self._fail_first_add = fail_first_add

    def add(self, value):
        with self._count_lock:
            self.add_count += 1
            should_fail = self._fail_first_add and self.add_count == 1
        if should_fail:
            raise RuntimeError("controlled add failure")
        return super().add(value)


def test_execution_record_preserves_effective_model_requirements():
    requirements = ModelRequirements(
        minimum_context_window=32768,
        reasoning=True,
        privacy="LOCAL_ONLY",
        allowed_providers=("provider-a",),
        maximum_input_cost_per_million=Decimal("1.50"),
    )
    attempt = _attempt()

    result = ModelExecutionRecordAssembler.from_attempt(
        attempt,
        record_id="requirements-trace",
        agent_run_id="run-requirements",
        effective_requirements=requirements,
    )

    assert result.effective_requirements == requirements
    assert result.to_dict()["effective_requirements"] == (
        model_requirements_to_dict(requirements)
    )
    assert ModelExecutionRecord.from_dict(result.to_dict()) == result


def test_idempotency_is_atomic_for_concurrent_identical_calls():
    repo = _CountingRepository()
    service = ModelExecutionRecordService(repo)
    value = record(id="atomic-1")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: service.create_record(value, idempotency_key="atomic-key"),
                range(2),
            )
        )
    assert results[0] == results[1] == value
    assert repo.add_count == 1
    assert repo._idempotency == {"atomic-key": ("atomic-1", value.fingerprint())}


def test_idempotency_conflicts_concurrently_without_duplicate_creation():
    repo = _CountingRepository()
    service = ModelExecutionRecordService(repo)
    values = [record(id="atomic-a"), record(id="atomic-b", model_id="model-b")]

    def call(value):
        try:
            return service.create_record(value, idempotency_key="conflict-key")
        except ModelExecutionIdempotencyConflictError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(call, values))
    assert sum(isinstance(result, ModelExecutionRecord) for result in results) == 1
    assert (
        sum(
            isinstance(result, ModelExecutionIdempotencyConflictError)
            for result in results
        )
        == 1
    )
    assert repo.add_count == 1
    assert len(repo) == 1


def test_failed_add_does_not_leave_idempotency_mapping_and_retry_succeeds():
    repo = _CountingRepository(fail_first_add=True)
    service = ModelExecutionRecordService(repo)
    value = record(id="retry-after-add-failure")
    with pytest.raises(RuntimeError):
        service.create_record(value, idempotency_key="retry-key")
    assert repo._idempotency == {}
    assert service.create_record(value, idempotency_key="retry-key") == value
    assert repo.add_count == 2


def test_lifecycle_events_and_terminal_technical_transitions_are_exact():
    class Bus:
        def __init__(self):
            self.events = []

        def publish(self, event):
            self.events.append(event.header.event_type)

    bus = Bus()
    service = ModelExecutionRecordService(
        InMemoryModelExecutionRecordRepository(), event_bus=bus
    )
    service.cancel_record(service.create_record(record(id="cancel-event")).id)
    service.fail_record(service.create_record(record(id="fail-event")).id)
    service.complete_record(service.create_record(record(id="complete-event")).id)
    assert bus.events == [
        "model_execution.created",
        "model_execution.cancelled",
        "model_execution.created",
        "model_execution.failed",
        "model_execution.created",
        "model_execution.completed",
    ]
    completed = service.get_record("complete-event")
    assert completed is not None
    assert service.fail_record(completed.id) == completed
    assert service.cancel_record(completed.id) == completed
    failed = service.get_record("fail-event")
    assert failed is not None
    assert service.fail_record(failed.id) == failed
    assert service.complete_record(failed.id) == failed
