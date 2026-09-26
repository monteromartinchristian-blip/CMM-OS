"""Phase 11.22 — kernel event adapter, Domain and Validation bridge tests.

These tests prove the Phase 11.22 kernel adapter accepts real
``kernel.events.Event`` objects, translates only explicitly mapped names, copies
only safe facts, rejects unsafe content before persistence, and leaves the
Phase 10.33 Domain Event contract, the Phase 7 validation publisher and the
canonical workflow contract completely unchanged.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from cmm.events.event_payload_safety import PlatformEventPayloadError
from cmm.events.event_system import EventSystem
from cmm.events.kernel_adapter import PlatformKernelEventAdapter, SkippedKernelEvent
from kernel.events.event import Event as KernelEvent
from tests.events.test_phase11_22_event_system import build_system

MOMENT = datetime(2024, 5, 1, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def system() -> EventSystem:
    return build_system()


@pytest.fixture
def adapter(system: EventSystem) -> PlatformKernelEventAdapter:
    return PlatformKernelEventAdapter(system)


# ── Source validation ────────────────────────────────────────────────────────


def test_adapter_accepts_a_real_kernel_event(adapter, system) -> None:
    event = KernelEvent(
        name="validation.completed",
        payload={"validation_id": "val-1", "status": "passed"},
    )

    event_id = adapter.handle(event)

    assert event_id is not None
    stored = system.repository.get(event_id)
    assert stored is not None
    assert stored.header.event_type == "validation.completed"


def test_adapter_is_callable_as_a_kernel_listener(adapter, system) -> None:
    event = KernelEvent(name="validation.completed", payload={"validation_id": "val-1"})

    adapter(event)  # listener seam

    assert system.repository.count() == 1


def test_adapter_rejects_a_non_kernel_event(adapter) -> None:
    with pytest.raises(TypeError):
        adapter.handle("not a kernel event")  # type: ignore[arg-type]


def test_adapter_rejects_a_blank_kernel_event_name(adapter) -> None:
    with pytest.raises(ValueError):
        adapter.handle(KernelEvent(name="   ", payload={}))


def test_adapter_rejects_a_non_mapping_payload(adapter) -> None:
    with pytest.raises(PlatformEventPayloadError):
        adapter.handle(KernelEvent(name="validation.completed", payload=["not", "map"]))


def test_adapter_handles_a_none_payload(adapter, system) -> None:
    event_id = adapter.handle(KernelEvent(name="validation.completed", payload=None))

    assert event_id is not None
    assert system.repository.count() == 1


# ── Explicit mapping only ────────────────────────────────────────────────────


def test_unknown_source_names_are_not_guessed(adapter, system) -> None:
    event_id = adapter.handle(
        KernelEvent(name="mystery.event", payload={"status": "x"})
    )

    assert event_id is None
    assert system.repository.count() == 0
    assert adapter.skipped_events()[0].source_event_type == "mystery.event"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("validation.completed", "validation.completed"),
        ("validation.failed", "validation.completed"),
        ("domain.execution.completed", "operation.executed"),
        ("domain.resolution.completed", "domain.selected"),
        ("domain.approval.requested", "approval.requested"),
        ("domain.approval.received", "approval.resolved"),
        ("domain.memory.updated", "memory.updated"),
        ("workflow.started", "workflow.started"),
        ("workflow.running", "workflow.started"),
        ("workflow.paused", "workflow.paused"),
        ("workflow.completed", "workflow.completed"),
        ("workflow.failed", "workflow.failed"),
    ],
)
def test_mapped_sources_reach_their_platform_event(
    adapter, system, source, expected
) -> None:
    event_id = adapter.handle(
        KernelEvent(name=source, payload={"workflow_id": "wf-1", "status": "ok"})
    )

    assert event_id is not None
    assert system.repository.get(event_id).header.event_type == expected


@pytest.mark.parametrize(
    "source",
    [
        "validation.started",
        "validation.step.started",
        "validation.step.completed",
        "validation.gate.approved",
        "domain.execution.started",
        "domain.composition.created",
        "domain.conflict.detected",
        "domain.permission.requested",
        "domain.workflow.resumed",
        "node.completed",
        "custom.domain.specialized.event",
    ],
)
def test_unmapped_source_events_stay_unmodified_and_unpublished(
    adapter, system, source
) -> None:
    """Step-level and unrelated facts must not be accidentally remapped."""

    event_id = adapter.handle(KernelEvent(name=source, payload={"workflow_id": "wf-1"}))

    assert event_id is None
    assert system.repository.count() == 0
    assert len(adapter.skipped_events()) == 1


def test_mapping_copies_only_present_safe_facts(adapter, system) -> None:
    event_id = adapter.handle(
        KernelEvent(
            name="validation.completed",
            payload={
                "validation_id": "val-1",
                "status": "passed",
                "policy": "default",
                # Not a platform vocabulary key: read-only, never copied.
                "steps": [{"name": "step-1"}],
            },
        )
    )

    stored = system.repository.get(event_id)
    assert stored is not None
    assert stored.payload.data == {
        "validation_id": "val-1",
        "status": "passed",
        "policy": "default",
        "event_type": "validation.completed",
    }


def test_missing_fact_stays_missing(adapter, system) -> None:
    event_id = adapter.handle(
        KernelEvent(name="workflow.completed", payload={"workflow_id": "wf-1"})
    )

    stored = system.repository.get(event_id)
    assert stored is not None
    assert "status" not in stored.payload.data


# ── Safety before persistence ────────────────────────────────────────────────


def test_unsafe_source_content_fails_before_persistence(adapter, system) -> None:
    with pytest.raises(PlatformEventPayloadError):
        adapter.handle(
            KernelEvent(
                name="validation.completed",
                payload={
                    "validation_id": "val-1",
                    "status": "Bearer abcdefghijklmnop0123456789",
                },
            )
        )

    assert system.repository.count() == 0
    assert system.stats().published_total == 0


def test_credential_like_identifier_fails_before_persistence(adapter, system) -> None:
    with pytest.raises(PlatformEventPayloadError):
        adapter.handle(
            KernelEvent(
                name="domain.memory.updated",
                payload={"domain_id": "api_key", "status": "updated"},
            )
        )

    assert system.repository.count() == 0


def test_identifier_aliases_are_read_without_inventing_facts(adapter, system) -> None:
    event_id = adapter.handle(
        KernelEvent(name="validation.completed", payload={"id": "evt-alias"})
    )

    stored = system.repository.get(event_id)
    assert stored is not None
    # ``id`` is a canonical alias for the event identifier, never a payload fact.
    assert "id" not in stored.payload.data


def test_owner_identity_comes_from_the_catalog(adapter, system) -> None:
    cases = {
        "validation.completed": "cmm.validation",
        "domain.memory.updated": "cmm.domains",
        "workflow.completed": "cmm.workflows",
    }

    for source, owner in cases.items():
        event_id = adapter.handle(
            KernelEvent(name=source, payload={"workflow_id": "wf-1"})
        )
        stored = system.repository.get(event_id)
        assert stored is not None
        assert stored.header.producer == owner, source


def test_correlation_is_preserved_from_the_source_event(adapter, system) -> None:
    event_id = adapter.handle(
        KernelEvent(
            name="workflow.completed",
            payload={"workflow_id": "wf-correlation", "status": "completed"},
        )
    )

    stored = system.repository.get(event_id)
    assert stored is not None
    assert stored.header.correlation_id == "wf-correlation"
    assert stored.header.aggregate_id == "wf-correlation"


def test_skipped_event_record_is_immutable(adapter) -> None:
    adapter.handle(KernelEvent(name="mystery.event", payload={}))
    skipped = adapter.skipped_events()[0]

    assert isinstance(skipped, SkippedKernelEvent)
    # A frozen dataclass refuses attribute assignment.
    with pytest.raises(dataclasses.FrozenInstanceError):
        skipped.source_event_type = "other"  # type: ignore[misc]


def test_adapter_declares_no_routing_or_command_capability(adapter) -> None:
    for attribute in ("route", "execute", "command", "dispatch"):
        assert not hasattr(adapter, attribute), attribute


def test_adapter_publishes_through_the_canonical_facade(adapter, system) -> None:
    received = []
    system.subscribe(received.append, ["validation.completed"])

    adapter.handle(
        KernelEvent(name="validation.completed", payload={"validation_id": "v"})
    )

    assert len(received) == 1


# ── Domain Events (DP-033) bridge regression ─────────────────────────────────


def test_domain_publisher_accepts_the_phase11_22_adapter_as_its_listener(
    adapter, system
) -> None:
    from cmm.domains.event_adapters import adapt_memory_updated
    from cmm.domains.event_publisher import DomainKernelEventPublisher

    publisher = DomainKernelEventPublisher(event_listener=adapter)
    domain_event = adapt_memory_updated(
        update_id="update-1", domain_id="domain:general"
    )

    publisher.publish(domain_event)

    types = [event.header.event_type for event in system.repository.list()]
    assert "memory.updated" in types
    assert system.repository.count() >= 1


def test_domain_publisher_contract_is_unchanged_without_the_adapter() -> None:
    from cmm.domains.event_adapters import adapt_memory_updated
    from cmm.domains.event_publisher import DomainKernelEventPublisher

    publisher = DomainKernelEventPublisher()
    domain_event = adapt_memory_updated(
        update_id="update-2", domain_id="domain:general"
    )

    kernel_event = publisher.publish(domain_event)

    assert kernel_event.name == domain_event.event_type
    assert len(publisher.emitted_events) == 1


def test_unmapped_domain_event_remains_valid_and_unmodified(adapter, system) -> None:
    from cmm.domains.event_adapters import adapt_execution_started
    from cmm.domains.event_publisher import DomainKernelEventPublisher

    publisher = DomainKernelEventPublisher(event_listener=adapter)
    domain_event = adapt_execution_started(
        execution_id="execution-1", domain_id="domain:general"
    )

    kernel_event = publisher.publish(domain_event)

    # The Domain Event and its kernel projection are untouched...
    assert kernel_event.name == "domain.execution.started"
    assert publisher.emitted_events[-1] is kernel_event
    # ...and the adapter simply published no platform event for it.
    assert system.repository.count() == 0
    assert adapter.skipped_events()[0].source_event_type == "domain.execution.started"


def test_domain_events_remain_23_canonical_contracts() -> None:
    from cmm.domains.event_catalog import CANONICAL_DOMAIN_EVENTS

    assert len(CANONICAL_DOMAIN_EVENTS) == 23
    assert len(set(CANONICAL_DOMAIN_EVENTS)) == 23


def test_domain_event_package_has_no_runtime_bus_dependency() -> None:
    import cmm.domains.event_publisher as publisher_module

    source = publisher_module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        text = handle.read()

    assert "AgentRuntimeEventBus" not in text
    assert "runtime_event_bus" not in text


def test_domain_events_registry_still_validates_and_fails_closed() -> None:
    """The canonical registry keeps failing closed on an unknown event type."""

    from cmm.domains.errors import DomainEventValidationError
    from cmm.domains.event_contracts import DomainEvent
    from cmm.domains.event_registry import DEFAULT_DOMAIN_EVENT_REGISTRY
    from cmm.domains.identifiers import DomainId

    unknown = DomainEvent(
        event_id="e1",
        event_type="not.a.domain.event",
        schema_version="1.0.0",
        domain_id=DomainId(slug="general"),
        actor="system",
        occurred_at=MOMENT,
        sensitivity="internal",
    )

    with pytest.raises(DomainEventValidationError):
        DEFAULT_DOMAIN_EVENT_REGISTRY.validate_event(unknown)


# ── Validation bridge regression ─────────────────────────────────────────────


def _validation_result():
    from cmm.validation.results import ValidationResult, ValidationStatus

    return ValidationResult(
        id="val-1",
        status=ValidationStatus.PASSED,
        steps=(),
        policy="default",
        duration_ms=12.5,
    )


def test_validation_publisher_best_effort_policy_is_preserved(adapter, system) -> None:
    from cmm.validation.integration.events import KernelEventPublisher

    publisher = KernelEventPublisher(event_listener=adapter, policy="best_effort")
    published = publisher.publish_validation_events(_validation_result())

    assert "validation.completed" in published
    types = [event.header.event_type for event in system.repository.list()]
    assert types.count("validation.completed") == 1


def test_validation_step_events_are_not_remapped(adapter, system) -> None:
    from cmm.validation.integration.events import KernelEventPublisher
    from cmm.validation.results import ValidationResult, ValidationStatus

    result = ValidationResult(
        id="val-steps",
        status=ValidationStatus.PASSED,
        steps=(),
        policy="default",
    )
    publisher = KernelEventPublisher(event_listener=adapter)
    publisher.publish_validation_events(result)

    skipped = {event.source_event_type for event in adapter.skipped_events()}
    assert "validation.started" in skipped
    assert "validation.step.started" not in skipped  # no steps in this result
    assert "validation.completed" not in skipped


def test_validation_failure_maps_to_completed_with_its_own_status(
    adapter, system
) -> None:
    from cmm.validation.integration.events import KernelEventPublisher
    from cmm.validation.results import ValidationResult, ValidationStatus

    publisher = KernelEventPublisher(event_listener=adapter)
    publisher.publish_validation_events(
        ValidationResult(
            id="val-failed",
            status=ValidationStatus.FAILED,
            steps=(),
            policy="default",
        )
    )

    stored = system.repository.query(event_type="validation.completed")
    assert len(stored) == 1
    assert stored[0].payload.data["status"] == "failed"
    # No fabricated success event.
    assert (
        system.repository.query(event_type="validation.completed")[0].payload.data[
            "status"
        ]
        != "passed"
    )


def test_validation_strict_policy_still_fails_closed_on_listener_error() -> None:
    from cmm.validation.integration.events import KernelEventPublisher

    def broken_listener(event) -> None:
        raise RuntimeError("listener exploded")

    publisher = KernelEventPublisher(event_listener=broken_listener, policy="strict")

    with pytest.raises(RuntimeError):
        publisher.publish(*_direct_publish_args())


def test_validation_raw_internals_do_not_leak(adapter, system) -> None:
    from cmm.validation.integration.events import KernelEventPublisher

    publisher = KernelEventPublisher(event_listener=adapter)
    publisher.publish_validation_events(_validation_result())

    stored = system.repository.query(event_type="validation.completed")[0]
    serialized = str(dict(stored.payload.data))
    for token in ("prompt", "reasoning", "provider", "traceback", "secret"):
        assert token not in serialized


def _direct_publish_args():
    from cmm.validation.integration.contracts import ValidationEventPayload

    payload = ValidationEventPayload(
        event_type="validation.completed",
        validation_id="val-1",
        timestamp=MOMENT.isoformat(),
    )
    return "validation.completed", payload


# ── Workflow lifecycle integration ───────────────────────────────────────────


def test_workflow_owner_event_names_map_to_the_platform_catalog(
    adapter, system
) -> None:
    from cmm.workflows.contracts import WorkflowEvent

    for source, expected in (
        ("workflow.running", "workflow.started"),
        ("workflow.paused", "workflow.paused"),
        ("workflow.completed", "workflow.completed"),
        ("workflow.failed", "workflow.failed"),
    ):
        workflow_event = WorkflowEvent(
            event_id=f"evt-{source}",
            event_type=source,
            workflow_id="wf-1",
            run_id="run-1",
            occurred_at=MOMENT,
            data={},
        )
        kernel_event = KernelEvent(
            name=workflow_event.event_type,
            payload=workflow_event.to_dict(),
            timestamp=workflow_event.occurred_at,
        )

        event_id = adapter.handle(kernel_event)

        assert event_id is not None, source
        stored = system.repository.get(event_id)
        assert stored is not None
        assert stored.header.event_type == expected
        assert (
            stored.header.workflow_id == "wf-1" or "workflow_id" in stored.payload.data
        )


def test_workflow_lifecycle_facts_carry_workflow_identity(adapter, system) -> None:
    event_id = adapter.handle(
        KernelEvent(
            name="workflow.failed",
            payload={"workflow_id": "wf-9", "run_id": "run-9", "error_code": "E1"},
        )
    )

    stored = system.repository.get(event_id)
    assert stored is not None
    assert stored.payload.data["workflow_id"] == "wf-9"
    assert stored.payload.data["error_code"] == "E1"


def test_reserved_platform_events_are_never_emitted_by_the_adapter(
    adapter, system
) -> None:
    """The adapter has no mapping that could emit a reserved catalog event."""

    from cmm.events.event_catalog import RESERVED_PLATFORM_EVENT_NAMES
    from cmm.events.event_translation import (
        KERNEL_SOURCE_TRANSLATIONS,
        ORCHESTRATION_SOURCE_TRANSLATIONS,
    )

    for translation in (
        *KERNEL_SOURCE_TRANSLATIONS,
        *ORCHESTRATION_SOURCE_TRANSLATIONS,
    ):
        assert translation.platform_event_type not in RESERVED_PLATFORM_EVENT_NAMES
