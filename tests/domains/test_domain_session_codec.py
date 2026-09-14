"""Phase 10.34 — Domain Session Codec Tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from cmm.domains.errors import DomainSessionSerializationError
from cmm.domains.session_codec import (
    DOMAIN_SESSION_EXTENSION_KEY,
    DomainSessionCodec,
)
from cmm.domains.session_contracts import (
    DomainSessionContext,
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
                reason_code="USER_GOAL_SHIFT",
                occurred_at=_now(),
            ),
        ),
        last_resolution_id="res-123",
        next_recommended_step="step:evaluate",
        revision=1,
        updated_at=_now(),
        metadata={"channel": "cli"},
    )


def test_attach_and_extract_dict_session():
    codec = DomainSessionCodec()
    ctx = _sample_context()
    session_payload: dict[str, Any] = {
        "id": "session-123",
        "objective": "Help user with workout",
        "status": "active",
        "metadata": {},
    }

    attached = codec.attach_to_session(session_payload, ctx)
    assert DOMAIN_SESSION_EXTENSION_KEY in attached
    assert codec.is_domain_session_attached(attached)

    extracted = codec.extract_from_session(attached)
    assert extracted is not None
    assert extracted.session_id == ctx.session_id
    assert extracted.primary_domain == ctx.primary_domain
    assert extracted.supporting_domains == ctx.supporting_domains
    assert len(extracted.domain_transitions) == 1


def test_extract_missing_returns_none():
    codec = DomainSessionCodec()
    session_payload = {
        "id": "session-123",
        "objective": "Generic task",
        "status": "active",
    }
    assert not codec.is_domain_session_attached(session_payload)
    extracted = codec.extract_from_session(session_payload)
    assert extracted is None


def test_extract_malformed_fails_closed():
    codec = DomainSessionCodec()
    session_payload = {
        "id": "session-123",
        DOMAIN_SESSION_EXTENSION_KEY: {
            "schema_version": 1,
            "session_id": "session-123",
            # missing primary_domain and updated_at
        },
    }
    with pytest.raises(DomainSessionSerializationError):
        codec.extract_from_session(session_payload)


def test_extract_invalid_type_fails_closed():
    codec = DomainSessionCodec()
    session_payload = {
        "id": "session-123",
        DOMAIN_SESSION_EXTENSION_KEY: "invalid string payload",
    }
    with pytest.raises(DomainSessionSerializationError):
        codec.extract_from_session(session_payload)


def test_detach_from_session():
    codec = DomainSessionCodec()
    ctx = _sample_context()
    session_payload = {"id": "session-123"}
    attached = codec.attach_to_session(session_payload, ctx)
    assert codec.is_domain_session_attached(attached)

    detached = codec.detach_from_session(attached)
    assert not codec.is_domain_session_attached(detached)
    assert DOMAIN_SESSION_EXTENSION_KEY not in detached
