"""Phase 9.23 – Agent Registry & Factory Tests.

Covers:
* Block A: enums, errors, AgentVersion, contracts, validation.
* Block B: store, registry, lifecycle, snapshots.
* Block C: factory contracts, factory registry, scopes, instance cache.
* Block D: compatibility, resolver, scorer, service, health, stats,
  snapshots and security audit.

Tests are organised by block with explicit section headers.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from cmm.agent_runtime.agent_registry_contracts import (
    AgentCapability,
    AgentDescriptor,
    AgentRequirement,
    AgentVersion,
)
from cmm.agent_runtime.agent_registry_enums import (
    AgentAvailability,
    AgentCapabilityKind,
    AgentCompatibilityStatus,
    AgentFactoryScope,
    AgentKind,
    AgentLifecycle,
    AgentRegistrationStatus,
    AgentResolutionStrategy,
    AgentVersionStatus,
)
from cmm.agent_runtime.agent_registry_errors import (
    AgentDependencyUnavailableError,
    AgentFactoryCompatibilityError,
    AgentFactoryCreationError,
    AgentFactoryError,
    AgentFactoryNotFoundError,
    AgentRegistryAliasConflictError,
    AgentRegistryConflictError,
    AgentRegistryDisabledError,
    AgentRegistryError,
    AgentRegistryNotFoundError,
    AgentRegistryValidationError,
    AgentRegistryVersionError,
    AgentResolutionAmbiguousError,
    AgentResolutionError,
    AgentResolutionNotFoundError,
)

# ═════════════════════════════════════════════════════════════════════════
# Test fixtures – small, deterministic, re-used.
# ═════════════════════════════════════════════════════════════════════════


def _ts(year: int = 2026, month: int = 1, day: int = 1) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


def _capability(
    name: str = "summarize",
    *,
    kind: AgentCapabilityKind = AgentCapabilityKind.OPERATION,
    operations: tuple[str, ...] = ("op.summarize",),
    required_permissions: tuple[str, ...] = (),
    metadata: MappingProxyType | None = None,
) -> AgentCapability:
    return AgentCapability(
        name=name,
        kind=kind,
        version="1.0.0",
        description=f"capability {name}",
        operations=operations,
        input_types=("text",),
        output_types=("summary",),
        required_permissions=required_permissions,
        metadata=metadata or MappingProxyType({}),
    )


def _descriptor(
    agent_id: str = "agent.alpha",
    *,
    version: AgentVersion | None = None,
    name: str = "Alpha Agent",
    kind: AgentKind = AgentKind.GENERAL,
    lifecycle: AgentLifecycle = AgentLifecycle.ACTIVE,
    factory_id: str = "factory.alpha",
    description: str | None = None,
    capabilities: tuple[AgentCapability, ...] = (),
    aliases: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
    required_permissions: tuple[str, ...] = (),
    required_components: tuple[str, ...] = (),
    supported_operations: tuple[str, ...] = (),
    priority: int = 0,
    metadata: MappingProxyType | None = None,
    created_at: datetime | None = None,
) -> AgentDescriptor:
    return AgentDescriptor(
        agent_id=agent_id,
        name=name,
        version=version or AgentVersion(1, 0, 0),
        kind=kind,
        lifecycle=lifecycle,
        description=description
        if description is not None
        else f"descriptor for {agent_id}",
        capabilities=capabilities,
        factory_id=factory_id,
        priority=priority,
        aliases=aliases,
        tags=tags,
        required_permissions=required_permissions,
        required_components=required_components,
        supported_operations=supported_operations,
        metadata=metadata or MappingProxyType({}),
        created_at=created_at or _ts(),
    )


# ═════════════════════════════════════════════════════════════════════════
# Block A – Enums
# ═════════════════════════════════════════════════════════════════════════


class TestEnums:
    """All enums exist and carry the documented string values."""

    @pytest.mark.parametrize(
        "name",
        [
            "GENERAL",
            "DOMAIN",
            "WORKFLOW",
            "TOOL",
            "COORDINATOR",
            "REVIEWER",
            "PLANNER",
            "EXECUTOR",
            "OBSERVER",
        ],
    )
    def test_agent_kind_values(self, name: str) -> None:
        assert hasattr(AgentKind, name)
        assert isinstance(getattr(AgentKind, name).value, str)
        assert getattr(AgentKind, name).value

    @pytest.mark.parametrize(
        "name",
        [
            "EXPERIMENTAL",
            "ACTIVE",
            "DEPRECATED",
            "RETIRED",
            "DISABLED",
        ],
    )
    def test_agent_lifecycle_values(self, name: str) -> None:
        assert hasattr(AgentLifecycle, name)

    @pytest.mark.parametrize(
        "name",
        [
            "AVAILABLE",
            "UNAVAILABLE",
            "DEGRADED",
            "UNKNOWN",
        ],
    )
    def test_agent_availability_values(self, name: str) -> None:
        assert hasattr(AgentAvailability, name)

    @pytest.mark.parametrize(
        "name",
        [
            "INPUT",
            "OUTPUT",
            "OPERATION",
            "KNOWLEDGE",
            "TOOL",
            "PERMISSION",
            "COGNITIVE",
            "COMPOSITE",
        ],
    )
    def test_agent_capability_kind_values(self, name: str) -> None:
        assert hasattr(AgentCapabilityKind, name)

    @pytest.mark.parametrize(
        "name",
        [
            "TRANSIENT",
            "REQUEST",
            "RUN",
            "SINGLETON",
        ],
    )
    def test_agent_factory_scope_values(self, name: str) -> None:
        assert hasattr(AgentFactoryScope, name)

    @pytest.mark.parametrize(
        "name",
        [
            "EXACT",
            "BEST_MATCH",
            "HIGHEST_PRIORITY",
            "HIGHEST_VERSION",
            "CAPABILITY_MATCH",
        ],
    )
    def test_agent_resolution_strategy_values(self, name: str) -> None:
        assert hasattr(AgentResolutionStrategy, name)

    def test_compatibility_status_is_exhaustive(self) -> None:
        # at least the documented incompatible reasons
        for name in (
            "INCOMPATIBLE_LIFECYCLE",
            "INCOMPATIBLE_VERSION",
            "INCOMPATIBLE_CAPABILITY",
            "INCOMPATIBLE_OPERATION",
            "INCOMPATIBLE_PERMISSION",
            "INCOMPATIBLE_COMPONENT",
            "INCOMPATIBLE_RUNTIME",
            "EXCLUDED",
            "FACTORY_UNAVAILABLE",
        ):
            assert name in {m.name for m in AgentCompatibilityStatus}

    def test_registration_and_version_status_enums(self) -> None:
        for name in (
            "REGISTERED",
            "UPDATED",
            "REPLACED",
            "REJECTED_CONFLICT",
            "REJECTED_INVALID",
            "NOT_FOUND",
            "REMOVED",
        ):
            assert hasattr(AgentRegistrationStatus, name)
        for name in (
            "ACTIVE",
            "EXPERIMENTAL",
            "DEPRECATED",
            "RETIRED",
            "DISABLED",
        ):
            assert hasattr(AgentVersionStatus, name)


# ═════════════════════════════════════════════════════════════════════════
# Block A – Errors
# ═════════════════════════════════════════════════════════════════════════


class TestErrors:
    """Error hierarchy carries stable codes and never leaks internals."""

    def test_base_error_has_default_code(self) -> None:
        err = AgentRegistryError("boom")
        assert err.error_code == "AGENT_REGISTRY_ERROR"
        assert err.message == "boom"
        assert err.details == {}

    def test_specific_error_codes(self) -> None:
        for cls, expected in (
            (AgentRegistryValidationError, "AGENT_REGISTRY_VALIDATION_ERROR"),
            (AgentRegistryConflictError, "AGENT_REGISTRY_CONFLICT"),
            (AgentRegistryNotFoundError, "AGENT_REGISTRY_NOT_FOUND"),
            (AgentRegistryDisabledError, "AGENT_REGISTRY_DISABLED"),
            (AgentRegistryVersionError, "AGENT_REGISTRY_VERSION_ERROR"),
            (AgentRegistryAliasConflictError, "AGENT_REGISTRY_ALIAS_CONFLICT"),
            (AgentFactoryError, "AGENT_FACTORY_ERROR"),
            (AgentFactoryNotFoundError, "AGENT_FACTORY_NOT_FOUND"),
            (AgentFactoryCreationError, "AGENT_FACTORY_CREATION_ERROR"),
            (
                AgentFactoryCompatibilityError,
                "AGENT_FACTORY_COMPATIBILITY_ERROR",
            ),
            (AgentResolutionError, "AGENT_RESOLUTION_ERROR"),
            (AgentResolutionNotFoundError, "AGENT_RESOLUTION_NOT_FOUND"),
            (AgentResolutionAmbiguousError, "AGENT_RESOLUTION_AMBIGUOUS"),
            (
                AgentDependencyUnavailableError,
                "AGENT_DEPENDENCY_UNAVAILABLE",
            ),
        ):
            err = cls("x", {"k": "v"})
            assert err.error_code == expected
            assert err.details == {"k": "v"}

    def test_sanitize_message_scrubs_sensitive(self) -> None:
        for sensitive in (
            "chain_of_thought step",
            "private_prompt thing",
            "internal_reasoning here",
            "api_key=123",
            "password=secret",
            "private_key=abc",
            "bearer xyz",
            "token=abc",
            "Traceback (most recent call last):",
        ):
            err = AgentRegistryError(sensitive)
            assert "internal" in err.message.lower() or err.message == (
                "An internal error occurred"
            )

    def test_safe_message_passes_through(self) -> None:
        err = AgentRegistryError("safe message")
        assert err.message == "safe message"

    def test_details_sanitized_recursively(self) -> None:
        err = AgentRegistryError(
            "x", {"inner": {"api_key": "abc"}, "list": ["password=1"]}
        )
        # ``api_key`` key itself is preserved as the key but its value is
        # sanitized to a generic string.
        assert err.details["inner"]["api_key"] == "An internal error occurred"
        assert err.details["list"] == ["An internal error occurred"]

    def test_to_dict_is_json_safe(self) -> None:
        err = AgentRegistryValidationError("bad", {"a": 1})
        d = err.to_dict()
        assert d == {
            "error_code": "AGENT_REGISTRY_VALIDATION_ERROR",
            "message": "bad",
            "details": {"a": 1},
        }

    def test_str_repr_safe(self) -> None:
        err = AgentRegistryError("safe")
        assert "safe" in str(err)
        # stack traces are not added.
        assert "Traceback" not in str(err)


# ═════════════════════════════════════════════════════════════════════════
# Block A – AgentVersion
# ═════════════════════════════════════════════════════════════════════════


class TestAgentVersion:
    """Version parsing, ordering, immutability and serialization."""

    def test_parse_simple_version(self) -> None:
        v = AgentVersion.parse("1.2.3")
        assert v == AgentVersion(1, 2, 3)
        assert v.prerelease is None

    def test_parse_prerelease_alpha(self) -> None:
        v = AgentVersion.parse("1.0.0-alpha")
        assert v.major == 1
        assert v.minor == 0
        assert v.patch == 0
        assert v.prerelease == "alpha"

    def test_parse_prerelease_beta_2(self) -> None:
        v = AgentVersion.parse("1.0.0-beta.2")
        assert v.prerelease == "beta.2"

    def test_parse_invalid_empty(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentVersion.parse("")

    def test_parse_invalid_whitespace(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentVersion.parse("   ")

    def test_parse_invalid_space_inside(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentVersion.parse("1 0 0")

    def test_parse_invalid_missing_part(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentVersion.parse("1.0")

    def test_parse_invalid_leading_zero(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentVersion.parse("01.0.0")

    def test_parse_invalid_non_string(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentVersion.parse(123)  # type: ignore[arg-type]

    def test_parse_invalid_negative_marker(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentVersion.parse("-1.0.0")

    def test_negative_components_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentVersion(major=-1, minor=0, patch=0)

    def test_invalid_prerelease_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentVersion(1, 0, 0, prerelease="   ")

    def test_invalid_prerelease_spaces_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentVersion(1, 0, 0, prerelease="alpha beta")

    def test_invalid_prerelease_special_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentVersion(1, 0, 0, prerelease="$bad")

    def test_non_int_component_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentVersion("1", 0, 0)  # type: ignore[arg-type]

    def test_bool_component_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentVersion(True, 0, 0)  # type: ignore[arg-type]

    def test_equality(self) -> None:
        assert AgentVersion(1, 0, 0) == AgentVersion(1, 0, 0)
        assert AgentVersion(1, 0, 0) != AgentVersion(1, 0, 1)

    def test_ordering(self) -> None:
        assert AgentVersion(1, 0, 0) < AgentVersion(1, 0, 1)
        assert AgentVersion(1, 0, 0) < AgentVersion(1, 1, 0)
        assert AgentVersion(1, 0, 0) < AgentVersion(2, 0, 0)
        assert AgentVersion(1, 0, 0) > AgentVersion(0, 9, 9)
        # prerelease < release
        assert AgentVersion(1, 0, 0, "alpha") < AgentVersion(1, 0, 0)

    def test_canonical_string(self) -> None:
        assert AgentVersion(1, 0, 0).canonical() == "1.0.0"
        assert AgentVersion(1, 0, 0, "alpha").canonical() == "1.0.0-alpha"

    def test_is_prerelease(self) -> None:
        assert AgentVersion(1, 0, 0).is_prerelease() is False
        assert AgentVersion(1, 0, 0, "alpha").is_prerelease() is True

    def test_immutable(self) -> None:
        v = AgentVersion(1, 0, 0)
        with pytest.raises(FrozenInstanceError):
            v.major = 2  # type: ignore[misc]

    def test_to_dict(self) -> None:
        d = AgentVersion(1, 2, 3, "alpha").to_dict()
        assert d == {
            "major": 1,
            "minor": 2,
            "patch": 3,
            "prerelease": "alpha",
        }


# ═════════════════════════════════════════════════════════════════════════
# Block A – AgentCapability
# ═════════════════════════════════════════════════════════════════════════


class TestAgentCapability:
    """Capability contract, validation, immutability, serialization."""

    def test_valid_capability(self) -> None:
        cap = _capability()
        assert cap.name == "summarize"
        assert cap.kind == AgentCapabilityKind.OPERATION
        assert "op.summarize" in cap.operations

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentCapability(name="", kind=AgentCapabilityKind.OPERATION)

    def test_whitespace_name_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentCapability(name="   ", kind=AgentCapabilityKind.OPERATION)

    def test_invalid_name_format(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentCapability(name="1bad", kind=AgentCapabilityKind.OPERATION)

    def test_invalid_kind_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentCapability(name="ok", kind="not_enum")  # type: ignore[arg-type]

    def test_duplicate_operations_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentCapability(
                name="cap",
                kind=AgentCapabilityKind.OPERATION,
                operations=("op.a", "op.a"),
            )

    def test_operations_sorted_deterministically(self) -> None:
        cap = AgentCapability(
            name="cap",
            kind=AgentCapabilityKind.OPERATION,
            operations=("z", "a", "m"),
        )
        assert cap.operations == ("a", "m", "z")

    def test_duplicate_permissions_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentCapability(
                name="cap",
                kind=AgentCapabilityKind.OPERATION,
                required_permissions=("p", "p"),
            )

    def test_metadata_defensively_copied(self) -> None:
        original = {"a": 1}
        cap = AgentCapability(
            name="cap",
            kind=AgentCapabilityKind.OPERATION,
            metadata=original,
        )
        original["a"] = 99
        assert cap.metadata["a"] == 1

    def test_metadata_forbidden_keys_rejected(self) -> None:
        for key in (
            "chain_of_thought",
            "private_prompt",
            "api_key",
            "password",
            "private_key",
        ):
            with pytest.raises(AgentRegistryValidationError):
                AgentCapability(
                    name="cap",
                    kind=AgentCapabilityKind.OPERATION,
                    metadata={key: "x"},
                )

    def test_metadata_non_serializable_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentCapability(
                name="cap",
                kind=AgentCapabilityKind.OPERATION,
                metadata={"bad": object()},
            )

    def test_immutable(self) -> None:
        cap = _capability()
        with pytest.raises(FrozenInstanceError):
            cap.name = "x"  # type: ignore[misc]

    def test_to_dict_round_trip(self) -> None:
        cap = _capability()
        d = cap.to_dict()
        assert d["name"] == "summarize"
        assert d["kind"] == "operation"
        assert d["operations"] == ["op.summarize"]
        assert d["metadata"] == {}


# ═════════════════════════════════════════════════════════════════════════
# Block A – AgentDescriptor
# ═════════════════════════════════════════════════════════════════════════


class TestAgentDescriptor:
    """Descriptor contract, validation, immutability, serialization."""

    def test_valid_descriptor(self) -> None:
        d = _descriptor()
        assert d.agent_id == "agent.alpha"
        assert d.lifecycle == AgentLifecycle.ACTIVE
        assert d.is_resolvable_default() is True

    def test_immutable(self) -> None:
        d = _descriptor()
        with pytest.raises(FrozenInstanceError):
            d.name = "x"  # type: ignore[misc]

    def test_aware_timestamp_required(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            _descriptor(created_at=datetime(2026, 1, 1))  # noqa: DTZ001

    def test_naive_timestamp_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            _descriptor(created_at=datetime.now())  # noqa: DTZ005

    def test_empty_agent_id_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            _descriptor(agent_id="")

    def test_invalid_agent_id_format(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            _descriptor(agent_id="1bad")

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            _descriptor(name="")

    def test_empty_description_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            _descriptor(
                name="x",
                description="",
            )

    def test_invalid_factory_id_format(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            _descriptor(factory_id="1bad")

    def test_empty_factory_id_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            _descriptor(factory_id="")

    def test_duplicate_capabilities_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            _descriptor(capabilities=(_capability("a"), _capability("a")))

    def test_duplicate_aliases_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            _descriptor(aliases=("a", "a"))

    def test_duplicate_tags_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            _descriptor(tags=("t", "t"))

    def test_duplicate_operations_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            _descriptor(supported_operations=("op.a", "op.a"))

    def test_duplicate_required_permissions_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            _descriptor(required_permissions=("p", "p"))

    def test_duplicate_required_components_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            _descriptor(required_components=("c", "c"))

    def test_alias_overlap_with_id_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            _descriptor(aliases=("agent.alpha",))

    def test_unsafe_metadata_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            _descriptor(metadata=MappingProxyType({"api_key": "x"}))

    def test_non_serializable_metadata_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            _descriptor(metadata=MappingProxyType({"bad": object()}))

    def test_lifecycle_retired_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            _descriptor(lifecycle=AgentLifecycle.RETIRED)

    def test_lifecycle_disabled_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            _descriptor(lifecycle=AgentLifecycle.DISABLED)

    def test_invalid_kind_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            _descriptor(kind="not_enum")  # type: ignore[arg-type]

    def test_priority_must_be_int(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            _descriptor(priority="x")  # type: ignore[arg-type]

    def test_version_must_be_agent_version(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            _descriptor(version="1.0.0")  # type: ignore[arg-type]

    def test_capability_invalid_type_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            _descriptor(capabilities=("not a capability",))  # type: ignore[arg-type]

    def test_serialization(self) -> None:
        d = _descriptor(
            capabilities=(_capability(),),
            aliases=("alias.a",),
            tags=("t1",),
        )
        s = d.to_dict()
        assert s["agent_id"] == "agent.alpha"
        assert s["version"] == "1.0.0"
        assert s["lifecycle"] == "active"
        assert s["aliases"] == ["alias.a"]
        assert s["capabilities"][0]["name"] == "summarize"
        assert s["created_at"].endswith("+00:00")

    def test_with_lifecycle_returns_new_instance(self) -> None:
        d = _descriptor()
        d2 = d.with_lifecycle(AgentLifecycle.DEPRECATED)
        assert d.lifecycle == AgentLifecycle.ACTIVE
        assert d2.lifecycle == AgentLifecycle.DEPRECATED
        assert d2.agent_id == d.agent_id

    def test_with_lifecycle_rejects_retired(self) -> None:
        d = _descriptor()
        with pytest.raises(AgentRegistryValidationError):
            d.with_lifecycle(AgentLifecycle.RETIRED)


# ═════════════════════════════════════════════════════════════════════════
# Block A – AgentRequirement
# ═════════════════════════════════════════════════════════════════════════


class TestAgentRequirement:
    """Requirement contract, immutability, serialization."""

    def test_valid_with_agent_id(self) -> None:
        r = AgentRequirement(agent_id="agent.alpha")
        assert r.has_any_filter() is True

    def test_valid_with_capabilities(self) -> None:
        r = AgentRequirement(required_capabilities=("summarize",))
        assert r.has_any_filter() is True

    def test_empty_requirement_rejected_by_validator(self) -> None:
        from cmm.agent_runtime.agent_registry_validation import (
            AgentRequirementValidator,
        )

        r = AgentRequirement()
        assert r.has_any_filter() is False
        with pytest.raises(AgentRegistryValidationError):
            AgentRequirementValidator.validate(r)

    def test_contradictory_agent_id_and_exclusion(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentRequirement(
                agent_id="agent.alpha",
                excluded_agents=("agent.alpha",),
            )

    def test_preferred_and_excluded_overlap(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentRequirement(
                preferred_agents=("a", "b"),
                excluded_agents=("b",),
            )

    def test_immutable(self) -> None:
        r = AgentRequirement(agent_id="a")
        with pytest.raises(FrozenInstanceError):
            r.agent_id = "b"  # type: ignore[misc]

    def test_allow_experimental_default_false(self) -> None:
        r = AgentRequirement(agent_id="a")
        assert r.allow_experimental is False
        assert r.allow_deprecated is False

    def test_allow_experimental_set(self) -> None:
        r = AgentRequirement(agent_id="a", allow_experimental=True)
        assert r.allow_experimental is True

    def test_invalid_version_string_caught_by_validator(self) -> None:
        from cmm.agent_runtime.agent_registry_validation import (
            AgentRequirementValidator,
        )

        r = AgentRequirement(agent_id="a", version="not-a-version")
        with pytest.raises(AgentRegistryValidationError):
            AgentRequirementValidator.validate(r)

    def test_duplicate_required_capabilities_rejected(self) -> None:
        with pytest.raises(AgentRegistryValidationError):
            AgentRequirement(required_capabilities=("a", "a"))

    def test_serialization(self) -> None:
        r = AgentRequirement(
            agent_id="agent.alpha",
            kind=AgentKind.PLANNER,
            required_capabilities=("c1",),
            allow_deprecated=True,
        )
        s = r.to_dict()
        assert s["agent_id"] == "agent.alpha"
        assert s["kind"] == "planner"
        assert s["required_capabilities"] == ["c1"]
        assert s["allow_deprecated"] is True


# ═════════════════════════════════════════════════════════════════════════
# Block A – Validation helpers
# ═════════════════════════════════════════════════════════════════════════


class TestValidation:
    """Validator helpers from ``agent_registry_validation``."""

    def test_version_validator_passes_through_instance(self) -> None:
        from cmm.agent_runtime.agent_registry_validation import (
            AgentVersionValidator,
        )

        v = AgentVersion(1, 0, 0)
        assert AgentVersionValidator.validate(v) is v

    def test_version_validator_parses_string(self) -> None:
        from cmm.agent_runtime.agent_registry_validation import (
            AgentVersionValidator,
        )

        v = AgentVersionValidator.validate("2.1.3")
        assert v == AgentVersion(2, 1, 3)

    def test_version_validator_rejects_non_string(self) -> None:
        from cmm.agent_runtime.agent_registry_validation import (
            AgentVersionValidator,
        )

        with pytest.raises(AgentRegistryValidationError):
            AgentVersionValidator.validate(123)

    def test_capability_validator_accepts_valid(self) -> None:
        from cmm.agent_runtime.agent_registry_validation import (
            AgentCapabilityValidator,
        )

        cap = _capability()
        assert AgentCapabilityValidator.validate(cap) is cap

    def test_capability_validator_rejects_other(self) -> None:
        from cmm.agent_runtime.agent_registry_validation import (
            AgentCapabilityValidator,
        )

        with pytest.raises(AgentRegistryValidationError):
            AgentCapabilityValidator.validate("not a capability")

    def test_descriptor_validator_accepts_valid(self) -> None:
        from cmm.agent_runtime.agent_registry_validation import (
            AgentDescriptorValidator,
        )

        d = _descriptor()
        assert AgentDescriptorValidator.validate(d) is d

    def test_descriptor_validator_rejects_other(self) -> None:
        from cmm.agent_runtime.agent_registry_validation import (
            AgentDescriptorValidator,
        )

        with pytest.raises(AgentRegistryValidationError):
            AgentDescriptorValidator.validate("not a descriptor")

    def test_factory_validator_rejects_none(self) -> None:
        from cmm.agent_runtime.agent_registry_validation import (
            AgentFactoryValidator,
        )

        with pytest.raises(AgentFactoryError):
            AgentFactoryValidator.validate_factory(None)

    def test_factory_validator_rejects_missing_factory_id(self) -> None:
        from cmm.agent_runtime.agent_registry_validation import (
            AgentFactoryValidator,
        )

        class BadFactory:
            scope = AgentFactoryScope.TRANSIENT
            thread_safe = True

            def supports(self, descriptor):
                return True

            def create(self, descriptor, context):
                return None

        with pytest.raises(AgentFactoryCompatibilityError):
            AgentFactoryValidator.validate_factory(BadFactory())

    def test_factory_validator_singleton_requires_thread_safe(self) -> None:
        from cmm.agent_runtime.agent_registry_validation import (
            AgentFactoryValidator,
        )

        class UnsafeSingleton:
            factory_id = "f1"
            scope = AgentFactoryScope.SINGLETON
            thread_safe = False

            def supports(self, descriptor):
                return True

            def create(self, descriptor, context):
                return None

        with pytest.raises(AgentFactoryCompatibilityError):
            AgentFactoryValidator.validate_factory(UnsafeSingleton())

    def test_factory_validator_requires_supports(self) -> None:
        from cmm.agent_runtime.agent_registry_validation import (
            AgentFactoryValidator,
        )

        class NoSupports:
            factory_id = "f1"
            scope = AgentFactoryScope.TRANSIENT
            thread_safe = True

            def create(self, descriptor, context):
                return None

        with pytest.raises(AgentFactoryCompatibilityError):
            AgentFactoryValidator.validate_factory(NoSupports())

    def test_factory_validator_requires_create(self) -> None:
        from cmm.agent_runtime.agent_registry_validation import (
            AgentFactoryValidator,
        )

        class NoCreate:
            factory_id = "f1"
            scope = AgentFactoryScope.TRANSIENT
            thread_safe = True

            def supports(self, descriptor):
                return True

        with pytest.raises(AgentFactoryCompatibilityError):
            AgentFactoryValidator.validate_factory(NoCreate())

    def test_factory_validator_supports_must_return_true(self) -> None:
        from cmm.agent_runtime.agent_registry_validation import (
            AgentFactoryValidator,
        )

        class BadSupports:
            factory_id = "f1"
            scope = AgentFactoryScope.TRANSIENT
            thread_safe = True

            def supports(self, descriptor):
                return False

            def create(self, descriptor, context):
                return None

        d = _descriptor()
        with pytest.raises(AgentFactoryCompatibilityError):
            AgentFactoryValidator.validate_descriptor_compatibility(BadSupports(), d)

    def test_factory_validator_supports_exception_mapped(self) -> None:
        from cmm.agent_runtime.agent_registry_validation import (
            AgentFactoryValidator,
        )

        class ExplodingSupports:
            factory_id = "f1"
            scope = AgentFactoryScope.TRANSIENT
            thread_safe = True

            def supports(self, descriptor):
                raise RuntimeError("private_prompt error")

            def create(self, descriptor, context):
                return None

        d = _descriptor()
        with pytest.raises(AgentFactoryCompatibilityError):
            AgentFactoryValidator.validate_descriptor_compatibility(
                ExplodingSupports(), d
            )


# ═════════════════════════════════════════════════════════════════════════
# Block B – Store
# ═════════════════════════════════════════════════════════════════════════


class TestStore:
    """``InMemoryAgentRegistryStore`` semantics and protocol conformance."""

    def test_protocol_has_required_methods(self) -> None:
        from cmm.agent_runtime.agent_registry_store import (
            AgentRegistryStore,
            InMemoryAgentRegistryStore,
        )

        # ``Protocol`` itself is structural; verify the documented
        # method names exist on the concrete implementation.
        store = InMemoryAgentRegistryStore()
        for name in (
            "add",
            "remove",
            "get",
            "list",
            "find_by_alias",
            "find_by_capability",
        ):
            assert callable(getattr(store, name))
        # and the protocol symbol exists as a class.
        assert isinstance(AgentRegistryStore, type)

    def test_add_then_get(self) -> None:
        from cmm.agent_runtime.agent_registry_store import (
            InMemoryAgentRegistryStore,
        )

        s = InMemoryAgentRegistryStore()
        d = _descriptor()
        s.add(d)
        assert s.get(d.agent_id, d.version) == d

    def test_get_returns_none_when_missing(self) -> None:
        from cmm.agent_runtime.agent_registry_store import (
            InMemoryAgentRegistryStore,
        )

        s = InMemoryAgentRegistryStore()
        assert s.get("agent.missing", AgentVersion(1, 0, 0)) is None

    def test_get_with_version_returns_exact(self) -> None:
        from cmm.agent_runtime.agent_registry_store import (
            InMemoryAgentRegistryStore,
        )

        s = InMemoryAgentRegistryStore()
        d_old = _descriptor()
        d_new = _descriptor(version=AgentVersion(2, 0, 0))
        s.add(d_old)
        s.add(d_new)
        assert s.get(d_old.agent_id, d_old.version) == d_old
        assert s.get(d_new.agent_id, d_new.version) == d_new

    def test_remove_returns_descriptor(self) -> None:
        from cmm.agent_runtime.agent_registry_store import (
            InMemoryAgentRegistryStore,
        )

        s = InMemoryAgentRegistryStore()
        d = _descriptor()
        s.add(d)
        removed = s.remove(d.agent_id, d.version)
        assert removed == d
        assert s.get(d.agent_id, d.version) is None

    def test_list_returns_tuple(self) -> None:
        from cmm.agent_runtime.agent_registry_store import (
            InMemoryAgentRegistryStore,
        )

        s = InMemoryAgentRegistryStore()
        s.add(_descriptor())
        s.add(_descriptor(agent_id="agent.beta", factory_id="factory.beta"))
        result = s.list()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_find_by_alias(self) -> None:
        from cmm.agent_runtime.agent_registry_store import (
            InMemoryAgentRegistryStore,
        )

        s = InMemoryAgentRegistryStore()
        d = _descriptor(aliases=("alias.a",))
        s.add(d)
        found = s.find_by_alias("alias.a")
        assert d in found

    def test_find_by_alias_missing(self) -> None:
        from cmm.agent_runtime.agent_registry_store import (
            InMemoryAgentRegistryStore,
        )

        s = InMemoryAgentRegistryStore()
        assert s.find_by_alias("nope") == ()

    def test_find_by_capability(self) -> None:
        from cmm.agent_runtime.agent_registry_store import (
            InMemoryAgentRegistryStore,
        )

        s = InMemoryAgentRegistryStore()
        cap = _capability("summarize")
        d_with = _descriptor(capabilities=(cap,))
        d_without = _descriptor(agent_id="agent.beta", factory_id="factory.beta")
        s.add(d_with)
        s.add(d_without)
        found = s.find_by_capability("summarize")
        assert d_with in found
        assert d_without not in found

    def test_find_by_capability_missing(self) -> None:
        from cmm.agent_runtime.agent_registry_store import (
            InMemoryAgentRegistryStore,
        )

        s = InMemoryAgentRegistryStore()
        assert s.find_by_capability("unknown") == ()

    def test_contains(self) -> None:
        from cmm.agent_runtime.agent_registry_store import (
            InMemoryAgentRegistryStore,
        )

        s = InMemoryAgentRegistryStore()
        d = _descriptor()
        s.add(d)
        assert s.contains(d.agent_id, d.version) is True
        assert s.contains("missing", AgentVersion(0, 0, 1)) is False

    def test_clear(self) -> None:
        from cmm.agent_runtime.agent_registry_store import (
            InMemoryAgentRegistryStore,
        )

        s = InMemoryAgentRegistryStore()
        s.add(_descriptor())
        s.clear()
        assert s.list() == ()

    def test_raw_snapshot_is_mappingproxy(self) -> None:
        from cmm.agent_runtime.agent_registry_store import (
            InMemoryAgentRegistryStore,
        )

        s = InMemoryAgentRegistryStore()
        s.add(_descriptor())
        snap = s.raw_snapshot()
        assert isinstance(snap, MappingProxyType)
        assert len(snap) == 1

    def test_duplicate_add_raises_conflict(self) -> None:
        from cmm.agent_runtime.agent_registry_store import (
            InMemoryAgentRegistryStore,
        )

        s = InMemoryAgentRegistryStore()
        d = _descriptor()
        s.add(d)
        # re-adding identical identity raises ConflictError.
        with pytest.raises(AgentRegistryConflictError):
            s.add(d)
        assert len(s.list()) == 1

    def test_remove_unknown_raises(self) -> None:
        from cmm.agent_runtime.agent_registry_store import (
            InMemoryAgentRegistryStore,
        )

        s = InMemoryAgentRegistryStore()
        with pytest.raises(AgentRegistryNotFoundError):
            s.remove("nope", AgentVersion(1, 0, 0))
