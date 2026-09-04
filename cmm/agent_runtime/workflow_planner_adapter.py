"""Phase 9.7 – Workflow Planner Adapter & Agent Planning Service.

Adapts autonomous goal reasoning context to existing deterministic TaskPlanner contracts
and produces auditable AgentWorkflowPlans without executing work or mutating runtime state.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any, Protocol

from cmm.agent_runtime.contracts import AgentRun
from cmm.agent_runtime.enums import (
    AgentPlanningDecision,
    AgentPlanningStatus,
    WorkflowPlanNodeKind,
    WorkflowPlanRisk,
    WorkflowPlanStatus,
    WorkflowPlanValidationStatus,
)
from cmm.agent_runtime.errors import (
    InvalidAgentPlanningContractError,
    PlannerExecutionError,
    PlannerResultTranslationError,
    PlannerUnavailableError,
    WorkflowReplanningError,
)
from cmm.agent_runtime.goal_contracts import Goal
from cmm.agent_runtime.goal_repository import GoalRepository
from cmm.agent_runtime.observation_contracts import ObservationSnapshot
from cmm.agent_runtime.workflow_planner_contracts import (
    AgentPlanningContext,
    AgentPlanningRequest,
    AgentReplanningRequest,
    AgentReplanningResult,
    AgentWorkflowApprovalNode,
    AgentWorkflowAssumption,
    AgentWorkflowBudgetEstimate,
    AgentWorkflowCheckpoint,
    AgentWorkflowDependency,
    AgentWorkflowOperation,
    AgentWorkflowPlan,
    AgentWorkflowPlanValidation,
    AgentWorkflowRecoveryStrategy,
    AgentWorkflowRisk,
    AgentWorkflowRollbackStrategy,
    AgentWorkflowTask,
    AgentWorkflowValidationNode,
    generate_planning_context_id,
    generate_workflow_approval_node_id,
    generate_workflow_checkpoint_id,
    generate_workflow_dependency_id,
    generate_workflow_id,
    generate_workflow_operation_id,
    generate_workflow_plan_id,
    generate_workflow_task_id,
    generate_workflow_validation_node_id,
)
from cmm.agent_runtime.workflow_planner_store import InMemoryWorkflowPlanStore
from cmm.agent_runtime.workflow_planner_validator import AgentWorkflowPlanValidator
from cmm.planner.task_planner import ExecutionPlan, TaskPlanner


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_WORKFLOW_REFERENCES_METADATA_KEY = "workflow_references"
_OPERATION_SEMANTICS_METADATA_KEY = "operation_semantics"
_DEPENDENCY_REFERENCES_METADATA_KEY = "dependency_references"
_OPERATION_CANDIDATES_METADATA_KEY = "operation_candidates"
_UNRESOLVED_OPERATION_DEPENDENCIES_METADATA_KEY = "unresolved_operation_dependencies"

_VALID_OPERATION_SEMANTICS_KEYS = frozenset(
    {
        "operation_name",
        "required_permissions",
        "required_validations",
        "requires_approval",
        "approval_ids",
        "reversible",
        "rollback_operation",
        "risk",
        "timeout_seconds",
        "metadata",
    }
)

_VALID_DEPENDENCY_REFERENCE_KEYS = frozenset(
    {
        "operation_dependencies",
        "workflow_dependencies",
        "domain_dependencies",
    }
)


def _workflow_references_from_metadata(
    metadata: Mapping[str, Any],
) -> tuple[str, ...]:
    """Validate the generic workflow-reference metadata seam.

    Domain-agnostic: references are opaque non-empty string IDs. They are
    never resolved, executed, or treated as permission here; they are only
    carried deterministically from request metadata into plan metadata.
    """
    if not isinstance(metadata, Mapping):
        raise InvalidAgentPlanningContractError("Request metadata must be a mapping.")
    if _WORKFLOW_REFERENCES_METADATA_KEY not in metadata:
        return ()
    value = metadata[_WORKFLOW_REFERENCES_METADATA_KEY]
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise InvalidAgentPlanningContractError(
            "workflow_references must be a list/tuple of non-empty strings."
        )
    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise InvalidAgentPlanningContractError(
                "workflow_references must contain only non-empty strings."
            )
        if item not in cleaned:
            cleaned.append(item)
    return tuple(cleaned)


def _operation_candidates_from_metadata(
    metadata: Mapping[str, Any],
) -> tuple[str, ...] | None:
    """Validate the generic operation-candidates metadata seam.

    Domain-agnostic: candidates are opaque non-empty string operation IDs
    supplied externally as the eligible operation set. ``None`` means the
    seam is absent and the canonical heuristic translation remains
    backward-compatible. A present-but-empty list is well-formed yet
    unsatisfiable and fails closed at plan time instead of inventing an
    operation.
    """
    if not isinstance(metadata, Mapping):
        raise InvalidAgentPlanningContractError("Request metadata must be a mapping.")
    if _OPERATION_CANDIDATES_METADATA_KEY not in metadata:
        return None
    value = metadata[_OPERATION_CANDIDATES_METADATA_KEY]
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise InvalidAgentPlanningContractError(
            "operation_candidates must be a list/tuple of non-empty strings."
        )
    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise InvalidAgentPlanningContractError(
                "operation_candidates must contain only non-empty strings."
            )
        if item not in cleaned:
            cleaned.append(item)
    return tuple(cleaned)


def _plan_metadata_with_references(
    base: dict[str, Any],
    request_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """Copy base plan metadata and carry validated generic references."""
    metadata = dict(base)
    references = _workflow_references_from_metadata(request_metadata)
    if references:
        metadata[_WORKFLOW_REFERENCES_METADATA_KEY] = list(references)
    candidates = _operation_candidates_from_metadata(request_metadata)
    if candidates is not None and len(candidates) > 0:
        metadata[_OPERATION_CANDIDATES_METADATA_KEY] = list(candidates)
    dependency_references = _dependency_references_from_metadata(request_metadata)
    if dependency_references and any(dependency_references.values()):
        metadata[_DEPENDENCY_REFERENCES_METADATA_KEY] = {
            "operation_dependencies": [
                list(pair) for pair in dependency_references["operation_dependencies"]
            ],
            "workflow_dependencies": {
                workflow_id: list(deps)
                for workflow_id, deps in dependency_references[
                    "workflow_dependencies"
                ].items()
            },
            "domain_dependencies": [
                list(pair) for pair in dependency_references["domain_dependencies"]
            ],
        }
    return metadata


def _clean_id_list(value: Any, *, key: str, owner: str) -> list[str]:
    """Validate a generic ID collection and normalize it deterministically."""
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise InvalidAgentPlanningContractError(f"{owner} {key} must be a list.")
    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise InvalidAgentPlanningContractError(
                f"{owner} {key} must contain only non-empty strings."
            )
        if item not in cleaned:
            cleaned.append(item)
    return cleaned


def _operation_semantics_from_metadata(
    metadata: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Validate the generic operation-semantics metadata seam.

    Domain-agnostic: each entry describes exact planning semantics for one
    operation name (permissions, validations, approval, reversibility,
    rollback, risk, timeout, provenance metadata). Entries are never executed
    or authorized here; they only overlay the translated plan operations that
    share the same operation name.
    """
    if not isinstance(metadata, Mapping):
        raise InvalidAgentPlanningContractError("Request metadata must be a mapping.")
    if _OPERATION_SEMANTICS_METADATA_KEY not in metadata:
        return ()
    value = metadata[_OPERATION_SEMANTICS_METADATA_KEY]
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise InvalidAgentPlanningContractError(
            "operation_semantics must be a list/tuple of mappings."
        )
    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        owner = f"operation_semantics[{index}]"
        if not isinstance(item, Mapping):
            raise InvalidAgentPlanningContractError(f"{owner} must be a mapping.")
        unknown = sorted(set(item) - _VALID_OPERATION_SEMANTICS_KEYS)
        if unknown:
            raise InvalidAgentPlanningContractError(
                f"{owner} has unknown fields: {unknown}."
            )
        name = item.get("operation_name")
        if not isinstance(name, str) or not name.strip():
            raise InvalidAgentPlanningContractError(
                f"{owner} operation_name must be a non-empty string."
            )
        if name in seen:
            raise InvalidAgentPlanningContractError(
                f"{owner} duplicates operation_name {name!r}."
            )
        seen.add(name)
        requires_approval = item.get("requires_approval", False)
        if not isinstance(requires_approval, bool):
            raise InvalidAgentPlanningContractError(
                f"{owner} requires_approval must be a boolean."
            )
        reversible = item.get("reversible", False)
        if not isinstance(reversible, bool):
            raise InvalidAgentPlanningContractError(
                f"{owner} reversible must be a boolean."
            )
        rollback = item.get("rollback_operation")
        if rollback is not None and (
            not isinstance(rollback, str) or not rollback.strip()
        ):
            raise InvalidAgentPlanningContractError(
                f"{owner} rollback_operation must be a non-empty string or None."
            )
        risk = item.get("risk")
        if risk is not None:
            if not isinstance(risk, str):
                raise InvalidAgentPlanningContractError(
                    f"{owner} risk must be a WorkflowPlanRisk value or None."
                )
            try:
                WorkflowPlanRisk(risk)
            except ValueError as exc:
                raise InvalidAgentPlanningContractError(
                    f"{owner} risk must be a WorkflowPlanRisk value or None."
                ) from exc
        timeout = item.get("timeout_seconds")
        if timeout is not None and (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not timeout > 0
        ):
            raise InvalidAgentPlanningContractError(
                f"{owner} timeout_seconds must be a positive number or None."
            )
        extra_metadata = item.get("metadata", {})
        if not isinstance(extra_metadata, Mapping):
            raise InvalidAgentPlanningContractError(
                f"{owner} metadata must be a mapping."
            )
        cleaned.append(
            {
                "operation_name": name,
                "required_permissions": _clean_id_list(
                    item.get("required_permissions", []),
                    key="required_permissions",
                    owner=owner,
                ),
                "required_validations": _clean_id_list(
                    item.get("required_validations", []),
                    key="required_validations",
                    owner=owner,
                ),
                "requires_approval": requires_approval,
                "approval_ids": _clean_id_list(
                    item.get("approval_ids", []),
                    key="approval_ids",
                    owner=owner,
                ),
                "reversible": reversible,
                "rollback_operation": rollback,
                "risk": risk,
                "timeout_seconds": float(timeout) if timeout is not None else None,
                "metadata": dict(extra_metadata),
            }
        )
    cleaned.sort(key=lambda entry: entry["operation_name"])
    return tuple(cleaned)


def _operation_dependency_pairs(value: Any, *, key: str) -> list[tuple[str, str]]:
    """Validate generic [upstream, downstream] dependency pairs."""
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise InvalidAgentPlanningContractError(
            f"dependency_references {key} must be a list."
        )
    pairs: list[tuple[str, str]] = []
    for index, item in enumerate(value):
        owner = f"dependency_references {key}[{index}]"
        if isinstance(item, (str, bytes)) or not isinstance(item, (list, tuple)):
            raise InvalidAgentPlanningContractError(
                f"{owner} must be a [upstream, downstream] pair."
            )
        if len(tuple(item)) != 2:
            raise InvalidAgentPlanningContractError(
                f"{owner} must be a [upstream, downstream] pair."
            )
        upstream, downstream = tuple(item)
        if not isinstance(upstream, str) or not upstream.strip():
            raise InvalidAgentPlanningContractError(
                f"{owner} upstream must be a non-empty string."
            )
        if not isinstance(downstream, str) or not downstream.strip():
            raise InvalidAgentPlanningContractError(
                f"{owner} downstream must be a non-empty string."
            )
        pair = (upstream, downstream)
        if pair not in pairs:
            pairs.append(pair)
    pairs.sort()
    return pairs


def _dependency_references_from_metadata(
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the generic dependency-references metadata seam.

    Domain-agnostic: operation pairs name upstream/downstream operations,
    workflow references map opaque workflow IDs to dependency IDs, and domain
    pairs name upstream/downstream dependency scopes. References are carried
    into plan metadata; operation pairs whose endpoints are both planned also
    materialize as canonical dependency edges.
    """
    if not isinstance(metadata, Mapping):
        raise InvalidAgentPlanningContractError("Request metadata must be a mapping.")
    if _DEPENDENCY_REFERENCES_METADATA_KEY not in metadata:
        return {}
    value = metadata[_DEPENDENCY_REFERENCES_METADATA_KEY]
    if not isinstance(value, Mapping):
        raise InvalidAgentPlanningContractError(
            "dependency_references must be a mapping."
        )
    unknown = sorted(set(value) - _VALID_DEPENDENCY_REFERENCE_KEYS)
    if unknown:
        raise InvalidAgentPlanningContractError(
            f"dependency_references has unknown fields: {unknown}."
        )
    workflow_raw = value.get("workflow_dependencies", {})
    if not isinstance(workflow_raw, Mapping):
        raise InvalidAgentPlanningContractError(
            "dependency_references workflow_dependencies must be a mapping."
        )
    workflow_cleaned: dict[str, list[str]] = {}
    for workflow_id, deps in workflow_raw.items():
        if not isinstance(workflow_id, str) or not workflow_id.strip():
            raise InvalidAgentPlanningContractError(
                "dependency_references workflow IDs must be non-empty strings."
            )
        workflow_cleaned[workflow_id] = sorted(
            set(
                _clean_id_list(
                    deps,
                    key=f"workflow_dependencies[{workflow_id}]",
                    owner="dependency_references",
                )
            )
        )
    return {
        "operation_dependencies": _operation_dependency_pairs(
            value.get("operation_dependencies", []),
            key="operation_dependencies",
        ),
        "workflow_dependencies": dict(sorted(workflow_cleaned.items())),
        "domain_dependencies": _operation_dependency_pairs(
            value.get("domain_dependencies", []),
            key="domain_dependencies",
        ),
    }


class WorkflowPlannerAdapter(Protocol):
    """Protocol for translating autonomous planning requests into AgentWorkflowPlans."""

    def plan(self, request: AgentPlanningRequest) -> AgentWorkflowPlan:
        """Create a structured workflow plan for ``request``."""

    def replan(self, request: AgentReplanningRequest) -> AgentReplanningResult:
        """Re-evaluate and version an existing workflow plan."""


class DefaultWorkflowPlannerAdapter:
    """Default implementation of WorkflowPlannerAdapter translating context to TaskPlanner."""

    def __init__(
        self,
        planner: TaskPlanner | None = None,
        goal_repository: GoalRepository | None = None,
        agent_run_provider: Callable[[str], AgentRun | None] | None = None,
        cognitive_result_provider: Callable[[str], Any | None] | None = None,
        snapshot_provider: Callable[[str], ObservationSnapshot | None] | None = None,
        operation_registry: Any | None = None,
        plan_store: InMemoryWorkflowPlanStore | None = None,
        validator: AgentWorkflowPlanValidator | None = None,
        clock: Callable[[], str] | None = None,
        id_factory: Callable[[str], str] | None = None,
    ) -> None:
        self._planner = planner
        self._goal_repository = goal_repository
        self._agent_run_provider = agent_run_provider
        self._cognitive_result_provider = cognitive_result_provider
        self._snapshot_provider = snapshot_provider
        self._operation_registry = operation_registry
        self._plan_store = plan_store or InMemoryWorkflowPlanStore()
        self._validator = validator or AgentWorkflowPlanValidator(
            operation_registry=operation_registry
        )
        self._clock = clock or _utc_now_iso
        self._id_factory = id_factory

    def build_context(self, request: AgentPlanningRequest) -> AgentPlanningContext:
        """Construct the immutable planning context delivered to the Planner."""
        if not isinstance(request, AgentPlanningRequest):
            raise InvalidAgentPlanningContractError(
                "Invalid request: must be AgentPlanningRequest."
            )

        goal_obj: Goal | None = None
        if self._goal_repository and request.goal_id:
            try:
                if hasattr(self._goal_repository, "get"):
                    goal_obj = self._goal_repository.get(request.goal_id)
                elif hasattr(self._goal_repository, "get_by_id"):
                    goal_obj = self._goal_repository.get_by_id(request.goal_id)
            except (KeyError, ValueError, RuntimeError, AttributeError):
                goal_obj = None

        agent_run_obj: AgentRun | None = None
        if self._agent_run_provider and request.agent_run_id:
            try:
                agent_run_obj = self._agent_run_provider(request.agent_run_id)
            except (KeyError, ValueError, RuntimeError, AttributeError):
                agent_run_obj = None

        obs_snapshot_obj: ObservationSnapshot | None = None
        if self._snapshot_provider and request.observation_snapshot_id:
            try:
                obs_snapshot_obj = self._snapshot_provider(
                    request.observation_snapshot_id
                )
            except (KeyError, ValueError, RuntimeError, AttributeError):
                obs_snapshot_obj = None

        ctx_id = generate_planning_context_id()
        objective = request.objective or (goal_obj.description if goal_obj else "")

        return AgentPlanningContext(
            id=ctx_id,
            request_id=request.id,
            goal=goal_obj,
            agent_run=agent_run_obj,
            objective=objective,
            success_criteria=list(request.success_criteria),
            constraints=list(request.constraints),
            requirements=list(request.requirements),
            observation_snapshot=obs_snapshot_obj,
            relevant_facts=[],
            cognitive_recommendations=[],
            accepted_gaps=[],
            assumptions=[
                "Goal objective is actionable and reachable with registered operations."
            ],
            resources=list(request.resource_ids),
            knowledge_ids=list(request.relevant_knowledge_ids),
            allowed_operations=list(request.allowed_operations),
            prohibited_operations=list(request.prohibited_operations),
            permissions=list(request.permissions),
            nominal_policies={"validation_policy": request.validation_policy},
            budget_estimate=dict(request.budget),
            timeout_seconds=request.timeout_seconds,
            metadata=dict(request.metadata),
            created_at=self._clock(),
        )

    def plan(self, request: AgentPlanningRequest) -> AgentWorkflowPlan:
        """Create an AgentWorkflowPlan for the given request using existing TaskPlanner."""
        if not isinstance(request, AgentPlanningRequest):
            raise InvalidAgentPlanningContractError(
                "Request must be instance of AgentPlanningRequest."
            )

        # Fail fast on malformed generic seams on every planning path.
        _operation_semantics_from_metadata(request.metadata)
        _operation_candidates_from_metadata(request.metadata)
        _dependency_references_from_metadata(request.metadata)

        context = self.build_context(request)

        # Check for complete_without_workflow condition
        cognitive_res = None
        if self._cognitive_result_provider and request.cognitive_result_id:
            cognitive_res = self._cognitive_result_provider(request.cognitive_result_id)

        cognitive_decision = getattr(cognitive_res, "decision", None)
        goal_status = (
            str(getattr(context.goal.status, "value", context.goal.status))
            if context.goal is not None
            else None
        )
        is_already_satisfied = goal_status in (
            "completed",
            "partially_completed",
        ) or cognitive_decision in (
            "complete_without_action",
            "COMPLETE_WITHOUT_ACTION",
        )

        if is_already_satisfied:
            # Produce completion plan without invoking planner
            wf_id = generate_workflow_id()
            plan_id = generate_workflow_plan_id()
            now = self._clock()

            plan = AgentWorkflowPlan(
                id=plan_id,
                goal_id=request.goal_id,
                agent_run_id=request.agent_run_id,
                workflow_id=wf_id,
                version=1,
                status=WorkflowPlanStatus.COMPLETED,
                objective=context.objective,
                scope=["No action required"],
                tasks=[],
                dependencies=[],
                operations=[],
                validation_nodes=[],
                approval_nodes=[],
                checkpoints=[],
                completion_criteria=["Goal already satisfied"],
                assumptions=[
                    AgentWorkflowAssumption(
                        id="assump-satisfied",
                        statement="Goal objective is already satisfied prior to execution.",
                        validated=True,
                    )
                ],
                confidence=1.0,
                validation=AgentWorkflowPlanValidation(
                    status=WorkflowPlanValidationStatus.PASSED,
                    is_valid=True,
                    validated_at=now,
                ),
                created_at=now,
                updated_at=now,
                metadata=_plan_metadata_with_references(
                    {"decision": AgentPlanningDecision.COMPLETE_WITHOUT_WORKFLOW.value},
                    request.metadata,
                ),
            )
            self._plan_store.add(plan)
            return plan

        # Planner invocation
        if self._planner is None:
            raise PlannerUnavailableError(
                "TaskPlanner instance is not configured in adapter."
            )

        objective_text = context.objective
        if not objective_text.strip():
            raise PlannerExecutionError(
                "Goal objective is empty; cannot invoke TaskPlanner."
            )

        try:
            exec_plan: ExecutionPlan = self._planner.create_plan(objective_text)
        except Exception as err:
            raise PlannerExecutionError(f"TaskPlanner execution failed: {err}") from err

        if not isinstance(exec_plan, ExecutionPlan):
            raise PlannerResultTranslationError(
                "TaskPlanner did not return a valid ExecutionPlan."
            )

        # Translate ExecutionPlan to AgentWorkflowPlan
        wf_plan = self.translate_plan(exec_plan, request, context)

        # Structural Validation
        val_result = self._validator.validate(wf_plan, request=request)

        # Update status according to validation
        if not val_result.is_valid:
            status = WorkflowPlanStatus.INVALID
        elif val_result.status == WorkflowPlanValidationStatus.PASSED_WITH_WARNINGS:
            status = WorkflowPlanStatus.VALID
        else:
            status = WorkflowPlanStatus.VALID

        final_plan = AgentWorkflowPlan.from_dict(
            {
                **wf_plan.to_dict(),
                "status": status.value,
                "validation": val_result.to_dict(),
                "updated_at": self._clock(),
            }
        )

        self._plan_store.add(final_plan)
        return final_plan

    def translate_plan(
        self,
        exec_plan: ExecutionPlan,
        request: AgentPlanningRequest,
        context: AgentPlanningContext | None = None,
    ) -> AgentWorkflowPlan:
        """Translate existing TaskPlanner's ExecutionPlan to AgentWorkflowPlan."""
        context = context or self.build_context(request)
        operation_semantics = {
            entry["operation_name"]: entry
            for entry in _operation_semantics_from_metadata(request.metadata)
        }
        dependency_references = _dependency_references_from_metadata(request.metadata)
        operation_candidates = _operation_candidates_from_metadata(request.metadata)
        if operation_candidates is not None and len(operation_candidates) == 0:
            raise InvalidAgentPlanningContractError(
                "operation_candidates is empty: no eligible operation can "
                "satisfy a planned step."
            )
        wf_id = generate_workflow_id()
        plan_id = generate_workflow_plan_id()
        now = self._clock()

        tasks: list[AgentWorkflowTask] = []
        dependencies: list[AgentWorkflowDependency] = []
        operations: list[AgentWorkflowOperation] = []
        validation_nodes: list[AgentWorkflowValidationNode] = []
        approval_nodes: list[AgentWorkflowApprovalNode] = []
        checkpoints: list[AgentWorkflowCheckpoint] = []

        prev_task_id: str | None = None

        # Map steps from ExecutionPlan to AgentWorkflowTask & Operations
        for step_index, step in enumerate(exec_plan.steps):
            t_id = generate_workflow_task_id()
            op_id = generate_workflow_operation_id()
            val_node_id = generate_workflow_validation_node_id()

            if operation_candidates is not None:
                # Generic deterministic selection: the canonical planner
                # still owns step generation; only the operation identity is
                # drawn from the externally supplied eligible set, consumed
                # round-robin in step order. No Domain semantics live here:
                # candidates are opaque operation IDs. Callers declaring
                # required operation dependencies must supply pairs
                # consistent with this documented order; opposing pairs
                # genuinely cycle with the sequential task chain and fail
                # closed through the canonical validator.
                op_name = operation_candidates[step_index % len(operation_candidates)]
                step_title_lower = step.title.lower()
            else:
                # Determine operation name and parameters based on step title
                step_title_lower = step.title.lower()
                if "entry point" in step_title_lower or "analyze" in step_title_lower:
                    op_name = "python.find_symbol"
                elif "dependenc" in step_title_lower:
                    op_name = "python.list_imports"
                elif "impact" in step_title_lower or "risk" in step_title_lower:
                    op_name = "python.describe_module"
                elif "prepare" in step_title_lower or "modif" in step_title_lower:
                    op_name = "filesystem.read_file"
                else:
                    op_name = "filesystem.exists"

            # Check for allowed / prohibited restrictions
            op_risk = WorkflowPlanRisk.LOW
            if "modif" in step_title_lower or "prepare" in step_title_lower:
                op_risk = WorkflowPlanRisk.MEDIUM

            # Overlay exact generic operation semantics when provided: the
            # heuristic Phase 9 substitutes above never override them.
            semantics = operation_semantics.get(op_name)
            op_permissions: list[str] = []
            op_validations: list[str] = []
            op_requires_approval = False
            op_approval_ids: list[str] = []
            op_reversible = True
            op_rollback: str | None = (
                f"{op_name}.revert" if op_risk != WorkflowPlanRisk.NONE else None
            )
            op_timeout: float | None = None
            semantics_metadata: dict[str, Any] = {}
            if semantics is not None:
                op_permissions = list(semantics["required_permissions"])
                op_validations = list(semantics["required_validations"])
                op_requires_approval = semantics["requires_approval"]
                op_approval_ids = list(semantics["approval_ids"])
                op_reversible = semantics["reversible"]
                op_rollback = semantics["rollback_operation"]
                if semantics["risk"] is not None:
                    op_risk = WorkflowPlanRisk(semantics["risk"])
                op_timeout = semantics["timeout_seconds"]
                semantics_metadata = dict(semantics["metadata"])

            # Operation definition
            operation = AgentWorkflowOperation(
                id=op_id,
                task_id=t_id,
                operation_name=op_name,
                parameters={"target": getattr(exec_plan, "goal", "")},
                expected_effects=[f"Execute step: {step.title}"],
                reversible=op_reversible,
                rollback_operation=op_rollback,
                required_permissions=op_permissions,
                required_validations=op_validations,
                requires_approval=op_requires_approval,
                risk=op_risk,
                timeout_seconds=op_timeout,
                metadata={
                    **semantics_metadata,
                    "plan_step_order": step.order,
                    "rationale": step.rationale,
                },
            )
            operations.append(operation)

            # Validation node for post-step check. Exact validation requirement
            # IDs stay traceable on the node: operation-specific IDs union the
            # plan-wide required validations, which this adapter previously
            # ignored.
            task_validation_ids = sorted(
                set(op_validations) | set(request.required_validations)
            )
            val_node = AgentWorkflowValidationNode(
                id=val_node_id,
                workflow_id=wf_id,
                policy=request.validation_policy,
                timing="post",
                required=True,
                blocking=True,
                related_id=t_id,
                expected_result="passed",
                metadata={"validation_requirement_ids": task_validation_ids},
            )
            validation_nodes.append(val_node)

            # Approval node if requested or high risk. Exact approval IDs stay
            # traceable via required_approvers and node metadata instead of an
            # anonymous generic node.
            task_approval_ids = sorted(
                set(op_approval_ids) | set(request.required_approvals)
            )
            if (
                request.required_approvals
                or op_requires_approval
                or op_risk
                in (
                    WorkflowPlanRisk.HIGH,
                    WorkflowPlanRisk.CRITICAL,
                )
            ):
                appr_id = generate_workflow_approval_node_id()
                approval_nodes.append(
                    AgentWorkflowApprovalNode(
                        id=appr_id,
                        workflow_id=wf_id,
                        reason=f"Approval required for step: {step.title}",
                        risk=op_risk,
                        related_id=t_id,
                        pending=True,
                        required_approvers=task_approval_ids,
                        metadata={"approval_requirement_ids": task_approval_ids},
                    )
                )

            # Task definition
            task = AgentWorkflowTask(
                id=t_id,
                workflow_id=wf_id,
                name=step.title,
                description=step.description,
                kind=WorkflowPlanNodeKind.TASK,
                status="pending",
                dependency_ids=[prev_task_id] if prev_task_id else [],
                operation_ids=[op_id],
                validation_node_ids=[val_node_id],
                inputs={"goal": exec_plan.goal},
                expected_outputs={"result": f"Output of {step.title}"},
                success_criteria=[step.rationale],
                metadata={"order": step.order},
            )
            tasks.append(task)

            # Dependency definition
            if prev_task_id:
                dep_id = generate_workflow_dependency_id()
                dependencies.append(
                    AgentWorkflowDependency(
                        id=dep_id,
                        source_task_id=prev_task_id,
                        target_task_id=t_id,
                        dependency_type="requires_completion",
                        blocking=True,
                    )
                )

            prev_task_id = t_id

        # Materialize generic operation dependency pairs whose endpoints are
        # both planned as canonical dependency edges. Pairs naming unplanned
        # operations stay traceable in plan metadata only.
        operation_tasks: dict[str, str] = {}
        for task, operation in zip(tasks, operations):
            operation_tasks.setdefault(operation.operation_name, task.id)
        existing_edges = {
            (dep.source_task_id, dep.target_task_id) for dep in dependencies
        }
        for upstream_name, downstream_name in dependency_references.get(
            "operation_dependencies", []
        ):
            if upstream_name not in operation_tasks:
                continue
            if downstream_name not in operation_tasks:
                continue
            source_task_id = operation_tasks[upstream_name]
            target_task_id = operation_tasks[downstream_name]
            if source_task_id == target_task_id:
                continue
            if (source_task_id, target_task_id) in existing_edges:
                continue
            dependencies.append(
                AgentWorkflowDependency(
                    id=generate_workflow_dependency_id(),
                    source_task_id=source_task_id,
                    target_task_id=target_task_id,
                    dependency_type="requires_completion",
                    blocking=True,
                    metadata={"source": "dependency_references"},
                )
            )
            existing_edges.add((source_task_id, target_task_id))
            for task in tasks:
                if (
                    task.id == target_task_id
                    and source_task_id not in task.dependency_ids
                ):
                    task.dependency_ids.append(source_task_id)

        # Add checkpoint if multi-step
        if len(tasks) > 1:
            chk_id = generate_workflow_checkpoint_id()
            checkpoints.append(
                AgentWorkflowCheckpoint(
                    id=chk_id,
                    workflow_id=wf_id,
                    name="Mid-plan Checkpoint",
                    position=len(tasks) // 2,
                    affected_resources=list(request.resource_ids),
                    reason="Verify intermediate state stability",
                    required=True,
                )
            )

        # Build strategy, budget, risks, assumptions
        rollback_strat = AgentWorkflowRollbackStrategy(
            id=f"rollback-{wf_id}",
            available=True,
            kind="step_by_step",
            trigger_conditions=["operation_failed", "validation_failed"],
            scope="workflow",
        )

        recovery_strat = AgentWorkflowRecoveryStrategy(
            id=f"recovery-{wf_id}",
            actions=["retry", "replan", "rollback"],
            maximum_attempts=3,
        )

        budget_est = AgentWorkflowBudgetEstimate(
            estimated_tokens=len(tasks) * 500,
            estimated_cost=0.01 * len(tasks),
            estimated_duration_seconds=float(len(tasks) * 10),
            estimated_operations=len(operations),
            limits=dict(request.budget),
        )

        risks = [
            AgentWorkflowRisk(
                id=f"risk-{wf_id}-1",
                name="Complexity Risk",
                level=WorkflowPlanRisk.LOW
                if len(tasks) <= 3
                else WorkflowPlanRisk.MEDIUM,
                description=f"Plan estimated complexity: {exec_plan.estimated_complexity}",
            )
        ]

        assumptions = [
            AgentWorkflowAssumption(
                id=f"assump-{wf_id}-1",
                statement="Planner step sequence is deterministically orderable.",
                validated=True,
            )
        ]

        completion_criteria = [
            f"Complete all {len(tasks)} planned steps for goal: {exec_plan.goal}"
        ]

        return AgentWorkflowPlan(
            id=plan_id,
            goal_id=request.goal_id,
            agent_run_id=request.agent_run_id,
            workflow_id=wf_id,
            planner_plan_id=f"plan-{id(exec_plan)}",
            version=1,
            status=WorkflowPlanStatus.DRAFT,
            objective=context.objective,
            scope=[s.title for s in exec_plan.steps],
            tasks=tasks,
            dependencies=dependencies,
            operations=operations,
            validation_nodes=validation_nodes,
            approval_nodes=approval_nodes,
            checkpoints=checkpoints,
            rollback_strategy=rollback_strat,
            recovery_strategy=recovery_strat,
            completion_criteria=completion_criteria,
            pause_conditions=["validation_failed", "approval_rejected"],
            cancellation_conditions=["goal_cancelled", "resource_revoked"],
            assumptions=assumptions,
            risks=risks,
            expected_effects=[f"Achieve: {context.objective}"],
            estimated_budget=budget_est,
            timeout_seconds=request.timeout_seconds or 300.0,
            confidence=0.9,
            created_at=now,
            updated_at=now,
            metadata=_plan_metadata_with_references(
                {"estimated_complexity": exec_plan.estimated_complexity},
                request.metadata,
            ),
        )

    def replan(self, request: AgentReplanningRequest) -> AgentReplanningResult:
        """Generate a new version of an existing workflow plan."""
        if not isinstance(request, AgentReplanningRequest):
            raise InvalidAgentPlanningContractError(
                "Request must be instance of AgentReplanningRequest."
            )

        prev_plan = self._plan_store.get(request.plan_id)
        if not prev_plan:
            raise WorkflowReplanningError(
                f"Previous plan '{request.plan_id}' not found in plan store."
            )

        # Construct sub-planning request
        base_planning_req = request.planning_request or AgentPlanningRequest(
            id=f"req-replan-{request.id}",
            goal_id=prev_plan.goal_id,
            agent_run_id=prev_plan.agent_run_id,
            objective=prev_plan.objective,
            timeout_seconds=prev_plan.timeout_seconds,
        )

        new_plan_draft = self.plan(base_planning_req)

        # Incremented version and link previous version
        new_version_num = prev_plan.version + 1
        new_plan_id = generate_workflow_plan_id()
        new_plan = AgentWorkflowPlan.from_dict(
            {
                **new_plan_draft.to_dict(),
                "id": new_plan_id,
                "workflow_id": prev_plan.workflow_id,
                "version": new_version_num,
                "previous_version_id": prev_plan.id,
                "status": WorkflowPlanStatus.VALID.value,
                "updated_at": self._clock(),
                "metadata": {
                    **new_plan_draft.metadata,
                    "replan_reason": request.reason.value,
                    "replan_details": request.reason_details,
                },
            }
        )

        # Update store: mark previous plan as superseded
        self._plan_store.supersede(prev_plan.id, new_plan.id)
        self._plan_store.add(new_plan)

        res_id = f"replan-res-{request.id}"
        return AgentReplanningResult(
            id=res_id,
            request_id=request.id,
            status=AgentPlanningStatus.COMPLETED,
            decision=AgentPlanningDecision.REPLAN,
            previous_plan_id=prev_plan.id,
            new_plan=new_plan,
            version=new_version_num,
            change_reason=request.reason,
            created_at=self._clock(),
        )


class AgentPlanningService:
    """Public high-level facade for managing agent planning, context building, validation, and store history."""

    def __init__(
        self,
        adapter: DefaultWorkflowPlannerAdapter | None = None,
        plan_store: InMemoryWorkflowPlanStore | None = None,
        validator: AgentWorkflowPlanValidator | None = None,
    ) -> None:
        self._store = plan_store or (
            adapter._plan_store if adapter else InMemoryWorkflowPlanStore()
        )
        self._validator = validator or (
            adapter._validator if adapter else AgentWorkflowPlanValidator()
        )
        self._adapter = adapter or DefaultWorkflowPlannerAdapter(
            plan_store=self._store, validator=self._validator
        )

    def plan(self, request: AgentPlanningRequest) -> AgentWorkflowPlan:
        """Create a new workflow plan for ``request``."""
        return self._adapter.plan(request)

    def replan(self, request: AgentReplanningRequest) -> AgentReplanningResult:
        """Trigger replanning and produce a new versioned plan."""
        return self._adapter.replan(request)

    def build_context(self, request: AgentPlanningRequest) -> AgentPlanningContext:
        """Build the immutable planning context."""
        return self._adapter.build_context(request)

    def translate_plan(
        self, execution_plan: ExecutionPlan, request: AgentPlanningRequest
    ) -> AgentWorkflowPlan:
        """Translate ExecutionPlan to AgentWorkflowPlan directly."""
        return self._adapter.translate_plan(execution_plan, request)

    def validate_plan(
        self, plan: AgentWorkflowPlan, request: AgentPlanningRequest | None = None
    ) -> AgentWorkflowPlanValidation:
        """Perform structural validation on ``plan``."""
        return self._validator.validate(plan, request=request)

    def get_plan(self, plan_id: str) -> AgentWorkflowPlan | None:
        """Retrieve stored plan by ID."""
        return self._store.get(plan_id)

    def get_latest_plan(self, workflow_id: str) -> AgentWorkflowPlan | None:
        """Retrieve latest plan version for workflow ID."""
        return self._store.get_latest(workflow_id)

    def list_versions(self, workflow_id: str) -> list[AgentWorkflowPlan]:
        """List all version instances for workflow ID."""
        return self._store.list_versions(workflow_id)
