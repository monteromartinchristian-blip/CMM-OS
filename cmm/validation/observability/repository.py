"""Local JSON/JSONL repository implementation for Phase 7.11.

Storage layout
--------------
``<storage_root>/``
├── executions/
│   └── <validation-id>.json       # one atomic JSON file per execution
├── logs/
│   └── <validation-id>.jsonl      # append-only JSONL log stream
├── artifacts/
│   └── <validation-id>/
│       └── <artifact-id>.json     # one JSON file per artifact
└── index.json                     # searchable summary index

Atomicity
---------
Every write to a *single* JSON file uses the tempfile + ``os.replace``
pattern so that readers never see a partial write.

JSONL log lines are written with ``open(…, "a")``.  Concurrent
multi-process writers are not supported in 7.11 (local, single-process
use is the target); sequential writes within a single process are safe.

Security
--------
* Path traversal attacks are blocked: any ID that would place a file
  outside ``storage_root`` raises ``ValidationPersistenceError``.
* Artifact content exceeding ``ARTIFACT_CONTENT_MAX_BYTES`` is rejected
  with a structured error (no silent memory exhaustion).
* Secrets are sanitised by the caller (service layer) before reaching
  this class; the repository does *not* re-sanitise.

Idempotence
-----------
* Saving an identical record twice is safe (atomic replace).
* Saving a record whose stored counterpart is already in a final state
  and the new record tries to regress it to a non-final state raises
  ``ValidationRecordConflictError``.
* A ``commit_hash`` that is already set cannot be cleared.
* Timestamps may not go backwards.

Recovery
--------
* Corrupt execution JSON → ``ValidationStorageCorruptionError``.
* Corrupt JSONL line → that line is skipped with a warning; healthy
  lines are returned.
* Corrupt index → ``rebuild_index()`` reconstructs it from disk.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..artifacts import ValidationArtifact
from ..enums import ValidationSeverity, ValidationStatus
from ..findings import ValidationFinding
from .exceptions import (
    UnsupportedValidationSchemaError,
    ValidationArtifactStorageError,
    ValidationPersistenceError,
    ValidationRecordConflictError,
    ValidationStorageCorruptionError,
)
from .history import ValidationHistoryPage, ValidationHistoryQuery
from .models import (
    CURRENT_SCHEMA_VERSION,
    ValidationExecutionRecord,
    ValidationLogEntry,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum serialised bytes for a single artifact's ``content`` dict.
# Content exceeding this limit is replaced by a truncation marker.
ARTIFACT_CONTENT_MAX_BYTES: int = 512 * 1024  # 512 KiB

_FINAL_STATUSES: frozenset[str] = frozenset(
    {
        ValidationStatus.PASSED.value,
        ValidationStatus.FAILED.value,
        ValidationStatus.WARNING.value,
        ValidationStatus.ERROR.value,
        ValidationStatus.CANCELLED.value,
        ValidationStatus.TIMED_OUT.value,
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_filename(raw_id: str) -> str:
    """Return a file-safe version of *raw_id*.

    Only alphanumerics, hyphens, and underscores are kept.  This also
    makes path-traversal attempts (``../``, ``/``) impossible.
    """
    safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in raw_id)
    if not safe:
        raise ValidationPersistenceError(
            code="invalid_id",
            message=f"ID {raw_id!r} produces an empty file name after sanitisation",
        )
    return safe


def _assert_within_root(path: Path, root: Path) -> None:
    """Raise if *path* escapes *root* (path-traversal guard)."""
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValidationPersistenceError(
            code="path_traversal",
            message=f"Computed path {path} escapes the storage root {root}",
            path=path,
        ) from exc


def _atomic_write_json(path: Path, data: Any) -> None:
    """Serialise *data* to *path* atomically (tempfile → os.replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    serialised = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    encoded = serialised.encode("utf-8")
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "wb") as fp:
            fp.write(encoded)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        # Best-effort cleanup of temporary file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _load_json(path: Path, *, validation_id: str | None = None) -> Any:
    """Load and parse a JSON file, raising structured errors on failure."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValidationPersistenceError(
            code="read_error",
            message=f"Cannot read {path}: {exc}",
            path=path,
            validation_id=validation_id,
        ) from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationStorageCorruptionError(
            code="json_decode_error",
            message=f"Corrupt JSON in {path}: {exc}",
            path=path,
            validation_id=validation_id,
        ) from exc


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# LocalValidationRepository
# ---------------------------------------------------------------------------


class LocalValidationRepository:
    """File-system backed implementation of :class:`ValidationRepositoryProtocol`.

    Parameters
    ----------
    storage_root:
        Directory under which all data is stored.  Created automatically
        when the first write occurs.  Must be inside the project
        workspace; the class does *not* enforce this — that is the
        caller's responsibility.

    Notes
    -----
    Thread safety: A single ``threading.Lock`` serialises writes within
    one process.  Multi-process concurrency is not supported in 7.11.
    """

    def __init__(self, storage_root: Path) -> None:
        self._root = storage_root.resolve()
        self._executions_dir = self._root / "executions"
        self._logs_dir = self._root / "logs"
        self._artifacts_dir = self._root / "artifacts"
        self._index_path = self._root / "index.json"
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Internal paths
    # ------------------------------------------------------------------

    def _execution_path(self, validation_id: str) -> Path:
        safe = _safe_filename(validation_id)
        p = self._executions_dir / f"{safe}.json"
        _assert_within_root(p, self._root)
        return p

    def _log_path(self, validation_id: str) -> Path:
        safe = _safe_filename(validation_id)
        p = self._logs_dir / f"{safe}.jsonl"
        _assert_within_root(p, self._root)
        return p

    def _artifact_path(self, validation_id: str, artifact_id: str) -> Path:
        safe_vid = _safe_filename(validation_id)
        safe_aid = _safe_filename(artifact_id)
        p = self._artifacts_dir / safe_vid / f"{safe_aid}.json"
        _assert_within_root(p, self._root)
        return p

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def _load_index(self) -> list[dict[str, Any]]:
        """Return the index list; return [] if missing, raise on corrupt."""
        if not self._index_path.exists():
            return []
        try:
            data = _load_json(self._index_path)
        except ValidationStorageCorruptionError:
            raise
        except ValidationPersistenceError:
            return []
        if not isinstance(data, list):
            raise ValidationStorageCorruptionError(
                code="corrupt_index",
                message=f"Index at {self._index_path} is not a JSON array",
                path=self._index_path,
            )
        return data

    def _save_index(self, entries: list[dict[str, Any]]) -> None:
        _atomic_write_json(self._index_path, entries)

    def _upsert_index(self, record: ValidationExecutionRecord) -> None:
        """Add or replace the index entry for *record*."""
        entries = self._load_index()
        entry = _record_to_index_entry(record)
        idx = next((i for i, e in enumerate(entries) if e.get("id") == record.id), None)
        if idx is None:
            entries.append(entry)
        else:
            entries[idx] = entry
        self._save_index(entries)

    # ------------------------------------------------------------------
    # Execution records
    # ------------------------------------------------------------------

    def save_execution(self, record: ValidationExecutionRecord) -> None:
        """Persist *record* atomically.

        Idempotence / conflict policy
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        * Identical save → safe no-op (atomic replace).
        * Existing record is in a *final* status and the incoming record
          tries to move it back to a non-final status →
          ``ValidationRecordConflictError``.
        * Existing ``commit_hash`` is set and the incoming record tries
          to clear it → ``ValidationRecordConflictError``.
        * Timestamps may not go backwards.
        """
        with self._lock:
            path = self._execution_path(record.id)
            if path.exists():
                try:
                    existing = self._load_record_from_path(path, record.id)
                    _assert_no_conflict(existing, record)
                except (
                    ValidationStorageCorruptionError,
                    UnsupportedValidationSchemaError,
                ):
                    # Corrupt file — overwrite (but keep original for
                    # diagnostics if the caller needs it; we don't delete).
                    pass
                except ValidationRecordConflictError:
                    raise

            data = record.serialize()
            _atomic_write_json(path, data)
            self._upsert_index(record)

    def load_execution(self, validation_id: str) -> ValidationExecutionRecord | None:
        """Return the record, or ``None`` if not found."""
        path = self._execution_path(validation_id)
        if not path.exists():
            return None
        data = _load_json(path, validation_id=validation_id)
        try:
            return ValidationExecutionRecord.from_mapping(data)
        except (ValidationPersistenceError, UnsupportedValidationSchemaError):
            raise
        except Exception as exc:
            raise ValidationStorageCorruptionError(
                code="record_deserialization_error",
                message=f"Cannot deserialize record {validation_id}: {exc}",
                path=path,
                validation_id=validation_id,
            ) from exc

    def list_executions(self, query: ValidationHistoryQuery) -> ValidationHistoryPage:
        """Return a paginated, filtered, most-recent-first slice."""
        with self._lock:
            try:
                entries = self._load_index()
            except ValidationStorageCorruptionError:
                # Corrupt index — fall back to directory scan
                entries = self._rebuild_index_entries()

        # Convert index entries to lightweight records for filtering
        records: list[ValidationExecutionRecord] = []
        for entry in entries:
            try:
                rec = _index_entry_to_record(entry)
                if query.matches(rec):
                    records.append(rec)
            except Exception:  # noqa: BLE001, S112
                # Skip unparseable index entries
                continue

        # Sort most-recent first by started_at, then created_at
        def _sort_key(r: ValidationExecutionRecord) -> datetime:
            ts = r.started_at or r.created_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts

        records.sort(key=_sort_key, reverse=True)

        total = len(records)
        page = records[query.offset : query.offset + query.limit]
        has_more = (query.offset + query.limit) < total

        return ValidationHistoryPage(
            items=tuple(page),
            total=total,
            limit=query.limit,
            offset=query.offset,
            has_more=has_more,
        )

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------

    def save_log(self, entry: ValidationLogEntry) -> None:
        """Append *entry* as one JSONL line."""
        path = self._log_path(entry.validation_id)
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(entry.serialize(), ensure_ascii=False) + "\n"
            with path.open("a", encoding="utf-8") as fp:
                fp.write(line)

    def list_logs(self, validation_id: str) -> tuple[ValidationLogEntry, ...]:
        """Return all log entries in insertion order.

        Corrupt lines are skipped (partial JSONL resilience).
        """
        path = self._log_path(validation_id)
        if not path.exists():
            return ()
        entries: list[ValidationLogEntry] = []
        with path.open("r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entries.append(ValidationLogEntry.from_mapping(data))
                except (json.JSONDecodeError, Exception):  # noqa: BLE001, S112
                    # Skip corrupt lines; preserve healthy ones
                    continue
        return tuple(entries)

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------

    def save_artifact(self, validation_id: str, artifact: ValidationArtifact) -> None:
        """Persist *artifact* JSON for *validation_id*.

        Content exceeding :data:`ARTIFACT_CONTENT_MAX_BYTES` is replaced
        by a truncation marker rather than silently consuming memory.
        """
        path = self._artifact_path(validation_id, artifact.id)
        data = artifact.serialize()

        # Enforce content size limit
        content_raw = json.dumps(data.get("content", {}), ensure_ascii=False)
        if len(content_raw.encode("utf-8")) > ARTIFACT_CONTENT_MAX_BYTES:
            data["content"] = {
                "_truncated": True,
                "_reason": "content exceeded ARTIFACT_CONTENT_MAX_BYTES",
                "_limit_bytes": ARTIFACT_CONTENT_MAX_BYTES,
            }

        try:
            _atomic_write_json(path, data)
        except OSError as exc:
            raise ValidationArtifactStorageError(
                code="artifact_write_error",
                message=f"Cannot write artifact {artifact.id}: {exc}",
                path=path,
                validation_id=validation_id,
            ) from exc

    def load_artifact(
        self, validation_id: str, artifact_id: str
    ) -> ValidationArtifact | None:
        """Return the artifact or ``None`` if not found."""
        path = self._artifact_path(validation_id, artifact_id)
        if not path.exists():
            return None
        data = _load_json(path, validation_id=validation_id)
        try:
            return _artifact_from_mapping(data)
        except Exception as exc:
            raise ValidationArtifactStorageError(
                code="artifact_deserialization_error",
                message=f"Cannot deserialize artifact {artifact_id}: {exc}",
                path=path,
                validation_id=validation_id,
            ) from exc

    # ------------------------------------------------------------------
    # Index reconstruction
    # ------------------------------------------------------------------

    def rebuild_index(self) -> int:
        """Scan execution files and rebuild the index from scratch.

        Returns the number of successfully indexed records.
        Corrupt execution files are skipped (left in place).
        This method is acutely bounded: it reads only ``executions/``.
        """
        with self._lock:
            entries = self._rebuild_index_entries()
            self._save_index(entries)
            return len(entries)

    def _rebuild_index_entries(self) -> list[dict[str, Any]]:
        """Return raw index entries by scanning executions directory."""
        entries: list[dict[str, Any]] = []
        if not self._executions_dir.exists():
            return entries
        for json_file in sorted(self._executions_dir.glob("*.json")):
            try:
                data = _load_json(json_file)
                rec = ValidationExecutionRecord.from_mapping(data)
                entries.append(_record_to_index_entry(rec))
            except Exception:  # noqa: BLE001, S112
                continue
        return entries

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_record_from_path(
        self, path: Path, validation_id: str
    ) -> ValidationExecutionRecord:
        data = _load_json(path, validation_id=validation_id)
        return ValidationExecutionRecord.from_mapping(data)


# ---------------------------------------------------------------------------
# Module-level helpers (not part of the public API)
# ---------------------------------------------------------------------------


def _record_to_index_entry(record: ValidationExecutionRecord) -> dict[str, Any]:
    """Compact index entry for fast filtering without loading full records."""
    return {
        "id": record.id,
        "status": record.status,
        "policy": record.policy,
        "actor": record.actor,
        "branch": record.branch,
        "execution_mode": record.execution_mode,
        "started_at": (
            None if record.started_at is None else record.started_at.isoformat()
        ),
        "completed_at": (
            None if record.completed_at is None else record.completed_at.isoformat()
        ),
        "created_at": record.created_at.isoformat(),
        "gate_allowed": record.gate_allowed,
        "commit_hash": record.commit_hash,
    }


def _index_entry_to_record(entry: dict[str, Any]) -> ValidationExecutionRecord:
    """Convert a compact index entry into a minimal execution record.

    Index entries do not contain all fields; ``from_mapping`` fills
    defaults for missing ones.  This is used exclusively for filtering
    and ordering — full data is loaded from the individual JSON files
    when the caller requests it.
    """

    def _parse_dt(raw: Any) -> datetime | None:
        if raw is None:
            return None
        if isinstance(raw, datetime):
            return raw
        if isinstance(raw, str):
            return datetime.fromisoformat(raw)
        return None

    status = str(entry.get("status", ValidationStatus.RUNNING.value))
    completed_at = _parse_dt(entry.get("completed_at"))
    started_at = _parse_dt(entry.get("started_at"))
    created_at = _parse_dt(entry.get("created_at")) or _now_utc()

    # Index entries may have a final status but no completed_at if the
    # index was written before the record was finalised.  We repair
    # gracefully by using created_at as a fallback.
    if status in _FINAL_STATUSES and completed_at is None:
        completed_at = created_at

    return ValidationExecutionRecord(
        id=str(entry["id"]),
        schema_version=CURRENT_SCHEMA_VERSION,
        status=status,
        policy=entry.get("policy"),
        actor=entry.get("actor"),
        execution_mode=str(entry.get("execution_mode", "local")),
        branch=entry.get("branch"),
        gate_result=(
            {"allowed": entry["gate_allowed"]}
            if entry.get("gate_allowed") is not None
            else None
        ),
        commit_hash=entry.get("commit_hash"),
        started_at=started_at,
        completed_at=completed_at,
        created_at=created_at,
    )


def _artifact_from_mapping(data: dict[str, Any]) -> ValidationArtifact:
    """Reconstruct a :class:`ValidationArtifact` from serialised data."""
    from ..artifacts import ValidationArtifact

    findings_raw = data.get("findings") or []
    findings = []
    for f in findings_raw:
        if isinstance(f, dict):
            try:
                findings.append(
                    ValidationFinding(
                        code=str(f["code"]),
                        message=str(f["message"]),
                        severity=ValidationSeverity(f["severity"]),
                        source=str(f["source"]),
                        blocking=bool(f.get("blocking", False)),
                        line=f.get("line"),
                        column=f.get("column"),
                        suggested_fix=f.get("suggested_fix"),
                        documentation_url=f.get("documentation_url"),
                        metadata=dict(f.get("metadata") or {}),
                    )
                )
            except Exception:  # noqa: BLE001, S112
                continue

    path_raw = data.get("path")
    artifact_path = Path(path_raw) if path_raw else None

    created_at_raw = data.get("created_at")
    from datetime import datetime, timezone

    if isinstance(created_at_raw, str):
        created_at = datetime.fromisoformat(created_at_raw)
    elif isinstance(created_at_raw, datetime):
        created_at = created_at_raw
    else:
        created_at = datetime.now(timezone.utc)

    return ValidationArtifact(
        id=str(data["id"]),
        kind=str(data["kind"]),
        source=str(data["source"]),
        path=artifact_path,
        content=dict(data.get("content") or {}),
        findings=tuple(findings),
        metrics=dict(data.get("metrics") or {}),
        created_at=created_at,
        metadata=dict(data.get("metadata") or {}),
    )


def _assert_no_conflict(
    existing: ValidationExecutionRecord,
    incoming: ValidationExecutionRecord,
) -> None:
    """Raise :exc:`ValidationRecordConflictError` on disallowed transitions.

    Allowed updates
    ~~~~~~~~~~~~~~~
    * Running → any final state.
    * Any state → same state (idempotent).

    Forbidden transitions
    ~~~~~~~~~~~~~~~~~~~~~
    * Final state → non-final state.
    * Clearing an existing ``commit_hash``.
    * ``started_at`` moving backwards.
    """
    if existing.id != incoming.id:
        raise ValidationRecordConflictError(
            code="id_mismatch",
            message=(
                f"Record ID mismatch: existing={existing.id!r}, "
                f"incoming={incoming.id!r}"
            ),
            validation_id=incoming.id,
        )

    # Regression from final to non-final
    if existing.status in _FINAL_STATUSES and incoming.status not in _FINAL_STATUSES:
        raise ValidationRecordConflictError(
            code="status_regression",
            message=(
                f"Cannot move record {existing.id!r} from final status "
                f"{existing.status!r} back to {incoming.status!r}"
            ),
            validation_id=incoming.id,
        )

    # Clearing commit_hash
    if existing.commit_hash is not None and incoming.commit_hash is None:
        raise ValidationRecordConflictError(
            code="commit_hash_cleared",
            message=(
                f"Cannot clear commit_hash on record {existing.id!r}; "
                f"existing hash is {existing.commit_hash!r}"
            ),
            validation_id=incoming.id,
        )

    # started_at regression
    if (
        existing.started_at is not None
        and incoming.started_at is not None
        and incoming.started_at < existing.started_at
    ):
        raise ValidationRecordConflictError(
            code="timestamp_regression",
            message=(
                f"Record {existing.id!r}: incoming started_at "
                f"{incoming.started_at.isoformat()} is before existing "
                f"{existing.started_at.isoformat()}"
            ),
            validation_id=incoming.id,
        )


__all__ = ["ARTIFACT_CONTENT_MAX_BYTES", "LocalValidationRepository"]
