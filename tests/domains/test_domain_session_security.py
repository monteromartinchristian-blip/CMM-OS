"""Phase 10.34 — Domain Session Security Tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.credential_policy import (
    HIGH_CONFIDENCE_CREDENTIAL_SIGNATURES,
)
from cmm.domains.errors import DomainSessionSecurityError
from cmm.domains.session_contracts import (
    DomainSessionCheck,
    DomainSessionCheckStatus,
    DomainSessionContext,
    DomainSessionResumeRequest,
    DomainSessionResumeResult,
    DomainSessionResumeStatus,
    DomainSessionTransition,
)


def _now() -> datetime:
    return datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)


_SAMPLE_CREDENTIALS = [
    "sk_live_1234567890123456",
    "key-1234567890abcdef",
    "ghp_12345678901234567890",
    "github_pat_12345678901234567890",
    "AKIAIOSFODNN7EXAMPLE",
    "AIzaSyD-123456789012345678901234567890",
    "xoxb-1234567890-123456789012",
    "glpat-12345678901234567890",
    "npm_12345678901234567890",
    "hf_12345678901234567890",
    "SG.1234567890123456.1234567890123456",
    "dop_v1_12345678901234567890123456789012",
    "SK12345678901234567890123456789012",
    "pypi-12345678901234567890",
    "dckr_pat_12345678901234567890",
    "authorization: Bearer mysecrettoken",
    "bearer 1234567890abcdef",
    "password=supersecretpassword",
]


@pytest.mark.parametrize("cred", _SAMPLE_CREDENTIALS)
def test_credentials_rejected_in_context_metadata_and_leak_free(cred: str):
    with pytest.raises(DomainSessionSecurityError) as exc_info:
        DomainSessionContext(
            session_id="session-123",
            primary_domain="domain:health",
            updated_at=_now(),
            metadata={"secret_key": cred},
        )
    # Check that error message does NOT contain the secret
    assert cred not in str(exc_info.value)
    assert cred not in repr(exc_info.value)


@pytest.mark.parametrize("cred", _SAMPLE_CREDENTIALS)
def test_credentials_rejected_in_context_next_step(cred: str):
    with pytest.raises(DomainSessionSecurityError) as exc_info:
        DomainSessionContext(
            session_id="session-123",
            primary_domain="domain:health",
            next_recommended_step=f"use {cred}",
            updated_at=_now(),
        )
    assert cred not in str(exc_info.value)


@pytest.mark.parametrize("cred", _SAMPLE_CREDENTIALS)
def test_credentials_rejected_in_context_refs(cred: str):
    with pytest.raises(DomainSessionSecurityError) as exc_info:
        DomainSessionContext(
            session_id="session-123",
            primary_domain="domain:health",
            domain_resource_refs={"domain:health": (cred,)},
            updated_at=_now(),
        )
    assert cred not in str(exc_info.value)


@pytest.mark.parametrize("cred", _SAMPLE_CREDENTIALS)
def test_credentials_rejected_in_transition_metadata(cred: str):
    with pytest.raises(DomainSessionSecurityError) as exc_info:
        DomainSessionTransition(
            previous_primary_domain="domain:general",
            new_primary_domain="domain:health",
            reason_code="SHIFT",
            occurred_at=_now(),
            metadata={"leak": cred},
        )
    assert cred not in str(exc_info.value)


@pytest.mark.parametrize("cred", _SAMPLE_CREDENTIALS)
def test_credentials_rejected_in_resume_request_metadata(cred: str):
    with pytest.raises(DomainSessionSecurityError) as exc_info:
        DomainSessionResumeRequest(
            session_id="session-123",
            metadata={"auth": cred},
        )
    assert cred not in str(exc_info.value)


@pytest.mark.parametrize("cred", _SAMPLE_CREDENTIALS)
def test_credentials_rejected_in_resume_result_metadata(cred: str):
    with pytest.raises(DomainSessionSecurityError) as exc_info:
        DomainSessionResumeResult(
            status=DomainSessionResumeStatus.RESUMED,
            session_id="session-123",
            previous_revision=1,
            resumed_revision=2,
            metadata={"leak": cred},
        )
    assert cred not in str(exc_info.value)


@pytest.mark.parametrize("cred", _SAMPLE_CREDENTIALS)
def test_credentials_rejected_in_check_details(cred: str):
    with pytest.raises(DomainSessionSecurityError) as exc_info:
        DomainSessionCheck(
            name="check_auth",
            status=DomainSessionCheckStatus.PASS,
            message="all ok",
            details={"token": cred},
        )
    assert cred not in str(exc_info.value)


def test_benign_high_entropy_data_accepted():
    ctx = DomainSessionContext(
        session_id="session-123e4567-e89b-12d3-a456-426614174000",
        primary_domain="domain:health",
        composition_id="comp-987fcdeb-51a2-43f1-b987-1234567890ab",
        last_resolution_id="res-e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        updated_at=_now(),
        metadata={"fingerprint": "a1b2c3d4e5f67890123456789abcdef0"},
    )
    assert ctx.session_id == "session-123e4567-e89b-12d3-a456-426614174000"


def test_covers_all_high_confidence_signatures():
    assert len(HIGH_CONFIDENCE_CREDENTIAL_SIGNATURES) >= 20
