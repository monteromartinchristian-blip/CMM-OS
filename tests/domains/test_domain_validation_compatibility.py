"""Phase 10.5 – Tests for DomainCompatibilityValidator and _version_matches."""

from __future__ import annotations

from pathlib import Path

from cmm.domains.validation_contracts import (
    DomainValidationExecutionContext,
    DomainValidationRequest,
)
from cmm.domains.validation_validators import (
    DomainCompatibilityValidator,
    _version_matches,
)
from cmm.validation.context import ValidationContext
from cmm.validation.steps import ValidationStep, ValidationStepType


class TestVersionMatches:
    """Tests for _version_matches helper."""

    def test_exact_match(self) -> None:
        assert _version_matches("1.0.0", "1.0.0") is True

    def test_gt_match(self) -> None:
        assert _version_matches("2.0.0", ">1.0.0") is True

    def test_lt_match(self) -> None:
        assert _version_matches("0.5.0", "<1.0.0") is True

    def test_gte_match(self) -> None:
        assert _version_matches("1.0.0", ">=1.0.0") is True
        assert _version_matches("2.0.0", ">=1.0.0") is True

    def test_lte_match(self) -> None:
        assert _version_matches("1.0.0", "<=1.0.0") is True
        assert _version_matches("0.9.0", "<=1.0.0") is True

    def test_neq_match(self) -> None:
        assert _version_matches("2.0.0", "!=1.0.0") is True
        assert _version_matches("1.0.0", "!=1.0.0") is False

    def test_gt_fail(self) -> None:
        assert _version_matches("1.0.0", ">2.0.0") is False

    def test_lt_fail(self) -> None:
        assert _version_matches("2.0.0", "<1.0.0") is False

    def test_constraint_empty(self) -> None:
        result = _version_matches("1.0.0", "   \t")
        # Empty/whitespace constraint: strip gives "", parse_semver("") raises -> None
        assert result is None

    def test_version_invalid(self) -> None:
        assert _version_matches("not-a-version", ">=1.0.0") is None

    def test_constraint_invalid(self) -> None:
        assert _version_matches("1.0.0", "xyz1.0.0") is None

    def test_operator_unknown_not_fail_open(self) -> None:
        # Unknown operators are treated as exact match (fallthrough)
        result = _version_matches("1.0.0", "?1.0.0")
        # Should not silently pass
        assert result is None

    def test_tilde_match(self) -> None:
        assert _version_matches("1.2.3", "~=1.0.0") is True
        assert _version_matches("2.0.0", "~=1.0.0") is False

    def test_no_leading_whitespace_sensitivity(self) -> None:
        assert _version_matches("1.0.0", "  >=1.0.0") is True


class TestDomainCompatibilityValidator:
    def test_pack_none_returns_blocker(self) -> None:
        request = DomainValidationRequest(pack=None, root_path="/tmp")
        exec_ctx = DomainValidationExecutionContext(
            request=request,
            validation_context=ValidationContext(project_root=Path("/tmp")),
        )
        validator = DomainCompatibilityValidator(exec_ctx)
        step = ValidationStep(
            name="domain.compatibility",
            step_type=ValidationStepType.INTERNAL,
            required=True,
            dependencies=(),
        )
        result = validator.validate(None, step)
        assert result.status.value in ("failed",)

    def test_no_manifest_returns_blocker(self) -> None:
        pack = object()
        request = DomainValidationRequest(pack=pack, root_path="/tmp")
        exec_ctx = DomainValidationExecutionContext(
            request=request,
            validation_context=ValidationContext(project_root=Path("/tmp")),
        )
        validator = DomainCompatibilityValidator(exec_ctx)
        step = ValidationStep(
            name="domain.compatibility",
            step_type=ValidationStepType.INTERNAL,
            required=True,
            dependencies=(),
        )
        result = validator.validate(None, step)
        assert result.status.value in ("failed",)

    def test_no_compatibility_passes(self) -> None:
        from types import SimpleNamespace

        pack = SimpleNamespace(
            definition=None,
            manifest=SimpleNamespace(
                domain_id="domain:test",
                package_version="1.0.0",
                compatibility=None,
            ),
        )
        request = DomainValidationRequest(pack=pack, root_path="/tmp")
        exec_ctx = DomainValidationExecutionContext(
            request=request,
            validation_context=ValidationContext(project_root=Path("/tmp")),
        )
        validator = DomainCompatibilityValidator(exec_ctx)
        step = ValidationStep(
            name="domain.compatibility",
            step_type=ValidationStepType.INTERNAL,
            required=True,
            dependencies=(),
        )
        result = validator.validate(None, step)
        assert result.status.value in ("passed",)
