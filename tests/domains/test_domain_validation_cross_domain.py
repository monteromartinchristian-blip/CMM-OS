"""Phase 10.43 — Workflow and cross-domain validation composition (Task 5)."""

from __future__ import annotations

import pytest

from cmm.domains.validation_integration import (
    DomainValidationIntegrationError,
    compose_effective_validation_ids,
    is_ignored_caller_validation_metadata,
    require_canonical_validation_success,
)
from cmm.domains.validation_policy_bindings import (
    build_cross_domain_execution_policy,
    build_domain_workflow_policy,
    compose_required_validation_ids,
)
from cmm.validation import ValidationResult, ValidationStatus
from cmm.validation.steps import ValidationStepResult


def _step(name: str) -> ValidationStepResult:
    return ValidationStepResult(name=name, status=ValidationStatus.PASSED)


def _result(result_id: str, steps: tuple) -> ValidationResult:
    return ValidationResult(id=result_id, status=ValidationStatus.PASSED, steps=steps)


class TestWorkflowObligationPreservation:
    def test_workflow_policy_preserves_required_ids(self) -> None:
        policy = build_domain_workflow_policy(
            required_validation_ids=("parent.validation", "child.validation")
        )
        assert set(policy.required_steps) == {
            "parent.validation",
            "child.validation",
        }

    def test_phase_1042_operation_semantics_preserve_validation(self) -> None:
        # Phase 10.42 remains canonical owner: required_validations carry the
        # operation validation_policy_id into planning without 10.43 replanning.
        from cmm.agent_runtime.enums import PolicyRiskLevel
        from cmm.domains.enums import DomainOperationType
        from cmm.domains.operation_contracts import DomainOperationDefinition
        from cmm.domains.planner_workflow_integration import _operation_semantics

        definition = DomainOperationDefinition(
            operation_id="test.op",
            domain_id="domain:test",
            version="1.0.0",
            name="op",
            description="test",
            operation_type=DomainOperationType.READ,
            risk_level=PolicyRiskLevel.LOW,
            reversible=True,
            requires_approval=False,
            validation_policy_id="parent.validation",
            rollback_policy_id="rollback.test.op",
            enabled=True,
            metadata={},
        )
        semantics = _operation_semantics(definition, ())
        assert semantics["required_validations"] == ["parent.validation"]

    def test_ineligible_optional_branch_invents_nothing(self) -> None:
        # An empty/optional workflow contributes no obligations.
        policy = build_domain_workflow_policy(required_validation_ids=())
        assert policy.required_steps == ()
        assert compose_effective_validation_ids(workflow_required=()) == ()


class TestCrossDomainComposition:
    def test_deterministic_restrictive_union(self) -> None:
        effective = compose_effective_validation_ids(
            primary_required=("domain.contracts", "domain.permissions"),
            supporting_required=("domain.permissions", "health.safety.validation"),
            operation_required=("operation.output.validation",),
            workflow_required=("workflow.result.validation",),
        )
        assert effective == (
            "domain.contracts",
            "domain.permissions",
            "health.safety.validation",
            "operation.output.validation",
            "workflow.result.validation",
        )
        # Deterministic: same inputs in different call order yield same output.
        reordered = compose_effective_validation_ids(
            workflow_required=("workflow.result.validation",),
            operation_required=("operation.output.validation",),
            supporting_required=("health.safety.validation", "domain.permissions"),
            primary_required=("domain.permissions", "domain.contracts"),
        )
        assert reordered == effective

    def test_supporting_cannot_weaken_primary(self) -> None:
        effective = compose_effective_validation_ids(
            primary_required=("domain.contracts", "domain.permissions"),
            supporting_required=("domain.permissions",),
        )
        assert "domain.contracts" in effective
        assert "domain.permissions" in effective

    def test_policy_builder_composes_monotonically(self) -> None:
        policy = build_cross_domain_execution_policy(
            primary_required=("domain.contracts", "domain.permissions"),
            supporting_required=("domain.permissions", "health.safety.validation"),
            operation_required=("operation.output.validation",),
            workflow_required=("workflow.result.validation",),
        )
        assert tuple(policy.required_steps) == (
            "domain.contracts",
            "domain.permissions",
            "health.safety.validation",
            "operation.output.validation",
            "workflow.result.validation",
        )

    def test_caller_metadata_cannot_remove_obligations(self) -> None:
        for key in (
            "required_validation_ids",
            "skip_validation",
            "validation_passed",
            "trust",
            "approval",
        ):
            assert is_ignored_caller_validation_metadata(key) is True
        # Host-derived composition never consults caller metadata: even when
        # caller claims empty/skipped, effective obligations remain.
        host_effective = compose_effective_validation_ids(
            primary_required=("domain.contracts",),
            operation_required=("operation.output.validation",),
        )
        assert host_effective == ("domain.contracts", "operation.output.validation")
        # A caller-supplied empty set is not an input to the composer at all;
        # composing with no groups yields empty, but composing with host
        # groups always preserves them (monotonic).
        assert set(host_effective) <= set(
            compose_required_validation_ids(host_effective, ("domain.contracts",))
        )

    def test_unknown_mandatory_id_fails_closed(self) -> None:
        effective = compose_effective_validation_ids(
            primary_required=("unknown.required.validation",),
        )
        assert effective == ("unknown.required.validation",)
        # The unknown ID is preserved (not silently dropped) and validation
        # fails closed for lack of evidence.
        with pytest.raises(DomainValidationIntegrationError):
            require_canonical_validation_success(
                required_validation_ids=effective,
                canonical_results=(),
            )

    def test_duplicate_declarations_create_single_truth(self) -> None:
        effective = compose_effective_validation_ids(
            primary_required=("domain.contracts",),
            supporting_required=("domain.contracts",),
            operation_required=("domain.contracts",),
            workflow_required=("domain.contracts",),
        )
        assert effective == ("domain.contracts",)
        canonical = _result("vr-1", steps=(_step("domain.contracts"),))
        refs = require_canonical_validation_success(
            required_validation_ids=effective,
            canonical_results=(canonical,),
        )
        # One effective ID → one canonical execution reference, no Domain-level
        # copied duplicate truth.
        assert refs == ("vr-1",)

    def test_full_seven_group_union(self) -> None:
        effective = compose_effective_validation_ids(
            global_required=("global.mandatory",),
            primary_required=("domain.contracts",),
            supporting_required=("domain.permissions",),
            operation_required=("operation.output.validation",),
            workflow_required=("workflow.result.validation",),
            dependency_required=("dependency.validation",),
            project_required=("project.validation",),
        )
        assert effective == (
            "dependency.validation",
            "domain.contracts",
            "domain.permissions",
            "global.mandatory",
            "operation.output.validation",
            "project.validation",
            "workflow.result.validation",
        )
