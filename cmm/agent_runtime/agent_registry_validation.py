"""Phase 9.23 – Agent Registry & Factory Validation.

Validators that the registry and factory call *before* accepting any
data. They never mutate input; they either return silently or raise a
structured ``AgentRegistryValidationError``.

The validators here are deliberately separate from the ``__post_init__``
checks in the contracts: ``__post_init__`` enforces structural shape,
while these validators enforce *cross-field* and *policy* rules.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.agent_registry_contracts import (
    AgentCapability,
    AgentDescriptor,
    AgentRequirement,
    AgentVersion,
)
from cmm.agent_runtime.agent_registry_enums import (
    AgentCapabilityKind,
    AgentFactoryScope,
    AgentLifecycle,
)
from cmm.agent_runtime.agent_registry_errors import (
    AgentFactoryCompatibilityError,
    AgentFactoryError,
    AgentRegistryValidationError,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _ensure_dict(meta: Any, field_name: str) -> dict[str, Any]:
    if meta is None:
        return {}
    if not isinstance(meta, Mapping):
        raise AgentRegistryValidationError(
            f"{field_name} must be a Mapping", {"field": field_name}
        )
    return dict(meta)


# ── Version validator ───────────────────────────────────────────────────────


class AgentVersionValidator:
    """Validates an ``AgentVersion`` instance or parses a string."""

    @staticmethod
    def validate(value: Any) -> AgentVersion:
        if isinstance(value, AgentVersion):
            return value
        if isinstance(value, str):
            return AgentVersion.parse(value)
        raise AgentRegistryValidationError(
            "AgentVersionValidator requires AgentVersion or string",
            {"type": type(value).__name__},
        )


# ── Capability validator ────────────────────────────────────────────────────


class AgentCapabilityValidator:
    """Validates a single ``AgentCapability``."""

    @staticmethod
    def validate(capability: Any) -> AgentCapability:
        if not isinstance(capability, AgentCapability):
            raise AgentRegistryValidationError(
                "AgentCapabilityValidator requires AgentCapability",
                {"type": type(capability).__name__},
            )
        # Name uniqueness inside a single capability is enforced by
        # ``__post_init__``. We re-check the kind here for explicit
        # policy.
        if not isinstance(capability.kind, AgentCapabilityKind):
            raise AgentRegistryValidationError(
                "AgentCapability kind must be AgentCapabilityKind",
                {"field": "kind"},
            )
        return capability


# ── Descriptor validator ────────────────────────────────────────────────────


class AgentDescriptorValidator:
    """Cross-field validation for ``AgentDescriptor``."""

    @staticmethod
    def validate(descriptor: Any) -> AgentDescriptor:
        if not isinstance(descriptor, AgentDescriptor):
            raise AgentRegistryValidationError(
                "AgentDescriptorValidator requires AgentDescriptor",
                {"type": type(descriptor).__name__},
            )
        # lifecycle policy: no RETIRED or DISABLED descriptors exist (the
        # constructor already rejected them, but the validator is the
        # authoritative gate).
        if descriptor.lifecycle in (
            AgentLifecycle.RETIRED,
            AgentLifecycle.DISABLED,
        ):
            raise AgentRegistryValidationError(
                "Descriptor cannot be RETIRED or DISABLED",
                {"field": "lifecycle", "value": descriptor.lifecycle.value},
            )
        # factory_id format.
        if not descriptor.factory_id or not descriptor.factory_id.strip():
            raise AgentRegistryValidationError(
                "Descriptor factory_id must be non-empty",
                {"field": "factory_id"},
            )
        # aliases must not overlap with agent_id.
        for alias in descriptor.aliases:
            if alias == descriptor.agent_id:
                raise AgentRegistryValidationError(
                    "Descriptor aliases must not overlap with agent_id",
                    {"agent_id": descriptor.agent_id, "alias": alias},
                )
        # capability policy – the constructor already enforces uniqueness
        # by name; re-check.
        names = [c.name for c in descriptor.capabilities]
        if len(set(names)) != len(names):
            raise AgentRegistryValidationError(
                "Descriptor capability names must be unique",
                {"duplicates": sorted({n for n in names if names.count(n) > 1})},
            )
        # created_at must be tz-aware.
        if descriptor.created_at.tzinfo is None:
            raise AgentRegistryValidationError(
                "Descriptor created_at must be timezone-aware",
                {"field": "created_at"},
            )
        # metadata must be a Mapping.
        if not isinstance(descriptor.metadata, MappingProxyType):
            raise AgentRegistryValidationError(
                "Descriptor metadata must be MappingProxyType",
                {"field": "metadata"},
            )
        return descriptor


# ── Requirement validator ───────────────────────────────────────────────────


class AgentRequirementValidator:
    """Cross-field validation for ``AgentRequirement``."""

    @staticmethod
    def validate(requirement: Any) -> AgentRequirement:
        if not isinstance(requirement, AgentRequirement):
            raise AgentRegistryValidationError(
                "AgentRequirementValidator requires AgentRequirement",
                {"type": type(requirement).__name__},
            )
        if not requirement.has_any_filter():
            raise AgentRegistryValidationError(
                "AgentRequirement must include at least one filter",
                {"field": "requirement"},
            )
        if requirement.agent_id is not None and requirement.agent_id in (
            requirement.excluded_agents
        ):
            raise AgentRegistryValidationError(
                "AgentRequirement excludes its own agent_id",
                {
                    "agent_id": requirement.agent_id,
                    "excluded_agents": list(requirement.excluded_agents),
                },
            )
        if requirement.version is not None:
            # verify the version string parses cleanly.
            AgentVersion.parse(requirement.version)
        overlap = set(requirement.preferred_agents) & set(requirement.excluded_agents)
        if overlap:
            raise AgentRegistryValidationError(
                "AgentRequirement preferred_agents and excluded_agents overlap",
                {"overlap": sorted(overlap)},
            )
        return requirement


# ── Factory validator ───────────────────────────────────────────────────────


class AgentFactoryValidator:
    """Validates that a callable factory conforms to the ``AgentFactory``
    protocol and that its scope/policy is consistent.
    """

    @staticmethod
    def validate_factory(factory: Any) -> None:
        if factory is None:
            raise AgentFactoryError("Factory cannot be None", {"field": "factory"})
        if not hasattr(factory, "factory_id"):
            raise AgentFactoryCompatibilityError(
                "Factory must expose factory_id",
                {"type": type(factory).__name__},
            )
        if not hasattr(factory, "scope"):
            raise AgentFactoryCompatibilityError(
                "Factory must expose scope",
                {"type": type(factory).__name__},
            )
        factory_id = factory.factory_id
        if not isinstance(factory_id, str) or not factory_id.strip():
            raise AgentFactoryCompatibilityError(
                "Factory factory_id must be a non-empty string",
                {"type": type(factory).__name__},
            )
        scope = factory.scope
        if not isinstance(scope, AgentFactoryScope):
            raise AgentFactoryCompatibilityError(
                "Factory scope must be AgentFactoryScope",
                {"type": type(factory).__name__},
            )
        if scope == AgentFactoryScope.SINGLETON:
            thread_safe = getattr(factory, "thread_safe", False)
            if thread_safe is not True:
                raise AgentFactoryCompatibilityError(
                    "SINGLETON factory must declare thread_safe=True",
                    {"factory_id": factory_id},
                )
        if not callable(getattr(factory, "supports", None)):
            raise AgentFactoryCompatibilityError(
                "Factory must implement supports()",
                {"type": type(factory).__name__},
            )
        if not callable(getattr(factory, "create", None)):
            raise AgentFactoryCompatibilityError(
                "Factory must implement create()",
                {"type": type(factory).__name__},
            )

    @staticmethod
    def validate_descriptor_compatibility(
        factory: Any, descriptor: AgentDescriptor
    ) -> None:
        AgentFactoryValidator.validate_factory(factory)
        supports = factory.supports
        try:
            result = supports(descriptor)
        except Exception:  # noqa: BLE001 - mapped to safe error
            raise AgentFactoryCompatibilityError(
                "Factory supports() raised an exception",
                {"factory_id": factory.factory_id},
            ) from None
        if result is not True:
            raise AgentFactoryCompatibilityError(
                "Factory does not support descriptor",
                {
                    "factory_id": factory.factory_id,
                    "agent_id": descriptor.agent_id,
                },
            )


__all__ = [
    "AgentCapabilityValidator",
    "AgentDescriptorValidator",
    "AgentFactoryValidator",
    "AgentRequirementValidator",
    "AgentVersionValidator",
]
