"""Integration tests for Kernel Event Publisher (Subphase 7.13)."""

from cmm.validation.enums import ValidationStatus
from cmm.validation.integration.contracts import ValidationPhase, ValidationTrigger
from cmm.validation.integration.events import KernelEventPublisher
from cmm.validation.results import ValidationResult
from cmm.validation.steps import ValidationStepResult
from kernel.events.event import Event


def test_kernel_event_publisher_sequence():
    published_events: list[Event] = []

    def on_event(evt: Event) -> None:
        published_events.append(evt)

    publisher = KernelEventPublisher(event_listener=on_event, policy="strict")

    step = ValidationStepResult(
        name="syntax_check",
        status=ValidationStatus.PASSED,
        duration_ms=5,
    )
    val_result = ValidationResult(
        id="val-evt-123",
        status=ValidationStatus.PASSED,
        policy="default",
        steps=(step,),
        duration_ms=10,
    )

    trig = ValidationTrigger(
        phase=ValidationPhase.AFTER_EXECUTION,
        source="test",
        actor="test_user",
    )

    types = publisher.publish_validation_events(val_result, trigger=trig)

    assert types == [
        "validation.started",
        "validation.step.started",
        "validation.step.completed",
        "validation.completed",
    ]
    assert len(published_events) == 4
    assert published_events[0].name == "validation.started"
    assert published_events[0].payload["validation_id"] == "val-evt-123"
    assert published_events[0].payload["actor"] == "test_user"


def test_kernel_event_publisher_best_effort():
    def broken_listener(evt: Event) -> None:
        raise RuntimeError("Network event bus unavailable")

    publisher = KernelEventPublisher(
        event_listener=broken_listener, policy="best_effort"
    )

    val_result = ValidationResult(
        id="val-evt-456",
        status=ValidationStatus.PASSED,
        duration_ms=5,
    )

    # Should not raise exception under best_effort policy
    types = publisher.publish_validation_events(val_result)
    assert len(types) == 2
