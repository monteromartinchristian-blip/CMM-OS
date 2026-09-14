"""Contract tests for atomic approval consumption repositories."""

from __future__ import annotations

import pytest

from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.errors import ApprovalAtomicityUnavailableError


class _NonAtomicApprovalRepository:
    """Deliberately incomplete backend: it offers no atomic boundary."""


def test_approval_repository_contract_requires_atomic_critical_section() -> None:
    with pytest.raises(ApprovalAtomicityUnavailableError):
        ApprovalService(_NonAtomicApprovalRepository())  # type: ignore[arg-type]
