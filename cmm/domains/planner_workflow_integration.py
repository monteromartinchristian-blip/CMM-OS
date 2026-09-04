"""Phase 10.42 — Domain-owned planner/workflow coordination boundary.

DP-042 — Domain-specialized Planner and Workflow Engine integration.

Coordination only. All stateful owners (resolver, composer, registries,
planning service, workflow executor) are received by dependency injection;
this boundary owns no planner, engine, runtime, store, registry, permission,
approval, validation, event, checkpoint, persistence, or state infrastructure.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from typing import Any

from cmm.agent_runtime.enums import WorkflowPlanChangeReason, WorkflowPlanStatus
from cmm.agent_runtime.workflow_planner_adapter import AgentPlanningService
from cmm.agent_runtime.workflow_planner_contracts import (
    AgentPlanningRequest,
    AgentReplanningRequest,
    AgentWorkflowPlan,
)
from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.composition_contracts import DomainComposition
from cmm.domains.enums import DomainResolutionStatus
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainResolutionBlockedError,
)
from cmm.domains.operation_contracts import DomainOperationDefinition
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


def _unresolved_operation_dependencies(
    *, plan: AgentWorkflowPlan
) -> tuple[tuple[str, str], ...]:
    """Extract unresolved required operation dependencies from plan metadata.

    The canonical planner records required operation-dependency pairs whose
    endpoints could not be resolved to planned nodes here instead of
    silently dropping them. Any entry means the plan was built with a
    missing blocking prerequisite.
    """
    raw = plan.metadata.get("unresolved_operation_dependencies", ())
    if isinstance(raw, (str, bytes)):
        return ()
    try:
        pairs = tuple(raw)
    except TypeError:
        return ()
    cleaned: list[tuple[str, str]] = []
    for pair in pairs:
        if isinstance(pair, (str, bytes)):
            continue
        try:
            endpoints = tuple(pair)
        except TypeError:
            continue
        if len(endpoints) != 2:
            continue
        upstream, downstream = endpoints
        if not isinstance(upstream, str) or not isinstance(downstream, str):
            continue
        if (upstream, downstream) not in cleaned:
            cleaned.append((upstream, downstream))
    return tuple(cleaned)


def _planned_operation_violation(
    *,
    plan: AgentWorkflowPlan,
    prepared: AgentPlanningRequest,
    capability_view: DomainPlanningCapabilityView,
) -> str | None:
    """Detect Domain-governed operation violations in a canonical plan.

    Prohibitions bind every planned operation. When the prepared allowlist is
    non-empty it binds every planned operation unconditionally: an operation
    that is declared-but-unavailable (hence absent from both the available and
    prohibited capability sets) must still be rejected instead of bypassing
    the Phase 10.42 post-plan check.
    """
    prohibited = set(prepared.prohibited_operations)
    allowed = set(prepared.allowed_operations)
    for operation in plan.operations:
        if operation.operation_name in prohibited:
            return "domain_prohibited_operation_planned"
        if allowed and operation.operation_name not in allowed:
            return "domain_operation_not_permitted"
    return None


def _invalid_canonical_plan_violation(*, plan: AgentWorkflowPlan) -> str | None:
    """Detect a canonical plan already known to be invalid.

    The canonical ``AgentWorkflowPlanValidator`` marks operations outside a
    non-empty allowlist as blocking errors; the integration boundary must fail
    closed on that verdict instead of returning the invalid plan unblocked.
    """
    if plan.status is WorkflowPlanStatus.INVALID:
        return "invalid_canonical_plan"
    validation = plan.validation
    if validation is not None and not validation.is_valid:
        return "invalid_canonical_plan"
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


def _build_operation_semantics(
    *,
    capability_view: DomainPlanningCapabilityView,
    definition_provider: Callable[[str], DomainOperationDefinition | None] | None,
) -> dict[str, dict[str, Any]]:
    """Project available Domain operation definitions into generic descriptors.

    Reads canonical ``DomainOperationDefinition`` fields only and emits the
    generic ``operation_semantics`` shape consumed by the Phase 9 planning
    seam: no Domain-specific keys, no invented values. Operations unknown to
    the provider contribute nothing.
    """
    if definition_provider is None:
        return {}
    if not callable(definition_provider):
        raise DomainContractValidationError(
            "operation_definition_provider must be callable",
            field="operation_definition_provider",
        )
    semantics: dict[str, dict[str, Any]] = {}
    for operation_id in capability_view.available_operation_ids:
        definition = definition_provider(operation_id)
        if definition is None:
            continue
        if type(definition) is not DomainOperationDefinition:
            raise DomainContractValidationError(
                "operation_definition_provider must return a "
                "DomainOperationDefinition or None",
                field="operation_definition_provider",
            )
        timeout_raw = definition.metadata.get("timeout_seconds")
        if (
            isinstance(timeout_raw, bool)
            or not isinstance(timeout_raw, (int, float))
            or not timeout_raw > 0
        ):
            timeout: float | None = None
        else:
            timeout = float(timeout_raw)
        semantics[operation_id] = {
            "required_permissions": list(definition.required_permissions),
            "required_validations": (
                [definition.validation_policy_id]
                if definition.validation_policy_id
                else []
            ),
            "requires_approval": bool(definition.requires_approval),
            "approval_ids": (
                list(capability_view.required_approval_ids)
                if definition.requires_approval
                else []
            ),
            "reversible": bool(definition.reversible),
            "rollback_operation": definition.rollback_policy_id,
            "risk": definition.risk_level.value,
            "timeout_seconds": timeout,
            "metadata": {
                "domain_id": definition.domain_id,
                "operation_id": definition.operation_id,
                "operation_version": definition.version,
                "operation_type": definition.operation_type.value,
            },
        }
    return semantics


def _build_operation_dependencies(
    *,
    capability_view: DomainPlanningCapabilityView,
    dependency_provider: Callable[[str], Collection[str]] | None,
) -> list[tuple[str, str]]:
    """Project per-operation upstream dependencies as [upstream, downstream] pairs.

    The provider answers upstream operation IDs for one available operation.
    Pairs are deterministic; self-pairs are dropped. Domain-level and workflow
    rows remain projected separately as reference metadata.
    """
    if dependency_provider is None:
        return []
    if not callable(dependency_provider):
        raise DomainContractValidationError(
            "operation_dependency_provider must be callable",
            field="operation_dependency_provider",
        )
    pairs: list[tuple[str, str]] = []
    for operation_id in capability_view.available_operation_ids:
        upstream_ids = dependency_provider(operation_id)
        if isinstance(upstream_ids, (str, bytes)) or not isinstance(
            upstream_ids, Collection
        ):
            raise DomainContractValidationError(
                "operation_dependency_provider must return a collection of strings",
                field="operation_dependency_provider",
            )
        for upstream in upstream_ids:
            if not isinstance(upstream, str) or not upstream.strip():
                raise DomainContractValidationError(
                    "operation dependencies must be non-empty strings",
                    field="operation_dependency_provider",
                )
            pair = (upstream, operation_id)
            if upstream != operation_id and pair not in pairs:
                pairs.append(pair)
    pairs.sort()
    return pairs


def _stable_operation_candidates(
    capability_view: DomainPlanningCapabilityView,
) -> list[str]:
    """Project available Domain operations as generic selection candidates.

    Opaque operation IDs only, deterministic sorted order. An empty
    capability set yields an empty candidate list, which the canonical
    planner seam treats as unsatisfiable (fail closed) instead of
    inventing an operation.
    """
    return sorted(capability_view.available_operation_ids)


def _stable_operation_semantics(
    semantics: Mapping[str, Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Normalize injected per-operation semantics deterministically."""
    if semantics is None:
        return []
    if not isinstance(semantics, Mapping):
        raise DomainContractValidationError(
            "operation_semantics must be a mapping", field="operation_semantics"
        )
    rows: list[dict[str, Any]] = []
    for operation_name in sorted(semantics):
        if not isinstance(operation_name, str) or not operation_name.strip():
            raise DomainContractValidationError(
                "operation_semantics keys must be non-empty strings",
                field="operation_semantics",
            )
        entry = semantics[operation_name]
        if not isinstance(entry, Mapping):
            raise DomainContractValidationError(
                "operation_semantics entries must be mappings",
                field="operation_semantics",
            )
        row = dict(entry)
        row["operation_name"] = operation_name
        rows.append(row)
    return rows


def _stable_dependency_pairs(value: Any, field_name: str) -> list[list[str]]:
    """Normalize [upstream, downstream] pairs deterministically."""
    if value is None:
        return []
    if isinstance(value, (str, bytes)) or not isinstance(value, Collection):
        raise DomainContractValidationError(
            f"{field_name} must be a collection of pairs", field=field_name
        )
    pairs: list[tuple[str, str]] = []
    for pair in value:
        if (
            isinstance(pair, (str, bytes))
            or not isinstance(pair, (list, tuple))
            or len(tuple(pair)) != 2
        ):
            raise DomainContractValidationError(
                f"{field_name} must contain [upstream, downstream] pairs",
                field=field_name,
            )
        upstream, downstream = tuple(pair)
        for endpoint in (upstream, downstream):
            if not isinstance(endpoint, str) or not endpoint.strip():
                raise DomainContractValidationError(
                    f"{field_name} endpoints must be non-empty strings",
                    field=field_name,
                )
        if (upstream, downstream) not in pairs:
            pairs.append((upstream, downstream))
    pairs.sort()
    return [[upstream, downstream] for upstream, downstream in pairs]


def _prepare_planning_request(
    *,
    incoming: AgentPlanningRequest,
    capability_view: DomainPlanningCapabilityView,
    selected_workflow_ids: Collection[str] = (),
    operation_semantics: Mapping[str, Mapping[str, Any]] | None = None,
    operation_dependencies: Collection[Any] | None = None,
) -> AgentPlanningRequest:
    """Compose the most-restrictive canonical planning request.

    The incoming request is never mutated. Domain specialization only narrows:
    allowed operations intersect, prohibitions/approvals/validations union,
    permissions intersect (never added), autonomy and budget are preserved
    exactly (the capability view carries no Domain budget/autonomy ceilings,
    so a missing Domain value invents no higher default and nothing may
    increase). The generic ``workflow_references`` metadata key carries only
    selected workflow IDs — never definitions, registries, or state. Exact
    per-operation semantics and dependency references travel through the
    generic ``operation_semantics`` / ``dependency_references`` metadata
    seams, which the canonical planner validates and projects into the plan.
    The eligible Domain operation IDs additionally travel through the generic
    ``operation_candidates`` metadata seam, from which the canonical planner
    deterministically selects planned operations; an empty eligible set is
    carried as an empty candidate list and fails closed downstream.
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
    operation_candidates = _stable_operation_candidates(capability_view)
    metadata["operation_candidates"] = operation_candidates
    semantics_rows = _stable_operation_semantics(operation_semantics)
    if semantics_rows:
        metadata["operation_semantics"] = semantics_rows
    operation_pairs = _stable_dependency_pairs(
        operation_dependencies, "operation_dependencies"
    )
    workflow_references = {
        owner: list(deps) for owner, deps in capability_view.workflow_dependency_ids
    }
    domain_pairs = [
        [owner, dependency]
        for owner, deps in capability_view.operation_dependency_ids
        for dependency in deps
    ]
    domain_pairs.sort()
    if operation_pairs or workflow_references or domain_pairs:
        metadata["dependency_references"] = {
            "operation_dependencies": operation_pairs,
            "workflow_dependencies": workflow_references,
            "domain_dependencies": domain_pairs,
        }

    data = incoming.to_dict()
    data["allowed_operations"] = allowed
    data["prohibited_operations"] = prohibited
    data["required_approvals"] = approvals
    data["required_validations"] = validations
    data["permissions"] = permissions
    data["metadata"] = metadata
    return AgentPlanningRequest.from_dict(data)


@dataclass(frozen=True, slots=True)
class _PlanningAttempt:
    """Ephemeral immutable bundle for one resolve/compose/constrain pass."""

    resolution: DomainResolutionResult
    composition: DomainComposition
    view: DomainPlanningCapabilityView
    prepared: AgentPlanningRequest
    selected: tuple[str, ...]


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
        operation_definition_provider: (
            Callable[[str], DomainOperationDefinition | None] | None
        ) = None,
        operation_dependency_provider: (Callable[[str], Collection[str]] | None) = None,
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
        for name, provider in (
            ("operation_definition_provider", operation_definition_provider),
            ("operation_dependency_provider", operation_dependency_provider),
        ):
            if provider is not None and not callable(provider):
                raise DomainContractValidationError(
                    f"{name} must be callable or None", field=name
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
        self._operation_definition_provider = operation_definition_provider
        self._operation_dependency_provider = operation_dependency_provider

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
        attempt = self._prepare_attempt(request)
        if isinstance(attempt, DomainPlannerWorkflowIntegrationResult):
            return attempt
        plan = self._planning_service.plan(attempt.prepared)
        if type(plan) is not AgentWorkflowPlan:
            raise DomainContractValidationError(
                "planning service must return an AgentWorkflowPlan",
                field="plan",
            )
        return self._finish(request=request, attempt=attempt, plan=plan)

    def replan(
        self,
        request: DomainPlannerWorkflowIntegrationRequest,
        *,
        reason: WorkflowPlanChangeReason,
        reason_details: str,
    ) -> DomainPlannerWorkflowIntegrationResult:
        """Replan through the canonical ``AgentPlanningService``.

        Sequence: current plan required → resolve/compose Domains again →
        rebuild the current capability view → fresh most-restrictive planning
        request → ``AgentReplanningRequest`` → ``AgentPlanningService.replan``
        → canonical new plan. The plan store is never written directly.
        """
        if type(request) is not DomainPlannerWorkflowIntegrationRequest:
            raise DomainContractValidationError(
                "request must be a DomainPlannerWorkflowIntegrationRequest",
                field="request",
            )
        if request.current_plan is None:
            raise DomainContractValidationError(
                "replan requires the current plan bound on the request",
                field="current_plan",
            )
        if not isinstance(reason, WorkflowPlanChangeReason):
            raise DomainContractValidationError(
                "reason must be a WorkflowPlanChangeReason", field="reason"
            )
        if not isinstance(reason_details, str):
            raise DomainContractValidationError(
                "reason_details must be a string", field="reason_details"
            )
        if not callable(getattr(self._planning_service, "replan", None)):
            raise DomainContractValidationError(
                "planning_service must provide a callable replan(...) method",
                field="planning_service",
            )
        attempt = self._prepare_attempt(request)
        if isinstance(attempt, DomainPlannerWorkflowIntegrationResult):
            return attempt
        outcome = self._planning_service.replan(
            AgentReplanningRequest(
                id=f"{request.request_id}:replan",
                plan_id=request.current_plan.id,
                reason=reason,
                reason_details=reason_details,
                planning_request=attempt.prepared,
            )
        )
        new_plan = outcome.new_plan
        if type(new_plan) is not AgentWorkflowPlan:
            raise DomainContractValidationError(
                "planning service must return an AgentWorkflowPlan",
                field="plan",
            )
        return self._finish(request=request, attempt=attempt, plan=new_plan)

    def _prepare_attempt(
        self, request: DomainPlannerWorkflowIntegrationRequest
    ) -> _PlanningAttempt | DomainPlannerWorkflowIntegrationResult:
        """Resolve, compose, project, and constrain; or fail closed."""
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
        operation_semantics = _build_operation_semantics(
            capability_view=view,
            definition_provider=self._operation_definition_provider,
        )
        operation_dependencies = _build_operation_dependencies(
            capability_view=view,
            dependency_provider=self._operation_dependency_provider,
        )
        if identity_conflict is not None:
            return self._blocked(
                request=request,
                resolution=resolution,
                composition=composition,
                view=view,
                prepared=_prepare_planning_request(
                    incoming=request.planning_request,
                    capability_view=view,
                    operation_semantics=operation_semantics,
                    operation_dependencies=operation_dependencies,
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
                    incoming=request.planning_request,
                    capability_view=view,
                    operation_semantics=operation_semantics,
                    operation_dependencies=operation_dependencies,
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
                    incoming=request.planning_request,
                    capability_view=view,
                    operation_semantics=operation_semantics,
                    operation_dependencies=operation_dependencies,
                ),
                reason_codes=("domain_workflow_unavailable",),
            )
        prepared = _prepare_planning_request(
            incoming=request.planning_request,
            capability_view=view,
            selected_workflow_ids=selected,
            operation_semantics=operation_semantics,
            operation_dependencies=operation_dependencies,
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
        if not prepared.metadata.get("operation_candidates", ["_sentinel"]):
            # Empty eligible operation set: no candidate can satisfy a
            # planned step. Fail closed before invoking the planner instead
            # of letting it invent an unrelated operation.
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
        return _PlanningAttempt(
            resolution=resolution,
            composition=composition,
            view=view,
            prepared=prepared,
            selected=selected,
        )

    def _finish(
        self,
        *,
        request: DomainPlannerWorkflowIntegrationRequest,
        attempt: _PlanningAttempt,
        plan: AgentWorkflowPlan,
    ) -> DomainPlannerWorkflowIntegrationResult:
        """Apply post-planning checks and bind the canonical result."""
        if _unresolved_operation_dependencies(plan=plan):
            return self._blocked(
                request=request,
                resolution=attempt.resolution,
                composition=attempt.composition,
                view=attempt.view,
                prepared=attempt.prepared,
                selected=attempt.selected,
                plan=plan,
                reason_codes=("domain_unresolved_operation_dependency",),
            )
        violation = _planned_operation_violation(
            plan=plan, prepared=attempt.prepared, capability_view=attempt.view
        )
        if violation is not None:
            return self._blocked(
                request=request,
                resolution=attempt.resolution,
                composition=attempt.composition,
                view=attempt.view,
                prepared=attempt.prepared,
                selected=attempt.selected,
                plan=plan,
                reason_codes=(violation,),
            )
        invalid = _invalid_canonical_plan_violation(plan=plan)
        if invalid is not None:
            return self._blocked(
                request=request,
                resolution=attempt.resolution,
                composition=attempt.composition,
                view=attempt.view,
                prepared=attempt.prepared,
                selected=attempt.selected,
                plan=plan,
                reason_codes=(invalid,),
            )
        plan_references = plan.metadata.get("workflow_references", ())
        if isinstance(plan_references, (str, bytes)):
            unexpected = True
        else:
            try:
                unexpected = any(
                    reference not in set(attempt.selected)
                    for reference in plan_references
                )
            except TypeError:
                unexpected = True
        if unexpected:
            return self._blocked(
                request=request,
                resolution=attempt.resolution,
                composition=attempt.composition,
                view=attempt.view,
                prepared=attempt.prepared,
                selected=attempt.selected,
                plan=plan,
                reason_codes=("domain_workflow_reference_unexpected",),
            )
        return DomainPlannerWorkflowIntegrationResult(
            request_id=request.request_id,
            resolution=attempt.resolution,
            composition=attempt.composition,
            capability_view=attempt.view,
            prepared_planning_request=attempt.prepared,
            plan=plan,
            selected_domain_workflow_ids=attempt.selected,
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
        """Delegate a planned workflow reference to the canonical executor.

        Path: ``InMemoryDomainWorkflowRegistry.resolve_active(...)`` →
        ``DomainWorkflowExecutor.execute_result(...)`` → shared
        ``WorkflowEngine``. No ``_revalidate_workflow_authority`` duplication:
        the executor already evaluates current permission/dependency gates at
        this boundary.
        """
        if not isinstance(workflow_id, str) or not workflow_id.strip():
            raise DomainContractValidationError(
                "workflow_id must be a non-empty string", field="workflow_id"
            )
        if type(context) is not DomainWorkflowContext:
            raise DomainContractValidationError(
                "context must be a DomainWorkflowContext", field="context"
            )
        if not isinstance(inputs, Mapping):
            raise DomainContractValidationError(
                "inputs must be a mapping", field="inputs"
            )
        definition = self._workflow_registry.resolve_active(workflow_id)
        return self._workflow_executor.execute_result(
            definition,
            context,
            dict(inputs),
        )


__all__ = [
    "DefaultDomainPlannerWorkflowIntegrator",
    "DomainPlanningCapabilityView",
]
