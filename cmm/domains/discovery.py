"""Phase 10.4 – Domain Discovery.

Discovers DomainCandidate entries from authorized filesystem locations.
Discovery never imports modules, never executes entrypoints, never
writes to disk, and never mutates the Kernel or registry.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime, timezone
from functools import cmp_to_key
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from cmm.domains.discovery_contracts import (
    DomainCandidate,
    DomainDiscoveryIssue,
    DomainDiscoveryResult,
    DomainSource,
    _compare_sources,
)
from cmm.domains.enums import DomainSourceKind
from cmm.domains.errors import DomainError
from cmm.domains.manifest_reader import DomainManifestReader, JsonDomainManifestReader

_SUPPORTED_SOURCE_KINDS: frozenset[DomainSourceKind] = frozenset(
    {
        DomainSourceKind.INTERNAL,
        DomainSourceKind.DIRECTORY,
        DomainSourceKind.DEVELOPMENT,
        DomainSourceKind.TEST,
    }
)

_MANIFEST_FILENAMES = ("manifest.json", "domain.json")
_PREFERRED_MANIFEST_FILENAME = "manifest.json"


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
class DomainDiscovery(Protocol):
    """Protocol for discovering domain pack candidates from sources."""

    def discover(self, sources: tuple[DomainSource, ...]) -> DomainDiscoveryResult: ...


class FileSystemDomainDiscovery:
    """Discovers domain pack candidates from filesystem-backed sources.

    Only ``INTERNAL``, ``DIRECTORY``, ``DEVELOPMENT``, and ``TEST`` source
    kinds have real operational support; other kinds are recorded as
    unsupported and skipped without raising.
    """

    def __init__(
        self,
        *,
        manifest_reader: DomainManifestReader | None = None,
        clock: Callable[[], datetime] | None = None,
        max_manifest_bytes: int = 1_048_576,
    ) -> None:
        self._manifest_reader = manifest_reader or JsonDomainManifestReader(
            max_bytes=max_manifest_bytes
        )
        self._clock = clock or _default_clock

    def discover(self, sources: tuple[DomainSource, ...]) -> DomainDiscoveryResult:
        candidates: list[DomainCandidate] = []
        issues: list[DomainDiscoveryIssue] = []
        scanned: list[str] = []

        enabled_sources = [s for s in sources if s.enabled]
        ordered_sources = sorted(enabled_sources, key=cmp_to_key(_compare_sources))

        # identity -> (candidate, source_priority) for duplicate/conflict tracking
        seen_identity: dict[tuple[str, str], tuple[DomainCandidate, int]] = {}
        seen_exact: set[tuple[str, str, str, str]] = set()
        rejected_identities: set[tuple[str, str]] = set()

        for source in ordered_sources:
            scanned.append(source.source_id)

            if source.kind not in _SUPPORTED_SOURCE_KINDS:
                issues.append(
                    DomainDiscoveryIssue(
                        source_id=source.source_id,
                        location=source.location,
                        code="unsupported_source_kind",
                        message=f"Source kind '{source.kind.value}' has no operational support in Phase 10.4",
                        blocking=False,
                    )
                )
                continue

            root = Path(source.location)
            try:
                root_exists = root.is_dir()
            except OSError:
                root_exists = False

            if not root_exists:
                issues.append(
                    DomainDiscoveryIssue(
                        source_id=source.source_id,
                        location=source.location,
                        code="source_root_unavailable",
                        message="Source location does not exist or is not a directory",
                        blocking=True,
                    )
                )
                continue

            try:
                resolved_root = root.resolve()
            except OSError:
                issues.append(
                    DomainDiscoveryIssue(
                        source_id=source.source_id,
                        location=source.location,
                        code="source_root_unresolvable",
                        message="Source root path could not be resolved",
                        blocking=True,
                    )
                )
                continue

            directories, escape_issues = _walk_directories(
                root, resolved_root, source.recursive
            )
            for esc_loc in escape_issues:
                issues.append(
                    DomainDiscoveryIssue(
                        source_id=source.source_id,
                        location=esc_loc,
                        code="DOMAIN_PATH_ESCAPE",
                        message="Symlink resolves outside the authorized source root",
                        blocking=True,
                    )
                )

            for directory in directories:
                self._process_directory(
                    source=source,
                    root=resolved_root,
                    directory=directory,
                    candidates=candidates,
                    issues=issues,
                    seen_identity=seen_identity,
                    seen_exact=seen_exact,
                    rejected_identities=rejected_identities,
                )

        final_candidates = [
            c
            for c in candidates
            if (_strip_domain_prefix(c.domain_id), c.detected_version)
            not in rejected_identities
        ]

        return DomainDiscoveryResult(
            candidates=tuple(final_candidates),
            issues=tuple(issues),
            scanned_sources=tuple(scanned),
            discovered_at=self._clock(),
        )

    def _process_directory(
        self,
        *,
        source: DomainSource,
        root: Path,
        directory: Path,
        candidates: list[DomainCandidate],
        issues: list[DomainDiscoveryIssue],
        seen_identity: dict[tuple[str, str], tuple[DomainCandidate, int]],
        seen_exact: set[tuple[str, str, str, str]],
        rejected_identities: set[tuple[str, str]],
    ) -> None:
        present = [name for name in _MANIFEST_FILENAMES if (directory / name).is_file()]
        if not present:
            return

        chosen_name = _PREFERRED_MANIFEST_FILENAME if len(present) > 1 else present[0]
        if len(present) > 1:
            issues.append(
                DomainDiscoveryIssue(
                    source_id=source.source_id,
                    location=str(directory),
                    code="ambiguous_manifest_name",
                    message=(
                        f"Both {' and '.join(_MANIFEST_FILENAMES)} present; "
                        f"using '{chosen_name}'"
                    ),
                    blocking=False,
                )
            )

        manifest_file = directory / chosen_name
        try:
            resolved_manifest = manifest_file.resolve()
        except OSError:
            issues.append(
                DomainDiscoveryIssue(
                    source_id=source.source_id,
                    location=str(manifest_file),
                    code="manifest_unresolvable",
                    message="Manifest file path could not be resolved",
                    blocking=True,
                )
            )
            return

        if not _is_within(resolved_manifest, root):
            issues.append(
                DomainDiscoveryIssue(
                    source_id=source.source_id,
                    location=str(manifest_file),
                    code="DOMAIN_PATH_ESCAPE",
                    message="Manifest file resolves outside the authorized source root",
                    blocking=True,
                )
            )
            return

        try:
            document = self._manifest_reader.read_document(resolved_manifest)
        except DomainError as exc:
            issues.append(
                DomainDiscoveryIssue(
                    source_id=source.source_id,
                    location=str(manifest_file),
                    code=exc.code,
                    message=exc.message,
                    blocking=True,
                )
            )
            return

        domain_slug, version = _extract_identity(document.data)
        if domain_slug is None or version is None:
            issues.append(
                DomainDiscoveryIssue(
                    source_id=source.source_id,
                    location=str(manifest_file),
                    code="DOMAIN_CANDIDATE_INVALID",
                    message="Manifest is missing a valid 'id' and/or 'version' field",
                    blocking=True,
                )
            )
            return

        checksum = f"sha256:{hashlib.sha256(document.raw_bytes).hexdigest()}"
        identity = (domain_slug, version)
        relative_manifest_path = str(resolved_manifest.relative_to(root)).replace(
            "\\", "/"
        )
        exact_key = (source.source_id, str(directory), chosen_name, checksum)

        if exact_key in seen_exact:
            return  # exact duplicate: deterministic dedup, no issue
        seen_exact.add(exact_key)

        try:
            candidate = DomainCandidate(
                candidate_id=f"{domain_slug}:{version}",
                source_id=source.source_id,
                source_kind=source.kind,
                location=str(root),
                manifest_path=relative_manifest_path,
                domain_id=f"domain:{domain_slug}",
                detected_version=version,
                checksum=checksum,
                trusted=source.trusted,
                discovered_at=self._clock(),
            )
        except DomainError as exc:
            issues.append(
                DomainDiscoveryIssue(
                    source_id=source.source_id,
                    location=str(manifest_file),
                    code="DOMAIN_CANDIDATE_INVALID",
                    message=exc.message,
                    blocking=True,
                )
            )
            return

        if identity in seen_identity:
            existing_candidate, _ = seen_identity[identity]
            if existing_candidate.checksum != checksum:
                rejected_identities.add(identity)
                issues.append(
                    DomainDiscoveryIssue(
                        source_id=source.source_id,
                        location=str(manifest_file),
                        code="DOMAIN_CANDIDATE_INVALID",
                        message=(
                            f"Conflicting candidates for identity "
                            f"({domain_slug}, {version}) with different checksums"
                        ),
                        blocking=True,
                    )
                )
            return  # same identity already recorded; do not add a second candidate

        seen_identity[identity] = (candidate, source.priority)
        candidates.append(candidate)

    def __repr__(self) -> str:
        return "FileSystemDomainDiscovery()"


def _extract_identity(parsed: Any) -> tuple[str | None, str | None]:
    raw_id = parsed.get("id") if hasattr(parsed, "get") else None
    version = parsed.get("version") if hasattr(parsed, "get") else None
    if not isinstance(raw_id, str) or not raw_id.strip():
        return None, None
    if not isinstance(version, str) or not version.strip():
        return None, None
    slug = raw_id.removeprefix("domain:")
    return slug.strip(), version.strip()


def _walk_directories(
    root: Path, resolved_root: Path, recursive: bool
) -> tuple[list[Path], list[str]]:
    """Yield candidate directories deterministically.

    Every directory is identified by its resolved physical path via
    ``visited``, so internal symlinks that point back to the root, an
    ancestor, or any already-processed directory are silently skipped
    (never re-walked, never treated as an escape) — this guarantees
    termination and a single pass per physical directory even in the
    presence of symlink cycles. Symlinks resolving outside
    ``resolved_root`` are reported as escapes and never descended into.
    """
    result: list[Path] = [root]
    escapes: list[str] = []
    visited: set[Path] = {resolved_root}

    def _list_child_dirs(parent: Path) -> list[Path]:
        try:
            entries = sorted(parent.iterdir(), key=lambda p: p.name)
        except OSError:
            return []
        return [p for p in entries if p.is_dir()]

    def _accept(path: Path) -> bool:
        try:
            resolved = path.resolve()
        except OSError:
            return False
        if not _is_within(resolved, resolved_root):
            escapes.append(str(path))
            return False
        if resolved in visited:
            return False
        visited.add(resolved)
        return True

    children = _list_child_dirs(root)
    accepted_children = [child for child in children if _accept(child)]
    result.extend(accepted_children)

    if recursive:
        queue = list(accepted_children)
        while queue:
            current = queue.pop(0)
            grandchildren = _list_child_dirs(current)
            accepted_grandchildren = [gc for gc in grandchildren if _accept(gc)]
            result.extend(accepted_grandchildren)
            queue.extend(accepted_grandchildren)

    return result, escapes


__all__ = [
    "DomainDiscovery",
    "FileSystemDomainDiscovery",
]
