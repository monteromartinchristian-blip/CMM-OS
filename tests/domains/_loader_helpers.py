"""Shared helpers for Phase 10.4 loader/discovery tests."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from cmm.domains.contracts import DomainDefinition
from cmm.domains.discovery_contracts import DomainCandidate
from cmm.domains.enums import DomainKind, DomainPackKind, DomainPackStatus, DomainStatus
from cmm.domains.identifiers import DomainId, DomainManifestId
from cmm.domains.manifest import DomainManifest
from cmm.domains.pack import DomainPack
from cmm.domains.registry_contracts import DomainRegistryRecord

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def write_domain_dir(
    root: Path,
    slug: str,
    version: str,
    *,
    author: str = "tester",
    license_: str = "MIT",
) -> Path:
    domain_dir = root / slug
    domain_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": slug,
        "version": version,
        "author": author,
        "license": license_,
    }
    (domain_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return domain_dir


def make_candidate(
    domain_dir: Path,
    slug: str,
    version: str,
    *,
    trusted: bool = True,
    source_id: str = "s1",
) -> DomainCandidate:
    manifest_file = domain_dir / "manifest.json"
    raw = manifest_file.read_bytes()
    checksum = f"sha256:{hashlib.sha256(raw).hexdigest()}"
    return DomainCandidate(
        candidate_id=f"{slug}:{version}",
        source_id=source_id,
        source_kind="directory",
        location=str(domain_dir),
        manifest_path="manifest.json",
        domain_id=f"domain:{slug}",
        detected_version=version,
        checksum=checksum,
        trusted=trusted,
        discovered_at=NOW,
    )


def make_minimal_manifest(slug: str, version: str) -> DomainManifest:
    return DomainManifest(
        id=DomainManifestId(slug=slug, version=version),
        domain_id=DomainId(slug=slug),
        schema_version="1",
        package_version=version,
        pack_kind=DomainPackKind.INTERNAL,
    )


def make_minimal_definition(slug: str, version: str) -> DomainDefinition:
    return DomainDefinition(
        id=f"domain:{slug}",
        name=slug,
        display_name=slug.title(),
        version=version,
        kind=DomainKind.PERSONAL,
        description=f"{slug} description",
        manifest_id=f"manifest:{slug}:{version}",
    )


def make_pack(slug: str, version: str, root_path: str = "/tmp/x") -> DomainPack:
    return DomainPack(
        definition=make_minimal_definition(slug, version),
        manifest=make_minimal_manifest(slug, version),
        root_path=root_path,
        status=DomainPackStatus.INSTALLED,
    )


def make_registry_record(slug: str, version: str) -> DomainRegistryRecord:
    return DomainRegistryRecord(
        definition=make_minimal_definition(slug, version),
        status=DomainStatus.REGISTERED,
        registered_at=NOW,
        updated_at=NOW,
    )
