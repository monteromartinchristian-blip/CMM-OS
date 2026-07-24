from __future__ import annotations

from pathlib import Path

import pytest

from cmm.validation.context import ValidationContext
from cmm.validation.enums import ValidationStatus
from cmm.validation.errors import ValidationContractError
from cmm.validation.policy import (
    DEFAULT_VALIDATION_POLICIES,
    ValidationPolicy,
    resolve_validation_policy,
)
from cmm.validation.testing_defaults import default_validation_steps


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_validation_policy_contract_serializes_roundtrip() -> None:
    policy = ValidationPolicy(
        name="small_change",
        required_steps=("formatter_check", "lint", "syntax", "ast", "affected_tests"),
        optional_steps=(),
        stop_on_blocking_failure=True,
        require_full_suite=False,
        allow_commit=True,
        metadata={"source": "roadmap"},
    )

    assert policy.serialize() == {
        "name": "small_change",
        "required_steps": ["formatter_check", "lint", "syntax", "ast", "affected_tests"],
        "optional_steps": [],
        "stop_on_blocking_failure": True,
        "require_full_suite": False,
        "allow_commit": True,
        "metadata": {"source": "roadmap"},
    }

    restored = ValidationPolicy.from_mapping(policy.serialize())
    assert restored == policy


@pytest.mark.parametrize(
    "policy_name",
    (
        "documentation_only",
        "small_change",
        "structural_change",
        "imports_change",
        "public_api_change",
        "kernel_change",
        "release",
        "autonomous_execution",
    ),
)
def test_initial_validation_policies_are_present(policy_name: str) -> None:
    assert policy_name in DEFAULT_VALIDATION_POLICIES


def test_requested_policy_wins_over_change_type(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "module.py", "def func(x):\n    return x\n")
    ctx = ValidationContext(
        project_root=tmp_path,
        changed_files=(Path("src/module.py"),),
        change_type="release",
        requested_policy="small_change",
    )

    policy = resolve_validation_policy(ctx)

    assert policy is not None
    assert policy.name == "small_change"
    assert policy.required_steps == ("formatter_check", "lint", "syntax", "ast", "affected_tests")


def test_change_type_can_select_validation_policy(tmp_path: Path) -> None:
    _write(tmp_path / "cmm" / "core" / "module.py", "def func(x):\n    return x\n")
    ctx = ValidationContext(
        project_root=tmp_path,
        changed_files=(Path("cmm/core/module.py"),),
        change_type="imports_change",
    )

    policy = resolve_validation_policy(ctx)

    assert policy is not None
    assert policy.name == "imports_change"
    assert "import_analysis" in policy.required_steps


def test_unknown_requested_policy_is_rejected(tmp_path: Path) -> None:
    ctx = ValidationContext(project_root=tmp_path, requested_policy="does_not_exist")

    with pytest.raises(ValidationContractError):
        resolve_validation_policy(ctx)


def test_small_change_policy_limits_validation_steps(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "module.py", "def func(x):\n    return x\n")
    _write(tmp_path / "tests" / "test_module.py", "def test_func():\n    assert True\n")
    ctx = ValidationContext(
        project_root=tmp_path,
        changed_files=(Path("src/module.py"),),
        change_type="small_change",
    )

    steps = default_validation_steps(ctx)

    assert [step.name for step in steps] == [
        "syntax",
        "formatter_check",
        "lint_check",
        "ast",
        "affected_tests",
    ]


def test_structural_change_policy_includes_static_analysis_and_test_scopes(tmp_path: Path) -> None:
    _write(tmp_path / "cmm" / "core" / "module.py", "def func(x):\n    return x\n")
    _write(tmp_path / "tests" / "core" / "test_module.py", "def test_unit():\n    assert True\n")
    _write(
        tmp_path / "tests" / "core" / "test_module_integration.py",
        "def test_integration():\n    assert True\n",
    )
    ctx = ValidationContext(
        project_root=tmp_path,
        changed_files=(Path("cmm/core/module.py"),),
        change_type="structural_change",
    )

    steps = default_validation_steps(ctx)
    names = [step.name for step in steps]

    assert names[:4] == [
        "syntax",
        "formatter_check",
        "lint_check",
        "ast",
    ]
    assert "change_impact" in names
    assert names.index("change_impact") < names.index("type_check")
    assert names.index("type_check") < names.index("dead_code")


def test_imports_change_policy_uses_lint_alias_and_change_impact(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "module.py", "from pkg.other import thing\n")
    _write(tmp_path / "tests" / "test_module.py", "def test_func():\n    assert True\n")
    ctx = ValidationContext(
        project_root=tmp_path,
        changed_files=(Path("pkg/module.py"),),
        change_type="imports_change",
    )

    steps = default_validation_steps(ctx)
    names = [step.name for step in steps]

    assert names == [
        "syntax",
        "formatter_check",
        "lint_check",
        "ast",
        "change_impact",
        "affected_tests",
    ]


def test_public_api_change_policy_requires_full_suite(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "module.py", "def func(x):\n    return x\n")
    ctx = ValidationContext(
        project_root=tmp_path,
        changed_files=(Path("pkg/module.py"),),
        change_type="public_api_change",
    )

    policy = resolve_validation_policy(ctx)
    assert policy is not None
    assert policy.require_full_suite is True

    steps = default_validation_steps(ctx)
    assert any(step.name == "full_suite" for step in steps)


def test_policy_context_can_authorize_commit_after_success(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "module.py", "def func(x):\n    return x\n")
    _write(tmp_path / "tests" / "test_module.py", "def test_func():\n    assert True\n")
    ctx = ValidationContext(
        project_root=tmp_path,
        changed_files=(Path("src/module.py"),),
        change_type="small_change",
        allow_commit=True,
    )

    from cmm.validation import ValidationExecutor, ValidationPipeline
    from cmm.validation.enums import ValidationStatus
    from cmm.validation.registry import ValidationRegistry
    from cmm.validation.steps import ValidationStep, ValidationStepResult, ValidationStepType

    class PassValidator:
        def validate(self, context: ValidationContext, step: ValidationStep):
            return ValidationStepResult(name=step.name, status=ValidationStatus.PASSED)

    registry = ValidationRegistry()
    for name in ("syntax", "formatter_check", "lint_check", "ast", "affected_tests"):
        registry.register(name, PassValidator())

    pipeline = ValidationPipeline(executor=ValidationExecutor(), registry=registry)
    steps = (
        ValidationStep(name="syntax", step_type=ValidationStepType.INTERNAL),
        ValidationStep(name="formatter_check", step_type=ValidationStepType.INTERNAL, dependencies=("syntax",)),
        ValidationStep(name="lint_check", step_type=ValidationStepType.INTERNAL, dependencies=("syntax",)),
        ValidationStep(name="ast", step_type=ValidationStepType.INTERNAL, dependencies=("syntax",)),
        ValidationStep(name="affected_tests", step_type=ValidationStepType.INTERNAL),
    )
    result = pipeline.run(ctx, steps)

    assert result.status == ValidationStatus.PASSED
    assert result.policy == "small_change"
    assert result.can_commit is True


def test_policy_alias_resolution() -> None:
    ctx = ValidationContext(project_root=Path("."), requested_policy="docs-only")
    policy = resolve_validation_policy(ctx)
    assert policy is not None
    assert policy.name == "documentation_only"

    ctx2 = ValidationContext(project_root=Path("."), requested_policy="smallchange")
    policy2 = resolve_validation_policy(ctx2)
    assert policy2 is not None
    assert policy2.name == "small_change"


def test_unknown_policy_alias_rejected() -> None:
    ctx = ValidationContext(project_root=Path("."), requested_policy="completely_unknown_policy_xyz")
    with pytest.raises(ValidationContractError, match="Unknown validation policy"):
        resolve_validation_policy(ctx)


def test_unknown_step_label_raises_contract_error() -> None:
    from cmm.validation.policy import expand_validation_step_labels
    with pytest.raises(ValidationContractError, match="Unknown validation step label 'nonexistent_label'"):
        expand_validation_step_labels("nonexistent_label")


def test_expand_step_labels_deduplication_and_order() -> None:
    from cmm.validation.policy import expand_validation_step_labels
    expanded = expand_validation_step_labels(("lint", "lint_check", "static_analysis", "syntax"))
    assert expanded == ("formatter_check", "lint_check", "change_impact", "type_check", "dead_code", "syntax")


def test_expand_step_labels_cyclic_alias_detection() -> None:
    from cmm.validation.policy import expand_validation_step_labels
    custom_aliases = {
        "step_a": ("step_b",),
        "step_b": ("step_a",),
    }
    with pytest.raises(ValidationContractError, match="Circular alias detected"):
        expand_validation_step_labels("step_a", aliases=custom_aliases)


def test_missing_required_step_raises_contract_error(tmp_path: Path) -> None:
    from cmm.validation.steps import ValidationStep, ValidationStepType
    from cmm.validation.testing_defaults import _select_policy_steps
    policy = ValidationPolicy(
        name="custom_strict",
        required_steps=("syntax", "ast"),
        optional_steps=(),
    )
    # Only provide syntax step, missing ast
    available_steps = (ValidationStep(name="syntax", step_type=ValidationStepType.INTERNAL),)
    with pytest.raises(ValidationContractError, match="Required validation step 'ast' for policy 'custom_strict' is missing"):
        _select_policy_steps(available_steps, policy)


def test_missing_optional_step_omitted_silently(tmp_path: Path) -> None:
    from cmm.validation.steps import ValidationStep, ValidationStepType
    from cmm.validation.testing_defaults import _select_policy_steps
    policy = ValidationPolicy(
        name="custom_optional",
        required_steps=("syntax",),
        optional_steps=("bandit",),
    )
    available_steps = (ValidationStep(name="syntax", step_type=ValidationStepType.INTERNAL),)
    selected = _select_policy_steps(available_steps, policy)
    assert [s.name for s in selected] == ["syntax"]


def test_select_policy_steps_includes_dependencies(tmp_path: Path) -> None:
    from cmm.validation.steps import ValidationStep, ValidationStepType
    from cmm.validation.testing_defaults import _select_policy_steps
    policy = ValidationPolicy(
        name="dep_test",
        required_steps=("formatter_check",),
    )
    available_steps = (
        ValidationStep(name="syntax", step_type=ValidationStepType.INTERNAL),
        ValidationStep(name="formatter_check", step_type=ValidationStepType.INTERNAL, dependencies=("syntax",)),
    )
    selected = _select_policy_steps(available_steps, policy)
    assert [s.name for s in selected] == ["syntax", "formatter_check"]


def test_can_commit_denied_by_policy(tmp_path: Path) -> None:
    from cmm.validation import ValidationExecutor, ValidationPipeline
    from cmm.validation.enums import ValidationStatus
    from cmm.validation.registry import ValidationRegistry
    from cmm.validation.steps import ValidationStep, ValidationStepResult, ValidationStepType

    ctx = ValidationContext(
        project_root=tmp_path,
        requested_policy="autonomous_execution",
        allow_commit=True,
    )

    class PassValidator:
        def validate(self, context: ValidationContext, step: ValidationStep):
            return ValidationStepResult(name=step.name, status=ValidationStatus.PASSED)

    registry = ValidationRegistry()
    for name in ("syntax", "lint_check", "ast", "change_impact", "security"):
        registry.register(name, PassValidator())

    pipeline = ValidationPipeline(executor=ValidationExecutor(), registry=registry)
    steps = (
        ValidationStep(name="syntax", step_type=ValidationStepType.INTERNAL),
        ValidationStep(name="lint_check", step_type=ValidationStepType.INTERNAL),
        ValidationStep(name="ast", step_type=ValidationStepType.INTERNAL),
        ValidationStep(name="change_impact", step_type=ValidationStepType.INTERNAL),
        ValidationStep(name="security", step_type=ValidationStepType.INTERNAL),
    )
    result = pipeline.run(ctx, steps)

    assert result.status == ValidationStatus.PASSED
    assert result.policy == "autonomous_execution"
    assert result.can_commit is False


def test_can_commit_denied_by_failed_result(tmp_path: Path) -> None:
    from cmm.validation import ValidationExecutor, ValidationPipeline
    from cmm.validation.enums import ValidationStatus
    from cmm.validation.findings import ValidationFinding, ValidationSeverity
    from cmm.validation.registry import ValidationRegistry
    from cmm.validation.steps import ValidationStep, ValidationStepResult, ValidationStepType

    ctx = ValidationContext(
        project_root=tmp_path,
        requested_policy="small_change",
        allow_commit=True,
    )

    class FailValidator:
        def validate(self, context: ValidationContext, step: ValidationStep):
            return ValidationStepResult(
                name=step.name,
                status=ValidationStatus.FAILED,
                findings=(
                    ValidationFinding(
                        code="TEST_FAIL",
                        message="Failed",
                        severity=ValidationSeverity.ERROR,
                        source="test",
                        blocking=True,
                    ),
                ),
            )

    registry = ValidationRegistry()
    registry.register("syntax", FailValidator())

    pipeline = ValidationPipeline(executor=ValidationExecutor(), registry=registry)
    steps = (ValidationStep(name="syntax", step_type=ValidationStepType.INTERNAL),)
    result = pipeline.run(ctx, steps)

    assert result.status == ValidationStatus.FAILED
    assert result.can_commit is False
