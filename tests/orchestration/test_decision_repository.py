"""Phase 11.2 — orchestration decision repository tests.

The repository owns orchestration decision records only.  It is deliberately
narrow: no session, goal, workflow, memory, knowledge or event storage, no
files, no database and no migration.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from cmm.orchestration.contracts import (
    ExecutionRoute,
    IntentKind,
    OrchestrationChannel,
    OrchestrationDecisionRecord,
    PolicyDisposition,
)
from cmm.orchestration.decision_repository import (
    InMemoryOrchestrationDecisionRepository,
    OrchestrationDecisionRepository,
)
from cmm.orchestration.errors import DecisionPersistenceError


def _record(
    decision_id: str = "decision-1",
    *,
    request_id: str = "request-1",
    session_id: str | None = "session-1",
    reason_codes: tuple[str, ...] = ("ORCHESTRATION_ROUTED",),
    occurred_at: datetime | None = None,
) -> OrchestrationDecisionRecord:
    return OrchestrationDecisionRecord(
        decision_id=decision_id,
        request_id=request_id,
        session_id=session_id,
        channel=OrchestrationChannel.CONVERSATION,
        intent=IntentKind.QUESTION,
        execution_route=ExecutionRoute.DIRECT_RESPONSE,
        policy_disposition=PolicyDisposition.ALLOW_ROUTE,
        reason_codes=reason_codes,
        occurred_at=occurred_at or datetime(2026, 9, 16, tzinfo=timezone.utc),
    )


def test_repository_satisfies_its_protocol() -> None:
    assert isinstance(
        InMemoryOrchestrationDecisionRepository(), OrchestrationDecisionRepository
    )


def test_save_returns_the_stored_record() -> None:
    repository = InMemoryOrchestrationDecisionRepository()
    record = _record()

    stored = repository.save(record)

    assert stored == record
    assert repository.get("decision-1") == record


def test_save_rejects_a_non_record_payload() -> None:
    repository = InMemoryOrchestrationDecisionRepository()

    with pytest.raises(TypeError):
        repository.save(object())  # type: ignore[arg-type]


def test_get_returns_none_for_unknown_decision() -> None:
    repository = InMemoryOrchestrationDecisionRepository()

    assert repository.get("decision-missing") is None


def test_get_requires_a_decision_identifier() -> None:
    repository = InMemoryOrchestrationDecisionRepository()

    with pytest.raises(ValueError):
        repository.get("   ")


def test_get_by_request_id_resolves_the_decision() -> None:
    repository = InMemoryOrchestrationDecisionRepository()
    repository.save(_record())

    found = repository.get_by_request_id("request-1")

    assert found is not None
    assert found.decision_id == "decision-1"


def test_get_by_request_id_returns_none_for_unknown_request() -> None:
    repository = InMemoryOrchestrationDecisionRepository()

    assert repository.get_by_request_id("request-missing") is None


def test_list_for_session_returns_only_that_session() -> None:
    repository = InMemoryOrchestrationDecisionRepository()
    repository.save(_record("decision-1", request_id="request-1"))
    repository.save(
        _record("decision-2", request_id="request-2", session_id="session-2")
    )
    repository.save(_record("decision-3", request_id="request-3", session_id=None))

    assert [item.decision_id for item in repository.list_for_session("session-1")] == [
        "decision-1"
    ]
    assert repository.list_for_session("session-missing") == ()


def test_list_for_session_is_deterministically_ordered() -> None:
    repository = InMemoryOrchestrationDecisionRepository()
    repository.save(
        _record(
            "decision-b",
            request_id="request-b",
            occurred_at=datetime(2026, 9, 16, 10, 0, tzinfo=timezone.utc),
        )
    )
    repository.save(
        _record(
            "decision-a",
            request_id="request-a",
            occurred_at=datetime(2026, 9, 16, 9, 0, tzinfo=timezone.utc),
        )
    )

    assert [item.decision_id for item in repository.list_for_session("session-1")] == [
        "decision-a",
        "decision-b",
    ]


def test_list_for_session_requires_a_session_identifier() -> None:
    repository = InMemoryOrchestrationDecisionRepository()

    with pytest.raises(ValueError):
        repository.list_for_session("")


def test_identical_replay_is_idempotent() -> None:
    repository = InMemoryOrchestrationDecisionRepository()
    record = _record()

    first = repository.save(record)
    second = repository.save(_record())

    assert second == first
    assert len(repository.list_for_session("session-1")) == 1


def test_contradictory_decision_identity_fails_closed() -> None:
    repository = InMemoryOrchestrationDecisionRepository()
    repository.save(_record())

    with pytest.raises(DecisionPersistenceError) as captured:
        repository.save(_record(reason_codes=("SOMETHING_ELSE",)))

    assert captured.value.code == "DECISION_PERSISTENCE_ERROR"
    assert dict(captured.value.to_error_result().details) == {
        "decision_id": "decision-1"
    }


def test_contradictory_request_identity_fails_closed() -> None:
    repository = InMemoryOrchestrationDecisionRepository()
    repository.save(_record("decision-1", request_id="request-1"))

    with pytest.raises(DecisionPersistenceError):
        repository.save(_record("decision-2", request_id="request-1"))

    assert repository.get("decision-2") is None
    assert repository.get_by_request_id("request-1").decision_id == "decision-1"


def test_identical_replay_ignores_the_recording_timestamp() -> None:
    repository = InMemoryOrchestrationDecisionRepository()
    repository.save(_record(occurred_at=datetime(2026, 9, 16, tzinfo=timezone.utc)))

    stored = repository.save(
        _record(occurred_at=datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc))
    )

    assert stored.occurred_at == datetime(2026, 9, 16, tzinfo=timezone.utc)


def test_stored_records_are_immutable() -> None:
    repository = InMemoryOrchestrationDecisionRepository()
    repository.save(_record())

    first = repository.get("decision-1")
    second = repository.get("decision-1")

    assert first is not None and second is not None
    assert first.to_dict() == second.to_dict()
    with pytest.raises((AttributeError, TypeError)):
        first.decision_id = "mutated"  # type: ignore[misc]


def test_record_serialization_has_no_raw_request_or_reasoning_content() -> None:
    repository = InMemoryOrchestrationDecisionRepository()
    repository.save(_record())

    payload = repository.get("decision-1").to_dict()
    serialized = json.dumps(payload, sort_keys=True)

    for forbidden in (
        "chain_of_thought",
        "hidden_reasoning",
        "raw_reasoning",
        "prompt",
        "provider_payload",
        "credential",
        "secret",
        "request_text",
    ):
        assert forbidden not in serialized


def test_records_reject_raw_request_payload_by_shape() -> None:
    with pytest.raises(TypeError):
        OrchestrationDecisionRecord(
            decision_id="decision-1",
            request_id="request-1",
            channel=OrchestrationChannel.CONVERSATION,
            intent=IntentKind.QUESTION,
            execution_route=ExecutionRoute.DIRECT_RESPONSE,
            policy_disposition=PolicyDisposition.ALLOW_ROUTE,
            request_text="raw user request text",
        )


def test_records_reject_arbitrary_objects_in_reference_fields() -> None:
    with pytest.raises(TypeError):
        _record(reason_codes=({"raw": "object"},))  # type: ignore[arg-type]


def test_repository_holds_no_canonical_substrate() -> None:
    """The only new repository is orchestration decisions; nothing else is stored."""

    repository = InMemoryOrchestrationDecisionRepository()

    assert not any(
        hasattr(repository, attribute)
        for attribute in (
            "session_store",
            "goal_repository",
            "workflow_repository",
            "memory_repository",
            "knowledge_repository",
            "event_repository",
        )
    )


def test_repository_is_thread_safe_for_distinct_records() -> None:
    import threading

    repository = InMemoryOrchestrationDecisionRepository()
    errors: list[BaseException] = []

    def save(index: int) -> None:
        try:
            repository.save(_record(f"decision-{index}", request_id=f"request-{index}"))
        except BaseException as error:  # noqa: BLE001 - recorded for the assertion
            errors.append(error)

    threads = [threading.Thread(target=save, args=(index,)) for index in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(repository.list_for_session("session-1")) == 16
