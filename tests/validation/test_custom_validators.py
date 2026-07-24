"""Comprehensive tests for custom validators (Phase 7.9 - Block 1)."""

from pathlib import Path
from typing import Any
import pytest

from cmm.validation import (
    CustomValidator,
    CustomValidatorRegistry,
    ValidationArtifact,
    ValidationContext,
    ValidationExecutor,
    ValidationFinding,
    ValidationPipeline,
    ValidationRegistry,
    ValidationRegistryError,
    ValidationSeverity,
    ValidationStatus,
    ValidationStep,
    ValidationStepResult,
    ValidationStepType,
    build_custom_validation_step,
    custom_validator_step,
)


# ============================================================================
# Helper Classes (Testing only)
# ============================================================================


class PassingValidator:
    name = "passing_rule"

    def validate(self, context: ValidationContext) -> ValidationStepResult:
        return ValidationStepResult(
            name="passing_rule",
            status=ValidationStatus.PASSED,
            metadata={"check": "passed"},
        )


class WarningValidator:
    name = "warning_rule"

    def validate(self, context: ValidationContext) -> ValidationStepResult:
        finding = ValidationFinding(
            code="WARN_CODE",
            message="Warning message",
            severity=ValidationSeverity.WARNING,
            source="custom.test",
            blocking=False,
        )
        return ValidationStepResult(
            name="warning_rule",
            status=ValidationStatus.WARNING,
            findings=(finding,),
        )


class BlockingValidator:
    name = "blocking_rule"

    def validate(self, context: ValidationContext) -> ValidationStepResult:
        finding = ValidationFinding(
            code="BLOCK_CODE",
            message="Blocking error",
            severity=ValidationSeverity.ERROR,
            source="custom.test",
            blocking=True,
        )
        return ValidationStepResult(
            name="blocking_rule",
            status=ValidationStatus.FAILED,
            findings=(finding,),
        )


class InvalidResultValidator:
    name = "invalid_result_rule"

    def validate(self, context: ValidationContext) -> Any:  # type: ignore
        return "invalid_string_result"


class SecretExplodingValidator:
    name = "secret_exploding_rule"

    def validate(self, context: ValidationContext) -> ValidationStepResult:
        raise RuntimeError("token=secret-value password=hunter2")


class ZeroDurationValidator:
    name = "zero_duration_rule"

    def validate(self, context: ValidationContext) -> ValidationStepResult:
        return ValidationStepResult(
            name="zero_duration_rule",
            status=ValidationStatus.PASSED,
            duration_ms=0,
        )


class ArtifactValidator:
    name = "artifact_rule"

    def validate(self, context: ValidationContext) -> ValidationStepResult:
        artifact = ValidationArtifact(
            id="art-1",
            kind="custom_report",
            source="custom.test",
            content={"info": "data"},
        )
        finding = ValidationFinding(
            code="INFO_CODE",
            message="Informational note",
            severity=ValidationSeverity.INFO,
            source="custom.test",
            blocking=False,
        )
        return ValidationStepResult(
            name="artifact_rule",
            status=ValidationStatus.PASSED,
            findings=(finding,),
            artifacts=(artifact,),
            metadata={"nested": {"key": "val"}},
        )


# ============================================================================
# Contract & Name Validation Tests
# ============================================================================


def test_contract_valid_validator():
    val = PassingValidator()
    assert isinstance(val, CustomValidator)
    assert val.name == "passing_rule"


@pytest.mark.parametrize(
    "valid_name",
    ["rule", "rule_1", "architecture-check", "planner_contract_2"],
)
def test_strict_name_validation_valid(valid_name: str):
    reg = CustomValidatorRegistry()

    class DynamicValidator:
        name = valid_name

        def validate(self, context: ValidationContext) -> ValidationStepResult:
            return ValidationStepResult(name=valid_name, status=ValidationStatus.PASSED)

    val = DynamicValidator()
    registered = reg.register(val)
    assert registered.name == valid_name
    assert reg.get(valid_name) is val


@pytest.mark.parametrize(
    "invalid_name",
    [
        "",
        "   ",
        "Rule",
        "foo bar",
        "foo/bar",
        "../foo",
        "foo.",
        ".foo",
        "foo:bar",
        "custom.foo",
        "_foo",
        "foo_",
        "-foo",
        "foo-",
    ],
)
def test_strict_name_validation_invalid(invalid_name: str):
    reg = CustomValidatorRegistry()

    class InvalidValidator:
        name = invalid_name

        def validate(self, context: ValidationContext) -> ValidationStepResult:
            return ValidationStepResult(name="test", status=ValidationStatus.PASSED)

    with pytest.raises(ValidationRegistryError) as exc_info:
        reg.register(InvalidValidator())
    assert exc_info.value.code == "invalid_custom_validator_name"


def test_contract_missing_validate_method():
    reg = CustomValidatorRegistry()

    class NoValidateValidator:
        name = "no_validate"

    with pytest.raises(ValidationRegistryError) as exc_info:
        reg.register(NoValidateValidator())  # type: ignore
    assert exc_info.value.code == "invalid_custom_validator"


def test_contract_validate_not_callable():
    reg = CustomValidatorRegistry()

    class NonCallableValidateValidator:
        name = "non_callable"
        validate = "not a method"

    with pytest.raises(ValidationRegistryError) as exc_info:
        reg.register(NonCallableValidateValidator())  # type: ignore
    assert exc_info.value.code == "invalid_custom_validator"


# ============================================================================
# Registry Tests
# ============================================================================


def test_registry_register_and_get():
    reg = CustomValidatorRegistry()
    val = PassingValidator()
    returned = reg.register(val)
    assert returned is val
    assert reg.get("passing_rule") is val
    assert reg.contains("passing_rule")
    assert "passing_rule" in reg
    assert len(reg) == 1


def test_registry_duplicate_registration_error():
    reg = CustomValidatorRegistry()
    val1 = PassingValidator()
    val2 = PassingValidator()
    reg.register(val1)

    with pytest.raises(ValidationRegistryError) as exc_info:
        reg.register(val2)
    assert exc_info.value.code == "duplicate_custom_validator"


def test_registry_require():
    reg = CustomValidatorRegistry()
    val = PassingValidator()
    reg.register(val)

    assert reg.require("passing_rule") is val

    with pytest.raises(ValidationRegistryError) as exc_info:
        reg.require("unknown_rule")
    assert exc_info.value.code == "unknown_custom_validator"


def test_registry_get_nonexistent():
    reg = CustomValidatorRegistry()
    assert reg.get("nonexistent") is None


def test_registry_unregister():
    reg = CustomValidatorRegistry()
    val = PassingValidator()
    reg.register(val)

    unregistered = reg.unregister("passing_rule")
    assert unregistered is val
    assert not reg.contains("passing_rule")
    assert len(reg) == 0

    with pytest.raises(ValidationRegistryError) as exc_info:
        reg.unregister("passing_rule")
    assert exc_info.value.code == "unknown_custom_validator"


def test_registry_names_and_validators_order():
    reg = CustomValidatorRegistry()
    v1 = PassingValidator()
    v2 = WarningValidator()
    v3 = BlockingValidator()

    reg.register(v1)
    reg.register(v2)
    reg.register(v3)

    assert reg.names() == ("passing_rule", "warning_rule", "blocking_rule")
    assert reg.validators() == (v1, v2, v3)
    assert list(iter(reg)) == ["passing_rule", "warning_rule", "blocking_rule"]


def test_registry_build_steps_unknown_and_duplicates():
    custom_reg = CustomValidatorRegistry()
    custom_reg.register(PassingValidator())
    custom_reg.register(WarningValidator())

    # Unknown step name raises unknown_custom_validator
    with pytest.raises(ValidationRegistryError) as exc_info:
        custom_reg.build_steps(["passing_rule", "unknown_rule"])
    assert exc_info.value.code == "unknown_custom_validator"

    # Duplicates are deduplicated in insertion order
    steps = custom_reg.build_steps(["passing_rule", "warning_rule", "passing_rule"])
    assert len(steps) == 2
    assert steps[0].name == "custom.passing_rule"
    assert steps[1].name == "custom.warning_rule"


# ============================================================================
# Adapter & Step Registration Collision Tests
# ============================================================================


def test_foo_produces_custom_foo():
    val = PassingValidator()
    step = build_custom_validation_step(val)
    assert step.name == "custom.passing_rule"
    assert step.step_type == ValidationStepType.INTERNAL


def test_custom_prefix_rejected_at_validator_creation():
    class CustomPrefixedValidator:
        name = "custom.foo"

        def validate(self, context: ValidationContext) -> ValidationStepResult:
            return ValidationStepResult(name="custom.foo", status=ValidationStatus.PASSED)

    with pytest.raises(ValidationRegistryError) as exc_info:
        build_custom_validation_step(CustomPrefixedValidator())
    assert exc_info.value.code == "invalid_custom_validator_name"


def test_no_silent_overwrite_in_validation_registry():
    val1 = PassingValidator()
    val_reg = ValidationRegistry()

    # Register first step
    step1 = build_custom_validation_step(val1, validation_registry=val_reg)
    original_handler = val_reg.get("custom.passing_rule")
    assert original_handler is not None

    # Idempotent re-registration of exact same validator instance works
    step1_again = build_custom_validation_step(val1, validation_registry=val_reg)
    assert step1_again.name == "custom.passing_rule"
    assert val_reg.get("custom.passing_rule") is original_handler

    # Attempting to register another validator under colliding step_name raises custom_validator_step_collision
    class CollidingPassingValidator:
        name = "passing_rule"

        def validate(self, context: ValidationContext) -> ValidationStepResult:
            return ValidationStepResult(name="passing_rule", status=ValidationStatus.PASSED)

    val2 = CollidingPassingValidator()
    with pytest.raises(ValidationRegistryError) as exc_info:
        build_custom_validation_step(val2, validation_registry=val_reg)

    assert exc_info.value.code == "custom_validator_step_collision"
    # Ensure original handler in validation_registry was NOT replaced
    assert val_reg.get("custom.passing_rule") is original_handler


# ============================================================================
# Mutation & Execution Sanitization Tests
# ============================================================================


def test_validator_name_mutation_detected(tmp_path: Path):
    val_reg = ValidationRegistry()
    val = PassingValidator()
    step = build_custom_validation_step(val, validation_registry=val_reg)
    ctx = ValidationContext(project_root=tmp_path)
    executor = ValidationExecutor()

    # Mutate validator.name after registration
    val.name = "mutated_rule"  # type: ignore

    res = executor.execute(ctx, step, val_reg)
    assert res.name == "custom.passing_rule"
    assert res.status == ValidationStatus.ERROR
    assert len(res.findings) == 1
    assert res.findings[0].code == "CUSTOM_VALIDATOR_NAME_MUTATED"
    assert res.metadata["error"] == "custom_validator_name_changed"
    assert res.metadata["registered_name"] == "passing_rule"
    assert res.metadata["current_name"] == "mutated_rule"


def test_exception_sanitization_and_no_secret_leak(tmp_path: Path):
    val_reg = ValidationRegistry()
    val = SecretExplodingValidator()
    step = build_custom_validation_step(val, validation_registry=val_reg)
    ctx = ValidationContext(project_root=tmp_path)
    executor = ValidationExecutor()

    res = executor.execute(ctx, step, val_reg)
    assert res.status == ValidationStatus.ERROR
    assert res.findings[0].code == "CUSTOM_VALIDATOR_EXECUTION_ERROR"
    assert res.metadata["error"] == "custom_validator_execution_error"
    assert res.metadata["exception_type"] == "RuntimeError"

    # Secrets MUST NOT leak in message, stderr, metadata or serialized result
    assert "secret-value" not in res.findings[0].message
    assert "hunter2" not in res.findings[0].message
    assert "secret-value" not in res.stderr
    assert "hunter2" not in res.stderr

    serialized = res.serialize()
    serialized_str = str(serialized)
    assert "secret-value" not in serialized_str
    assert "hunter2" not in serialized_str


def test_duration_measurement_when_result_has_zero(tmp_path: Path):
    val_reg = ValidationRegistry()
    val = ZeroDurationValidator()
    step = build_custom_validation_step(val, validation_registry=val_reg)
    ctx = ValidationContext(project_root=tmp_path)
    executor = ValidationExecutor()

    res = executor.execute(ctx, step, val_reg)
    assert res.status == ValidationStatus.PASSED
    assert res.duration_ms >= 0


# ============================================================================
# Pipeline Integration Tests
# ============================================================================


def test_pipeline_integration_passing(tmp_path: Path):
    custom_reg = CustomValidatorRegistry()
    custom_reg.register(PassingValidator())
    custom_reg.register(ArtifactValidator())

    val_reg = ValidationRegistry()
    steps = custom_reg.build_steps(
        ["passing_rule", "artifact_rule"],
        validation_registry=val_reg,
    )

    pipeline = ValidationPipeline(executor=ValidationExecutor(), registry=val_reg)
    ctx = ValidationContext(project_root=tmp_path, allow_commit=True, requested_policy="small_change")

    result = pipeline.run(ctx, steps)
    assert result.status == ValidationStatus.PASSED
    assert len(result.steps) == 2
    assert len(result.artifacts) == 1
    assert result.artifacts[0].id == "art-1"
    assert result.can_commit is True

    serialized = result.serialize()
    assert serialized["status"] == "passed"
    assert len(serialized["steps"]) == 2
    assert len(serialized["artifacts"]) == 1


def test_pipeline_integration_secret_exploding_sanitized_in_pipeline(tmp_path: Path):
    custom_reg = CustomValidatorRegistry()
    custom_reg.register(SecretExplodingValidator())

    val_reg = ValidationRegistry()
    step = custom_reg.build_step("secret_exploding_rule", validation_registry=val_reg)

    pipeline = ValidationPipeline(executor=ValidationExecutor(), registry=val_reg)
    ctx = ValidationContext(project_root=tmp_path, allow_commit=True, requested_policy="small_change")

    result = pipeline.run(ctx, [step])
    assert result.status == ValidationStatus.ERROR
    serialized = result.serialize()
    serialized_str = str(serialized)
    assert "secret-value" not in serialized_str
    assert "hunter2" not in serialized_str


def test_public_exports():
    import cmm.validation as val_mod

    assert hasattr(val_mod, "CustomValidator")
    assert hasattr(val_mod, "CustomValidatorRegistry")
    assert hasattr(val_mod, "build_custom_validation_step")
    assert hasattr(val_mod, "custom_validator_step")
    assert "CustomValidator" in val_mod.__all__
    assert "CustomValidatorRegistry" in val_mod.__all__
    assert "build_custom_validation_step" in val_mod.__all__
    assert "custom_validator_step" in val_mod.__all__
