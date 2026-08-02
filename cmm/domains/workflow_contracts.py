from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.agent_security_enums import SensitivityLevel
from cmm.domains.workflow_errors import DomainWorkflowValidationError
from cmm.workflows.contracts import WorkflowDefinition, WorkflowNode, WorkflowRun
from cmm.workflows.enums import WorkflowAvailabilityStatus


@dataclass(frozen=True, slots=True)
class DomainWorkflowDefinition:
    workflow_id: str
    domain_id: str
    version: str
    name: str
    description: str = ""
    nodes: tuple[WorkflowNode, ...] = ()
    input_schema: Mapping[str, Any] = field(default_factory=dict)
    output_schema: Mapping[str, Any] = field(default_factory=dict)
    required_permissions: tuple[str, ...] = ()
    required_resources: tuple[str, ...] = ()
    supporting_domain_ids: tuple[str, ...] = ()
    enabled: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)
    completion_criteria: Mapping[str, Any] = field(default_factory=dict)
    approval_gates: tuple[str, ...] = ()
    purpose: str | None = None
    sensitivity: SensitivityLevel | None = None

    def __post_init__(self) -> None:
        if not self.workflow_id or not self.domain_id.startswith("domain:"):
            raise DomainWorkflowValidationError("workflow_id and canonical domain_id are required")
        if not self.nodes:
            raise DomainWorkflowValidationError("domain workflow requires nodes")
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(self, "required_permissions", tuple(self.required_permissions))
        object.__setattr__(self, "required_resources", tuple(self.required_resources))
        object.__setattr__(self, "supporting_domain_ids", tuple(self.supporting_domain_ids))
        object.__setattr__(self, "input_schema", MappingProxyType(dict(self.input_schema)))
        object.__setattr__(self, "output_schema", MappingProxyType(dict(self.output_schema)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        object.__setattr__(self, "completion_criteria", MappingProxyType(dict(self.completion_criteria)))
        object.__setattr__(self, "approval_gates", tuple(self.approval_gates))
        if self.purpose is not None and (
            not isinstance(self.purpose, str) or not self.purpose.strip()
        ):
            raise DomainWorkflowValidationError("purpose must be non-empty or None")
        object.__setattr__(
            self, "purpose", None if self.purpose is None else self.purpose.strip()
        )
        try:
            sensitivity = (
                None
                if self.sensitivity is None
                else SensitivityLevel(self.sensitivity)
            )
        except (TypeError, ValueError) as exc:
            raise DomainWorkflowValidationError("invalid workflow sensitivity") from exc
        object.__setattr__(self, "sensitivity", sensitivity)

    def to_common(self) -> WorkflowDefinition:
        return WorkflowDefinition(self.workflow_id, self.version, self.name, self.description, self.nodes, self.enabled, self.metadata, self.completion_criteria)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "domain_id": self.domain_id,
            "version": self.version,
            "name": self.name,
            "description": self.description,
            "nodes": [node.to_dict() for node in self.nodes],
            "input_schema": dict(self.input_schema),
            "output_schema": dict(self.output_schema),
            "required_permissions": list(self.required_permissions),
            "required_resources": list(self.required_resources),
            "supporting_domain_ids": list(self.supporting_domain_ids),
            "enabled": self.enabled,
            "metadata": dict(self.metadata),
            "completion_criteria": dict(self.completion_criteria),
            "approval_gates": list(self.approval_gates),
            "purpose": self.purpose,
            "sensitivity": self.sensitivity.value if self.sensitivity is not None else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainWorkflowDefinition:
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise DomainWorkflowValidationError(
                f"unknown workflow definition fields: {sorted(unknown)}"
            )
        values = dict(data)
        values["nodes"] = tuple(
            WorkflowNode.from_dict(item) for item in values.get("nodes", ())
        )
        return cls(**values)


@dataclass(frozen=True, slots=True)
class DomainWorkflowContext:
    primary_domain_id: str
    supporting_domain_ids: tuple[str, ...] = ()
    available_permissions: frozenset[str] = frozenset()
    denied_permissions: frozenset[str] = frozenset()
    available_resources: frozenset[str] = frozenset()
    available_operations: frozenset[str] = frozenset()
    approved_gates: frozenset[str] = frozenset()
    known_domain_ids: frozenset[str] = frozenset()
    authorized_domain_ids: frozenset[str] = frozenset()
    operation_domain_ids: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DomainWorkflowResolution:
    workflow_id: str
    workflow_version: str
    domain_id: str
    status: WorkflowAvailabilityStatus
    reasons: tuple[str, ...] = ()
    unavailable_nodes: tuple[str, ...] = ()
    missing_permissions: tuple[str, ...] = ()
    denied_permissions: tuple[str, ...] = ()
    missing_resources: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DomainWorkflowRun:
    common_run: WorkflowRun
    primary_domain_id: str
    provenance: Mapping[str, Any] = field(default_factory=dict)
    execution_result: Any = None

    @property
    def status(self):
        return self.common_run.status


@dataclass(frozen=True, slots=True)
class DomainWorkflowResult:
    common_result: Any
    domain_id: str
    provenance: Mapping[str, Any] = field(default_factory=dict)

    @property
    def status(self):
        return self.common_result.run.status

    @property
    def run_id(self) -> str:
        return self.common_result.run.run_id

    def to_dict(self) -> dict[str, Any]:
        return {"common_result": self.common_result.to_dict(), "domain_id": self.domain_id, "provenance": dict(self.provenance)}
