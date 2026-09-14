"""Phase 10.35 — Tests for Domain SDK scaffold engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from cmm.domains.enums import DomainPackKind
from cmm.domains.errors import DomainError
from cmm.domains.manifest_reader import JsonDomainManifestReader
from cmm.domains.sdk.scaffold import DomainScaffolder


def test_basic_domain_scaffold_creates_minimal_canonical_pack(tmp_path: Path) -> None:
    destination = tmp_path / "sample-pack"
    scaffolder = DomainScaffolder()

    result = scaffolder.create(
        name="sample-pack",
        destination=destination,
        template="basic_domain",
    )

    assert result == destination.resolve()
    assert (destination / "manifest.json").is_file()
    assert (destination / "README.md").is_file()
    assert (destination / "fixtures" / "sample.json").is_file()
    assert (destination / "tests" / "test_domain.py").is_file()

    # Parse manifest with canonical JsonDomainManifestReader
    from cmm.domains.manifest import DomainManifest

    reader = JsonDomainManifestReader()
    manifest_doc = reader.read_document(destination / "manifest.json")
    assert manifest_doc.data["id"] == "sample-pack"
    assert manifest_doc.data["version"] == "0.1.0"
    manifest = DomainManifest.from_declarative_dict(manifest_doc.data)
    assert manifest.domain_id.slug == "sample-pack"
    assert manifest.package_version == "0.1.0"
    assert manifest.pack_kind is DomainPackKind.EXTERNAL
    assert "enabled" not in manifest_doc.data


def test_scaffold_rejects_invalid_names(tmp_path: Path) -> None:
    scaffolder = DomainScaffolder()

    with pytest.raises(DomainError):
        scaffolder.create(name="../escape", destination=tmp_path / "escape")

    with pytest.raises(DomainError):
        scaffolder.create(name="/absolute", destination=tmp_path / "abs")

    with pytest.raises(DomainError):
        scaffolder.create(name="INVALID_NAME", destination=tmp_path / "inv")

    with pytest.raises(DomainError):
        scaffolder.create(name="with_underscores", destination=tmp_path / "und")


def test_scaffold_rejects_existing_non_empty_destination(tmp_path: Path) -> None:
    destination = tmp_path / "existing"
    destination.mkdir(parents=True)
    (destination / "pre_existing.txt").write_text("content", encoding="utf-8")

    scaffolder = DomainScaffolder()
    with pytest.raises(DomainError):
        scaffolder.create(name="sample-pack", destination=destination)


def test_scaffold_rejects_unknown_template(tmp_path: Path) -> None:
    scaffolder = DomainScaffolder()
    with pytest.raises(DomainError):
        scaffolder.create(
            name="sample-pack",
            destination=tmp_path / "sample-pack",
            template="non_existent_template",
        )


def test_scaffold_is_deterministic(tmp_path: Path) -> None:
    dest1 = tmp_path / "dest1"
    dest2 = tmp_path / "dest2"
    scaffolder = DomainScaffolder()

    scaffolder.create(name="deterministic-pack", destination=dest1)
    scaffolder.create(name="deterministic-pack", destination=dest2)

    for rel_path in [
        "manifest.json",
        "README.md",
        "fixtures/sample.json",
        "tests/test_domain.py",
    ]:
        content1 = (dest1 / rel_path).read_bytes()
        content2 = (dest2 / rel_path).read_bytes()
        assert content1 == content2, f"Mismatch in {rel_path}"
