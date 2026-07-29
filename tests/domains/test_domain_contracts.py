"""Phase 10.1 – Tests for domain contracts (happy paths, validations, invariants)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from cmm.domains.contracts import (
    DomainCapability,
    DomainConflict,
    DomainDefinition,
    DomainDependency,
    DomainMetadata,
    DomainResult,
)
from cmm.domains.enums import DomainKind, DomainStatus
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainError,
    DomainSerializationError,
)
from cmm.domains.identifiers import DomainId, DomainManifestId, DomainResultId

# ── DomainMetadata ────────────────────────────────────────────────────────────


class TestDomainMetadata:
    """Tests for DomainMetadata."""

    def test_valid_minimal(self) -> None:
        meta = DomainMetadata(author="test", license="MIT")
        assert meta.author == "test"
        assert meta.license == "MIT"
        assert meta.tags == ()
        assert meta.experimental is False
        assert meta.deprecated is False
        assert meta.metadata == {}

    def test_valid_full(self) -> None:
        created = datetime(2024, 1, 1, tzinfo=timezone.utc)
        updated = datetime(2024, 6, 1, tzinfo=timezone.utc)
        meta = DomainMetadata(
            author="Alice",
            license="MIT",
            homepage="https://example.com",
            repository="https://github.com/example/repo",
            created_at=created,
            updated_at=updated,
            minimum_cmm_version="0.1.0",
            maximum_cmm_version="1.0.0",
            tags=("ai", "ml"),
            experimental=True,
            deprecated=False,
            metadata={"extra": "info"},
        )
        assert meta.author == "Alice"
        assert meta.tags == ("ai", "ml")
        assert meta.created_at == created
        assert meta.updated_at == updated

    def test_sort_tags(self) -> None:
        meta = DomainMetadata(author="A", license="MIT", tags=["z", "a", "m"])
        assert len(meta.tags) == 3

    def test_duplicate_tags(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainMetadata(author="A", license="MIT", tags=["dup", "dup"])

    def test_empty_tags(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainMetadata(author="A", license="MIT", tags=["valid", ""])

    def test_empty_author(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainMetadata(author="", license="MIT")

    def test_empty_license(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainMetadata(author="A", license="")

    def test_updated_before_created(self) -> None:
        created = datetime(2024, 6, 1, tzinfo=timezone.utc)
        updated = datetime(2024, 1, 1, tzinfo=timezone.utc)
        with pytest.raises(DomainContractValidationError):
            DomainMetadata(
                author="A", license="MIT", created_at=created, updated_at=updated
            )

    def test_naive_created_at(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainMetadata(
                author="A",
                license="MIT",
                created_at=datetime(2024, 1, 1),  # noqa: DTZ001
            )

    def test_naive_updated_at(self) -> None:
        created = datetime(2024, 1, 1, tzinfo=timezone.utc)
        with pytest.raises(DomainContractValidationError):
            DomainMetadata(
                author="A",
                license="MIT",
                created_at=created,
                updated_at=datetime(2024, 6, 1),  # noqa: DTZ001
            )

    def test_experimental_must_be_bool(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainMetadata(author="A", license="MIT", experimental="yes")  # type: ignore[arg-type]

    def test_metadata_keys_must_be_strings(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainMetadata(author="A", license="MIT", metadata={1: "value"})  # type: ignore[arg-type]

    def test_defensive_copy_tags(self) -> None:
        tags = ["tag1", "tag2"]
        meta = DomainMetadata(author="A", license="MIT", tags=tags)
        tags.append("tag3")
        assert meta.tags == ("tag1", "tag2")

    def test_defensive_copy_metadata(self) -> None:
        d = {"key": "value"}
        meta = DomainMetadata(author="A", license="MIT", metadata=d)
        d["another"] = "other"
        assert meta.metadata == MappingProxyType({"key": "value"})

    def test_frozen(self) -> None:
        meta = DomainMetadata(author="A", license="MIT")
        with pytest.raises(Exception):  # noqa: B017
            meta.tags = ()  # type: ignore[misc]

    def test_empty_homepage_normalized_to_none(self) -> None:
        meta = DomainMetadata(author="A", license="MIT", homepage="  ")
        assert meta.homepage is None

    def test_empty_repository_normalized_to_none(self) -> None:
        meta = DomainMetadata(author="A", license="MIT", repository="  ")
        assert meta.repository is None


# ── DomainCapability ─────────────────────────────────────────────────────────


class TestDomainCapability:
    """Tests for DomainCapability."""

    def test_valid(self) -> None:
        cap = DomainCapability(
            name="reasoning",
            kind="cognitive",
            provided_by=DomainId(slug="core"),
            version="1.0.0",
        )
        assert cap.name == "reasoning"
        assert cap.provided_by.slug == "core"

    def test_provided_by_string_coercion(self) -> None:
        cap = DomainCapability(
            name="reasoning", kind="cognitive", provided_by="domain:core", version="1.0"
        )
        assert isinstance(cap.provided_by, DomainId)
        assert cap.provided_by.slug == "core"

    def test_empty_name(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainCapability(
                name="",
                kind="cognitive",
                provided_by=DomainId(slug="core"),
                version="1.0",
            )

    def test_empty_kind(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainCapability(
                name="r", kind="", provided_by=DomainId(slug="core"), version="1.0"
            )

    def test_empty_version(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainCapability(
                name="r",
                kind="cognitive",
                provided_by=DomainId(slug="core"),
                version="",
            )

    def test_duplicate_requirements(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainCapability(
                name="r",
                kind="k",
                provided_by=DomainId(slug="core"),
                version="1.0",
                requirements=["req", "req"],
            )

    def test_duplicate_permissions(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainCapability(
                name="r",
                kind="k",
                provided_by=DomainId(slug="core"),
                version="1.0",
                permissions=["perm", "perm"],
            )

    def test_frozen(self) -> None:
        cap = DomainCapability(
            name="r", kind="k", provided_by=DomainId(slug="core"), version="1.0"
        )
        with pytest.raises(Exception):  # noqa: B017
            cap.name = "other"  # type: ignore[misc]


# ── DomainDependency ─────────────────────────────────────────────────────────


class TestDomainDependency:
    """Tests for DomainDependency."""

    def test_valid_required(self) -> None:
        dep = DomainDependency(domain_id=DomainId(slug="other"), required=True)
        assert dep.required is True
        assert dep.domain_id.slug == "other"

    def test_valid_optional(self) -> None:
        dep = DomainDependency(domain_id=DomainId(slug="other"), required=False)
        assert dep.required is False

    def test_string_coercion(self) -> None:
        dep = DomainDependency(domain_id="domain:other")
        assert isinstance(dep.domain_id, DomainId)
        assert dep.domain_id.slug == "other"

    def test_empty_version_constraint_normalized(self) -> None:
        dep = DomainDependency(
            domain_id=DomainId(slug="other"), version_constraint="  "
        )
        assert dep.version_constraint is None

    def test_empty_reason_normalized(self) -> None:
        dep = DomainDependency(domain_id=DomainId(slug="other"), reason="  ")
        assert dep.reason is None

    def test_frozen(self) -> None:
        dep = DomainDependency(domain_id=DomainId(slug="other"))
        with pytest.raises(Exception):  # noqa: B017
            dep.required = False  # type: ignore[misc]


# ── DomainConflict ────────────────────────────────────────────────────────────


class TestDomainConflict:
    """Tests for DomainConflict."""

    def test_valid(self) -> None:
        conflict = DomainConflict(
            domain_id=DomainId(slug="incompatible"),
            reason="Shared resources clash",
            severity="high",
        )
        assert conflict.reason == "Shared resources clash"
        assert conflict.severity == "high"

    def test_empty_reason(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainConflict(domain_id=DomainId(slug="x"), reason="", severity="high")

    def test_empty_severity(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainConflict(domain_id=DomainId(slug="x"), reason="R", severity="")

    def test_frozen(self) -> None:
        conflict = DomainConflict(
            domain_id=DomainId(slug="x"), reason="R", severity="low"
        )
        with pytest.raises(Exception):  # noqa: B017
            conflict.severity = "high"  # type: ignore[misc]


# ── DomainDefinition ─────────────────────────────────────────────────────────


def _make_domain_id(slug: str) -> DomainId:
    return DomainId(slug=slug)


def _make_manifest_id(slug: str, version: str = "1.0.0") -> DomainManifestId:
    return DomainManifestId(slug=slug, version=version)


class TestDomainDefinition:
    """Tests for DomainDefinition."""

    def test_valid_minimal(self) -> None:
        ddef = DomainDefinition(
            id=_make_domain_id("my-domain"),
            name="my-domain",
            display_name="My Domain",
            version="1.0.0",
            kind=DomainKind.CORE,
            description="A test domain",
            manifest_id=_make_manifest_id("my-domain", "1.0.0"),
        )
        assert ddef.id.slug == "my-domain"
        assert str(ddef.id) == "domain:my-domain"
        assert ddef.enabled is True

    def test_valid_full(self) -> None:
        created = datetime(2024, 1, 1, tzinfo=timezone.utc)
        ddef = DomainDefinition(
            id="domain:my-domain",
            name="my-domain",
            display_name="My Domain",
            version="1.0.0",
            kind="core",
            description="A test domain",
            manifest_id="manifest:my-domain:1.0.0",
            resources=("res1", "res2"),
            rules=("rule1",),
            operations=("op1",),
            workflows=("wf1",),
            permissions=("perm1",),
            validators=("val1",),
            dependencies=(
                DomainDependency(domain_id=DomainId(slug="dep-a"), required=True),
            ),
            optional_dependencies=(
                DomainDependency(domain_id=DomainId(slug="dep-b"), required=False),
            ),
            capabilities=(
                DomainCapability(
                    name="cap1",
                    kind="cognitive",
                    provided_by="domain:my-domain",
                    version="1.0",
                ),
            ),
            metadata=DomainMetadata(author="A", license="MIT", created_at=created),
        )
        assert ddef.kind == DomainKind.CORE
        assert len(ddef.dependencies) == 1
        assert len(ddef.optional_dependencies) == 1
        assert len(ddef.capabilities) == 1

    # ── Required fields ─────────────────────────────────────────────────

    def test_empty_name(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainDefinition(
                id="domain:test",
                name="",
                display_name="Test",
                version="1.0",
                kind=DomainKind.CORE,
                description="desc",
                manifest_id="manifest:test:1.0",
            )

    def test_empty_display_name(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainDefinition(
                id="domain:test",
                name="test",
                display_name="",
                version="1.0",
                kind=DomainKind.CORE,
                description="desc",
                manifest_id="manifest:test:1.0",
            )

    def test_empty_version(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainDefinition(
                id="domain:test",
                name="test",
                display_name="Test",
                version="",
                kind=DomainKind.CORE,
                description="desc",
                manifest_id="manifest:test:1.0",
            )

    def test_empty_description(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainDefinition(
                id="domain:test",
                name="test",
                display_name="Test",
                version="1.0",
                kind=DomainKind.CORE,
                description="",
                manifest_id="manifest:test:1.0",
            )

    # ── Name/id coherence ────────────────────────────────────────────────

    def test_name_mismatch_slug(self) -> None:
        with pytest.raises(DomainContractValidationError, match="name.*must match"):
            DomainDefinition(
                id="domain:my-domain",
                name="different-name",
                display_name="Test",
                version="1.0",
                kind=DomainKind.CORE,
                description="desc",
                manifest_id="manifest:my-domain:1.0",
            )

    def test_manifest_id_slug_mismatch(self) -> None:
        with pytest.raises(DomainContractValidationError, match="manifest_id slug"):
            DomainDefinition(
                id="domain:my-domain",
                name="my-domain",
                display_name="Test",
                version="1.0",
                kind=DomainKind.CORE,
                description="desc",
                manifest_id="manifest:other-slug:1.0",
            )

    def test_manifest_id_version_mismatch(self) -> None:
        with pytest.raises(DomainContractValidationError, match="manifest_id version"):
            DomainDefinition(
                id="domain:my-domain",
                name="my-domain",
                display_name="Test",
                version="1.0",
                kind=DomainKind.CORE,
                description="desc",
                manifest_id="manifest:my-domain:2.0",
            )

    # ── Self-dependency ──────────────────────────────────────────────────

    def test_self_dependency_required(self) -> None:
        with pytest.raises(
            DomainContractValidationError, match="cannot depend on itself"
        ):
            DomainDefinition(
                id="domain:test",
                name="test",
                display_name="Test",
                version="1.0",
                kind=DomainKind.CORE,
                description="desc",
                manifest_id="manifest:test:1.0",
                dependencies=(
                    DomainDependency(domain_id=DomainId(slug="test"), required=True),
                ),
            )

    def test_self_dependency_optional(self) -> None:
        with pytest.raises(
            DomainContractValidationError, match="cannot depend on itself"
        ):
            DomainDefinition(
                id="domain:test",
                name="test",
                display_name="Test",
                version="1.0",
                kind=DomainKind.CORE,
                description="desc",
                manifest_id="manifest:test:1.0",
                optional_dependencies=(
                    DomainDependency(domain_id=DomainId(slug="test"), required=False),
                ),
            )

    # ── Self-conflict ────────────────────────────────────────────────────

    def test_self_conflict(self) -> None:
        with pytest.raises(
            DomainContractValidationError, match="cannot conflict with itself"
        ):
            DomainDefinition(
                id="domain:test",
                name="test",
                display_name="Test",
                version="1.0",
                kind=DomainKind.CORE,
                description="desc",
                manifest_id="manifest:test:1.0",
                conflicts=(
                    DomainConflict(
                        domain_id=DomainId(slug="test"), reason="R", severity="low"
                    ),
                ),
            )

    # ── Dependency uniqueness across required/optional ───────────────────

    def test_dep_in_both_required_and_optional(self) -> None:
        dep = DomainDependency(domain_id=DomainId(slug="x"))
        with pytest.raises(DomainContractValidationError, match="appears in both"):
            DomainDefinition(
                id="domain:test",
                name="test",
                display_name="Test",
                version="1.0",
                kind=DomainKind.CORE,
                description="desc",
                manifest_id="manifest:test:1.0",
                dependencies=(dep,),
                optional_dependencies=(dep,),
            )

    # ── Required/optional flag enforcement ───────────────────────────────

    def test_required_dep_with_required_false(self) -> None:
        with pytest.raises(
            DomainContractValidationError, match="must have required=True"
        ):
            DomainDefinition(
                id="domain:test",
                name="test",
                display_name="Test",
                version="1.0",
                kind=DomainKind.CORE,
                description="desc",
                manifest_id="manifest:test:1.0",
                dependencies=(
                    DomainDependency(domain_id=DomainId(slug="x"), required=False),
                ),
            )

    def test_optional_dep_with_required_true(self) -> None:
        with pytest.raises(
            DomainContractValidationError, match="must have required=False"
        ):
            DomainDefinition(
                id="domain:test",
                name="test",
                display_name="Test",
                version="1.0",
                kind=DomainKind.CORE,
                description="desc",
                manifest_id="manifest:test:1.0",
                optional_dependencies=(
                    DomainDependency(domain_id=DomainId(slug="x"), required=True),
                ),
            )

    # ── Capability ownership ─────────────────────────────────────────────

    def test_capability_belongs_to_other_domain(self) -> None:
        with pytest.raises(DomainContractValidationError, match="must match domain id"):
            DomainDefinition(
                id="domain:test",
                name="test",
                display_name="Test",
                version="1.0",
                kind=DomainKind.CORE,
                description="desc",
                manifest_id="manifest:test:1.0",
                capabilities=(
                    DomainCapability(
                        name="cap",
                        kind="k",
                        provided_by=DomainId(slug="other-domain"),
                        version="1.0",
                    ),
                ),
            )

    # ── Duplicate conflicts ──────────────────────────────────────────────

    def test_duplicate_conflict_same_target(self) -> None:
        with pytest.raises(DomainContractValidationError, match="Duplicate conflict"):
            DomainDefinition(
                id="domain:test",
                name="test",
                display_name="Test",
                version="1.0",
                kind=DomainKind.CORE,
                description="desc",
                manifest_id="manifest:test:1.0",
                conflicts=(
                    DomainConflict(
                        domain_id=DomainId(slug="x"), reason="R1", severity="low"
                    ),
                    DomainConflict(
                        domain_id=DomainId(slug="x"), reason="R2", severity="high"
                    ),
                ),
            )

    # ── Duplicate string collections ─────────────────────────────────────

    def test_duplicate_resources(self) -> None:
        with pytest.raises(
            DomainContractValidationError, match="Duplicate items in resources"
        ):
            DomainDefinition(
                id="domain:test",
                name="test",
                display_name="Test",
                version="1.0",
                kind=DomainKind.CORE,
                description="desc",
                manifest_id="manifest:test:1.0",
                resources=("dup", "dup"),
            )

    # ── Manifest ID parsing from string ──────────────────────────────────

    def test_manifest_id_string_coercion(self) -> None:
        ddef = DomainDefinition(
            id="domain:test",
            name="test",
            display_name="Test",
            version="1.0.0",
            kind=DomainKind.CORE,
            description="desc",
            manifest_id="manifest:test:1.0.0",
        )
        assert ddef.manifest_id.slug == "test"
        assert ddef.manifest_id.version == "1.0.0"

    def test_manifest_id_string_missing_prefix(self) -> None:
        with pytest.raises(
            DomainContractValidationError, match="must start with 'manifest:'"
        ):
            DomainDefinition(
                id="domain:test",
                name="test",
                display_name="Test",
                version="1.0",
                kind=DomainKind.CORE,
                description="desc",
                manifest_id="test:1.0",
            )

    # ── String ID coercion ───────────────────────────────────────────────

    def test_string_id_coercion(self) -> None:
        ddef = DomainDefinition(
            id="domain:test",
            name="test",
            display_name="Test",
            version="1.0",
            kind=DomainKind.CORE,
            description="desc",
            manifest_id="manifest:test:1.0",
        )
        assert str(ddef.id) == "domain:test"

    # ── Immutability ─────────────────────────────────────────────────────

    def test_frozen(self) -> None:
        ddef = DomainDefinition(
            id="domain:test",
            name="test",
            display_name="Test",
            version="1.0",
            kind=DomainKind.CORE,
            description="desc",
            manifest_id="manifest:test:1.0",
        )
        with pytest.raises(Exception):  # noqa: B017
            ddef.name = "other"  # type: ignore[misc]

    # ── Defensive copy ───────────────────────────────────────────────────

    def test_defensive_copy_dependencies(self) -> None:
        deps = [DomainDependency(domain_id=DomainId(slug="x"))]
        ddef = DomainDefinition(
            id="domain:test",
            name="test",
            display_name="Test",
            version="1.0",
            kind=DomainKind.CORE,
            description="desc",
            manifest_id="manifest:test:1.0",
            dependencies=tuple(deps),
        )
        deps.append(DomainDependency(domain_id=DomainId(slug="y")))
        assert len(ddef.dependencies) == 1

    def test_empty_reasoning_profile_normalized(self) -> None:
        ddef = DomainDefinition(
            id="domain:test",
            name="test",
            display_name="Test",
            version="1.0",
            kind=DomainKind.CORE,
            description="desc",
            manifest_id="manifest:test:1.0",
            reasoning_profile="  ",
        )
        assert ddef.reasoning_profile is None

    # ── Metadata coercion from dict ──────────────────────────────────────

    def test_metadata_coercion_from_dict(self) -> None:
        ddef = DomainDefinition(
            id="domain:test",
            name="test",
            display_name="Test",
            version="1.0",
            kind=DomainKind.CORE,
            description="desc",
            manifest_id="manifest:test:1.0",
            metadata={"author": "A", "license": "MIT"},  # type: ignore[arg-type]
        )
        assert isinstance(ddef.metadata, DomainMetadata)
        assert ddef.metadata.author == "A"


# ── DomainResult ──────────────────────────────────────────────────────────────


class TestDomainResult:
    """Tests for DomainResult."""

    def test_valid_minimal(self) -> None:
        result = DomainResult(
            id=DomainResultId.generate(),
            status="completed",
            objective="Analyze data",
            primary_domain=DomainId(slug="core"),
        )
        assert result.status == "completed"
        assert str(result.primary_domain) == "domain:core"
        assert result.confidence == 0.0

    def test_valid_full(self) -> None:
        created = datetime(2024, 6, 1, tzinfo=timezone.utc)
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
            trace_id="trace-1",
            session_id="session-1",
            created_at=created,
            metadata={"source": "test"},
        )
        assert len(result.supporting_domains) == 1
        assert result.confidence == 0.95
        assert len(result.findings) == 1
        assert len(result.recommendations) == 1

    # ── Confidence bounds ────────────────────────────────────────────────

    def test_confidence_below_zero(self) -> None:
        with pytest.raises(DomainContractValidationError, match="between 0.0 and 1.0"):
            DomainResult(
                id=DomainResultId.generate(),
                status="ok",
                objective="test",
                primary_domain=DomainId(slug="core"),
                confidence=-0.1,
            )

    def test_confidence_above_one(self) -> None:
        with pytest.raises(DomainContractValidationError, match="between 0.0 and 1.0"):
            DomainResult(
                id=DomainResultId.generate(),
                status="ok",
                objective="test",
                primary_domain=DomainId(slug="core"),
                confidence=1.5,
            )

    def test_confidence_one_is_valid(self) -> None:
        result = DomainResult(
            id=DomainResultId.generate(),
            status="ok",
            objective="test",
            primary_domain=DomainId(slug="core"),
            confidence=1.0,
        )
        assert result.confidence == 1.0

    def test_confidence_zero_is_valid(self) -> None:
        result = DomainResult(
            id=DomainResultId.generate(),
            status="ok",
            objective="test",
            primary_domain=DomainId(slug="core"),
            confidence=0.0,
        )
        assert result.confidence == 0.0

    # ── Primary/supporting domains ───────────────────────────────────────

    def test_primary_as_supporting(self) -> None:
        with pytest.raises(
            DomainContractValidationError, match="primary domain in supporting"
        ):
            DomainResult(
                id=DomainResultId.generate(),
                status="ok",
                objective="test",
                primary_domain=DomainId(slug="core"),
                supporting_domains=(DomainId(slug="core"),),
            )

    def test_duplicate_supporting(self) -> None:
        with pytest.raises(DomainContractValidationError, match="Duplicate or primary"):
            DomainResult(
                id=DomainResultId.generate(),
                status="ok",
                objective="test",
                primary_domain=DomainId(slug="core"),
                supporting_domains=(DomainId(slug="helper"), DomainId(slug="helper")),
            )

    # ── Empty strings ────────────────────────────────────────────────────

    def test_empty_status(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainResult(
                id=DomainResultId.generate(),
                status="",
                objective="test",
                primary_domain=DomainId(slug="core"),
            )

    def test_empty_objective(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainResult(
                id=DomainResultId.generate(),
                status="ok",
                objective="",
                primary_domain=DomainId(slug="core"),
            )

    # ── Naive datetime ───────────────────────────────────────────────────

    def test_naive_created_at(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainResult(
                id=DomainResultId.generate(),
                status="ok",
                objective="test",
                primary_domain=DomainId(slug="core"),
                created_at=datetime(2024, 1, 1),  # noqa: DTZ001
            )

    # ── String ID coercion ───────────────────────────────────────────────

    def test_primary_domain_string_coercion(self) -> None:
        result = DomainResult(
            id="domain-result:abc",
            status="ok",
            objective="test",
            primary_domain="domain:core",
        )
        assert isinstance(result.primary_domain, DomainId)

    def test_supporting_domain_string_coercion(self) -> None:
        result = DomainResult(
            id=DomainResultId.generate(),
            status="ok",
            objective="test",
            primary_domain=DomainId(slug="core"),
            supporting_domains=("domain:helper",),
        )
        assert isinstance(result.supporting_domains[0], DomainId)

    # ── Immutability ─────────────────────────────────────────────────────

    def test_frozen(self) -> None:
        result = DomainResult(
            id=DomainResultId.generate(),
            status="ok",
            objective="test",
            primary_domain=DomainId(slug="core"),
        )
        with pytest.raises(Exception):  # noqa: B017
            result.confidence = 0.5  # type: ignore[misc]

    # ── Empty collections normalized ─────────────────────────────────────

    def test_empty_optional_strings_normalized(self) -> None:
        result = DomainResult(
            id=DomainResultId.generate(),
            status="ok",
            objective="test",
            primary_domain=DomainId(slug="core"),
            reasoning_result_id="  ",
            workflow_result_id="  ",
            trace_id="  ",
            session_id="  ",
        )
        assert result.reasoning_result_id is None
        assert result.workflow_result_id is None
        assert result.trace_id is None
        assert result.session_id is None


# ── Enum values ───────────────────────────────────────────────────────────────


class TestDomainEnums:
    """Tests for DomainStatus and DomainKind."""

    def test_domain_status_all_values(self) -> None:
        expected = {
            "discovered",
            "registered",
            "loading",
            "active",
            "disabled",
            "degraded",
            "incompatible",
            "invalid",
            "failed",
            "unloaded",
        }
        actual = {v.value for v in DomainStatus}
        assert expected == actual

    def test_domain_kind_all_values(self) -> None:
        expected = {
            "core",
            "personal",
            "professional",
            "project",
            "system",
            "external",
            "experimental",
        }
        actual = {v.value for v in DomainKind}
        assert expected == actual


# ── Regression: strict booleans ───────────────────────────────────────────────


class TestStrictBooleans:
    """Regression tests for strict boolean validation."""

    def test_experimental_rejects_0(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainMetadata(author="A", license="MIT", experimental=0)  # type: ignore[arg-type]

    def test_experimental_rejects_1(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainMetadata(author="A", license="MIT", experimental=1)  # type: ignore[arg-type]

    def test_deprecated_rejects_string(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainMetadata(author="A", license="MIT", deprecated="false")  # type: ignore[arg-type]

    def test_required_rejects_0(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainDependency(domain_id="domain:test", required=0)  # type: ignore[arg-type]

    def test_required_rejects_1(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainDependency(domain_id="domain:test", required=1)  # type: ignore[arg-type]

    def test_enabled_rejects_0(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainDefinition(
                id="domain:test",
                name="test",
                display_name="Test",
                version="1.0",
                kind=DomainKind.CORE,
                description="desc",
                manifest_id="manifest:test:1.0",
                enabled=0,  # type: ignore[arg-type]
            )

    def test_enabled_rejects_1_in_domain_definition(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainDefinition(
                id="domain:test",
                name="test",
                display_name="Test",
                version="1.0",
                kind=DomainKind.CORE,
                description="desc",
                manifest_id="manifest:test:1.0",
                enabled=1,  # type: ignore[arg-type]
            )

    def test_experimental_from_dict_rejects_0(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainMetadata.from_dict(
                {"author": "A", "license": "MIT", "experimental": 0}
            )

    def test_deprecated_from_dict_rejects_1(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainMetadata.from_dict({"author": "A", "license": "MIT", "deprecated": 1})

    def test_required_from_dict_rejects_list(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainDependency.from_dict({"domain_id": "domain:test", "required": []})

    def test_enabled_from_dict_rejects_string(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainDefinition.from_dict(
                {
                    "id": "domain:test",
                    "name": "test",
                    "display_name": "Test",
                    "version": "1.0",
                    "kind": "core",
                    "description": "desc",
                    "manifest_id": "manifest:test:1.0",
                    "enabled": "true",
                }
            )


# ── Regression: strict confidence ─────────────────────────────────────────────


class TestStrictConfidence:
    """Regression tests for strict confidence validation."""

    def test_confidence_true_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainResult(
                id=DomainResultId.generate(),
                status="ok",
                objective="test",
                primary_domain=DomainId(slug="core"),
                confidence=True,  # type: ignore[arg-type]
            )

    def test_confidence_false_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainResult(
                id=DomainResultId.generate(),
                status="ok",
                objective="test",
                primary_domain=DomainId(slug="core"),
                confidence=False,  # type: ignore[arg-type]
            )

    def test_confidence_string_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainResult(
                id=DomainResultId.generate(),
                status="ok",
                objective="test",
                primary_domain=DomainId(slug="core"),
                confidence="0.5",  # type: ignore[arg-type]
            )

    def test_confidence_nan_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainResult(
                id=DomainResultId.generate(),
                status="ok",
                objective="test",
                primary_domain=DomainId(slug="core"),
                confidence=float("nan"),
            )

    def test_confidence_inf_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainResult(
                id=DomainResultId.generate(),
                status="ok",
                objective="test",
                primary_domain=DomainId(slug="core"),
                confidence=float("inf"),
            )

    def test_confidence_neg_inf_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainResult(
                id=DomainResultId.generate(),
                status="ok",
                objective="test",
                primary_domain=DomainId(slug="core"),
                confidence=float("-inf"),
            )

    def test_confidence_none_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainResult(
                id=DomainResultId.generate(),
                status="ok",
                objective="test",
                primary_domain=DomainId(slug="core"),
                confidence=None,  # type: ignore[arg-type]
            )

    def test_confidence_list_rejected(self) -> None:
        with pytest.raises(DomainContractValidationError):
            DomainResult(
                id=DomainResultId.generate(),
                status="ok",
                objective="test",
                primary_domain=DomainId(slug="core"),
                confidence=[],  # type: ignore[arg-type]
            )

    def test_confidence_int_0_is_valid(self) -> None:
        result = DomainResult(
            id=DomainResultId.generate(),
            status="ok",
            objective="test",
            primary_domain=DomainId(slug="core"),
            confidence=0,
        )
        assert result.confidence == 0.0

    def test_confidence_int_1_is_valid(self) -> None:
        result = DomainResult(
            id=DomainResultId.generate(),
            status="ok",
            objective="test",
            primary_domain=DomainId(slug="core"),
            confidence=1,
        )
        assert result.confidence == 1.0

    def test_confidence_from_dict_rejects_string(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainResult.from_dict(
                {
                    "id": "domain-result:abc",
                    "status": "ok",
                    "objective": "test",
                    "primary_domain": "domain:core",
                    "confidence": "0.5",
                }
            )

    def test_confidence_from_dict_rejects_bool(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainResult.from_dict(
                {
                    "id": "domain-result:abc",
                    "status": "ok",
                    "objective": "test",
                    "primary_domain": "domain:core",
                    "confidence": True,
                }
            )

    def test_confidence_from_dict_rejects_inf(self) -> None:
        with pytest.raises(DomainSerializationError):
            DomainResult.from_dict(
                {
                    "id": "domain-result:abc",
                    "status": "ok",
                    "objective": "test",
                    "primary_domain": "domain:core",
                    "confidence": float("inf"),
                }
            )


# ── Regression: deep immutability ─────────────────────────────────────────────


class TestDeepImmutability:
    """Regression tests for deep-frozen structures."""

    def test_metadata_nested_dict_is_immutable(self) -> None:
        meta = DomainMetadata(
            author="A",
            license="MIT",
            metadata={"nested": {"key": "value"}},
        )
        assert isinstance(meta.metadata, MappingProxyType)
        assert isinstance(meta.metadata["nested"], MappingProxyType)
        with pytest.raises(TypeError):
            meta.metadata["nested"]["key"] = "changed"  # type: ignore[index]

    def test_metadata_deep_copy_defensive(self) -> None:
        d = {"nested": {"items": [1, 2, 3]}}
        meta = DomainMetadata(author="A", license="MIT", metadata=d)
        d["nested"]["items"].append(4)
        assert meta.metadata["nested"]["items"] == (1, 2, 3)  # type: ignore[index]

    def test_findings_are_deep_immutable(self) -> None:
        finding = {"key": "value", "nested": {"inner": 42}}
        result = DomainResult(
            id=DomainResultId.generate(),
            status="ok",
            objective="test",
            primary_domain=DomainId(slug="core"),
            findings=(finding,),
        )
        finding["key"] = "changed"
        assert result.findings[0]["key"] == "value"  # type: ignore[index]
        assert isinstance(result.findings[0], MappingProxyType)

    def test_recommendations_deep_copy_defensive(self) -> None:
        rec = {"action": "do-x"}
        result = DomainResult(
            id=DomainResultId.generate(),
            status="ok",
            objective="test",
            primary_domain=DomainId(slug="core"),
            recommendations=(rec,),
        )
        rec["extra"] = "oops"
        assert "extra" not in result.recommendations[0]

    def test_presentation_policy_deep_immutable(self) -> None:
        ddef = DomainDefinition(
            id="domain:test",
            name="test",
            display_name="Test",
            version="1.0",
            kind=DomainKind.CORE,
            description="desc",
            manifest_id="manifest:test:1.0",
            presentation_policy={"theme": "dark", "colors": ["red", "blue"]},
        )
        assert isinstance(ddef.presentation_policy, MappingProxyType)
        assert isinstance(ddef.presentation_policy["colors"], tuple)
        with pytest.raises(TypeError):
            ddef.presentation_policy["colors"][0] = "green"  # type: ignore[index]

    def test_error_details_deep_immutable(self) -> None:
        err = DomainContractValidationError(
            "test", field="x", details={"nested": {"key": "value"}}
        )
        assert isinstance(err.details["nested"], MappingProxyType)


# ── Regression: nested error context ──────────────────────────────────────────


class TestNestedErrorContext:
    """Regression tests for nested error paths."""

    def test_invalid_dependency_field_path(self) -> None:
        with pytest.raises(DomainSerializationError) as exc_info:
            DomainDefinition.from_dict(
                {
                    "id": "domain:test",
                    "name": "test",
                    "display_name": "Test",
                    "version": "1.0",
                    "kind": "core",
                    "description": "desc",
                    "manifest_id": "manifest:test:1.0",
                    "dependencies": [{"domain_id": "domain:dep-a", "required": "yes"}],
                }
            )
        assert "dependencies[0]" in str(exc_info.value.field)

    def test_invalid_conflict_field_path(self) -> None:
        with pytest.raises(DomainError) as exc_info:
            DomainDefinition.from_dict(
                {
                    "id": "domain:test",
                    "name": "test",
                    "display_name": "Test",
                    "version": "1.0",
                    "kind": "core",
                    "description": "desc",
                    "manifest_id": "manifest:test:1.0",
                    "conflicts": [
                        {"domain_id": "domain:x", "reason": "r", "severity": ""}
                    ],
                }
            )
        assert "conflicts[0]" in str(exc_info.value.field)

    def test_invalid_capability_domain_id_field_path(self) -> None:
        with pytest.raises(DomainError) as exc_info:
            DomainDefinition.from_dict(
                {
                    "id": "domain:test",
                    "name": "test",
                    "display_name": "Test",
                    "version": "1.0",
                    "kind": "core",
                    "description": "desc",
                    "manifest_id": "manifest:test:1.0",
                    "capabilities": [
                        {"name": "", "kind": "k", "provided_by": "BAD", "version": "1"}
                    ],
                }
            )
        assert "capabilities[0]" in str(exc_info.value.field)

    def test_invalid_capability_name_field_path(self) -> None:
        with pytest.raises(DomainError) as exc_info:
            DomainDefinition.from_dict(
                {
                    "id": "domain:test",
                    "name": "test",
                    "display_name": "Test",
                    "version": "1.0",
                    "kind": "core",
                    "description": "desc",
                    "manifest_id": "manifest:test:1.0",
                    "capabilities": [
                        {
                            "name": "",
                            "kind": "k",
                            "provided_by": "domain:test",
                            "version": "1",
                        }
                    ],
                }
            )
        assert "capabilities[0]" in str(exc_info.value.field)

    def test_invalid_metadata_nested_error(self) -> None:
        with pytest.raises(DomainError) as exc_info:
            DomainDefinition.from_dict(
                {
                    "id": "domain:test",
                    "name": "test",
                    "display_name": "Test",
                    "version": "1.0",
                    "kind": "core",
                    "description": "desc",
                    "manifest_id": "manifest:test:1.0",
                    "metadata": {"author": "A", "license": ""},
                }
            )
        assert "metadata" in str(exc_info.value.field)

    def test_invalid_supporting_domain_field_path(self) -> None:
        with pytest.raises(DomainSerializationError) as exc_info:
            DomainResult.from_dict(
                {
                    "id": "domain-result:abc",
                    "status": "ok",
                    "objective": "test",
                    "primary_domain": "domain:core",
                    "supporting_domains": ["not-a-domain-id"],
                }
            )
        assert "supporting_domains[0]" in str(exc_info.value.field)

    def test_invalid_original_code_preserved(self) -> None:
        with pytest.raises(DomainSerializationError) as exc_info:
            DomainDefinition.from_dict(
                {
                    "id": "domain:test",
                    "name": "test",
                    "display_name": "Test",
                    "version": "1.0",
                    "kind": "core",
                    "description": "desc",
                    "manifest_id": "manifest:test:1.0",
                    "dependencies": [{"domain_id": "domain:dep-a", "required": "yes"}],
                }
            )
        details = dict(exc_info.value.details)
        assert "_original_code" in details

    def test_invalid_type_in_dependency_list(self) -> None:
        with pytest.raises(DomainSerializationError) as exc_info:
            DomainDefinition.from_dict(
                {
                    "id": "domain:test",
                    "name": "test",
                    "display_name": "Test",
                    "version": "1.0",
                    "kind": "core",
                    "description": "desc",
                    "manifest_id": "manifest:test:1.0",
                    "dependencies": ["not-a-mapping"],
                }
            )
        assert "dependencies[0]" in str(exc_info.value.field)

    def test_invalid_type_in_findings_list(self) -> None:
        with pytest.raises(DomainSerializationError) as exc_info:
            DomainResult.from_dict(
                {
                    "id": "domain-result:abc",
                    "status": "ok",
                    "objective": "test",
                    "primary_domain": "domain:core",
                    "findings": ["not-a-mapping"],
                }
            )
        assert "findings[0]" in str(exc_info.value.field)
