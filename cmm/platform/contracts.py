"""Phase 11.1 — platform boundary contracts.

This module defines only the immutable values required by the Phase 11.1
integration core.  It deliberately does not redefine any canonical subsystem
contract: roadmap contract names that already have a canonical production owner
stay owned by that subsystem and are recorded, not cloned.

Service descriptor metadata is a small descriptive boundary, not a storage
surface.  Values are recursively normalized to immutable representations,
secret-shaped keys fail closed against a fixed denylist, and opaque runtime
objects are rejected.  This is a structural boundary; no content heuristics are
performed.

See ``docs/reference/phase-11-integration-core.md`` for the canonicalization
matrix that classifies every roadmap contract name.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

#: Normalized metadata key names (``api_key``) that fail closed.
SENSITIVE_METADATA_KEYS = frozenset(
    {
        "secret",
        "secrets",
        "credential",
        "credentials",
        "password",
        "passwd",
        "token",
        "api_key",
        "apikey",
        "access_key",
        "private_key",
        "auth",
        "authorization",
        "cookie",
        "session_key",
        "prompt",
        "reasoning",
        "provider_payload",
        "payload",
    }
)

#: Normalized metadata key tokens whose presence in any segment fails closed.
SENSITIVE_METADATA_KEY_TOKENS = frozenset(
    {
        "secret",
        "secrets",
        "credential",
        "credentials",
        "password",
        "passwd",
        "token",
        "auth",
        "authorization",
        "cookie",
        "prompt",
        "reasoning",
        "payload",
    }
)


def _non_empty(value: str, field_name: str) -> str:
    """Return the normalized value or fail closed on blank input."""

    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


def _metadata_key_tokens(key: str) -> tuple[str, ...]:
    """Split a metadata key into deterministic lowercase tokens."""

    return tuple(token for token in re.split(r"[^a-z0-9]+", key.lower()) if token)


def _is_sensitive_metadata_key(key: str) -> bool:
    """Return whether *key* names secret-bearing content.

    Comparison is exact over the normalized key and its deterministic segments,
    so it never guesses at arbitrary string content.
    """

    tokens = _metadata_key_tokens(key)
    if not tokens:
        return False
    if "_".join(tokens) in SENSITIVE_METADATA_KEYS:
        return True
    return any(token in SENSITIVE_METADATA_KEY_TOKENS for token in tokens)


def _normalize_metadata_value(value: object, key: str) -> object:
    """Return an immutable descriptive representation of *value*."""

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes | bytearray):
        raise TypeError(f"metadata '{key}' must not carry binary data")
    if isinstance(value, Mapping):
        return MappingProxyType(_normalize_metadata_mapping(value))
    if isinstance(value, Sequence):
        return tuple(_normalize_metadata_value(item, key) for item in value)

    raise TypeError(
        f"metadata '{key}' must be a descriptive immutable value, "
        f"not {type(value).__name__}"
    )


def _normalize_metadata_mapping(
    metadata: Mapping[object, object],
) -> dict[str, object]:
    """Copy *metadata* into a recursively immutable, secret-free mapping."""

    normalized: dict[str, object] = {}
    for key, value in metadata.items():
        if not isinstance(key, str):
            raise TypeError("metadata keys must be strings")
        if _is_sensitive_metadata_key(key):
            raise ValueError(
                f"metadata key '{key}' is not permitted in a service descriptor"
            )
        normalized[key] = _normalize_metadata_value(value, key)
    return normalized


class ContractClassification(str, Enum):
    """How a roadmap contract name maps onto repository reality."""

    CANONICAL_EXISTING = "canonical_existing"
    CANONICAL_ADAPTED = "canonical_adapted"
    NEW_PLATFORM_BOUNDARY = "new_platform_boundary"


class ServiceMode(str, Enum):
    """Binding mode of a platform service.

    ``ADAPTER`` describes an adapter-backed implementation that satisfies the
    same stable service contract.  Phase 11.1 implements no remote transport.
    """

    LOCAL = "local"
    ADAPTER = "adapter"


class ContainerState(str, Enum):
    """Lifecycle state of the application composition root."""

    BUILDING = "building"
    READY = "ready"
    FAILED = "failed"


class RuntimeContractMatch(str, Enum):
    """How the authoritative registry matches an implementation to its contract.

    ``INSTANCE_OF`` is the Phase 11.1 default and keeps the inherited
    subtype-compatible rule ``isinstance(implementation, runtime_contract)``.

    ``EXACT_TYPE`` is the reusable opt-in exact rule
    ``type(implementation) is runtime_contract``: a subclass, an adapter or a
    duck-typed look-alike can never claim an exact contract's composition
    identity.
    """

    INSTANCE_OF = "instance_of"
    EXACT_TYPE = "exact_type"


@dataclass(frozen=True, slots=True)
class ContractMetadata:
    """Immutable description of one public contract boundary.

    This describes a boundary only.  It never replaces version fields that a
    canonical model already owns.
    """

    contract_name: str
    contract_version: str
    schema_version: str
    owner: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "contract_name", _non_empty(self.contract_name, "contract_name")
        )
        object.__setattr__(
            self,
            "contract_version",
            _non_empty(self.contract_version, "contract_version"),
        )
        object.__setattr__(
            self, "schema_version", _non_empty(self.schema_version, "schema_version")
        )
        object.__setattr__(self, "owner", _non_empty(self.owner, "owner"))


@dataclass(frozen=True, slots=True)
class ContractCanonicalizationEntry:
    """One row of the canonicalization matrix.

    Records whether a roadmap contract name is satisfied by an existing
    canonical type, adapted from one, or genuinely new at the platform boundary.
    """

    roadmap_name: str
    python_symbol: str
    owner: str
    metadata: ContractMetadata
    classification: ContractClassification
    justification: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "roadmap_name", _non_empty(self.roadmap_name, "roadmap_name")
        )
        object.__setattr__(
            self, "python_symbol", _non_empty(self.python_symbol, "python_symbol")
        )
        object.__setattr__(self, "owner", _non_empty(self.owner, "owner"))
        object.__setattr__(
            self, "justification", _non_empty(self.justification, "justification")
        )


@dataclass(frozen=True, slots=True)
class ServiceDependency:
    """A required platform service plus the contract the service must satisfy."""

    service_id: str
    contract: ContractMetadata

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "service_id", _non_empty(self.service_id, "service_id")
        )


@dataclass(frozen=True, slots=True)
class ServiceDescriptor:
    """Immutable description of one platform service binding.

    Descriptors carry identifiers and boundary metadata only.  They never carry
    secrets, provider credentials, mutable runtime state, or copied sensitive
    domain content.

    ``metadata`` accepts only descriptive immutable values — ``None``, ``bool``,
    ``int``, ``float``, ``str``, mappings of those values, and sequences of
    them.  Mappings are copied and normalized to immutable representations,
    sequences become tuples, and any other object is rejected.  Keys naming
    secret-bearing content are rejected recursively, so descriptor metadata can
    never become a secret or live-state storage surface.

    ``mode`` must be a real :class:`ServiceMode`.  Malformed values are rejected
    here rather than silently coerced, because a ready composition must always
    produce a valid, serializable inspection snapshot.
    """

    service_id: str
    contract: ContractMetadata
    implementation_id: str
    dependencies: tuple[ServiceDependency, ...] = ()
    mode: ServiceMode = ServiceMode.LOCAL
    authority: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        service_id = _non_empty(self.service_id, "service_id")
        implementation_id = _non_empty(self.implementation_id, "implementation_id")

        if not isinstance(self.mode, ServiceMode):
            raise TypeError(
                f"mode must be a ServiceMode, not {type(self.mode).__name__}"
            )

        dependency_ids = tuple(dep.service_id for dep in self.dependencies)
        if service_id in dependency_ids:
            raise ValueError("service cannot depend on itself")
        if len(set(dependency_ids)) != len(dependency_ids):
            raise ValueError("dependency service IDs must be unique")

        authority = None if self.authority is None else self.authority.strip()
        if authority == "":
            raise ValueError("authority must be non-empty when provided")

        if not isinstance(self.metadata, Mapping):
            raise TypeError("metadata must be a mapping")

        object.__setattr__(self, "service_id", service_id)
        object.__setattr__(self, "implementation_id", implementation_id)
        object.__setattr__(self, "authority", authority)
        object.__setattr__(
            self,
            "dependencies",
            tuple(sorted(self.dependencies, key=lambda item: item.service_id)),
        )
        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(_normalize_metadata_mapping(self.metadata)),
        )


@dataclass(frozen=True, slots=True)
class ServiceBinding:
    """A descriptor bound to an already-constructed canonical implementation.

    The binding holds a reference to the canonical object.  It never clones or
    owns that object's internal state.

    ``runtime_contract_match`` selects the rule the authoritative registry
    applies to this binding.  ``INSTANCE_OF`` is the Phase 11.1 default and
    preserves the inherited subtype-compatible behavior; ``EXACT_TYPE`` requires
    the exact concrete runtime type and accepts no subclass.

    A runtime contract may declare the private marker
    ``__cmm_exact_runtime_contract__ = True``.  That marker is a *minimum*
    semantic, not a preference: the registry upgrades any declared mode to
    ``EXACT_TYPE``, so a hand-built binding can neither omit this field nor set it
    back to ``INSTANCE_OF`` to downgrade an exact contract.  An exact contract
    that is not a real Python type fails closed rather than passing unchecked.
    """

    descriptor: ServiceDescriptor
    implementation: object
    runtime_contract: type[Any] | None = None
    runtime_contract_match: RuntimeContractMatch = RuntimeContractMatch.INSTANCE_OF

    def __post_init__(self) -> None:
        if not isinstance(self.runtime_contract_match, RuntimeContractMatch):
            raise TypeError(
                "runtime_contract_match must be a RuntimeContractMatch, "
                f"not {type(self.runtime_contract_match).__name__}"
            )

        if self.runtime_contract_match is RuntimeContractMatch.EXACT_TYPE and not (
            isinstance(self.runtime_contract, type)
        ):
            raise ValueError(
                "runtime_contract_match=EXACT_TYPE requires runtime_contract to be "
                "a real Python type"
            )


@dataclass(frozen=True, slots=True)
class ErrorResult:
    """Minimal platform-boundary composition failure value.

    This is a boundary result only.  It never replaces canonical
    subsystem-specific error types inside those subsystems.

    ``details`` carries identifiers and reason codes only.  Arbitrary runtime
    objects, exception instances, secrets, credentials, provider payloads,
    prompts, tracebacks and hidden reasoning are rejected rather than
    serialized.
    """

    code: str
    message: str
    category: str
    details: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _non_empty(self.code, "code"))
        object.__setattr__(self, "message", _non_empty(self.message, "message"))
        object.__setattr__(self, "category", _non_empty(self.category, "category"))

        details = dict(self.details)
        for key, value in details.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise TypeError("error details must map strings to strings")
            _non_empty(key, "detail key")

        object.__setattr__(self, "details", MappingProxyType(details))


__all__ = [
    "ContainerState",
    "ContractCanonicalizationEntry",
    "ContractClassification",
    "ContractMetadata",
    "ErrorResult",
    "RuntimeContractMatch",
    "ServiceBinding",
    "ServiceDependency",
    "ServiceDescriptor",
    "ServiceMode",
]
