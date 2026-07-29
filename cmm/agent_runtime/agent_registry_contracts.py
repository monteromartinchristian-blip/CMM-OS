"""Phase 9.23 – Agent Registry & Factory Contracts.

Immutable, JSON-serializable, type-safe contracts used by the Agent
Registry & Factory subsystem.

All dataclasses are ``frozen=True`` and never expose mutable internal
state. ``runtime_object`` is intentionally *not* a public contract here
and must never be serialized.

Identity is ``(agent_id, version)``. Multiple versions of the same
agent may coexist; the registry resolves per agent, with a default
strategy of ``BEST_MATCH``.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.agent_registry_enums import (
    AgentCapabilityKind,
    AgentCompatibilityStatus,
    AgentFactoryScope,
    AgentKind,
    AgentLifecycle,
    AgentResolutionStrategy,
)
from cmm.agent_runtime.agent_registry_errors import (
    AgentRegistryValidationError,
)
from cmm.agent_runtime.model_requirements_contracts import (
    model_requirements_to_dict,
)
from kernel.llm.model_selection import ModelRequirements

# ── Helpers ──────────────────────────────────────────────────────────────────


_AGENT_ID_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.\-]{1,63}$")
_CAPABILITY_NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.\-]{0,63}$")
_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.\-]{0,127}$")
_FACTORY_ID_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.\-]{0,63}$")
_VERSION_PATTERN = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z.\-]+))?$"
)

_FORBIDDEN_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "chain_of_thought",
        "private_prompt",
        "internal_reasoning",
        "api_key",
        "apikey",
        "password",
        "passwd",
        "private_key",
        "secret",
        "bearer",
        "token",
    }
)

_LIFECYCLE_RESOLVABLE: frozenset[AgentLifecycle] = frozenset({AgentLifecycle.ACTIVE})


def _validate_non_empty_str(val: Any, field_name: str) -> str:
    if not isinstance(val, str):
        raise AgentRegistryValidationError(
            f"{field_name} must be a string", {"field": field_name}
        )
    if not val.strip():
        raise AgentRegistryValidationError(
            f"{field_name} must be a non-empty string", {"field": field_name}
        )
    return val.strip()


def _validate_identifier(val: Any, field_name: str) -> str:
    s = _validate_non_empty_str(val, field_name)
    if not _IDENTIFIER_PATTERN.match(s):
        raise AgentRegistryValidationError(
            f"{field_name} has invalid format",
            {"field": field_name, "value": s},
        )
    return s


def _ensure_tz_aware(dt: Any, field_name: str) -> datetime:
    if not isinstance(dt, datetime):
        raise AgentRegistryValidationError(
            f"{field_name} must be a datetime", {"field": field_name}
        )
    if dt.tzinfo is None:
        raise AgentRegistryValidationError(
            f"{field_name} must be timezone-aware",
            {"field": field_name},
        )
    return dt


def _validate_metadata(meta: Any, field_name: str) -> MappingProxyType[str, Any]:
    if meta is None:
        return MappingProxyType({})
    if not isinstance(meta, Mapping):
        raise AgentRegistryValidationError(
            f"{field_name} must be a Mapping",
            {"field": field_name},
        )
    out: dict[str, Any] = {}
    for key, value in meta.items():
        if not isinstance(key, str):
            raise AgentRegistryValidationError(
                f"{field_name} keys must be strings",
                {"field": field_name},
            )
        lower = key.lower()
        if lower in _FORBIDDEN_METADATA_KEYS:
            raise AgentRegistryValidationError(
                f"{field_name} contains forbidden key",
                {"field": field_name, "key": key},
            )
        if not _is_json_safe(value):
            raise AgentRegistryValidationError(
                f"{field_name} contains non-serializable value",
                {"field": field_name, "key": key},
            )
        out[key] = value
    return MappingProxyType(dict(out))


def _is_json_safe(value: Any) -> bool:
    """Return True when ``value`` is JSON-serializable."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return True
    if isinstance(value, (list, tuple)):
        return all(_is_json_safe(item) for item in value)
    if isinstance(value, Mapping):
        return all(isinstance(k, str) and _is_json_safe(v) for k, v in value.items())
    return bool(isinstance(value, datetime))


def _freeze_str_tuple(
    seq: Any, field_name: str, *, allow_empty: bool = True
) -> tuple[str, ...]:
    if seq is None:
        if allow_empty:
            return ()
        raise AgentRegistryValidationError(
            f"{field_name} cannot be None", {"field": field_name}
        )
    if not isinstance(seq, (tuple, list, set, frozenset, Sequence)) or isinstance(
        seq, (str, bytes)
    ):
        raise AgentRegistryValidationError(
            f"{field_name} must be a sequence of strings",
            {"field": field_name},
        )
    cleaned: list[str] = []
    for item in seq:
        if not isinstance(item, str) or not item.strip():
            raise AgentRegistryValidationError(
                f"{field_name} must contain non-empty strings",
                {"field": field_name},
            )
        cleaned.append(item.strip())
    return tuple(cleaned)


def _freeze_unique_str_tuple(seq: Any, field_name: str) -> tuple[str, ...]:
    items = _freeze_str_tuple(seq, field_name)
    if len(set(items)) != len(items):
        raise AgentRegistryValidationError(
            f"{field_name} must not contain duplicates",
            {"field": field_name},
        )
    return items


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _generate_uuid() -> str:
    return str(uuid.uuid4())


# ── AgentVersion ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentVersion:
    """Semantic-like agent version value type.

    Accepts parsing of:

    * ``1.0.0``
    * ``2.1.3``
    * ``1.0.0-alpha``
    * ``1.0.0-beta.2``

    Negative numbers, spaces, missing parts, or ambiguous suffixes are
    rejected. Comparison is deterministic.
    """

    major: int
    minor: int
    patch: int
    prerelease: str | None = None

    def __post_init__(self) -> None:
        for part_name, part_val in (
            ("major", self.major),
            ("minor", self.minor),
            ("patch", self.patch),
        ):
            if not isinstance(part_val, int) or isinstance(part_val, bool):
                raise AgentRegistryValidationError(
                    f"AgentVersion {part_name} must be an integer",
                    {"field": part_name},
                )
            if part_val < 0:
                raise AgentRegistryValidationError(
                    f"AgentVersion {part_name} must be non-negative",
                    {"field": part_name, "value": part_val},
                )
        if self.prerelease is not None:
            if not isinstance(self.prerelease, str):
                raise AgentRegistryValidationError(
                    "AgentVersion prerelease must be a string or None",
                    {"field": "prerelease"},
                )
            if not self.prerelease:
                raise AgentRegistryValidationError(
                    "AgentVersion prerelease must not be empty when present",
                    {"field": "prerelease"},
                )
            if " " in self.prerelease:
                raise AgentRegistryValidationError(
                    "AgentVersion prerelease must not contain spaces",
                    {"field": "prerelease"},
                )
            if not re.match(r"^[0-9A-Za-z.\-]+$", self.prerelease):
                raise AgentRegistryValidationError(
                    "AgentVersion prerelease has invalid characters",
                    {"field": "prerelease"},
                )

    @classmethod
    def parse(cls, raw: Any) -> AgentVersion:
        """Parse a version string into an ``AgentVersion`` value.

        Strict parsing: empty, whitespace, missing parts or non-canonical
        forms are rejected.
        """
        if not isinstance(raw, str):
            raise AgentRegistryValidationError(
                "AgentVersion source must be a string",
                {"value_type": type(raw).__name__},
            )
        stripped = raw.strip()
        if not stripped:
            raise AgentRegistryValidationError(
                "AgentVersion string must not be empty",
                {"value": raw},
            )
        if " " in stripped:
            raise AgentRegistryValidationError(
                "AgentVersion string must not contain spaces",
                {"value": raw},
            )
        match = _VERSION_PATTERN.match(stripped)
        if not match:
            raise AgentRegistryValidationError(
                "AgentVersion string is not a valid canonical version",
                {"value": raw},
            )
        return cls(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
            prerelease=match.group("prerelease"),
        )

    def is_prerelease(self) -> bool:
        return self.prerelease is not None

    def canonical(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease is None:
            return base
        return f"{base}-{self.prerelease}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "major": self.major,
            "minor": self.minor,
            "patch": self.patch,
            "prerelease": self.prerelease,
        }

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.canonical()

    def _comparison_key(self) -> tuple[int, int, int, int, str]:
        """Return a deterministic ordering key.

        Pre-release builds sort before the corresponding release:
        ``1.0.0-alpha`` < ``1.0.0``. Within the same numeric triple,
        pre-release tags are compared lexicographically, with ``""``
        (the release tag) sorting *after* any non-empty pre-release.

        Implementation note: the first tuple element is ``1`` when
        ``prerelease is None`` and ``0`` otherwise, so any release is
        strictly greater than any pre-release with the same numeric
        triple.
        """
        if self.prerelease is None:
            return (1, self.major, self.minor, self.patch, "")
        return (0, self.major, self.minor, self.patch, self.prerelease)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, AgentVersion):
            return NotImplemented
        return self._comparison_key() < other._comparison_key()

    def __le__(self, other: object) -> bool:
        if not isinstance(other, AgentVersion):
            return NotImplemented
        return self._comparison_key() <= other._comparison_key()

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, AgentVersion):
            return NotImplemented
        return self._comparison_key() > other._comparison_key()

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, AgentVersion):
            return NotImplemented
        return self._comparison_key() >= other._comparison_key()

    def __hash__(self) -> int:
        return hash((self.major, self.minor, self.patch, self.prerelease))


# ── AgentCapability ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentCapability:
    """Immutable capability declaration attached to a descriptor."""

    name: str
    kind: AgentCapabilityKind
    version: str | None = None
    description: str | None = None
    operations: tuple[str, ...] = ()
    input_types: tuple[str, ...] = ()
    output_types: tuple[str, ...] = ()
    required_permissions: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise AgentRegistryValidationError(
                "AgentCapability name must be a string",
                {"field": "name"},
            )
        name = self.name.strip()
        if not name:
            raise AgentRegistryValidationError(
                "AgentCapability name must be non-empty",
                {"field": "name"},
            )
        if not _CAPABILITY_NAME_PATTERN.match(name):
            raise AgentRegistryValidationError(
                "AgentCapability name has invalid format",
                {"field": "name", "value": name},
            )
        if not isinstance(self.kind, AgentCapabilityKind):
            raise AgentRegistryValidationError(
                "AgentCapability kind must be an AgentCapabilityKind enum",
                {"field": "kind"},
            )
        if self.version is not None and (
            not isinstance(self.version, str) or not self.version.strip()
        ):
            raise AgentRegistryValidationError(
                "AgentCapability version must be a non-empty string or None",
                {"field": "version"},
            )
        if self.description is not None and not isinstance(self.description, str):
            raise AgentRegistryValidationError(
                "AgentCapability description must be a string or None",
                {"field": "description"},
            )
        for field_name, value in (
            ("operations", self.operations),
            ("input_types", self.input_types),
            ("output_types", self.output_types),
            ("required_permissions", self.required_permissions),
        ):
            object.__setattr__(self, field_name, _freeze_str_tuple(value, field_name))
        # Operations must be unique and sorted deterministically.
        if len(set(self.operations)) != len(self.operations):
            raise AgentRegistryValidationError(
                "AgentCapability operations must be unique",
                {"field": "operations"},
            )
        object.__setattr__(
            self,
            "operations",
            tuple(sorted(self.operations)),
        )
        if len(set(self.required_permissions)) != len(self.required_permissions):
            raise AgentRegistryValidationError(
                "AgentCapability required_permissions must be unique",
                {"field": "required_permissions"},
            )
        object.__setattr__(
            self,
            "metadata",
            _validate_metadata(self.metadata, "AgentCapability.metadata"),
        )
        # name normalization
        object.__setattr__(self, "name", name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind.value,
            "version": self.version,
            "description": self.description,
            "operations": list(self.operations),
            "input_types": list(self.input_types),
            "output_types": list(self.output_types),
            "required_permissions": list(self.required_permissions),
            "metadata": dict(self.metadata),
        }


# ── AgentDescriptor ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentDescriptor:
    """Declarative descriptor for a registered agent version.

    Identity is ``(agent_id, version)``. The descriptor is immutable
    and safe to share. ``created_at`` must always be timezone-aware.
    """

    agent_id: str
    name: str
    version: AgentVersion
    kind: AgentKind
    lifecycle: AgentLifecycle
    description: str
    capabilities: tuple[AgentCapability, ...]
    factory_id: str
    priority: int = 0
    aliases: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    required_permissions: tuple[str, ...] = ()
    required_components: tuple[str, ...] = ()
    supported_operations: tuple[str, ...] = ()
    compatible_runtime_versions: tuple[str, ...] = ()
    model_requirements: ModelRequirements | None = None
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    created_at: datetime = field(default_factory=_now_utc)

    def __post_init__(self) -> None:
        if not isinstance(self.agent_id, str) or not self.agent_id.strip():
            raise AgentRegistryValidationError(
                "AgentDescriptor agent_id must be a non-empty string",
                {"field": "agent_id"},
            )
        if not _AGENT_ID_PATTERN.match(self.agent_id):
            raise AgentRegistryValidationError(
                "AgentDescriptor agent_id has invalid format",
                {"field": "agent_id", "value": self.agent_id},
            )
        if not isinstance(self.name, str) or not self.name.strip():
            raise AgentRegistryValidationError(
                "AgentDescriptor name must be a non-empty string",
                {"field": "name"},
            )
        if not isinstance(self.description, str) or not self.description.strip():
            raise AgentRegistryValidationError(
                "AgentDescriptor description must be a non-empty string",
                {"field": "description"},
            )
        if not isinstance(self.version, AgentVersion):
            raise AgentRegistryValidationError(
                "AgentDescriptor version must be an AgentVersion instance",
                {"field": "version"},
            )
        if not isinstance(self.kind, AgentKind):
            raise AgentRegistryValidationError(
                "AgentDescriptor kind must be an AgentKind enum",
                {"field": "kind"},
            )
        if not isinstance(self.lifecycle, AgentLifecycle):
            raise AgentRegistryValidationError(
                "AgentDescriptor lifecycle must be an AgentLifecycle enum",
                {"field": "lifecycle"},
            )
        if not isinstance(self.factory_id, str) or not self.factory_id.strip():
            raise AgentRegistryValidationError(
                "AgentDescriptor factory_id must be a non-empty string",
                {"field": "factory_id"},
            )
        if not _FACTORY_ID_PATTERN.match(self.factory_id):
            raise AgentRegistryValidationError(
                "AgentDescriptor factory_id has invalid format",
                {"field": "factory_id", "value": self.factory_id},
            )
        if not isinstance(self.priority, int) or isinstance(self.priority, bool):
            raise AgentRegistryValidationError(
                "AgentDescriptor priority must be an integer",
                {"field": "priority"},
            )
        if (
            self.model_requirements is not None
            and not isinstance(self.model_requirements, ModelRequirements)
        ):
            raise AgentRegistryValidationError(
                "AgentDescriptor model_requirements must be "
                "a ModelRequirements instance or None",
                {"field": "model_requirements"},
            )

        # capabilities – must be AgentCapability instances, no dup names.
        if not isinstance(self.capabilities, tuple):
            raise AgentRegistryValidationError(
                "AgentDescriptor capabilities must be a tuple",
                {"field": "capabilities"},
            )
        seen_names: set[str] = set()
        for cap in self.capabilities:
            if not isinstance(cap, AgentCapability):
                raise AgentRegistryValidationError(
                    "AgentDescriptor capabilities must be AgentCapability",
                    {"field": "capabilities"},
                )
            if cap.name in seen_names:
                raise AgentRegistryValidationError(
                    "AgentDescriptor capabilities must be unique by name",
                    {"field": "capabilities", "duplicate": cap.name},
                )
            seen_names.add(cap.name)

        # aliases / tags / operations / permissions / components.
        object.__setattr__(
            self, "aliases", _freeze_unique_str_tuple(self.aliases, "aliases")
        )
        object.__setattr__(self, "tags", _freeze_unique_str_tuple(self.tags, "tags"))
        object.__setattr__(
            self,
            "required_permissions",
            _freeze_unique_str_tuple(self.required_permissions, "required_permissions"),
        )
        object.__setattr__(
            self,
            "required_components",
            _freeze_unique_str_tuple(self.required_components, "required_components"),
        )
        object.__setattr__(
            self,
            "supported_operations",
            _freeze_unique_str_tuple(self.supported_operations, "supported_operations"),
        )
        object.__setattr__(
            self,
            "compatible_runtime_versions",
            _freeze_unique_str_tuple(
                self.compatible_runtime_versions, "compatible_runtime_versions"
            ),
        )
        # aliases must not overlap with agent_id.
        for alias in self.aliases:
            if alias == self.agent_id:
                raise AgentRegistryValidationError(
                    "AgentDescriptor aliases must not overlap with agent_id",
                    {"agent_id": self.agent_id, "alias": alias},
                )
        # metadata – immutable, JSON safe, no secrets.
        object.__setattr__(
            self,
            "metadata",
            _validate_metadata(self.metadata, "AgentDescriptor.metadata"),
        )
        # created_at – must be tz-aware.
        object.__setattr__(
            self, "created_at", _ensure_tz_aware(self.created_at, "created_at")
        )
        # RETIRED and DISABLED descriptors are rejected at construction so
        # they can never enter the registry.
        if self.lifecycle in (
            AgentLifecycle.RETIRED,
            AgentLifecycle.DISABLED,
        ):
            raise AgentRegistryValidationError(
                "AgentDescriptor lifecycle cannot be RETIRED or DISABLED",
                {"field": "lifecycle", "value": self.lifecycle.value},
            )

    def is_resolvable_default(self) -> bool:
        """Return whether this descriptor is resolvable under default rules.

        Default rules select only ``ACTIVE`` agents.
        """
        return self.lifecycle == AgentLifecycle.ACTIVE

    def with_lifecycle(self, lifecycle: AgentLifecycle) -> AgentDescriptor:
        """Return a new descriptor with ``lifecycle`` replaced.

        The original descriptor is immutable; this is the supported way
        to change lifecycle. ``RETIRED`` is rejected here.
        """
        if lifecycle in (AgentLifecycle.RETIRED, AgentLifecycle.DISABLED):
            raise AgentRegistryValidationError(
                "Descriptor cannot be transitioned to RETIRED or DISABLED",
                {"field": "lifecycle", "value": lifecycle.value},
            )
        return AgentDescriptor(
            agent_id=self.agent_id,
            name=self.name,
            version=self.version,
            kind=self.kind,
            lifecycle=lifecycle,
            description=self.description,
            capabilities=self.capabilities,
            factory_id=self.factory_id,
            priority=self.priority,
            aliases=self.aliases,
            tags=self.tags,
            required_permissions=self.required_permissions,
            required_components=self.required_components,
            supported_operations=self.supported_operations,
            compatible_runtime_versions=self.compatible_runtime_versions,
            model_requirements=self.model_requirements,
            metadata=self.metadata,
            created_at=self.created_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "version": self.version.canonical(),
            "kind": self.kind.value,
            "lifecycle": self.lifecycle.value,
            "description": self.description,
            "capabilities": [c.to_dict() for c in self.capabilities],
            "factory_id": self.factory_id,
            "priority": self.priority,
            "aliases": list(self.aliases),
            "tags": list(self.tags),
            "required_permissions": list(self.required_permissions),
            "required_components": list(self.required_components),
            "supported_operations": list(self.supported_operations),
            "compatible_runtime_versions": list(self.compatible_runtime_versions),
            "model_requirements": (
                model_requirements_to_dict(self.model_requirements)
                if self.model_requirements is not None
                else None
            ),
            "metadata": dict(self.metadata),
            "created_at": self.created_at.isoformat(),
        }


# ── AgentRequirement ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentRequirement:
    """Structured request used to resolve an agent.

    The requirement may be empty (no constraints at all) but if every
    selection field is empty, a structured error is raised by the
    requirement validator.
    """

    agent_id: str | None = None
    version: str | None = None
    kind: AgentKind | None = None
    required_capabilities: tuple[str, ...] = ()
    required_operations: tuple[str, ...] = ()
    required_tags: tuple[str, ...] = ()
    required_permissions: tuple[str, ...] = ()
    preferred_agents: tuple[str, ...] = ()
    excluded_agents: tuple[str, ...] = ()
    allow_experimental: bool = False
    allow_deprecated: bool = False
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if self.agent_id is not None and (
            not isinstance(self.agent_id, str) or not self.agent_id.strip()
        ):
            raise AgentRegistryValidationError(
                "AgentRequirement agent_id must be a non-empty string or None",
                {"field": "agent_id"},
            )
        if self.version is not None and (
            not isinstance(self.version, str) or not self.version.strip()
        ):
            raise AgentRegistryValidationError(
                "AgentRequirement version must be a non-empty string or None",
                {"field": "version"},
            )
        if self.kind is not None and not isinstance(self.kind, AgentKind):
            raise AgentRegistryValidationError(
                "AgentRequirement kind must be an AgentKind or None",
                {"field": "kind"},
            )

        object.__setattr__(
            self,
            "required_capabilities",
            _freeze_unique_str_tuple(
                self.required_capabilities, "required_capabilities"
            ),
        )
        object.__setattr__(
            self,
            "required_operations",
            _freeze_unique_str_tuple(self.required_operations, "required_operations"),
        )
        object.__setattr__(
            self,
            "required_tags",
            _freeze_unique_str_tuple(self.required_tags, "required_tags"),
        )
        object.__setattr__(
            self,
            "required_permissions",
            _freeze_unique_str_tuple(self.required_permissions, "required_permissions"),
        )
        object.__setattr__(
            self,
            "preferred_agents",
            _freeze_unique_str_tuple(self.preferred_agents, "preferred_agents"),
        )
        object.__setattr__(
            self,
            "excluded_agents",
            _freeze_unique_str_tuple(self.excluded_agents, "excluded_agents"),
        )
        # Contradictory exclusion: agent_id == excluded_agent.
        if self.agent_id is not None and self.agent_id in self.excluded_agents:
            raise AgentRegistryValidationError(
                "AgentRequirement excludes its own agent_id",
                {
                    "agent_id": self.agent_id,
                    "excluded_agents": list(self.excluded_agents),
                },
            )
        # preferred cannot be excluded.
        overlap = set(self.preferred_agents) & set(self.excluded_agents)
        if overlap:
            raise AgentRegistryValidationError(
                "AgentRequirement preferred_agents and excluded_agents overlap",
                {"overlap": sorted(overlap)},
            )
        object.__setattr__(
            self,
            "metadata",
            _validate_metadata(self.metadata, "AgentRequirement.metadata"),
        )

    def has_any_filter(self) -> bool:
        """Return True if at least one filtering field is set."""
        return any(
            (
                self.agent_id is not None,
                self.version is not None,
                self.kind is not None,
                bool(self.required_capabilities),
                bool(self.required_operations),
                bool(self.required_tags),
                bool(self.required_permissions),
                bool(self.preferred_agents),
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "version": self.version,
            "kind": self.kind.value if self.kind is not None else None,
            "required_capabilities": list(self.required_capabilities),
            "required_operations": list(self.required_operations),
            "required_tags": list(self.required_tags),
            "required_permissions": list(self.required_permissions),
            "preferred_agents": list(self.preferred_agents),
            "excluded_agents": list(self.excluded_agents),
            "allow_experimental": self.allow_experimental,
            "allow_deprecated": self.allow_deprecated,
            "metadata": dict(self.metadata),
        }


# ── AgentResolutionCandidate / AgentResolution ──────────────────────────────


@dataclass(frozen=True)
class AgentResolutionCandidate:
    """Per-descriptor evaluation result of a resolution attempt."""

    descriptor: AgentDescriptor
    compatibility: AgentCompatibilityStatus
    score: int
    matched_capabilities: tuple[str, ...] = ()
    missing_capabilities: tuple[str, ...] = ()
    matched_operations: tuple[str, ...] = ()
    missing_operations: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.descriptor, AgentDescriptor):
            raise AgentRegistryValidationError(
                "AgentResolutionCandidate descriptor must be an AgentDescriptor",
                {"field": "descriptor"},
            )
        if not isinstance(self.compatibility, AgentCompatibilityStatus):
            raise AgentRegistryValidationError(
                "AgentResolutionCandidate compatibility must be enum",
                {"field": "compatibility"},
            )
        if not isinstance(self.score, int) or isinstance(self.score, bool):
            raise AgentRegistryValidationError(
                "AgentResolutionCandidate score must be int",
                {"field": "score"},
            )
        for name in (
            "matched_capabilities",
            "missing_capabilities",
            "matched_operations",
            "missing_operations",
            "rejection_reasons",
        ):
            value = getattr(self, name)
            if not isinstance(value, tuple):
                raise AgentRegistryValidationError(
                    f"{name} must be a tuple", {"field": name}
                )
            for item in value:
                if not isinstance(item, str):
                    raise AgentRegistryValidationError(
                        f"{name} items must be strings",
                        {"field": name},
                    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "descriptor": self.descriptor.to_dict(),
            "compatibility": self.compatibility.value,
            "score": self.score,
            "matched_capabilities": list(self.matched_capabilities),
            "missing_capabilities": list(self.missing_capabilities),
            "matched_operations": list(self.matched_operations),
            "missing_operations": list(self.missing_operations),
            "rejection_reasons": list(self.rejection_reasons),
        }


@dataclass(frozen=True)
class AgentResolution:
    """Structured result of an agent resolution attempt."""

    selected: AgentDescriptor | None
    candidates: tuple[AgentResolutionCandidate, ...]
    strategy: AgentResolutionStrategy
    resolved_at: datetime = field(default_factory=_now_utc)
    request_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.strategy, AgentResolutionStrategy):
            raise AgentRegistryValidationError(
                "AgentResolution strategy must be enum",
                {"field": "strategy"},
            )
        if not isinstance(self.candidates, tuple):
            raise AgentRegistryValidationError(
                "AgentResolution candidates must be a tuple",
                {"field": "candidates"},
            )
        for c in self.candidates:
            if not isinstance(c, AgentResolutionCandidate):
                raise AgentRegistryValidationError(
                    "AgentResolution candidates must be AgentResolutionCandidate",
                    {"field": "candidates"},
                )
        if self.selected is not None:
            if not isinstance(self.selected, AgentDescriptor):
                raise AgentRegistryValidationError(
                    "AgentResolution selected must be AgentDescriptor or None",
                    {"field": "selected"},
                )
            # selected must appear among candidates with COMPATIBLE
            # status. We use ``is`` (identity) rather than equality
            # because ``AgentDescriptor`` is not hashable – each
            # descriptor instance is immutable and represents exactly
            # one identity, so identity comparison is safe.
            if not any(
                c.descriptor is self.selected
                and c.compatibility == AgentCompatibilityStatus.COMPATIBLE
                for c in self.candidates
            ):
                raise AgentRegistryValidationError(
                    "AgentResolution selected must be among compatible candidates",
                    {"field": "selected"},
                )
        object.__setattr__(
            self, "resolved_at", _ensure_tz_aware(self.resolved_at, "resolved_at")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected": self.selected.to_dict() if self.selected else None,
            "candidates": [c.to_dict() for c in self.candidates],
            "strategy": self.strategy.value,
            "resolved_at": self.resolved_at.isoformat(),
            "request_id": self.request_id,
        }


# ── Compatibility Result ────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentCompatibilityResult:
    """Structured compatibility verdict for a (descriptor, requirement) pair."""

    status: AgentCompatibilityStatus
    reasons: tuple[str, ...] = ()
    missing_components: tuple[str, ...] = ()
    missing_permissions: tuple[str, ...] = ()
    missing_capabilities: tuple[str, ...] = ()
    missing_operations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, AgentCompatibilityStatus):
            raise AgentRegistryValidationError(
                "AgentCompatibilityResult status must be enum",
                {"field": "status"},
            )
        for name in (
            "reasons",
            "missing_components",
            "missing_permissions",
            "missing_capabilities",
            "missing_operations",
        ):
            value = getattr(self, name)
            if not isinstance(value, tuple):
                raise AgentRegistryValidationError(
                    f"{name} must be a tuple", {"field": name}
                )
            for item in value:
                if not isinstance(item, str):
                    raise AgentRegistryValidationError(
                        f"{name} items must be strings",
                        {"field": name},
                    )

    @property
    def is_compatible(self) -> bool:
        return self.status == AgentCompatibilityStatus.COMPATIBLE

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "reasons": list(self.reasons),
            "missing_components": list(self.missing_components),
            "missing_permissions": list(self.missing_permissions),
            "missing_capabilities": list(self.missing_capabilities),
            "missing_operations": list(self.missing_operations),
        }


# ── AgentInstance / AgentFactoryContext ─────────────────────────────────────


@dataclass(frozen=True)
class AgentFactoryContext:
    """Immutable context handed to a factory when creating an instance."""

    request_id: str = field(default_factory=_generate_uuid)
    run_id: str | None = None
    actor_id: str | None = None
    permissions: tuple[str, ...] = ()
    components: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    configuration: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    created_at: datetime = field(default_factory=_now_utc)

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not self.request_id.strip():
            raise AgentRegistryValidationError(
                "AgentFactoryContext request_id must be a non-empty string",
                {"field": "request_id"},
            )
        if self.run_id is not None and (
            not isinstance(self.run_id, str) or not self.run_id.strip()
        ):
            raise AgentRegistryValidationError(
                "AgentFactoryContext run_id must be a non-empty string or None",
                {"field": "run_id"},
            )
        if self.actor_id is not None and (
            not isinstance(self.actor_id, str) or not self.actor_id.strip()
        ):
            raise AgentRegistryValidationError(
                "AgentFactoryContext actor_id must be a non-empty string or None",
                {"field": "actor_id"},
            )
        object.__setattr__(
            self,
            "permissions",
            _freeze_unique_str_tuple(self.permissions, "permissions"),
        )
        # components and configuration must be JSON-safe, no secrets.
        object.__setattr__(
            self,
            "components",
            _validate_metadata(self.components, "AgentFactoryContext.components"),
        )
        object.__setattr__(
            self,
            "configuration",
            _validate_metadata(self.configuration, "AgentFactoryContext.configuration"),
        )
        object.__setattr__(
            self, "created_at", _ensure_tz_aware(self.created_at, "created_at")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "run_id": self.run_id,
            "actor_id": self.actor_id,
            "permissions": list(self.permissions),
            "components": dict(self.components),
            "configuration": dict(self.configuration),
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class AgentInstance:
    """Identifier-bearing wrapper around the runtime object created by a factory.

    ``runtime_object`` is intentionally typed as ``Any`` but is treated
    as opaque: it must never be serialized, logged or returned in any
    public response.
    """

    instance_id: str
    descriptor: AgentDescriptor
    runtime_object: Any
    created_at: datetime = field(default_factory=_now_utc)
    scope: AgentFactoryScope = AgentFactoryScope.TRANSIENT

    def __post_init__(self) -> None:
        if not isinstance(self.instance_id, str) or not self.instance_id.strip():
            raise AgentRegistryValidationError(
                "AgentInstance instance_id must be a non-empty string",
                {"field": "instance_id"},
            )
        if not isinstance(self.descriptor, AgentDescriptor):
            raise AgentRegistryValidationError(
                "AgentInstance descriptor must be AgentDescriptor",
                {"field": "descriptor"},
            )
        if not isinstance(self.scope, AgentFactoryScope):
            raise AgentRegistryValidationError(
                "AgentInstance scope must be AgentFactoryScope",
                {"field": "scope"},
            )
        object.__setattr__(
            self, "created_at", _ensure_tz_aware(self.created_at, "created_at")
        )

    def to_dict(self) -> dict[str, Any]:
        # ``runtime_object`` is intentionally excluded.
        return {
            "instance_id": self.instance_id,
            "descriptor": self.descriptor.to_dict(),
            "created_at": self.created_at.isoformat(),
            "scope": self.scope.value,
        }


# ── Provisioning result ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentProvisioningResult:
    """Structured result of a ``resolve_and_create`` operation."""

    resolution: AgentResolution
    instance: AgentInstance | None
    created_at: datetime = field(default_factory=_now_utc)
    request_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.resolution, AgentResolution):
            raise AgentRegistryValidationError(
                "AgentProvisioningResult resolution must be AgentResolution",
                {"field": "resolution"},
            )
        if self.instance is not None and not isinstance(self.instance, AgentInstance):
            raise AgentRegistryValidationError(
                "AgentProvisioningResult instance must be AgentInstance or None",
                {"field": "instance"},
            )
        # Either there is no selection and no instance, or both are set.
        if self.resolution.selected is None and self.instance is not None:
            raise AgentRegistryValidationError(
                "AgentProvisioningResult cannot include instance without selection",
                {"field": "instance"},
            )
        if self.resolution.selected is not None and self.instance is None:
            raise AgentRegistryValidationError(
                "AgentProvisioningResult cannot succeed without instance",
                {"field": "instance"},
            )
        if self.instance is not None and (
            self.instance.descriptor != self.resolution.selected
        ):
            raise AgentRegistryValidationError(
                "AgentProvisioningResult instance descriptor must match selected",
                {"field": "instance"},
            )
        object.__setattr__(
            self, "created_at", _ensure_tz_aware(self.created_at, "created_at")
        )

    @property
    def is_success(self) -> bool:
        return self.instance is not None and self.resolution.selected is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolution": self.resolution.to_dict(),
            "instance": self.instance.to_dict() if self.instance else None,
            "created_at": self.created_at.isoformat(),
            "request_id": self.request_id,
        }


__all__ = [
    "AgentCapability",
    "AgentCompatibilityResult",
    "AgentDescriptor",
    "AgentFactoryContext",
    "AgentInstance",
    "AgentProvisioningResult",
    "AgentRequirement",
    "AgentResolution",
    "AgentResolutionCandidate",
    "AgentVersion",
]
