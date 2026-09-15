"""Phase 11.1 – Tests for the integration service registry.

This module also owns the structured composition error tests: the typed
platform exceptions are produced by registry and container operations, so their
safe-diagnostics contract is asserted next to the operations that raise them.
"""

from __future__ import annotations

import pytest

from cmm.platform.errors import (
    CircularDependencyError,
    ContainerNotReadyError,
    DuplicateAuthorityError,
    DuplicateServiceError,
    FrozenServiceRegistryError,
    IncompatibleContractError,
    InvalidConfigurationError,
    InvalidReplacementError,
    MissingDependencyError,
    PlatformCompositionError,
)

TYPED_ERRORS = (
    DuplicateServiceError,
    MissingDependencyError,
    IncompatibleContractError,
    CircularDependencyError,
    DuplicateAuthorityError,
    InvalidReplacementError,
    InvalidConfigurationError,
    ContainerNotReadyError,
    FrozenServiceRegistryError,
)


# ── Structured platform composition errors ───────────────────────────────────


def test_platform_composition_error_exposes_safe_error_result() -> None:
    error = PlatformCompositionError(
        code="MISSING_DEPENDENCY",
        message="Required service is missing",
        category="composition",
        details={"service_id": "agent.runtime"},
    )

    assert error.result.code == "MISSING_DEPENDENCY"
    assert error.result.details == {"service_id": "agent.runtime"}
    assert "traceback" not in error.result.details


def test_platform_composition_error_details_are_immutable() -> None:
    source = {"service_id": "agent.runtime"}
    error = PlatformCompositionError(
        code="MISSING_DEPENDENCY",
        message="Required service is missing",
        category="composition",
        details=source,
    )

    source["injected"] = "later"

    assert dict(error.result.details) == {"service_id": "agent.runtime"}

    with pytest.raises(TypeError):
        error.result.details["injected"] = "later"  # type: ignore[index]


def test_platform_composition_error_rejects_non_string_details() -> None:
    with pytest.raises(TypeError):
        PlatformCompositionError(
            code="MISSING_DEPENDENCY",
            message="Required service is missing",
            category="composition",
            details={"service": object()},  # type: ignore[dict-item]
        )


def test_platform_composition_error_does_not_serialize_runtime_objects() -> None:
    """No arbitrary exception object may reach the public error result."""

    inner = RuntimeError("secret internal detail")
    error = PlatformCompositionError(
        code="COMPOSITION_FAILED",
        message="Composition failed",
        category="composition",
    )

    assert error.result.details == {}
    assert inner not in error.args
    assert error.__cause__ is None
    assert "secret internal detail" not in str(error)


def test_platform_composition_error_message_is_safe() -> None:
    error = PlatformCompositionError(
        code="MISSING_DEPENDENCY",
        message="Required service is missing",
        category="composition",
    )

    assert str(error) == "Required service is missing"
    assert "Traceback" not in str(error)


@pytest.mark.parametrize("error_type", TYPED_ERRORS)
def test_every_typed_error_carries_a_structured_result(
    error_type: type[PlatformCompositionError],
) -> None:
    error = error_type("deterministic diagnostic")

    assert isinstance(error, PlatformCompositionError)
    assert isinstance(error, Exception)
    assert error.result.code
    assert error.result.category
    assert error.result.message == "deterministic diagnostic"
    assert dict(error.result.details) == {}


def test_typed_errors_use_distinct_stable_codes() -> None:
    codes = {error_type.default_code for error_type in TYPED_ERRORS}

    assert len(codes) == len(TYPED_ERRORS)
    assert all(code.isupper() for code in codes)


def test_typed_errors_expose_stable_categories() -> None:
    assert DuplicateServiceError.default_category == "composition"
    assert CircularDependencyError.default_category == "composition"
    assert InvalidConfigurationError.default_category == "configuration"
    assert ContainerNotReadyError.default_category == "lifecycle"
    assert FrozenServiceRegistryError.default_category == "lifecycle"


def test_typed_error_accepts_safe_structured_details() -> None:
    error = MissingDependencyError(
        "Required service is missing",
        details={
            "service_id": "agent.runtime",
            "dependency_id": "validation.application",
        },
    )

    assert error.result.code == "MISSING_DEPENDENCY"
    assert error.result.details["service_id"] == "agent.runtime"
    assert error.result.details["dependency_id"] == "validation.application"
