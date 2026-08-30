"""Phase 10.35 — Domain SDK Canonical Validation Facade."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cmm.domains.discovery import FileSystemDomainDiscovery
from cmm.domains.discovery_contracts import DomainCandidate, DomainSource
from cmm.domains.enums import DomainSourceKind
from cmm.domains.errors import DomainContractValidationError, DomainError
from cmm.domains.manifest_reader import JsonDomainManifestReader
from cmm.domains.pack import DomainPack, ParsedDomainPack
from cmm.domains.validation import PipelineDomainValidator
from cmm.domains.validation_contracts import (
    DomainValidationRequest,
    DomainValidationResult,
)


@dataclass(frozen=True, slots=True)
class _ResolvedDomainTarget:
    root: Path
    candidate: DomainCandidate | None
    domain_pack: DomainPack | None


def _resolve_domain_target(pack_root: Path | str) -> _ResolvedDomainTarget:
    """Resolve one SDK target through canonical discovery and manifest parsing."""
    root = Path(pack_root).resolve()
    if not root.exists() or not root.is_dir():
        raise DomainContractValidationError(
            f"Domain pack root does not exist or is not a directory: {pack_root}"
        )

    # 1. Canonical Discovery
    source = DomainSource(
        source_id="sdk_target",
        kind=DomainSourceKind.DIRECTORY,
        location=str(root),
        trusted=False,
        recursive=False,
    )
    discovery = FileSystemDomainDiscovery().discover((source,))

    candidate = discovery.candidates[0] if discovery.candidates else None
    domain_pack: DomainPack | None = None

    if candidate is not None:
        manifest_path = Path(candidate.location) / candidate.manifest_path
        try:
            manifest_doc = JsonDomainManifestReader().read_document(manifest_path)
            parsed = ParsedDomainPack.from_declarative_dict(manifest_doc.data)
            domain_pack = DomainPack(
                definition=parsed.definition,
                manifest=parsed.manifest,
                root_path=str(root),
            )
        except (DomainError, OSError, ValueError, TypeError):
            domain_pack = None

    return _ResolvedDomainTarget(
        root=root,
        candidate=candidate,
        domain_pack=domain_pack,
    )


def _validate_resolved_domain_target(
    target: _ResolvedDomainTarget,
) -> DomainValidationResult:
    """Validate a previously resolved target with the canonical pipeline."""
    request = DomainValidationRequest(
        pack=target.domain_pack,
        root_path=str(target.root),
        candidate=target.candidate,
        strict=False,
        run_tests=False,
    )
    validator = PipelineDomainValidator()
    return validator.validate(request)


def validate_domain_path(pack_root: Path | str) -> DomainValidationResult:
    """Validate a Domain Pack at pack_root using canonical Domain Validation."""
    return _validate_resolved_domain_target(_resolve_domain_target(pack_root))
