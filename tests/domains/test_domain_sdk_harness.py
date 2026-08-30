"""Phase 10.35 — Tests for Domain SDK Test Harness."""

from __future__ import annotations

from pathlib import Path

import pytest

from cmm.domains.enums import DomainValidationStatus
from cmm.domains.errors import DomainError
from cmm.domains.registry import DomainRegistry
from cmm.domains.sdk.harness import DomainHarnessError, DomainTestHarness
from cmm.domains.sdk.scaffold import DomainScaffolder


def test_harness_validate_delegates_to_canonical_validation(tmp_path: Path) -> None:
    pack_root = tmp_path / "sample-pack"
    DomainScaffolder().create("sample-pack", destination=pack_root)

    harness = DomainTestHarness()
    result = harness.validate(pack_root)
    assert result.status in (DomainValidationStatus.PASSED, DomainValidationStatus.WARNING)
    assert result.manifest_valid is True


def test_harness_load_fixture_loads_data(tmp_path: Path) -> None:
    pack_root = tmp_path / "sample-pack"
    DomainScaffolder().create("sample-pack", destination=pack_root)

    harness = DomainTestHarness()
    data = harness.load_fixture(pack_root, "sample.json")
    assert isinstance(data, dict)
    assert data.get("domain") == "sample-pack"


def test_harness_prepare_creates_isolated_context(tmp_path: Path) -> None:
    pack_root1 = tmp_path / "pack1"
    pack_root2 = tmp_path / "pack2"
    DomainScaffolder().create("pack-one", destination=pack_root1)
    DomainScaffolder().create("pack-two", destination=pack_root2)

    harness1 = DomainTestHarness()
    harness2 = DomainTestHarness()

    ctx1 = harness1.prepare(pack_root1)
    ctx2 = harness2.prepare(pack_root2)

    assert ctx1.domain_registry is not ctx2.domain_registry
    assert ctx1.resource_registry is not ctx2.resource_registry
    assert ctx1.profile_registry is not ctx2.profile_registry
    assert ctx1.rule_registry is not ctx2.rule_registry
    assert ctx1.operation_registry is not ctx2.operation_registry
    assert ctx1.workflow_registry is not ctx2.workflow_registry
    assert ctx1.permission_registry is not ctx2.permission_registry


def test_harness_prepare_blocks_on_validation_failure(tmp_path: Path) -> None:
    pack_root = tmp_path / "broken-pack"
    DomainScaffolder().create("broken-pack", destination=pack_root)

    # Corrupt manifest
    manifest_path = pack_root / "manifest.json"
    manifest_path.write_text("{broken json", encoding="utf-8")

    harness = DomainTestHarness()
    with pytest.raises((DomainHarnessError, DomainError)):
        harness.prepare(pack_root)


def test_harness_does_not_mutate_global_state(tmp_path: Path) -> None:
    pack_root = tmp_path / "global-check"
    DomainScaffolder().create("global-check", destination=pack_root)

    global_reg = DomainRegistry()
    snapshot_before = global_reg.snapshot_state()

    harness = DomainTestHarness()
    harness.prepare(pack_root)

    snapshot_after = global_reg.snapshot_state()
    assert snapshot_before == snapshot_after
