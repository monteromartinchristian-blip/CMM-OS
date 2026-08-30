"""Phase 10.35 — Tests for Domain SDK Packager."""

from __future__ import annotations

import tarfile
from pathlib import Path

import pytest

from cmm.domains.enums import DomainValidationStatus
from cmm.domains.errors import DomainError
from cmm.domains.sdk.cli import validate_domain_path
from cmm.domains.sdk.packager import DomainPackager, DomainPackagingError
from cmm.domains.sdk.scaffold import DomainScaffolder


def test_packager_creates_valid_tar_gz(tmp_path: Path) -> None:
    pack_root = tmp_path / "sample-pack"
    DomainScaffolder().create("sample-pack", destination=pack_root)

    packager = DomainPackager()
    output_archive = tmp_path / "sample-pack.tar.gz"
    result_path = packager.pack(pack_root, output=output_archive)

    assert result_path == output_archive.resolve()
    assert result_path.is_file()
    assert result_path.suffixes[-2:] == [".tar", ".gz"]

    # Verify archive content
    with tarfile.open(result_path, "r:gz") as tar:
        names = tar.getnames()
        assert "manifest.json" in names
        assert "README.md" in names
        assert "fixtures/sample.json" in names
        assert "tests/test_domain.py" in names


def test_packager_blocks_on_validation_failure(tmp_path: Path) -> None:
    pack_root = tmp_path / "broken-pack"
    DomainScaffolder().create("broken-pack", destination=pack_root)

    # Corrupt manifest
    manifest_path = pack_root / "manifest.json"
    manifest_path.write_text("{broken json", encoding="utf-8")

    output_archive = tmp_path / "broken-pack.tar.gz"
    packager = DomainPackager()

    with pytest.raises((DomainPackagingError, DomainError)):
        packager.pack(pack_root, output=output_archive)

    assert not output_archive.exists()


def test_packager_excludes_transient_artifacts(tmp_path: Path) -> None:
    pack_root = tmp_path / "clean-pack"
    DomainScaffolder().create("clean-pack", destination=pack_root)

    # Add transient files
    pycache = pack_root / "__pycache__"
    pycache.mkdir()
    (pycache / "cached.pyc").write_bytes(b"bytecode")
    (pack_root / ".DS_Store").write_bytes(b"ds_store")
    (pack_root / ".pytest_cache").mkdir()
    (pack_root / ".pytest_cache" / "cache.json").write_text("{}", encoding="utf-8")

    output_archive = tmp_path / "clean-pack.tar.gz"
    DomainPackager().pack(pack_root, output=output_archive)

    with tarfile.open(output_archive, "r:gz") as tar:
        names = tar.getnames()
        assert not any("__pycache__" in n for n in names)
        assert not any(".DS_Store" in n for n in names)
        assert not any(".pytest_cache" in n for n in names)
        assert not any(n.endswith(".pyc") for n in names)


def test_packager_is_byte_for_byte_deterministic(tmp_path: Path) -> None:
    pack_root = tmp_path / "deterministic-pack"
    DomainScaffolder().create("deterministic-pack", destination=pack_root)

    out1 = tmp_path / "out1.tar.gz"
    out2 = tmp_path / "out2.tar.gz"

    packager = DomainPackager()
    packager.pack(pack_root, output=out1)
    packager.pack(pack_root, output=out2)

    assert out1.read_bytes() == out2.read_bytes()


def test_unpack_and_revalidate(tmp_path: Path) -> None:
    pack_root = tmp_path / "source-pack"
    DomainScaffolder().create("source-pack", destination=pack_root)

    archive_path = tmp_path / "source-pack.tar.gz"
    DomainPackager().pack(pack_root, output=archive_path)

    # Safe extraction into a fresh directory
    extracted_root = tmp_path / "extracted-pack"
    extracted_root.mkdir()

    with tarfile.open(archive_path, "r:gz") as tar:
        for member in tar.getmembers():
            # Ensure member has no path traversal
            if member.name.startswith("/") or ".." in member.name.split("/"):
                raise ValueError(f"Dangerous archive member: {member.name}")
            tar.extract(member, path=extracted_root, filter="data" if hasattr(tarfile, "data_filter") else None)

    # Revalidate extracted domain pack
    result = validate_domain_path(extracted_root)
    assert result.status in (DomainValidationStatus.PASSED, DomainValidationStatus.WARNING)
    assert result.manifest_valid is True
