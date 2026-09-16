"""Phase 11.3 — the narrow application-owned idempotency seam.

Idempotency is part of a public *command* boundary, so Phase 11.3 owns exactly
one seam for it and nothing more:

- :class:`IdempotencyRecord` — the key, the canonical command fingerprint and
  the safe public response that was produced;
- :class:`IdempotencyRepository` — the two-method boundary protocol;
- :class:`InMemoryIdempotencyRepository` — one bounded, process-local,
  deterministic implementation;
- :func:`fingerprint_command` — the canonical fingerprint of a public command.

The fingerprint is SHA-256 over a canonical JSON document of the public command
semantics (``sort_keys``, compact separators, UTF-8).  It includes the API
version, operation, actor, session, expected revision, payload and metadata, and
excludes ``request_id`` and ``idempotency_key``: a retry of the same request
with a fresh request identity is the same command, while a reused key with
different content is not.

No durable store, no distributed lock, no transaction manager and no global
cache framework is introduced.  A same-key/same-record replay is a no-op; a
same-key/different-record repeat raises
:class:`~cmm.application.errors.IdempotencyConflictError`, and the stored record
is never overwritten.  When the repository is full the oldest inserted record
is evicted deterministically.

See ``docs/reference/phase-11-application-backend.md``.
"""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass
from typing import Protocol

from cmm.application.contracts import (
    MAX_IDEMPOTENCY_KEY_LENGTH,
    MAX_IDENTIFIER_LENGTH,
    ApplicationCommand,
    ApplicationResponse,
)
from cmm.application.errors import IdempotencyConflictError

__all__ = [
    "DEFAULT_IDEMPOTENCY_CAPACITY",
    "IdempotencyRecord",
    "IdempotencyRepository",
    "InMemoryIdempotencyRepository",
    "fingerprint_command",
]

#: Default bound of the in-memory repository.
DEFAULT_IDEMPOTENCY_CAPACITY = 1024

#: Public command fields that never identify the command itself.
_EXCLUDED_FINGERPRINT_FIELDS = ("request_id", "idempotency_key")


# ── Canonical fingerprint ────────────────────────────────────────────────────


def fingerprint_command(command: ApplicationCommand) -> str:
    """Return the canonical SHA-256 fingerprint of one public command.

    The digest is built from the command's public representation minus its
    request identity and idempotency key, using a canonical JSON encoding, so it
    is stable across processes and independent of mapping order or ``hash()``.
    """

    if not isinstance(command, ApplicationCommand):
        raise TypeError("command must be an ApplicationCommand")

    document = command.to_dict()
    for field_name in _EXCLUDED_FINGERPRINT_FIELDS:
        document.pop(field_name, None)

    canonical = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ── Record and repository boundary ───────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    """One idempotency key bound to a fingerprint and a safe response."""

    key: str
    fingerprint: str
    response: ApplicationResponse

    def __post_init__(self) -> None:
        if not isinstance(self.key, str):
            raise TypeError("key must be a string")
        normalized_key = self.key.strip()
        if not normalized_key:
            raise ValueError("key must be non-empty")
        if len(normalized_key) > MAX_IDEMPOTENCY_KEY_LENGTH:
            raise ValueError(
                f"key must not exceed {MAX_IDEMPOTENCY_KEY_LENGTH} characters"
            )
        object.__setattr__(self, "key", normalized_key)

        if not isinstance(self.fingerprint, str):
            raise TypeError("fingerprint must be a string")
        if not self.fingerprint.strip():
            raise ValueError("fingerprint must be non-empty")
        if len(self.fingerprint) > MAX_IDENTIFIER_LENGTH:
            raise ValueError(
                f"fingerprint must not exceed {MAX_IDENTIFIER_LENGTH} characters"
            )

        if not isinstance(self.response, ApplicationResponse):
            raise TypeError("response must be an ApplicationResponse")


class IdempotencyRepository(Protocol):
    """The bounded idempotency boundary: look up and store one record."""

    def get(self, key: str) -> IdempotencyRecord | None: ...

    def put(self, record: IdempotencyRecord) -> None: ...


def _require_key(key: object) -> str:
    if not isinstance(key, str):
        raise TypeError("key must be a string")
    return key


class InMemoryIdempotencyRepository:
    """Bounded, process-local idempotency repository.

    Eviction is deterministic and insertion-ordered (``OrderedDict`` order), so
    a full repository always drops the oldest inserted record and a replay never
    refreshes a key.  The implementation is deliberately not thread-safe and not
    durable: durable idempotency belongs to later storage work.
    """

    def __init__(self, capacity: int = DEFAULT_IDEMPOTENCY_CAPACITY) -> None:
        # ``bool`` is an ``int`` subclass, so it is rejected explicitly: a
        # capacity of ``True`` is a caller defect, not a capacity of one.
        if isinstance(capacity, bool) or not isinstance(capacity, int):
            raise TypeError("capacity must be a positive int")
        if capacity < 1:
            raise ValueError("capacity must be a positive int")
        self._capacity = capacity
        self._records: OrderedDict[str, IdempotencyRecord] = OrderedDict()

    def get(self, key: str) -> IdempotencyRecord | None:
        """Return the stored record for *key*, or ``None`` when unknown."""

        return self._records.get(_require_key(key))

    def put(self, record: IdempotencyRecord) -> None:
        """Store *record*, replay it silently or fail closed on a conflict."""

        if not isinstance(record, IdempotencyRecord):
            raise TypeError("record must be an IdempotencyRecord")

        stored = self._records.get(record.key)
        if stored is not None:
            if stored != record:
                raise IdempotencyConflictError(
                    details={"reason_code": "IDEMPOTENCY_KEY_REUSED"}
                )
            return

        if len(self._records) >= self._capacity:
            self._records.popitem(last=False)
        self._records[record.key] = record
