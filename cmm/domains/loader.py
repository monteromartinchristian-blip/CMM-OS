"""Phase 10.4 – Domain Loader.

Converts a validated ``DomainCandidate`` into a materialized ``DomainPack``
registered (but not enabled) in the ``DomainRegistry``. Only public
registry APIs are used — no private store access.

Every public operation (``load``/``unload``/``reload``) is transactional:
any failure after a registry mutation is rolled back so the registry and
the loader's local state never diverge and no partial record is left
behind.
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from functools import cmp_to_key
from pathlib import Path
from typing import Protocol, runtime_checkable

from cmm.domains.contracts import _deep_unfreeze
from cmm.domains.discovery_contracts import DomainCandidate
from cmm.domains.enums import DomainLoadStatus, DomainPackStatus
from cmm.domains.errors import (
    DomainChecksumMismatch,
    DomainError,
    DomainLoadFailed,
    DomainLoadRollbackFailed,
    DomainRegistryNotFound,
    DomainReloadFailed,
    DomainReloadRollbackFailed,
    DomainRollbackFailed,
    DomainSourceUntrusted,
    DomainUnloadFailed,
    DomainUnloadRollbackFailed,
)
from cmm.domains.loader_contracts import DomainLoaderSnapshot, DomainLoadResult
from cmm.domains.manifest import _validate_safe_relative_path
from cmm.domains.manifest_reader import DomainManifestReader
from cmm.domains.pack import DomainPack, ParsedDomainPack
from cmm.domains.registry import DomainRegistry
from cmm.domains.registry_contracts import DomainRegistryStoreSnapshot


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _strip_domain_prefix(domain_id: str) -> str:
    return domain_id.removeprefix("domain:")


@runtime_checkable
class DomainLoader(Protocol):
    """Protocol for loading, unloading, and reloading domain packs."""

    def load(
        self, candidate: DomainCandidate, *, allow_untrusted: bool = False
    ) -> DomainLoadResult: ...

    def unload(
        self, domain_id: str, version: str | None = None
    ) -> DomainLoadResult: ...

    def reload(
        self, candidate: DomainCandidate, *, allow_untrusted: bool = False
    ) -> DomainLoadResult: ...

    def get_loaded(
        self, domain_id: str, version: str | None = None
    ) -> DomainLoadResult | None: ...

    def list_loaded(self) -> tuple[DomainLoadResult, ...]: ...

    def snapshot(self) -> DomainLoaderSnapshot: ...


class DeclarativeDomainLoader:
    """Loads declarative ``DomainCandidate`` entries into the registry."""

    def __init__(
        self,
        *,
        discovery: object | None = None,
        manifest_reader: DomainManifestReader,
        registry: DomainRegistry,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._discovery = discovery
        self._manifest_reader = manifest_reader
        self._registry = registry
        self._clock = clock or _default_clock
        self._lock = threading.RLock()
        self._loaded: dict[tuple[str, str], DomainLoadResult] = {}
        # Keyed by (source_id, candidate_id, checksum): candidate_id alone
        # does not carry source or content identity, so two distinct
        # candidates sharing a candidate_id must never silently overwrite
        # each other.
        self._known_candidates: dict[tuple[str, str, str], DomainCandidate] = {}

    # ── Public API ───────────────────────────────────────────────────────

    def load(
        self, candidate: DomainCandidate, *, allow_untrusted: bool = False
    ) -> DomainLoadResult:
        if not isinstance(candidate, DomainCandidate):
            raise DomainLoadFailed(
                f"candidate must be a DomainCandidate, got {type(candidate).__name__}",
                field="candidate",
            )

        with self._lock:
            # Policy: every candidate the loader is asked to load is
            # recorded here regardless of the outcome (untrusted rejection,
            # build failure, registry conflict, or success) — it is never
            # rolled back, since it reflects an attempt that genuinely
            # happened, not registry/loaded state.
            self._record_known_candidate(candidate)

            if not candidate.trusted and not allow_untrusted:
                raise DomainSourceUntrusted(
                    "Cannot load an untrusted candidate without allow_untrusted=True",
                    field="candidate",
                    details={"candidate_id": candidate.candidate_id},
                )

            pack, build_errors = self._build_pack(candidate)
            if pack is None:
                return DomainLoadResult(
                    candidate=candidate,
                    status=DomainLoadStatus.FAILED,
                    pack=None,
                    registry_record=None,
                    errors=tuple(build_errors),
                    warnings=(),
                    loaded_at=self._clock(),
                )

            # Snapshot immediately before the first mutation.
            registry_before = self._registry.snapshot_state()
            loaded_before = dict(self._loaded)

            try:
                registered_definition = self._registry.register(pack.definition)
            except DomainError as exc:
                # register() raised before mutating anything (validation
                # failure or identity conflict) — no rollback needed.
                return DomainLoadResult(
                    candidate=candidate,
                    status=DomainLoadStatus.REJECTED,
                    pack=None,
                    registry_record=None,
                    errors=(exc.message,),
                    warnings=(),
                    loaded_at=self._clock(),
                )

            try:
                record = self._registry.get_record(
                    registered_definition.id.slug, registered_definition.version
                )
                result = DomainLoadResult(
                    candidate=candidate,
                    status=DomainLoadStatus.LOADED,
                    pack=pack,
                    registry_record=record,
                    errors=(),
                    warnings=(),
                    loaded_at=self._clock(),
                )
                key = (registered_definition.id.slug, registered_definition.version)
                self._loaded[key] = result
            except Exception as exc:
                self._rollback_registry_or_raise(
                    registry_before,
                    rollback_error_cls=DomainLoadRollbackFailed,
                    original_exc=exc,
                )
                self._loaded = loaded_before
                raise DomainLoadFailed(
                    "Failed to finalize load after registration",
                    field="candidate",
                    details={"error": type(exc).__name__},
                ) from exc

            return result

    def unload(self, domain_id: str, version: str | None = None) -> DomainLoadResult:
        with self._lock:
            key = self._find_loaded_key(domain_id, version)
            if key is None:
                raise DomainRegistryNotFound(
                    f"No loaded entry found for domain: {domain_id}"
                    + (f"@{version}" if version else ""),
                    field="domain_id",
                    details={"domain_id": domain_id},
                )

            existing = self._loaded[key]

            # Snapshot immediately before the first mutation.
            registry_before = self._registry.snapshot_state()
            loaded_before = dict(self._loaded)

            try:
                self._registry.unregister(key[0], key[1])
            except DomainError as exc:
                # Nothing was mutated (entry not found by unregister) — no
                # rollback needed.
                raise DomainUnloadFailed(
                    f"Failed to unregister domain during unload: {key[0]}@{key[1]}",
                    field="domain_id",
                    details={"error": exc.code},
                ) from exc

            try:
                del self._loaded[key]
                result = DomainLoadResult(
                    candidate=existing.candidate,
                    status=DomainLoadStatus.UNLOADED,
                    pack=None,
                    registry_record=None,
                    errors=(),
                    warnings=(),
                    loaded_at=self._clock(),
                )
            except Exception as exc:
                self._rollback_registry_or_raise(
                    registry_before,
                    rollback_error_cls=DomainUnloadRollbackFailed,
                    original_exc=exc,
                )
                self._loaded = loaded_before
                raise DomainUnloadFailed(
                    "Failed to finalize unload after unregistration",
                    field="domain_id",
                    details={"error": type(exc).__name__},
                ) from exc

            return result

    def reload(
        self, candidate: DomainCandidate, *, allow_untrusted: bool = False
    ) -> DomainLoadResult:
        if not isinstance(candidate, DomainCandidate):
            raise DomainLoadFailed(
                f"candidate must be a DomainCandidate, got {type(candidate).__name__}",
                field="candidate",
            )

        with self._lock:
            # Same known-candidate policy as load(): always recorded, never
            # rolled back.
            self._record_known_candidate(candidate)

            if not candidate.trusted and not allow_untrusted:
                raise DomainSourceUntrusted(
                    "Cannot reload an untrusted candidate without allow_untrusted=True",
                    field="candidate",
                    details={"candidate_id": candidate.candidate_id},
                )

            # Validate the new candidate fully BEFORE touching the previous one.
            pack, build_errors = self._build_pack(candidate)
            if pack is None:
                return DomainLoadResult(
                    candidate=candidate,
                    status=DomainLoadStatus.FAILED,
                    pack=None,
                    registry_record=None,
                    errors=tuple(build_errors),
                    warnings=(),
                    loaded_at=self._clock(),
                )

            new_slug = pack.definition.id.slug
            previous_key = self._find_loaded_key(new_slug, None)

            # Snapshot the ENTIRE registry and loaded state immediately
            # before the first mutation (unregistering the previous
            # version, if any). Rollback restores every record and index,
            # not just the primary one being replaced.
            registry_before = self._registry.snapshot_state()
            loaded_before = dict(self._loaded)

            if previous_key is not None:
                try:
                    self._registry.unregister(previous_key[0], previous_key[1])
                except DomainError as exc:
                    # Nothing was mutated — no rollback needed.
                    return DomainLoadResult(
                        candidate=candidate,
                        status=DomainLoadStatus.FAILED,
                        pack=None,
                        registry_record=None,
                        errors=(
                            f"Failed to unregister previous version during reload: {exc.message}",
                        ),
                        warnings=(),
                        loaded_at=self._clock(),
                    )

            try:
                registered_definition = self._registry.register(pack.definition)
            except DomainError as exc:
                # The previous version may already have been unregistered
                # above — restore the full prior registry state.
                self._rollback_registry_or_raise(
                    registry_before,
                    rollback_error_cls=DomainReloadRollbackFailed,
                    original_exc=exc,
                )
                return DomainLoadResult(
                    candidate=candidate,
                    status=DomainLoadStatus.FAILED,
                    pack=None,
                    registry_record=None,
                    errors=(
                        f"Failed to register new version during reload: {exc.message}",
                    ),
                    warnings=(),
                    loaded_at=self._clock(),
                )

            new_key = (registered_definition.id.slug, registered_definition.version)

            try:
                record = self._registry.get_record(new_key[0], new_key[1])
                result = DomainLoadResult(
                    candidate=candidate,
                    status=DomainLoadStatus.LOADED,
                    pack=pack,
                    registry_record=record,
                    errors=(),
                    warnings=(),
                    loaded_at=self._clock(),
                )
                if previous_key is not None and previous_key != new_key:
                    del self._loaded[previous_key]
                self._loaded[new_key] = result
            except Exception as exc:
                self._rollback_registry_or_raise(
                    registry_before,
                    rollback_error_cls=DomainReloadRollbackFailed,
                    original_exc=exc,
                )
                self._loaded = loaded_before
                raise DomainReloadFailed(
                    "Failed to finalize reload after registration",
                    field="candidate",
                    details={"error": type(exc).__name__},
                ) from exc

            return result

    def get_loaded(
        self, domain_id: str, version: str | None = None
    ) -> DomainLoadResult | None:
        with self._lock:
            key = self._find_loaded_key(domain_id, version)
            if key is None:
                return None
            return self._loaded[key]

    def list_loaded(self) -> tuple[DomainLoadResult, ...]:
        with self._lock:
            return tuple(
                sorted(
                    self._loaded.values(),
                    key=lambda r: (r.candidate.candidate_id, r.loaded_at),
                )
            )

    def snapshot(self) -> DomainLoaderSnapshot:
        with self._lock:
            return DomainLoaderSnapshot(
                known_candidates=tuple(self._known_candidates.values()),
                load_results=tuple(self._loaded.values()),
                captured_at=self._clock(),
            )

    # ── Private helpers ──────────────────────────────────────────────────

    def _rollback_registry_or_raise(
        self,
        registry_before: DomainRegistryStoreSnapshot,
        *,
        rollback_error_cls: type[DomainRollbackFailed],
        original_exc: Exception,
    ) -> None:
        """Restore the registry to *registry_before* or fail loudly.

        Never swallows a rollback failure: if ``restore_state()`` itself
        raises, atomicity is lost and the caller must be told explicitly
        via *rollback_error_cls*, carrying only safe type names — never
        ``str(exc)``/``repr(exc)`` or a traceback.
        """
        try:
            self._registry.restore_state(registry_before)
        except Exception as rollback_exc:
            raise rollback_error_cls(
                "Registry rollback failed after a loader operation error; "
                "atomicity is lost",
                field="registry",
                details={
                    "original_error": type(original_exc).__name__,
                    "rollback_error": type(rollback_exc).__name__,
                },
            ) from rollback_exc

    def _record_known_candidate(self, candidate: DomainCandidate) -> None:
        key = (candidate.source_id, candidate.candidate_id, candidate.checksum)
        self._known_candidates[key] = candidate

    def _find_loaded_key(
        self, domain_id: str, version: str | None
    ) -> tuple[str, str] | None:
        slug = _strip_domain_prefix(domain_id)
        if version is not None:
            key = (slug, version)
            return key if key in self._loaded else None
        matching = [k for k in self._loaded if k[0] == slug]
        if not matching:
            return None
        if len(matching) == 1:
            return matching[0]

        from cmm.domains.registry_contracts import _compare_versions_desc_safe

        matching.sort(
            key=cmp_to_key(lambda a, b: _compare_versions_desc_safe(a[1], b[1]))
        )
        return matching[0]

    def _build_pack(
        self, candidate: DomainCandidate
    ) -> tuple[DomainPack | None, list[str]]:
        errors: list[str] = []

        root = Path(candidate.location)
        if not root.is_dir():
            errors.append(
                f"Candidate location is not a directory: {candidate.location}"
            )
            return None, errors
        resolved_root = root.resolve()

        try:
            safe_relative = _validate_safe_relative_path(
                candidate.manifest_path, "manifest_path"
            )
        except DomainError as exc:
            errors.append(f"Invalid manifest_path: {exc.message}")
            return None, errors

        manifest_file = root / safe_relative
        try:
            resolved_manifest = manifest_file.resolve()
        except OSError:
            errors.append("Manifest file path could not be resolved")
            return None, errors

        if not _is_within(resolved_manifest, resolved_root):
            errors.append(
                "Manifest file resolves outside the authorized candidate root"
            )
            return None, errors

        if not resolved_manifest.is_file():
            errors.append(f"Manifest file does not exist: {safe_relative}")
            return None, errors

        try:
            document = self._manifest_reader.read_document(resolved_manifest)
        except DomainError as exc:
            errors.append(f"Failed to read manifest: {exc.message}")
            return None, errors

        recalculated = f"sha256:{hashlib.sha256(document.raw_bytes).hexdigest()}"
        if recalculated != candidate.checksum:
            raise DomainChecksumMismatch(
                "Recalculated checksum does not match candidate checksum",
                field="checksum",
                details={
                    "candidate_id": candidate.candidate_id,
                    "expected": candidate.checksum,
                    "actual": recalculated,
                },
            )

        try:
            parsed_pack = ParsedDomainPack.from_declarative_dict(
                _deep_unfreeze(document.data)
            )
        except DomainError as exc:
            errors.append(f"Invalid manifest content: {exc.message}")
            return None, errors

        if parsed_pack.manifest.package_version != candidate.detected_version:
            errors.append(
                "Manifest package_version does not match candidate detected_version: "
                f"{parsed_pack.manifest.package_version!r} != {candidate.detected_version!r}"
            )
            return None, errors

        expected_slug = _strip_domain_prefix(candidate.domain_id)
        if parsed_pack.manifest.domain_id.slug != expected_slug:
            errors.append("Manifest domain_id does not match candidate identity")
            return None, errors
        if parsed_pack.definition.id.slug != expected_slug:
            errors.append("Definition domain_id does not match candidate identity")
            return None, errors
        if parsed_pack.definition.version != candidate.detected_version:
            errors.append(
                "Definition version does not match candidate detected_version"
            )
            return None, errors

        try:
            pack = DomainPack(
                definition=parsed_pack.definition,
                manifest=parsed_pack.manifest,
                root_path=str(resolved_root),
                status=DomainPackStatus.INSTALLED,
                source=candidate.source_id,
                installed_at=self._clock(),
            )
        except DomainError as exc:
            errors.append(f"Failed to build DomainPack: {exc.message}")
            return None, errors

        return pack, errors


__all__ = [
    "DeclarativeDomainLoader",
    "DomainLoader",
]
