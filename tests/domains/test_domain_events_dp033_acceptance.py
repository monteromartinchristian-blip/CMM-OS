"""Phase 10.33 — AT-DP-033 Acceptance Test Gate.

66 comprehensive end-to-end checkpoints verifying all requirements of
Phase 10.33: Domain Events.
"""

from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from cmm.domains.composition_contracts import DomainComposition, DomainCompositionStatus
from cmm.domains.conflict_resolution import DomainConflictResolver
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
    adapt_approval_received,
    adapt_approval_requested,
    adapt_composition_created,
    adapt_composition_updated,
    adapt_conflict_detected,
    adapt_conflict_resolution,
    adapt_execution_failed,
    adapt_memory_proposed,
    adapt_memory_updated,
    adapt_operation_completed,
    adapt_operation_failed,
    adapt_operation_started,
    adapt_permission_denied,
    adapt_permission_requested,
    adapt_resolution_result,
    adapt_resolution_started,
    adapt_workflow_completed,
    adapt_workflow_paused,
    adapt_workflow_resumed,
    adapt_workflow_started,
)
from cmm.domains.event_catalog import (
    CANONICAL_DOMAIN_EVENTS,
    CANONICAL_DOMAIN_EVENTS_SET,
    get_canonical_domain_namespace,
)
from cmm.domains.event_contracts import DomainEvent, DomainEventReference
from cmm.domains.event_factory import DomainEventFactory
from cmm.domains.event_publisher import DomainKernelEventPublisher
from cmm.domains.event_registry import (
    DomainEventRegistry,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.lifecycle_bridge import DomainLifecycleEventBridge
from cmm.domains.resolver_contracts import DomainResolutionResult
from kernel.events.event import Event


def _make_conflict_ref(source_id: str = "ref-1") -> DomainConflictReference:
    return DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id=source_id,
        domain_id=DomainId(slug="health"),
        blocking=False,
        severity=DomainConflictSeverity.MATERIAL,
        authority_kind=DomainConflictAuthority.UNCLASSIFIED,
    )


# CP-01: Canonical general domain event catalog exact cardinality = 23 and exact membership
def test_cp01_canonical_catalog_exact_23() -> None:
    expected = {
        "domain.resolution.started",
        "domain.resolution.completed",
        "domain.resolution.ambiguous",
        "domain.composition.created",
        "domain.composition.updated",
        "domain.execution.started",
        "domain.execution.completed",
        "domain.execution.failed",
        "domain.conflict.detected",
        "domain.conflict.resolved",
        "domain.permission.requested",
        "domain.permission.denied",
        "domain.approval.requested",
        "domain.approval.received",
        "domain.memory.proposed",
        "domain.memory.updated",
        "domain.workflow.started",
        "domain.workflow.paused",
        "domain.workflow.resumed",
        "domain.workflow.completed",
        "domain.operation.started",
        "domain.operation.completed",
        "domain.operation.failed",
    }
    assert len(CANONICAL_DOMAIN_EVENTS) == 23
    assert len(CANONICAL_DOMAIN_EVENTS_SET) == 23
    assert set(CANONICAL_DOMAIN_EVENTS) == expected


# CP-02: DomainEvent immutability on root and nested payload/metadata
def test_cp02_domain_event_immutability() -> None:
    now = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    event = DomainEvent(
        event_id="evt-cp02",
        event_type="domain.resolution.completed",
        schema_version="1.0.0",
        domain_id=DomainId(slug="project"),
        actor="agent-1",
        occurred_at=now,
        sensitivity="internal",
        payload={"result": "ok", "sub": {"score": 1.0}},
        metadata={"source": "test"},
    )
    with pytest.raises((AttributeError, TypeError)):
        event.event_id = "mutated"  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        event.payload["result"] = "bad"  # type: ignore[index]
    with pytest.raises((AttributeError, TypeError)):
        event.payload["sub"]["score"] = 0.0  # type: ignore[index]
    with pytest.raises((AttributeError, TypeError)):
        event.metadata["source"] = "mutated"  # type: ignore[index]


# CP-03: DomainEventReference immutability and contract validation
def test_cp03_domain_event_reference_immutability_and_contract() -> None:
    ref = DomainEventReference(
        kind="resolution", reference_id="res-cp03", domain_id=DomainId(slug="project")
    )
    assert ref.kind == "resolution"
    assert ref.reference_id == "res-cp03"
    assert ref.domain_id == DomainId(slug="project")
    with pytest.raises((AttributeError, TypeError)):
        ref.kind = "other"  # type: ignore[misc]
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEventReference(kind="", reference_id="res-1")
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEventReference(kind="res", reference_id="")


# CP-04: Timezone awareness enforcement on occurred_at
def test_cp04_timezone_awareness_enforcement() -> None:
    naive_dt = datetime(2026, 8, 28, 12, 0, 0)  # noqa: DTZ001
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEvent(
            event_id="evt-cp04",
            event_type="domain.execution.started",
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor="agent-1",
            occurred_at=naive_dt,
            sensitivity="internal",
        )


# CP-05: Non-empty identifier validation for required event fields
@pytest.mark.parametrize("empty_val", ["", "   "])
def test_cp05_non_empty_identifier_validation(empty_val: str) -> None:
    now = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEvent(
            event_id=empty_val,
            event_type="domain.resolution.started",
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor="a",
            occurred_at=now,
            sensitivity="s",
        )
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEvent(
            event_id="e1",
            event_type=empty_val,
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor="a",
            occurred_at=now,
            sensitivity="s",
        )
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEvent(
            event_id="e1",
            event_type="domain.resolution.started",
            schema_version=empty_val,
            domain_id=DomainId(slug="project"),
            actor="a",
            occurred_at=now,
            sensitivity="s",
        )
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEvent(
            event_id="e1",
            event_type="domain.resolution.started",
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor=empty_val,
            occurred_at=now,
            sensitivity="s",
        )
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEvent(
            event_id="e1",
            event_type="domain.resolution.started",
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor="a",
            occurred_at=now,
            sensitivity=empty_val,
        )


# CP-06: Recursive credential and secret key rejection from payload
@pytest.mark.parametrize(
    "secret_key",
    [
        "password",
        "api_key",
        "apiKey",
        "secret",
        "token",
        "access_token",
        "auth_token",
        "private_key",
        "credential",
        "authorization",
        "cookie",
    ],
)
def test_cp06_recursive_secret_key_rejection(secret_key: str) -> None:
    now = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(DomainContractValidationError):
        DomainEvent(
            event_id="evt-cp06",
            event_type="domain.execution.started",
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor="agent-1",
            occurred_at=now,
            sensitivity="internal",
            payload={"deep": {"nested": {secret_key: "secret_value"}}},
        )


# CP-07: JSON-safety enforcement on payload and metadata
def test_cp07_json_safety_enforcement() -> None:
    now = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEvent(
            event_id="evt-cp07",
            event_type="domain.execution.started",
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor="agent-1",
            occurred_at=now,
            sensitivity="internal",
            payload={"non_finite": float("nan")},
        )


# CP-08: Reference-first provenance preservation
def test_cp08_reference_first_provenance() -> None:
    now = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    ref = DomainEventReference(
        kind="conflict_case", reference_id="case-100", domain_id=DomainId(slug="health")
    )
    event = DomainEvent(
        event_id="evt-cp08",
        event_type="domain.conflict.detected",
        schema_version="1.0.0",
        domain_id=DomainId(slug="health"),
        actor="resolver",
        occurred_at=now,
        provenance=(ref,),
        sensitivity="internal",
    )
    assert len(event.provenance) == 1
    assert event.provenance[0].kind == "conflict_case"
    assert event.provenance[0].reference_id == "case-100"


# CP-09: Deterministic round-trip serialization and deserialization
def test_cp09_deterministic_roundtrip_serialization() -> None:
    now = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    ref = DomainEventReference(
        kind="workflow_run", reference_id="wf-1", domain_id=DomainId(slug="project")
    )
    event = DomainEvent(
        event_id="evt-cp09",
        event_type="domain.workflow.started",
        schema_version="1.0.0",
        domain_id=DomainId(slug="project"),
        related_domain_ids=(DomainId(slug="general"), DomainId(slug="health")),
        actor="runner-1",
        session_id="sess-cp09",
        occurred_at=now,
        provenance=(ref,),
        sensitivity="internal",
        permissions=("domain.project.execute",),
        correlation_id="corr-cp09",
        causation_id="caus-cp09",
        payload={"workflow_id": "wf-1", "step_count": 3},
        metadata={"env": "test"},
    )
    serialized = event.to_dict()
    deserialized = DomainEvent.from_dict(serialized)
    assert deserialized == event
    assert deserialized.to_dict() == serialized


# CP-10: Unknown fields fail closed on deserialization
def test_cp10_unknown_fields_fail_closed_deserialization() -> None:
    now = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    event = DomainEvent(
        event_id="evt-cp10",
        event_type="domain.execution.started",
        schema_version="1.0.0",
        domain_id=DomainId(slug="project"),
        actor="agent-1",
        occurred_at=now,
        sensitivity="internal",
    )
    data = event.to_dict()
    data["extra_unknown_key"] = "malicious_or_unknown"
    with pytest.raises(DomainEventSerializationError):
        DomainEvent.from_dict(data)


# CP-11: Specialized event registration and namespace enforcement
def test_cp11_specialized_event_registration_and_namespace() -> None:
    registry = DomainEventRegistry()
    registry.register_specialized(
        domain_id=DomainId(slug="health"),
        event_type="health.symptom.updated",
        schema_version="1.0.0",
    )
    assert registry.is_registered("health.symptom.updated") is True
    decl = registry.get_declaration("health.symptom.updated")
    assert decl is not None
    assert decl.domain_id == DomainId(slug="health")
    assert decl.is_builtin is False


# CP-12: Canonical hyphenated domain namespace conversion (e.g. domain:life-plan -> life_plan.*)
def test_cp12_hyphenated_domain_namespace_conversion() -> None:
    assert get_canonical_domain_namespace(DomainId(slug="life-plan")) == "life_plan"
    assert get_canonical_domain_namespace("domain:mental-health") == "mental_health"
    registry = DomainEventRegistry()
    registry.register_specialized(
        domain_id=DomainId(slug="life-plan"),
        event_type="life_plan.goal.updated",
    )
    assert registry.is_registered("life_plan.goal.updated") is True


# CP-13: Duplicate specialized event registration rejection
def test_cp13_duplicate_specialized_registration_rejection() -> None:
    registry = DomainEventRegistry()
    registry.register_specialized(
        domain_id=DomainId(slug="university"),
        event_type="university.grade.recorded",
    )
    with pytest.raises(DomainEventRegistryError):
        registry.register_specialized(
            domain_id=DomainId(slug="university"),
            event_type="university.grade.recorded",
        )


# CP-14: Built-in general event override rejection
def test_cp14_builtin_override_rejection() -> None:
    registry = DomainEventRegistry()
    with pytest.raises(DomainEventRegistryError):
        registry.register_specialized(
            domain_id=DomainId(slug="project"),
            event_type="domain.resolution.completed",
        )


# CP-15: Cross-domain specialized event registration rejection
def test_cp15_cross_domain_registration_rejection() -> None:
    registry = DomainEventRegistry()
    with pytest.raises(DomainEventRegistryError):
        registry.register_specialized(
            domain_id=DomainId(slug="health"),
            event_type="opposition.mock_exam.completed",
        )


# CP-16: Unknown event types fail closed before publication
def test_cp16_unknown_event_types_fail_closed_on_publish() -> None:
    now = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    event = DomainEvent(
        event_id="evt-cp16",
        event_type="domain.unknown.unregistered_event",
        schema_version="1.0.0",
        domain_id=DomainId(slug="project"),
        actor="tester",
        occurred_at=now,
        sensitivity="internal",
    )
    publisher = DomainKernelEventPublisher()
    with pytest.raises(DomainEventValidationError):
        publisher.publish(event)
    assert len(publisher.emitted_events) == 0


# CP-17: Lossless conversion to kernel.events.Event
def test_cp17_kernel_event_conversion_lossless() -> None:
    now = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    ref = DomainEventReference(
        kind="operation_run", reference_id="op-1", domain_id=DomainId(slug="health")
    )
    event = DomainEvent(
        event_id="evt-cp17",
        event_type="domain.operation.completed",
        schema_version="1.0.0",
        domain_id=DomainId(slug="health"),
        actor="executor",
        occurred_at=now,
        provenance=(ref,),
        sensitivity="internal",
        permissions=("domain.health.execute",),
        payload={"operation_id": "op-1", "status": "completed"},
        metadata={"duration_ms": 120},
    )
    publisher = DomainKernelEventPublisher()
    kernel_evt = publisher.publish(event)

    assert isinstance(kernel_evt, Event)
    assert kernel_evt.name == "domain.operation.completed"
    assert kernel_evt.timestamp == now
    assert kernel_evt.payload == event.to_dict()


# CP-18: Publication does not mutate source event across repeated calls
def test_cp18_publication_immutability() -> None:
    now = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    event = DomainEvent(
        event_id="evt-cp18",
        event_type="domain.resolution.started",
        schema_version="1.0.0",
        domain_id=DomainId(slug="project"),
        actor="system",
        occurred_at=now,
        sensitivity="internal",
    )
    before_dict = event.to_dict()
    publisher = DomainKernelEventPublisher()
    publisher.publish(event)
    assert event.to_dict() == before_dict
    publisher.publish(event)
    assert event.to_dict() == before_dict
    assert len(publisher.emitted_events) == 2


# CP-19: Publication error handling wraps listener failures in DomainEventPublicationError
def test_cp19_publication_error_wrapping() -> None:
    now = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    event = DomainEvent(
        event_id="evt-cp19",
        event_type="domain.execution.started",
        schema_version="1.0.0",
        domain_id=DomainId(slug="project"),
        actor="system",
        occurred_at=now,
        sensitivity="internal",
    )

    def failing_listener(evt: Event) -> None:
        raise ConnectionError("Kernel unavailable")

    publisher = DomainKernelEventPublisher(event_listener=failing_listener)
    with pytest.raises(DomainEventPublicationError):
        publisher.publish(event)


# CP-20: Deterministic event factory with injected clock and id_factory
def test_cp20_deterministic_event_factory() -> None:
    fixed_time = datetime(2026, 8, 28, 18, 0, 0, tzinfo=timezone.utc)
    factory = DomainEventFactory(
        clock=lambda: fixed_time,
        id_factory=lambda: "evt-fixed-id-100",
    )
    event = factory.create_event(
        event_type="domain.workflow.completed",
        domain_id="domain:project",
        actor="orchestrator",
    )
    assert event.event_id == "evt-fixed-id-100"
    assert event.occurred_at == fixed_time
    assert event.domain_id == DomainId(slug="project")


# CP-21: Resolution lifecycle adaptation (started, completed, ambiguous)
def test_cp21_resolution_lifecycle_adaptation() -> None:
    evt_start = adapt_resolution_started("ctx-cp21", domain_id="domain:project")
    assert evt_start.event_type == "domain.resolution.started"

    res_ok = DomainResolutionResult(
        id="res-cp21-ok",
        context_id="ctx-cp21",
        status=DomainResolutionStatus.RESOLVED,
        primary_domain=DomainId(slug="project"),
        confidence=0.9,
    )
    evt_comp = adapt_resolution_result(res_ok)
    assert evt_comp.event_type == "domain.resolution.completed"

    res_amb = DomainResolutionResult(
        id="res-cp21-amb",
        context_id="ctx-cp21",
        status=DomainResolutionStatus.AMBIGUOUS,
        ambiguous_domains=(DomainId(slug="project"), DomainId(slug="health")),
        requires_clarification=True,
        recommended_question="Which domain is relevant?",
    )
    evt_amb = adapt_resolution_result(res_amb)
    assert evt_amb.event_type == "domain.resolution.ambiguous"


# CP-22: Composition lifecycle adaptation (created vs updated)
def test_cp22_composition_lifecycle_adaptation() -> None:
    comp1 = DomainComposition(
        id="comp-cp22-1",
        resolution_id="res-1",
        primary_domain=DomainId(slug="project"),
        status=DomainCompositionStatus.COMPOSED,
    )
    evt_created = adapt_composition_created(comp1)
    assert evt_created.event_type == "domain.composition.created"

    comp2 = DomainComposition(
        id="comp-cp22-2",
        resolution_id="res-1",
        primary_domain=DomainId(slug="project"),
        supporting_domains=(DomainId(slug="health"),),
        status=DomainCompositionStatus.COMPOSED,
    )
    evt_updated = adapt_composition_updated(comp1, comp2)
    assert evt_updated is not None
    assert evt_updated.event_type == "domain.composition.updated"

    # Identical recomputation returns None
    assert adapt_composition_updated(comp1, comp1) is None


# CP-23: Conflict detected lifecycle adaptation
def test_cp23_conflict_detected_adaptation() -> None:
    case = DomainConflictCase(
        id="case-cp23",
        domains=(DomainId(slug="health"), DomainId(slug="sport")),
        kind=DomainConflictKind.COMPOSITION,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(_make_conflict_ref("ref-cp23"),),
        blocking=False,
    )
    evt = adapt_conflict_detected(case)
    assert evt.event_type == "domain.conflict.detected"
    assert evt.domain_id == DomainId(slug="health")


# CP-24: Conflict resolved lifecycle emitted ONLY when semantically resolved
def test_cp24_conflict_resolved_adaptation_semantically_resolved() -> None:
    res = DomainConflictResolution(
        conflict_id="case-cp24",
        status=DomainConflictStatus.RESOLVED,
        strategy=DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE,
        winning_reference_ids=("ref-cp24",),
        reason_codes=(DomainConflictReasonCode.PRIMARY_PRECEDENCE,),
        can_proceed=True,
    )
    evt = adapt_conflict_resolution(res, primary_domain=DomainId(slug="project"))
    assert evt is not None
    assert evt.event_type == "domain.conflict.resolved"
    assert evt.payload["conflict_id"] == "case-cp24"
    assert evt.payload["can_proceed"] is True


# CP-25: Critical Invariant: maintain_conflict, postpone_action, ask_user, human_review NEVER emit resolved
def test_cp25_unresolved_conflict_outcomes_never_emit_resolved() -> None:
    # 1. Unresolved
    res_unres = DomainConflictResolution(
        conflict_id="c-unres",
        status=DomainConflictStatus.UNRESOLVED,
        strategy=DomainConflictStrategy.MAINTAIN_CONFLICT,
        conflict_preserved=True,
        preserved_reference_ids=("r1",),
        reason_codes=(DomainConflictReasonCode.PRESERVED,),
        can_proceed=False,
    )
    assert adapt_conflict_resolution(res_unres, primary_domain="domain:project") is None

    # 2. Postpone
    res_post = DomainConflictResolution(
        conflict_id="c-post",
        status=DomainConflictStatus.POSTPONED,
        strategy=DomainConflictStrategy.POSTPONE_ACTION,
        action_postponed=True,
        conflict_preserved=True,
        preserved_reference_ids=("r1",),
        reason_codes=(DomainConflictReasonCode.ACTION_POSTPONED,),
        can_proceed=False,
    )
    assert adapt_conflict_resolution(res_post, primary_domain="domain:project") is None

    # 3. Ask user
    res_user = DomainConflictResolution(
        conflict_id="c-user",
        status=DomainConflictStatus.AWAITING_USER,
        strategy=DomainConflictStrategy.ASK_USER,
        requires_user_input=True,
        conflict_preserved=True,
        preserved_reference_ids=("r1",),
        reason_codes=(DomainConflictReasonCode.USER_INPUT_REQUIRED,),
        can_proceed=False,
    )
    assert adapt_conflict_resolution(res_user, primary_domain="domain:project") is None

    # 4. Human review
    res_hr = DomainConflictResolution(
        conflict_id="c-hr",
        status=DomainConflictStatus.AWAITING_HUMAN_REVIEW,
        strategy=DomainConflictStrategy.HUMAN_REVIEW,
        requires_human_review=True,
        conflict_preserved=True,
        preserved_reference_ids=("r1",),
        reason_codes=(DomainConflictReasonCode.HUMAN_REVIEW_REQUIRED,),
        can_proceed=False,
    )
    assert adapt_conflict_resolution(res_hr, primary_domain="domain:project") is None

    # 5. Blocked
    res_blk = DomainConflictResolution(
        conflict_id="c-blk",
        status=DomainConflictStatus.BLOCKED,
        strategy=DomainConflictStrategy.MOST_RESTRICTIVE,
        conflict_preserved=True,
        preserved_reference_ids=("r1",),
        reason_codes=(DomainConflictReasonCode.SAFETY_PRECEDENCE,),
        can_proceed=False,
    )
    assert adapt_conflict_resolution(res_blk, primary_domain="domain:project") is None


# CP-26: Permission events cannot grant permissions or weaken fail-closed behavior
def test_cp26_permission_event_adaptation() -> None:
    evt_req = adapt_permission_requested(
        "domain.project.read", DomainId(slug="project")
    )
    assert evt_req.event_type == "domain.permission.requested"
    assert evt_req.permissions == ()
    assert evt_req.payload["capability"] == "domain.project.read"

    evt_den = adapt_permission_denied(
        "domain.project.read", DomainId(slug="project"), reason="denied"
    )
    assert evt_den.event_type == "domain.permission.denied"
    assert evt_den.permissions == ()
    assert evt_den.payload["capability"] == "domain.project.read"
    assert evt_den.payload["reason"] == "denied"


# CP-27: Approval events cannot decide approvals
def test_cp27_approval_event_adaptation() -> None:
    evt_req = adapt_approval_requested(
        "appr-cp27", DomainId(slug="project"), action="delete"
    )
    assert evt_req.event_type == "domain.approval.requested"

    evt_rec = adapt_approval_received(
        "appr-cp27", DomainId(slug="project"), approved=False, decision_by="manager"
    )
    assert evt_rec.event_type == "domain.approval.received"
    assert evt_rec.payload["approved"] is False


# CP-28: Memory proposed != memory updated
def test_cp28_memory_event_adaptation_proposed_vs_updated() -> None:
    evt_prop = adapt_memory_proposed("prop-cp28", DomainId(slug="reflection"))
    assert evt_prop.event_type == "domain.memory.proposed"

    evt_upd = adapt_memory_updated("upd-cp28", DomainId(slug="reflection"))
    assert evt_upd.event_type == "domain.memory.updated"
    assert evt_prop.event_type != evt_upd.event_type


# CP-29: Workflow and Operation lifecycle event adaptation
def test_cp29_workflow_and_operation_event_adaptation() -> None:
    assert (
        adapt_workflow_started("wf-1", DomainId(slug="project")).event_type
        == "domain.workflow.started"
    )
    assert (
        adapt_workflow_paused("wf-1", DomainId(slug="project")).event_type
        == "domain.workflow.paused"
    )
    assert (
        adapt_workflow_resumed("wf-1", DomainId(slug="project")).event_type
        == "domain.workflow.resumed"
    )
    assert (
        adapt_workflow_completed("wf-1", DomainId(slug="project")).event_type
        == "domain.workflow.completed"
    )

    assert (
        adapt_operation_started("op-1", DomainId(slug="health")).event_type
        == "domain.operation.started"
    )
    assert (
        adapt_operation_completed("op-1", DomainId(slug="health")).event_type
        == "domain.operation.completed"
    )
    assert (
        adapt_operation_failed("op-1", DomainId(slug="health"), error="fail").event_type
        == "domain.operation.failed"
    )


# CP-30: Pure DomainConflictResolver AST check (no event publisher/factory imports or side effects)
def test_cp30_conflict_resolver_remains_pure() -> None:
    path = Path("cmm/domains/conflict_resolution.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_modules = {
        "event_publisher",
        "event_factory",
        "event_contracts",
        "kernel.events",
        "time",
        "datetime",
        "uuid",
        "random",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for f in forbidden_modules:
                    assert f not in alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for f in forbidden_modules:
                assert f not in node.module


# CP-31: Domain Intelligence does NOT depend on AgentRuntimeEventBus
def test_cp31_no_agent_runtime_event_bus_dependency() -> None:
    event_files = [
        Path("cmm/domains/event_catalog.py"),
        Path("cmm/domains/event_contracts.py"),
        Path("cmm/domains/event_registry.py"),
        Path("cmm/domains/event_factory.py"),
        Path("cmm/domains/event_publisher.py"),
        Path("cmm/domains/event_adapters.py"),
    ]
    for file_path in event_files:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "runtime_event_bus" not in alias.name
                    assert "AgentRuntimeEventBus" not in alias.name
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert "runtime_event_bus" not in node.module
                for alias in node.names:
                    assert "AgentRuntimeEventBus" not in alias.name


# CP-32: Fresh import side-effect freedom
def test_cp32_fresh_import_side_effect_freedom() -> None:
    # Importing cmm.domains.event_registry must not mutate external state or trigger domain pack execution
    from cmm.domains import (
        CANONICAL_DOMAIN_EVENTS,
        DEFAULT_DOMAIN_EVENT_REGISTRY,
    )

    assert len(CANONICAL_DOMAIN_EVENTS) == 23
    assert len(DEFAULT_DOMAIN_EVENT_REGISTRY.list_general_events()) == 23


# CP-33: Custom registry validator enforcement
def test_cp33_custom_registry_validator_enforcement() -> None:
    registry = DomainEventRegistry()

    def symptom_validator(evt: DomainEvent) -> None:
        if "severity" not in evt.payload:
            raise DomainEventValidationError(
                "Symptom event requires severity in payload", field="payload"
            )

    registry.register_specialized(
        domain_id=DomainId(slug="health"),
        event_type="health.symptom.updated",
        validator=symptom_validator,
    )

    now = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    bad_evt = DomainEvent(
        event_id="evt-bad",
        event_type="health.symptom.updated",
        schema_version="1.0.0",
        domain_id=DomainId(slug="health"),
        actor="doctor",
        occurred_at=now,
        sensitivity="confidential",
        payload={"note": "headache"},
    )
    with pytest.raises(DomainEventValidationError):
        registry.validate_event(bad_evt)

    good_evt = DomainEvent(
        event_id="evt-good",
        event_type="health.symptom.updated",
        schema_version="1.0.0",
        domain_id=DomainId(slug="health"),
        actor="doctor",
        occurred_at=now,
        sensitivity="confidential",
        payload={"severity": "mild", "note": "headache"},
    )
    registry.validate_event(good_evt)


# CP-34: Privacy marker rejection in payload and metadata (B2)
def test_cp34_privacy_marker_rejection() -> None:
    now = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEvent(
            event_id="evt-cot",
            event_type="domain.resolution.started",
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor="system",
            occurred_at=now,
            sensitivity="internal",
            payload={"chain_of_thought": "private thinking"},
        )


# CP-35: Secret-like value rejection (B2)
def test_cp35_secret_like_value_rejection() -> None:
    now = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEvent(
            event_id="evt-sec",
            event_type="domain.resolution.started",
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor="system",
            occurred_at=now,
            sensitivity="internal",
            payload={"error": "Authorization: Bearer fake-secret-token-1234567890"},
        )


# CP-36: Safe failure-event representation (B2)
def test_cp36_safe_failure_event_representation() -> None:
    evt = adapt_operation_failed(
        operation_id="op-safe",
        domain_id="domain:project",
        error="Failed with Authorization: Bearer fake-token-1234567890",
    )
    assert "fake-token" not in str(evt.payload)
    assert "Authorization: Bearer" not in str(evt.payload)
    assert evt.payload["status"] == "failed"


# CP-37: Schema-version mismatch rejection (M1)
def test_cp37_schema_version_mismatch_rejection() -> None:
    registry = DomainEventRegistry()
    registry.register_specialized(
        domain_id="domain:project",
        event_type="project.release.prepared",
        schema_version="2.0.0",
    )
    now = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    mismatched = DomainEvent(
        event_id="evt-v1",
        event_type="project.release.prepared",
        schema_version="1.0.0",
        domain_id=DomainId(slug="project"),
        actor="system",
        occurred_at=now,
        sensitivity="internal",
    )
    with pytest.raises(DomainEventValidationError):
        registry.validate_event(mismatched)


# CP-38: Strict actor deserialization (M2)
def test_cp38_strict_actor_deserialization() -> None:
    data = {
        "event_id": "evt-act",
        "event_type": "domain.resolution.started",
        "schema_version": "1.0.0",
        "domain_id": {"slug": "project"},
        "actor": 12345,
        "occurred_at": "2026-08-28T12:00:00+00:00",
        "sensitivity": "internal",
    }
    with pytest.raises(
        (DomainEventSerializationError, DomainEventContractError, TypeError)
    ):
        DomainEvent.from_dict(data)


# CP-39: Strict permissions deserialization (M2)
def test_cp39_strict_permissions_deserialization() -> None:
    data = {
        "event_id": "evt-perm",
        "event_type": "domain.resolution.started",
        "schema_version": "1.0.0",
        "domain_id": {"slug": "project"},
        "actor": "system",
        "occurred_at": "2026-08-28T12:00:00+00:00",
        "sensitivity": "internal",
        "permissions": "read",
    }
    with pytest.raises((DomainEventSerializationError, DomainEventContractError)):
        DomainEvent.from_dict(data)


# CP-40: Invalid provenance rejection (M2)
def test_cp40_invalid_provenance_rejection() -> None:
    factory = DomainEventFactory()
    with pytest.raises(
        (DomainEventContractError, DomainContractValidationError, TypeError)
    ):
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id="domain:project",
            actor="system",
            provenance=(object(),),
        )


# CP-41: Invalid payload rejection (M2)
def test_cp41_invalid_payload_rejection() -> None:
    factory = DomainEventFactory()
    with pytest.raises(
        (DomainEventContractError, DomainContractValidationError, TypeError)
    ):
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id="domain:project",
            actor="system",
            payload=["invalid_list_payload"],
        )


# CP-42: Explicit empty event_id rejection (M2)
def test_cp42_explicit_empty_event_id_rejection() -> None:
    factory = DomainEventFactory()
    with pytest.raises((DomainEventContractError, DomainContractValidationError)):
        factory.create_event(
            event_type="domain.resolution.started",
            domain_id="domain:project",
            actor="system",
            event_id="",
        )


# CP-43: Permission effective-context isolation (M3)
def test_cp43_permission_effective_context_isolation() -> None:
    evt = adapt_permission_requested(
        capability="domain.project.write",
        domain_id="domain:project",
        actor="system",
    )
    assert evt.permissions == ()
    assert evt.payload["capability"] == "domain.project.write"


# CP-44: Failed-listener non-emission (M4)
def test_cp44_failed_listener_non_emission() -> None:
    def failing_listener(evt: Event) -> None:
        raise RuntimeError("Listener failure")

    publisher = DomainKernelEventPublisher(event_listener=failing_listener)
    now = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    event = DomainEvent(
        event_id="evt-pub-fail",
        event_type="domain.resolution.started",
        schema_version="1.0.0",
        domain_id=DomainId(slug="project"),
        actor="system",
        occurred_at=now,
        sensitivity="internal",
    )
    with pytest.raises(DomainEventPublicationError):
        publisher.publish(event)
    assert len(publisher.emitted_events) == 0


# CP-45: Real Kernel lifecycle integration (M5)
def test_cp45_real_kernel_lifecycle_integration() -> None:
    bridge = DomainLifecycleEventBridge()
    res = DomainResolutionResult(
        id="res-cp45",
        context_id="ctx-cp45",
        primary_domain=DomainId(slug="project"),
        status=DomainResolutionStatus.RESOLVED,
    )
    kernel_evt = bridge.emit_resolution_result(res)
    assert isinstance(kernel_evt, Event)
    assert kernel_evt.name == "domain.resolution.completed"
    assert len(bridge.publisher.emitted_events) == 1


# CP-46: Pure resolver dependency direction (M5)
def test_cp46_pure_resolver_dependency_direction() -> None:
    import cmm.domains.conflict_resolution as cr_mod

    source = Path(cr_mod.__file__).read_text(encoding="utf-8")
    assert "DomainKernelEventPublisher" not in source
    assert "DomainEventFactory" not in source
    assert "kernel.events" not in source
    assert "DomainLifecycleEventBridge" not in source


# CP-47: Implementation plan presence (m1)
def test_cp47_implementation_plan_presence() -> None:
    repo_root = Path(__file__).resolve().parent.parent.parent
    plan_path = (
        repo_root
        / "docs"
        / "superpowers"
        / "plans"
        / "2026-08-28-domain-events-implementation-plan.md"
    )
    assert plan_path.exists(), f"Plan must exist at {plan_path}"
    assert len(plan_path.read_text(encoding="utf-8").strip()) > 100


# CP-48: Top-level secret rejection across actor and permissions (B2)
def test_cp48_top_level_secret_rejection() -> None:
    now = datetime(2026, 8, 29, 12, 0, 0, tzinfo=timezone.utc)
    synthetic_key = "sk-" + "a" * 40
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEvent(
            event_id="evt-cp48-1",
            event_type="domain.resolution.started",
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor=synthetic_key,
            sensitivity="internal",
            occurred_at=now,
        )

    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEvent(
            event_id="evt-cp48-2",
            event_type="domain.resolution.started",
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor="system",
            sensitivity="internal",
            occurred_at=now,
            permissions=("Bearer secret1234567890",),
        )


# CP-49: DomainEventReference privacy rejection on kind and secret reference_id (B2)
def test_cp49_reference_privacy_rejection() -> None:
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEventReference(kind="system_prompt", reference_id="ref-cp49")

    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEventReference(
            kind="resolution", reference_id="Authorization: Bearer secret-token-xyz"
        )


# CP-50: Password, secret, credential, cookie, and token patterns rejection in payload and metadata (B2)
@pytest.mark.parametrize(
    "secret_dict",
    [
        {"pass": "password=supersecret"},
        {"cookie_val": "cookie: sessionid123456"},
        {"cred": "credential: admincred"},
        {"sec": "secret=mysecretkey"},
    ],
)
def test_cp50_expanded_secret_patterns_rejection(secret_dict: dict[str, str]) -> None:
    now = datetime(2026, 8, 29, 12, 0, 0, tzinfo=timezone.utc)
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEvent(
            event_id="evt-cp50-p",
            event_type="domain.resolution.started",
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor="system",
            sensitivity="internal",
            occurred_at=now,
            payload=secret_dict,
        )

    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEvent(
            event_id="evt-cp50-m",
            event_type="domain.resolution.started",
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor="system",
            sensitivity="internal",
            occurred_at=now,
            metadata=secret_dict,
        )


# CP-51: Safe failure adapter representation and comprehensive secret sanitization (B2)
def test_cp51_safe_failure_adapter_representation() -> None:
    evt_op = adapt_operation_failed(
        operation_id="op-cp51",
        domain_id="domain:project",
        error="Failure with password=hunter2 and Set-Cookie: cookie: secretcookie123",
        error_code="ERR_AUTH_FAILED",
        error_type="AuthenticationError",
    )
    assert evt_op.payload["status"] == "failed"
    assert evt_op.payload["error_code"] == "ERR_AUTH_FAILED"
    assert evt_op.payload["error_type"] == "AuthenticationError"
    error_str = str(evt_op.payload["error"])
    assert "hunter2" not in error_str
    assert "secretcookie123" not in error_str


# CP-52: Safe publisher listener failure wrapping without raw exception secret leakage (B2)
def test_cp52_safe_publisher_listener_failure() -> None:
    def failing_listener(evt: Event) -> None:
        raise RuntimeError(
            "Database connection error with Authorization: Bearer SECRET_PUB_KEY_999"
        )

    publisher = DomainKernelEventPublisher(event_listener=failing_listener)
    now = datetime(2026, 8, 29, 12, 0, 0, tzinfo=timezone.utc)
    event = DomainEvent(
        event_id="evt-cp52",
        event_type="domain.resolution.started",
        schema_version="1.0.0",
        domain_id=DomainId(slug="project"),
        actor="system",
        sensitivity="internal",
        occurred_at=now,
    )
    with pytest.raises(DomainEventPublicationError) as exc_info:
        publisher.publish(event)
    err_msg = str(exc_info.value)
    assert "SECRET_PUB_KEY_999" not in err_msg
    assert "Authorization: Bearer" not in err_msg


# CP-53: Strict session_id type validation and JSON safety (M2)
@pytest.mark.parametrize("invalid_id", [123, object(), ["bad"], {"bad": 1}, True])
def test_cp53_strict_session_id_type_validation(invalid_id: Any) -> None:
    now = datetime(2026, 8, 29, 12, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError, TypeError)
    ):
        DomainEvent(
            event_id="evt-cp53",
            event_type="domain.resolution.started",
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor="system",
            sensitivity="internal",
            occurred_at=now,
            session_id=invalid_id,
        )


# CP-54: Strict correlation_id type validation and JSON safety (M2)
@pytest.mark.parametrize("invalid_id", [123, object(), ["bad"], {"bad": 1}, True])
def test_cp54_strict_correlation_id_type_validation(invalid_id: Any) -> None:
    now = datetime(2026, 8, 29, 12, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError, TypeError)
    ):
        DomainEvent(
            event_id="evt-cp54",
            event_type="domain.resolution.started",
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor="system",
            sensitivity="internal",
            occurred_at=now,
            correlation_id=invalid_id,
        )


# CP-55: Strict causation_id type validation and JSON safety (M2)
@pytest.mark.parametrize("invalid_id", [123, object(), ["bad"], {"bad": 1}, True])
def test_cp55_strict_causation_id_type_validation(invalid_id: Any) -> None:
    now = datetime(2026, 8, 29, 12, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError, TypeError)
    ):
        DomainEvent(
            event_id="evt-cp55",
            event_type="domain.resolution.started",
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor="system",
            sensitivity="internal",
            occurred_at=now,
            causation_id=invalid_id,
        )


# CP-56: Full event JSON-safe round trip serialization with json.dumps (M2)
def test_cp56_json_safe_roundtrip_serialization() -> None:
    now = datetime(2026, 8, 29, 12, 0, 0, tzinfo=timezone.utc)
    event = DomainEvent(
        event_id="evt-cp56",
        event_type="domain.resolution.completed",
        schema_version="1.0.0",
        domain_id=DomainId(slug="project"),
        actor="agent-json",
        occurred_at=now,
        sensitivity="internal",
        session_id="session-cp56",
        correlation_id="corr-cp56",
        causation_id="cause-cp56",
        permissions=("read", "execute"),
        payload={"score": 0.98, "valid": True, "count": 10},
        metadata={"env": "testing"},
    )
    raw_dict = event.to_dict()
    dumped = json.dumps(raw_dict)
    assert isinstance(dumped, str)
    loaded = json.loads(dumped)
    assert loaded["session_id"] == "session-cp56"
    assert loaded["correlation_id"] == "corr-cp56"
    assert loaded["causation_id"] == "cause-cp56"


# CP-57: Real conflict bridge call-around execution with DomainConflictResolver (M5)
def test_cp57_real_conflict_bridge_call_around() -> None:
    published_events: list[Event] = []
    publisher = DomainKernelEventPublisher(event_listener=published_events.append)
    bridge = DomainLifecycleEventBridge(publisher=publisher)
    resolver = DomainConflictResolver()

    ref1 = DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id="ref-p",
        domain_id=DomainId(slug="project"),
        severity=DomainConflictSeverity.MATERIAL,
        authority_kind=DomainConflictAuthority.PRIMARY_DOMAIN,
    )
    ref2 = DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id="ref-s",
        domain_id=DomainId(slug="general"),
        severity=DomainConflictSeverity.MATERIAL,
        authority_kind=DomainConflictAuthority.UNCLASSIFIED,
    )
    case = DomainConflictCase(
        id="case-cp57",
        domains=(DomainId(slug="project"), DomainId(slug="general")),
        kind=DomainConflictKind.RECOMMENDATION,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref1, ref2),
    )

    resolution = bridge.resolve_conflict_with_events(
        resolver=resolver,
        case=case,
        primary_domain="domain:project",
    )
    assert resolution.status == DomainConflictStatus.RESOLVED
    assert len(published_events) == 2
    assert published_events[0].name == "domain.conflict.detected"
    assert published_events[1].name == "domain.conflict.resolved"


# CP-58: Primary-domain propagation and semantic effect in conflict bridge (M5)
def test_cp58_primary_domain_propagation_and_semantic_effect() -> None:
    bridge = DomainLifecycleEventBridge()
    resolver = DomainConflictResolver()

    ref_h = DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id="ref-health-win",
        domain_id=DomainId(slug="health"),
        severity=DomainConflictSeverity.MATERIAL,
        authority_kind=DomainConflictAuthority.PRIMARY_DOMAIN,
    )
    ref_p = DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id="ref-proj-loss",
        domain_id=DomainId(slug="project"),
        severity=DomainConflictSeverity.MATERIAL,
        authority_kind=DomainConflictAuthority.PRIMARY_DOMAIN,
    )
    case = DomainConflictCase(
        id="case-cp58",
        domains=(DomainId(slug="health"), DomainId(slug="project")),
        kind=DomainConflictKind.RECOMMENDATION,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref_h, ref_p),
    )

    res = bridge.resolve_conflict_with_events(
        resolver=resolver,
        case=case,
        primary_domain=DomainId(slug="health"),
    )
    assert res.winning_reference_ids == ("ref-health-win",)


# CP-59: Conflict bridge resolved-event emission semantic correctness (M5)
def test_cp59_unresolved_conflict_does_not_emit_resolved() -> None:
    published_events: list[Event] = []
    publisher = DomainKernelEventPublisher(event_listener=published_events.append)
    bridge = DomainLifecycleEventBridge(publisher=publisher)
    resolver = DomainConflictResolver()

    ref_a = DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id="ref-cp59-a",
        domain_id=DomainId(slug="project"),
        severity=DomainConflictSeverity.BLOCKING,
        authority_kind=DomainConflictAuthority.UNCLASSIFIED,
        blocking=True,
    )
    ref_b = DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id="ref-cp59-b",
        domain_id=DomainId(slug="general"),
        severity=DomainConflictSeverity.BLOCKING,
        authority_kind=DomainConflictAuthority.UNCLASSIFIED,
        blocking=True,
    )
    case = DomainConflictCase(
        id="case-cp59",
        domains=(DomainId(slug="project"), DomainId(slug="general")),
        kind=DomainConflictKind.RECOMMENDATION,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref_a, ref_b),
        blocking=True,
    )

    bridge.resolve_conflict_with_events(
        resolver=resolver,
        case=case,
        primary_domain="domain:project",
    )
    assert len(published_events) == 1
    assert published_events[0].name == "domain.conflict.detected"


# CP-60: Deterministic sequence ordering and rejection of unordered sets (m2)
def test_cp60_deterministic_sequence_ordering_and_set_rejection() -> None:
    now = datetime(2026, 8, 29, 12, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError, TypeError)
    ):
        DomainEvent(
            event_id="evt-cp60-set",
            event_type="domain.resolution.started",
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor="system",
            sensitivity="internal",
            occurred_at=now,
            related_domain_ids={DomainId(slug="health")},  # type: ignore[arg-type]
        )

    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError, TypeError)
    ):
        DomainEvent(
            event_id="evt-cp60-perm-set",
            event_type="domain.resolution.started",
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor="system",
            sensitivity="internal",
            occurred_at=now,
            permissions={"read"},  # type: ignore[arg-type]
        )


# CP-61: Explicit event_id privacy boundary enforcement (B2)
def test_cp61_explicit_event_id_privacy_boundary() -> None:
    now = datetime(2026, 8, 29, 12, 0, 0, tzinfo=timezone.utc)
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEvent(
            event_id="sk-" + "A" * 40,
            event_type="domain.resolution.started",
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor="system",
            sensitivity="internal",
            occurred_at=now,
        )

    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEvent(
            event_id="password=supersecret",
            event_type="domain.resolution.started",
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor="system",
            sensitivity="internal",
            occurred_at=now,
        )


# CP-62: Provenance reference_id privacy validation (B2)
def test_cp62_provenance_reference_id_privacy_validation() -> None:
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEventReference(kind="resolution", reference_id="system_prompt")

    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEventReference(
            kind="resolution", reference_id="raw_prompt: hidden instructions"
        )

    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEventReference(kind="resolution", reference_id="pii:user@example.com")


# CP-63: Recursive payload and metadata string value privacy validation (B2)
def test_cp63_recursive_payload_and_metadata_string_value_privacy() -> None:
    now = datetime(2026, 8, 29, 12, 0, 0, tzinfo=timezone.utc)
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEvent(
            event_id="evt-cp63-1",
            event_type="domain.resolution.started",
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor="system",
            sensitivity="internal",
            occurred_at=now,
            payload={"note": "system_prompt: secret instructions"},
        )

    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        DomainEvent(
            event_id="evt-cp63-2",
            event_type="domain.resolution.started",
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor="system",
            sensitivity="internal",
            occurred_at=now,
            metadata={"deep": {"list": ["safe", "chain_of_thought: reasoning"]}},
        )


# CP-64: Comprehensive multi-part Cookie and Set-Cookie header sanitization (B2)
def test_cp64_multi_part_cookie_sanitization() -> None:
    evt_cookie = adapt_operation_failed(
        operation_id="op-cp64",
        domain_id="domain:project",
        error="Cookie: foo=bar; sessionid=SECRET_SESSION_12345",
    )
    assert "SECRET_SESSION_12345" not in str(evt_cookie.payload)
    assert "sessionid" not in str(evt_cookie.payload)

    evt_set_cookie = adapt_execution_failed(
        execution_id="exec-cp64",
        domain_id="domain:project",
        error="Set-Cookie: a=b; csrftoken=SECRET_CSRF_67890",
    )
    assert "SECRET_CSRF_67890" not in str(evt_set_cookie.payload)
    assert "csrftoken" not in str(evt_set_cookie.payload)


# CP-65: Validation error non-disclosure invariant (B2)
def test_cp65_validation_error_nondisclosure_invariant() -> None:
    secret_text = "ULTRA_CONFIDENTIAL_INSTRUCTIONS_9999"
    with pytest.raises(
        (DomainContractValidationError, DomainEventContractError)
    ) as exc_info:
        DomainEventReference(
            kind="resolution",
            reference_id=f"system_prompt: {secret_text}",
        )
    assert secret_text not in str(exc_info.value)
    assert secret_text not in str(getattr(exc_info.value, "details", {}))


# CP-66: Kernel event publication boundary privacy guarantee (B2)
def test_cp66_kernel_publication_boundary_privacy_guarantee() -> None:
    publisher = DomainKernelEventPublisher()
    now = datetime(2026, 8, 29, 12, 0, 0, tzinfo=timezone.utc)
    with pytest.raises((DomainContractValidationError, DomainEventContractError)):
        bad_evt = DomainEvent(
            event_id="sk-" + "Z" * 40,
            event_type="domain.resolution.started",
            schema_version="1.0.0",
            domain_id=DomainId(slug="project"),
            actor="system",
            sensitivity="internal",
            occurred_at=now,
        )
        publisher.publish(bad_evt)
    assert len(publisher.emitted_events) == 0
