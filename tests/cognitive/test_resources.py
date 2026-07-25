from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from cmm.cognitive import (
    Confidence,
    InvalidResourceError,
    InvalidResourcePermissionError,
    InvalidResourceProvenanceError,
    InvalidResourceTemporalScopeError,
    Resource,
    ResourceIntegrityStatus,
    ResourceKind,
    ResourcePermission,
    ResourcePermissionOperation,
    ResourceProvenance,
    ResourceSourceKind,
    ResourceTemporalScope,
    ResourceTransformation,
    SensitivityLevel,
)

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)


def provenance() -> ResourceProvenance:
    return ResourceProvenance(
        source_type=ResourceSourceKind.UPLOADED_FILE,
        source_id="file-123",
        author="Hospital Example",
        retrieved_at=NOW,
        original_location="/documents/report.pdf",
        checksum="sha256:abc123",
    )


def temporal_scope() -> ResourceTemporalScope:
    return ResourceTemporalScope(
        content_created_at=NOW - timedelta(days=2),
        observed_at=NOW - timedelta(days=1),
        ingested_at=NOW,
        valid_from=NOW - timedelta(days=1),
        valid_until=NOW + timedelta(days=30),
        last_verified_at=NOW,
        timezone_name="Europe/Madrid",
    )


def test_resource_provenance_serializes_transformations() -> None:
    transformation = ResourceTransformation(
        operation="extract_text",
        actor_id="actor-system",
        created_at=NOW,
        input_checksum="sha256:one",
        output_checksum="sha256:two",
    )
    value = ResourceProvenance(
        source_type=ResourceSourceKind.UPLOADED_FILE,
        source_id="file-123",
        retrieved_at=NOW,
        transformation_history=(transformation,),
    )

    serialized = value.to_dict()

    assert serialized["source_type"] == "uploaded_file"
    assert serialized["source_id"] == "file-123"
    assert serialized["transformation_history"][0]["operation"] == "extract_text"


def test_resource_provenance_rejects_empty_source_id() -> None:
    with pytest.raises(InvalidResourceProvenanceError):
        ResourceProvenance(
            source_type=ResourceSourceKind.SYSTEM,
            source_id="",
            retrieved_at=NOW,
        )


def test_resource_temporal_scope_distinguishes_dates() -> None:
    scope = temporal_scope()

    assert scope.content_created_at == NOW - timedelta(days=2)
    assert scope.observed_at == NOW - timedelta(days=1)
    assert scope.ingested_at == NOW
    assert scope.last_verified_at == NOW


def test_resource_temporal_scope_rejects_invalid_validity_interval() -> None:
    with pytest.raises(InvalidResourceTemporalScopeError):
        ResourceTemporalScope(
            ingested_at=NOW,
            valid_from=NOW,
            valid_until=NOW - timedelta(seconds=1),
        )


def test_resource_temporal_scope_rejects_naive_datetime() -> None:
    with pytest.raises(InvalidResourceTemporalScopeError):
        ResourceTemporalScope(
            ingested_at=datetime(2026, 7, 25, 12, 0),
        )


def test_resource_temporal_scope_checks_validity() -> None:
    scope = temporal_scope()

    assert scope.is_valid_at(NOW)
    assert not scope.is_valid_at(NOW + timedelta(days=40))


def test_resource_permission_allows_authorized_context() -> None:
    permission = ResourcePermission(
        allowed_actor_ids=("actor-user",),
        allowed_domains=("medical",),
        allowed_operations=(
            ResourcePermissionOperation.READ,
            ResourcePermissionOperation.INFER,
        ),
        expires_at=NOW + timedelta(days=1),
    )

    assert permission.allows(
        ResourcePermissionOperation.INFER,
        actor_id="actor-user",
        domain="medical",
        at=NOW,
    )
    assert not permission.allows(
        ResourcePermissionOperation.EXPORT,
        actor_id="actor-user",
        domain="medical",
        at=NOW,
    )


def test_resource_permission_rejects_duplicate_actor_ids() -> None:
    with pytest.raises(InvalidResourcePermissionError):
        ResourcePermission(
            allowed_actor_ids=("actor-user", "actor-user"),
        )


def test_resource_permission_expires() -> None:
    permission = ResourcePermission(
        allowed_operations=(ResourcePermissionOperation.READ,),
        expires_at=NOW,
    )

    assert not permission.allows(
        ResourcePermissionOperation.READ,
        at=NOW + timedelta(seconds=1),
    )


def test_resource_serializes_complete_contract() -> None:
    permission = ResourcePermission(
        allowed_actor_ids=("actor-user",),
        allowed_domains=("medical",),
        allowed_operations=(
            ResourcePermissionOperation.READ,
            ResourcePermissionOperation.INFER,
        ),
        expires_at=NOW + timedelta(days=5),
    )
    resource = Resource(
        id="resource:medical-report:123",
        domain="medical",
        kind=ResourceKind.MEDICAL_REPORT,
        source=ResourceSourceKind.UPLOADED_FILE,
        content={"diagnosis": "Example"},
        provenance=provenance(),
        reliability=Confidence(0.92, source="system"),
        temporal_scope=temporal_scope(),
        version="1",
        language="es",
        entity_ids=("entity:person:user",),
        relationship_ids=("relation:document:author",),
        sensitivity=SensitivityLevel.HIGHLY_SENSITIVE,
        permissions=(permission,),
        integrity=ResourceIntegrityStatus.VERIFIED,
        created_at=NOW,
        updated_at=NOW,
        metadata={"format": "pdf"},
    )

    serialized = resource.to_dict()

    assert serialized["id"] == "resource:medical-report:123"
    assert serialized["kind"] == "medical_report"
    assert serialized["source"] == "uploaded_file"
    assert serialized["reliability"]["value"] == 0.92
    assert serialized["sensitivity"] == "highly_sensitive"
    assert serialized["integrity"] == "verified"
    assert serialized["permissions"][0]["allowed_operations"] == [
        "read",
        "infer",
    ]


def test_resource_default_permissions_are_read_only() -> None:
    resource = Resource(
        domain="general",
        kind=ResourceKind.NOTE,
        source=ResourceSourceKind.USER_INPUT,
        content="A note.",
        provenance=provenance(),
        reliability=Confidence(1.0),
        temporal_scope=temporal_scope(),
        created_at=NOW,
        updated_at=NOW,
    )

    assert resource.permits(ResourcePermissionOperation.READ)
    assert not resource.permits(ResourcePermissionOperation.PERSIST)


def test_resource_uses_explicit_permissions() -> None:
    permission = ResourcePermission(
        allowed_actor_ids=("actor-system",),
        allowed_domains=("project",),
        allowed_operations=(ResourcePermissionOperation.TRANSFORM,),
    )
    resource = Resource(
        domain="project",
        kind=ResourceKind.PROJECT_FILE,
        source=ResourceSourceKind.PROJECT,
        content={"path": "cmm/example.py"},
        provenance=provenance(),
        reliability=Confidence(1.0),
        temporal_scope=temporal_scope(),
        permissions=(permission,),
        created_at=NOW,
        updated_at=NOW,
    )

    assert resource.permits(
        ResourcePermissionOperation.TRANSFORM,
        actor_id="actor-system",
        domain="project",
        at=NOW,
    )
    assert not resource.permits(
        ResourcePermissionOperation.TRANSFORM,
        actor_id="actor-user",
        domain="project",
        at=NOW,
    )


def test_resource_rejects_empty_domain() -> None:
    with pytest.raises(InvalidResourceError):
        Resource(
            domain="",
            kind=ResourceKind.NOTE,
            source=ResourceSourceKind.USER_INPUT,
            content="A note.",
            provenance=provenance(),
            reliability=Confidence(1.0),
            temporal_scope=temporal_scope(),
            created_at=NOW,
            updated_at=NOW,
        )


def test_resource_rejects_updated_at_before_created_at() -> None:
    with pytest.raises(InvalidResourceError):
        Resource(
            domain="general",
            kind=ResourceKind.NOTE,
            source=ResourceSourceKind.USER_INPUT,
            content="A note.",
            provenance=provenance(),
            reliability=Confidence(1.0),
            temporal_scope=temporal_scope(),
            created_at=NOW,
            updated_at=NOW - timedelta(seconds=1),
        )


def test_resource_rejects_duplicate_entity_ids() -> None:
    with pytest.raises(InvalidResourceError):
        Resource(
            domain="general",
            kind=ResourceKind.NOTE,
            source=ResourceSourceKind.USER_INPUT,
            content="A note.",
            provenance=provenance(),
            reliability=Confidence(1.0),
            temporal_scope=temporal_scope(),
            entity_ids=("entity:one", "entity:one"),
            created_at=NOW,
            updated_at=NOW,
        )


def test_resource_contract_is_immutable() -> None:
    resource = Resource(
        domain="general",
        kind=ResourceKind.NOTE,
        source=ResourceSourceKind.USER_INPUT,
        content="A note.",
        provenance=provenance(),
        reliability=Confidence(1.0),
        temporal_scope=temporal_scope(),
        created_at=NOW,
        updated_at=NOW,
    )

    with pytest.raises(AttributeError):
        resource.domain = "medical"
