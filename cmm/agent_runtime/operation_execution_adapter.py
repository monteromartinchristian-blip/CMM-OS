"""Phase 9.13 – Agent Execution Adapter and Operation Resolver.

Defines AgentOperationResolver and AgentExecutionAdapter connecting the Agent Runtime Loop
to registered transformation operations without allowing arbitrary execution.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from cmm.agent_runtime.enums import (
    AgentOperationExecutionStatus,
    AgentValidationDecision,
    AgentValidationStage,
)
from cmm.agent_runtime.errors import (
    AgentOperationCapabilityError,
    AgentOperationCapabilityExceededError,
    AgentOperationIdempotencyConflictError,
    AgentOperationRequestNotFoundError,
    DuplicateAgentOperationRequestError,
    ValidationAdapterError,
)
from cmm.agent_runtime.operation_execution_contracts import (
    AgentOperationExecutionResult,
    AgentOperationRequest,
    OperationCapability,
    OperationDescriptor,
    OperationExecutionGateResult,
)
from cmm.agent_runtime.operation_execution_gates import OperationExecutionGateEvaluator
from cmm.agent_runtime.operation_execution_repository import (
    AgentOperationExecutionRepository,
    InMemoryAgentOperationExecutionRepository,
)
from cmm.agent_runtime.operation_registry import (
    AgentOperationRegistry,
    InMemoryAgentOperationRegistry,
)
from cmm.agent_runtime.validation_execution_adapter import AgentValidationAdapter
from cmm.agent_runtime.validation_integration_contracts import (
    AgentValidationRequest,
    ValidationExecutionContext,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentOperationResolver:
    """Resolves an operation request against registry and capabilities."""

    def __init__(
        self,
        registry: AgentOperationRegistry,
        capabilities: dict[tuple[str, str], OperationCapability] | None = None,
    ) -> None:
        self._registry = registry
        self._capabilities = capabilities or {}

    def register_capability(self, capability: OperationCapability) -> None:
        key = (capability.operation_name, capability.operation_version)
        self._capabilities[key] = capability

    def resolve(
        self,
        operation_name: str,
        operation_version: str = "1",
        uses_count: int = 0,
    ) -> tuple[OperationDescriptor, OperationCapability]:
        desc = self._registry.resolve(operation_name, operation_version)

        key = (operation_name, operation_version)
        cap = self._capabilities.get(key)
        if cap is None:
            # Default capability if not explicitly specified
            cap = OperationCapability(
                operation_name=operation_name,
                operation_version=operation_version,
                allowed=True,
            )

        if not cap.allowed:
            raise AgentOperationCapabilityError(
                f"Capability for operation '{operation_name}' version '{operation_version}' is disallowed."
            )

        if cap.maximum_uses is not None and uses_count >= cap.maximum_uses:
            raise AgentOperationCapabilityExceededError(
                f"Operation '{operation_name}' has exceeded maximum uses ({cap.maximum_uses})."
            )

        return desc, cap


class AgentExecutionAdapter:
    """Adapter for validating gates, reserving budget/locks, and executing registered operations."""

    def __init__(
        self,
        registry: AgentOperationRegistry | None = None,
        repository: AgentOperationExecutionRepository | None = None,
        gate_evaluator: OperationExecutionGateEvaluator | None = None,
        execution_delegate: Callable[[AgentOperationRequest], dict[str, Any]]
        | None = None,
        capabilities: dict[tuple[str, str], OperationCapability] | None = None,
        validation_adapter: AgentValidationAdapter | None = None,
    ) -> None:
        self._registry = registry or InMemoryAgentOperationRegistry()
        self._repository = repository or InMemoryAgentOperationExecutionRepository()
        self._gate_evaluator = gate_evaluator or OperationExecutionGateEvaluator(
            self._registry
        )
        self._execution_delegate = execution_delegate
        self._resolver = AgentOperationResolver(self._registry, capabilities)
        self._validation_adapter = validation_adapter

    @property
    def registry(self) -> AgentOperationRegistry:
        return self._registry

    @property
    def repository(self) -> AgentOperationExecutionRepository:
        return self._repository

    @property
    def validation_adapter(self) -> AgentValidationAdapter | None:
        return self._validation_adapter

    def register_operation(
        self,
        descriptor: OperationDescriptor,
        capability: OperationCapability | None = None,
    ) -> None:
        self._registry.register(descriptor)
        if capability:
            self._resolver.register_capability(capability)

    def execute(self, request: AgentOperationRequest) -> AgentOperationExecutionResult:
        started_at = _now_iso()

        # Step 1: Idempotency check
        existing_result = self._repository.find_by_idempotency_key(
            request.idempotency_key
        )
        if existing_result is not None:
            # Verify if request fingerprint matches existing request
            try:
                prev_req = self._repository.get_request(existing_result.request_id)
                if prev_req.calculate_fingerprint() == request.calculate_fingerprint():
                    return existing_result
                else:
                    raise AgentOperationIdempotencyConflictError(
                        f"Idempotency key '{request.idempotency_key}' re-invoked with conflicting payload."
                    )
            except AgentOperationRequestNotFoundError:
                prev_req = None

        # Store request
        try:
            self._repository.add_request(request)
        except DuplicateAgentOperationRequestError:
            pass

        # Step 2: Resolve capability and uses count
        uses_count = self._repository.count_uses(
            request.agent_run_id, request.operation_name, request.operation_version
        )

        cap: OperationCapability | None = None
        desc: OperationDescriptor | None = None
        try:
            desc, cap = self._resolver.resolve(
                request.operation_name, request.operation_version, uses_count
            )
        except Exception as exc:  # noqa: BLE001
            res_id = f"op-res-{uuid.uuid4().hex[:8]}"
            res = AgentOperationExecutionResult(
                id=res_id,
                request_id=request.id,
                agent_run_id=request.agent_run_id,
                workflow_id=request.workflow_id,
                task_id=request.task_id,
                operation_name=request.operation_name,
                operation_version=request.operation_version,
                idempotency_key=request.idempotency_key,
                status=AgentOperationExecutionStatus.BLOCKED,
                success=False,
                reason_codes=("operation.capability_error", str(exc)),
                started_at=started_at,
                completed_at=_now_iso(),
            )
            self._repository.add_result(res)
            return res

        # Check fail-safe validation adapter requirement
        requires_val = bool(request.metadata.get("requires_validation", False))
        if requires_val and self._validation_adapter is None:
            raise ValidationAdapterError(
                f"Operation '{request.operation_name}' mandates validation, but no AgentValidationAdapter was injected."
            )

        # Step 3: Security Gate Evaluation
        gate_res: OperationExecutionGateResult = self._gate_evaluator.evaluate(
            request, capability=cap, uses_count=uses_count
        )

        if not gate_res.allowed:
            res_id = f"op-res-{uuid.uuid4().hex[:8]}"
            status_val = (
                AgentOperationExecutionStatus.BLOCKED
                if gate_res.blocked
                else AgentOperationExecutionStatus.FAILED
            )
            res = AgentOperationExecutionResult(
                id=res_id,
                request_id=request.id,
                agent_run_id=request.agent_run_id,
                workflow_id=request.workflow_id,
                task_id=request.task_id,
                operation_name=request.operation_name,
                operation_version=request.operation_version,
                idempotency_key=request.idempotency_key,
                status=status_val,
                success=False,
                reason_codes=gate_res.reason_codes,
                started_at=started_at,
                completed_at=_now_iso(),
            )
            self._repository.add_result(res)
            return res

        # Step 3b: Pre-Validation Check
        val_result_ids: list[str] = []
        if self._validation_adapter is not None:
            pre_req = AgentValidationRequest(
                id=f"val-req-pre-{uuid.uuid4().hex[:8]}",
                run_id=request.agent_run_id,
                iteration_id=request.task_id,
                operation_request_id=request.id,
                stage=AgentValidationStage.PRE_EXECUTION,
                idempotency_key=f"pre-{request.idempotency_key}"
                if request.idempotency_key
                else "",
            )
            pre_res = self._validation_adapter.validate(
                pre_req,
                exec_context=ValidationExecutionContext(
                    run_id=request.agent_run_id,
                    iteration_id=request.task_id,
                    operation_name=request.operation_name,
                    environment=request.environment,
                ),
            )
            val_result_ids.append(pre_res.request_id)
            if pre_res.decision != AgentValidationDecision.CONTINUE:
                res_id = f"op-res-{uuid.uuid4().hex[:8]}"
                res = AgentOperationExecutionResult(
                    id=res_id,
                    request_id=request.id,
                    agent_run_id=request.agent_run_id,
                    workflow_id=request.workflow_id,
                    task_id=request.task_id,
                    operation_name=request.operation_name,
                    operation_version=request.operation_version,
                    idempotency_key=request.idempotency_key,
                    status=AgentOperationExecutionStatus.BLOCKED,
                    success=False,
                    validation_result_ids=tuple(val_result_ids),
                    reason_codes=(
                        "operation.pre_validation_blocked",
                        pre_res.decision.value,
                    ),
                    started_at=started_at,
                    completed_at=_now_iso(),
                )
                self._repository.add_result(res)
                return res

        # Step 4: Delegate to Execution Engine
        if not self._execution_delegate:
            res_id = f"op-res-{uuid.uuid4().hex[:8]}"
            res = AgentOperationExecutionResult(
                id=res_id,
                request_id=request.id,
                agent_run_id=request.agent_run_id,
                workflow_id=request.workflow_id,
                task_id=request.task_id,
                operation_name=request.operation_name,
                operation_version=request.operation_version,
                idempotency_key=request.idempotency_key,
                status=AgentOperationExecutionStatus.FAILED,
                success=False,
                validation_result_ids=tuple(val_result_ids),
                reason_codes=("operation.no_execution_delegate",),
                started_at=started_at,
                completed_at=_now_iso(),
            )
            self._repository.add_result(res)
            return res

        try:
            exec_output = self._execution_delegate(request)
        except Exception as exc:  # noqa: BLE001
            res_id = f"op-res-{uuid.uuid4().hex[:8]}"
            res = AgentOperationExecutionResult(
                id=res_id,
                request_id=request.id,
                agent_run_id=request.agent_run_id,
                workflow_id=request.workflow_id,
                task_id=request.task_id,
                operation_name=request.operation_name,
                operation_version=request.operation_version,
                idempotency_key=request.idempotency_key,
                status=AgentOperationExecutionStatus.FAILED,
                success=False,
                validation_result_ids=tuple(val_result_ids),
                reason_codes=("operation.execution_failed", str(exc)),
                started_at=started_at,
                completed_at=_now_iso(),
            )
            self._repository.add_result(res)
            return res

        # Step 4b: Post-Validation Check
        success = exec_output.get("success", True)
        validation_failed = False
        if self._validation_adapter is not None and success:
            post_req = AgentValidationRequest(
                id=f"val-req-post-{uuid.uuid4().hex[:8]}",
                run_id=request.agent_run_id,
                iteration_id=request.task_id,
                operation_request_id=request.id,
                stage=AgentValidationStage.POST_EXECUTION,
                idempotency_key=f"post-{request.idempotency_key}"
                if request.idempotency_key
                else "",
            )
            post_res = self._validation_adapter.validate(
                post_req,
                exec_context=ValidationExecutionContext(
                    run_id=request.agent_run_id,
                    iteration_id=request.task_id,
                    operation_name=request.operation_name,
                    environment=request.environment,
                ),
            )
            val_result_ids.append(post_res.request_id)
            if post_res.decision != AgentValidationDecision.CONTINUE:
                success = False
                validation_failed = True

        # Capture outputs
        effects = tuple(exec_output.get("effects", ()))
        side_effects = tuple(exec_output.get("side_effects", ()))
        artifacts = tuple(exec_output.get("artifacts", ()))
        del_validations = exec_output.get("validation_result_ids", ())
        for v_id in del_validations:
            if v_id not in val_result_ids:
                val_result_ids.append(v_id)

        if success:
            status = AgentOperationExecutionStatus.COMPLETED
        elif validation_failed:
            status = AgentOperationExecutionStatus.VALIDATION_FAILED
        else:
            status = AgentOperationExecutionStatus.FAILED

        res_id = f"op-res-{uuid.uuid4().hex[:8]}"
        res = AgentOperationExecutionResult(
            id=res_id,
            request_id=request.id,
            agent_run_id=request.agent_run_id,
            workflow_id=request.workflow_id,
            task_id=request.task_id,
            operation_name=request.operation_name,
            operation_version=request.operation_version,
            idempotency_key=request.idempotency_key,
            status=status,
            success=success,
            execution_result_id=exec_output.get("execution_result_id"),
            effects=effects,
            side_effects=side_effects,
            artifacts=artifacts,
            validation_result_ids=tuple(val_result_ids),
            budget_consumption_id=exec_output.get("budget_consumption_id"),
            rollback_available=desc.reversible if desc else True,
            rollback_reference=exec_output.get("rollback_reference"),
            resource_versions_before=exec_output.get("resource_versions_before", {}),
            resource_versions_after=exec_output.get("resource_versions_after", {}),
            reason_codes=("operation.execution_completed",),
            started_at=started_at,
            completed_at=_now_iso(),
        )

        self._repository.add_result(res)
        return res
