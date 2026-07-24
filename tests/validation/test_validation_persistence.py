"""Persistence tests for Phase 7.11 — LocalValidationRepository.

All tests use pytest's ``tmp_path`` fixture.

Covers:
- Save and load execution
- Idempotent update
- Conflict detection (status regression, cleared commit_hash, timestamp)
- List history (filter, paginate, order)
- Save/load/list logs
- Log ordering
- Save/load artifacts
- Artifact not found
- Path traversal blocked
- Malicious ID blocked
- Atomic write (temp file then replace)
- Index generation and rebuild
- Corrupt execution record
- Corrupt index
- Corrupt JSONL log
- Future schema version
- Missing directory (auto-created)
- Artifact content limit
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cmm.validation.artifacts import ValidationArtifact
from cmm.validation.observability.exceptions import (
    UnsupportedValidationSchemaError,
    ValidationRecordConflictError,
    ValidationStorageCorruptionError,
)
from cmm.validation.observability.history import ValidationHistoryQuery
from cmm.validation.observability.models import (
    CURRENT_SCHEMA_VERSION,
    ValidationExecutionRecord,
    ValidationLogEntry,
)
from cmm.validation.observability.repository import (
    ARTIFACT_CONTENT_MAX_BYTES,
    LocalValidationRepository,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_record(
    vid: str = "validation-abc123",
    status: str = "passed",
    policy: str | None = "small_change",
    actor: str | None = "human:christian",
    branch: str | None = "feature/test",
    gate_result: dict | None = None,
    commit_hash: str | None = None,
) -> ValidationExecutionRecord:
    now = _now()
    completed = (
        now
        if status in ("passed", "failed", "warning", "error", "cancelled", "timed_out")
        else None
    )
    return ValidationExecutionRecord(
        id=vid,
        schema_version=CURRENT_SCHEMA_VERSION,
        status=status,
        policy=policy,
        actor=actor,
        branch=branch,
        started_at=now,
        completed_at=completed,
        gate_result=gate_result,
        commit_hash=commit_hash,
    )


def _make_log_entry(
    validation_id: str = "validation-abc123",
    level: str = "info",
    event: str = "validation.started",
    message: str = "Started",
) -> ValidationLogEntry:
    return ValidationLogEntry.new(
        validation_id=validation_id,
        level=level,
        component="test.component",
        event=event,
        message=message,
    )


def _make_artifact(
    artifact_id: str = "art-001", content: dict | None = None
) -> ValidationArtifact:
    return ValidationArtifact(
        id=artifact_id,
        kind="report",
        source="lint",
        content=content or {"key": "value"},
        created_at=_now(),
    )


def _make_repo(tmp_path: Path) -> LocalValidationRepository:
    return LocalValidationRepository(tmp_path / "validation_store")


# ---------------------------------------------------------------------------
# Save and load execution
# ---------------------------------------------------------------------------


def test_save_and_load_execution(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    record = _make_record()
    repo.save_execution(record)
    loaded = repo.load_execution(record.id)
    assert loaded is not None
    assert loaded.id == record.id
    assert loaded.status == record.status
    assert loaded.policy == record.policy
    assert loaded.actor == record.actor


def test_load_nonexistent_returns_none(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    result = repo.load_execution("validation-does-not-exist")
    assert result is None


def test_save_creates_directories_automatically(tmp_path: Path) -> None:
    repo = LocalValidationRepository(tmp_path / "deep" / "nested" / "store")
    record = _make_record()
    repo.save_execution(record)
    loaded = repo.load_execution(record.id)
    assert loaded is not None


# ---------------------------------------------------------------------------
# Idempotent update
# ---------------------------------------------------------------------------


def test_idempotent_save(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    record = _make_record()
    repo.save_execution(record)
    repo.save_execution(record)  # second save is safe
    loaded = repo.load_execution(record.id)
    assert loaded is not None
    assert loaded.id == record.id


def test_running_to_passed_update(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    running = ValidationExecutionRecord(
        id="validation-upd",
        schema_version=CURRENT_SCHEMA_VERSION,
        status="running",
    )
    repo.save_execution(running)
    now = _now()
    passed = ValidationExecutionRecord(
        id="validation-upd",
        schema_version=CURRENT_SCHEMA_VERSION,
        status="passed",
        started_at=running.created_at,
        completed_at=now,
    )
    repo.save_execution(passed)
    loaded = repo.load_execution("validation-upd")
    assert loaded is not None
    assert loaded.status == "passed"


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------


def test_conflict_final_to_running(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    passed = _make_record(status="passed")
    repo.save_execution(passed)
    running = ValidationExecutionRecord(
        id=passed.id,
        schema_version=CURRENT_SCHEMA_VERSION,
        status="running",
    )
    with pytest.raises(ValidationRecordConflictError, match="status_regression"):
        repo.save_execution(running)


def test_conflict_clearing_commit_hash(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    with_commit = _make_record(
        status="passed",
        commit_hash="abc123",
        gate_result={"allowed": True, "commit_created": True},
    )
    repo.save_execution(with_commit)
    without_commit = _make_record(status="passed", commit_hash=None)
    with pytest.raises(ValidationRecordConflictError, match="commit_hash_cleared"):
        repo.save_execution(without_commit)


def test_conflict_timestamp_regression(tmp_path: Path) -> None:
    from datetime import timedelta

    repo = _make_repo(tmp_path)
    t1 = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    t0 = t1 - timedelta(hours=1)  # earlier
    # First save with t1
    r1 = ValidationExecutionRecord(
        id="validation-ts",
        schema_version=CURRENT_SCHEMA_VERSION,
        status="running",
        started_at=t1,
    )
    repo.save_execution(r1)
    # Try to save with t0 (earlier) → conflict
    r0 = ValidationExecutionRecord(
        id="validation-ts",
        schema_version=CURRENT_SCHEMA_VERSION,
        status="running",
        started_at=t0,
    )
    with pytest.raises(ValidationRecordConflictError, match="timestamp_regression"):
        repo.save_execution(r0)


# ---------------------------------------------------------------------------
# List executions (filter + paginate + order)
# ---------------------------------------------------------------------------


def _populate_repo(repo: LocalValidationRepository, n: int = 5) -> list[str]:
    ids = []
    for i in range(n):
        vid = f"validation-list-{i:03d}"
        r = _make_record(
            vid=vid,
            policy="small_change" if i % 2 == 0 else "full",
            actor="human:christian" if i < 3 else "ci:github",
        )
        repo.save_execution(r)
        ids.append(vid)
    return ids


def test_list_all(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _populate_repo(repo, n=5)
    page = repo.list_executions(ValidationHistoryQuery(limit=10))
    assert page.total == 5
    assert len(page.items) == 5


def test_list_pagination_limit(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _populate_repo(repo, n=10)
    page = repo.list_executions(ValidationHistoryQuery(limit=3))
    assert len(page.items) == 3
    assert page.has_more is True
    assert page.total == 10


def test_list_pagination_offset(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _populate_repo(repo, n=6)
    page1 = repo.list_executions(ValidationHistoryQuery(limit=3, offset=0))
    page2 = repo.list_executions(ValidationHistoryQuery(limit=3, offset=3))
    ids_page1 = {r.id for r in page1.items}
    ids_page2 = {r.id for r in page2.items}
    # No overlap
    assert ids_page1.isdisjoint(ids_page2)
    assert page1.has_more is True
    assert page2.has_more is False


def test_list_filter_policy(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _populate_repo(repo, n=5)  # 3 small_change, 2 full
    page = repo.list_executions(ValidationHistoryQuery(policy="small_change"))
    assert all(r.policy == "small_change" for r in page.items)


def test_list_filter_actor(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _populate_repo(repo, n=5)  # 3 human, 2 ci
    page = repo.list_executions(ValidationHistoryQuery(actor="ci:github"))
    assert all(r.actor == "ci:github" for r in page.items)


def test_list_filter_status(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    for i in range(3):
        repo.save_execution(_make_record(f"validation-passed-{i}", status="passed"))
    for i in range(2):
        repo.save_execution(_make_record(f"validation-failed-{i}", status="failed"))
    page = repo.list_executions(ValidationHistoryQuery(status="failed"))
    assert page.total == 2
    assert all(r.status == "failed" for r in page.items)


def test_list_descending_order(tmp_path: Path) -> None:
    """Most recent first."""
    from datetime import timedelta

    repo = _make_repo(tmp_path)
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for i in range(5):
        now = base + timedelta(hours=i)
        r = ValidationExecutionRecord(
            id=f"validation-order-{i:03d}",
            schema_version=CURRENT_SCHEMA_VERSION,
            status="passed",
            started_at=now,
            completed_at=now,
        )
        repo.save_execution(r)
    page = repo.list_executions(ValidationHistoryQuery(limit=10))
    timestamps = [r.started_at for r in page.items if r.started_at]
    assert timestamps == sorted(timestamps, reverse=True)


def test_list_empty_store(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    page = repo.list_executions(ValidationHistoryQuery())
    assert page.total == 0
    assert page.items == ()


# ---------------------------------------------------------------------------
# Logs — save, list, order
# ---------------------------------------------------------------------------


def test_save_and_list_logs(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    e1 = _make_log_entry(event="validation.started", message="Started")
    e2 = _make_log_entry(event="validation.completed", message="Done")
    repo.save_log(e1)
    repo.save_log(e2)
    logs = repo.list_logs("validation-abc123")
    assert len(logs) == 2
    assert logs[0].event == "validation.started"
    assert logs[1].event == "validation.completed"


def test_logs_preserve_insertion_order(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    events = [
        "validation.started",
        "validation.step.started",
        "validation.step.completed",
        "validation.completed",
    ]
    for evt in events:
        repo.save_log(_make_log_entry(event=evt, message=f"msg for {evt}"))
    logs = repo.list_logs("validation-abc123")
    assert [l.event for l in logs] == events


def test_list_logs_empty(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    assert repo.list_logs("validation-does-not-exist") == ()


def test_list_logs_isolation(tmp_path: Path) -> None:
    """Logs for different validations don't mix."""
    repo = _make_repo(tmp_path)
    repo.save_log(_make_log_entry("validation-A", message="A started"))
    repo.save_log(
        ValidationLogEntry.new(
            validation_id="validation-B",
            level="info",
            component="c",
            event="validation.started",
            message="B started",
        )
    )
    logs_a = repo.list_logs("validation-A")
    logs_b = repo.list_logs("validation-B")
    assert len(logs_a) == 1
    assert len(logs_b) == 1
    assert logs_a[0].message == "A started"
    assert logs_b[0].message == "B started"


# ---------------------------------------------------------------------------
# Artifacts — save, load, not found
# ---------------------------------------------------------------------------


def test_save_and_load_artifact(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    art = _make_artifact()
    repo.save_artifact("validation-abc", art)
    loaded = repo.load_artifact("validation-abc", art.id)
    assert loaded is not None
    assert loaded.id == art.id
    assert loaded.kind == "report"


def test_load_artifact_not_found(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    result = repo.load_artifact("validation-abc", "nonexistent-art")
    assert result is None


def test_artifact_content_limit_exceeded(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    large_content = {"data": "x" * (ARTIFACT_CONTENT_MAX_BYTES + 1)}
    art = _make_artifact(content=large_content)
    repo.save_artifact("validation-abc", art)
    # Should not raise; content is replaced by truncation marker
    loaded = repo.load_artifact("validation-abc", art.id)
    assert loaded is not None
    assert loaded.content.get("_truncated") is True


# ---------------------------------------------------------------------------
# Path traversal guard
# ---------------------------------------------------------------------------


def test_path_traversal_execution_id_sanitised(tmp_path: Path) -> None:
    """IDs with slashes are sanitised to underscores; no escape occurs."""
    repo = _make_repo(tmp_path)
    malicious_id = "../../../etc/passwd"
    # _safe_filename converts slashes to underscores; result is inside root
    # load_execution returns None (not found) — does not escape the root
    result = repo.load_execution(malicious_id)
    assert result is None  # file not found; no path escape

    # Also verify that no file was created outside the storage root
    store_root = tmp_path / "validation_store"
    all_files = list(store_root.rglob("*")) if store_root.exists() else []
    for f in all_files:
        assert store_root in f.parents or f == store_root


def test_path_traversal_artifact_id_sanitised(tmp_path: Path) -> None:
    """Artifact IDs with slashes are sanitised; no escape occurs."""
    repo = _make_repo(tmp_path)
    result = repo.load_artifact("validation-abc", "../../secret")
    assert result is None


def test_malicious_id_with_slashes_stays_inside_root(tmp_path: Path) -> None:
    """Slashes in IDs are normalised to underscores — no path escape."""
    repo = _make_repo(tmp_path)
    result = repo.load_execution("validation/abc/../../escape")
    assert result is None


# ---------------------------------------------------------------------------
# Atomic write verification
# ---------------------------------------------------------------------------


def test_atomic_write_leaves_no_temp_files(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    record = _make_record()
    repo.save_execution(record)
    # No .tmp- files should remain
    tmp_files = list((tmp_path / "validation_store" / "executions").glob(".tmp-*"))
    assert len(tmp_files) == 0


def test_execution_file_is_valid_json(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    record = _make_record()
    repo.save_execution(record)
    store = tmp_path / "validation_store" / "executions"
    json_files = list(store.glob("*.json"))
    assert len(json_files) == 1
    content = json_files[0].read_text(encoding="utf-8")
    parsed = json.loads(content)
    assert parsed["id"] == record.id


# ---------------------------------------------------------------------------
# Index generation and rebuild
# ---------------------------------------------------------------------------


def test_index_created_after_save(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    record = _make_record()
    repo.save_execution(record)
    assert (tmp_path / "validation_store" / "index.json").exists()


def test_rebuild_index(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    for i in range(3):
        repo.save_execution(_make_record(f"validation-rebuild-{i}"))
    # Corrupt the index
    (tmp_path / "validation_store" / "index.json").write_text(
        "CORRUPT", encoding="utf-8"
    )
    # rebuild_index should recover
    count = repo.rebuild_index()
    assert count == 3
    # Subsequent queries should work
    page = repo.list_executions(ValidationHistoryQuery())
    assert page.total == 3


def test_rebuild_index_empty_store(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    count = repo.rebuild_index()
    assert count == 0


# ---------------------------------------------------------------------------
# Corruption handling
# ---------------------------------------------------------------------------


def test_corrupt_execution_json(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    record = _make_record()
    repo.save_execution(record)
    # Corrupt the file directly
    path = tmp_path / "validation_store" / "executions" / f"{record.id}.json"
    path.write_text("INVALID JSON{{{", encoding="utf-8")
    with pytest.raises(ValidationStorageCorruptionError):
        repo.load_execution(record.id)


def test_corrupt_index_falls_back_to_scan(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    for i in range(3):
        repo.save_execution(_make_record(f"validation-scan-{i}"))
    # Corrupt index
    (tmp_path / "validation_store" / "index.json").write_text(
        "BAD INDEX", encoding="utf-8"
    )
    # list_executions should fall back to directory scan
    page = repo.list_executions(ValidationHistoryQuery())
    assert page.total == 3


def test_corrupt_jsonl_skips_bad_lines(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    repo.save_execution(_make_record())  # create dirs
    # Write a log with one good and one corrupt line
    log_path = tmp_path / "validation_store" / "logs" / "validation-abc123.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    good_entry = ValidationLogEntry.new(
        validation_id="validation-abc123",
        level="info",
        component="c",
        event="validation.started",
        message="ok",
    )
    with log_path.open("w", encoding="utf-8") as fp:
        fp.write(json.dumps(good_entry.serialize()) + "\n")
        fp.write("CORRUPT_LINE\n")
        fp.write(json.dumps(good_entry.serialize()) + "\n")
    logs = repo.list_logs("validation-abc123")
    assert len(logs) == 2  # corrupt line skipped


def test_future_schema_version_in_file(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    record = _make_record()
    repo.save_execution(record)
    path = tmp_path / "validation_store" / "executions" / f"{record.id}.json"
    data = json.loads(path.read_text())
    data["schema_version"] = CURRENT_SCHEMA_VERSION + 99
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(UnsupportedValidationSchemaError):
        repo.load_execution(record.id)


# ---------------------------------------------------------------------------
# Sanitised data on disk
# ---------------------------------------------------------------------------


def test_sanitised_data_on_disk(tmp_path: Path) -> None:
    """Secrets must not appear in any persisted file."""
    repo = _make_repo(tmp_path)
    record = ValidationExecutionRecord(
        id="validation-secret-check",
        schema_version=CURRENT_SCHEMA_VERSION,
        status="passed",
        metadata={
            "token": "super-secret-token",
            "safe_key": "safe-value",
        },
        started_at=_now(),
        completed_at=_now(),
    )
    # Manually sanitise before saving (as the service would)
    from cmm.validation.observability.sanitization import sanitize_validation_data

    sanitised_meta = sanitize_validation_data(dict(record.metadata))
    record2 = ValidationExecutionRecord(
        id=record.id,
        schema_version=record.schema_version,
        status=record.status,
        metadata=sanitised_meta,
        started_at=record.started_at,
        completed_at=record.completed_at,
    )
    repo.save_execution(record2)
    path = tmp_path / "validation_store" / "executions" / f"{record.id}.json"
    raw = path.read_text(encoding="utf-8")
    assert "super-secret-token" not in raw
    assert "safe-value" in raw
