"""Phase 10.34 — Domain Session Serialization Tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.errors import DomainSessionSerializationError
from cmm.domains.session_contracts import (
    DOMAIN_SESSION_SCHEMA_VERSION,
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


def _sample_context() -> DomainSessionContext:
    return DomainSessionContext(
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
        domain_transitions=(
            DomainSessionTransition(
                previous_primary_domain="domain:general",
                new_primary_domain="domain:health",
                previous_supporting_domains=(),
                new_supporting_domains=("domain:sport",),
                reason_code="USER_GOAL_SHIFT",
                resolution_id="res-123",
                composition_id="comp-123",
                occurred_at=_now(),
                metadata={"trigger": "user_message"},
            ),
        ),
        last_resolution_id="res-123",
        next_recommended_step="step:evaluate",
        revision=1,
        updated_at=_now(),
        metadata={"channel": "cli"},
    )


def test_round_trip_context():
    ctx = _sample_context()
    data = ctx.to_dict()
    assert data["schema_version"] == DOMAIN_SESSION_SCHEMA_VERSION
    assert data["session_id"] == "session-123"
    assert data["primary_domain"] == "domain:health"

    reconstructed = DomainSessionContext.from_dict(data)
    assert reconstructed.session_id == ctx.session_id
    assert reconstructed.primary_domain == ctx.primary_domain
    assert reconstructed.supporting_domains == ctx.supporting_domains
    assert reconstructed.domain_versions == ctx.domain_versions
    assert reconstructed.composition_id == ctx.composition_id
    assert reconstructed.effective_profile == ctx.effective_profile
    assert reconstructed.effective_rule_ids == ctx.effective_rule_ids
    assert reconstructed.effective_permission_refs == ctx.effective_permission_refs
    assert reconstructed.active_workflow_refs == ctx.active_workflow_refs
    assert reconstructed.available_operation_ids == ctx.available_operation_ids
    assert reconstructed.domain_resource_refs == ctx.domain_resource_refs
    assert reconstructed.domain_knowledge_refs == ctx.domain_knowledge_refs
    assert (
        reconstructed.pending_domain_question_refs == ctx.pending_domain_question_refs
    )
    assert reconstructed.domain_conflict_refs == ctx.domain_conflict_refs
    assert reconstructed.approval_refs == ctx.approval_refs
    assert reconstructed.partial_result_refs == ctx.partial_result_refs
    assert reconstructed.trace_refs == ctx.trace_refs
    assert len(reconstructed.domain_transitions) == 1
    assert reconstructed.last_resolution_id == ctx.last_resolution_id
    assert reconstructed.next_recommended_step == ctx.next_recommended_step
    assert reconstructed.revision == ctx.revision
    assert reconstructed.updated_at == ctx.updated_at
    assert reconstructed.metadata == ctx.metadata


def test_json_serialization_allow_nan_false():
    ctx = _sample_context()
    json_str = ctx.to_json()
    assert isinstance(json_str, str)
    # Check parse back from json
    reconstructed = DomainSessionContext.from_json(json_str)
    assert reconstructed.session_id == ctx.session_id


def test_reject_unknown_top_level_field():
    ctx = _sample_context()
    data = ctx.to_dict()
    data["unknown_evil_field"] = "malicious"
    with pytest.raises(DomainSessionSerializationError):
        DomainSessionContext.from_dict(data)


def test_reject_unsupported_schema_version():
    ctx = _sample_context()
    data = ctx.to_dict()
    data["schema_version"] = 999
    with pytest.raises(DomainSessionSerializationError):
        DomainSessionContext.from_dict(data)


def test_reject_missing_required_fields():
    ctx = _sample_context()
    data = ctx.to_dict()
    del data["session_id"]
    with pytest.raises(DomainSessionSerializationError):
        DomainSessionContext.from_dict(data)


def test_reject_naive_timestamp_in_from_dict():
    ctx = _sample_context()
    data = ctx.to_dict()
    data["updated_at"] = "2026-08-30T10:00:00"  # naive, no tz offset
    with pytest.raises(DomainSessionSerializationError):
        DomainSessionContext.from_dict(data)


def test_caller_mutation_isolation():
    raw_dict = {
        "schema_version": DOMAIN_SESSION_SCHEMA_VERSION,
        "session_id": "session-123",
        "primary_domain": "domain:health",
        "supporting_domains": ["domain:sport"],
        "domain_versions": {"domain:health": "1.0.0"},
        "composition_id": None,
        "effective_profile": None,
        "effective_rule_ids": [],
        "effective_permission_refs": [],
        "active_workflow_refs": [],
        "available_operation_ids": [],
        "domain_resource_refs": {"domain:health": ["res:1"]},
        "domain_knowledge_refs": {},
        "pending_domain_question_refs": [],
        "domain_conflict_refs": [],
        "approval_refs": [],
        "partial_result_refs": [],
        "trace_refs": [],
        "domain_transitions": [],
        "last_resolution_id": None,
        "next_recommended_step": None,
        "revision": 1,
        "updated_at": "2026-08-30T10:00:00+00:00",
        "metadata": {"key": "original"},
    }
    ctx = DomainSessionContext.from_dict(raw_dict)
    raw_dict["supporting_domains"].append("domain:mutated")
    raw_dict["domain_versions"]["domain:health"] = "9.9.9"
    raw_dict["metadata"]["key"] = "mutated"

    assert ctx.supporting_domains == ("domain:sport",)
    assert ctx.domain_versions["domain:health"] == "1.0.0"
    assert ctx.metadata["key"] == "original"


def test_round_trip_transition():
    tr = DomainSessionTransition(
        previous_primary_domain="domain:general",
        new_primary_domain="domain:health",
        previous_supporting_domains=(),
        new_supporting_domains=("domain:sport",),
        reason_code="USER_GOAL_SHIFT",
        resolution_id="res-123",
        composition_id="comp-123",
        occurred_at=_now(),
        metadata={"trigger": "user_message"},
    )
    data = tr.to_dict()
    reconstructed = DomainSessionTransition.from_dict(data)
    assert reconstructed.previous_primary_domain == tr.previous_primary_domain
    assert reconstructed.new_primary_domain == tr.new_primary_domain
    assert reconstructed.reason_code == tr.reason_code
    assert reconstructed.occurred_at == tr.occurred_at
    assert reconstructed.metadata == tr.metadata

    # Reject unknown field in transition
    data["unknown_field"] = "bad"
    with pytest.raises(DomainSessionSerializationError):
        DomainSessionTransition.from_dict(data)


def test_round_trip_check():
    chk = DomainSessionCheck(
        name="domain_check",
        status=DomainSessionCheckStatus.PASS,
        message="ok",
        blocking=False,
        details={"info": "valid"},
    )
    data = chk.to_dict()
    reconstructed = DomainSessionCheck.from_dict(data)
    assert reconstructed.name == chk.name
    assert reconstructed.status is chk.status
    assert reconstructed.message == chk.message
    assert reconstructed.blocking == chk.blocking
    assert reconstructed.details == chk.details

    # Reject unknown field
    data["unknown_field"] = "bad"
    with pytest.raises(DomainSessionSerializationError):
        DomainSessionCheck.from_dict(data)


def test_round_trip_resume_request():
    req = DomainSessionResumeRequest(
        session_id="session-123",
        actor="actor-1",
        temporal_reference=_now(),
        current_resource_versions={"res:1": "1.0"},
        current_knowledge_versions={"know:1": "2.0"},
        metadata={"m": "v"},
    )
    data = req.to_dict()
    reconstructed = DomainSessionResumeRequest.from_dict(data)
    assert reconstructed.session_id == req.session_id
    assert reconstructed.actor == req.actor
    assert reconstructed.temporal_reference == req.temporal_reference
    assert reconstructed.current_resource_versions == req.current_resource_versions

    data["unknown_field"] = "bad"
    with pytest.raises(DomainSessionSerializationError):
        DomainSessionResumeRequest.from_dict(data)


def test_round_trip_resume_result():
    res = DomainSessionResumeResult(
        status=DomainSessionResumeStatus.RESUMED,
        session_id="session-123",
        previous_revision=1,
        resumed_revision=2,
        context=_sample_context(),
        checks=(
            DomainSessionCheck(
                name="c1",
                status=DomainSessionCheckStatus.PASS,
                message="all ok",
            ),
        ),
        warnings=("warn1",),
        blocking_findings=(),
        recovered_question_refs=("q:1",),
        recovered_approval_refs=(),
        next_recommended_step="step:proceed",
        recorded_resumption=True,
        metadata={"res": "ok"},
    )
    data = res.to_dict()
    reconstructed = DomainSessionResumeResult.from_dict(data)
    assert reconstructed.status == res.status
    assert reconstructed.session_id == res.session_id
    assert reconstructed.previous_revision == res.previous_revision
    assert reconstructed.resumed_revision == res.resumed_revision
    assert reconstructed.context is not None
    assert reconstructed.context.session_id == res.context.session_id
    assert len(reconstructed.checks) == 1
    assert reconstructed.warnings == res.warnings
    assert reconstructed.recorded_resumption == res.recorded_resumption

    data["unknown_field"] = "bad"
    with pytest.raises(DomainSessionSerializationError):
        DomainSessionResumeResult.from_dict(data)
