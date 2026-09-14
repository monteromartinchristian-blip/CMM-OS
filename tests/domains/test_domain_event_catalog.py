"""Phase 10.33 — Domain Event Catalog and Namespace Tests.

Tests covering:
- Exact 23 canonical general domain events (membership & cardinality)
- Canonical domain namespace extraction (hyphen to underscore)
- Event type syntax validation
- Specialized event namespace validation
"""

from __future__ import annotations

import pytest

from cmm.domains.event_catalog import (
    CANONICAL_DOMAIN_EVENTS,
    CANONICAL_DOMAIN_EVENTS_SET,
    get_canonical_domain_namespace,
    is_canonical_general_event,
    validate_event_type_syntax,
    validate_specialized_event_namespace,
)
from cmm.domains.identifiers import DomainId

EXPECTED_23_EVENTS = (
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
)


def test_canonical_catalog_exact_cardinality_and_membership() -> None:
    assert len(CANONICAL_DOMAIN_EVENTS) == 23
    assert len(CANONICAL_DOMAIN_EVENTS_SET) == 23
    assert set(CANONICAL_DOMAIN_EVENTS) == set(EXPECTED_23_EVENTS)
    for evt in EXPECTED_23_EVENTS:
        assert is_canonical_general_event(evt) is True


def test_non_canonical_events_not_in_general_catalog() -> None:
    assert is_canonical_general_event("health.symptom.updated") is False
    assert is_canonical_general_event("domain.unknown.event") is False
    assert is_canonical_general_event("domain.resolution.other") is False


@pytest.mark.parametrize(
    ("domain_input", "expected_ns"),
    [
        (DomainId(slug="health"), "health"),
        (DomainId(slug="life-plan"), "life_plan"),
        (DomainId(slug="mental-health"), "mental_health"),
        (DomainId(slug="neurodivergence"), "neurodivergence"),
        ("domain:opposition", "opposition"),
        ("domain:project-management", "project_management"),
        ("sport", "sport"),
    ],
)
def test_get_canonical_domain_namespace(
    domain_input: DomainId | str, expected_ns: str
) -> None:
    assert get_canonical_domain_namespace(domain_input) == expected_ns


@pytest.mark.parametrize(
    ("event_name", "valid"),
    [
        ("domain.resolution.started", True),
        ("health.symptom.updated", True),
        ("life_plan.goal.updated", True),
        ("university.grade.recorded", True),
        ("project.release.prepared", True),
        ("InvalidEvent", False),
        ("domain..resolution", False),
        ("domain.resolution.", False),
        (".domain.resolution", False),
        ("domain resolution", False),
        ("domain:resolution", False),
    ],
)
def test_validate_event_type_syntax(event_name: str, valid: bool) -> None:
    assert validate_event_type_syntax(event_name) is valid


@pytest.mark.parametrize(
    ("event_name", "domain", "valid"),
    [
        ("health.symptom.updated", DomainId(slug="health"), True),
        ("health.medication.changed", DomainId(slug="health"), True),
        ("university.grade.recorded", DomainId(slug="university"), True),
        ("university.deadline.approaching", DomainId(slug="university"), True),
        ("opposition.mock_exam.completed", DomainId(slug="opposition"), True),
        ("life_plan.goal.updated", DomainId(slug="life-plan"), True),
        ("project.validation.failed", DomainId(slug="project"), True),
        ("project.release.prepared", DomainId(slug="project"), True),
        # Mismatched domain
        ("health.symptom.updated", DomainId(slug="university"), False),
        ("life_plan.goal.updated", DomainId(slug="health"), False),
        # General event is not a specialized event
        ("domain.resolution.started", DomainId(slug="health"), False),
    ],
)
def test_validate_specialized_event_namespace(
    event_name: str, domain: DomainId, valid: bool
) -> None:
    assert validate_specialized_event_namespace(event_name, domain) is valid
