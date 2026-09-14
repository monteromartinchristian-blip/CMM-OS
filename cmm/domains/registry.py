"""Phase 10.3 – Domain Registry.

Thread-safe, deterministic, decoupled registry for DomainDefinition entries.

Lifecycle is stored in ``DomainRegistryRecord.status``, the single
authoritative source.  ``definition.enabled`` is derived from status.

Only the ``DomainRegistryStore`` protocol is used — no private store access.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from functools import cmp_to_key
from typing import TYPE_CHECKING

from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainStatus
from cmm.domains.errors import (
    DomainCapabilityConflict,
    DomainContractValidationError,
    DomainDependencyMissing,
    DomainRegistryConflict,
    DomainRegistryNotFound,
    DomainRegistryStateError,
)
from cmm.domains.registry_contracts import (
    DomainQuery,
    DomainRegistryRecord,
    DomainRegistrySnapshot,
    DomainRegistryStoreSnapshot,
    DomainValidationResult,
    _canonical_slug,
    _compare_records,
    _compare_versions_desc_safe,
    get_status_sort_priority,
    parse_semver,
)
from cmm.domains.registry_validation import DomainDefinitionRegistryValidator

if TYPE_CHECKING:
    from cmm.domains.registry_store import DomainRegistryStore


# ── Lifecycle helpers ──────────────────────────────────────────────────────────

_DEPENDENCY_SATISFYING_STATUSES: frozenset[DomainStatus] = frozenset(
    {DomainStatus.ACTIVE, DomainStatus.DEGRADED}
)

_NON_ENABLEABLE_STATUSES: frozenset[DomainStatus] = frozenset(
    {
        DomainStatus.INVALID,
        DomainStatus.FAILED,
        DomainStatus.INCOMPATIBLE,
        DomainStatus.UNLOADED,
    }
)

_NON_DISABLEABLE_STATUSES: frozenset[DomainStatus] = frozenset(
    {
        DomainStatus.INVALID,
        DomainStatus.FAILED,
        DomainStatus.UNLOADED,
    }
)


def _canonical_version(version: str) -> str:
    try:
        return str(parse_semver(version))
    except DomainContractValidationError:
        return version


def _make_record(
    definition: DomainDefinition, status: DomainStatus, *, now: datetime | None = None
) -> DomainRegistryRecord:
    ts = now or datetime.now(timezone.utc)
    return DomainRegistryRecord(
        definition=definition, status=status, registered_at=ts, updated_at=ts
    )


def _record_with_status(
    record: DomainRegistryRecord, status: DomainStatus, *, now: datetime | None = None
) -> DomainRegistryRecord:
    ts = now or datetime.now(timezone.utc)
    return DomainRegistryRecord(
        definition=record.definition,
        status=status,
        registered_at=record.registered_at,
        updated_at=ts,
    )


def _records_equal(a: DomainRegistryRecord, b: DomainRegistryRecord) -> bool:
    return a.definition.to_dict() == b.definition.to_dict() and a.status == b.status


# ── DomainRegistry ─────────────────────────────────────────────────────────────


class DomainRegistry:
    """Thread-safe, deterministic domain definition registry."""

    def __init__(
        self,
        store: DomainRegistryStore | None = None,
        validator: DomainDefinitionRegistryValidator | None = None,
    ) -> None:
        from cmm.domains.registry_store import InMemoryDomainRegistryStore

        self._lock = threading.RLock()
        self._store: DomainRegistryStore = (
            store if store is not None else InMemoryDomainRegistryStore()
        )
        self._validator = (
            validator if validator is not None else DomainDefinitionRegistryValidator()
        )

    def _active_version_key(self, slug: str) -> tuple[str, str] | None:
        records = self._store.list()
        for r in records:
            if (
                _canonical_slug(r.definition.id.slug) == slug
                and r.status == DomainStatus.ACTIVE
            ):
                return (
                    _canonical_slug(r.definition.id.slug),
                    _canonical_version(r.definition.version),
                )
        return None

    def _resolve_best_version(self, slug: str) -> tuple[str, str] | None:
        records = self._store.list()
        slug_records = [
            r for r in records if _canonical_slug(r.definition.id.slug) == slug
        ]
        if not slug_records:
            return None

        def compare(left: DomainRegistryRecord, right: DomainRegistryRecord) -> int:
            left_priority = get_status_sort_priority(left.status)
            right_priority = get_status_sort_priority(right.status)
            if left_priority != right_priority:
                return -1 if left_priority < right_priority else 1
            return _compare_versions_desc_safe(
                left.definition.version, right.definition.version
            )

        slug_records.sort(key=cmp_to_key(compare))
        best = slug_records[0]
        return (
            _canonical_slug(best.definition.id.slug),
            _canonical_version(best.definition.version),
        )

    # ── Public API ─────────────────────────────────────────────────────────

    def register(self, definition: DomainDefinition) -> DomainDefinition:
        slug = _canonical_slug(definition.id.slug)
        version = _canonical_version(definition.version)
        record = _make_record(definition, DomainStatus.REGISTERED)

        with self._lock:
            registered_records = self._store.list()
            registered_defs = tuple(r.definition for r in registered_records)
            _result = self._validator.validate(
                record.definition, registered=registered_defs
            )

            existing = self._store.get(slug, version)
            if existing is not None:
                if _records_equal(existing, record):
                    return existing.definition
                raise DomainRegistryConflict(
                    f"Same identity ({slug}, {version}) already registered with different content",
                    field="definition",
                    details={"domain_id": slug, "version": version},
                )

            self._store.add(record)
            stored = self._store.get(slug, version)
            return stored.definition

    def restore_record(self, record: DomainRegistryRecord) -> DomainRegistryRecord:
        """Restore an exact registry record for rollback purposes.

        Unlike ``register()``, this bypasses dependency/conflict validation
        and status normalization: it persists *record* verbatim (including
        its lifecycle ``status`` and original timestamps), overwriting any
        existing entry with the same identity. Intended exclusively for
        callers (e.g. the domain loader) that must restore a previously
        captured record after a failed rollback-requiring operation — not
        for ordinary registration.
        """
        if not isinstance(record, DomainRegistryRecord):
            raise DomainContractValidationError(
                f"record must be a DomainRegistryRecord, got {type(record).__name__}",
                field="record",
            )
        slug = _canonical_slug(record.definition.id.slug)
        version = _canonical_version(record.definition.version)
        with self._lock:
            existing = self._store.get(slug, version)
            if existing is not None:
                self._store.replace(record)
            else:
                self._store.add(record)
            stored = self._store.get(slug, version)
            return stored

    def snapshot_state(self) -> DomainRegistryStoreSnapshot:
        """Capture the full store state (every record and index) for
        transactional rollback. Callers that need to roll back a
        multi-step operation should capture this immediately before
        their first mutation and pass it to ``restore_state()`` on
        failure.
        """
        with self._lock:
            return self._store.snapshot_state()

    def restore_state(self, snapshot: DomainRegistryStoreSnapshot) -> None:
        """Restore the full store state from a snapshot captured by
        ``snapshot_state()``. Replaces every record and index — this is
        the atomic counterpart to ``snapshot_state()`` and the mechanism
        loader transactions must use for rollback (never several
        independent compensating operations).
        """
        if not isinstance(snapshot, DomainRegistryStoreSnapshot):
            raise DomainContractValidationError(
                f"snapshot must be a DomainRegistryStoreSnapshot, got {type(snapshot).__name__}",
                field="snapshot",
            )
        with self._lock:
            self._store.restore_state(snapshot)

    def unregister(
        self,
        domain_id: str,
        version: str | None = None,
    ) -> DomainDefinition | tuple[DomainDefinition, ...]:
        slug = _canonical_slug(domain_id)
        with self._lock:
            if version is not None:
                ver = _canonical_version(version)
                existing = self._store.get(slug, ver)
                if existing is None:
                    raise DomainRegistryNotFound(
                        f"Entry not found for unregister: ({slug}, {ver})",
                        field="domain_id",
                        details={"domain_id": slug, "version": ver},
                    )
                removed = self._store.remove(slug, ver)
                return removed.definition
            else:
                records = self._store.list()
                slug_records = [
                    r for r in records if _canonical_slug(r.definition.id.slug) == slug
                ]
                if not slug_records:
                    raise DomainRegistryNotFound(
                        f"No entries found for domain: {slug}",
                        field="domain_id",
                        details={"domain_id": slug},
                    )

                snap = self._store.snapshot_state()
                removed_list: list[DomainDefinition] = []
                try:
                    for r in slug_records:
                        removed_list.append(
                            self._store.remove(
                                _canonical_slug(r.definition.id.slug),
                                _canonical_version(r.definition.version),
                            ).definition
                        )
                except Exception:  # noqa: BLE001  -- transactional boundary
                    self._store.restore_state(snap)
                    raise DomainRegistryStateError(
                        f"Failed to unregister all versions for {slug}: partial removal rolled back",
                        field="domain_id",
                        details={"domain_id": slug},
                    )

                if len(removed_list) == 1:
                    return removed_list[0]
                removed_list.sort(
                    key=cmp_to_key(
                        lambda a, b: _compare_versions_desc_safe(a.version, b.version)
                    )
                )
                return tuple(removed_list)

    def get(
        self, domain_id: str, version: str | None = None
    ) -> DomainDefinition | None:
        slug = _canonical_slug(domain_id)
        with self._lock:
            if version is not None:
                ver = _canonical_version(version)
                record = self._store.get(slug, ver)
                return record.definition if record else None
            else:
                best_key = self._resolve_best_version(slug)
                if best_key is None:
                    return None
                record = self._store.get(best_key[0], best_key[1])
                return record.definition if record else None

    def get_required(
        self, domain_id: str, version: str | None = None
    ) -> DomainDefinition:
        result = self.get(domain_id, version)
        if result is None:
            slug = _canonical_slug(domain_id)
            raise DomainRegistryNotFound(
                f"Required domain not found: {domain_id}"
                + (f"@{version}" if version else ""),
                field="domain_id",
                details={"domain_id": slug, "version": version},
            )
        return result

    def get_record(
        self, domain_id: str, version: str | None = None
    ) -> DomainRegistryRecord | None:
        slug = _canonical_slug(domain_id)
        with self._lock:
            if version is not None:
                return self._store.get(slug, _canonical_version(version))
            best_key = self._resolve_best_version(slug)
            if best_key is None:
                return None
            return self._store.get(best_key[0], best_key[1])

    def list(self, query: DomainQuery | None = None) -> tuple[DomainDefinition, ...]:
        with self._lock:
            all_records = self._store.list()
            if query is None:
                all_records_sorted = sorted(
                    all_records, key=cmp_to_key(_compare_records)
                )
                return tuple(r.definition for r in all_records_sorted)
            return self._apply_query(all_records, query)

    def list_records(
        self, query: DomainQuery | None = None
    ) -> tuple[DomainRegistryRecord, ...]:
        with self._lock:
            all_records = self._store.list()
            if query is None:
                return tuple(sorted(all_records, key=cmp_to_key(_compare_records)))
            filtered = self._filter_records(all_records, query)
            return tuple(sorted(filtered, key=cmp_to_key(_compare_records)))

    def _apply_query(
        self, records: tuple[DomainRegistryRecord, ...], query: DomainQuery
    ) -> tuple[DomainDefinition, ...]:
        filtered = self._filter_records(records, query)
        return tuple(
            r.definition for r in sorted(filtered, key=cmp_to_key(_compare_records))
        )

    def _filter_records(
        self, records: tuple[DomainRegistryRecord, ...], query: DomainQuery
    ) -> list[DomainRegistryRecord]:
        results: list[DomainRegistryRecord] = []
        for r in records:
            if query.kinds and r.definition.kind not in query.kinds:
                continue
            if query.statuses and r.status not in query.statuses:
                continue
            if query.capabilities:
                def_cap_names = {c.name for c in r.definition.capabilities}
                if not all(c in def_cap_names for c in query.capabilities):
                    continue
            if query.enabled is True and not r.definition.enabled:
                continue
            if query.enabled is False and r.definition.enabled:
                continue
            if query.tags:
                if r.definition.metadata is None:
                    continue
                def_tags = set(r.definition.metadata.tags)
                if not all(t in def_tags for t in query.tags):
                    continue
            if query.metadata:
                if r.definition.metadata is None:
                    continue
                def_meta = dict(r.definition.metadata.metadata)
                if not all(
                    mk in def_meta and def_meta[mk] == mv
                    for mk, mv in query.metadata.items()
                ):
                    continue
            if query.minimum_version is not None:
                try:
                    min_sv = parse_semver(query.minimum_version)
                    def_sv = parse_semver(r.definition.version)
                    if def_sv < min_sv:
                        continue
                except DomainContractValidationError:
                    continue
            if not query.include_experimental:
                if r.definition.kind == DomainKind.EXPERIMENTAL:
                    continue
                if (
                    r.definition.metadata is not None
                    and r.definition.metadata.experimental
                ):
                    continue
            results.append(r)
        return results

    def enable(self, domain_id: str, version: str | None = None) -> DomainDefinition:
        slug = _canonical_slug(domain_id)
        with self._lock:
            if version is not None:
                ver = _canonical_version(version)
                target_record = self._store.get(slug, ver)
                if target_record is None:
                    raise DomainRegistryNotFound(
                        f"Cannot enable: not found ({slug}, {ver})",
                        field="domain_id",
                        details={"domain_id": slug, "version": ver},
                    )
            else:
                best_key = self._resolve_best_version(slug)
                if best_key is None:
                    raise DomainRegistryNotFound(
                        f"Cannot enable: no versions found for {slug}",
                        field="domain_id",
                        details={"domain_id": slug},
                    )
                target_record = self._store.get(best_key[0], best_key[1])
                ver = target_record.definition.version

            if target_record.status in _NON_ENABLEABLE_STATUSES:
                raise DomainRegistryStateError(
                    f"Cannot enable domain in {target_record.status.value} state: ({slug}, {ver})",
                    field="status",
                    details={
                        "domain_id": slug,
                        "version": ver,
                        "current_status": target_record.status.value,
                    },
                )

            if target_record.status == DomainStatus.ACTIVE:
                return target_record.definition

            registered_records = self._store.list()
            registered_defs = tuple(r.definition for r in registered_records)
            result = self._validator.validate(
                target_record.definition, registered=registered_defs
            )
            if not result.valid:
                raise DomainRegistryStateError(
                    f"Cannot enable invalid domain ({slug}, {ver})",
                    field="definition",
                    details={
                        "domain_id": slug,
                        "version": ver,
                        "errors": list(result.errors),
                        "conflicts": list(result.conflicts),
                    },
                )

            # Check ONLY required dependencies (optional deps do NOT block)
            missing = []
            for dep in target_record.definition.dependencies:
                dep_slug = dep.domain_id.slug
                found = False
                # Only check if this dependency has required=True or default (required)
                # DomainDependency has a `required` field (bool)
                is_required = getattr(dep, "required", True)
                if not is_required:
                    continue  # optional deps don't block enable
                for r in registered_records:
                    if (
                        _canonical_slug(r.definition.id.slug) == dep_slug
                        and r.status in _DEPENDENCY_SATISFYING_STATUSES
                    ):
                        if dep.version_constraint:
                            try:
                                min_ver = parse_semver(dep.version_constraint)
                                if parse_semver(r.definition.version) >= min_ver:
                                    found = True
                                    break
                            except DomainContractValidationError:
                                pass
                        else:
                            found = True
                            break
                if not found:
                    missing.append(dep_slug)

            if missing:
                raise DomainDependencyMissing(
                    f"Cannot enable ({slug}, {ver}): required dependencies not satisfied: {missing}",
                    field="dependencies",
                    details={"domain_id": slug, "version": ver, "missing": missing},
                )

            # Atomic transition
            snap = self._store.snapshot_state()
            prev_active_key = self._active_version_key(slug)
            try:
                if prev_active_key is not None and prev_active_key != (slug, ver):
                    prev_record = self._store.get(
                        prev_active_key[0], prev_active_key[1]
                    )
                    self._store.replace(
                        _record_with_status(prev_record, DomainStatus.DISABLED)
                    )
                self._store.replace(
                    _record_with_status(target_record, DomainStatus.ACTIVE)
                )
            except Exception:  # noqa: BLE001  -- transactional boundary
                self._store.restore_state(snap)
                raise DomainRegistryStateError(
                    f"Enable failed for ({slug}, {ver}): rolled back",
                    field="status",
                    details={"domain_id": slug, "version": ver},
                )

            updated = self._store.get(slug, ver)
            return updated.definition

    def disable(self, domain_id: str, version: str | None = None) -> DomainDefinition:
        slug = _canonical_slug(domain_id)
        with self._lock:
            if version is not None:
                ver = _canonical_version(version)
                target_record = self._store.get(slug, ver)
                if target_record is None:
                    raise DomainRegistryNotFound(
                        f"Cannot disable: not found ({slug}, {ver})",
                        field="domain_id",
                        details={"domain_id": slug, "version": ver},
                    )
            else:
                active_key = self._active_version_key(slug)
                if active_key is not None:
                    target_record = self._store.get(active_key[0], active_key[1])
                else:
                    best_key = self._resolve_best_version(slug)
                    if best_key is None:
                        raise DomainRegistryNotFound(
                            f"Cannot disable: no versions found for {slug}",
                            field="domain_id",
                            details={"domain_id": slug},
                        )
                    target_record = self._store.get(best_key[0], best_key[1])

            if target_record.status in _NON_DISABLEABLE_STATUSES:
                raise DomainRegistryStateError(
                    f"Cannot disable domain in {target_record.status.value} state: ({slug}, {target_record.definition.version})",
                    field="status",
                    details={
                        "domain_id": slug,
                        "version": target_record.definition.version,
                        "current_status": target_record.status.value,
                    },
                )

            if target_record.status == DomainStatus.DISABLED:
                return target_record.definition

            self._store.replace(
                _record_with_status(target_record, DomainStatus.DISABLED)
            )
            updated = self._store.get(slug, target_record.definition.version)
            return updated.definition

    def validate(
        self, domain_id: str, version: str | None = None
    ) -> DomainValidationResult:
        definition = self.get_required(domain_id, version)
        if version is None:
            version = definition.version
        with self._lock:
            registered_records = self._store.list()
            registered_defs = tuple(r.definition for r in registered_records)
            return self._validator.validate(definition, registered=registered_defs)

    def resolve_capability(
        self, capability: str, *, include_experimental: bool = False
    ) -> tuple[DomainDefinition, ...]:
        if not capability or not capability.strip():
            raise DomainCapabilityConflict(
                "capability must be a non-empty string",
                field="capability",
                details={"capability": capability},
            )
        with self._lock:
            candidates = self._store.find_by_capability(capability.strip())
            filtered = []
            for r in candidates:
                if r.status != DomainStatus.ACTIVE:
                    continue
                if not include_experimental:
                    if r.definition.kind == DomainKind.EXPERIMENTAL:
                        continue
                    if (
                        r.definition.metadata is not None
                        and r.definition.metadata.experimental
                    ):
                        continue
                filtered.append(r)
            filtered.sort(key=cmp_to_key(_compare_records))
            return tuple(r.definition for r in filtered)

    def contains(self, domain_id: str, version: str | None = None) -> bool:
        slug = _canonical_slug(domain_id)
        if version is not None:
            return self._store.get(slug, _canonical_version(version)) is not None
        records = self._store.list()
        return any(_canonical_slug(r.definition.id.slug) == slug for r in records)

    def versions(self, domain_id: str) -> tuple[DomainDefinition, ...]:
        slug = _canonical_slug(domain_id)
        with self._lock:
            all_records = self._store.list()
            matching = [
                r.definition
                for r in all_records
                if _canonical_slug(r.definition.id.slug) == slug
            ]
            matching.sort(
                key=cmp_to_key(
                    lambda a, b: _compare_versions_desc_safe(a.version, b.version)
                )
            )
            return tuple(matching)

    def snapshot(self) -> DomainRegistrySnapshot:
        with self._lock:
            records = self._store.list()
            return DomainRegistrySnapshot(
                captured_at=datetime.now(timezone.utc),
                records=records,
                snapshot_version="10.3.0",
            )

    def list_operations(
        self, domain_id: str, version: str | None = None
    ) -> tuple[str, ...]:
        definition = self.get_required(domain_id, version)
        return tuple(sorted(definition.operations))

    def list_workflows(
        self, domain_id: str, version: str | None = None
    ) -> tuple[str, ...]:
        definition = self.get_required(domain_id, version)
        return tuple(sorted(definition.workflows))

    def list_resources(
        self, domain_id: str, version: str | None = None
    ) -> tuple[str, ...]:
        definition = self.get_required(domain_id, version)
        return tuple(sorted(definition.resources))

    def list_rules(self, domain_id: str, version: str | None = None) -> tuple[str, ...]:
        definition = self.get_required(domain_id, version)
        return tuple(sorted(definition.rules))


__all__ = ["DomainRegistry"]
