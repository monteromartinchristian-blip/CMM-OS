"""Phase 11.1 — platform boundary contracts.

This module defines only the immutable values required by the Phase 11.1
integration core.  It deliberately does not redefine any canonical subsystem
contract: roadmap contract names that already have a canonical production owner
stay owned by that subsystem and are recorded, not cloned.

See ``docs/reference/phase-11-integration-core.md`` for the canonicalization
matrix that classifies every roadmap contract name.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any


def _non_empty(value: str, field_name: str) -> str:
    """Return the normalized value or fail closed on blank input."""

    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
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

        dependency_ids = tuple(dep.service_id for dep in self.dependencies)
        if service_id in dependency_ids:
            raise ValueError("service cannot depend on itself")
        if len(set(dependency_ids)) != len(dependency_ids):
            raise ValueError("dependency service IDs must be unique")

        authority = None if self.authority is None else self.authority.strip()
        if authority == "":
            raise ValueError("authority must be non-empty when provided")

        object.__setattr__(self, "service_id", service_id)
        object.__setattr__(self, "implementation_id", implementation_id)
        object.__setattr__(self, "authority", authority)
        object.__setattr__(
            self,
            "dependencies",
            tuple(sorted(self.dependencies, key=lambda item: item.service_id)),
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ServiceBinding:
    """A descriptor bound to an already-constructed canonical implementation.

    The binding holds a reference to the canonical object.  It never clones or
    owns that object's internal state.
    """

    descriptor: ServiceDescriptor
    implementation: object
    runtime_contract: type[Any] | None = None


__all__ = [
    "ContainerState",
    "ContractCanonicalizationEntry",
    "ContractClassification",
    "ContractMetadata",
    "ServiceBinding",
    "ServiceDependency",
    "ServiceDescriptor",
    "ServiceMode",
]
