"""Unit tests for Phase 7.11 — ValidationExecutionRecord and ValidationLogEntry.

Tests cover:
- Valid construction
- Invalid fields (id, schema_version, timestamps, status)
- Defensive copies
- Serialisation round-trip
- Schema version handling
- Gate/commit coherence
- Log entry fields and validation
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.validation.observability.exceptions import (
    UnsupportedValidationSchemaError,
    ValidationPersistenceError,
)
from cmm.validation.observability.models import (
    CURRENT_SCHEMA_VERSION,
    ValidationExecutionRecord,
    ValidationLogEntry,
    new_validation_id,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_record(**kwargs) -> ValidationExecutionRecord:
    now = _now()
    defaults = {
        "id": "validation-abc123",
        "schema_version": 1,
        "status": "passed",
        "completed_at": now,
        "started_at": now,
    }
    defaults.update(kwargs)
    return ValidationExecutionRecord(**defaults)


# ---------------------------------------------------------------------------
# new_validation_id
# ---------------------------------------------------------------------------


def test_new_validation_id_format() -> None:
    vid = new_validation_id()
    assert vid.startswith("validation-")
    assert len(vid) > len("validation-")


def test_new_validation_id_unique() -> None:
    ids = {new_validation_id() for _ in range(100)}
    assert len(ids) == 100


# ---------------------------------------------------------------------------
# ValidationExecutionRecord — valid construction
# ---------------------------------------------------------------------------


def test_record_basic_construction() -> None:
    now = _now()
    r = ValidationExecutionRecord(
        id="validation-test-001",
        schema_version=1,
        status="passed",
        started_at=now,
        completed_at=now,
    )
    assert r.id == "validation-test-001"
    assert r.schema_version == 1
    assert r.status == "passed"


def test_record_collections_are_tuples() -> None:
    r = ValidationExecutionRecord(
        id="validation-x",
        schema_version=1,
        status="passed",
        changed_files=["a.py", "b.py"],  # type: ignore[arg-type]
        affected_tests=["test_a"],
        step_results=[{"name": "lint"}],
        findings=[{"code": "F001"}],
        artifacts=[{"id": "art1"}],
        completed_at=_now(),
    )
    assert isinstance(r.changed_files, tuple)
    assert isinstance(r.affected_tests, tuple)
    assert isinstance(r.step_results, tuple)
    assert isinstance(r.findings, tuple)
    assert isinstance(r.artifacts, tuple)


def test_record_metadata_is_defensive_copy() -> None:
    original = {"key": "value"}
    r = ValidationExecutionRecord(
        id="validation-y",
        schema_version=1,
        status="passed",
        metadata=original,
        completed_at=_now(),
    )
    original["key"] = "mutated"
    assert r.metadata["key"] == "value"


def test_record_is_active_property() -> None:
    r = ValidationExecutionRecord(
        id="validation-running",
        schema_version=1,
        status="running",
    )
    assert r.is_active is True
    assert r.is_final is False


def test_record_is_final_property() -> None:
    r = _make_record(status="passed")
    assert r.is_final is True
    assert r.is_active is False


def test_record_gate_allowed_property_none_when_no_gate() -> None:
    r = _make_record()
    assert r.gate_allowed is None


def test_record_gate_allowed_property() -> None:
    r = _make_record(gate_result={"allowed": True})
    assert r.gate_allowed is True


def test_record_gate_denied_property() -> None:
    r = _make_record(gate_result={"allowed": False})
    assert r.gate_allowed is False


# ---------------------------------------------------------------------------
# ValidationExecutionRecord — invalid fields
# ---------------------------------------------------------------------------


def test_record_empty_id_raises() -> None:
    with pytest.raises(ValueError, match="id must not be empty"):
        ValidationExecutionRecord(
            id="",
            schema_version=1,
            status="passed",
            completed_at=_now(),
        )


def test_record_zero_schema_version_raises() -> None:
    with pytest.raises(ValueError, match="schema_version must be a positive integer"):
        ValidationExecutionRecord(
            id="validation-x",
            schema_version=0,
            status="passed",
            completed_at=_now(),
        )


def test_record_negative_schema_version_raises() -> None:
    with pytest.raises(ValueError, match="schema_version must be a positive integer"):
        ValidationExecutionRecord(
            id="validation-x",
            schema_version=-1,
            status="passed",
            completed_at=_now(),
        )


def test_record_future_schema_version_raises() -> None:
    future_version = CURRENT_SCHEMA_VERSION + 1
    with pytest.raises(UnsupportedValidationSchemaError):
        ValidationExecutionRecord(
            id="validation-x",
            schema_version=future_version,
            status="passed",
            completed_at=_now(),
        )


def test_record_empty_status_raises() -> None:
    with pytest.raises(ValueError, match="status must not be empty"):
        ValidationExecutionRecord(
            id="validation-x",
            schema_version=1,
            status="",
            completed_at=_now(),
        )


def test_record_completed_before_started_raises() -> None:
    t0 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2025, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="completed_at cannot be before started_at"):
        ValidationExecutionRecord(
            id="validation-x",
            schema_version=1,
            status="passed",
            started_at=t0,
            completed_at=t1,
        )


def test_record_final_status_requires_completed_at() -> None:
    with pytest.raises(ValueError, match="final status.*must have completed_at"):
        ValidationExecutionRecord(
            id="validation-x",
            schema_version=1,
            status="passed",
            completed_at=None,
        )


def test_record_running_does_not_require_completed_at() -> None:
    r = ValidationExecutionRecord(
        id="validation-x",
        schema_version=1,
        status="running",
    )
    assert r.completed_at is None


def test_record_commit_hash_coherence_with_gate() -> None:
    with pytest.raises(ValueError, match="commit_hash must be set"):
        ValidationExecutionRecord(
            id="validation-x",
            schema_version=1,
            status="passed",
            gate_result={"commit_created": True},
            commit_hash=None,
            completed_at=_now(),
        )


def test_record_commit_hash_coherence_passes_when_set() -> None:
    r = ValidationExecutionRecord(
        id="validation-x",
        schema_version=1,
        status="passed",
        gate_result={"commit_created": True},
        commit_hash="abc123",
        completed_at=_now(),
    )
    assert r.commit_hash == "abc123"


# ---------------------------------------------------------------------------
# Serialisation round-trip
# ---------------------------------------------------------------------------


def test_record_serialize_produces_dict() -> None:
    r = _make_record()
    d = r.serialize()
    assert isinstance(d, dict)
    assert d["id"] == r.id
    assert d["schema_version"] == r.schema_version
    assert d["status"] == r.status


def test_record_round_trip() -> None:
    now = _now()
    original = ValidationExecutionRecord(
        id="validation-roundtrip-001",
        schema_version=1,
        status="failed",
        policy="small_change",
        actor="human:christian",
        execution_mode="local",
        project_root="/workspace",
        branch="feature/test",
        base_commit="abc123",
        changed_files=("src/foo.py",),
        affected_tests=("tests/test_foo.py",),
        step_results=({"name": "lint", "status": "passed"},),
        findings=({"code": "F001"},),
        artifacts=({"id": "art1"},),
        metrics={"total_duration_ms": 1000},
        gate_result=None,
        commit_hash=None,
        started_at=now,
        completed_at=now,
        created_at=now,
        metadata={"custom": "data"},
    )
    payload = original.serialize()
    restored = ValidationExecutionRecord.from_mapping(payload)

    assert restored.id == original.id
    assert restored.schema_version == original.schema_version
    assert restored.status == original.status
    assert restored.policy == original.policy
    assert restored.actor == original.actor
    assert restored.branch == original.branch
    assert restored.changed_files == original.changed_files
    assert restored.affected_tests == original.affected_tests
    assert restored.metadata == original.metadata


def test_record_from_mapping_missing_schema_version_raises() -> None:
    with pytest.raises(ValidationPersistenceError, match="schema_version"):
        ValidationExecutionRecord.from_mapping(
            {"id": "validation-x", "status": "passed"}
        )


def test_record_from_mapping_future_version_raises() -> None:
    with pytest.raises(UnsupportedValidationSchemaError):
        ValidationExecutionRecord.from_mapping(
            {
                "id": "validation-x",
                "schema_version": CURRENT_SCHEMA_VERSION + 99,
                "status": "running",
            }
        )


# ---------------------------------------------------------------------------
# ValidationLogEntry — valid construction
# ---------------------------------------------------------------------------


def _make_log_entry(**kwargs) -> ValidationLogEntry:
    defaults = {
        "id": "log-abc",
        "validation_id": "validation-abc",
        "timestamp": _now(),
        "level": "info",
        "component": "validation.pipeline",
        "event": "validation.started",
        "message": "Validation started",
    }
    defaults.update(kwargs)
    return ValidationLogEntry(**defaults)


def test_log_entry_valid() -> None:
    entry = _make_log_entry()
    assert entry.level == "info"
    assert entry.validation_id == "validation-abc"


def test_log_entry_all_levels() -> None:
    for level in ("debug", "info", "warning", "error", "critical"):
        entry = _make_log_entry(level=level)
        assert entry.level == level


def test_log_entry_invalid_level_raises() -> None:
    with pytest.raises(ValueError, match="level must be one of"):
        _make_log_entry(level="trace")


def test_log_entry_empty_id_raises() -> None:
    with pytest.raises(ValueError, match="id must not be empty"):
        _make_log_entry(id="")


def test_log_entry_empty_validation_id_raises() -> None:
    with pytest.raises(ValueError, match="validation_id must not be empty"):
        _make_log_entry(validation_id="")


def test_log_entry_empty_event_raises() -> None:
    with pytest.raises(ValueError, match="event must not be empty"):
        _make_log_entry(event="")


def test_log_entry_empty_message_raises() -> None:
    with pytest.raises(ValueError, match="message must not be empty"):
        _make_log_entry(message="")


def test_log_entry_empty_component_raises() -> None:
    with pytest.raises(ValueError, match="component must not be empty"):
        _make_log_entry(component="")


def test_log_entry_negative_duration_raises() -> None:
    with pytest.raises(ValueError, match="duration_ms must be non-negative"):
        _make_log_entry(duration_ms=-1)


def test_log_entry_metadata_defensive_copy() -> None:
    meta = {"k": "v"}
    entry = _make_log_entry(metadata=meta)
    meta["k"] = "mutated"
    assert entry.metadata["k"] == "v"


def test_log_entry_serialization() -> None:
    entry = _make_log_entry(
        step_name="lint_check",
        duration_ms=842,
        status="passed",
        correlation_id="validation-abc",
    )
    d = entry.serialize()
    assert d["step_name"] == "lint_check"
    assert d["duration_ms"] == 842
    assert d["status"] == "passed"
    assert d["correlation_id"] == "validation-abc"


def test_log_entry_round_trip() -> None:
    entry = _make_log_entry(
        step_name="mypy_check",
        duration_ms=200,
        metadata={"extra": "data"},
    )
    payload = entry.serialize()
    restored = ValidationLogEntry.from_mapping(payload)
    assert restored.id == entry.id
    assert restored.validation_id == entry.validation_id
    assert restored.level == entry.level
    assert restored.event == entry.event
    assert restored.step_name == entry.step_name
    assert restored.duration_ms == entry.duration_ms
    assert restored.metadata == entry.metadata


def test_log_entry_naive_timestamp_gets_utc() -> None:
    naive_ts = datetime(2025, 6, 1, 12, 0, 0)  # noqa: DTZ001 - intentionally naive
    entry = ValidationLogEntry(
        id="log-x",
        validation_id="validation-x",
        timestamp=naive_ts,
        level="info",
        component="c",
        event="e",
        message="m",
    )
    assert entry.timestamp.tzinfo is not None


def test_log_entry_new_factory() -> None:
    entry = ValidationLogEntry.new(
        validation_id="validation-factory",
        level="warning",
        component="validation.security",
        event="validation.step.failed",
        message="Security check failed",
        step_name="bandit",
        duration_ms=500,
        status="failed",
        metadata={"rule": "B101"},
    )
    assert entry.id.startswith("log-")
    assert entry.validation_id == "validation-factory"
    assert entry.correlation_id == "validation-factory"
    assert entry.step_name == "bandit"


def test_log_temporal_order() -> None:
    """Entries created later should have a later or equal timestamp."""
    t1 = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2025, 1, 1, 10, 0, 1, tzinfo=timezone.utc)

    e1 = ValidationLogEntry(
        id="log-1",
        validation_id="v-1",
        timestamp=t1,
        level="info",
        component="c",
        event="validation.started",
        message="started",
    )
    e2 = ValidationLogEntry(
        id="log-2",
        validation_id="v-1",
        timestamp=t2,
        level="info",
        component="c",
        event="validation.completed",
        message="completed",
    )
    assert e1.timestamp < e2.timestamp
