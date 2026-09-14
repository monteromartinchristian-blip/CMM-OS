"""Phase 10.35 — Tests for Domain SDK Packager."""

from __future__ import annotations

import tarfile
from pathlib import Path

import pytest

from cmm.domains.enums import DomainValidationStatus
from cmm.domains.errors import DomainError
from cmm.domains.sdk import packager as packager_module
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
    output.parent.mkdir()

    DomainPackager().pack(pack_root, output=output)

    with tarfile.open(output, "r:gz") as tar:
        assert "dist/inside-output-pack.tar.gz" not in tar.getnames()


def test_packager_rejects_existing_unrelated_file_without_overwriting(
    tmp_path: Path,
) -> None:
    pack_root = tmp_path / "unrelated-output-pack"
    DomainScaffolder().create("unrelated-output-pack", destination=pack_root)
    output = tmp_path / "important.tar.gz"
    original_bytes = b"DO NOT OVERWRITE"
    output.write_bytes(original_bytes)

    with pytest.raises(DomainPackagingError):
        DomainPackager().pack(pack_root, output=output)

    assert output.read_bytes() == original_bytes


def test_packager_rejects_source_member_output_without_mutating_pack(
    tmp_path: Path,
) -> None:
    pack_root = tmp_path / "source-member-output-pack"
    DomainScaffolder().create("source-member-output-pack", destination=pack_root)
    manifest = pack_root / "manifest.json"
    original_bytes = manifest.read_bytes()

    with pytest.raises(DomainPackagingError):
        DomainPackager().pack(pack_root, output=manifest)

    assert manifest.read_bytes() == original_bytes
    result = validate_domain_path(pack_root)
    assert result.status in (
        DomainValidationStatus.PASSED,
        DomainValidationStatus.WARNING,
    )
    assert result.manifest_valid is True


def test_packager_rejects_symlink_alias_to_source_member(tmp_path: Path) -> None:
    pack_root = tmp_path / "source-alias-output-pack"
    DomainScaffolder().create("source-alias-output-pack", destination=pack_root)
    manifest = pack_root / "manifest.json"
    original_bytes = manifest.read_bytes()
    output = tmp_path / "manifest-alias.tar.gz"
    output.symlink_to(manifest)

    with pytest.raises(DomainPackagingError):
        DomainPackager().pack(pack_root, output=output)

    assert output.is_symlink()
    assert output.resolve() == manifest.resolve()
    assert manifest.read_bytes() == original_bytes


def test_packager_rejects_output_directory(tmp_path: Path) -> None:
    pack_root = tmp_path / "directory-output-pack"
    DomainScaffolder().create("directory-output-pack", destination=pack_root)
    output = tmp_path / "existing-directory.tar.gz"
    output.mkdir()

    with pytest.raises(DomainPackagingError):
        DomainPackager().pack(pack_root, output=output)

    assert output.is_dir()


@pytest.mark.parametrize("suffix", [".zip", ".txt", ".tar"])
def test_packager_rejects_invalid_output_suffix(
    tmp_path: Path,
    suffix: str,
) -> None:
    pack_root = tmp_path / "invalid-suffix-pack"
    DomainScaffolder().create("invalid-suffix-pack", destination=pack_root)
    output = tmp_path / f"archive{suffix}"

    with pytest.raises(DomainPackagingError):
        DomainPackager().pack(pack_root, output=output)

    assert not output.exists()


def test_packager_rejects_preexisting_archive_without_overwriting(
    tmp_path: Path,
) -> None:
    pack_root = tmp_path / "preexisting-output-pack"
    DomainScaffolder().create("preexisting-output-pack", destination=pack_root)
    output = pack_root / "preexisting-output-pack.tar.gz"
    original_bytes = b"stale archive bytes"
    output.write_bytes(original_bytes)

    with pytest.raises(DomainPackagingError):
        DomainPackager().pack(pack_root, output=output)

    assert output.read_bytes() == original_bytes


def test_packager_does_not_reuse_predictable_temporary_path(tmp_path: Path) -> None:
    pack_root = tmp_path / "temporary-collision-pack"
    DomainScaffolder().create("temporary-collision-pack", destination=pack_root)
    output = tmp_path / "temporary-collision-pack.tar.gz"
    predictable_temp = tmp_path / "temporary-collision-pack.tar.gz.tmp"
    original_bytes = b"IMPORTANT TEMPORARY DATA"
    predictable_temp.write_bytes(original_bytes)

    DomainPackager().pack(pack_root, output=output)

    assert output.is_file()
    assert predictable_temp.read_bytes() == original_bytes


def test_packager_translates_parent_creation_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack_root = tmp_path / "parent-error-pack"
    DomainScaffolder().create("parent-error-pack", destination=pack_root)
    blocked_parent = tmp_path / "blocked-parent"
    output = blocked_parent / "parent-error-pack.tar.gz"
    real_mkdir = Path.mkdir

    def deny_blocked_parent(path: Path, *args: object, **kwargs: object) -> None:
        if path == blocked_parent:
            raise PermissionError("permission denied by test")
        real_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", deny_blocked_parent)

    with pytest.raises(DomainPackagingError, match="destination|permission"):
        DomainPackager().pack(pack_root, output=output)

    assert not output.exists()


def test_packager_preserves_in_root_tree_on_finalization_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack_root = tmp_path / "in-root-finalization-failure-pack"
    DomainScaffolder().create(
        "in-root-finalization-failure-pack",
        destination=pack_root,
    )
    output = pack_root / "dist" / "release" / "archive.tar.gz"
    output.parent.mkdir(parents=True)
    inventory_before = {
        path.relative_to(pack_root).as_posix() for path in pack_root.rglob("*")
    }

    def deny_publication(source: Path, destination: Path) -> None:
        raise PermissionError("publication denied by test")

    monkeypatch.setattr(packager_module.os, "link", deny_publication)

    with pytest.raises(DomainPackagingError, match="finalize"):
        DomainPackager().pack(pack_root, output=output)

    inventory_after = {
        path.relative_to(pack_root).as_posix() for path in pack_root.rglob("*")
    }
    assert inventory_after == inventory_before
    assert not output.exists()


def test_packager_rejects_missing_in_root_parent_without_mutating_pack(
    tmp_path: Path,
) -> None:
    pack_root = tmp_path / "missing-in-root-parent-pack"
    DomainScaffolder().create("missing-in-root-parent-pack", destination=pack_root)
    inventory_before = {
        path.relative_to(pack_root).as_posix() for path in pack_root.rglob("*")
    }
    output = pack_root / "dist" / "release" / "archive.tar.gz"

    with pytest.raises(DomainPackagingError, match="parent"):
        DomainPackager().pack(pack_root, output=output)

    inventory_after = {
        path.relative_to(pack_root).as_posix() for path in pack_root.rglob("*")
    }
    assert inventory_after == inventory_before


def test_packager_does_not_recreate_in_root_parent_removed_after_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack_root = tmp_path / "removed-in-root-parent-pack"
    DomainScaffolder().create("removed-in-root-parent-pack", destination=pack_root)
    output = pack_root / "dist" / "archive.tar.gz"
    output.parent.mkdir()
    packager = DomainPackager()
    real_validate_destination = packager._validate_destination

    def remove_parent_after_validation(root: Path, out_path: Path) -> bool:
        in_root = real_validate_destination(root, out_path)
        output.parent.rmdir()
        return in_root

    monkeypatch.setattr(
        packager,
        "_validate_destination",
        remove_parent_after_validation,
    )

    with pytest.raises(DomainPackagingError, match="write|finalize"):
        packager.pack(pack_root, output=output)

    assert not output.parent.exists()
    assert not output.exists()


def test_packager_preserves_competing_destination_created_at_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack_root = tmp_path / "publication-race-pack"
    DomainScaffolder().create("publication-race-pack", destination=pack_root)
    output = tmp_path / "publication-race-pack.tar.gz"
    competing_bytes = b"COMPETING DESTINATION"
    real_link = packager_module.os.link

    def create_competitor_then_link(source: Path, destination: Path) -> None:
        destination.write_bytes(competing_bytes)
        real_link(source, destination)

    monkeypatch.setattr(
        packager_module.os,
        "link",
        create_competitor_then_link,
    )

    with pytest.raises(DomainPackagingError, match="already exists"):
        DomainPackager().pack(pack_root, output=output)

    assert output.read_bytes() == competing_bytes
    assert list(tmp_path.glob(f".{output.name}.*.tmp")) == []


def test_packager_cleans_temporary_archive_after_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack_root = tmp_path / "temporary-cleanup-pack"
    DomainScaffolder().create("temporary-cleanup-pack", destination=pack_root)
    output = tmp_path / "temporary-cleanup-pack.tar.gz"

    def fail_fsync(file_descriptor: int) -> None:
        raise OSError("fsync failed by test")

    monkeypatch.setattr(packager_module.os, "fsync", fail_fsync)

    with pytest.raises(DomainPackagingError, match="write|finalize"):
        DomainPackager().pack(pack_root, output=output)

    assert not output.exists()
    assert list(tmp_path.glob(f".{output.name}.*.tmp")) == []


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
