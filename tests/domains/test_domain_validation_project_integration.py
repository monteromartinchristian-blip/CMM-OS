"""Phase 10.43 — Project Domain mandatory Phase 7 validation (Task 6)."""

from __future__ import annotations

import pytest

from cmm.domains.project.operations import build_project_operation_definitions
from cmm.domains.validation_integration import (
    DomainValidationIntegrationError,
    is_project_domain_code_mutation,
    project_change_requires_validation,
    require_canonical_validation_success,
)
from cmm.domains.validation_policy_bindings import (
    PROJECT_DOMAIN_CHANGE_POLICY_NAME,
    build_project_domain_change_policy,
)
from cmm.validation import (
    CommitGateEvaluator,
    ValidationFinding,
    ValidationPolicy,
    ValidationResult,
    ValidationSeverity,
    ValidationStatus,
)
from cmm.validation.steps import ValidationStepResult


def _ops() -> dict:
    return {op.operation_id: op for op in build_project_operation_definitions()}


def _step(name: str, status=ValidationStatus.PASSED) -> ValidationStepResult:
    return ValidationStepResult(name=name, status=status)


def _validation_result(
    result_id: str = "vr-1",
    status=ValidationStatus.PASSED,
    steps: tuple = (),
    policy: str | None = "small_change",
) -> ValidationResult:
    return ValidationResult(
        id=result_id, status=status, policy=policy, steps=tuple(steps)
    )


class TestProjectDeclarationBinding:
    def test_project_modify_code_requires_project_domain_change_policy(self) -> None:
        ops = _ops()
        definition = ops["project.modify_code"]
        # Existing canonical declaration preserved: every Project operation
        # carries a validation policy ID, and modify_code specifically does.
        assert definition.validation_policy_id is not None
        assert definition.validation_policy_id == "validation.project.modify_code"
        # Phase 10.43 Project policy covers that declaration: building the
        # canonical ProjectDomainChangePolicy with the operation's ID yields
        # a canonical ValidationPolicy requiring it.
        policy = build_project_domain_change_policy(
            required_validation_ids=(definition.validation_policy_id,),
        )
        assert isinstance(policy, ValidationPolicy)
        assert policy.metadata["domain_policy_family"] == (
            PROJECT_DOMAIN_CHANGE_POLICY_NAME
        )
        assert definition.validation_policy_id in policy.required_steps

    def test_is_project_code_mutation_semantic(self) -> None:
        assert is_project_domain_code_mutation("project.modify_code") is True
        assert is_project_domain_code_mutation("project.run_validation") is False
        assert is_project_domain_code_mutation("project.prepare_commit") is False
        assert is_project_domain_code_mutation("") is False
        assert is_project_domain_code_mutation(None) is False

    def test_project_change_requires_validation(self) -> None:
        assert project_change_requires_validation("project.modify_code") is True
        # run_validation availability never exempts a later mutation.
        assert project_change_requires_validation("project.run_validation") is False


class TestProjectMutationValidation:
    def test_mutation_without_evidence_blocked(self) -> None:
        with pytest.raises(DomainValidationIntegrationError):
            require_canonical_validation_success(
                required_validation_ids=("syntax",),
                canonical_results=(),
            )

    def test_failing_affected_test_blocks_acceptance(self) -> None:
        failing = _validation_result(
            "vr-fail",
            status=ValidationStatus.FAILED,
            steps=(_step("syntax", ValidationStatus.FAILED),),
        )
        with pytest.raises(DomainValidationIntegrationError):
            require_canonical_validation_success(
                required_validation_ids=("syntax",),
                canonical_results=(failing,),
            )

    def test_corrected_regression_passes(self) -> None:
        passing = _validation_result(
            "vr-pass",
            status=ValidationStatus.PASSED,
            steps=(_step("syntax"), _step("ast")),
        )
        refs = require_canonical_validation_success(
            required_validation_ids=("syntax", "ast"),
            canonical_results=(passing,),
        )
        assert refs == ("vr-pass",)

    def test_run_validation_does_not_exempt_modify_code(self) -> None:
        # Historic/explicit validation operation availability is not
        # equivalent to post-change validation success: a new mutation still
        # carries its current required obligation.
        assert project_change_requires_validation("project.modify_code") is True
        with pytest.raises(DomainValidationIntegrationError):
            require_canonical_validation_success(
                required_validation_ids=("syntax",),
                canonical_results=(),
            )


class TestPrepareCommitGate:
    def test_blocking_finding_denies_commit_authorization(self) -> None:
        finding = ValidationFinding(
            code="TEST_FAIL",
            message="failing test",
            severity=ValidationSeverity.ERROR,
            source="pytest",
            blocking=True,
        )
        result = ValidationResult(
            id="vr-block",
            status=ValidationStatus.FAILED,
            policy="small_change",
            steps=(_step("syntax", ValidationStatus.FAILED),),
            blocking_findings=(finding,),
        )
        policy = build_project_domain_change_policy()
        gate = CommitGateEvaluator.evaluate(result, policy)
        assert gate.allowed is False

    def test_passing_validation_defers_to_gate(self) -> None:
        from cmm.validation.policy import DEFAULT_VALIDATION_POLICIES

        policy = DEFAULT_VALIDATION_POLICIES["small_change"]
        result = _validation_result(
            "vr-ok",
            status=ValidationStatus.PASSED,
            steps=(
                _step("formatter_check"),
                _step("syntax"),
                _step("ast"),
                _step("affected_tests"),
            ),
            policy="small_change",
        )
        gate = CommitGateEvaluator.evaluate(result, policy)
        # Existing gate decides eligibility; Domain code never issues its own
        # commit authorization (no Domain commit-gate symbol exists).
        assert gate.validation_result_id == "vr-ok"

    def test_domain_layer_has_no_commit_gate(self) -> None:
        import cmm.domains.validation_integration as mod

        assert not hasattr(mod, "DomainValidationCommitGate")
        assert not hasattr(mod, "issue_commit_authorization")


class TestImpactEscalation:
    def test_small_change_uses_lower_impact_set(self) -> None:
        policy = build_project_domain_change_policy(impact="small")
        assert policy.require_full_suite is False
        assert "syntax" in policy.required_steps

    def test_structural_change_includes_broader_checks(self) -> None:
        small = build_project_domain_change_policy(impact="small")
        structural = build_project_domain_change_policy(impact="structural")
        assert set(small.required_steps) <= set(structural.required_steps)
        assert len(structural.required_steps) > len(small.required_steps)

    def test_broad_change_escalates_to_full_suite(self) -> None:
        broad = build_project_domain_change_policy(impact="broad")
        assert broad.require_full_suite is True


class TestRealProjectMutationValidation:
    def test_real_project_modify_code_requires_current_phase7_validation(
        self, tmp_path
    ) -> None:
        from cmm.domains.enums import DomainOperationStatus
        from tests.domains.test_domain_validation_runtime_integration import (
            _modify_code_stack,
        )

        # Baseline: valid tree validates and the mutation is accepted.
        orchestrator, request, _, project_dir = _modify_code_stack(
            tmp_path, break_tree=False, break_on_execute=False
        )
        assert orchestrator.execute(request).status is DomainOperationStatus.COMPLETED

        # The mutation itself introduces a regression: current canonical
        # validation fails and accepted success becomes impossible.
        breaking_orch, breaking_request, _, _ = _modify_code_stack(
            tmp_path, break_tree=False, break_on_execute=True
        )
        breaking = breaking_orch.execute(breaking_request)
        assert breaking.status is not DomainOperationStatus.COMPLETED

        # Correcting the regression restores acceptance: validation is
        # re-executed against current state, never reused from history.
        (project_dir / "main.py").write_text("x = 1\n", encoding="utf-8")
        fixed_orch, fixed_request, _, _ = _modify_code_stack(
            tmp_path, break_tree=False, break_on_execute=False
        )
        assert (
            fixed_orch.execute(fixed_request).status is DomainOperationStatus.COMPLETED
        )

    def test_historic_project_run_validation_does_not_exempt_new_mutation(
        self, tmp_path
    ) -> None:
        from cmm.domains.enums import DomainOperationStatus
        from cmm.domains.operation_availability import (
            DomainOperationAvailabilityContext,
            DomainOperationAvailabilityResolver,
        )
        from cmm.domains.project.operations import build_project_operation_definitions
        from tests.domains.test_domain_validation_runtime_integration import (
            _modify_code_stack,
        )

        ops = {op.operation_id: op for op in build_project_operation_definitions()}
        run_validation = ops["project.run_validation"]
        # run_validation is registered and available: availability is not
        # evidence, and it never exempts a later mutation.
        resolver = DomainOperationAvailabilityResolver()
        availability = resolver.resolve(
            run_validation,
            DomainOperationAvailabilityContext(
                primary_domain_id=run_validation.domain_id,
                supporting_domain_ids=(),
                granted_permissions=(),
                denied_permissions=(),
                available_resources=run_validation.required_resources,
                capabilities=("execute", "transaction", "rollback", "validation"),
                available_validation_policy_ids=(
                    (run_validation.validation_policy_id,)
                    if run_validation.validation_policy_id
                    else ()
                ),
                available_rollback_policy_ids=(
                    (run_validation.rollback_policy_id,)
                    if run_validation.rollback_policy_id
                    else ()
                ),
                approval_status=None,
                approval_fingerprint=None,
                request_fingerprint="fp",
                metadata={},
            ),
        )
        assert availability.status is DomainOperationStatus.AVAILABLE

        orchestrator, request, _, _ = _modify_code_stack(
            tmp_path, break_tree=True, break_on_execute=False
        )
        blocked = orchestrator.execute(request)
        assert blocked.status is not DomainOperationStatus.COMPLETED
        assert blocked.metadata.get("validation_result_ids") != ()

    def test_project_prepare_commit_remains_owned_by_phase7_commit_gate(
        self, tmp_path
    ) -> None:
        from pathlib import Path

        from cmm.domains.validation_integration import (
            DomainValidationIntegrationError,
            require_canonical_validation_success,
        )
        from cmm.validation import (
            ValidationContext,
            build_default_validation_pipeline,
        )
        from cmm.validation.catalog import ast_step, syntax_step

        project_dir = tmp_path / "commitproj"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "main.py").write_text("def broken(:\n", encoding="utf-8")

        def _canonical_result():
            pipeline = build_default_validation_pipeline()
            context = ValidationContext(project_root=Path(project_dir))
            return pipeline.run(context, (syntax_step(), ast_step()))

        # Real canonical failure: no evidence to project, gate denies.
        failing = _canonical_result()
        assert failing.status.value == "failed"
        with pytest.raises(DomainValidationIntegrationError):
            require_canonical_validation_success(
                required_validation_ids=("syntax",),
                canonical_results=(failing,),
            )
        policy = build_project_domain_change_policy(impact="small")
        assert CommitGateEvaluator.evaluate(failing, policy).allowed is False

        # Corrected tree: real canonical evidence, existing gate decides.
        (project_dir / "main.py").write_text("x = 1\n", encoding="utf-8")
        passing = _canonical_result()
        assert passing.status.value == "passed"
        refs = require_canonical_validation_success(
            required_validation_ids=("syntax", "ast"),
            canonical_results=(passing,),
        )
        assert refs == (passing.id,)
        gate = CommitGateEvaluator.evaluate(passing, policy)
        assert gate.validation_result_id == passing.id
