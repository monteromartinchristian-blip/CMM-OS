"""Phase 10.35 — Tests for Domain SDK Fixture Loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cmm.domains.errors import DomainError
from cmm.domains.sdk.fixtures import DomainFixtureError, DomainFixtureLoader
from cmm.domains.sdk.scaffold import DomainScaffolder


def test_fixture_loader_loads_scaffold_sample(tmp_path: Path) -> None:
    pack_root = tmp_path / "sample-pack"
    DomainScaffolder().create("sample-pack", destination=pack_root)

    loader = DomainFixtureLoader()
    data = loader.load(pack_root, "sample.json")
    assert isinstance(data, dict)
    assert data.get("domain") == "sample-pack"
    assert data.get("sample_key") == "sample_value"


def test_fixture_loader_loads_nested_fixtures(tmp_path: Path) -> None:
    pack_root = tmp_path / "sample-pack"
    DomainScaffolder().create("sample-pack", destination=pack_root)

    nested_dir = pack_root / "fixtures" / "sub"
    nested_dir.mkdir(parents=True)
    (nested_dir / "custom.json").write_text(
        json.dumps({"nested": True}), encoding="utf-8"
    )

    loader = DomainFixtureLoader()
    data = loader.load(pack_root, "sub/custom.json")
    assert isinstance(data, dict)
    assert data.get("nested") is True


def test_fixture_loader_missing_fixture_raises_error(tmp_path: Path) -> None:
    pack_root = tmp_path / "sample-pack"
    DomainScaffolder().create("sample-pack", destination=pack_root)

    loader = DomainFixtureLoader()
    with pytest.raises(DomainFixtureError):
        loader.load(pack_root, "non_existent.json")


def test_fixture_loader_rejects_path_escape(tmp_path: Path) -> None:
    pack_root = tmp_path / "sample-pack"
    DomainScaffolder().create("sample-pack", destination=pack_root)

    outside = tmp_path / "outside.json"
    outside.write_text('{"secret": "outside"}', encoding="utf-8")

    loader = DomainFixtureLoader()
    with pytest.raises((DomainFixtureError, DomainError)):
        loader.load(pack_root, "../outside.json")

    with pytest.raises((DomainFixtureError, DomainError)):
        loader.load(pack_root, str(outside))


def test_fixture_loader_malformed_json_raises(tmp_path: Path) -> None:
    pack_root = tmp_path / "sample-pack"
    DomainScaffolder().create("sample-pack", destination=pack_root)

    (pack_root / "fixtures" / "broken.json").write_text("{broken", encoding="utf-8")

    loader = DomainFixtureLoader()
    with pytest.raises(DomainFixtureError):
        loader.load(pack_root, "broken.json")
