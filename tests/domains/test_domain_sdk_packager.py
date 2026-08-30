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
            tar.extract(
                member,
                path=extracted_root,
                filter="data" if hasattr(tarfile, "data_filter") else None,
            )

    # Revalidate extracted domain pack
    result = validate_domain_path(extracted_root)
    assert result.status in (
        DomainValidationStatus.PASSED,
        DomainValidationStatus.WARNING,
    )
    assert result.manifest_valid is True


def test_output_archive_inside_pack_root_is_not_packaged(tmp_path: Path) -> None:
    pack_root = tmp_path / "inside-output-pack"
    DomainScaffolder().create("inside-output-pack", destination=pack_root)
    output = pack_root / "dist" / "inside-output-pack.tar.gz"

    DomainPackager().pack(pack_root, output=output)

    with tarfile.open(output, "r:gz") as tar:
        assert "dist/inside-output-pack.tar.gz" not in tar.getnames()


def test_preexisting_output_inside_pack_root_is_not_packaged(tmp_path: Path) -> None:
    pack_root = tmp_path / "preexisting-output-pack"
    DomainScaffolder().create("preexisting-output-pack", destination=pack_root)
    output = pack_root / "preexisting-output-pack.tar.gz"
    output.write_bytes(b"stale archive bytes")

    DomainPackager().pack(pack_root, output=output)
    first_bytes = output.read_bytes()
    DomainPackager().pack(pack_root, output=output)

    with tarfile.open(output, "r:gz") as tar:
        assert "preexisting-output-pack.tar.gz" not in tar.getnames()
    assert output.read_bytes() == first_bytes


def test_packager_rejects_escaping_symlink(tmp_path: Path) -> None:
    pack_root = tmp_path / "escaping-link-pack"
    DomainScaffolder().create("escaping-link-pack", destination=pack_root)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    (pack_root / "outside-link.txt").symlink_to(outside)

    with pytest.raises(DomainPackagingError, match="validation|escape"):
        DomainPackager().pack(pack_root, output=tmp_path / "escaping.tar.gz")


def test_packager_preserves_safe_relative_in_root_symlink(tmp_path: Path) -> None:
    pack_root = tmp_path / "safe-link-pack"
    DomainScaffolder().create("safe-link-pack", destination=pack_root)
    link = pack_root / "sample-link.json"
    link.symlink_to("fixtures/sample.json")
    output = tmp_path / "safe-link-pack.tar.gz"

    DomainPackager().pack(pack_root, output=output)

    with tarfile.open(output, "r:gz") as tar:
        member = tar.getmember("sample-link.json")
        assert member.issym()
        assert member.linkname == "fixtures/sample.json"

    extracted_root = tmp_path / "safe-link-extracted"
    extracted_root.mkdir()
    with tarfile.open(output, "r:gz") as tar:
        for member in tar.getmembers():
            tar.extract(
                member,
                path=extracted_root,
                filter="data" if hasattr(tarfile, "data_filter") else None,
            )
    extracted_link = extracted_root / "sample-link.json"
    assert extracted_link.is_symlink()
    assert extracted_link.resolve().is_relative_to(extracted_root)
    revalidated = validate_domain_path(extracted_root)
    assert revalidated.status in (
        DomainValidationStatus.PASSED,
        DomainValidationStatus.WARNING,
    )


@pytest.mark.parametrize("target", ["/absolute/target", "missing-target.json"])
def test_packager_rejects_absolute_or_broken_symlink(
    tmp_path: Path, target: str
) -> None:
    pack_root = tmp_path / "unsafe-link-pack"
    DomainScaffolder().create("unsafe-link-pack", destination=pack_root)
    (pack_root / "unsafe-link").symlink_to(target)

    with pytest.raises(DomainPackagingError, match="validation|symlink"):
        DomainPackager().pack(pack_root, output=tmp_path / "unsafe.tar.gz")
