"""Phase 10.5 – Tests for DomainDependenciesValidator."""

from __future__ import annotations

from pathlib import Path

from cmm.domains.validation_contracts import (
    DomainValidationExecutionContext,
    DomainValidationRequest,
)
from cmm.domains.validation_validators import DomainDependenciesValidator
from cmm.validation.context import ValidationContext
from cmm.validation.steps import ValidationStep, ValidationStepType


def _make_pack_with_deps(deps=None, opt_deps=None):
    from types import SimpleNamespace

    return SimpleNamespace(
        definition=SimpleNamespace(
            id="domain:test",
            version="1.0.0",
            resources=(),
            operations=(),
            workflows=(),
            permissions=(),
            dependencies=tuple(deps) if deps else (),
            optional_dependencies=tuple(opt_deps) if opt_deps else (),
        ),
        manifest=SimpleNamespace(
            domain_id="domain:test",
            package_version="1.0.0",
            resources={},
            operations={},
            workflows={},
        ),
    )


def _make_snapshot(records):
    from types import SimpleNamespace

    return SimpleNamespace(records=tuple(records))


def _make_record(domain_id, status="active"):
    from types import SimpleNamespace

    return SimpleNamespace(domain_id=domain_id, status=status)


class TestDomainDependenciesValidator:
    def test_pack_none_returns_blocker(self) -> None:
        request = DomainValidationRequest(pack=None, root_path="/tmp")
        exec_ctx = DomainValidationExecutionContext(
            request=request,
            validation_context=ValidationContext(project_root=Path("/tmp")),
        )
        validator = DomainDependenciesValidator(exec_ctx)
        step = ValidationStep(
            name="domain.dependencies",
            step_type=ValidationStepType.INTERNAL,
            required=True,
            dependencies=(),
        )
        result = validator.validate(None, step)
        assert result.status.value in ("failed",)

    def test_no_definition_returns_blocker(self) -> None:
        pack = object()
        request = DomainValidationRequest(pack=pack, root_path="/tmp")
        exec_ctx = DomainValidationExecutionContext(
            request=request,
            validation_context=ValidationContext(project_root=Path("/tmp")),
        )
        validator = DomainDependenciesValidator(exec_ctx)
        step = ValidationStep(
            name="domain.dependencies",
            step_type=ValidationStepType.INTERNAL,
            required=True,
            dependencies=(),
        )
        result = validator.validate(None, step)
        assert result.status.value in ("failed",)

    def test_missing_dep_found_in_snapshot(self) -> None:
        from types import SimpleNamespace

        Dep = SimpleNamespace(domain_id="dep:missing")
        pack = _make_pack_with_deps(deps=[Dep])
        snapshot = _make_snapshot([])
        request = DomainValidationRequest(
            pack=pack, root_path="/tmp", registry_snapshot=snapshot
        )
        exec_ctx = DomainValidationExecutionContext(
            request=request,
            validation_context=ValidationContext(project_root=Path("/tmp")),
        )
        validator = DomainDependenciesValidator(exec_ctx)
        step = ValidationStep(
            name="domain.dependencies",
            step_type=ValidationStepType.INTERNAL,
            required=True,
            dependencies=(),
        )
        result = validator.validate(None, step)
        assert any("Required dep missing" in f.message for f in result.findings)

    def test_disabled_dep_found(self) -> None:
        from types import SimpleNamespace

        Dep = SimpleNamespace(domain_id="dep:disabled")
        pack = _make_pack_with_deps(deps=[Dep])
        rec = _make_record("dep:disabled", status="disabled")
        snapshot = _make_snapshot([rec])
        request = DomainValidationRequest(
            pack=pack, root_path="/tmp", registry_snapshot=snapshot
        )
        exec_ctx = DomainValidationExecutionContext(
            request=request,
            validation_context=ValidationContext(project_root=Path("/tmp")),
        )
        validator = DomainDependenciesValidator(exec_ctx)
        step = ValidationStep(
            name="domain.dependencies",
            step_type=ValidationStepType.INTERNAL,
            required=True,
            dependencies=(),
        )
        result = validator.validate(None, step)
        assert any("disabled" in f.message.lower() for f in result.findings)

    def test_optional_missing_is_warning(self) -> None:
        from types import SimpleNamespace

        Dep = SimpleNamespace(domain_id="dep:optional-missing")
        pack = _make_pack_with_deps(opt_deps=[Dep])
        rec = _make_record("dep:other")
        snapshot = _make_snapshot([rec])
        request = DomainValidationRequest(
            pack=pack, root_path="/tmp", registry_snapshot=snapshot
        )
        exec_ctx = DomainValidationExecutionContext(
            request=request,
            validation_context=ValidationContext(project_root=Path("/tmp")),
        )
        validator = DomainDependenciesValidator(exec_ctx)
        step = ValidationStep(
            name="domain.dependencies",
            step_type=ValidationStepType.INTERNAL,
            required=True,
            dependencies=(),
        )
        result = validator.validate(None, step)
        warnings_only = [f for f in result.findings if not f.blocking]
        assert len(warnings_only) > 0

    def test_no_deps_passes(self) -> None:
        pack = _make_pack_with_deps(deps=[], opt_deps=[])
        request = DomainValidationRequest(pack=pack, root_path="/tmp")
        exec_ctx = DomainValidationExecutionContext(
            request=request,
            validation_context=ValidationContext(project_root=Path("/tmp")),
        )
        validator = DomainDependenciesValidator(exec_ctx)
        step = ValidationStep(
            name="domain.dependencies",
            step_type=ValidationStepType.INTERNAL,
            required=True,
            dependencies=(),
        )
        result = validator.validate(None, step)
        assert len(result.findings) == 0
