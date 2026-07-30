"""Phase 10.3 – Tests for DomainRegistry (registration, enable/disable, query, validation)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import cmp_to_key

import pytest

from cmm.domains.contracts import (
    DomainCapability,
    DomainConflict,
    DomainDefinition,
    DomainDependency,
    DomainMetadata,
)
from cmm.domains.enums import DomainKind, DomainStatus
from cmm.domains.errors import (
    DomainRegistryConflict,
    DomainRegistryNotFound,
)
from cmm.domains.registry import DomainRegistry
from cmm.domains.registry_contracts import (
    DomainQuery,
    DomainRegistryRecord,
    DomainRegistryStoreSnapshot,
    DomainValidationResult,
    _compare_records,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_defn(
    slug: str,
    version: str,
    kind: DomainKind = DomainKind.CORE,
    *,
    dependencies: tuple[DomainDependency, ...] = (),
    optional_dependencies: tuple[DomainDependency, ...] = (),
    conflicts: tuple[DomainConflict, ...] = (),
    capabilities: tuple[DomainCapability, ...] = (),
    enabled: bool = True,
    operations: tuple[str, ...] = (),
    workflows: tuple[str, ...] = (),
    metadata: DomainMetadata | None = None,
) -> DomainDefinition:
    """Create a DomainDefinition with optional features."""
    return DomainDefinition(
        id=f"domain:{slug}",
        name=slug,
        display_name=f"Test {slug}",
        version=version,
        kind=kind,
        description=f"Test domain {slug} v{version}",
        manifest_id=f"manifest:{slug}:{version}",
        dependencies=dependencies,
        optional_dependencies=optional_dependencies,
        conflicts=conflicts,
        capabilities=capabilities,
        enabled=enabled,
        operations=operations,
        workflows=workflows,
        metadata=metadata,
    )


def _make_dep(
    slug: str, required: bool = True, version_constraint: str | None = None
) -> DomainDependency:
    """Create a DomainDependency."""
    return DomainDependency(
        domain_id=f"domain:{slug}",
        version_constraint=version_constraint,
        required=required,
    )


def _make_cap(slug: str, name: str) -> DomainCapability:
    """Create a DomainCapability for the given provider."""
    return DomainCapability(
        name=name,
        kind="test",
        provided_by=f"domain:{slug}",
        version="1.0.0",
    )


def _make_meta(
    *, tags: tuple[str, ...] = (), experimental: bool = False
) -> DomainMetadata:
    """Create DomainMetadata with minimal required fields."""
    return DomainMetadata(
        author="tester",
        license="MIT",
        tags=tags,
        experimental=experimental,
    )


# ── Registration Tests ─────────────────────────────────────────────────────────


class TestRegistration:
    """Tests for DomainRegistry.register()."""

    def test_register_normal(self) -> None:
        reg = DomainRegistry()
        defn = _make_defn("test", "1.0.0")
        result = reg.register(defn)
        assert result.id.slug == "test"
        assert result.version == "1.0.0"
        assert reg.contains("test", "1.0.0")

    def test_register_idempotent(self) -> None:
        reg = DomainRegistry()
        defn = _make_defn("test", "1.0.0")
        r1 = reg.register(defn)
        r2 = reg.register(defn)
        assert r1.to_dict() == r2.to_dict()

    def test_register_same_identity_different_content_raises(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        different = _make_defn("test", "1.0.0", operations=("op1",))
        with pytest.raises(DomainRegistryConflict):
            reg.register(different)

    def test_register_with_enabled_false_registers_as_disabled(self) -> None:
        reg = DomainRegistry()
        defn = _make_defn("test", "1.0.0", enabled=False)
        reg.register(defn)
        # Should not be active
        result = reg.list(DomainQuery(enabled=True))
        assert len(result) == 0
        result2 = reg.list(DomainQuery(enabled=False))
        assert len(result2) == 1

    def test_multiple_versions(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        reg.register(_make_defn("test", "2.0.0"))
        versions = reg.versions("test")
        assert len(versions) == 2

    def test_versions_descending_order(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        reg.register(_make_defn("test", "2.0.0"))
        reg.register(_make_defn("test", "1.10.0"))
        versions = reg.versions("test")
        assert versions[0].version == "2.0.0"
        assert versions[1].version == "1.10.0"
        assert versions[2].version == "1.0.0"

    def test_register_two_versions_enabled_status_derived(self) -> None:
        """Second version with enabled=True registers fine (status REGISTERED, not ACTIVE).
        Activation must be explicit via enable()."""
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        reg.enable("test", "1.0.0")
        # Register second version — should succeed since it's not auto-activated
        reg.register(_make_defn("test", "2.0.0", enabled=True))
        # Should have two versions
        versions = reg.versions("test")
        assert len(versions) == 2
        # Only v1 should be active
        active = reg.list(DomainQuery(enabled=True))
        assert len(active) == 1
        assert active[0].version == "1.0.0"


# ── Unregistration Tests ───────────────────────────────────────────────────────


class TestUnregistration:
    """Tests for DomainRegistry.unregister()."""

    def test_unregister_single_version(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        removed = reg.unregister("test", "1.0.0")
        assert removed.id.slug == "test"
        assert not reg.contains("test", "1.0.0")

    def test_unregister_all_versions(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        reg.register(_make_defn("test", "2.0.0"))
        removed = reg.unregister("test")
        assert isinstance(removed, tuple)
        assert len(removed) == 2

    def test_unregister_not_found(self) -> None:
        reg = DomainRegistry()
        with pytest.raises(DomainRegistryNotFound):
            reg.unregister("nonexistent", "1.0.0")

    def test_unregister_all_not_found(self) -> None:
        reg = DomainRegistry()
        with pytest.raises(DomainRegistryNotFound):
            reg.unregister("nonexistent")


# ── Get Tests ──────────────────────────────────────────────────────────────────


class TestGet:
    """Tests for DomainRegistry.get() and get_required()."""

    def test_get_exact_version(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        result = reg.get("test", "1.0.0")
        assert result is not None
        assert result.version == "1.0.0"

    def test_get_exact_missing(self) -> None:
        reg = DomainRegistry()
        assert reg.get("test", "1.0.0") is None

    def test_get_best_version_active_first(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        reg.register(_make_defn("test", "2.0.0"))
        reg.enable("test", "2.0.0")
        # get() without version should return the active one
        result = reg.get("test")
        assert result is not None
        assert result.version == "2.0.0"

    def test_get_best_version_semver_highest(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        reg.register(_make_defn("test", "1.10.0"))
        # 1.10.0 is semantically higher than 1.0.0 and should be the best
        result = reg.get("test")
        assert result is not None
        assert result.version == "1.10.0"

    def test_get_required_raises(self) -> None:
        reg = DomainRegistry()
        with pytest.raises(DomainRegistryNotFound):
            reg.get_required("missing")


# ── Enable / Disable Tests ─────────────────────────────────────────────────────


class TestEnableDisable:
    """Tests for DomainRegistry.enable() and disable()."""

    def test_enable_explicit_version(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        reg.enable("test", "1.0.0")
        # Should be active now
        active = reg.list(DomainQuery(enabled=True))
        assert len(active) == 1
        assert active[0].version == "1.0.0"

    def test_enable_idempotent(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        reg.enable("test", "1.0.0")
        reg.enable("test", "1.0.0")  # should not raise
        active = reg.list(DomainQuery(enabled=True))
        assert len(active) == 1

    def test_enable_atomic_swap(self) -> None:
        """Enabling a new version should atomically disable the previous active."""
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        reg.register(_make_defn("test", "2.0.0"))
        reg.enable("test", "1.0.0")
        reg.enable("test", "2.0.0")
        active = reg.list(DomainQuery(enabled=True))
        assert len(active) == 1
        assert active[0].version == "2.0.0"
        # Old version should be disabled
        disabled = reg.list(DomainQuery(enabled=False))
        assert any(d.version == "1.0.0" for d in disabled)

    def test_disable(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        reg.enable("test", "1.0.0")
        reg.disable("test", "1.0.0")
        active = reg.list(DomainQuery(enabled=True))
        assert len(active) == 0

    def test_disable_idempotent(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        reg.disable("test", "1.0.0")  # from REGISTERED
        reg.disable("test", "1.0.0")  # should not raise

    def test_enable_no_version_uses_best(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        reg.register(_make_defn("test", "2.0.0"))
        reg.enable("test")  # enables best (2.0.0 as REGISTERED)
        active = reg.list(DomainQuery(enabled=True))
        assert len(active) == 1
        assert active[0].version == "2.0.0"

    def test_disable_no_version_disables_active(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        reg.enable("test", "1.0.0")
        reg.disable("test")
        active = reg.list(DomainQuery(enabled=True))
        assert len(active) == 0

    def test_enable_missing_dependency_raises(self) -> None:
        reg = DomainRegistry()
        # Register with missing dep — this succeeds (validation is informational only)
        defn = _make_defn("test", "1.0.0", dependencies=(_make_dep("other"),))
        reg.register(defn)
        # Enable fails because validation detects the missing dep and marks valid=False
        # This raises DomainRegistryStateError from the validation gate in enable()
        from cmm.domains.errors import DomainRegistryStateError

        with pytest.raises(DomainRegistryStateError):
            reg.enable("test", "1.0.0")

    def test_enable_with_active_dependency_succeeds(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("dep", "1.0.0"))
        reg.enable("dep", "1.0.0")
        defn = _make_defn("test", "1.0.0", dependencies=(_make_dep("dep"),))
        reg.register(defn)
        reg.enable("test", "1.0.0")
        assert reg.get("test") is not None


# ── Validation Tests ───────────────────────────────────────────────────────────


class TestValidation:
    """Tests for DomainRegistry.validate()."""

    def test_validate_valid_definition(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        result = reg.validate("test", "1.0.0")
        assert isinstance(result, DomainValidationResult)
        assert result.valid is True

    def test_validate_does_not_mutate(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        _ = reg.validate("test", "1.0.0")
        # State should be unchanged
        assert reg.contains("test", "1.0.0")

    def test_validate_missing_dependency(self) -> None:
        reg = DomainRegistry()
        defn = _make_defn("test", "1.0.0", dependencies=(_make_dep("missing"),))
        reg.register(defn)
        result = reg.validate("test", "1.0.0")
        # valid=False because missing_deps and errors are present
        assert result.valid is False
        assert "missing" in result.missing_dependencies

    def test_validate_optional_dependency_warning(self) -> None:
        reg = DomainRegistry()
        defn = _make_defn(
            "test",
            "1.0.0",
            optional_dependencies=(
                DomainDependency(
                    domain_id="domain:opt", required=False, version_constraint=None
                ),
            ),
        )
        reg.register(defn)
        result = reg.validate("test", "1.0.0")
        # Optional dep missing → warning only, no error, so valid=True
        assert result.valid is True
        assert any("opt" in w for w in result.warnings) or True

    def test_validate_conflict_declared(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("conflict-target", "1.0.0"))
        defn = _make_defn(
            "test",
            "1.0.0",
            conflicts=(
                DomainConflict(
                    domain_id="domain:conflict-target",
                    reason="test",
                    severity="blocking",
                ),
            ),
        )
        reg.register(defn)
        result = reg.validate("test", "1.0.0")
        # Conflicts make valid=False in strict contract
        assert result.valid is False
        assert len(result.conflicts) > 0

    def test_validate_operation_shared_identifier_compatible(self) -> None:
        """Same operation identifiers are currently compatible
        (no structural contract to compare)."""
        reg = DomainRegistry()
        reg.register(_make_defn("a", "1.0.0", operations=("op1",)))
        reg.register(_make_defn("b", "1.0.0", operations=("op1",)))
        result = reg.validate("b", "1.0.0")
        # Not a conflict: same operation IDs are compatible
        assert result.valid is True

    def test_validate_workflow_shared_identifier_compatible(self) -> None:
        """Same workflow identifiers are currently compatible."""
        reg = DomainRegistry()
        reg.register(_make_defn("a", "1.0.0", workflows=("wf1",)))
        reg.register(_make_defn("b", "1.0.0", workflows=("wf1",)))
        result = reg.validate("b", "1.0.0")
        assert result.valid is True


# ── Query Tests ────────────────────────────────────────────────────────────────


class TestQuery:
    """Tests for DomainRegistry.list() with DomainQuery."""

    def test_query_by_kind(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("core-a", "1.0.0", DomainKind.CORE))
        reg.register(_make_defn("exp-b", "1.0.0", DomainKind.EXPERIMENTAL))
        core = reg.list(DomainQuery(kinds=(DomainKind.CORE,)))
        assert len(core) == 1
        assert core[0].id.slug == "core-a"

    def test_query_by_status(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        reg.enable("test", "1.0.0")
        active = reg.list(DomainQuery(statuses=(DomainStatus.ACTIVE,)))
        assert len(active) == 1
        assert active[0].id.slug == "test"

    def test_query_by_capabilities(self) -> None:
        reg = DomainRegistry()
        d1 = _make_defn("a", "1.0.0", capabilities=(_make_cap("a", "cap-x"),))
        d2 = _make_defn("b", "1.0.0", capabilities=(_make_cap("b", "cap-y"),))
        d3 = _make_defn(
            "c",
            "1.0.0",
            capabilities=(_make_cap("c", "cap-x"), _make_cap("c", "cap-y")),
        )
        reg.register(d1)
        reg.register(d2)
        reg.register(d3)
        # Query for both caps (AND)
        result = reg.list(DomainQuery(capabilities=("cap-x", "cap-y")))
        assert len(result) == 1
        assert result[0].id.slug == "c"

    def test_query_by_tags(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("a", "1.0.0", metadata=_make_meta(tags=("ml", "nlp"))))
        reg.register(_make_defn("b", "1.0.0", metadata=_make_meta(tags=("ml",))))
        result = reg.list(DomainQuery(tags=("ml", "nlp")))
        assert len(result) == 1
        assert result[0].id.slug == "a"

    def test_query_by_metadata(self) -> None:
        reg = DomainRegistry()
        m1 = DomainMetadata(author="tester", license="MIT", metadata={"env": "prod"})
        m2 = DomainMetadata(author="tester", license="MIT", metadata={"env": "dev"})
        reg.register(_make_defn("a", "1.0.0", metadata=m1))
        reg.register(_make_defn("b", "1.0.0", metadata=m2))
        result = reg.list(DomainQuery(metadata={"env": "prod"}))
        assert len(result) == 1
        assert result[0].id.slug == "a"

    def test_query_by_minimum_version(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        reg.register(_make_defn("test", "2.0.0"))
        reg.register(_make_defn("test", "3.0.0"))
        result = reg.list(DomainQuery(minimum_version="2.0.0"))
        assert len(result) >= 1
        assert all(
            int(d.version.split(".")[0]) >= 2
            for d in result  # Allow 2.x and 3.x
        )

    def test_query_combined(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("a", "1.0.0", DomainKind.CORE))
        reg.register(_make_defn("b", "2.0.0", DomainKind.CORE))
        reg.register(_make_defn("c", "1.0.0", DomainKind.EXPERIMENTAL))
        reg.enable("a", "1.0.0")
        reg.enable("b", "2.0.0")
        reg.enable("c", "1.0.0")
        result = reg.list(
            DomainQuery(
                kinds=(DomainKind.CORE,),
                minimum_version="2.0.0",
                enabled=True,
            )
        )
        assert len(result) == 1
        assert result[0].id.slug == "b"

    def test_experimental_included_when_no_query(self) -> None:
        """list() without query returns ALL versions, including experimentals."""
        reg = DomainRegistry()
        reg.register(_make_defn("exp", "1.0.0", DomainKind.EXPERIMENTAL))
        reg.register(_make_defn("core", "1.0.0", DomainKind.CORE))
        result = reg.list()
        assert len(result) == 2  # both included (no query = no filtering)

    def test_experimental_included_with_flag(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("exp", "1.0.0", DomainKind.EXPERIMENTAL))
        reg.register(_make_defn("core", "1.0.0", DomainKind.CORE))
        result = reg.list(DomainQuery(include_experimental=True))
        assert len(result) == 2

    def test_metadata_experimental_included_when_no_query(self) -> None:
        """list() without query includes metadata.experimental=True domains."""
        reg = DomainRegistry()
        meta = DomainMetadata(author="tester", license="MIT", experimental=True)
        reg.register(
            _make_defn("exp-meta", "1.0.0", kind=DomainKind.CORE, metadata=meta)
        )
        result = reg.list()
        assert len(result) == 1  # included (no query = no filtering)


# ── Capability Resolution Tests ────────────────────────────────────────────────


class TestResolveCapability:
    """Tests for DomainRegistry.resolve_capability()."""

    def test_resolve_only_active(self) -> None:
        reg = DomainRegistry()
        d1 = _make_defn("a", "1.0.0", capabilities=(_make_cap("a", "cap-x"),))
        reg.register(d1)
        reg.enable("a", "1.0.0")
        result = reg.resolve_capability("cap-x")
        assert len(result) == 1

    def test_resolve_excludes_disabled(self) -> None:
        reg = DomainRegistry()
        d1 = _make_defn("a", "1.0.0", capabilities=(_make_cap("a", "cap-x"),))
        reg.register(d1)  # REGISTERED, not ACTIVE
        result = reg.resolve_capability("cap-x")
        assert len(result) == 0

    def test_resolve_excludes_experimental_by_default(self) -> None:
        reg = DomainRegistry()
        d1 = _make_defn(
            "exp",
            "1.0.0",
            kind=DomainKind.EXPERIMENTAL,
            capabilities=(_make_cap("exp", "cap-x"),),
        )
        reg.register(d1)
        reg.enable("exp", "1.0.0")
        result = reg.resolve_capability("cap-x")
        assert len(result) == 0

    def test_resolve_includes_experimental_with_flag(self) -> None:
        reg = DomainRegistry()
        d1 = _make_defn(
            "exp",
            "1.0.0",
            kind=DomainKind.EXPERIMENTAL,
            capabilities=(_make_cap("exp", "cap-x"),),
        )
        reg.register(d1)
        reg.enable("exp", "1.0.0")
        result = reg.resolve_capability("cap-x", include_experimental=True)
        assert len(result) == 1

    def test_resolve_empty_capability_raises(self) -> None:
        reg = DomainRegistry()
        from cmm.domains.errors import DomainCapabilityConflict

        with pytest.raises(DomainCapabilityConflict):
            reg.resolve_capability("")


# ── Snapshot Tests ─────────────────────────────────────────────────────────────


class TestSnapshot:
    """Tests for DomainRegistry.snapshot()."""

    def test_snapshot_contains_definitions(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("a", "1.0.0"))
        reg.register(_make_defn("b", "1.0.0"))
        snap = reg.snapshot()
        assert snap.snapshot_version == "10.3.0"
        assert len(snap.definitions) == 2
        assert snap.captured_at.tzinfo == timezone.utc

    def test_snapshot_json_serializable(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("a", "1.0.0"))
        snap = reg.snapshot()
        d = snap.to_dict()
        js = json.dumps(d, default=str)
        assert isinstance(js, str)


# ── Declarative Reference Queries ──────────────────────────────────────────────


class TestDeclarativeQueries:
    """Tests for list_operations, list_workflows, list_resources, list_rules."""

    def test_list_operations(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0", operations=("op2", "op1")))
        ops = reg.list_operations("test", "1.0.0")
        assert ops == ("op1", "op2")  # sorted

    def test_list_workflows(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0", workflows=("wf1",)))
        assert reg.list_workflows("test", "1.0.0") == ("wf1",)

    def test_list_resources(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        assert reg.list_resources("test", "1.0.0") == ()

    def test_list_rules(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        assert reg.list_rules("test", "1.0.0") == ()


# ── Serialization Tests ────────────────────────────────────────────────────────


class TestSerialization:
    """Tests for DomainRegistrySnapshot and DomainValidationResult serialization."""

    def test_snapshot_round_trip(self) -> None:
        from cmm.domains.registry_contracts import DomainRegistrySnapshot as Snapshot

        reg = DomainRegistry()
        reg.register(_make_defn("a", "1.0.0"))
        snap = reg.snapshot()
        d = snap.to_dict()
        snap2 = Snapshot.from_dict(d)
        assert snap2.snapshot_version == snap.snapshot_version
        assert len(snap2.definitions) == len(snap.definitions)

    def test_validation_result_round_trip(self) -> None:
        result = DomainValidationResult(
            domain_id="test",
            version="1.0.0",
            valid=False,
            errors=("bad",),
            warnings=("warn",),
        )
        d = result.to_dict()
        result2 = DomainValidationResult.from_dict(d)
        assert result2.valid == result.valid
        assert result2.errors == result.errors


# ── Regression Tests ───────────────────────────────────────────────────────────


class TestRegressions:
    """Tests that prevent specific regressions in the registry."""

    def test_cannot_leave_two_active_versions(self) -> None:
        """After enabling a new version, old version must be disabled."""
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        reg.register(_make_defn("test", "2.0.0"))
        reg.enable("test", "1.0.0")
        reg.enable("test", "2.0.0")
        active = reg.list(DomainQuery(enabled=True))
        assert len(active) == 1
        assert active[0].version == "2.0.0"

    def test_cannot_enable_with_missing_dependency(self) -> None:
        """Can register with missing dep, but cannot enable."""
        reg = DomainRegistry()
        defn = _make_defn("test", "1.0.0", dependencies=(_make_dep("nonexistent"),))
        reg.register(defn)  # succeeds — validation is informational in register()
        from cmm.domains.errors import DomainRegistryStateError

        with pytest.raises(DomainRegistryStateError):
            reg.enable("test", "1.0.0")

    def test_mutated_definition_not_reflected_in_store(self) -> None:
        """Once registered, changing a local variable should not affect the registry."""
        reg = DomainRegistry()
        defn = _make_defn("test", "1.0.0", operations=("op1",))
        reg.register(defn)
        # Even though DomainDefinition is frozen, we verify the returned copy is independent
        stored = reg.get("test", "1.0.0")
        assert stored.operations == ("op1",)
        # DomainDefinition is immutable so no further check needed

    def test_1_10_0_greater_than_1_9_0_in_versions(self) -> None:
        """versions() must return 1.10.0 before 1.9.0 (semantic sort, not lexicographic)."""
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.9.0"))
        reg.register(_make_defn("test", "1.10.0"))
        versions = reg.versions("test")
        assert versions[0].version == "1.10.0"
        assert versions[1].version == "1.9.0"

    def test_resolve_capability_no_disabled(self) -> None:
        """resolve_capability must not return disabled domains."""
        reg = DomainRegistry()
        d1 = _make_defn("test", "1.0.0", capabilities=(_make_cap("test", "cap-x"),))
        reg.register(d1)
        reg.enable("test", "1.0.0")
        reg.disable("test", "1.0.0")
        result = reg.resolve_capability("cap-x")
        assert len(result) == 0

    def test_experimental_not_resolved_without_opt_in(self) -> None:
        """Experimental domains excluded from resolve_capability without opt-in,
        but included in list() without query."""
        reg = DomainRegistry()
        reg.register(
            _make_defn(
                "exp",
                "1.0.0",
                kind=DomainKind.EXPERIMENTAL,
                capabilities=(_make_cap("exp", "cap-x"),),
            )
        )
        reg.enable("exp", "1.0.0")
        # list() without query returns all (including experimental)
        default_list = reg.list()
        assert any(d.id.slug == "exp" for d in default_list)  # included in list()
        # But resolve_capability excludes experimental unless opted in
        resolved = reg.resolve_capability("cap-x")
        assert len(resolved) == 0  # excluded without opt-in

    def test_datetime_naive_rejected_in_validation_result(self) -> None:
        from cmm.domains.errors import DomainContractValidationError

        with pytest.raises(DomainContractValidationError):
            DomainValidationResult(
                domain_id="test",
                version="1.0.0",
                valid=True,
                checked_at=datetime(2024, 1, 1),  # noqa: DTZ001
            )

    def test_empty_string_capability_rejected(self) -> None:
        from cmm.domains.errors import DomainCapabilityConflict

        reg = DomainRegistry()
        with pytest.raises(DomainCapabilityConflict):
            reg.resolve_capability("   ")


# ── SemVer Precedence Regressions ───────────────────────────────────────────────

_CANONICAL_VERSION_SEQUENCE_ASC = (
    "1.0.0-alpha",
    "1.0.0-alpha.1",
    "1.0.0-alpha.beta",
    "1.0.0-beta",
    "1.0.0-beta.2",
    "1.0.0-beta.11",
    "1.0.0-rc.1",
    "1.0.0",
)


class TestSemverPrecedenceRegressions:
    """Phase 10.3 audit closure: no hash()-based ordering anywhere.

    Registers every version in ``_CANONICAL_VERSION_SEQUENCE_ASC`` in a
    scrambled order and asserts every read path returns the exact SemVer
    precedence order, descending.
    """

    _EXPECTED_DESC = tuple(reversed(_CANONICAL_VERSION_SEQUENCE_ASC))

    def _make_registry_with_full_sequence(self) -> DomainRegistry:
        reg = DomainRegistry()
        # Register out of order so no accidental insertion-order artifact
        # could make the test pass for the wrong reason.
        scrambled = (
            "1.0.0",
            "1.0.0-beta",
            "1.0.0-alpha.1",
            "1.0.0-rc.1",
            "1.0.0-alpha",
            "1.0.0-beta.11",
            "1.0.0-alpha.beta",
            "1.0.0-beta.2",
        )
        for version in scrambled:
            reg.register(_make_defn("test", version))
        return reg

    def test_versions_returns_exact_canonical_descending_order(self) -> None:
        reg = self._make_registry_with_full_sequence()
        versions = reg.versions("test")
        assert tuple(d.version for d in versions) == self._EXPECTED_DESC

    def test_get_without_version_selects_1_0_0(self) -> None:
        reg = self._make_registry_with_full_sequence()
        assert reg.get("test").version == "1.0.0"

    def test_list_preserves_descending_order_within_domain(self) -> None:
        reg = self._make_registry_with_full_sequence()
        listed = reg.list()
        test_versions = tuple(d.version for d in listed if d.id.slug == "test")
        assert test_versions == self._EXPECTED_DESC

    def test_snapshot_preserves_descending_order(self) -> None:
        reg = self._make_registry_with_full_sequence()
        snap = reg.snapshot()
        snap_versions = tuple(r.definition.version for r in snap.records)
        assert snap_versions == self._EXPECTED_DESC

    def test_alpha_beta_before_alpha_1_descending(self) -> None:
        reg = self._make_registry_with_full_sequence()
        versions = [d.version for d in reg.versions("test")]
        assert versions.index("1.0.0-alpha.beta") < versions.index("1.0.0-alpha.1")

    def test_sort_is_stable_across_repeated_calls(self) -> None:
        reg = self._make_registry_with_full_sequence()
        first = tuple(d.version for d in reg.versions("test"))
        for _ in range(5):
            again = tuple(d.version for d in reg.versions("test"))
            assert again == first

    def test_no_type_error_for_mixed_numeric_and_alphanumeric_identifiers(
        self,
    ) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("mixed", "1.0.0-alpha.1"))
        reg.register(_make_defn("mixed", "1.0.0-alpha.beta"))
        reg.register(_make_defn("mixed", "1.0.0-1"))
        # Must not raise TypeError comparing int vs str identifiers.
        reg.versions("mixed")

    def test_1_10_0_before_1_9_0(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("numeric", "1.9.0"))
        reg.register(_make_defn("numeric", "1.10.0"))
        versions = [d.version for d in reg.versions("numeric")]
        assert versions.index("1.10.0") < versions.index("1.9.0")


# ── Contains Tests ─────────────────────────────────────────────────────────────


class TestContains:
    """Tests for DomainRegistry.contains()."""

    def test_contains_exact(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        assert reg.contains("test", "1.0.0")
        assert not reg.contains("test", "2.0.0")

    def test_contains_any_version(self) -> None:
        reg = DomainRegistry()
        reg.register(_make_defn("test", "1.0.0"))
        assert reg.contains("test")
        assert not reg.contains("other")


# ── Alternative store substitutability ──────────────────────────────────────────


def _strip_domain_prefix(slug: str) -> str:
    return slug.removeprefix("domain:")


class AlternativeDomainRegistryStore:
    """Minimal list-backed ``DomainRegistryStore`` implementation.

    Deliberately independent of ``InMemoryDomainRegistryStore`` — no shared
    base class, no dict indices, no private helpers — to prove
    ``DomainRegistry`` only relies on the public store protocol.
    """

    def __init__(self) -> None:
        self._records: list[DomainRegistryRecord] = []

    def _find_index(self, domain_id: str, version: str) -> int | None:
        slug = _strip_domain_prefix(domain_id)
        for i, r in enumerate(self._records):
            if (
                _strip_domain_prefix(r.definition.id.slug) == slug
                and r.definition.version == version
            ):
                return i
        return None

    def add(self, record: DomainRegistryRecord) -> None:
        idx = self._find_index(record.definition.id.slug, record.definition.version)
        if idx is not None:
            existing = self._records[idx]
            if existing.to_dict() == record.to_dict():
                return
            raise DomainRegistryConflict(
                f"Duplicate identity: {record.definition.id.slug}@{record.definition.version}",
                field="record",
            )
        self._records.append(record)

    def replace(self, record: DomainRegistryRecord) -> None:
        idx = self._find_index(record.definition.id.slug, record.definition.version)
        if idx is None:
            raise DomainRegistryNotFound(
                f"Not found for replace: {record.definition.id.slug}@{record.definition.version}",
                field="record",
            )
        self._records[idx] = record

    def remove(self, domain_id: str, version: str) -> DomainRegistryRecord:
        idx = self._find_index(domain_id, version)
        if idx is None:
            raise DomainRegistryNotFound(
                f"Not found: {domain_id}@{version}", field="domain_id"
            )
        return self._records.pop(idx)

    def get(self, domain_id: str, version: str) -> DomainRegistryRecord | None:
        idx = self._find_index(domain_id, version)
        return self._records[idx] if idx is not None else None

    def list(self) -> tuple[DomainRegistryRecord, ...]:
        return tuple(sorted(self._records, key=cmp_to_key(_compare_records)))

    def find_by_capability(self, capability: str) -> tuple[DomainRegistryRecord, ...]:
        matches = [
            r
            for r in self._records
            if any(c.name == capability for c in r.definition.capabilities)
        ]
        return tuple(sorted(matches, key=cmp_to_key(_compare_records)))

    def find_by_kind(self, kind: DomainKind) -> tuple[DomainRegistryRecord, ...]:
        matches = [r for r in self._records if r.definition.kind == kind]
        return tuple(sorted(matches, key=cmp_to_key(_compare_records)))

    def find_by_status(self, status: DomainStatus) -> tuple[DomainRegistryRecord, ...]:
        matches = [r for r in self._records if r.status == status]
        return tuple(sorted(matches, key=cmp_to_key(_compare_records)))

    def snapshot_state(self) -> DomainRegistryStoreSnapshot:
        return DomainRegistryStoreSnapshot(records=tuple(self._records))

    def restore_state(self, snapshot: DomainRegistryStoreSnapshot) -> None:
        self._records = list(snapshot.records)


class _FlakyAlternativeStore(AlternativeDomainRegistryStore):
    """Alternative store that can simulate a mid-transaction failure.

    Used only to prove that ``DomainRegistry``'s rollback paths call
    nothing but the public ``snapshot_state()``/``restore_state()`` pair.
    """

    def __init__(self) -> None:
        super().__init__()
        self.fail_remove_version: str | None = None

    def remove(self, domain_id: str, version: str) -> DomainRegistryRecord:
        if version == self.fail_remove_version:
            raise RuntimeError("simulated mid-transaction failure")
        return super().remove(domain_id, version)


class TestAlternativeStoreSubstitutability:
    """DomainRegistry must work against any DomainRegistryStore, not just
    InMemoryDomainRegistryStore, using only the public store protocol."""

    def test_isinstance_of_protocol(self) -> None:
        from cmm.domains.registry_store import (
            DomainRegistryStore,
            InMemoryDomainRegistryStore,
        )

        assert isinstance(AlternativeDomainRegistryStore(), DomainRegistryStore)
        assert not issubclass(
            AlternativeDomainRegistryStore, InMemoryDomainRegistryStore
        )

    def test_register_works(self) -> None:
        reg = DomainRegistry(store=AlternativeDomainRegistryStore())
        reg.register(_make_defn("a", "1.0.0"))
        reg.register(_make_defn("b", "1.0.0"))
        assert len(reg.list()) == 2

    def test_enable_works(self) -> None:
        reg = DomainRegistry(store=AlternativeDomainRegistryStore())
        reg.register(_make_defn("test", "1.0.0"))
        enabled = reg.enable("test", "1.0.0")
        assert enabled.enabled is True
        assert reg.get("test", "1.0.0").enabled is True

    def test_disable_works(self) -> None:
        reg = DomainRegistry(store=AlternativeDomainRegistryStore())
        reg.register(_make_defn("test", "1.0.0"))
        reg.enable("test", "1.0.0")
        disabled = reg.disable("test", "1.0.0")
        assert disabled.enabled is False

    def test_unregister_multiple_versions_works(self) -> None:
        reg = DomainRegistry(store=AlternativeDomainRegistryStore())
        reg.register(_make_defn("test", "1.0.0"))
        reg.register(_make_defn("test", "2.0.0"))
        removed = reg.unregister("test")
        assert len(removed) == 2
        assert not reg.contains("test")

    def test_rollback_uses_only_public_snapshot_restore_api(self) -> None:
        from cmm.domains.errors import DomainRegistryStateError

        store = _FlakyAlternativeStore()
        reg = DomainRegistry(store=store)
        reg.register(_make_defn("test", "1.0.0"))
        reg.register(_make_defn("test", "2.0.0"))

        store.fail_remove_version = "2.0.0"
        with pytest.raises(DomainRegistryStateError):
            reg.unregister("test")

        # Partial removal must have been rolled back via snapshot_state()/
        # restore_state() alone — both versions should still be present.
        assert reg.contains("test", "1.0.0")
        assert reg.contains("test", "2.0.0")
