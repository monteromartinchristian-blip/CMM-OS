"""Phase 10.42 — Domain-owned planner/workflow coordination boundary.

DP-042 — Domain-specialized Planner and Workflow Engine integration.

Coordination only. All stateful owners (resolver, composer, registries,
planning service, workflow executor) are received by dependency injection;
this boundary owns no planner, engine, runtime, store, registry, permission,
approval, validation, event, checkpoint, persistence, or state infrastructure.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from typing import Any

from cmm.agent_runtime.enums import WorkflowPlanChangeReason
from cmm.agent_runtime.workflow_planner_adapter import AgentPlanningService
from cmm.agent_runtime.workflow_planner_contracts import (
    AgentPlanningRequest,
    AgentWorkflowPlan,
)
from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.composition_contracts import DomainComposition
from cmm.domains.enums import DomainResolutionStatus
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainResolutionBlockedError,
)
from cmm.domains.planner_workflow_integration_contracts import (
    DomainPlannerWorkflowIntegrationRequest,
    DomainPlannerWorkflowIntegrationResult,
    DomainPlanningCapabilityView,
)
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resolver_contracts import DomainResolutionResult
from cmm.domains.workflow_contracts import DomainWorkflowContext, DomainWorkflowResult
from cmm.domains.workflow_errors import DomainWorkflowRegistryError
from cmm.domains.workflow_execution import DomainWorkflowExecutor
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.workflows.errors import WorkflowRegistryError


def _require_dependency(dependency: object, name: str, method: str) -> None:
    if dependency is None or not callable(getattr(dependency, method, None)):
        raise DomainContractValidationError(
            f"{name} must provide a callable {method}(...) method",
            field=name,
        )


def _planned_operation_violation(
    *,
    plan: AgentWorkflowPlan,
    prepared: AgentPlanningRequest,
    capability_view: DomainPlanningCapabilityView,
) -> str | None:
    """Detect Domain-governed operation violations in a canonical plan.

    Only operations naming a known Domain capability are Domain-governed:
    generic Phase 9 operations remain Phase 9's own business. Prohibitions
    bind every planned operation; the allowlist binds Domain-governed ones.
    """
    prohibited = set(prepared.prohibited_operations)
    allowed = set(prepared.allowed_operations)
    known_domain_operations = set(capability_view.available_operation_ids) | set(
        capability_view.prohibited_operation_ids
    )
    for operation in plan.operations:
        if operation.operation_name in prohibited:
            return "domain_prohibited_operation_planned"
        if (
            allowed
            and operation.operation_name in known_domain_operations
            and operation.operation_name not in allowed
        ):
            return "domain_operation_not_permitted"
    return None


def _clean_ids(value: Any, field_name: str) -> tuple[str, ...]:
    """Validate an injected ID collection and normalize it deterministically."""
    if isinstance(value, (str, bytes)) or not isinstance(value, Collection):
        raise DomainContractValidationError(
            f"{field_name} must be a collection of strings", field=field_name
        )
    cleaned = tuple(
        item.strip() for item in value if isinstance(item, str) and item.strip()
    )
    if len(cleaned) != len(tuple(value)):
        raise DomainContractValidationError(
            f"{field_name} must contain only non-blank strings", field=field_name
        )
    return tuple(sorted(set(cleaned)))


def _build_capability_view(
    *,
    resolution: DomainResolutionResult,
    composition: DomainComposition,
    domain_registry: DomainRegistry,
    workflow_registry: InMemoryDomainWorkflowRegistry,
    operation_availability: Callable[[str, str], bool],
    effective_permission_ids: Collection[str],
    prohibited_operation_ids: Collection[str],
    required_approval_ids: Collection[str],
    required_validation_ids: Collection[str],
    authority_reference_ids: Collection[str],
) -> DomainPlanningCapabilityView:
    """Project the current read-only Domain planning capability view.

    Sources are canonical only: resolution/composition identity, Domain
    registry listings, active workflow registry authority, the injected
    operation-availability answer, injected permission/prohibition sets, and
    injected approval/validation/authority declarations. Nothing is inferred
    from free text; registration is never treated as authorization.

    Per-operation availability (enabled implementation, resources, current
    permission state) is answered by the injected ``operation_availability``
    callable, which the owner wires to the canonical operation and permission
    infrastructure. Per-workflow permission filtering uses the workflow
    definitions visible through the workflow registry.
    """
    if type(resolution) is not DomainResolutionResult:
        raise DomainContractValidationError(
            "resolution must be a DomainResolutionResult", field="resolution"
        )
    if type(composition) is not DomainComposition:
        raise DomainContractValidationError(
            "composition must be a DomainComposition", field="composition"
        )
    if composition.resolution_id != resolution.id:
        raise DomainContractValidationError(
            "composition.resolution_id must match resolution.id",
            field="composition",
        )
    if resolution.primary_domain is None:
        raise DomainContractValidationError(
            "resolution must have a primary domain", field="resolution"
        )
    primary_domain_id = str(resolution.primary_domain)
    if str(composition.primary_domain) != primary_domain_id:
        raise DomainContractValidationError(
            "composition primary domain must match resolution primary domain",
            field="composition",
        )
    if not callable(operation_availability):
        raise DomainContractValidationError(
            "operation_availability must be callable", field="operation_availability"
        )

    supporting_domain_ids = tuple(str(item) for item in composition.supporting_domains)
    effective_domains = (primary_domain_id, *supporting_domain_ids)

    effective_permissions = set(
        _clean_ids(effective_permission_ids, "effective_permission_ids")
    )
    prohibited = set(_clean_ids(prohibited_operation_ids, "prohibited_operation_ids"))

    available_operations: set[str] = set()
    operation_dependency_rows: dict[str, tuple[str, ...]] = {}
    for domain_id in effective_domains:
        # Canonical listing only: unlisted operations are never exposed.
        listed = domain_registry.list_operations(domain_id)
        definition = domain_registry.get_required(domain_id)
        declared_deps = tuple(
            sorted(
                {
                    str(dep.domain_id)
                    for dep in (
                        *definition.dependencies,
                        *definition.optional_dependencies,
                    )
                }
            )
        )
        if declared_deps:
            # DomainOperationDefinition declares no per-operation edges, so
            # rows are keyed by owning domain to preserve provenance without
            # inventing per-operation dependencies.
            operation_dependency_rows[domain_id] = declared_deps
        for operation_id in listed:
            if operation_id in prohibited:
                continue
            if not operation_availability(operation_id, domain_id):
                continue
            available_operations.add(operation_id)

    available_workflows: set[str] = set()
    workflow_dependency_rows: dict[str, tuple[str, ...]] = {}
    workflow_approval_gates: set[str] = set()
    for domain_id in effective_domains:
        for workflow_id in domain_registry.list_workflows(domain_id):
            try:
                workflow = workflow_registry.resolve_active(workflow_id)
            except (WorkflowRegistryError, DomainWorkflowRegistryError, KeyError):
                # Declared but not resolvable: excluded, never fabricated.
                continue
            if any(
                permission not in effective_permissions
                for permission in workflow.required_permissions
            ):
                continue
            available_workflows.add(workflow_id)
            node_deps = tuple(
                sorted(
                    {
                        dependency
                        for node in workflow.nodes
                        for dependency in node.dependencies
                    }
                )
            )
            if node_deps:
                workflow_dependency_rows[workflow_id] = node_deps
            workflow_approval_gates.update(workflow.approval_gates)

    required_approvals = tuple(
        sorted(
            set(_clean_ids(required_approval_ids, "required_approval_ids"))
            | workflow_approval_gates
        )
    )
    blocking_conflicts = tuple(
        sorted(
            {
                conflict.code
                for conflict in composition.conflicts
                if conflict.blocking and not conflict.resolved
            }
        )
    )

    return DomainPlanningCapabilityView(
        primary_domain_id=primary_domain_id,
        supporting_domain_ids=supporting_domain_ids,
        available_operation_ids=tuple(sorted(available_operations)),
        prohibited_operation_ids=tuple(sorted(prohibited)),
        available_workflow_ids=tuple(sorted(available_workflows)),
        operation_dependency_ids=tuple(sorted(operation_dependency_rows.items())),
        workflow_dependency_ids=tuple(sorted(workflow_dependency_rows.items())),
        required_permission_ids=tuple(sorted(effective_permissions)),
        required_approval_ids=required_approvals,
        required_validation_ids=_clean_ids(
            required_validation_ids, "required_validation_ids"
        ),
        cross_domain_constraint_ids=blocking_conflicts,
        authority_reference_ids=_clean_ids(
            authority_reference_ids, "authority_reference_ids"
        ),
        metadata={
            "resolution_id": resolution.id,
            "composition_id": composition.id,
        },
    )


def _stable_union(first: Collection[str], second: Collection[str]) -> list[str]:
    """Union preserving first-seen order across both collections."""
    ordered: list[str] = []
    seen: set[str] = set()
    for item in (*tuple(first), *tuple(second)):
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _prepare_planning_request(
    *,
    incoming: AgentPlanningRequest,
    capability_view: DomainPlanningCapabilityView,
    selected_workflow_ids: Collection[str] = (),
) -> AgentPlanningRequest:
    """Compose the most-restrictive canonical planning request.

    The incoming request is never mutated. Domain specialization only narrows:
    allowed operations intersect, prohibitions/approvals/validations union,
    permissions intersect (never added), autonomy and budget are preserved
    exactly (the capability view carries no Domain budget/autonomy ceilings,
    so a missing Domain value invents no higher default and nothing may
    increase). The generic ``workflow_references`` metadata key carries only
    selected workflow IDs — never definitions, registries, or state.
    """
    if type(incoming) is not AgentPlanningRequest:
        raise DomainContractValidationError(
            "incoming must be an AgentPlanningRequest", field="incoming"
        )
    if type(capability_view) is not DomainPlanningCapabilityView:
        raise DomainContractValidationError(
            "capability_view must be a DomainPlanningCapabilityView",
            field="capability_view",
        )
    selected = _clean_ids(selected_workflow_ids, "selected_workflow_ids")
    available_workflows = set(capability_view.available_workflow_ids)
    for workflow_id in selected:
        if workflow_id not in available_workflows:
            raise DomainContractValidationError(
                f"selected workflow {workflow_id!r} is not an available Domain workflow",
                field="selected_workflow_ids",
            )

    available_operations = set(capability_view.available_operation_ids)
    if incoming.allowed_operations:
        allowed = [
            operation
            for operation in incoming.allowed_operations
            if operation in available_operations
        ]
    else:
        allowed = sorted(available_operations)

    prohibited = _stable_union(
        incoming.prohibited_operations, capability_view.prohibited_operation_ids
    )
    approvals = _stable_union(
        incoming.required_approvals, capability_view.required_approval_ids
    )
    validations = _stable_union(
        incoming.required_validations, capability_view.required_validation_ids
    )

    domain_permissions = set(capability_view.required_permission_ids)
    permissions = [
        permission
        for permission in incoming.permissions
        if permission in domain_permissions
    ]

    metadata = dict(incoming.metadata)
    if selected:
        metadata["workflow_references"] = selected

    data = incoming.to_dict()
    data["allowed_operations"] = allowed
    data["prohibited_operations"] = prohibited
    data["required_approvals"] = approvals
    data["required_validations"] = validations
    data["permissions"] = permissions
    data["metadata"] = metadata
    return AgentPlanningRequest.from_dict(data)


class DefaultDomainPlannerWorkflowIntegrator:
    """Prepare, constrain, invoke, observe, and bind the canonical planner.

    Coordination only: resolution, composition, registries, planning, and
    workflow execution remain owned by the injected canonical collaborators.
    """

    def __init__(
        self,
        *,
        resolver: DefaultDomainResolver,
        composer: DefaultDomainComposer,
        domain_registry: DomainRegistry,
        workflow_registry: InMemoryDomainWorkflowRegistry,
        planning_service: AgentPlanningService,
        workflow_executor: DomainWorkflowExecutor,
        operation_availability: Callable[[str, str], bool],
        permission_ids_provider: Callable[[DomainComposition], Collection[str]],
        prohibited_operation_ids_provider: Callable[
            [DomainComposition], Collection[str]
        ],
        approval_ids_provider: Callable[[DomainComposition], Collection[str]],
        validation_ids_provider: Callable[[DomainComposition], Collection[str]],
        authority_reference_ids_provider: Callable[
            [DomainComposition], Collection[str]
        ],
    ) -> None:
        _require_dependency(resolver, "resolver", "resolve")
        _require_dependency(composer, "composer", "compose")
        _require_dependency(planning_service, "planning_service", "plan")
        _require_dependency(workflow_executor, "workflow_executor", "execute_result")
        if type(domain_registry) is not DomainRegistry:
            raise DomainContractValidationError(
                "domain_registry must be a DomainRegistry",
                field="domain_registry",
            )
        if type(workflow_registry) is not InMemoryDomainWorkflowRegistry:
            raise DomainContractValidationError(
                "workflow_registry must be an InMemoryDomainWorkflowRegistry",
                field="workflow_registry",
            )
        if not callable(operation_availability):
            raise DomainContractValidationError(
                "operation_availability must be callable",
                field="operation_availability",
            )
        for name, provider in (
            ("permission_ids_provider", permission_ids_provider),
            ("prohibited_operation_ids_provider", prohibited_operation_ids_provider),
            ("approval_ids_provider", approval_ids_provider),
            ("validation_ids_provider", validation_ids_provider),
            ("authority_reference_ids_provider", authority_reference_ids_provider),
        ):
            if not callable(provider):
                raise DomainContractValidationError(
                    f"{name} must be callable", field=name
                )
        self._resolver = resolver
        self._composer = composer
        self._domain_registry = domain_registry
        self._workflow_registry = workflow_registry
        self._planning_service = planning_service
        self._workflow_executor = workflow_executor
        self._operation_availability = operation_availability
        self._permission_ids_provider = permission_ids_provider
        self._prohibited_operation_ids_provider = prohibited_operation_ids_provider
        self._approval_ids_provider = approval_ids_provider
        self._validation_ids_provider = validation_ids_provider
        self._authority_reference_ids_provider = authority_reference_ids_provider

    def integrate(
        self,
        request: DomainPlannerWorkflowIntegrationRequest,
    ) -> DomainPlannerWorkflowIntegrationResult:
        """Project current capabilities and plan through the canonical planner."""
        if type(request) is not DomainPlannerWorkflowIntegrationRequest:
            raise DomainContractValidationError(
                "request must be a DomainPlannerWorkflowIntegrationRequest",
                field="request",
            )
        resolution = self._resolver.resolve(request.resolution_context)
        if resolution.status is not DomainResolutionStatus.RESOLVED:
            raise DomainResolutionBlockedError(
                "Domain resolution does not permit planner integration",
                details={
                    "resolution_status": resolution.status.value,
                    "resolution_id": resolution.id,
                },
            )
        composition = self._compose(resolution)
        identity_conflict = self._identity_conflict(request)
        blocking_conflicts = tuple(
            conflict
            for conflict in composition.conflicts
            if conflict.blocking and not conflict.resolved
        )
        view = _build_capability_view(
            resolution=resolution,
            composition=composition,
            domain_registry=self._domain_registry,
            workflow_registry=self._workflow_registry,
            operation_availability=self._operation_availability,
            effective_permission_ids=self._permission_ids_provider(composition),
            prohibited_operation_ids=self._prohibited_operation_ids_provider(
                composition
            ),
            required_approval_ids=self._approval_ids_provider(composition),
            required_validation_ids=self._validation_ids_provider(composition),
            authority_reference_ids=self._authority_reference_ids_provider(composition),
        )
        if identity_conflict is not None:
            return self._blocked(
                request=request,
                resolution=resolution,
                composition=composition,
                view=view,
                prepared=_prepare_planning_request(
                    incoming=request.planning_request, capability_view=view
                ),
                reason_codes=(identity_conflict,),
            )
        if blocking_conflicts:
            return self._blocked(
                request=request,
                resolution=resolution,
                composition=composition,
                view=view,
                prepared=_prepare_planning_request(
                    incoming=request.planning_request, capability_view=view
                ),
                reason_codes=(
                    "domain_composition_blocked",
                    *(conflict.code for conflict in blocking_conflicts),
                ),
            )
        selected = self._select_workflows(request, view)
        if selected is None:
            return self._blocked(
                request=request,
                resolution=resolution,
                composition=composition,
                view=view,
                prepared=_prepare_planning_request(
                    incoming=request.planning_request, capability_view=view
                ),
                reason_codes=("domain_workflow_unavailable",),
            )
        prepared = _prepare_planning_request(
            incoming=request.planning_request,
            capability_view=view,
            selected_workflow_ids=selected,
        )
        if (
            request.planning_request.allowed_operations
            and not prepared.allowed_operations
        ):
            return self._blocked(
                request=request,
                resolution=resolution,
                composition=composition,
                view=view,
                prepared=prepared,
                selected=selected,
                reason_codes=("domain_no_permitted_operations",),
            )
        if (
            view.required_permission_ids
            and request.planning_request.permissions
            and not prepared.permissions
        ):
            return self._blocked(
                request=request,
                resolution=resolution,
                composition=composition,
                view=view,
                prepared=prepared,
                selected=selected,
                reason_codes=("domain_permission_unsatisfiable",),
            )
        plan = self._planning_service.plan(prepared)
        if type(plan) is not AgentWorkflowPlan:
            raise DomainContractValidationError(
                "planning service must return an AgentWorkflowPlan",
                field="plan",
            )
        violation = _planned_operation_violation(
            plan=plan, prepared=prepared, capability_view=view
        )
        if violation is not None:
            return self._blocked(
                request=request,
                resolution=resolution,
                composition=composition,
                view=view,
                prepared=prepared,
                selected=selected,
                plan=plan,
                reason_codes=(violation,),
            )
        plan_references = plan.metadata.get("workflow_references", ())
        if isinstance(plan_references, (str, bytes)):
            unexpected = True
        else:
            try:
                unexpected = any(
                    reference not in set(selected) for reference in plan_references
                )
            except TypeError:
                unexpected = True
        if unexpected:
            return self._blocked(
                request=request,
                resolution=resolution,
                composition=composition,
                view=view,
                prepared=prepared,
                selected=selected,
                plan=plan,
                reason_codes=("domain_workflow_reference_unexpected",),
            )
        return DomainPlannerWorkflowIntegrationResult(
            request_id=request.request_id,
            resolution=resolution,
            composition=composition,
            capability_view=view,
            prepared_planning_request=prepared,
            plan=plan,
            selected_domain_workflow_ids=selected,
            blocked=False,
            reason_codes=(),
            metadata={},
        )

    def _compose(self, resolution: DomainResolutionResult) -> DomainComposition:
        """Compose using canonical components and registry-owned definitions."""
        domain_ids = (
            str(resolution.primary_domain),
            *(str(item) for item in resolution.supporting_domains),
        )
        definitions = [
            self._domain_registry.get_required(domain_id) for domain_id in domain_ids
        ]
        return self._composer.compose(resolution, definitions)

    @staticmethod
    def _identity_conflict(
        request: DomainPlannerWorkflowIntegrationRequest,
    ) -> str | None:
        """Detect Domain vs Phase 9 identity disagreement; None means aligned."""
        context = request.resolution_context
        planning = request.planning_request
        if context.goal_id is not None and context.goal_id != planning.goal_id:
            return "identity_conflict"
        if context.actor not in ("", "system") and context.actor != planning.actor_id:
            return "identity_conflict"
        return None

    @staticmethod
    def _select_workflows(
        request: DomainPlannerWorkflowIntegrationRequest,
        view: DomainPlanningCapabilityView,
    ) -> tuple[str, ...] | None:
        """Select explicitly requested workflows; None means fail closed.

        Available workflows are planning capabilities, never automatically
        selected actions: without an explicit request nothing is selected.
        """
        if "requested_workflow_ids" not in request.metadata:
            return ()
        requested_raw = request.metadata["requested_workflow_ids"]
        if isinstance(requested_raw, (str, bytes)) or not isinstance(
            requested_raw, (list, tuple)
        ):
            raise DomainContractValidationError(
                "requested_workflow_ids must be a list/tuple of non-empty strings",
                field="requested_workflow_ids",
            )
        requested = tuple(requested_raw)
        for item in requested:
            if not isinstance(item, str) or not item.strip():
                raise DomainContractValidationError(
                    "requested_workflow_ids must contain only non-empty strings",
                    field="requested_workflow_ids",
                )
        available = set(view.available_workflow_ids)
        if any(item not in available for item in requested):
            return None
        selected: list[str] = []
        for item in requested:
            if item not in selected:
                selected.append(item)
        return tuple(selected)

    @staticmethod
    def _blocked(
        *,
        request: DomainPlannerWorkflowIntegrationRequest,
        resolution: DomainResolutionResult,
        composition: DomainComposition,
        view: DomainPlanningCapabilityView,
        prepared: AgentPlanningRequest,
        selected: tuple[str, ...] = (),
        plan: AgentWorkflowPlan | None = None,
        reason_codes: tuple[str, ...],
    ) -> DomainPlannerWorkflowIntegrationResult:
        """Build a fail-closed blocked result binding canonical objects."""
        return DomainPlannerWorkflowIntegrationResult(
            request_id=request.request_id,
            resolution=resolution,
            composition=composition,
            capability_view=view,
            prepared_planning_request=prepared,
            plan=plan,
            selected_domain_workflow_ids=selected,
            blocked=True,
            reason_codes=tuple(reason_codes),
            metadata={},
        )

    def execute_workflow_reference(
        self,
        *,
        workflow_id: str,
        context: DomainWorkflowContext,
        inputs: Mapping[str, Any],
    ) -> DomainWorkflowResult:
        """Delegate a planned workflow reference to the canonical executor."""
        raise NotImplementedError

    def replan(
        self,
        request: DomainPlannerWorkflowIntegrationRequest,
        *,
        reason: WorkflowPlanChangeReason,
        reason_details: str,
    ) -> DomainPlannerWorkflowIntegrationResult:
        """Replan through the canonical ``AgentPlanningService``."""
        raise NotImplementedError


__all__ = [
    "DefaultDomainPlannerWorkflowIntegrator",
    "DomainPlanningCapabilityView",
]
