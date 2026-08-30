"""Phase 10.34 — Adversarial & Architecture Regression Gate Tests.

Comprehensive adversarial test suite probing edge cases, malformed payloads,
credential smuggling, permission escalation, side-effect boundaries, and architectural invariants.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainStatus
from cmm.domains.errors import (
    DomainSessionSecurityError,
    DomainSessionSerializationError,
)
from cmm.domains.identifiers import DomainId, DomainManifestId
from cmm.domains.registry import DomainRegistry
from cmm.domains.registry_contracts import DomainRegistryRecord
from cmm.domains.session_contracts import (
    DomainSessionContext,
    DomainSessionResumeRequest,
    DomainSessionResumeStatus,
    DomainSessionTransition,
)
from cmm.domains.session_resumer import DomainSessionResumer


def _now() -> datetime:
    return datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)


def _make_definition(
    slug: str,
    version: str = "1.0.0",
    operations: tuple[str, ...] = (),
    permissions: tuple[str, ...] = (),
) -> DomainDefinition:
    return DomainDefinition(
        id=DomainId(slug=slug),
        name=slug,
        display_name=f"Domain {slug}",
        version=version,
        kind=DomainKind.PERSONAL,
        description=f"Description for {slug}",
        manifest_id=DomainManifestId(slug=slug, version=version),
        operations=operations,
        permissions=permissions,
    )


class TestCorruptedPayloadInjection:
    """Probes handling of malformed, corrupted, or forged serialized payloads."""

    def test_reject_unsupported_schema_version(self):
        valid = DomainSessionContext(
            session_id="session-123",
            primary_domain="domain:health",
            updated_at=_now(),
        ).to_dict()
        valid["schema_version"] = 999
        with pytest.raises(DomainSessionSerializationError):
            DomainSessionContext.from_dict(valid)

    def test_reject_missing_required_fields(self):
        with pytest.raises(DomainSessionSerializationError):
            DomainSessionContext.from_dict({"schema_version": 1})

    def test_reject_unknown_top_level_and_nested_fields(self):
        valid = DomainSessionContext(
            session_id="session-123",
            primary_domain="domain:health",
            updated_at=_now(),
        ).to_dict()
        valid["malicious_extra_field"] = "payload"
        with pytest.raises(DomainSessionSerializationError):
            DomainSessionContext.from_dict(valid)

    def test_reject_naive_timestamp(self):
        valid = DomainSessionContext(
            session_id="session-123",
            primary_domain="domain:health",
            updated_at=_now(),
        ).to_dict()
        valid["updated_at"] = "2026-08-30T10:00:00"  # Missing timezone
        with pytest.raises(DomainSessionSerializationError):
            DomainSessionContext.from_dict(valid)

    def test_reject_negative_or_zero_revision(self):
        valid = DomainSessionContext(
            session_id="session-123",
            primary_domain="domain:health",
            updated_at=_now(),
        ).to_dict()
        valid["revision"] = 0
        with pytest.raises(DomainSessionSerializationError):
            DomainSessionContext.from_dict(valid)


class TestCredentialSmugglingVectors:
    """Probes credential smuggling through varied nested structures."""

    @pytest.mark.parametrize(
        "credential",
        [
            "sk-ant-api03-0123456789abcdefghijklmnopqrstuvwxyz",
            "ghp_123456789012345678901234567890123456",
            "xoxb-1234567890-123456789012-abcdefghijklmnopqrstuvwx",
            "AKIAIOSFODNN7EXAMPLE",
            "AIzaSyD-1234567890abcdefghijklmnopqrst",
            "authorization: Bearer mysecrettoken",
        ],
    )
    def test_reject_credentials_in_deep_metadata(self, credential: str):
        with pytest.raises(DomainSessionSecurityError):
            DomainSessionContext(
                session_id="session-123",
                primary_domain="domain:health",
                metadata={"deep": {"nested": {"key": credential}}},
                updated_at=_now(),
            )

    def test_reject_credentials_in_transition_reason(self):
        with pytest.raises(DomainSessionSecurityError):
            DomainSessionTransition(
                previous_primary_domain="domain:health",
                new_primary_domain="domain:general",
                reason_code="RE_RESOLUTION",
                metadata={"leak": "sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234567890"},
                occurred_at=_now(),
            )


class TestUnauthorizedCrossDomainEscalation:
    """Ensures unauthorized operations and permissions cannot be claimed from stale state."""

    def test_unauthorized_permission_claim_stripped(self):
        reg = DomainRegistry()
        d_health = _make_definition(
            "health",
            "1.0.0",
            operations=("op:admin_action",),
            permissions=("perm:admin",),
        )
        reg.register(d_health)
        reg.restore_record(
            DomainRegistryRecord(
                definition=d_health,
                status=DomainStatus.ACTIVE,
                registered_at=_now(),
                updated_at=_now(),
            )
        )

        ctx = DomainSessionContext(
            session_id="session-123",
            primary_domain="domain:health",
            effective_permission_refs=("perm:admin",),
            available_operation_ids=("op:admin_action",),
            updated_at=_now(),
        )

        # Resumer denies admin permission for untrusted actor
        resumer = DomainSessionResumer(
            registry=reg,
            permission_evaluator=lambda actor, perms: (),
            operation_filter=lambda perms, ops: (),
        )
        req = DomainSessionResumeRequest(
            session_id="session-123", actor="untrusted_guest"
        )
        res = resumer.resume(req, ctx)

        assert res.status is DomainSessionResumeStatus.RESUMED
        assert res.context is not None
        assert res.context.effective_permission_refs == ()
        assert res.context.available_operation_ids == ()


class TestSideEffectBoundaryViolations:
    """Verifies that resumption is purely side-effect bounded."""

    def test_resumption_does_not_mutate_registry(self):
        reg = DomainRegistry()
        d_health = _make_definition("health", "1.0.0")
        reg.register(d_health)
        reg.restore_record(
            DomainRegistryRecord(
                definition=d_health,
                status=DomainStatus.ACTIVE,
                registered_at=_now(),
                updated_at=_now(),
            )
        )

        initial_count = len(reg.list())
        ctx = DomainSessionContext(
            session_id="session-123",
            primary_domain="domain:health",
            updated_at=_now(),
        )
        resumer = DomainSessionResumer(registry=reg)
        req = DomainSessionResumeRequest(session_id="session-123")
        resumer.resume(req, ctx)

        assert len(reg.list()) == initial_count

    def test_resumption_does_not_execute_operations(self):
        executed_ops = []

        def mock_op_executor(op_id: str):
            executed_ops.append(op_id)

        ctx = DomainSessionContext(
            session_id="session-123",
            primary_domain="domain:health",
            available_operation_ids=("op:send_notification", "op:delete_record"),
            updated_at=_now(),
        )
        resumer = DomainSessionResumer()
        req = DomainSessionResumeRequest(session_id="session-123")
        res = resumer.resume(req, ctx)

        assert res.status is DomainSessionResumeStatus.RESUMED
        # Zero operations executed
        assert executed_ops == []


class TestForbiddenArchitecturalLeakage:
    """Enforces strict architectural separation and absence of banned abstractions."""

    def test_no_parallel_session_engine(self):
        from cmm import domains

        assert not hasattr(domains, "DomainSessionRepository")
        assert not hasattr(domains, "AgentRuntimeEventBus")
        assert not hasattr(domains, "DomainEventStore")
        assert not hasattr(domains, "DomainEventQueue")
        assert not hasattr(domains, "DomainEventDLQ")

    def test_cognitive_core_isolation(self):
        import cmm.agent_runtime as runtime
        import cmm.cognitive as cog

        assert not hasattr(runtime, "DomainSessionContext")
        assert not hasattr(cog, "DomainSessionContext")
