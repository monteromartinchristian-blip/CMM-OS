"""Phase 10.1 – Tests for domain serialization (to_dict, from_dict, round-trip)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.contracts import (
    DomainCapability,
    DomainConflict,
    DomainDefinition,
    DomainDependency,
    DomainMetadata,
    DomainResult,
)
from cmm.domains.enums import DomainKind
from cmm.domains.errors import DomainSerializationError
from cmm.domains.identifiers import DomainId, DomainResultId

# ── DomainMetadata round-trip ─────────────────────────────────────────────────


class TestDomainMetadataSerialization:
    """Serialization tests for DomainMetadata."""

    def test_round_trip_minimal(self) -> None:
        meta = DomainMetadata(author="A", license="MIT")
        d = meta.to_dict()
        restored = DomainMetadata.from_dict(d)
        assert restored == meta
        assert restored.to_dict() == d

    def test_round_trip_full(self) -> None:
        created = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        updated = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        meta = DomainMetadata(
            author="Alice",
            license="Apache-2.0",
            homepage="https://example.com",
            repository="https://github.com/example/repo",
            created_at=created,
            updated_at=updated,
            minimum_cmm_version="0.1.0",
            maximum_cmm_version="1.0.0",
            tags=("ml", "ai", "data"),
            experimental=True,
            deprecated=False,
            metadata={"key": "value", "num": 42},
        )
        d = meta.to_dict()
        restored = DomainMetadata.from_dict(d)
        assert restored.author == meta.author
        assert restored.license == meta.license
        assert restored.created_at == created
        assert restored.updated_at == updated
        assert restored.tags == meta.tags
        assert restored.experimental == meta.experimental
        assert restored.metadata == meta.metadata

    def test_datetime_iso_format(self) -> None:
        created = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        meta = DomainMetadata(author="A", license="MIT", created_at=created)
        d = meta.to_dict()
        assert d["created_at"] == "2024-01-01T12:00:00+00:00"

    def test_tags_as_list(self) -> None:
        meta = DomainMetadata(author="A", license="MIT", tags=("a", "b", "c"))
        d = meta.to_dict()
        assert d["tags"] == ["a", "b", "c"]

    def test_metadata_as_dict(self) -> None:
        meta = DomainMetadata(author="A", license="MIT", metadata={"x": 1})
        d = meta.to_dict()
        assert d["metadata"] == {"x": 1}

    def test_missing_required_field(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainMetadata.from_dict({"author": "A"})

    def test_unknown_fields_rejected(self) -> None:
        d = {"author": "A", "license": "MIT", "extra_field": "should-fail"}
        with pytest.raises(DomainSerializationError):
            DomainMetadata.from_dict(d)

    def test_from_dict_requires_mapping(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainMetadata.from_dict("not a dict")  # type: ignore[arg-type]

    def test_deterministic_output(self) -> None:
        meta = DomainMetadata(
            author="A", license="MIT", tags=("a", "b"), metadata={"k": "v"}
        )
        d1 = meta.to_dict()
        d2 = meta.to_dict()
        assert d1 == d2


# ── DomainCapability round-trip ──────────────────────────────────────────────


class TestDomainCapabilitySerialization:
    """Serialization tests for DomainCapability."""

    def test_round_trip(self) -> None:
        cap = DomainCapability(
            name="reasoning",
            kind="cognitive",
            provided_by=DomainId(slug="core"),
            version="1.0.0",
            requirements=("req1", "req2"),
            permissions=("perm1",),
            metadata={"desc": "A capability"},
        )
        d = cap.to_dict()
        restored = DomainCapability.from_dict(d)
        assert restored.name == cap.name
        assert restored.kind == cap.kind
        assert restored.provided_by == cap.provided_by
        assert restored.version == cap.version
        assert restored.requirements == cap.requirements
        assert restored.permissions == cap.permissions

    def test_provided_by_as_string(self) -> None:
        cap = DomainCapability(
            name="r", kind="k", provided_by=DomainId(slug="core"), version="1.0"
        )
        d = cap.to_dict()
        assert d["provided_by"] == "domain:core"

    def test_missing_required_field(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainCapability.from_dict(
                {"name": "r", "kind": "k", "provided_by": "domain:x"}
            )

    def test_from_dict_requires_mapping(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainCapability.from_dict([])  # type: ignore[arg-type]


# ── DomainDependency round-trip ──────────────────────────────────────────────


class TestDomainDependencySerialization:
    """Serialization tests for DomainDependency."""

    def test_round_trip(self) -> None:
        dep = DomainDependency(
            domain_id=DomainId(slug="target"),
            version_constraint=">=1.0",
            required=True,
            reason="needed for feature X",
            metadata={"priority": "high"},
        )
        d = dep.to_dict()
        restored = DomainDependency.from_dict(d)
        assert restored.domain_id == dep.domain_id
        assert restored.version_constraint == dep.version_constraint
        assert restored.required == dep.required
        assert restored.reason == dep.reason

    def test_domain_id_as_string(self) -> None:
        dep = DomainDependency(domain_id=DomainId(slug="target"))
        d = dep.to_dict()
        assert d["domain_id"] == "domain:target"

    def test_none_version_constraint_becomes_none(self) -> None:
        dep = DomainDependency(domain_id=DomainId(slug="target"))
        d = dep.to_dict()
        assert d["version_constraint"] is None

    def test_from_dict_default_required_true(self) -> None:
        dep = DomainDependency.from_dict({"domain_id": "domain:target"})
        assert dep.required is True

    def test_json_roundtrip_via_json(self) -> None:
        import json

        dep = DomainDependency(
            domain_id=DomainId(slug="target"),
            version_constraint=">=1.0",
            required=False,
            reason="optional dep",
        )
        d = dep.to_dict()
        json_str = json.dumps(d)
        loaded = json.loads(json_str)
        restored = DomainDependency.from_dict(loaded)
        assert restored.domain_id.slug == "target"
        assert restored.required is False


# ── DomainConflict round-trip ────────────────────────────────────────────────


class TestDomainConflictSerialization:
    """Serialization tests for DomainConflict."""

    def test_round_trip(self) -> None:
        conflict = DomainConflict(
            domain_id=DomainId(slug="incompatible"),
            reason="Shared resources",
            severity="critical",
            metadata={"source": "auto"},
        )
        d = conflict.to_dict()
        restored = DomainConflict.from_dict(d)
        assert restored.domain_id == conflict.domain_id
        assert restored.reason == conflict.reason
        assert restored.severity == conflict.severity


# ── DomainDefinition round-trip ──────────────────────────────────────────────


class TestDomainDefinitionSerialization:
    """Serialization tests for DomainDefinition."""

    def test_round_trip_minimal(self) -> None:
        ddef = DomainDefinition(
            id="domain:my-domain",
            name="my-domain",
            display_name="My Domain",
            version="1.0.0",
            kind=DomainKind.CORE,
            description="A test domain",
            manifest_id="manifest:my-domain:1.0.0",
        )
        d = ddef.to_dict()
        restored = DomainDefinition.from_dict(d)
        assert restored.id == ddef.id
        assert restored.name == ddef.name
        assert restored.kind == ddef.kind
        assert restored.enabled == ddef.enabled

    def test_round_trip_full(self) -> None:
        created = datetime(2024, 1, 1, tzinfo=timezone.utc)
        ddef = DomainDefinition(
            id="domain:test",
            name="test",
            display_name="Test",
            version="1.0.0",
            kind="core",
            description="A full domain",
            manifest_id="manifest:test:1.0.0",
            reasoning_profile="default",
            resources=("res1",),
            rules=("rule1",),
            operations=("op1",),
            workflows=("wf1",),
            permissions=("perm1",),
            validators=("val1",),
            presentation_policy={"theme": "dark"},
            dependencies=(
                DomainDependency(domain_id=DomainId(slug="dep-a"), required=True),
            ),
            optional_dependencies=(
                DomainDependency(domain_id=DomainId(slug="dep-b"), required=False),
            ),
            conflicts=(
                DomainConflict(
                    domain_id=DomainId(slug="conflict-x"), reason="R", severity="low"
                ),
            ),
            capabilities=(
                DomainCapability(
                    name="cap1", kind="k", provided_by="domain:test", version="1.0"
                ),
            ),
            enabled=False,
            metadata=DomainMetadata(author="A", license="MIT", created_at=created),
        )
        d = ddef.to_dict()
        restored = DomainDefinition.from_dict(d)
        assert restored.enabled is False
        assert restored.kind == DomainKind.CORE
        assert len(restored.dependencies) == 1
        assert len(restored.optional_dependencies) == 1
        assert len(restored.conflicts) == 1
        assert len(restored.capabilities) == 1
        assert restored.metadata is not None
        assert restored.metadata.author == "A"

    def test_enum_must_be_string(self) -> None:
        ddef = DomainDefinition(
            id="domain:test",
            name="test",
            display_name="Test",
            version="1.0",
            kind=DomainKind.CORE,
            description="desc",
            manifest_id="manifest:test:1.0",
        )
        d = ddef.to_dict()
        assert d["kind"] == "core"

    def test_id_is_canonical_string(self) -> None:
        ddef = DomainDefinition(
            id="domain:test",
            name="test",
            display_name="Test",
            version="1.0",
            kind=DomainKind.CORE,
            description="desc",
            manifest_id="manifest:test:1.0",
        )
        d = ddef.to_dict()
        assert d["id"] == "domain:test"

    def test_manifest_id_is_canonical_string(self) -> None:
        ddef = DomainDefinition(
            id="domain:test",
            name="test",
            display_name="Test",
            version="1.0",
            kind=DomainKind.CORE,
            description="desc",
            manifest_id="manifest:test:1.0",
        )
        d = ddef.to_dict()
        assert d["manifest_id"] == "manifest:test:1.0"

    def test_missing_required_field(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainDefinition.from_dict({"id": "domain:test"})

    def test_nested_dependency_serialization(self) -> None:
        ddef = DomainDefinition(
            id="domain:test",
            name="test",
            display_name="Test",
            version="1.0",
            kind=DomainKind.CORE,
            description="desc",
            manifest_id="manifest:test:1.0",
            dependencies=(
                DomainDependency(domain_id=DomainId(slug="dep-a"), required=True),
            ),
        )
        d = ddef.to_dict()
        assert len(d["dependencies"]) == 1
        assert d["dependencies"][0]["domain_id"] == "domain:dep-a"
        assert d["dependencies"][0]["required"] is True

    def test_deterministic_output(self) -> None:
        ddef = DomainDefinition(
            id="domain:test",
            name="test",
            display_name="Test",
            version="1.0",
            kind=DomainKind.CORE,
            description="desc",
            manifest_id="manifest:test:1.0",
        )
        d1 = ddef.to_dict()
        d2 = ddef.to_dict()
        assert d1 == d2


# ── DomainResult round-trip ──────────────────────────────────────────────────


class TestDomainResultSerialization:
    """Serialization tests for DomainResult."""

    def test_round_trip_minimal(self) -> None:
        result = DomainResult(
            id=DomainResultId.generate(),
            status="completed",
            objective="Analyze",
            primary_domain=DomainId(slug="core"),
        )
        d = result.to_dict()
        restored = DomainResult.from_dict(d)
        assert restored.status == result.status
        assert restored.objective == result.objective
        assert restored.primary_domain == result.primary_domain

    def test_round_trip_full(self) -> None:
        created = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = DomainResult(
            id=DomainResultId.generate(),
            status="completed",
            objective="Analyze data",
            primary_domain=DomainId(slug="core"),
            supporting_domains=(DomainId(slug="helper"),),
            reasoning_result_id="reason-1",
            workflow_result_id="wf-1",
            operation_result_ids=("op1", "op2"),
            findings=({"key": "value"},),
            recommendations=({"action": "do-x"},),
            approval_ids=("appr-1",),
            confidence=0.95,
            trace_id="trace-abc",
            session_id="session-xyz",
            created_at=created,
            metadata={"source": "test"},
        )
        d = result.to_dict()
        restored = DomainResult.from_dict(d)
        assert restored.confidence == 0.95
        assert len(restored.supporting_domains) == 1
        assert len(restored.findings) == 1
        assert len(restored.recommendations) == 1
        assert restored.trace_id == "trace-abc"

    def test_datetime_iso_format(self) -> None:
        created = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = DomainResult(
            id=DomainResultId.generate(),
            status="ok",
            objective="test",
            primary_domain=DomainId(slug="core"),
            created_at=created,
        )
        d = result.to_dict()
        assert d["created_at"] == "2024-06-01T12:00:00+00:00"

    def test_id_is_canonical_string(self) -> None:
        rid = DomainResultId(opaque_id="abc123")
        result = DomainResult(
            id=rid, status="ok", objective="test", primary_domain=DomainId(slug="core")
        )
        d = result.to_dict()
        assert d["id"] == "domain-result:abc123"

    def test_primary_domain_is_canonical_string(self) -> None:
        result = DomainResult(
            id=DomainResultId.generate(),
            status="ok",
            objective="test",
            primary_domain=DomainId(slug="core"),
        )
        d = result.to_dict()
        assert d["primary_domain"] == "domain:core"

    def test_supporting_domains_as_list_of_strings(self) -> None:
        result = DomainResult(
            id=DomainResultId.generate(),
            status="ok",
            objective="test",
            primary_domain=DomainId(slug="core"),
            supporting_domains=(DomainId(slug="a"), DomainId(slug="b")),
        )
        d = result.to_dict()
        assert d["supporting_domains"] == ["domain:a", "domain:b"]

    def test_findings_as_list_of_dicts(self) -> None:
        result = DomainResult(
            id=DomainResultId.generate(),
            status="ok",
            objective="test",
            primary_domain=DomainId(slug="core"),
            findings=({"key": "v1"}, {"key": "v2"}),
        )
        d = result.to_dict()
        assert d["findings"] == [{"key": "v1"}, {"key": "v2"}]

    def test_missing_required_field(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainResult.from_dict({"id": "domain-result:abc"})

    def test_deterministic_output(self) -> None:
        result = DomainResult(
            id=DomainResultId.generate(),
            status="ok",
            objective="test",
            primary_domain=DomainId(slug="core"),
        )
        d1 = result.to_dict()
        d2 = result.to_dict()
        assert d1 == d2
