"""Phase 11.1 — safe deterministic composition inspection.

A ready composition must be inspectable without leaking runtime internals.  This
module therefore serializes an explicit **allowlist** of boundary identifiers
and nothing else.

Never exposed: raw implementation objects, runtime contract objects, arbitrary
descriptor metadata, secrets, credentials, tokens, passwords, prompts, hidden
reasoning, provider payloads or opaque internal state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cmm.platform.contracts import ContainerState, ServiceMode
from cmm.platform.service_registry import IntegrationServiceRegistry


def _require_identifier(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


@dataclass(frozen=True, slots=True)
class ServiceInspection:
    """Allowlisted, serialization-safe view of one composed service."""

    service_id: str
    implementation_id: str
    contract_name: str
    contract_version: str
    schema_version: str
    owner: str
    dependency_ids: tuple[str, ...]
    mode: ServiceMode
    authority: str | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "service_id", _require_identifier(self.service_id, "service_id")
        )
        object.__setattr__(
            self,
            "implementation_id",
            _require_identifier(self.implementation_id, "implementation_id"),
        )
        object.__setattr__(
            self,
            "dependency_ids",
            tuple(sorted(self.dependency_ids)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a fresh, plain, JSON-serializable mapping."""

        return {
            "service_id": self.service_id,
            "implementation_id": self.implementation_id,
            "contract_name": self.contract_name,
            "contract_version": self.contract_version,
            "schema_version": self.schema_version,
            "owner": self.owner,
            "dependency_ids": list(self.dependency_ids),
            "mode": ServiceMode(self.mode).value,
            "authority": self.authority,
        }


@dataclass(frozen=True, slots=True)
class ApplicationCompositionSnapshot:
    """Allowlisted, serialization-safe view of the whole composition."""

    state: ContainerState
    services: tuple[ServiceInspection, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a fresh, plain, JSON-serializable mapping."""

        return {
            "state": ContainerState(self.state).value,
            "services": [service.to_dict() for service in self.services],
        }


def build_composition_snapshot(
    state: ContainerState,
    registry: IntegrationServiceRegistry,
) -> ApplicationCompositionSnapshot:
    """Build a deterministic allowlisted snapshot of *registry*.

    Side-effect free: no bound implementation is constructed, called, inspected
    or otherwise executed.
    """

    services = tuple(
        ServiceInspection(
            service_id=binding.descriptor.service_id,
            implementation_id=binding.descriptor.implementation_id,
            contract_name=binding.descriptor.contract.contract_name,
            contract_version=binding.descriptor.contract.contract_version,
            schema_version=binding.descriptor.contract.schema_version,
            owner=binding.descriptor.contract.owner,
            dependency_ids=tuple(
                dependency.service_id for dependency in binding.descriptor.dependencies
            ),
            mode=binding.descriptor.mode,
            authority=binding.descriptor.authority,
        )
        for binding in registry.list_bindings()
    )

    return ApplicationCompositionSnapshot(state=state, services=services)


__all__ = [
    "ApplicationCompositionSnapshot",
    "ServiceInspection",
    "build_composition_snapshot",
]
