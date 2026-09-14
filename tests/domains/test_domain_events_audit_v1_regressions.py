"""Phase 10.33 independent audit V1 regression tests.

These tests encode findings B1, B2, M1, M2, M3, M4, M5, and m1 from the
independent audit of Phase 10.33 Domain Events.

They are intentionally added before production remediation and must be
observed RED on audited HEAD 009084d.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from cmm.domains.conflict_resolution_contracts import (
    DomainConflictAuthority,
    DomainConflictCase,
    DomainConflictKind,
    DomainConflictReasonCode,
    DomainConflictReference,
    DomainConflictResolution,
    DomainConflictSeverity,
    DomainConflictSourceKind,
    DomainConflictStatus,
    DomainConflictStrategy,
)
from cmm.domains.enums import DomainResolutionStatus
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainEventContractError,
    DomainEventPublicationError,
    DomainEventRegistryError,
    DomainEventSerializationError,
    DomainEventValidationError,
)
from cmm.domains.event_adapters import (
    adapt_execution_failed,
    adapt_operation_failed,
    adapt_permission_denied,
    adapt_permission_requested,
)
from cmm.domains.event_contracts import DomainEvent
from cmm.domains.event_factory import DomainEventFactory
from cmm.domains.event_publisher import DomainKernelEventPublisher
from cmm.domains.event_registry import DomainEventRegistry
from cmm.domains.identifiers import DomainId
from cmm.domains.resolver_contracts import DomainResolutionResult
from kernel.events.event import Event


def _sample_event(
    *,
    event_id: str = "evt-123",
    event_type: str = "domain.resolution.started",
    schema_version: str = "1.0.0",
    domain_id: DomainId | str = "domain:project",
    actor: str = "system",
    sensitivity: str = "internal",
    occurred_at: datetime | None = None,
    payload: Any = None,
    metadata: Any = None,
    permissions: Sequence[str] = (),
    provenance: Sequence[Any] = (),
) -> DomainEvent:
    dom = DomainId.from_str(domain_id) if isinstance(domain_id, str) else domain_id
    occ = occurred_at or datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    return DomainEvent(
        event_id=event_id,
        event_type=event_type,
        schema_version=schema_version,
        domain_id=dom,
        actor=actor,
        sensitivity=sensitivity,
        occurred_at=occ,
        payload=payload if payload is not None else {},
        metadata=metadata if metadata is not None else {},
        permissions=tuple(permissions),
        provenance=tuple(provenance),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCKER B1 — Repository secret ignore policy & no credential leak
# ═══════════════════════════════════════════════════════════════════════════════


def test_audit_v1_b1_gitignore_protects_env_files() -> None:
    """Verify repository .gitignore includes .env and .env.* patterns."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    gitignore_path = repo_root / ".gitignore"
    assert gitignore_path.exists(), ".gitignore must exist in repository root"
    content = gitignore_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines()]
    assert ".env" in lines, ".gitignore must contain .env"
    assert ".env.*" in lines, ".gitignore must contain .env.*"


# ═══════════════════════════════════════════════════════════════════════════════
# BLOCKER B2 — DomainEvent privacy boundary fail-closed & secret detection
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "forbidden_key",
    [
        "chain_of_thought",
        "chain-of-thought",
        "chainofthought",
        "hidden_reasoning",
        "reasoning_content",
        "raw_reasoning",
        "reasoning_text",
        "system_prompt",
        "developer_prompt",
        "private_prompt",
        "raw_prompt",
        "prompt",
        "pii",
        "credentials",
        "credential",
        "authorization",
        "authorization_header",
        "provider_request",
        "provider_response",
        "tool_arguments",
        "tool_response",
        "raw_content",
        "secret",
        "password",
        "api_key",
        "apikey",
        "auth_token",
        "cookie",
    ],
)
def test_audit_v1_b2_rejects_forbidden_privacy_keys_in_payload(
    forbidden_key: str,
) -> None:
    """Verify that forbidden privacy markers/keys are rejected from payload."""
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(payload={forbidden_key: "sample_value"})


@pytest.mark.parametrize(
    "forbidden_key",
    [
        "chain_of_thought",
        "system_prompt",
        "developer_prompt",
        "pii",
        "authorization_header",
        "provider_request",
        "tool_arguments",
    ],
)
def test_audit_v1_b2_rejects_forbidden_privacy_keys_in_metadata(
    forbidden_key: str,
) -> None:
    """Verify that forbidden privacy markers/keys are rejected from metadata."""
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(metadata={forbidden_key: "sample_value"})


def test_audit_v1_b2_rejects_nested_forbidden_keys() -> None:
    """Verify recursive scanning in nested mappings and sequences."""
    # Nested in mapping
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(payload={"nested": {"chain_of_thought": "private_reasoning"}})

    # Nested in list
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(payload={"items": [{"system_prompt": "secret"}]})

    # Nested in tuple
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(metadata={"tags": ({"pii": "user_id_123"},)})


@pytest.mark.parametrize(
    "secret_value",
    [
        "Authorization: Bearer fake-secret-token-abcdef123456",
        "Bearer fake-secret-token-abcdef123456",
        "sk-1234567890abcdef1234567890abcdef",
        "api_key=fake-key-abcdef1234567890",
        "session_token=fake-session-cookie-xyz123456",
    ],
)
def test_audit_v1_b2_rejects_secret_like_values_in_payload_and_metadata(
    secret_value: str,
) -> None:
    """Harmless keys containing dangerous secret-shaped values must be rejected."""
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(payload={"error_message": secret_value})

    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        _sample_event(metadata={"info": secret_value})


def test_audit_v1_b2_failure_adapters_sanitize_or_reject_raw_errors() -> None:
    """Failure adapters must sanitize or safely represent errors without leaking secrets."""
    # Safe error passes through adapter
    safe_evt = adapt_operation_failed(
        operation_id="op-1",
        domain_id="domain:project",
        error="File not found in project workspace",
    )
    assert safe_evt.payload["status"] == "failed"
    assert "File not found" in str(safe_evt.payload["error"])

    # Dangerous error containing Bearer token or secrets must not survive in payload
    dangerous_error = (
        "Request failed with Authorization: Bearer fake-token-1234567890abcdef"
    )
    adapted_evt = adapt_operation_failed(
        operation_id="op-2",
        domain_id="domain:project",
        error=dangerous_error,
    )
    # The payload must be safe: no Bearer token or authorization header allowed to survive
    for val in adapted_evt.payload.values():
        val_str = str(val)
        assert "Authorization: Bearer" not in val_str
        assert "fake-token" not in val_str

    dangerous_exec_error = "Execution failed with Bearer fake-exec-token-1234567890"
    exec_evt = adapt_execution_failed(
        execution_id="exec-1",
        domain_id="domain:project",
        error=dangerous_exec_error,
    )
    for val in exec_evt.payload.values():
        val_str = str(val)
        assert "fake-exec-token" not in val_str


# ═══════════════════════════════════════════════════════════════════════════════
# MAJOR M1 — Registry enforces declared schema version
# ═══════════════════════════════════════════════════════════════════════════════


def test_audit_v1_m1_specialized_schema_version_mismatch_fails() -> None:
    """Registry must reject specialized event when schema version does not match declaration."""
    registry = DomainEventRegistry()
    registry.register_specialized(
        domain_id="domain:project",
        event_type="project.release.prepared",
        schema_version="2.0.0",
    )

    event_v1 = _sample_event(
        event_type="project.release.prepared",
        schema_version="1.0.0",
        domain_id="domain:project",
    )
    with pytest.raises(DomainEventValidationError) as exc_info:
        registry.validate_event(event_v1)
    assert (
        "schema_version" in str(exc_info.value)
        or "schema version" in str(exc_info.value).lower()
    )

    event_v2 = _sample_event(
        event_type="project.release.prepared",
        schema_version="2.0.0",
        domain_id="domain:project",
    )
    # Matching version validates successfully
    registry.validate_event(event_v2)


def test_audit_v1_m1_builtin_schema_version_mismatch_fails() -> None:
    """Registry must reject built-in event when schema version does not match canonical 1.0.0."""
    registry = DomainEventRegistry()
    event_mismatch = _sample_event(
        event_type="domain.resolution.started",
        schema_version="2.0.0",
    )
    with pytest.raises(DomainEventValidationError):
        registry.validate_event(event_mismatch)


@pytest.mark.parametrize("invalid_version", ["", "   ", "v1", "beta", "1.0.0.0", "abc"])
def test_audit_v1_m1_registry_rejects_invalid_declaration_version(
    invalid_version: str,
) -> None:
    """Registry must reject empty, whitespace-only, or malformed schema versions."""
    registry = DomainEventRegistry()
    with pytest.raises(DomainEventRegistryError):
        registry.register_specialized(
            domain_id="domain:project",
            event_type="project.validation.failed",
            schema_version=invalid_version,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# MAJOR M2 — Deserialization and factory are fail-closed (no coercion)
# ═══════════════════════════════════════════════════════════════════════════════


def test_audit_v1_m2_from_dict_rejects_non_string_actor() -> None:
    """DomainEvent.from_dict must reject non-string actor without coercing str(123)."""
    data = {
        "event_id": "evt-123",
        "event_type": "domain.resolution.started",
        "schema_version": "1.0.0",
        "domain_id": {"slug": "project", "kind": "project"},
        "actor": 123,  # Invalid: int
        "occurred_at": "2026-08-28T12:00:00+00:00",
        "sensitivity": "internal",
    }
    with pytest.raises(
        (DomainEventSerializationError, DomainEventContractError, TypeError)
    ):
        DomainEvent.from_dict(data)


def test_audit_v1_m2_from_dict_rejects_scalar_string_permissions() -> None:
    """DomainEvent.from_dict must reject scalar string for permissions instead of tuple('read')."""
    data = {
        "event_id": "evt-123",
        "event_type": "domain.resolution.started",
        "schema_version": "1.0.0",
        "domain_id": {"slug": "project"},
        "actor": "system",
        "occurred_at": "2026-08-28T12:00:00+00:00",
        "sensitivity": "internal",
        "permissions": "read",  # Invalid: scalar string
    }
    with pytest.raises((DomainEventSerializationError, DomainEventContractError)):
        DomainEvent.from_dict(data)


def test_audit_v1_m2_from_dict_rejects_invalid_payload_type() -> None:
    """DomainEvent.from_dict must reject non-mapping payload (e.g. list)."""
    data = {
        "event_id": "evt-123",
        "event_type": "domain.resolution.started",
        "schema_version": "1.0.0",
        "domain_id": {"slug": "project"},
        "actor": "system",
        "occurred_at": "2026-08-28T12:00:00+00:00",
        "sensitivity": "internal",
        "payload": ["invalid", "list"],  # Invalid: list
    }
    with pytest.raises((DomainEventSerializationError, DomainEventContractError)):
        DomainEvent.from_dict(data)


def test_audit_v1_m2_factory_rejects_invalid_provenance_entry() -> None:
    """DomainEventFactory must reject unsupported provenance entry rather than silently ignoring it."""
    factory = DomainEventFactory()
    with pytest.raises(
        (DomainEventContractError, DomainContractValidationError, TypeError)
    ):
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id="domain:project",
            actor="system",
            provenance=(object(),),  # Invalid: raw object
        )


def test_audit_v1_m2_factory_rejects_invalid_payload_type() -> None:
    """DomainEventFactory must reject non-mapping payload rather than silently becoming {}."""
    factory = DomainEventFactory()
    with pytest.raises(
        (DomainEventContractError, DomainContractValidationError, TypeError)
    ):
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id="domain:project",
            actor="system",
            payload=[],  # Invalid: list
        )


def test_audit_v1_m2_factory_rejects_explicit_empty_event_id() -> None:
    """DomainEventFactory must reject explicit event_id='' instead of generating an ID."""
    factory = DomainEventFactory()
    with pytest.raises((DomainEventContractError, DomainContractValidationError)):
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id="domain:project",
            actor="system",
            event_id="",  # Explicit empty string
        )


# ═══════════════════════════════════════════════════════════════════════════════
# MAJOR M3 — Permission events misstate effective permissions
# ═══════════════════════════════════════════════════════════════════════════════


def test_audit_v1_m3_permission_requested_does_not_grant_capability() -> None:
    """adapt_permission_requested must NOT set permissions=(capability,)."""
    event = adapt_permission_requested(
        capability="domain.project.write",
        domain_id="domain:project",
        actor="system",
    )
    # The requested capability is in payload, NOT in permissions
    assert event.permissions == ()
    assert event.payload["capability"] == "domain.project.write"


def test_audit_v1_m3_permission_denied_does_not_expose_capability_as_effective() -> (
    None
):
    """adapt_permission_denied must NOT set permissions=(capability,)."""
    event = adapt_permission_denied(
        capability="domain.project.write",
        domain_id="domain:project",
        reason="Insufficient authority",
        actor="system",
    )
    assert event.permissions == ()
    assert event.payload["capability"] == "domain.project.write"
    assert event.payload["reason"] == "Insufficient authority"


def test_audit_v1_m3_permission_adapters_preserve_authoritative_effective_permissions() -> (
    None
):
    """When authoritative effective_permissions are supplied, they are preserved."""
    event_req = adapt_permission_requested(
        capability="domain.project.write",
        domain_id="domain:project",
        effective_permissions=("domain.project.read",),
    )
    assert event_req.permissions == ("domain.project.read",)

    event_den = adapt_permission_denied(
        capability="domain.project.write",
        domain_id="domain:project",
        reason="Denied by policy",
        effective_permissions=("domain.project.read",),
    )
    assert event_den.permissions == ("domain.project.read",)


# ═══════════════════════════════════════════════════════════════════════════════
# MAJOR M4 — Failed publication is not recorded as emitted
# ═══════════════════════════════════════════════════════════════════════════════


def test_audit_v1_m4_failed_publication_not_in_emitted_events() -> None:
    """When kernel listener raises, publisher raises DomainEventPublicationError and does NOT record event."""

    def failing_listener(evt: Event) -> None:
        raise RuntimeError("Kernel event bus connection dropped")

    publisher = DomainKernelEventPublisher(event_listener=failing_listener)
    event = _sample_event()

    with pytest.raises(DomainEventPublicationError):
        publisher.publish(event)

    assert len(publisher.emitted_events) == 0, (
        "Failed event must NOT be in emitted_events"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# MAJOR M5 — Real production path integrates lifecycle events with Kernel
# ═══════════════════════════════════════════════════════════════════════════════


def test_audit_v1_m5_lifecycle_bridge_integrates_resolution_lifecycle() -> None:
    """DomainLifecycleEventBridge orchestrates resolution lifecycle and emits Kernel events."""
    from cmm.domains.lifecycle_bridge import DomainLifecycleEventBridge

    published_events: list[Event] = []
    publisher = DomainKernelEventPublisher(event_listener=published_events.append)
    bridge = DomainLifecycleEventBridge(publisher=publisher)

    # Resolution result
    res_result = DomainResolutionResult(
        id="res-101",
        context_id="ctx-101",
        primary_domain=DomainId(slug="project"),
        status=DomainResolutionStatus.RESOLVED,
        confidence=0.95,
    )

    published = bridge.emit_resolution_result(res_result)
    assert isinstance(published, Event)
    assert published.name == "domain.resolution.completed"
    assert published.payload["payload"]["result_id"] == "res-101"
    assert len(publisher.emitted_events) == 1
    assert len(published_events) == 1


def test_audit_v1_m5_lifecycle_bridge_integrates_conflict_lifecycle() -> None:
    """DomainLifecycleEventBridge orchestrates conflict lifecycle and emits Kernel events."""
    from cmm.domains.lifecycle_bridge import DomainLifecycleEventBridge

    published_events: list[Event] = []
    publisher = DomainKernelEventPublisher(event_listener=published_events.append)
    bridge = DomainLifecycleEventBridge(publisher=publisher)

    # 1. Conflict detected
    ref = DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id="ref-1",
        domain_id=DomainId(slug="project"),
        severity=DomainConflictSeverity.MATERIAL,
        authority_kind=DomainConflictAuthority.PRIMARY_DOMAIN,
    )
    case = DomainConflictCase(
        id="case-101",
        domains=(DomainId(slug="project"), DomainId(slug="general")),
        kind=DomainConflictKind.RECOMMENDATION,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
    )

    det_evt = bridge.emit_conflict_detected(case)
    assert det_evt.name == "domain.conflict.detected"
    assert det_evt.payload["payload"]["conflict_id"] == "case-101"

    # 2. Conflict resolved
    resolution = DomainConflictResolution(
        conflict_id="case-101",
        status=DomainConflictStatus.RESOLVED,
        strategy=DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE,
        winning_reference_ids=("ref-1",),
        reason_codes=(DomainConflictReasonCode.PRIMARY_PRECEDENCE,),
        can_proceed=True,
    )
    res_evt = bridge.emit_conflict_resolution(
        resolution, primary_domain="domain:project"
    )
    assert res_evt is not None
    assert res_evt.name == "domain.conflict.resolved"
    assert res_evt.payload["payload"]["conflict_id"] == "case-101"
    assert len(publisher.emitted_events) == 2


def test_audit_v1_m5_pure_conflict_resolver_dependency_direction() -> None:
    """DomainConflictResolver must not import or depend on Domain Event publishers or Kernel events."""
    import cmm.domains.conflict_resolution as cr_mod

    source = Path(cr_mod.__file__).read_text(encoding="utf-8")
    assert "DomainKernelEventPublisher" not in source
    assert "DomainEventFactory" not in source
    assert "kernel.events" not in source
    assert "DomainLifecycleEventBridge" not in source


# ═══════════════════════════════════════════════════════════════════════════════
# MINOR m1 — Implementation plan document exists in repository
# ═══════════════════════════════════════════════════════════════════════════════


def test_audit_v1_m1_implementation_plan_document_exists() -> None:
    """The canonical implementation plan referenced by the roadmap must exist."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    plan_path = (
        repo_root
        / "docs"
        / "superpowers"
        / "plans"
        / "2026-08-28-domain-events-implementation-plan.md"
    )
    assert plan_path.exists(), f"Implementation plan must exist at {plan_path}"
    content = plan_path.read_text(encoding="utf-8")
    assert len(content.strip()) > 100
    assert "Phase 10.33" in content
    assert "Domain Events" in content
