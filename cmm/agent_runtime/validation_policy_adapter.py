"""Phase 9.14 – Validation Policy Adapter and Resolver.

Derives cumulative, fail-safe validation requirements based on agent definition, goal,
operation descriptor, effects, autonomy, policies, and commit gate configuration.
"""

from __future__ import annotations

from cmm.agent_runtime.contracts import AgentDefinition, AgentRun
from cmm.agent_runtime.enums import (
    AgentValidationStage,
    OperationEffectType,
    ValidationRequirementKind,
)
from cmm.agent_runtime.errors import ValidationPolicySelectionError
from cmm.agent_runtime.goal_contracts import Goal
from cmm.agent_runtime.operation_execution_contracts import (
    OperationCapability,
    OperationDescriptor,
)
from cmm.agent_runtime.validation_integration_contracts import (
    ValidationPolicySelection,
    ValidationRequirement,
)


class ValidationRequirementResolver:
    """Resolves required validation checks for a given operation context."""

    def resolve_requirements(
        self,
        operation_descriptor: OperationDescriptor | None = None,
        capability: OperationCapability | None = None,
        stage: AgentValidationStage = AgentValidationStage.PRE_EXECUTION,
        agent_definition: AgentDefinition | None = None,
        goal: Goal | None = None,
        agent_run: AgentRun | None = None,
        environment: str = "local",
        sensitivity: str = "medium",
        commit_gate_required: bool = False,
        is_rollback: bool = False,
    ) -> tuple[ValidationRequirement, ...]:
        reqs: list[ValidationRequirement] = []
        op_name = operation_descriptor.name if operation_descriptor else "unknown"
        op_ver = operation_descriptor.version if operation_descriptor else "1"
        op_slug = f"{op_name}-{op_ver}"

        if is_rollback or stage == AgentValidationStage.POST_ROLLBACK:
            reqs.append(
                ValidationRequirement(
                    requirement_id=f"req-rollback-{op_slug}",
                    validation_kind=ValidationRequirementKind.POST_CONDITION,
                    stage=AgentValidationStage.POST_ROLLBACK,
                    required=True,
                    blocking=True,
                    operation_name=op_name,
                    operation_version=op_ver,
                    metadata={"reason": "rollback_validation"},
                )
            )

        if not operation_descriptor:
            # Default preventative check if no descriptor
            reqs.append(
                ValidationRequirement(
                    requirement_id=f"req-prevent-{op_slug}-{stage.value}",
                    validation_kind=ValidationRequirementKind.PREVENTATIVE,
                    stage=stage,
                    required=True,
                    blocking=True,
                    metadata={"reason": "no_descriptor_default_check"},
                )
            )
            return tuple(reqs)

        effects = tuple(OperationEffectType(e) for e in operation_descriptor.effects)
        tags = tuple(operation_descriptor.metadata.get("tags", ()))
        is_read_only = bool(effects) and all(
            e == OperationEffectType.READ for e in effects
        )
        is_destructive = (
            OperationEffectType.DELETE in effects or not operation_descriptor.reversible
        )
        is_code_modifying = any(
            e
            in (
                OperationEffectType.CREATE,
                OperationEffectType.UPDATE,
                OperationEffectType.DELETE,
            )
            for e in effects
        ) and any(
            "code" in str(tag) or "src" in str(tag) or "python" in str(tag)
            for tag in tags
        )

        is_python_file = is_code_modifying or any("python" in str(tag) for tag in tags)
        is_publish = (
            OperationEffectType.PUBLISH in effects
            or any("publish" in str(tag) for tag in tags)
            or commit_gate_required
        )

        # Stage specific checks
        if stage == AgentValidationStage.PRE_EXECUTION:
            # Preventative sanity check
            reqs.append(
                ValidationRequirement(
                    requirement_id=f"req-pre-sanity-{op_slug}",
                    validation_kind=ValidationRequirementKind.PREVENTATIVE,
                    stage=AgentValidationStage.PRE_EXECUTION,
                    required=True,
                    blocking=is_destructive or sensitivity in ("high", "critical"),
                    operation_name=op_name,
                    operation_version=op_ver,
                    metadata={"read_only": is_read_only, "sensitivity": sensitivity},
                )
            )

            if is_destructive:
                reqs.append(
                    ValidationRequirement(
                        requirement_id=f"req-pre-destructive-{op_slug}",
                        validation_kind=ValidationRequirementKind.SECURITY,
                        stage=AgentValidationStage.PRE_EXECUTION,
                        required=True,
                        blocking=True,
                        operation_name=op_name,
                        operation_version=op_ver,
                        metadata={"reason": "destructive_operation_pre_check"},
                    )
                )

        elif stage == AgentValidationStage.POST_EXECUTION:
            if not is_read_only:
                # Mutative operations require post-validation
                reqs.append(
                    ValidationRequirement(
                        requirement_id=f"req-post-mutative-{op_slug}",
                        validation_kind=ValidationRequirementKind.POST_CONDITION,
                        stage=AgentValidationStage.POST_EXECUTION,
                        required=True,
                        blocking=True,
                        operation_name=op_name,
                        operation_version=op_ver,
                    )
                )

            if is_code_modifying or is_python_file:
                reqs.append(
                    ValidationRequirement(
                        requirement_id=f"req-syntax-{op_slug}",
                        validation_kind=ValidationRequirementKind.SYNTAX,
                        stage=AgentValidationStage.POST_EXECUTION,
                        required=True,
                        blocking=True,
                        validator_ids=("syntax_validator",),
                        operation_name=op_name,
                        operation_version=op_ver,
                    )
                )

            if is_python_file:
                reqs.append(
                    ValidationRequirement(
                        requirement_id=f"req-ast-{op_slug}",
                        validation_kind=ValidationRequirementKind.AST,
                        stage=AgentValidationStage.POST_EXECUTION,
                        required=True,
                        blocking=True,
                        validator_ids=("ast_validator",),
                        operation_name=op_name,
                        operation_version=op_ver,
                    )
                )
                reqs.append(
                    ValidationRequirement(
                        requirement_id=f"req-unit-test-{op_slug}",
                        validation_kind=ValidationRequirementKind.UNIT_TEST,
                        stage=AgentValidationStage.POST_EXECUTION,
                        required=True,
                        blocking=True,
                        validator_ids=("affected_tests_step",),
                        operation_name=op_name,
                        operation_version=op_ver,
                    )
                )

        elif stage == AgentValidationStage.PRE_COMMIT:
            if is_publish or commit_gate_required or not is_read_only:
                reqs.append(
                    ValidationRequirement(
                        requirement_id=f"req-commit-gate-{op_slug}",
                        validation_kind=ValidationRequirementKind.COMMIT_GATE,
                        stage=AgentValidationStage.PRE_COMMIT,
                        required=True,
                        blocking=True,
                        operation_name=op_name,
                        operation_version=op_ver,
                    )
                )

        return tuple(reqs)


class AgentValidationPolicyAdapter:
    """Adapts runtime policies and contexts to produce a cumulative ValidationPolicySelection."""

    def __init__(self, resolver: ValidationRequirementResolver | None = None) -> None:
        self._resolver = resolver or ValidationRequirementResolver()

    def select_policy(
        self,
        operation_descriptor: OperationDescriptor | None = None,
        capability: OperationCapability | None = None,
        stage: AgentValidationStage = AgentValidationStage.PRE_EXECUTION,
        agent_definition: AgentDefinition | None = None,
        goal: Goal | None = None,
        agent_run: AgentRun | None = None,
        environment: str = "local",
        sensitivity: str = "medium",
        commit_gate_required: bool = False,
        is_rollback: bool = False,
        custom_requirements: tuple[ValidationRequirement, ...] = (),
    ) -> ValidationPolicySelection:
        try:
            resolved_reqs = self._resolver.resolve_requirements(
                operation_descriptor=operation_descriptor,
                capability=capability,
                stage=stage,
                agent_definition=agent_definition,
                goal=goal,
                agent_run=agent_run,
                environment=environment,
                sensitivity=sensitivity,
                commit_gate_required=commit_gate_required,
                is_rollback=is_rollback,
            )
        except Exception as exc:
            raise ValidationPolicySelectionError(
                f"Failed to resolve validation policy requirements: {exc}"
            ) from exc

        # Combine resolved requirements with custom requirements cumulatively (fail-safe)
        combined_reqs = list(resolved_reqs)
        for custom_req in custom_requirements:
            if not any(
                r.requirement_id == custom_req.requirement_id for r in combined_reqs
            ):
                combined_reqs.append(custom_req)

        policy_id = f"policy-val-{operation_descriptor.name if operation_descriptor else 'default'}-{stage.value}"
        rationale = (
            f"Stage: {stage.value}",
            f"Environment: {environment}",
            f"Sensitivity: {sensitivity}",
            f"Reversible: {operation_descriptor.reversible if operation_descriptor else 'unknown'}",
        )

        return ValidationPolicySelection(
            policy_id=policy_id,
            requirements=tuple(combined_reqs),
            rationale=rationale,
            cumulative=True,
        )
