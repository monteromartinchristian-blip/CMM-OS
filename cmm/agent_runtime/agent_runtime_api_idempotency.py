"""Phase 9.21 – Agent Runtime API Idempotency Store.

Thread-safe in-memory idempotency support.
Same key + same payload returns cached result.
Same key + different payload produces conflict.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class IdempotencyEntry:
    """Stored idempotency result."""

    key: str
    fingerprint: str
    result: Any
    created_at: float = field(default_factory=time.time)


class AgentRuntimeApiIdempotencyStore:
    """Abstract idempotency store interface."""

    def get(self, key: str) -> IdempotencyEntry | None:
        raise NotImplementedError

    def store(self, key: str, fingerprint: str, result: Any) -> IdempotencyEntry:
        raise NotImplementedError

    def remove(self, key: str) -> IdempotencyEntry | None:
        raise NotImplementedError

    def cleanup(self, max_age_seconds: float) -> int:
        raise NotImplementedError


class InMemoryAgentRuntimeApiIdempotencyStore(AgentRuntimeApiIdempotencyStore):
    """Thread-safe in-memory idempotency store with configurable expiration."""

    def __init__(self, default_ttl_seconds: float = 300.0) -> None:
        if default_ttl_seconds <= 0:
            raise ValueError("default_ttl_seconds must be positive")
        self._store: dict[str, IdempotencyEntry] = {}
        self._lock = threading.RLock()
        self._default_ttl = default_ttl_seconds

    def get(self, key: str) -> IdempotencyEntry | None:
        if not key:
            return None
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            # Check TTL
            if time.time() - entry.created_at > self._default_ttl:
                del self._store[key]
                return None
            return entry

    def store(self, key: str, fingerprint: str, result: Any) -> IdempotencyEntry:
        if not key:
            raise ValueError("idempotency key cannot be empty")
        if not fingerprint:
            raise ValueError("fingerprint cannot be empty")
        with self._lock:
            entry = IdempotencyEntry(key=key, fingerprint=fingerprint, result=result)
            self._store[key] = entry
            return entry

    def remove(self, key: str) -> IdempotencyEntry | None:
        if not key:
            return None
        with self._lock:
            return self._store.pop(key, None)

    def clear(self, max_age_seconds: float | None = None) -> int:
        ttl = max_age_seconds if max_age_seconds is not None else self._default_ttl
        removed = 0
        with self._lock:
            now = time.time()
            expired = [k for k, v in self._store.items() if now - v.created_at > ttl]
            for k in expired:
                del self._store[k]
                removed += 1
        return removed

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._store)


def compute_fingerprint(operation: str, payload: dict[str, Any]) -> str:
    """Deterministic SHA256 fingerprint for idempotency matching."""
    if not operation:
        raise ValueError("operation cannot be empty")
    # Double JSON serialization with sort_keys for deterministic fingerprint
    # independent of key order
    normalized = json.dumps(
        {
            "operation": operation,
            "payload": json.dumps(payload, sort_keys=True),
        },
        sort_keys=True,
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
