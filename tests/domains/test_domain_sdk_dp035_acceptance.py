"""Phase 10.35 — DP-035 Domain SDK End-to-End Acceptance Test."""

from __future__ import annotations

import subprocess
import sys
import tarfile
from pathlib import Path

from cmm.domains.contracts import DomainId
from cmm.domains.enums import DomainValidationStatus
from cmm.domains.manifest import DomainManifest
from cmm.domains.registry import DomainRegistry
from cmm.domains.sdk import (
    DomainBuilder,
    DomainFixtureLoader,
    DomainPackager,
    DomainScaffolder,
    DomainTestHarness,
    ManifestBuilder,
    validate_domain_path,
)


class TestDomainSdkDP035Acceptance:
    """Complete end-to-end acceptance suite for Phase 10.35 Domain SDK."""

    def test_full_sdk_lifecycle_e2e(self, tmp_path: Path) -> None:
        # Snapshot global state before doing anything
        global_registry = DomainRegistry()
        global_snapshot_before = global_registry.snapshot_state()

        # Step 1: Scaffold a new domain pack
        pack_slug = "custom-analytics"
        pack_root = tmp_path / pack_slug
        scaffolder = DomainScaffolder()
        scaffolder.create(pack_slug, destination=pack_root)

        assert pack_root.is_dir()
        manifest_file = pack_root / "manifest.json"
        readme_file = pack_root / "README.md"
        fixture_file = pack_root / "fixtures" / "sample.json"
        test_file = pack_root / "tests" / "test_domain.py"

        assert manifest_file.is_file()
        assert readme_file.is_file()
        assert fixture_file.is_file()
        assert test_file.is_file()

        # Step 2: Validate the newly scaffolded pack via CLI
        proc_val = subprocess.run(
            [sys.executable, "-m", "cmm", "domain", "validate", str(pack_root)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc_val.returncode == 0, f"CLI validate failed:\n{proc_val.stderr}"

        # Step 3: Run the scaffolded test via CLI
        proc_test = subprocess.run(
            [sys.executable, "-m", "cmm", "domain", "test", str(pack_root)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc_test.returncode == 0, f"CLI test failed:\n{proc_test.stderr}"

        # Step 4: Programmatic validation via DomainTestHarness
        harness = DomainTestHarness()
        val_result = harness.validate(pack_root)
        assert val_result.status in (
            DomainValidationStatus.PASSED,
            DomainValidationStatus.WARNING,
        )
        assert val_result.manifest_valid is True
        assert val_result.contracts_valid is True
        assert val_result.permissions_valid is True
        assert val_result.compatibility_valid is True
        assert val_result.security_valid is True
        assert val_result.fragmentation_valid is True

        # Step 5: Safe fixture loading
        fixture_loader = DomainFixtureLoader()
        fixture_data = fixture_loader.load(pack_root, "sample.json")
        assert isinstance(fixture_data, dict)
        assert fixture_data.get("domain") == pack_slug

        # Step 6: Isolated runtime preparation
        harness_ctx = harness.prepare(pack_root)
        assert harness_ctx.domain_registry is not None
        assert harness_ctx.resource_registry is not None
        assert harness_ctx.profile_registry is not None
        assert harness_ctx.rule_registry is not None
        assert harness_ctx.operation_registry is not None
        assert harness_ctx.workflow_registry is not None
        assert harness_ctx.permission_registry is not None

        # Step 7: Fluent builders build canonical contracts
        manifest_builder = (
            ManifestBuilder(
                slug="custom-analytics", version="1.0.0", name="Custom Analytics"
            )
            .with_description("Advanced analytics domain pack")
            .with_metadata(author="CMM Team", tier="enterprise")
        )
        manifest_obj = manifest_builder.build()
        assert isinstance(manifest_obj, DomainManifest)
        assert manifest_obj.domain_id.slug == "custom-analytics"
        assert manifest_obj.package_version == "1.0.0"

        domain_builder = (
            DomainBuilder(manifest_obj)
            .with_display_name("Custom Analytics Pack")
            .with_description("Custom Analytics for CMM OS")
        )
        definition_obj = domain_builder.build()
        assert definition_obj.id == DomainId.from_str("domain:custom-analytics")
        assert definition_obj.display_name == "Custom Analytics Pack"
        assert definition_obj.version == "1.0.0"

        # Step 8: Package domain pack via CLI
        archive_path = tmp_path / "custom-analytics-1.0.0.tar.gz"
        proc_pack = subprocess.run(
            [
                sys.executable,
                "-m",
                "cmm",
                "domain",
                "pack",
                str(pack_root),
                "--output",
                str(archive_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc_pack.returncode == 0, f"CLI pack failed:\n{proc_pack.stderr}"
        assert archive_path.is_file()

        # Step 9: Repackage and verify byte-for-byte determinism
        archive_path_2 = tmp_path / "custom-analytics-repack.tar.gz"
        DomainPackager().pack(pack_root, output=archive_path_2)
        assert archive_path.read_bytes() == archive_path_2.read_bytes()

        # Step 10: Extract in isolated location and revalidate
        extracted_root = tmp_path / "extracted-custom-analytics"
        extracted_root.mkdir()
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                assert not member.name.startswith("/")
                assert ".." not in member.name.split("/")
                tar.extract(
                    member,
                    path=extracted_root,
                    filter="data" if hasattr(tarfile, "data_filter") else None,
                )

        reval_result = validate_domain_path(extracted_root)
        assert reval_result.status in (
            DomainValidationStatus.PASSED,
            DomainValidationStatus.WARNING,
        )
        assert reval_result.manifest_valid is True

        # Step 11: Global registry and system state remains untouched
        global_snapshot_after = global_registry.snapshot_state()
        assert global_snapshot_before == global_snapshot_after
