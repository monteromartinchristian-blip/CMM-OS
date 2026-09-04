"""Phase 10.42 — immutable planner/workflow integration contracts.

DP-042 — Domain-specialized Planner and Workflow Engine integration.

Value objects only. No registries, services, stores, executors, planners,
runtimes, approval/validation owners, or state machines live in this module.

The canonical ``TaskPlanner`` / ``AgentPlanningService`` remains the sole
plan owner; ``AgentWorkflowPlan`` remains the only plan contract. These
contracts only project Domain capabilities as planning constraints and bind
canonical results by reference.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from cmm.agent_runtime.enums import WorkflowPlanChangeReason
from cmm.agent_runtime.workflow_planner_contracts import (
    AgentPlanningRequest,
    AgentWorkflowPlan,
)
from cmm.domains.composition_contracts import DomainComposition
from cmm.domains.contracts import _deep_freeze
from cmm.domains.errors import DomainContractValidationError
from cmm.domains.resolution_contracts import DomainResolutionContext
from cmm.domains.resolver_contracts import DomainResolutionResult
from cmm.domains.workflow_contracts import DomainWorkflowContext, DomainWorkflowResult


def _non_blank(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DomainContractValidationError(
            f"{field_name} must be a non-empty string", field=field_name
        )
    return value.strip()


def _unique_sorted_ids(value: Any, field_name: str) -> tuple[str, ...]:
    """Validate a sequence of IDs, then normalize to a sorted duplicate-free tuple."""
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise DomainContractValidationError(
            f"{field_name} must be a sequence of strings", field=field_name
        )
    cleaned = tuple(_non_blank(item, field_name) for item in value)
    if len(set(cleaned)) != len(cleaned):
        raise DomainContractValidationError(
            f"{field_name} must not contain duplicates", field=field_name
        )
    return tuple(sorted(cleaned))


def _stable_unique_ids(value: Any, field_name: str) -> tuple[str, ...]:
    """Validate IDs and deduplicate preserving first-seen order."""
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise DomainContractValidationError(
            f"{field_name} must be a sequence of strings", field=field_name
        )
    cleaned = tuple(_non_blank(item, field_name) for item in value)
    seen: set[str] = set()
    ordered: list[str] = []
    for item in cleaned:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return tuple(ordered)


def _dependency_rows(
    value: Any, field_name: str
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Validate ``((owner_id, (dep_id, ...)), ...)`` rows and sort by owner."""
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise DomainContractValidationError(
            f"{field_name} must be a sequence of (owner, dependencies) pairs",
            field=field_name,
        )
    rows: list[tuple[str, tuple[str, ...]]] = []
    owners: set[str] = set()
    for index, row in enumerate(value):
        if (
            isinstance(row, (str, bytes))
            or not isinstance(row, Sequence)
            or len(row) != 2
        ):
            raise DomainContractValidationError(
                f"{field_name}[{index}] must be an (owner_id, dependencies) pair",
                field=field_name,
            )
        owner = _non_blank(row[0], f"{field_name}[{index}].owner_id")
        if owner in owners:
            raise DomainContractValidationError(
                f"{field_name} must not duplicate owner {owner!r}",
                field=field_name,
            )
        owners.add(owner)
        deps_raw = row[1]
        if isinstance(deps_raw, (str, bytes)) or not isinstance(deps_raw, Sequence):
            raise DomainContractValidationError(
                f"{field_name}[{index}].dependencies must be a sequence of strings",
                field=field_name,
            )
        deps = tuple(
            _non_blank(dep, f"{field_name}[{index}].dependencies") for dep in deps_raw
        )
        if len(set(deps)) != len(deps):
            raise DomainContractValidationError(
                f"{field_name}[{index}].dependencies must not contain duplicates",
                field=field_name,
            )
        rows.append((owner, tuple(sorted(deps))))
    rows.sort(key=lambda row: row[0])
    return tuple(rows)


def _check_json_safe(value: Any, field_name: str) -> None:
    """Reject metadata values that cannot be references/constraints.

    Only JSON-safe scalars and containers are allowed, so raw service,
    store, registry, or execution-state handles can never hide in metadata.
    """
    if value is None or isinstance(value, (str, bool, int)):
        if isinstance(value, float) and not math.isfinite(value):
            raise DomainContractValidationError(
                f"{field_name} must be JSON-safe and finite", field=field_name
            )
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DomainContractValidationError(
                f"{field_name} must be JSON-safe and finite", field=field_name
            )
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise DomainContractValidationError(
                    f"{field_name} keys must be strings", field=field_name
                )
            _check_json_safe(item, f"{field_name}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _check_json_safe(item, f"{field_name}[{index}]")
        return
    raise DomainContractValidationError(
        f"{field_name} must be JSON-safe (no service/store/registry handles)",
        field=field_name,
    )


def _freeze_metadata(value: Any, field_name: str) -> Any:
    if not isinstance(value, Mapping):
        raise DomainContractValidationError(
            f"{field_name} must be a mapping", field=field_name
        )
    _check_json_safe(dict(value), field_name)
    return _deep_freeze(dict(value))


def _exact_type(value: Any, expected_type: type, field_name: str) -> None:
    if type(value) is not expected_type:
        raise DomainContractValidationError(
            f"{field_name} must be a {expected_type.__name__}",
            field=field_name,
        )


def _exact_bool(value: Any, field_name: str) -> None:
    if not isinstance(value, bool):
        raise DomainContractValidationError(
            f"{field_name} must be a bool", field=field_name
        )


@dataclass(frozen=True, slots=True)
class DomainPlanningCapabilityView:
    """Immutable read-only projection of effective Domain planning capabilities.

    Advisory to planning and restrictive to execution: presence in this view
    never authorizes execution. Current authority is revalidated at every
    execution boundary.
    """

    primary_domain_id: str
    supporting_domain_ids: tuple[str, ...] = ()
    available_operation_ids: tuple[str, ...] = ()
    prohibited_operation_ids: tuple[str, ...] = ()
    available_workflow_ids: tuple[str, ...] = ()
    operation_dependency_ids: tuple[tuple[str, tuple[str, ...]], ...] = ()
    workflow_dependency_ids: tuple[tuple[str, tuple[str, ...]], ...] = ()
    required_permission_ids: tuple[str, ...] = ()
    required_approval_ids: tuple[str, ...] = ()
    required_validation_ids: tuple[str, ...] = ()
    cross_domain_constraint_ids: tuple[str, ...] = ()
    authority_reference_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "primary_domain_id",
            _non_blank(self.primary_domain_id, "primary_domain_id"),
        )
        for attr in (
            "supporting_domain_ids",
            "available_operation_ids",
            "prohibited_operation_ids",
            "available_workflow_ids",
            "required_permission_ids",
            "required_approval_ids",
            "required_validation_ids",
            "cross_domain_constraint_ids",
            "authority_reference_ids",
        ):
            object.__setattr__(
                self, attr, _unique_sorted_ids(getattr(self, attr), attr)
            )
        object.__setattr__(
            self,
            "operation_dependency_ids",
            _dependency_rows(self.operation_dependency_ids, "operation_dependency_ids"),
        )
        object.__setattr__(
            self,
            "workflow_dependency_ids",
            _dependency_rows(self.workflow_dependency_ids, "workflow_dependency_ids"),
        )
        object.__setattr__(
            self, "metadata", _freeze_metadata(self.metadata, "metadata")
        )


@dataclass(frozen=True, slots=True)
class DomainPlannerWorkflowIntegrationRequest:
    """Immutable wrapper binding a canonical Domain context and planning request."""

    request_id: str
    resolution_context: DomainResolutionContext
    planning_request: AgentPlanningRequest
    current_plan: AgentWorkflowPlan | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _non_blank(self.request_id, "request_id")
        )
        _exact_type(
            self.resolution_context, DomainResolutionContext, "resolution_context"
        )
        _exact_type(self.planning_request, AgentPlanningRequest, "planning_request")
        if self.current_plan is not None:
            _exact_type(self.current_plan, AgentWorkflowPlan, "current_plan")
        object.__setattr__(
            self, "metadata", _freeze_metadata(self.metadata, "metadata")
        )


@dataclass(frozen=True, slots=True)
class DomainPlannerWorkflowIntegrationResult:
    """Immutable aggregate binding canonical planning results by reference."""

    request_id: str
    resolution: DomainResolutionResult
    composition: DomainComposition
    capability_view: DomainPlanningCapabilityView
    prepared_planning_request: AgentPlanningRequest
    plan: AgentWorkflowPlan | None
    selected_domain_workflow_ids: tuple[str, ...] = ()
    blocked: bool = False
    reason_codes: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _non_blank(self.request_id, "request_id")
        )
        _exact_type(self.resolution, DomainResolutionResult, "resolution")
        _exact_type(self.composition, DomainComposition, "composition")
        _exact_type(
            self.capability_view, DomainPlanningCapabilityView, "capability_view"
        )
        _exact_type(
            self.prepared_planning_request,
            AgentPlanningRequest,
            "prepared_planning_request",
        )
        if self.composition.resolution_id != self.resolution.id:
            raise DomainContractValidationError(
                "composition.resolution_id must match resolution.id",
                field="composition",
            )
        if self.plan is not None:
            _exact_type(self.plan, AgentWorkflowPlan, "plan")
        object.__setattr__(
            self,
            "selected_domain_workflow_ids",
            _stable_unique_ids(
                self.selected_domain_workflow_ids, "selected_domain_workflow_ids"
            ),
        )
        _exact_bool(self.blocked, "blocked")
        object.__setattr__(
            self, "reason_codes", _stable_unique_ids(self.reason_codes, "reason_codes")
        )
        if self.blocked and not self.reason_codes:
            raise DomainContractValidationError(
                "blocked results require at least one reason_code",
                field="reason_codes",
            )
        object.__setattr__(
            self, "metadata", _freeze_metadata(self.metadata, "metadata")
        )


@runtime_checkable
class DomainPlannerWorkflowIntegrator(Protocol):
    """Protocol for the Domain-owned planner/workflow coordination boundary."""

    def integrate(
        self,
        request: DomainPlannerWorkflowIntegrationRequest,
    ) -> DomainPlannerWorkflowIntegrationResult: ...

    def execute_workflow_reference(
        self,
        *,
        workflow_id: str,
        context: DomainWorkflowContext,
        inputs: Mapping[str, Any],
    ) -> DomainWorkflowResult: ...

    def replan(
        self,
        request: DomainPlannerWorkflowIntegrationRequest,
        *,
        reason: WorkflowPlanChangeReason,
        reason_details: str,
    ) -> DomainPlannerWorkflowIntegrationResult: ...


__all__ = [
    "DomainPlannerWorkflowIntegrationRequest",
    "DomainPlannerWorkflowIntegrationResult",
    "DomainPlannerWorkflowIntegrator",
    "DomainPlanningCapabilityView",
]
