"""Unit tests for ValidationCancellationRegistry and cancellation (Phase 7.12)."""

from __future__ import annotations

from pathlib import Path

from cmm.validation import (
    StartValidationRequest,
    ValidationApplicationService,
    ValidationCancellationRegistry,
)


def test_cancellation_registry_basic() -> None:
    reg = ValidationCancellationRegistry()
    token = reg.register("val-123")
    assert token.is_cancelled() is False

    assert reg.cancel("val-123") is True
    assert token.is_cancelled() is True

    assert reg.cancel("val-nonexistent") is False
    reg.unregister("val-123")
    assert reg.get_token("val-123") is None


import pytest

from cmm.validation import ValidationNotFoundError


def test_service_cancel_validation(tmp_path: Path) -> None:
    (tmp_path / "cmm").mkdir()
    (tmp_path / "cmm" / "__init__.py").write_text("# init")

    service = ValidationApplicationService(project_root=tmp_path)
    req = StartValidationRequest(project_root=tmp_path, policy_name="small_change")
    res = service.start_validation(req)

    # Token is cleaned up after completion
    assert service.cancellation_registry.get_token(res.validation_id) is None

    # Cancel finished execution is idempotent and returns status
    cancel_resp1 = service.cancel_validation(res.validation_id)
    assert cancel_resp1.validation_id == res.validation_id

    cancel_resp2 = service.cancel_validation(res.validation_id)
    assert cancel_resp2.validation_id == res.validation_id

    # Cancel unknown execution raises ValidationNotFoundError
    with pytest.raises(ValidationNotFoundError):
        service.cancel_validation("val-unknown-99999")
