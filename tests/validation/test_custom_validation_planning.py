"""Tests for Phase 7.9 Block 3: Custom validation planning, policies, selection, and pipeline integration."""

from __future__ import annotations

from pathlib import Path
import pytest

from cmm.validation import (
    DEFAULT_VALIDATION_POLICIES,
    CustomValidator,
    CustomValidatorRegistry,
    ValidationContext,
    ValidationContractError,
    ValidationExecutor,
    ValidationFinding,
    ValidationPipeline,
    ValidationPlan,
    ValidationPolicy,
    ValidationResult,
    ValidationSeverity,
    ValidationStatus,
    ValidationStepResult,
    build_default_custom_validator_registry,
    build_default_validation_plan,
    build_default_validation_registry,
    build_validation_plan,
    default_custom_validators,
    default_validation_policies,
    default_validation_steps,
    expand_validation_step_labels,
    validate_custom_policy,
)
from cmm.validation.custom_validators import (
    ProjectManifestValidator,
    ValidationContractValidator,
    PublicApiValidator,
    TestLayoutValidator,
)


class DummyPassCustomValidator:
    """Dummy custom validator that passes."""

    def __init__(self, name: str = "dummy_pass") -> None:
        self.name = name

    def validate(self, context: ValidationContext) -> ValidationStepResult:
        return ValidationStepResult(
            name=f"custom.{self.name}",
            status=ValidationStatus.PASSED,
            metadata={"dummy": "ok"},
        )


class DummyFailCustomValidator:
    """Dummy custom validator that fails."""

    def __init__(self, name: str = "dummy_fail") -> None:
        self.name = name

    def validate(self, context: ValidationContext) -> ValidationStepResult:
        finding = ValidationFinding(
            code="DUMMY_FAIL",
            message="Dummy validator intentionally failed",
            severity=ValidationSeverity.ERROR,
            source="custom.dummy_fail",
            blocking=True,
        )
        return ValidationStepResult(
            name=f"custom.{self.name}",
            status=ValidationStatus.FAILED,
            findings=(finding,),
        )


# ============================================================================
# 1. FINDINGS BLOQUEANTES EN CUSTOM VALIDATORS
# ============================================================================


def test_custom_validators_emit_blocking_findings_when_files_missing(
    tmp_path: Path,
) -> None:
    context = ValidationContext(project_root=tmp_path)

    # 1. ProjectManifestValidator
    res_manifest = ProjectManifestValidator().validate(context)
    assert res_manifest.status == ValidationStatus.FAILED
    assert any(
        f.blocking is True and f.code == "PROJECT_MANIFEST_MISSING"
        for f in res_manifest.findings
    )

    # 2. ValidationContractValidator
    res_contract = ValidationContractValidator().validate(context)
    assert res_contract.status == ValidationStatus.FAILED
    assert any(
        f.blocking is True and f.code == "VALIDATION_MODULE_MISSING"
        for f in res_contract.findings
    )

    # 3. TestLayoutValidator
    res_layout = TestLayoutValidator().validate(context)
    assert res_layout.status == ValidationStatus.FAILED
    assert any(
        f.blocking is True and f.code == "TEST_LAYOUT_DIRECTORY_MISSING"
        for f in res_layout.findings
    )


# ============================================================================
# 2. REGISTRO DE HANDLERS EN CATALOG & PLAN
# ============================================================================


def test_build_default_validation_registry_has_no_custom_handlers() -> None:
    registry = build_default_validation_registry()
    assert not any(name.startswith("custom.") for name in registry.names())


def test_build_default_validation_plan_contains_custom_handlers(tmp_path: Path) -> None:
    context = ValidationContext(project_root=tmp_path, requested_policy="small_change")
    plan = build_default_validation_plan(context)
    assert any(name.startswith("custom.") for name in plan.registry.names())
    assert plan.registry.has("custom.project_manifest")


# ============================================================================
# 3. COMPATIBILIDAD DE default_validation_steps
# ============================================================================


def test_default_validation_steps_returns_historical_builtins_no_custom(
    tmp_path: Path,
) -> None:
    context = ValidationContext(project_root=tmp_path, change_type="small_change")
    steps = default_validation_steps(context)

    step_names = [s.name for s in steps]
    assert set(step_names).issubset(
        {"syntax", "formatter_check", "lint_check", "ast", "affected_tests"}
    )
    assert not any(name.startswith("custom.") for name in step_names)


def test_build_default_validation_plan_contains_selected_custom(tmp_path: Path) -> None:
    context = ValidationContext(project_root=tmp_path, change_type="small_change")
    plan = build_default_validation_plan(context)

    plan_step_names = [s.name for s in plan.steps]
    assert "custom.project_manifest" in plan_step_names
    assert "custom.validation_contract" in plan_step_names
    assert "custom.public_api" in plan_step_names
    assert "custom.test_layout" in plan_step_names


# ============================================================================
# 4. UN SOLO ALIAS AGREGADO custom_checks & RESTRICCIÓN DE NOMBRES
# ============================================================================


def test_custom_checks_alias_expands_four_canonical_steps() -> None:
    expanded = expand_validation_step_labels("custom_checks")
    assert expanded == (
        "custom.project_manifest",
        "custom.validation_contract",
        "custom.public_api",
        "custom.test_layout",
    )


def test_removed_aliases_raise_unknown_label_error() -> None:
    for removed_alias in ("custom_validations", "cmm_contracts", "project_contracts"):
        with pytest.raises(
            ValidationContractError,
            match=f"Unknown validation step label '{removed_alias}'",
        ):
            expand_validation_step_labels(removed_alias)


def test_unprefixed_custom_name_in_requested_steps_raises_error(tmp_path: Path) -> None:
    context = ValidationContext(
        project_root=tmp_path,
        requested_steps=("project_manifest",),
    )
    with pytest.raises(
        ValidationContractError,
        match=r"Invalid custom step name 'project_manifest'\. Custom steps must use the canonical prefix 'custom\.project_manifest'\.",
    ):
        build_default_validation_plan(context)


def test_canonical_custom_name_works(tmp_path: Path) -> None:
    context = ValidationContext(
        project_root=tmp_path,
        requested_steps=("custom.project_manifest",),
    )
    plan = build_default_validation_plan(context)
    assert [s.name for s in plan.steps] == ["custom.project_manifest"]


# ============================================================================
# 5. DETECCIÓN DE CICLOS REALES
# ============================================================================


def test_real_circular_alias_raises_error() -> None:
    custom_aliases = {
        "step_a": ("step_b",),
        "step_b": ("step_a",),
    }
    with pytest.raises(
        ValidationContractError,
        match="Circular alias detected in validation step labels: step_a -> step_b -> step_a",
    ):
        expand_validation_step_labels("step_a", aliases=custom_aliases)


# ============================================================================
# 6. POLÍTICAS PREDETERMINADAS Y ASIGNACIÓN
# ============================================================================


def test_default_policy_table_custom_step_assignments() -> None:
    policies = default_validation_policies()

    # documentation_only
    doc = policies["documentation_only"]
    assert "custom.project_manifest" in doc.optional_steps

    # small_change
    small = policies["small_change"]
    assert "custom_checks" in small.optional_steps

    # structural_change
    struct = policies["structural_change"]
    assert "custom_checks" in struct.required_steps

    # imports_change
    imp = policies["imports_change"]
    assert "custom_checks" in imp.optional_steps

    # public_api_change
    pub = policies["public_api_change"]
    assert "custom.project_manifest" in pub.required_steps
    assert "custom.validation_contract" in pub.required_steps
    assert "custom.public_api" in pub.required_steps
    assert "custom.test_layout" in pub.optional_steps

    # kernel_change
    kernel = policies["kernel_change"]
    assert "custom_checks" in kernel.required_steps

    # release
    rel = policies["release"]
    assert "custom_checks" in rel.required_steps

    # full
    full_p = policies["full"]
    assert "custom_checks" in full_p.required_steps

    # autonomous_execution
    auto = policies["autonomous_execution"]
    assert "custom_checks" in auto.required_steps


# ============================================================================
# 7. REQUISITOS DE ValidationPlan Y REGISTRY CUSTOM EXPLÍCITO
# ============================================================================


def test_validation_plan_custom_registry_explicit_empty(tmp_path: Path) -> None:
    empty_reg = CustomValidatorRegistry()
    policy = ValidationPolicy(
        name="p", required_steps=(), optional_steps=("custom_checks",)
    )
    context = ValidationContext(project_root=tmp_path)
    plan = build_validation_plan(context, policy=policy, custom_registry=empty_reg)

    assert len(plan.selected_custom_validators) == 0
    assert len(plan.missing_optional_custom_validators) == 4


def test_validation_plan_custom_registry_explicit_missing_required_raises(
    tmp_path: Path,
) -> None:
    empty_reg = CustomValidatorRegistry()
    policy = ValidationPolicy(name="p", required_steps=("custom.project_manifest",))
    context = ValidationContext(project_root=tmp_path)
    with pytest.raises(
        ValidationContractError,
        match="Required custom validator 'project_manifest' for policy 'p' is not registered",
    ):
        build_validation_plan(context, policy=policy, custom_registry=empty_reg)


# ============================================================================
# 8. EJECUCIÓN PIPELINE END-TO-END
# ============================================================================


def test_pipeline_execution_with_custom_validators(tmp_path: Path) -> None:
    custom_reg = CustomValidatorRegistry()
    custom_reg.register(DummyPassCustomValidator("dummy_pass"))

    policy = ValidationPolicy(
        name="pipeline_policy",
        required_steps=("custom.dummy_pass",),
    )
    context = ValidationContext(project_root=tmp_path)
    plan = build_validation_plan(context, policy=policy, custom_registry=custom_reg)

    executor = ValidationExecutor()
    pipeline = ValidationPipeline(executor=executor, registry=plan.registry)
    result = pipeline.run(context, plan.steps)

    assert result.status == ValidationStatus.PASSED
    assert len(result.steps) == 1
    assert result.steps[0].name == "custom.dummy_pass"
    assert result.steps[0].status == ValidationStatus.PASSED


def test_pipeline_execution_custom_validator_failure(tmp_path: Path) -> None:
    custom_reg = CustomValidatorRegistry()
    custom_reg.register(DummyFailCustomValidator("dummy_fail"))

    policy = ValidationPolicy(
        name="fail_policy",
        required_steps=("custom.dummy_fail",),
    )
    context = ValidationContext(project_root=tmp_path)
    plan = build_validation_plan(context, policy=policy, custom_registry=custom_reg)

    executor = ValidationExecutor()
    pipeline = ValidationPipeline(executor=executor, registry=plan.registry)
    result = pipeline.run(context, plan.steps)

    assert result.status == ValidationStatus.FAILED
    assert result.can_commit is False
    assert len(result.blocking_findings) >= 1
    assert result.blocking_findings[0].code == "DUMMY_FAIL"
