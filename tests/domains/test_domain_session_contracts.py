"""Phase 10.34 — Domain Session Contracts Tests."""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from cmm.domains.errors import (
    DomainContractValidationError,
    DomainSessionContractError,
    DomainSessionError,
)
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
    return datetime.now(timezone.utc)


def test_domain_session_context_nominal():
    now = _now()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        supporting_domains=("domain:sport",),
        domain_versions={"domain:health": "1.0.0", "domain:sport": "1.2.0"},
        composition_id="comp-123",
        effective_profile="health-profile",
        effective_rule_ids=("rule:1", "rule:2"),
        effective_permission_refs=("perm:1",),
        active_workflow_refs=("wf:1",),
        available_operation_ids=("op:1", "op:2"),
        domain_resource_refs={"domain:health": ("res:1",)},
        domain_knowledge_refs={"domain:health": ("know:1",)},
        pending_domain_question_refs=("q:1",),
        domain_conflict_refs=("conf:1",),
        approval_refs=("appr:1",),
        partial_result_refs=("pres:1",),
        trace_refs=("tr:1",),
        domain_transitions=(),
        last_resolution_id="res-123",
        next_recommended_step="step:evaluate",
        revision=1,
        updated_at=now,
        metadata={"channel": "cli"},
    )

    assert ctx.session_id == "session-123"
    assert ctx.primary_domain == "domain:health"
    assert ctx.supporting_domains == ("domain:sport",)
    assert ctx.domain_versions == {"domain:health": "1.0.0", "domain:sport": "1.2.0"}
    assert isinstance(ctx.domain_versions, MappingProxyType)
    assert ctx.effective_rule_ids == ("rule:1", "rule:2")
    assert ctx.domain_resource_refs["domain:health"] == ("res:1",)
    assert isinstance(ctx.metadata, MappingProxyType)
    assert ctx.revision == 1
    assert ctx.updated_at == now


def test_domain_session_context_frozen_and_slotted():
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        updated_at=_now(),
    )
    with pytest.raises((AttributeError, TypeError)):
        ctx.session_id = "session-456"  # type: ignore

    with pytest.raises((AttributeError, TypeError)):
        ctx.new_attribute = "value"  # type: ignore


def test_domain_session_context_normalizes_and_deduplicates():
    now = _now()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        supporting_domains=("domain:sport", "domain:sport", "domain:general"),
        effective_rule_ids=("rule:1", "rule:1", "rule:2"),
        domain_resource_refs={"domain:health": ("res:1", "res:1", "res:2")},
        updated_at=now,
    )
    assert ctx.supporting_domains == ("domain:sport", "domain:general")
    assert ctx.effective_rule_ids == ("rule:1", "rule:2")
    assert ctx.domain_resource_refs["domain:health"] == ("res:1", "res:2")


def test_domain_session_context_validation_failures():
    now = _now()
    # Empty session_id
    with pytest.raises((DomainSessionContractError, DomainContractValidationError)):
        DomainSessionContext(
            session_id="",
            primary_domain="domain:health",
            updated_at=now,
        )

    # Empty primary_domain
    with pytest.raises((DomainSessionContractError, DomainContractValidationError)):
        DomainSessionContext(
            session_id="session-123",
            primary_domain="",
            updated_at=now,
        )

    # Invalid revision (< 1)
    with pytest.raises((DomainSessionContractError, DomainContractValidationError)):
        DomainSessionContext(
            session_id="session-123",
            primary_domain="domain:health",
            revision=0,
            updated_at=now,
        )

    # Naive updated_at
    with pytest.raises((DomainSessionContractError, DomainContractValidationError)):
        DomainSessionContext(
            session_id="session-123",
            primary_domain="domain:health",
            updated_at=datetime(2026, 1, 1, 12, 0, 0),  # noqa: DTZ001 - testing naive rejection
        )


def test_domain_session_transition_nominal():
    now = _now()
    tr = DomainSessionTransition(
        previous_primary_domain="domain:general",
        new_primary_domain="domain:health",
        previous_supporting_domains=(),
        new_supporting_domains=("domain:sport",),
        reason_code="USER_GOAL_SHIFT",
        resolution_id="res-123",
        composition_id="comp-123",
        occurred_at=now,
        metadata={"trigger": "user_message"},
    )
    assert tr.previous_primary_domain == "domain:general"
    assert tr.new_primary_domain == "domain:health"
    assert tr.reason_code == "USER_GOAL_SHIFT"
    assert tr.occurred_at == now
    assert isinstance(tr.metadata, MappingProxyType)


def test_domain_session_transition_validation():
    now = _now()
    # Empty new_primary_domain
    with pytest.raises((DomainSessionContractError, DomainContractValidationError)):
        DomainSessionTransition(
            previous_primary_domain=None,
            new_primary_domain="",
            reason_code="REASON",
            occurred_at=now,
        )

    # Empty reason_code
    with pytest.raises((DomainSessionContractError, DomainContractValidationError)):
        DomainSessionTransition(
            previous_primary_domain=None,
            new_primary_domain="domain:health",
            reason_code="",
            occurred_at=now,
        )

    # Naive occurred_at
    with pytest.raises((DomainSessionContractError, DomainContractValidationError)):
        DomainSessionTransition(
            previous_primary_domain=None,
            new_primary_domain="domain:health",
            reason_code="REASON",
            occurred_at=datetime(2026, 1, 1, 12, 0, 0),  # noqa: DTZ001 - testing naive rejection
        )


def test_domain_session_check_and_status():
    check = DomainSessionCheck(
        name="domain_active_check",
        status=DomainSessionCheckStatus.PASS,
        message="All domains active",
        blocking=False,
        details={"primary": "domain:health"},
    )
    assert check.name == "domain_active_check"
    assert check.status is DomainSessionCheckStatus.PASS
    assert check.blocking is False
    assert isinstance(check.details, MappingProxyType)

    # Empty check name
    with pytest.raises((DomainSessionContractError, DomainContractValidationError)):
        DomainSessionCheck(
            name="",
            status=DomainSessionCheckStatus.PASS,
            message="msg",
        )


def test_domain_session_resume_request_and_result():
    req = DomainSessionResumeRequest(
        session_id="session-123",
        actor="user-456",
        temporal_reference=_now(),
        current_resource_versions={"res:1": "v1.0"},
        current_knowledge_versions={"know:1": "v2.0"},
        metadata={"actor_kind": "user"},
    )
    assert req.session_id == "session-123"
    assert req.actor == "user-456"
    assert req.current_resource_versions == {"res:1": "v1.0"}
    assert isinstance(req.metadata, MappingProxyType)

    res = DomainSessionResumeResult(
        status=DomainSessionResumeStatus.RESUMED,
        session_id="session-123",
        previous_revision=1,
        resumed_revision=2,
        context=None,
        checks=(),
        warnings=(),
        blocking_findings=(),
        recovered_question_refs=(),
        recovered_approval_refs=(),
        next_recommended_step="step:continue",
        recorded_resumption=True,
    )
    assert res.status is DomainSessionResumeStatus.RESUMED
    assert res.resumed_revision == 2
    assert res.recorded_resumption is True


def test_error_hierarchy():
    assert issubclass(DomainSessionError, Exception)
    assert issubclass(DomainSessionContractError, DomainSessionError)
    assert issubclass(DomainSessionContractError, DomainContractValidationError)
