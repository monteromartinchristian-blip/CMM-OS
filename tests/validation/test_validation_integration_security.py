"""Security tests for Validation Integration (Subphase 7.13)."""

from pathlib import Path

import pytest

from cmm.validation.integration.contracts import ValidationEventPayload
from cmm.validation.integration.service import ValidationIntegrationService
from cmm.validation.interfaces.application import ValidationApplicationService


def test_security_path_traversal_prevention(tmp_path: Path):
    app_service = ValidationApplicationService(project_root=tmp_path)
    service = ValidationIntegrationService(application_service=app_service)

    outside_file = Path("/tmp/outside_secret.py")

    with pytest.raises(ValueError, match="outside project root"):
        service.validate_after_execution(
            project_root=tmp_path,
            changed_files=(outside_file,),
        )


def test_security_event_payload_secret_sanitization():
    payload = ValidationEventPayload(
        event_type="validation.started",
        validation_id="val-sec-1",
        metadata={
            "authorization_header": "Bearer secret_token_xyz",
            "db_password": "supersecretpassword",
            "user_email": "user@example.com",
        },
    )
    serialized = payload.serialize()
    meta = serialized["metadata"]

    assert "user_email" in meta
    assert "authorization_header" not in meta
    assert "db_password" not in meta
