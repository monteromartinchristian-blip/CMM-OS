from datetime import datetime, timezone

import pytest

from cmm.validation.commit_gate.authorization import CommitAuthorization
from cmm.validation.errors import ValidationContractError


def test_commit_authorization_valid() -> None:
    now = datetime.now(timezone.utc)
    auth = CommitAuthorization(
        authorized=True,
        actor="human:christian",
        requested_at=now,
        reason="Manual approval after continuous validation",
        validation_result_id="val-123",
        metadata={"session_id": "s-456"},
    )

    assert auth.authorized is True
    assert auth.actor == "human:christian"
    assert auth.validation_result_id == "val-123"

    serialized = auth.serialize()
    assert serialized["actor"] == "human:christian"
    assert serialized["authorized"] is True

    roundtrip = CommitAuthorization.from_mapping(serialized)
    assert roundtrip.actor == "human:christian"
    assert roundtrip.authorized is True
    assert roundtrip.validation_result_id == "val-123"


def test_commit_authorization_invalid_actor() -> None:
    with pytest.raises(ValidationContractError, match="actor must not be empty"):
        CommitAuthorization(authorized=True, actor="")

    with pytest.raises(ValidationContractError, match="actor must not be empty"):
        CommitAuthorization(authorized=True, actor="   ")
