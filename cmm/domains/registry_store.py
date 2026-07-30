"""Phase 10.3 – Registry Store.

Thread-safe, in-memory store for DomainRegistryRecord entries with deterministic indexing.

Provides the ``DomainRegistryStore`` protocol and the concrete
``InMemoryDomainRegistryStore`` implementation.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from functools import cmp_to_key
from typing import Protocol, runtime_checkable

from cmm.domains.enums import DomainKind, DomainStatus
from cmm.domains.errors import (
    DomainRegistryConflict,
    DomainRegistryNotFound,
)
from cmm.domains.registry_contracts import (
    DomainRegistryRecord,
    DomainRegistryStoreSnapshot,
    _canonical_slug,
    _compare_records,
)


def _canonical_version(version: str) -> str:
    from cmm.domains.registry_contracts import _SemanticVersion

    try:
        return str(_SemanticVersion(version))
    except Exception:  # noqa: BLE001  -- graceful fallback for non-semver versions
        return version


def _records_equal(a: DomainRegistryRecord, b: DomainRegistryRecord) -> bool:
    return a.to_dict() == b.to_dict()


@runtime_checkable
class DomainRegistryStore(Protocol):
    """Protocol for thread-safe domain registry record storage."""

    def add(self, record: DomainRegistryRecord) -> None: ...
    def replace(self, record: DomainRegistryRecord) -> None: ...
    def remove(self, domain_id: str, version: str) -> DomainRegistryRecord: ...
    def get(self, domain_id: str, version: str) -> DomainRegistryRecord | None: ...
    def list(self) -> tuple[DomainRegistryRecord, ...]: ...
    def find_by_capability(
        self, capability: str
    ) -> tuple[DomainRegistryRecord, ...]: ...
    def find_by_kind(self, kind: DomainKind) -> tuple[DomainRegistryRecord, ...]: ...
    def find_by_status(
        self, status: DomainStatus
    ) -> tuple[DomainRegistryRecord, ...]: ...
    def snapshot_state(self) -> DomainRegistryStoreSnapshot: ...
    def restore_state(self, snapshot: DomainRegistryStoreSnapshot) -> None: ...


@dataclass
class InMemoryDomainRegistryStore:
    """Thread-safe, in-memory implementation of ``DomainRegistryStore``.

    Stores ``DomainRegistryRecord`` objects indexed by (slug, version).
    Maintains secondary indices for capability, kind, and status.
    All public methods return defensive copies (no live views).
    """

    _lock: threading.RLock = field(
        default_factory=threading.RLock, init=False, repr=False
    )

    _entries: dict[tuple[str, str], DomainRegistryRecord] = field(
        default_factory=dict, init=False, repr=False
    )
    _by_capability: dict[str, set[tuple[str, str]]] = field(
        default_factory=dict, init=False, repr=False
    )
    _by_kind: dict[DomainKind, set[tuple[str, str]]] = field(
        default_factory=dict, init=False, repr=False
    )
    _by_status: dict[DomainStatus, set[tuple[str, str]]] = field(
        default_factory=dict, init=False, repr=False
    )

    def _add_to_indices(
        self, key: tuple[str, str], record: DomainRegistryRecord
    ) -> None:
        for cap in record.definition.capabilities:
            self._by_capability.setdefault(cap.name, set()).add(key)
        self._by_kind.setdefault(record.definition.kind, set()).add(key)
        self._by_status.setdefault(record.status, set()).add(key)

    def _remove_from_indices(
        self, key: tuple[str, str], record: DomainRegistryRecord
    ) -> None:
        for cap in record.definition.capabilities:
            cap_set = self._by_capability.get(cap.name)
            if cap_set is not None:
                cap_set.discard(key)
                if not cap_set:
                    del self._by_capability[cap.name]
        kind_set = self._by_kind.get(record.definition.kind)
        if kind_set is not None:
            kind_set.discard(key)
            if not kind_set:
                del self._by_kind[record.definition.kind]
        status_set = self._by_status.get(record.status)
        if status_set is not None:
            status_set.discard(key)
            if not status_set:
                del self._by_status[record.status]

    # ── Public API ─────────────────────────────────────────────────────────

    def add(self, record: DomainRegistryRecord) -> None:
        key = (
            _canonical_slug(record.definition.id.slug),
            _canonical_version(record.definition.version),
        )
        with self._lock:
            if key in self._entries:
                existing = self._entries[key]
                if _records_equal(record, existing):
                    return  # idempotent
                raise DomainRegistryConflict(
                    f"Duplicate identity ({key[0]}, {key[1]}) with different content",
                    field="record",
                    details={"domain_id": key[0], "version": key[1]},
                )
            self._entries[key] = record
            self._add_to_indices(key, record)

    def replace(self, record: DomainRegistryRecord) -> None:
        key = (
            _canonical_slug(record.definition.id.slug),
            _canonical_version(record.definition.version),
        )
        with self._lock:
            if key not in self._entries:
                raise DomainRegistryNotFound(
                    f"Entry not found for replace: ({key[0]}, {key[1]})",
                    field="record",
                    details={"domain_id": key[0], "version": key[1]},
                )
            old = self._entries[key]
            self._remove_from_indices(key, old)
            self._entries[key] = record
            self._add_to_indices(key, record)

    def remove(self, domain_id: str, version: str) -> DomainRegistryRecord:
        slug = _canonical_slug(domain_id)
        ver = _canonical_version(version)
        key = (slug, ver)
        with self._lock:
            if key not in self._entries:
                raise DomainRegistryNotFound(
                    f"Entry not found: ({slug}, {ver})",
                    field="domain_id",
                    details={"domain_id": slug, "version": ver},
                )
            record = self._entries.pop(key)
            self._remove_from_indices(key, record)
            return record

    def get(self, domain_id: str, version: str) -> DomainRegistryRecord | None:
        slug = _canonical_slug(domain_id)
        ver = _canonical_version(version)
        key = (slug, ver)
        with self._lock:
            return self._entries.get(key)

    def list(self) -> tuple[DomainRegistryRecord, ...]:
        with self._lock:
            entries = list(self._entries.values())
            entries.sort(key=cmp_to_key(_compare_records))
            return tuple(entries)

    def find_by_capability(self, capability: str) -> tuple[DomainRegistryRecord, ...]:
        with self._lock:
            keys = self._by_capability.get(capability, set())
            result = [self._entries[k] for k in keys if k in self._entries]
            result.sort(key=cmp_to_key(_compare_records))
            return tuple(result)

    def find_by_kind(self, kind: DomainKind) -> tuple[DomainRegistryRecord, ...]:
        with self._lock:
            keys = self._by_kind.get(kind, set())
            result = [self._entries[k] for k in keys if k in self._entries]
            result.sort(key=cmp_to_key(_compare_records))
            return tuple(result)

    def find_by_status(self, status: DomainStatus) -> tuple[DomainRegistryRecord, ...]:
        with self._lock:
            keys = self._by_status.get(status, set())
            result = [self._entries[k] for k in keys if k in self._entries]
            result.sort(key=cmp_to_key(_compare_records))
            return tuple(result)

    def snapshot_state(self) -> DomainRegistryStoreSnapshot:
        """Capture full store state for atomic rollback."""
        with self._lock:
            return DomainRegistryStoreSnapshot(records=tuple(self._entries.values()))

    def restore_state(self, snapshot: DomainRegistryStoreSnapshot) -> None:
        """Restore full store state from a snapshot."""
        with self._lock:
            self._entries.clear()
            self._by_capability.clear()
            self._by_kind.clear()
            self._by_status.clear()
            for record in snapshot.records:
                key = (
                    _canonical_slug(record.definition.id.slug),
                    _canonical_version(record.definition.version),
                )
                self._entries[key] = record
                self._add_to_indices(key, record)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._by_capability.clear()
            self._by_kind.clear()
            self._by_status.clear()


__all__ = [
    "DomainRegistryStore",
    "InMemoryDomainRegistryStore",
]
