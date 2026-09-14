"""Phase 10.35 — Tests for SDK ManifestBuilder and DomainBuilder."""

from __future__ import annotations

import pytest

from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainPackKind
from cmm.domains.errors import DomainError
from cmm.domains.manifest import DomainManifest
from cmm.domains.registry import DomainRegistry
from cmm.domains.sdk.builders import DomainBuilder, ManifestBuilder


def test_manifest_builder_default_construction() -> None:
    builder = ManifestBuilder(slug="example")
    manifest = builder.build()

    assert isinstance(manifest, DomainManifest)
    assert manifest.domain_id.slug == "example"
    assert manifest.package_version == "0.1.0"
    assert manifest.schema_version == "1"
    assert manifest.pack_kind == DomainPackKind.EXTERNAL


def test_manifest_builder_deterministic_to_dict() -> None:
    builder = ManifestBuilder(slug="example", version="1.2.0")
    manifest = builder.build()

    assert manifest.to_dict() == builder.to_dict()
    assert (
        builder.to_dict() == ManifestBuilder(slug="example", version="1.2.0").to_dict()
    )


def test_manifest_builder_fluent_methods() -> None:
    builder = (
        ManifestBuilder(slug="custom-domain", version="2.0.0", name="custom-domain")
        .with_description("A custom domain pack")
        .with_pack_kind(DomainPackKind.EXPERIMENTAL)
        .with_metadata(custom_key="value")
    )
    manifest = builder.build()

    assert manifest.domain_id.slug == "custom-domain"
    assert manifest.package_version == "2.0.0"
    assert manifest.pack_kind == DomainPackKind.EXPERIMENTAL
    assert manifest.metadata.get("custom_key") == "value"


def test_manifest_builder_invalid_inputs_fail_canonically() -> None:
    with pytest.raises(DomainError):
        ManifestBuilder(slug="INVALID_SLUG!@#").build()

    with pytest.raises(DomainError):
        ManifestBuilder(slug="").build()

    with pytest.raises(DomainError):
        ManifestBuilder(slug="invalid_slug_with_underscores").build()

    with pytest.raises(DomainError):
        ManifestBuilder(slug="valid", version="").build()


def test_domain_builder_from_manifest() -> None:
    manifest = ManifestBuilder(slug="sample-domain", version="0.1.0").build()
    builder = DomainBuilder(manifest=manifest)
    definition = builder.build()

    assert isinstance(definition, DomainDefinition)
    assert definition.id.slug == "sample-domain"
    assert definition.name == "sample-domain"
    assert definition.version == "0.1.0"
    assert definition.manifest_id == manifest.id
    assert definition.kind == DomainKind.PERSONAL


def test_domain_builder_fluent_customization() -> None:
    manifest = ManifestBuilder(slug="sample-domain", version="0.1.0").build()
    builder = (
        DomainBuilder(manifest=manifest)
        .with_display_name("Sample Domain Display")
        .with_description("Custom domain description")
        .with_kind(DomainKind.CORE)
    )
    definition = builder.build()

    assert definition.display_name == "Sample Domain Display"
    assert definition.description == "Custom domain description"
    assert definition.kind == DomainKind.CORE


def test_builders_have_no_registry_or_filesystem_side_effects(tmp_path) -> None:
    registry = DomainRegistry()
    snapshot_before = registry.snapshot_state()

    manifest_builder = ManifestBuilder(slug="isolated-domain")
    manifest = manifest_builder.build()
    domain_builder = DomainBuilder(manifest=manifest)
    definition = domain_builder.build()

    snapshot_after = registry.snapshot_state()
    assert snapshot_before == snapshot_after
    assert definition.id.slug == "isolated-domain"
