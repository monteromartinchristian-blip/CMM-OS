"""Phase 10.5 – Tests for DomainManifestValidator."""

from __future__ import annotations

from pathlib import Path

from cmm.domains.validation_contracts import (
    DomainValidationExecutionContext,
    DomainValidationRequest,
)
from cmm.domains.validation_validators import DomainManifestValidator
from cmm.validation.context import ValidationContext
from cmm.validation.steps import ValidationStep, ValidationStepType


class DummyPack:
    def __init__(self) -> None:
        from types import SimpleNamespace

        self.manifest = SimpleNamespace(
            resources=[],
            rules=[],
            operations=[],
            workflows=[],
            validators=[],
            profiles=[],
            prompts=[],
        )
        self.definition = None


class TestDomainManifestValidator:
    def test_pack_none_returns_blocker(self) -> None:
        request = DomainValidationRequest(pack=None, root_path="/tmp")
        exec_ctx = DomainValidationExecutionContext(
            request=request,
            validation_context=ValidationContext(project_root=Path("/tmp")),
        )
        validator = DomainManifestValidator(exec_ctx)
        step = ValidationStep(
            name="domain.manifest",
            step_type=ValidationStepType.INTERNAL,
            required=True,
            dependencies=(),
        )
        result = validator.validate(None, step)
        assert result.status.value in ("failed",)
        assert any("Pack is None" in f.message for f in result.findings)

    def test_no_manifest_returns_blocker(self) -> None:
        pack = object()  # no manifest attribute
        request = DomainValidationRequest(pack=pack, root_path="/tmp")
        exec_ctx = DomainValidationExecutionContext(
            request=request,
            validation_context=ValidationContext(project_root=Path("/tmp")),
        )
        validator = DomainManifestValidator(exec_ctx)
        step = ValidationStep(
            name="domain.manifest",
            step_type=ValidationStepType.INTERNAL,
            required=True,
            dependencies=(),
        )
        result = validator.validate(None, step)
        assert result.status.value in ("failed",)

    def test_valid_manifest_passes(self) -> None:
        pack = DummyPack()
        request = DomainValidationRequest(pack=pack, root_path="/tmp")
        exec_ctx = DomainValidationExecutionContext(
            request=request,
            validation_context=ValidationContext(project_root=Path("/tmp")),
        )
        validator = DomainManifestValidator(exec_ctx)
        step = ValidationStep(
            name="domain.manifest",
            step_type=ValidationStepType.INTERNAL,
            required=True,
            dependencies=(),
        )
        result = validator.validate(None, step)
        assert result.status.value in ("passed", "warning")
