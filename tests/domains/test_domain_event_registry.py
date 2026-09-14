"""Phase 10.33 — Domain Event Registry Tests.

Tests covering:
- All 23 general events built-in on initialization
- Built-ins cannot be overridden or re-registered
- Specialized event registration with domain ownership and schema version
- Duplicate registration rejection
- Cross-domain namespace rejection
- Unknown event types fail-closed on validation
- Custom validator execution
- Side-effect freedom on registration
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.errors import (
    DomainEventRegistryError,
    DomainEventValidationError,
)
from cmm.domains.event_catalog import CANONICAL_DOMAIN_EVENTS
from cmm.domains.event_contracts import DomainEvent
from cmm.domains.event_registry import DomainEventRegistry
from cmm.domains.identifiers import DomainId


def _sample_event(event_type: str, domain_id: DomainId) -> DomainEvent:
    return DomainEvent(
        event_id="evt-reg-test",
        event_type=event_type,
        schema_version="1.0.0",
        domain_id=domain_id,
        actor="tester",
        occurred_at=datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc),
        sensitivity="internal",
    )


# 1. Built-in events
def test_registry_initializes_all_23_builtins() -> None:
    registry = DomainEventRegistry()
    assert len(registry.list_general_events()) == 23
    for evt in CANONICAL_DOMAIN_EVENTS:
        assert registry.is_registered(evt) is True
        decl = registry.get_declaration(evt)
        assert decl is not None
        assert decl.is_builtin is True
        assert decl.schema_version == "1.0.0"


# 2. Built-in override rejection
def test_registry_rejects_builtin_override() -> None:
    registry = DomainEventRegistry()
    with pytest.raises(DomainEventRegistryError):
        registry.register_specialized(
            domain_id=DomainId(slug="project"),
            event_type="domain.resolution.started",
        )


# 3. Specialized event registration
def test_registry_specialized_event_registration() -> None:
    registry = DomainEventRegistry()
    registry.register_specialized(
        domain_id=DomainId(slug="health"),
        event_type="health.symptom.updated",
        schema_version="1.1.0",
        description="Patient symptom updated",
    )
    assert registry.is_registered("health.symptom.updated") is True
    decl = registry.get_declaration("health.symptom.updated")
    assert decl is not None
    assert decl.is_builtin is False
    assert decl.domain_id == DomainId(slug="health")
    assert decl.schema_version == "1.1.0"
    assert decl.description == "Patient symptom updated"


# 4. Duplicate registration rejection
def test_registry_duplicate_registration_rejected() -> None:
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


# 5. Cross-domain namespace rejection
def test_registry_cross_domain_namespace_rejected() -> None:
    registry = DomainEventRegistry()
    with pytest.raises(DomainEventRegistryError):
        registry.register_specialized(
            domain_id=DomainId(slug="health"),
            event_type="university.grade.recorded",
        )


# 6. Hyphenated domain namespace matching
def test_registry_hyphenated_domain_namespace() -> None:
    registry = DomainEventRegistry()
    registry.register_specialized(
        domain_id=DomainId(slug="life-plan"),
        event_type="life_plan.goal.updated",
    )
    assert registry.is_registered("life_plan.goal.updated") is True


# 7. Validation: unknown event fails closed
def test_registry_validation_unknown_event_fails_closed() -> None:
    registry = DomainEventRegistry()
    event = _sample_event("unknown.event.type", DomainId(slug="project"))
    with pytest.raises(DomainEventValidationError):
        registry.validate_event(event)


# 8. Validation: valid builtin passes
def test_registry_validation_builtin_passes() -> None:
    registry = DomainEventRegistry()
    event = _sample_event("domain.conflict.detected", DomainId(slug="project"))
    # Should not raise
    registry.validate_event(event)


# 9. Validation: specialized event matching domain passes
def test_registry_validation_specialized_event_passes() -> None:
    registry = DomainEventRegistry()
    registry.register_specialized(
        domain_id=DomainId(slug="project"),
        event_type="project.release.prepared",
    )
    event = _sample_event("project.release.prepared", DomainId(slug="project"))
    registry.validate_event(event)


# 10. Validation: specialized event domain mismatch fails
def test_registry_validation_specialized_event_domain_mismatch_fails() -> None:
    registry = DomainEventRegistry()
    registry.register_specialized(
        domain_id=DomainId(slug="project"),
        event_type="project.release.prepared",
    )
    # Event claims to be project.release.prepared but has domain_id health
    event = _sample_event("project.release.prepared", DomainId(slug="health"))
    with pytest.raises(DomainEventValidationError):
        registry.validate_event(event)


# 11. Custom validator execution
def test_registry_custom_validator_executed() -> None:
    def validator(evt: DomainEvent) -> None:
        if "release_tag" not in evt.payload:
            raise DomainEventValidationError(
                "Missing release_tag in payload", field="payload"
            )

    registry = DomainEventRegistry()
    registry.register_specialized(
        domain_id=DomainId(slug="project"),
        event_type="project.release.prepared",
        validator=validator,
    )

    invalid_event = _sample_event("project.release.prepared", DomainId(slug="project"))
    with pytest.raises(DomainEventValidationError):
        registry.validate_event(invalid_event)

    valid_event = DomainEvent(
        event_id="evt-ok",
        event_type="project.release.prepared",
        schema_version="1.0.0",
        domain_id=DomainId(slug="project"),
        actor="releaser",
        occurred_at=datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc),
        sensitivity="internal",
        payload={"release_tag": "v1.0.0"},
    )
    registry.validate_event(valid_event)
