"""Phase 11.22 — durable event repository tests.

The durable repository is an *implementation* of the existing canonical
``AgentRuntimeEventRepository`` contract.  These tests prove the Phase 11.22
durability guarantees: canonical serialization, restart round-trip, deterministic
append order, correlation filtering, content-bound deduplication, fail-closed
corruption handling, bounded parent creation, restrictive permissions and no
unsafe deserialization.

Every test uses a temporary directory; nothing is written into the source tree or
a real user data location.
"""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timedelta, timezone

import pytest

from cmm.agent_runtime.runtime_event_contracts import AgentRuntimeEvent
from cmm.agent_runtime.runtime_event_errors import (
    AgentRuntimeEventIdentityConflictError,
    AgentRuntimeEventPersistenceCorruptionError,
    AgentRuntimeEventRepositoryError,
)
from cmm.agent_runtime.runtime_event_factory import (
    AgentRuntimeEventFactory,
    event_fingerprint,
)
from cmm.agent_runtime.runtime_event_repository import (
    FileAgentRuntimeEventRepository,
    InMemoryAgentRuntimeEventRepository,
)

OCCURRED = datetime(2024, 5, 1, 10, 0, 0, tzinfo=timezone.utc)


def make_event(
    *,
    event_id: str = "evt_1",
    event_type: str = "goal.created",
    occurred_at: datetime | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    producer: str | None = None,
    aggregate_id: str | None = None,
    payload: dict | None = None,
) -> AgentRuntimeEvent:
    factory = AgentRuntimeEventFactory()
    moment = occurred_at or OCCURRED
    return factory.create_event(
        event_type,
        payload if payload is not None else {"goal_id": "g1"},
        event_id=event_id,
        occurred_at=moment,
        emitted_at=moment,
        correlation_id=correlation_id,
        causation_id=causation_id,
        producer=producer,
        aggregate_id=aggregate_id,
    )


@pytest.fixture
def storage_path(tmp_path):
    return tmp_path / "events" / "runtime_events.jsonl"


# ── Contract conformance ─────────────────────────────────────────────────────


def test_durable_repository_implements_the_canonical_contract(storage_path) -> None:
    from cmm.agent_runtime import AgentRuntimeEventRepository

    repository = FileAgentRuntimeEventRepository(storage_path)

    assert isinstance(repository, AgentRuntimeEventRepository)


def test_durable_repository_path_is_the_configured_path(storage_path) -> None:
    repository = FileAgentRuntimeEventRepository(storage_path)

    assert repository.path == storage_path
    # The configured parent directory is created, and the storage file appears on
    # the first durable append rather than at construction time.
    assert storage_path.parent.is_dir()

    repository.save(make_event(event_id="evt_path"))
    assert storage_path.is_file()


# ── Round trip and ordering ──────────────────────────────────────────────────


def test_save_then_reopen_round_trips_every_event(storage_path) -> None:
    repository = FileAgentRuntimeEventRepository(storage_path)
    event = make_event(event_id="evt_rt", correlation_id="corr-1")
    repository.save(event)

    reopened = FileAgentRuntimeEventRepository(storage_path)
    restored = reopened.get("evt_rt")

    assert restored is not None
    assert restored.header.event_id == event.header.event_id
    assert restored.header.event_type == event.header.event_type
    assert restored.header.correlation_id == "corr-1"
    assert restored.payload.data == event.payload.data
    assert event_fingerprint(restored) == event_fingerprint(event)


def test_append_order_is_preserved_across_reopen(storage_path) -> None:
    repository = FileAgentRuntimeEventRepository(storage_path)
    moments = [OCCURRED - timedelta(hours=offset) for offset in range(3)]
    for index, moment in enumerate(moments):
        repository.save(make_event(event_id=f"evt_{index}", occurred_at=moment))

    reopened = FileAgentRuntimeEventRepository(storage_path)
    listed = reopened.list()

    # Insertion order, not occurred_at order: the third event has the oldest
    # timestamp but must still be last.
    assert [event.header.event_id for event in listed] == ["evt_0", "evt_1", "evt_2"]


def test_list_is_deterministic_and_supports_pagination(storage_path) -> None:
    repository = FileAgentRuntimeEventRepository(storage_path)
    for index in range(5):
        repository.save(make_event(event_id=f"evt_{index}"))

    assert [event.header.event_id for event in repository.list()] == [
        f"evt_{index}" for index in range(5)
    ]
    assert [event.header.event_id for event in repository.list(limit=2)] == [
        "evt_0",
        "evt_1",
    ]
    assert [event.header.event_id for event in repository.list(limit=2, offset=3)] == [
        "evt_3",
        "evt_4",
    ]


def test_query_filters_match_the_canonical_vocabulary(storage_path) -> None:
    repository = FileAgentRuntimeEventRepository(storage_path)
    repository.save(
        make_event(event_id="evt_a", event_type="goal.created", correlation_id="c1")
    )
    repository.save(
        make_event(event_id="evt_b", event_type="goal.updated", correlation_id="c2")
    )

    assert [e.header.event_id for e in repository.query(event_type="goal.created")] == [
        "evt_a"
    ]
    assert [e.header.event_id for e in repository.query(correlation_id="c2")] == [
        "evt_b"
    ]
    assert repository.count() == 2
    assert repository.count(event_type="goal.created") == 1
    assert repository.exists("evt_a")
    assert not repository.exists("evt_missing")
    assert repository.get("evt_missing") is None


def test_correlation_filtering_survives_reopen(storage_path) -> None:
    repository = FileAgentRuntimeEventRepository(storage_path)
    repository.save(make_event(event_id="evt_a", correlation_id="corr-keep"))
    repository.save(make_event(event_id="evt_b", correlation_id="corr-other"))

    reopened = FileAgentRuntimeEventRepository(storage_path)

    assert [
        event.header.event_id for event in reopened.query(correlation_id="corr-keep")
    ] == ["evt_a"]


def test_producer_and_aggregate_identity_survive_reopen(storage_path) -> None:
    repository = FileAgentRuntimeEventRepository(storage_path)
    repository.save(
        make_event(
            event_id="evt_p",
            event_type="message.received",
            producer="cmm.orchestration",
            aggregate_id="req-1",
        )
    )

    restored = FileAgentRuntimeEventRepository(storage_path).get("evt_p")

    assert restored is not None
    assert restored.header.producer == "cmm.orchestration"
    assert restored.header.aggregate_id == "req-1"


# ── Duplicate and conflict semantics ─────────────────────────────────────────


def test_identical_duplicate_is_idempotent_and_stores_no_second_record(
    storage_path,
) -> None:
    repository = FileAgentRuntimeEventRepository(storage_path)
    event = make_event(event_id="evt_dup")

    repository.save(event)
    repository.save(event)
    repository.save(make_event(event_id="evt_dup"))

    assert repository.count() == 1
    assert len(storage_path.read_text().strip().splitlines()) == 1


def test_same_id_with_different_content_fails_closed(storage_path) -> None:
    repository = FileAgentRuntimeEventRepository(storage_path)
    repository.save(make_event(event_id="evt_conflict", payload={"goal_id": "g1"}))

    with pytest.raises(AgentRuntimeEventIdentityConflictError):
        repository.save(make_event(event_id="evt_conflict", payload={"goal_id": "g2"}))

    # No mutation: the original record is intact and no second record was written.
    assert repository.count() == 1
    assert repository.get("evt_conflict").payload.data == {"goal_id": "g1"}
    assert len(storage_path.read_text().strip().splitlines()) == 1


def test_same_id_different_producer_fails_closed(storage_path) -> None:
    repository = FileAgentRuntimeEventRepository(storage_path)
    repository.save(make_event(event_id="evt_x", producer="cmm.orchestration"))

    with pytest.raises(AgentRuntimeEventIdentityConflictError):
        repository.save(make_event(event_id="evt_x", producer="cmm.domains"))


# ── Corruption fails closed ──────────────────────────────────────────────────


def test_malformed_json_fails_closed(storage_path) -> None:
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_text('{"header": {"event_id": "evt_1"')  # truncated JSON

    with pytest.raises(AgentRuntimeEventPersistenceCorruptionError):
        FileAgentRuntimeEventRepository(storage_path)


def test_truncated_line_after_valid_record_fails_closed(storage_path) -> None:
    repository = FileAgentRuntimeEventRepository(storage_path)
    repository.save(make_event(event_id="evt_1"))

    with storage_path.open("a", encoding="utf-8") as handle:
        handle.write('{"header": {"event_id": "evt_2"}\n')

    with pytest.raises(AgentRuntimeEventPersistenceCorruptionError):
        FileAgentRuntimeEventRepository(storage_path)


def test_record_that_is_not_a_canonical_event_fails_closed(storage_path) -> None:
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_text(
        json.dumps({"header": {"event_id": "evt_1"}, "payload": {"data": {}}}) + "\n"
    )

    with pytest.raises(AgentRuntimeEventPersistenceCorruptionError):
        FileAgentRuntimeEventRepository(storage_path)


def test_tampered_record_fails_its_fingerprint_check(storage_path) -> None:
    repository = FileAgentRuntimeEventRepository(storage_path)
    repository.save(make_event(event_id="evt_tamper"))

    record = json.loads(storage_path.read_text().strip())
    record["payload"]["data"] = {"goal_id": "g9"}
    storage_path.write_text(json.dumps(record) + "\n")

    with pytest.raises(AgentRuntimeEventPersistenceCorruptionError):
        FileAgentRuntimeEventRepository(storage_path)


def test_unsupported_record_schema_version_fails_closed(storage_path) -> None:
    repository = FileAgentRuntimeEventRepository(storage_path)
    repository.save(make_event(event_id="evt_version"))

    record = json.loads(storage_path.read_text().strip())
    record["record_schema_version"] = "9.9.9"
    storage_path.write_text(json.dumps(record) + "\n")

    with pytest.raises(AgentRuntimeEventPersistenceCorruptionError):
        FileAgentRuntimeEventRepository(storage_path)


def test_unsupported_event_schema_version_fails_closed(storage_path) -> None:
    repository = FileAgentRuntimeEventRepository(storage_path)
    repository.save(make_event(event_id="evt_schema"))

    record = json.loads(storage_path.read_text().strip())
    record["header"]["schema_version"] = "9.9.9"
    storage_path.write_text(json.dumps(record) + "\n")

    with pytest.raises(AgentRuntimeEventPersistenceCorruptionError):
        FileAgentRuntimeEventRepository(storage_path)


def test_duplicate_stored_event_id_fails_closed(storage_path) -> None:
    repository = FileAgentRuntimeEventRepository(storage_path)
    repository.save(make_event(event_id="evt_dupe_record"))

    line = storage_path.read_text().strip()
    storage_path.write_text(f"{line}\n{line}\n")

    with pytest.raises(AgentRuntimeEventPersistenceCorruptionError):
        FileAgentRuntimeEventRepository(storage_path)


def test_corruption_is_never_silently_skipped(storage_path) -> None:
    repository = FileAgentRuntimeEventRepository(storage_path)
    repository.save(make_event(event_id="evt_ok"))

    with storage_path.open("a", encoding="utf-8") as handle:
        handle.write("not json at all\n")

    # Reopening must fail rather than returning only the good record.
    with pytest.raises(AgentRuntimeEventPersistenceCorruptionError):
        FileAgentRuntimeEventRepository(storage_path)


# ── Append-only and deletion ─────────────────────────────────────────────────


def test_delete_is_refused_by_append_only_semantics(storage_path) -> None:
    repository = FileAgentRuntimeEventRepository(storage_path)
    repository.save(make_event(event_id="evt_1"))

    with pytest.raises(RuntimeError):
        repository.delete("evt_1")

    assert repository.count() == 1


def test_save_many_appends_in_order(storage_path) -> None:
    repository = FileAgentRuntimeEventRepository(storage_path)
    repository.save_many([make_event(event_id=f"evt_{index}") for index in range(4)])

    assert [event.header.event_id for event in repository.list()] == [
        f"evt_{index}" for index in range(4)
    ]


# ── Storage path behaviour ───────────────────────────────────────────────────


def test_parent_directory_is_created_only_for_the_configured_path(tmp_path) -> None:
    target = tmp_path / "a" / "b" / "c" / "events.jsonl"

    FileAgentRuntimeEventRepository(target)

    assert target.parent.is_dir()
    assert sorted(entry.name for entry in tmp_path.iterdir()) == ["a"]


def test_parent_creation_can_be_disabled(tmp_path) -> None:
    target = tmp_path / "missing" / "events.jsonl"

    with pytest.raises(AgentRuntimeEventRepositoryError):
        FileAgentRuntimeEventRepository(target, create_parents=False)


def test_unwritable_path_fails_safely(tmp_path) -> None:
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    os.chmod(blocked, 0o500)
    try:
        with pytest.raises(AgentRuntimeEventRepositoryError):
            FileAgentRuntimeEventRepository(blocked / "nested" / "events.jsonl")
    finally:
        os.chmod(blocked, 0o700)


def test_file_permissions_are_restrictive_where_supported(storage_path) -> None:
    repository = FileAgentRuntimeEventRepository(storage_path)
    repository.save(make_event(event_id="evt_perm"))

    mode = stat.S_IMODE(storage_path.stat().st_mode)

    # Owner read/write only; the group/other bits must never grant access.
    assert mode & 0o077 == 0, oct(mode)


def test_empty_path_is_rejected() -> None:
    with pytest.raises((ValueError, TypeError)):
        FileAgentRuntimeEventRepository("")


def test_repository_error_is_a_canonical_runtime_event_error(storage_path) -> None:
    from cmm.agent_runtime.runtime_event_errors import AgentRuntimeEventError

    assert issubclass(AgentRuntimeEventRepositoryError, AgentRuntimeEventError)
    assert issubclass(AgentRuntimeEventIdentityConflictError, AgentRuntimeEventError)
    assert issubclass(
        AgentRuntimeEventPersistenceCorruptionError, AgentRuntimeEventError
    )


# ── No unsafe deserialization ────────────────────────────────────────────────


def test_storage_module_uses_no_unsafe_deserialization() -> None:
    """Only ``json`` may deserialize stored evidence."""

    import ast
    from pathlib import Path

    module_path = (
        Path(__file__).resolve().parents[2]
        / "cmm"
        / "agent_runtime"
        / "runtime_event_repository.py"
    )
    tree = ast.parse(module_path.read_text())

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    for forbidden in ("pickle", "yaml", "marshal", "shelve", "dill"):
        assert forbidden not in imported, f"unsafe module {forbidden} imported"

    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    for forbidden_call in ("eval", "exec", "compile", "__import__"):
        assert forbidden_call not in called_names, f"unsafe call {forbidden_call} used"


def test_durable_and_in_memory_repositories_share_filter_semantics(
    storage_path,
) -> None:
    durable = FileAgentRuntimeEventRepository(storage_path)
    memory = InMemoryAgentRuntimeEventRepository()
    events = [
        make_event(event_id="evt_a", event_type="goal.created", correlation_id="c1"),
        make_event(event_id="evt_b", event_type="goal.updated", correlation_id="c2"),
    ]
    for event in events:
        durable.save(event)
        memory.save(event)

    for filters in (
        {"event_type": "goal.created"},
        {"correlation_id": "c2"},
        {"event_type": "goal.created", "correlation_id": "c1"},
    ):
        assert [e.header.event_id for e in durable.query(**filters)] == [
            e.header.event_id for e in memory.query(**filters)
        ]
