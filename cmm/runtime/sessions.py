"""Shared Session Infrastructure — generic persistent session authority.

Owned by ``cmm.runtime`` (outside any specific subsystem). Provides:

- ``SharedSessionState``: immutable, JSON-safe, revisioned session envelope
  carrying typed generic ``extensions`` plus an append-only ``change_history``.
- ``SessionStore`` protocol: load/save boundary with optimistic revision
  checking (guards against lost updates).
- ``FileSessionStore``: durable, atomic, process-restart-safe file-backed
  implementation (write-to-temp + atomic replace).
- ``InMemorySessionStore``: test/embedding backing that can be shared across
  service instances to demonstrate restart boundaries.

Dependency direction (mandatory): subsystems depend on this shared
infrastructure; this module never imports any subsystem — it is generic and
knows nothing about specific extension contents.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol

__all__ = [
    "FileSessionStore",
    "InMemorySessionStore",
    "SessionNotFoundError",
    "SessionPersistenceError",
    "SessionStore",
    "SharedSessionChange",
    "SharedSessionState",
]


class SessionPersistenceError(RuntimeError):
    """Raised when shared session persistence fails (corruption, IO, conflict)."""


class SessionNotFoundError(SessionPersistenceError):
    """Raised when a referenced shared session does not exist."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_tz(dt: datetime, field_name: str) -> datetime:
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return dt


def _freeze(value: Any) -> Any:
    """Recursively freeze JSON-safe values into immutable containers."""
    if isinstance(value, Mapping):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    return value


def _unfreeze(value: Any) -> Any:
    """Recursively convert immutable containers back to JSON-native ones."""
    if isinstance(value, Mapping):
        return {k: _unfreeze(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_unfreeze(v) for v in value]
    return value


def _validate_json_safe(value: Any, field_name: str) -> None:
    """Ensure value can be serialized with ``json.dumps(..., allow_nan=False)``."""
    try:
        json.dumps(_unfreeze(value), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be JSON-safe: {exc}") from exc


@dataclass(frozen=True, slots=True)
class SharedSessionChange:
    """Append-only history entry for a shared session revision change."""

    from_revision: int
    to_revision: int
    reason: str = "update"
    occurred_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if isinstance(self.from_revision, bool) or not isinstance(
            self.from_revision, int
        ):
            raise TypeError("from_revision must be an int")
        if isinstance(self.to_revision, bool) or not isinstance(self.to_revision, int):
            raise TypeError("to_revision must be an int")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be a non-empty string")
        object.__setattr__(self, "reason", self.reason.strip())
        object.__setattr__(
            self, "occurred_at", _ensure_tz(self.occurred_at, "occurred_at")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_revision": self.from_revision,
            "to_revision": self.to_revision,
            "reason": self.reason,
            "occurred_at": self.occurred_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SharedSessionChange:
        return cls(
            from_revision=data["from_revision"],
            to_revision=data["to_revision"],
            reason=data["reason"],
            occurred_at=datetime.fromisoformat(data["occurred_at"]),
        )


@dataclass(frozen=True, slots=True)
class SharedSessionState:
    """Immutable, revisioned, JSON-safe shared session envelope.

    ``extensions`` carries typed subsystem extensions (e.g.
    ``{"domain_session": {...}}``) — the shared surface stays generic and
    never interprets extension contents.
    """

    session_id: str
    status: str = "ACTIVE"
    extensions: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    revision: int = 0
    change_history: tuple[SharedSessionChange, ...] = ()
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not isinstance(self.session_id, str) or not self.session_id.strip():
            raise ValueError("session_id must be a non-empty string")
        object.__setattr__(self, "session_id", self.session_id.strip())
        if not isinstance(self.status, str) or not self.status.strip():
            raise ValueError("status must be a non-empty string")
        object.__setattr__(self, "status", self.status.strip())
        if isinstance(self.revision, bool) or not isinstance(self.revision, int):
            raise TypeError("revision must be an int")
        if self.revision < 0:
            raise ValueError("revision must be >= 0")
        _validate_json_safe(self.extensions, "extensions")
        object.__setattr__(self, "extensions", _freeze(dict(self.extensions)))
        object.__setattr__(self, "change_history", tuple(self.change_history))
        object.__setattr__(
            self, "created_at", _ensure_tz(self.created_at, "created_at")
        )
        object.__setattr__(
            self, "updated_at", _ensure_tz(self.updated_at, "updated_at")
        )

    # ── helpers ──────────────────────────────────────────────────────────────

    def with_status(self, status: str) -> SharedSessionState:
        """Return a copy with a new lifecycle status and a pending revision bump."""
        return replace(self, status=status)

    def with_extension(
        self, key: str, payload: Mapping[str, Any], *, reason: str = "extension"
    ) -> SharedSessionState:
        """Return a copy with a (replaced) extension payload.

        The revision is bumped by the store on commit, not here — this keeps
        this dataclass pure and lets the store enforce optimistic concurrency.
        """
        if not isinstance(key, str) or not key.strip():
            raise ValueError("extension key must be a non-empty string")
        _validate_json_safe(payload, f"extensions[{key!r}]")
        new_exts = dict(self.extensions)
        new_exts[key] = _unfreeze(_freeze(dict(payload)))
        return replace(
            self,
            extensions=MappingProxyType(new_exts),
            updated_at=_utc_now(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "status": self.status,
            "extensions": _unfreeze(self.extensions),
            "revision": self.revision,
            "change_history": [c.to_dict() for c in self.change_history],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SharedSessionState:
        if not isinstance(data, Mapping):
            raise TypeError("SharedSessionState.from_dict requires a mapping")
        return cls(
            session_id=data["session_id"],
            status=data.get("status", "ACTIVE"),
            extensions=dict(data.get("extensions", {})),
            revision=data.get("revision", 0),
            change_history=tuple(
                SharedSessionChange.from_dict(c) for c in data.get("change_history", ())
            ),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if "created_at" in data
                else _utc_now()
            ),
            updated_at=(
                datetime.fromisoformat(data["updated_at"])
                if "updated_at" in data
                else _utc_now()
            ),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), allow_nan=False, sort_keys=True)

    @classmethod
    def from_json(cls, raw: str) -> SharedSessionState:
        return cls.from_dict(json.loads(raw))


class SessionStore(Protocol):
    """Persistence boundary protocol for shared sessions.

    Implementations must:
    - persist durably (survive process restart);
    - commit atomically (no partial states on disk);
    - enforce optimistic revision checking on save (reject stale writers);
    - assign monotonic revisions server-side.
    """

    def load(self, session_id: str) -> SharedSessionState | None: ...

    def save(self, state: SharedSessionState) -> SharedSessionState: ...


def _commit(
    state: SharedSessionState, existing: SharedSessionState | None
) -> SharedSessionState:
    """Compute the committed state with revision bump and history append."""
    if existing is not None:
        if state.revision != existing.revision:
            raise SessionPersistenceError(
                "Revision conflict: expected "
                f"{existing.revision} but got {state.revision} for session "
                f"'{state.session_id}'"
            )
        from_rev = existing.revision
    else:
        from_rev = 0
    change = SharedSessionChange(
        from_revision=from_rev,
        to_revision=from_rev + 1,
        reason=f"status:{state.status}",
    )
    return replace(
        state,
        revision=from_rev + 1,
        change_history=state.change_history + (change,),
        updated_at=_utc_now(),
    )


class FileSessionStore:
    """Durable file-backed shared session store with atomic writes.

    One JSON file per session under ``root``. Writes go to a temp file then
    ``os.replace`` (atomic on POSIX and Windows), making completed revisions
    durable and crash-safe across process restarts.
    """

    def __init__(self, root: Path | None) -> None:
        self._root = Path(root) if root is not None else None

    def _path_for(self, session_id: str) -> Path:
        if self._root is None:
            raise SessionPersistenceError("FileSessionStore requires a root directory")
        # Defensive: never let a session id escape the store root
        if "/" in session_id or "\\" in session_id or session_id in (".", ".."):
            raise SessionPersistenceError("Invalid session id")
        return self._root / f"{session_id}.json"

    def load(self, session_id: str) -> SharedSessionState | None:
        path = self._path_for(session_id)
        if not path.exists():
            return None
        try:
            raw = path.read_text(encoding="utf-8")
            return SharedSessionState.from_json(raw)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise SessionPersistenceError(
                f"Corrupt shared session store entry for '{session_id}'"
            ) from exc

    def save(self, state: SharedSessionState) -> SharedSessionState:
        path = self._path_for(state.session_id)
        existing = self.load(state.session_id)
        committed = _commit(state, existing)
        try:
            self._root = self._root or Path(tempfile.mkdtemp(prefix="cmm-sessions-"))
            self._root.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                dir=str(self._root), prefix=".tmp-session-", suffix=".json"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(committed.to_json())
                os.replace(tmp_name, path)
            except BaseException:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise
        except OSError as exc:
            raise SessionPersistenceError(
                f"Failed to persist shared session '{state.session_id}'"
            ) from exc
        return committed


class InMemorySessionStore:
    """In-memory shared session store.

    Accepts an external ``backing`` dict so that independent service
    instances (simulating process restarts in tests) share one durable
    representation.
    """

    def __init__(self, backing: dict[str, SharedSessionState] | None = None) -> None:
        self._backing: dict[str, SharedSessionState] = (
            backing if backing is not None else {}
        )

    def load(self, session_id: str) -> SharedSessionState | None:
        return self._backing.get(session_id)

    def save(self, state: SharedSessionState) -> SharedSessionState:
        committed = _commit(state, self._backing.get(state.session_id))
        self._backing[state.session_id] = committed
        return committed
